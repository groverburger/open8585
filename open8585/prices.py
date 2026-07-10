"""Bulk daily OHLCV download with a local parquet cache.

Pattern adapted from ngram_asset_momentum/run_experiment.py, extended to
thousands of symbols: chunked yf.download calls, tidy long format, and a
parquet cache that is reused while fresh.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import yfinance as yf

CHUNK_SIZE = 200
CACHE_MAX_AGE_HOURS = 20
# ~3 years: the ratings only need 252 trading days, but the published
# weekly charts show 104 weeks and need 40 more weeks of runway so the
# 40-week moving average spans the full chart width
LOOKBACK_DAYS = 1050


def _normalize_chunk(raw: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    """Flatten yfinance's multi-index columns into long format."""
    frames = []
    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        for sym in symbols:
            if sym not in raw.columns.get_level_values(0):
                continue
            sub = raw[sym].dropna(how="all")
            if sub.empty:
                continue
            sub = sub.reset_index().rename(columns=str.lower)
            sub["symbol"] = sym
            frames.append(sub)
    else:  # single symbol chunk
        sub = raw.dropna(how="all").reset_index().rename(columns=str.lower)
        sub["symbol"] = symbols[0]
        frames.append(sub)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out.rename(columns={"index": "date"})
    keep = ["date", "symbol", "open", "high", "low", "close", "volume"]
    return out[[c for c in keep if c in out.columns]]


def download_prices(
    symbols: list[str],
    cache_path: Path,
    refresh: bool = False,
    lookback_days: int = LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Daily adjusted OHLCV for `symbols`, long format, cached to parquet."""
    cache_path = Path(cache_path)
    if cache_path.exists() and not refresh:
        age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        if age_hours <= CACHE_MAX_AGE_HOURS:
            cached = pd.read_parquet(cache_path)
            if set(symbols) <= set(cached["symbol"].unique()):
                return cached[cached["symbol"].isin(symbols)]

    start = (pd.Timestamp.today() - pd.Timedelta(days=lookback_days)).date()
    frames = []
    total_chunks = (len(symbols) + CHUNK_SIZE - 1) // CHUNK_SIZE
    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i : i + CHUNK_SIZE]
        chunk_no = i // CHUNK_SIZE + 1
        for attempt in range(3):
            try:
                raw = yf.download(
                    tickers=chunk,
                    start=str(start),
                    auto_adjust=True,  # adjusted OHLC, raw volume
                    group_by="ticker",
                    threads=True,
                    progress=False,
                )
                break
            except Exception as exc:  # noqa: BLE001 - network layer varies
                wait = 10 * (attempt + 1)
                print(f"  chunk {chunk_no}/{total_chunks} failed ({exc}); retrying in {wait}s")
                time.sleep(wait)
        else:
            print(f"  chunk {chunk_no}/{total_chunks} skipped after retries")
            continue
        tidy = _normalize_chunk(raw, chunk)
        if not tidy.empty:
            frames.append(tidy)
        print(f"  prices chunk {chunk_no}/{total_chunks}: {len(tidy)} rows")

    prices = pd.concat(frames, ignore_index=True)
    prices["date"] = pd.to_datetime(prices["date"]).dt.tz_localize(None)
    prices = prices.dropna(subset=["close"]).sort_values(["symbol", "date"])
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(cache_path, index=False)
    return prices
