# Helios Watch

**Early warning for geomagnetic storms, using live satellite data.**

Helios Watch pulls the most recent solar-wind measurements from NASA's satellites,
feeds them into a machine-learning model, and shows the probability that a
geomagnetic storm (a "solar storm" at Earth) is on its way.

🏆 **Winner, Accenture x Builders Club Hackathon, University of Birmingham, 14 October 2026**

<!-- TODO: add screenshots of the frontend here -->
<!-- ![Helios Watch dashboard](docs/screenshot.png) -->

---

## Why it matters

When the Sun throws out a burst of charged plasma (a coronal mass ejection), it
can hit Earth's magnetic field and trigger a geomagnetic storm. Strong storms
disrupt GPS, satellites, radio communications and power grids. Satellites
parked between the Sun and Earth measure the incoming solar wind before it
arrives, which gives a short window of warning. Helios Watch turns those
measurements into a single, readable storm probability.

## How it works

```
 NASA OMNIWeb  ──►  Tailer  ──►  data.txt  ──►  ML model  ──►  Frontend
 (satellite        (fetches      (hourly        (storm         (parameters +
  data)             & cleans)     records)       probability)   prediction)
```

1. **Tailer** retrieves hourly satellite data from
   [NASA OMNIWeb](https://omniweb.gsfc.nasa.gov/form/dx1.html), removes hours
   with missing values, and writes the result to `data.txt`.
2. **ML model** reads `data.txt` and predicts the probability of a storm from
   each hour of data.
3. **Frontend** displays the input parameters alongside the final prediction.

## Data

Each hour in `data.txt` contains 16 variables:

| Group | Variables |
| --- | --- |
| Magnetic field | IMF magnitude; Bx; By and Bz (GSE); By and Bz (GSM); sigma in IMF magnitude; sigma in IMF vector |
| Plasma | Proton temperature; proton density; flow speed |
| Derived | Flow pressure; Ey electric field |
| Indices | Kp × 10; Dst; AE |

The key storm driver is **southward Bz (GSM)** combined with **fast solar wind**.
For reference, Kp ≥ 5 (stored as ≥ 50) is a NOAA G1 storm or stronger, and
Dst ≤ −50 nT is a moderate storm or stronger.

> **Note:** OMNIWeb is a curated archive, so its newest data is typically a few
> weeks behind real time. Helios Watch always uses the most recent data OMNIWeb
> has published.

## Getting started

### Requirements

- Python 3.8+
- TODO: list the ML libraries (for example `scikit-learn`, `pandas`, `joblib`) or add a `requirements.txt`

### 1. Collect the data (Tailer)

```bash
# Load historical data once (writes data.txt)
python3 Tailer.py range 20160901 20260930

# Or fetch just the most recent 30 days
python3 Tailer.py latest

# Or keep data.txt updated as OMNIWeb publishes new hours
python3 Tailer.py live
```

`range` and `latest` replace `data.txt`; `live` appends new hours to it.

### 2. Train and run the model

```bash
# TODO: confirm these commands
python3 train_solar_storm.py      # trains and saves solar_storm_model.joblib
python3 predict_solar_storm.py    # reads data.txt, outputs storm probabilities
```

### 3. Open the frontend

TODO: how to run or open the frontend.

## Project structure

| File | Purpose |
| --- | --- |
| `Tailer.py` | Fetches hourly data from NASA OMNIWeb and writes `data.txt` |
| `data.txt` | Hourly satellite data collected by the Tailer |
| `train_solar_storm.py` | Trains the storm-probability model |
| `predict_solar_storm.py` | Runs the trained model on `data.txt` |
| `solar_storm_model.joblib` | The saved, trained model |
| `solar_storm_model.predictions.csv` | Model predictions output |
| `data_convert.py` | TODO: describe |
| `data.json` | TODO: describe |
| `main.py` | TODO: describe |
| `mlattempt.py` | TODO: describe (early ML experiment?) |
| `draft.py` | TODO: describe (draft / scratch?) |

## Team

| Name | Role |
| --- | --- |
| Mustafa | Tailer (data collection) |
| Anu | Tailer (data collection) |
| Khushhaal | Machine-learning model |
| Zia | Machine-learning model |
| Alagappan | Frontend |

## Acknowledgements

The OMNI data were obtained from the GSFC/SPDF OMNIWeb interface at
https://omniweb.gsfc.nasa.gov.

Thanks to Accenture and the Builders Club at the University of Birmingham for
hosting the hackathon.

## License

Released under the [MIT License](LICENSE).
