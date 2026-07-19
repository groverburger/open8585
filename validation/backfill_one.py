#!/usr/bin/env python3
"""Fetch reported EPS for ONE symbol and update its cache file.
Run as a subprocess so a hung Yahoo call can be hard-killed by the parent
(yfinance can block inside C code where SIGALRM never fires).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))
from open8585.fundamentals import _series_to_records  # noqa: E402

symbol = sys.argv[1]
path = Path(__file__).parent.parent / "data" / "fundamentals" / f"{symbol}.json"
rec = json.loads(path.read_text())
ed = yf.Ticker(symbol).get_earnings_dates(limit=12)
reported = ed["Reported EPS"].dropna() if ed is not None else pd.Series(dtype=float)
import time
if len(reported):
    rec["reported_eps"] = _series_to_records(reported.sort_index())
    rec["street_checked_at"] = time.time()
    path.write_text(json.dumps(rec))
    print(f"{symbol}: {len(reported)} quarters")
else:
    # remember we looked: most micro-caps have no street coverage anywhere,
    # and re-polling them every week wastes the refresh budget
    rec["street_checked_at"] = time.time()
    path.write_text(json.dumps(rec))
    print(f"{symbol}: empty")
