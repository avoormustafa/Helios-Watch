# Tracking-Tailing-Algorithm
Accenture x Builders Club Hackathon 

# Storm Tail-er — OMNIWeb data collector

`omniweb_collector.py` pulls hourly solar-wind and geomagnetic data from
NASA's [OMNIWeb](https://omniweb.gsfc.nasa.gov/form/dx1.html) and saves it as
**`data.txt`** in the same folder as the script. It is the "Tail-er" in our
Storm Tracker: it keeps `data.txt` up to date so the prediction model always
has the newest data.

It sends exactly the query you would make by ticking the boxes on the OMNIWeb
form and clicking **List data**, just automatically.

## Requirements

- Python 3.8 or newer
- An internet connection
- Nothing to install (standard library only)

## Quick start

```bash
# 1. Load history (one-off): Sept 2016 to Sept 2026
python omniweb_collector.py range 20160901 20260930

# 2. Keep data.txt growing as OMNIWeb publishes new hours
python omniweb_collector.py live
```

Stop `live` with **Ctrl+C**. Rerunning it later picks up where `data.txt` left off.

## Modes

| Command | What it does to `data.txt` |
| --- | --- |
| `python omniweb_collector.py range YYYYMMDD YYYYMMDD` | **Replaces** it with that date range |
| `python omniweb_collector.py latest` | **Replaces** it with the most recent 30 days OMNIWeb has |
| `python omniweb_collector.py live` | **Adds** new hours to the end every 3 hours; never duplicates or deletes rows |

There is only ever one `data.txt`. To keep an old copy before running `range`
or `latest` again, rename it first (e.g. `data_2016-2026.txt`).

## What's in `data.txt`

```
# Source: NASA OMNIWeb (...), hourly OMNI2
# Updated: 2026-10-14T17:15:20
# Rows: <count>, from <first hour> to <last hour> (hours with missing values removed)
Selected parameters:
 1 ...
YEAR DOY HR    1    2    3 ...  16
2024 131  0  6.5  3.0  2.0 ... 168
```

Each data row is one hour: `YEAR`, `DOY` (day of year, 1 = 1 Jan), `HR` (0–23, UTC),
then 16 values in this order:

| # | Variable | Units |
| --- | --- | --- |
| 1 | IMF magnitude (average) | nT |
| 2 | Bx (GSE = GSM) | nT |
| 3 | By, GSE | nT |
| 4 | Bz, GSE | nT |
| 5 | By, GSM | nT |
| 6 | Bz, GSM | nT |
| 7 | Sigma in IMF magnitude | nT |
| 8 | Sigma in IMF vector | nT |
| 9 | Proton temperature | K |
| 10 | Proton density | per cm³ |
| 11 | Flow speed | km/s |
| 12 | Flow pressure | nPa |
| 13 | Ey electric field | mV/m |
| 14 | Kp × 10 (so 50 = Kp 5) | — |
| 15 | Dst index | nT |
| 16 | AE index | nT |

**Storm reference points:** Kp ≥ 5 (column 14 ≥ 50) is a NOAA G1 storm or
stronger; Dst ≤ −50 nT (column 15) is a moderate storm or stronger.

### Reading it in Python

```python
rows = [line.split() for line in open("data.txt") if line[:4].isdigit()]
# rows[0] -> ['2016', '245', '0', '6.5', '3.0', ...]  (all strings; convert with float())
```

## Settings

Edit the top of `omniweb_collector.py`:

| Setting | Default | Meaning |
| --- | --- | --- |
| `OUTPUT_FILE` | `"data.txt"` | Output file name (saved next to the script) |
| `DROP_MISSING_ROWS` | `True` | Remove any hour where a variable is missing (see below) |
| `LATEST_DAYS` | `30` | How far back `latest` / `live` request |
| `CHECK_EVERY_MINUTES` | `180` | How often `live` checks OMNIWeb |
| `VARIABLES` | 16 variables | Which OMNIWeb variables to request (code = OMNI word number − 1) |

### Missing values

OMNIWeb marks missing data with "fill" values such as `999.9`, `9999.`,
`9999999.`, `99.99`, `999.99`, `99` (Kp) and `99999` (Dst). With
`DROP_MISSING_ROWS = True`, any hour containing one of these is left out of
`data.txt`, so every row is complete.

## Things to know

- **OMNIWeb is not real-time.** Its newest solar-wind data is usually 3–4
  weeks behind today, so `live` collects the newest data OMNIWeb *has*, not
  what's happening right now. For true real-time data, use NOAA's live
  solar-wind feed (see `tailer.py`).
- **Indices end earlier than the solar wind.** AE (and sometimes Dst) is
  published later than the magnetic-field and plasma data. Because incomplete
  rows are dropped, `data.txt` stops at the last hour where *all 16* exist.
  Set `DROP_MISSING_ROWS = False` to keep newer hours with those gaps.
- **Big ranges take a while.** `range` fetches one year per request; ten years
  is ten requests, so give it a minute or two.

## Troubleshooting

| Problem | Likely cause / fix |
| --- | --- |
| `No data came back` | Dates are past what OMNIWeb has yet; use an earlier end date |
| `data.txt` has fewer rows than expected | Hours with missing values were dropped (see above) |
| Request errors / timeouts | OMNIWeb is busy or down; try again later, or use a shorter range |
| Columns look wrong | Open the OMNIWeb form, run the same dates manually, and compare |

## Data credit

OMNIWeb asks users to acknowledge: *"The OMNI data were obtained from the
GSFC/SPDF OMNIWeb interface at https://omniweb.gsfc.nasa.gov".*
Please include this on the project slides.
