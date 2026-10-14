"""Predict geomagnetic storm risk using the previously trained joblib model.

Run:
  python predict_solar_storm.py --data data.txt --model solar_storm_model.joblib
  python predict_solar_storm.py --data data.txt --at '2026-09-13 12:00'
  python predict_solar_storm.py --data data.txt --all --output storm_forecasts.csv

The model estimates P(any Dst <= -50 nT during t+1 through t+6).
Only use joblib models from trusted sources; joblib loading can execute code.
"""
import argparse
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from train_solar_storm import load_data, HEADERS


def build_features(df):
    """Replicate the exact training feature engineering without needing future labels."""
    raw = [c for c in HEADERS if c not in ('year', 'day', 'hour', 'Kp_index')]
    raw.append('Kp')
    X = df[raw].copy()
    X['southward_Bz_GSM'] = (-df['BZ_nT_GSM']).clip(lower=0)
    X['speed_times_southward_Bz'] = df['plasma_speed'] * X['southward_Bz_GSM']
    X['hour_sin'] = np.sin(2 * np.pi * df.index.hour / 24)
    X['hour_cos'] = np.cos(2 * np.pi * df.index.hour / 24)
    X['doy_sin'] = np.sin(2 * np.pi * df.index.dayofyear / 365.25)
    X['doy_cos'] = np.cos(2 * np.pi * df.index.dayofyear / 365.25)
    lag_cols = ['BZ_nT_GSM', 'plasma_speed', 'proton_dens', 'flow_pressure',
                'electric_field', 'Dst_index', 'AE_index', 'Kp']
    for col in lag_cols:
        for lag in (1, 3, 6, 12, 24):
            X[f'{col}_lag{lag}h'] = df[col].shift(lag)
        for hours in (3, 6, 12, 24):
            X[f'{col}_mean{hours}h'] = df[col].rolling(hours, min_periods=hours).mean()
            if col in ('BZ_nT_GSM', 'Dst_index', 'AE_index'):
                X[f'{col}_min{hours}h'] = df[col].rolling(hours, min_periods=hours).min()
    return X.replace([np.inf, -np.inf], np.nan)


def predict(data_path, model_path, at=None, all_rows=False, output=None):
    bundle = joblib.load(model_path)
    model = bundle['pipeline']
    cols = bundle['columns']
    threshold = float(bundle['threshold'])
    horizon = int(bundle['horizon_hours'])
    dst_limit = int(bundle['storm_dst_threshold'])
    df = load_data(data_path)
    if len(df) < 25:
        raise ValueError('At least 25 hourly timestamps are recommended to construct 24-hour history.')
    X = build_features(df)
    missing = set(cols) - set(X.columns)
    if missing:
        raise ValueError(f'Features missing from input: {sorted(missing)}')
    X = X[cols]  # exact same feature names/order as training
    # Ensure current hour has the key solar-wind measurements.
    valid = df[['BZ_nT_GSM', 'plasma_speed']].notna().all(axis=1)
    if at is not None:
        timestamp = pd.Timestamp(at)
        if timestamp not in X.index:
            raise ValueError(f'{timestamp} is not in the hourly dataset ({X.index.min()} to {X.index.max()})')
        selected = X.loc[[timestamp]]
        if not bool(valid.loc[timestamp]):
            raise ValueError('Selected hour has missing Bz GSM or solar wind speed.')
    elif all_rows:
        selected = X.loc[valid & (X.index >= X.index.min() + pd.Timedelta(hours=24))]
    else:
        candidates = X.index[valid & (X.index >= X.index.min() + pd.Timedelta(hours=24))]
        if len(candidates) == 0:
            raise ValueError('No eligible forecast timestamp available.')
        selected = X.loc[[candidates[-1]]]
    if selected.empty:
        raise ValueError('No eligible forecast rows found.')
    probabilities = model.predict_proba(selected)[:, 1]
    results = pd.DataFrame({
        'forecast_issued_utc': selected.index,
        'forecast_window_start_utc': selected.index + pd.Timedelta(hours=1),
        'forecast_window_end_utc': selected.index + pd.Timedelta(hours=horizon),
        'storm_probability': probabilities,
        'storm_probability_percent': np.round(probabilities * 100, 2),
        'predicted_storm': probabilities >= threshold,
    })
    if output:
        results.to_csv(output, index=False)
        print(f'Saved {len(results):,} forecasts to {output}')
    if not all_rows:
        row = results.iloc[0]
        print(f"Forecast issued (UTC): {row['forecast_issued_utc']}")
        print(f"Forecast period (UTC): {row['forecast_window_start_utc']} to {row['forecast_window_end_utc']}")
        print(f'Event: Dst <= {dst_limit} nT at any hour in forecast period')
        print(f"Storm probability: {row['storm_probability_percent']:.2f}%")
        print(f'Decision threshold: {threshold:.3f}')
        print(f"Prediction: {'STORM' if row['predicted_storm'] else 'NO STORM'}")
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--data', default='data.txt')
    parser.add_argument('--model', default='solar_storm_model.joblib')
    parser.add_argument('--at', help='Specific UTC hour, e.g. "2026-09-13 12:00"')
    parser.add_argument('--all', action='store_true', help='Predict for all eligible historical timestamps')
    parser.add_argument('--output', help='Optional output CSV filename')
    args = parser.parse_args()
    if args.at and args.all:
        parser.error('--at and --all cannot be used together')
    predict(args.data, args.model, args.at, args.all, args.output)
