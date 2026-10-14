"""Usage:
    pip install numpy pandas scikit-learn joblib matplotlib
    python train_solar_storm.py --data /mnt/data/data.txt

A positive label means Dst <= -50 nT at ANY of the NEXT 6 hours
(not including the present hour). The forecast is a geomagnetic-storm
proxy, not a prediction of solar flares or CME occurrence at the Sun.
"""
import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (average_precision_score, classification_report,
                             confusion_matrix, precision_recall_curve,
                             roc_auc_score)
from sklearn.pipeline import Pipeline

HEADERS = [
    "year", "day", "hour", "scalar", "BX_nT_GSE_GSM", "BY_nT_GSE",
    "BZ_nT_GSE", "BY_nT_GSM", "BZ_nT_GSM", "RMS_magnitude",
    "RMS_field_vector", "SW_Plasma_temp", "proton_dens", "plasma_speed",
    "flow_pressure", "electric_field", "Kp_index", "Dst_index", "AE_index",
]
HORIZON = 6
THRESHOLD_DST = -50


def load_data(path):
    df = pd.read_csv(path, sep=r"\s+", names=HEADERS, header=None,
                     comment="#", engine="c", on_bad_lines="error")
    if df.shape[1] != 19:
        raise ValueError(f"Expected 19 columns, got {df.shape[1]}")
    for c in HEADERS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.loc[df.year.between(1900, 2100) & df.day.between(1, 366)
                & df.hour.between(0, 23)].copy()
    dates = pd.to_datetime(df.year.astype(int).astype(str), format="%Y")
    df["timestamp"] = dates + pd.to_timedelta(df.day - 1, unit="D") + pd.to_timedelta(df.hour, unit="h")
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df = df.asfreq("h")  # Missing hours remain missing; don't shift time horizons.

    # Standard OMNI missing-data sentinels; verify these against your data provider.
    # Range guards also catch 9999.9, 99999, 9999999 etc.
    limits = {
        "scalar": (-100, 500), "BX_nT_GSE_GSM": (-500, 500),
        "BY_nT_GSE": (-500, 500), "BZ_nT_GSE": (-500, 500),
        "BY_nT_GSM": (-500, 500), "BZ_nT_GSM": (-500, 500),
        "RMS_magnitude": (0, 500), "RMS_field_vector": (0, 500),
        "SW_Plasma_temp": (0, 1e8), "proton_dens": (0, 1000),
        "plasma_speed": (0, 3000), "flow_pressure": (0, 1000),
        "electric_field": (-1000, 1000), "Kp_index": (0, 90),
        "Dst_index": (-1500, 500), "AE_index": (0, 10000),
    }
    for col, (lo, hi) in limits.items():
        df.loc[~df[col].between(lo, hi), col] = np.nan
    # Your Kp values appear to be Kp*10 (e.g. 17=1.7, 43=4.3).
    df["Kp"] = df["Kp_index"] / 10.0
    return df


def make_features_and_labels(df):
    raw = [c for c in HEADERS if c not in ("year", "day", "hour", "Kp_index")]
    raw.append("Kp")
    X = df[raw].copy()
    # A few physically motivated, present-time-only features.
    X["southward_Bz_GSM"] = (-df["BZ_nT_GSM"]).clip(lower=0)
    X["speed_times_southward_Bz"] = df["plasma_speed"] * X["southward_Bz_GSM"]
    X["hour_sin"] = np.sin(2 * np.pi * df.index.hour / 24)
    X["hour_cos"] = np.cos(2 * np.pi * df.index.hour / 24)
    X["doy_sin"] = np.sin(2 * np.pi * df.index.dayofyear / 365.25)
    X["doy_cos"] = np.cos(2 * np.pi * df.index.dayofyear / 365.25)

    lag_cols = ["BZ_nT_GSM", "plasma_speed", "proton_dens", "flow_pressure",
                "electric_field", "Dst_index", "AE_index", "Kp"]
    for col in lag_cols:
        for lag in (1, 3, 6, 12, 24):
            X[f"{col}_lag{lag}h"] = df[col].shift(lag)
        # Rolling window ends at the present hour; never uses future values.
        for hours in (3, 6, 12, 24):
            X[f"{col}_mean{hours}h"] = df[col].rolling(hours, min_periods=hours).mean()
            if col in ("BZ_nT_GSM", "Dst_index", "AE_index"):
                X[f"{col}_min{hours}h"] = df[col].rolling(hours, min_periods=hours).min()

    # Future Dst readings at t+1 ... t+6 (never t). A missing future
    # Dst means the sample is ineligible, rather than silently 'no storm'.
    future = pd.concat([df["Dst_index"].shift(-h) for h in range(1, HORIZON + 1)], axis=1)
    eligible = future.notna().all(axis=1) & df["Dst_index"].notna()
    y = future.le(THRESHOLD_DST).any(axis=1).astype(int)
    # At least one current solar-wind input should be present.
    eligible &= df[["BZ_nT_GSM", "plasma_speed"]].notna().all(axis=1)
    X = X.loc[eligible].replace([np.inf, -np.inf], np.nan)
    y = y.loc[eligible]
    return X, y


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data.txt")
    parser.add_argument("--out", default="solar_storm_model.joblib")
    args = parser.parse_args()
    df = load_data(args.data)
    X, y = make_features_and_labels(df)
    if len(X) < 1000:
        raise ValueError("Not enough eligible hourly records")

    # Chronological train / validation / test, with a 6h embargo at boundaries.
    n = len(X)
    i, j = int(n * 0.70), int(n * 0.85)
    gap = HORIZON
    X_train, y_train = X.iloc[:i-gap], y.iloc[:i-gap]
    X_val, y_val = X.iloc[i:j-gap], y.iloc[i:j-gap]
    X_test, y_test = X.iloc[j:], y.iloc[j:]
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("classifier", HistGradientBoostingClassifier(
            max_iter=250, learning_rate=0.05, max_leaf_nodes=15,
            l2_regularization=5.0, min_samples_leaf=50, random_state=42)),
    ])
    model.fit(X_train, y_train)
    val_prob = model.predict_proba(X_val)[:, 1]
    # Choose decision threshold using validation only (never test).
    precision, recall, thresholds = precision_recall_curve(y_val, val_prob)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    decision_threshold = float(thresholds[np.argmax(f1)]) if len(thresholds) else 0.5

    test_prob = model.predict_proba(X_test)[:, 1]
    test_pred = (test_prob >= decision_threshold).astype(int)
    print(f"Data: {df.index.min()} to {df.index.max()} | eligible hours: {n:,}")
    for name, yy in (("train", y_train), ("validation", y_val), ("test", y_test)):
        print(f"{name}: {len(yy):,} hours; storm-label rate: {yy.mean():.2%}")
    print(f"Chosen threshold from validation: {decision_threshold:.3f}")
    print("Test confusion matrix [[TN, FP], [FN, TP]]:\n", confusion_matrix(y_test, test_pred))
    print(classification_report(y_test, test_pred, zero_division=0))
    print(f"Test PR-AUC (average precision): {average_precision_score(y_test, test_prob):.4f}")
    if y_test.nunique() == 2:
        print(f"Test ROC-AUC: {roc_auc_score(y_test, test_prob):.4f}")
    print(f"Baseline positive rate: {y_test.mean():.4f}")

    out = Path(args.out)
    joblib.dump({"pipeline": model, "columns": X.columns.tolist(),
                 "threshold": decision_threshold, "horizon_hours": HORIZON,
                 "storm_dst_threshold": THRESHOLD_DST}, out)
    pd.DataFrame({"timestamp": X_test.index, "actual_storm_next_6h": y_test.values,
                  "predicted_probability": test_prob,
                  "predicted_storm": test_pred}).to_csv(out.with_suffix(".predictions.csv"), index=False)
    print(f"Saved model: {out}; test predictions: {out.with_suffix('.predictions.csv')}")


if __name__ == "__main__":
    main()