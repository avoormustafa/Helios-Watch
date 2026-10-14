"""
OMNIWeb collector
=================
Queries NASA OMNIWeb (the same service behind https://omniweb.gsfc.nasa.gov/form/dx1.html)
for hourly OMNI data and saves the results as data.txt, next to this script.

No installs needed (Python 3 standard library only).

Usage:
    python omniweb_collector.py range 20160901 20260930   # data.txt = that date range
    python omniweb_collector.py latest                    # data.txt = the most recent data
    python omniweb_collector.py live                      # keep checking; add new hours to data.txt

Note: OMNIWeb is not real-time. Its newest solar-wind data is usually a few
weeks old, so "live" means "the newest data OMNIWeb has", checked every few hours.
"""

import datetime as dt
import html
import os
import re
import sys
import time
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# SETTINGS - edit these
# ---------------------------------------------------------------------------

# Data is saved as data.txt in the same folder as this script (wherever you run it from).
# 'range' and 'latest' replace data.txt; 'live' adds new hours to the end of it.
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = "data.txt"
DROP_MISSING_ROWS = True             # remove hours where any variable is a fill value (999.9 etc.)
LATEST_DAYS = 30                     # 'latest'/'live': how many days back to request
CHECK_EVERY_MINUTES = 180            # 'live': how often to check OMNIWeb for new hours

# The 16 variables ticked on the OMNIWeb form.
# code = OMNIWeb's internal variable number (OMNI word number - 1); fill = its "no data" value.
VARIABLES = [
    # (code, name,                          fill)
    (8,  "IMF Magnitude Avg, nT",           999.9),
    (12, "Bx, GSE/GSM, nT",                 999.9),
    (13, "By, GSE, nT",                     999.9),
    (14, "Bz, GSE, nT",                     999.9),
    (15, "By, GSM, nT",                     999.9),
    (16, "Bz, GSM, nT",                     999.9),
    (17, "Sigma in IMF Magnitude Avg",      999.9),
    (18, "Sigma in IMF Vector Avg",         999.9),
    (22, "Proton Temperature, K",           9999999.0),
    (23, "Proton Density, n/cc",            999.9),
    (24, "Flow Speed, km/s",                9999.0),
    (28, "Flow Pressure, nPa",              99.99),
    (35, "Ey - Electric Field, mV/m",       999.99),
    (38, "Kp*10 Index",                     99.0),
    (40, "Dst Index, nT",                   99999.0),
    (41, "AE Index, nT",                    9999.0),
]

OMNIWEB_URL = "https://omniweb.gsfc.nasa.gov/cgi/nx1.cgi"

# ---------------------------------------------------------------------------
# Talking to OMNIWeb
# ---------------------------------------------------------------------------

DATA_ROW = re.compile(r"^\s*(\d{4})\s+(\d{1,3})\s+(\d{1,2})\s+(.*)$")


def request_omniweb(start, end):
    """Ask OMNIWeb for hourly data between two dates (YYYYMMDD strings).
    Returns the plain text of the result page."""
    params = [("activity", "retrieve"), ("res", "hour"), ("spacecraft", "omni2"),
              ("start_date", start), ("end_date", end)]
    params += [("vars", str(code)) for code, _, _ in VARIABLES]
    params += [("scale", "Linear"), ("view", "0"), ("table", "0")]
    body = urllib.parse.urlencode(params).encode("ascii")
    req = urllib.request.Request(OMNIWEB_URL, data=body,
                                 headers={"User-Agent": "omniweb-collector/1.0 (hackathon)"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read().decode("latin-1", errors="replace")


def parse_result(page):
    """Split OMNIWeb's result page into (header_lines, data_rows).
    header = the 'Selected parameters' list + the 'YEAR DOY HR ...' column line."""
    text = html.unescape(re.sub(r"<[^>]+>", "", page))   # strip HTML tags
    lines = text.splitlines()
    header, rows, in_header = [], [], False
    for line in lines:
        if "Selected parameters" in line:
            in_header = True
        match = DATA_ROW.match(line)
        if match and len(match.group(4).split()) >= len(VARIABLES):
            rows.append(line.rstrip())
            in_header = False
        elif in_header and line.strip():
            header.append(line.rstrip())
    return header, rows


def row_time(row):
    year, doy, hour = (int(x) for x in DATA_ROW.match(row).groups()[:3])
    return dt.datetime(year, 1, 1) + dt.timedelta(days=doy - 1, hours=hour)


def row_is_complete(row):
    """False if any variable in this row is OMNI's 'no data' value."""
    values = DATA_ROW.match(row).group(4).split()
    for (_, _, fill), raw in zip(VARIABLES, values):
        try:
            if abs(float(raw) - fill) < 1e-6:
                return False
        except ValueError:
            return False
    return True


def fetch(start, end):
    """Fetch one date range, in yearly chunks so OMNIWeb isn't asked for too much at once."""
    start_d = dt.datetime.strptime(start, "%Y%m%d").date()
    end_d = dt.datetime.strptime(end, "%Y%m%d").date()
    header, rows = [], []
    chunk_start = start_d
    while chunk_start <= end_d:
        chunk_end = min(dt.date(chunk_start.year, 12, 31), end_d)
        print(f"  requesting {chunk_start} to {chunk_end} ...")
        h, r = parse_result(request_omniweb(chunk_start.strftime("%Y%m%d"),
                                            chunk_end.strftime("%Y%m%d")))
        header = header or h
        rows += r
        chunk_start = chunk_end + dt.timedelta(days=1)
    return header, rows


def fetch_latest(days=LATEST_DAYS):
    """Fetch the newest data. OMNIWeb may refuse an end date past what it has,
    so step the end date back a week at a time until data comes back."""
    end = dt.date.today()
    for _ in range(10):
        start = end - dt.timedelta(days=days)
        header, rows = parse_result(request_omniweb(start.strftime("%Y%m%d"),
                                                    end.strftime("%Y%m%d")))
        if rows:
            return header, rows
        end -= dt.timedelta(days=7)
    return [], []


# ---------------------------------------------------------------------------
# Saving .txt files
# ---------------------------------------------------------------------------

def output_path():
    return os.path.join(OUTPUT_DIR, OUTPUT_FILE)


def read_saved_rows():
    """Data rows already in data.txt (empty list if the file doesn't exist yet)."""
    try:
        with open(output_path(), encoding="utf-8") as f:
            return [line.rstrip("\n") for line in f if DATA_ROW.match(line)]
    except OSError:
        return []


def save_txt(header, rows, append=False):
    """Write data.txt. append=True keeps the rows already in it and adds only newer ones."""
    total = len(rows)
    if DROP_MISSING_ROWS:
        rows = [r for r in rows if row_is_complete(r)]
    dropped = total - len(rows)
    added = rows
    if append:
        existing = read_saved_rows()
        last = row_time(existing[-1]) if existing else None
        added = [r for r in rows if last is None or row_time(r) > last]
        rows = existing + added
    path = output_path()
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Source: NASA OMNIWeb ({OMNIWEB_URL}), hourly OMNI2\n")
        f.write(f"# Updated: {dt.datetime.now().isoformat(timespec='seconds')}\n")
        if rows:
            f.write(f"# Rows: {len(rows)}, from {row_time(rows[0])} to {row_time(rows[-1])}"
                    + (" (hours with missing values removed)\n" if DROP_MISSING_ROWS else "\n"))
        f.write("\n".join(header) + "\n")
        f.write("\n".join(rows) + "\n")
    if added or not append:
        print(f"{'Added' if append else 'Saved'} {len(added)} rows to {path}"
              + (f" ({dropped} incomplete rows dropped)" if DROP_MISSING_ROWS and dropped else ""))
    return added


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def run_range(start, end):
    print(f"Fetching {start} to {end} from OMNIWeb")
    header, rows = fetch(start, end)
    if not rows:
        print("No data came back. Check the dates (OMNIWeb lags a few weeks behind today).")
        return
    save_txt(header, rows)


def run_latest():
    header, rows = fetch_latest()
    if not rows:
        print("No recent data came back from OMNIWeb.")
        return None
    save_txt(header, rows)
    return rows


def run_live():
    print(f"Checking OMNIWeb every {CHECK_EVERY_MINUTES} min, adding new hours to "
          f"{output_path()}. Ctrl+C to stop.")
    while True:
        try:
            header, rows = fetch_latest()
            if not save_txt(header, rows, append=True):
                newest = row_time(rows[-1]) if rows else None
                print(f"[{dt.datetime.now():%H:%M}] no new hours (OMNIWeb newest: {newest})")
        except Exception as exc:
            print(f"[warn] OMNIWeb request failed: {exc}")
        time.sleep(CHECK_EVERY_MINUTES * 60)


def main(argv):
    mode = argv[1] if len(argv) > 1 else "latest"
    if mode == "range" and len(argv) == 4:
        run_range(argv[2], argv[3])
    elif mode == "latest":
        run_latest()
    elif mode == "live":
        run_live()
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)