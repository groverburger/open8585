#!/usr/bin/env python3
"""Append missing Yahoo daily bars to the existing price parquet cache."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from open8585.prices import CHUNK_SIZE, _normalize_chunk


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT/"data"/"prices.parquet")
    parser.add_argument("--through", type=pd.Timestamp, required=True,
                        help="Inclusive final session requested")
    args = parser.parse_args()

    existing = pd.read_parquet(args.cache)
    existing["date"] = pd.to_datetime(existing.date).dt.tz_localize(None)
    last_date = existing.date.max()
    if last_date >= args.through:
        print(f"cache already reaches {last_date.date()}")
        return

    symbols = sorted(existing.symbol.unique())
    start = (last_date+pd.Timedelta(days=1)).date().isoformat()
    end = (args.through+pd.Timedelta(days=1)).date().isoformat()
    frames = []
    failures = []
    total = (len(symbols)+CHUNK_SIZE-1)//CHUNK_SIZE
    for offset in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[offset:offset+CHUNK_SIZE]
        number = offset//CHUNK_SIZE+1
        raw = None
        for attempt in range(3):
            try:
                raw = yf.download(
                    tickers=chunk,
                    start=start,
                    end=end,
                    auto_adjust=True,
                    group_by="ticker",
                    threads=True,
                    progress=False,
                )
                break
            except Exception as exc:  # noqa: BLE001
                print(f"chunk {number}/{total} attempt {attempt+1} failed: {exc}")
                time.sleep(5*(attempt+1))
        if raw is None:
            failures.extend(chunk)
            continue
        tidy = _normalize_chunk(raw, chunk)
        if not tidy.empty:
            frames.append(tidy)
        print(f"chunk {number}/{total}: {len(tidy)} rows", flush=True)

    if not frames:
        raise RuntimeError("Yahoo returned no new price rows; cache was not changed")
    new = pd.concat(frames, ignore_index=True)
    new["date"] = pd.to_datetime(new.date).dt.tz_localize(None)
    combined = pd.concat([existing, new], ignore_index=True)
    combined = (
        combined.dropna(subset=["close"])
        .drop_duplicates(["symbol", "date"], keep="last")
        .sort_values(["symbol", "date"])
    )
    temporary = args.cache.with_suffix(".incremental.tmp.parquet")
    combined.to_parquet(temporary, index=False)
    temporary.replace(args.cache)
    print(f"added {len(new):,} rows through {new.date.max().date()}")
    print(f"symbols on final fetched session: {new.loc[new.date.eq(new.date.max()), 'symbol'].nunique():,}")
    if failures:
        print(f"chunks failed for {len(failures)} symbols")


if __name__ == "__main__":
    main()
