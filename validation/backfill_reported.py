#!/usr/bin/env python3
"""Serially re-fetch reported (street) EPS for cached fundamentals records
that are missing it. Yahoo's earnings-calendar endpoint rate-limits hard
and then returns empty frames instead of erroring, so this runs slowly,
detects throttling via consecutive-empty streaks, and pauses to let the
limit reset. Priority symbols (screen survivors + reference sample, passed
as a file of one symbol per line) are fetched first.

Usage: python3 validation/backfill_reported.py [priority_file]
"""

from __future__ import annotations

import json
import signal
import sys
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))
from canslim.fundamentals import _series_to_records  # noqa: E402

CACHE = Path(__file__).parent.parent / "data" / "fundamentals"
DELAY = 0.5
CALL_TIMEOUT = 25        # yfinance can hang indefinitely without this
THROTTLE_STREAK = 8      # consecutive empties -> assume throttled
THROTTLE_PAUSE = 300     # seconds to wait for the limit to reset
MAX_PAUSES = 8


class CallTimeout(Exception):
    pass


def _alarm(*_args):
    raise CallTimeout()


signal.signal(signal.SIGALRM, _alarm)


def fetch_reported(symbol: str) -> list[list]:
    signal.alarm(CALL_TIMEOUT)
    try:
        ed = yf.Ticker(symbol).get_earnings_dates(limit=12)
    finally:
        signal.alarm(0)
    reported = ed["Reported EPS"].dropna() if ed is not None else pd.Series(dtype=float)
    return _series_to_records(reported.sort_index())


def main() -> None:
    priority: list[str] = []
    if len(sys.argv) > 1:
        priority = Path(sys.argv[1]).read_text().split()

    todo = []
    for p in sorted(CACHE.glob("*.json")):
        rec = json.loads(p.read_text())
        if not rec.get("reported_eps") and rec.get("q_eps"):
            todo.append((p, rec))
    order = {s: i for i, s in enumerate(priority)}
    todo.sort(key=lambda pr: order.get(pr[1]["symbol"], len(order)))
    print(f"{len(todo)} records missing reported EPS ({len(order)} prioritized)")

    filled = empties = pauses = 0
    i = 0
    while i < len(todo):
        p, rec = todo[i]
        try:
            reported = fetch_reported(rec["symbol"])
        except Exception:  # rate-limit errors raise here
            reported = []
        if reported:
            rec["reported_eps"] = reported
            p.write_text(json.dumps(rec))
            filled += 1
            empties = 0
        else:
            empties += 1
            if empties >= THROTTLE_STREAK:
                pauses += 1
                if pauses > MAX_PAUSES:
                    print("giving up: still throttled after max pauses")
                    break
                print(f"throttled ({empties} consecutive empties); pausing {THROTTLE_PAUSE}s "
                      f"(pause {pauses}/{MAX_PAUSES}, {filled} filled so far)")
                time.sleep(THROTTLE_PAUSE)
                i -= empties - 1  # retry the streak
                empties = 0
                continue
        i += 1
        if i % 50 == 0:
            print(f"  {i}/{len(todo)} attempted, {filled} filled")
        time.sleep(DELAY)
    print(f"done: filled {filled}")


if __name__ == "__main__":
    main()
