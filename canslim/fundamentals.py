"""Quarterly/annual EPS and sales via yfinance, and the EPS Rating.

IBD's EPS Rating combines the two most recent quarters' EPS growth vs the
same quarters a year earlier with the 3-5 year annual growth rate, then
percentile-ranks the result 1-99 against all stocks. We reconstruct it
rank-based: each growth component is percentile-ranked against a random
reference sample of the whole universe (mid-rank for ties), the component
percentiles are combined

    combined = 0.25 * pct(q0_yoy) + 0.25 * pct(q1_yoy) + 0.50 * pct(annual)

(weights renormalized over available components), and the combined score
is percentiled once more into 1-99. Ranking per component keeps stocks
with a negative year-ago base (growth conventionally displayed as +999,
~25% of the market) from all saturating at one value, and ranking against
the reference sample keeps the rating anchored to "beats X% of the
market", not "beats X% of the stocks that already passed the price
screen".

EPS sources, in order of preference:
  1. Reported (street) EPS from the earnings calendar - excludes one-time
     items, closest to what IBD uses, ~8 quarters available.
  2. GAAP Diluted EPS from the quarterly income statement (~7 quarters).

Sales % change is the latest quarter's Total Revenue vs the same quarter
a year earlier. Fetches are cached per ticker as JSON for 7 days.
"""

from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

CACHE_MAX_AGE_DAYS = 7
MAX_WORKERS = 8
GROWTH_CAP = 999.0  # IBD prints 999 for growth off a <=0 base


def _series_to_records(s: pd.Series) -> list[list]:
    out = []
    for ts, val in s.items():
        if val is None or (isinstance(val, float) and math.isnan(val)):
            continue
        out.append([str(pd.Timestamp(ts).date()), float(val)])
    return out


def _fetch_one(symbol: str) -> dict:
    t = yf.Ticker(symbol)
    rec: dict = {"symbol": symbol, "fetched_at": time.time()}

    try:
        ed = t.get_earnings_dates(limit=12)
        reported = ed["Reported EPS"].dropna() if ed is not None else pd.Series(dtype=float)
        rec["reported_eps"] = _series_to_records(reported.sort_index())
    except Exception:
        rec["reported_eps"] = []

    try:
        q = t.quarterly_income_stmt
        rec["q_eps"] = _series_to_records(q.loc["Diluted EPS"].dropna().sort_index()) if "Diluted EPS" in q.index else []
        rec["q_revenue"] = _series_to_records(q.loc["Total Revenue"].dropna().sort_index()) if "Total Revenue" in q.index else []
    except Exception:
        rec["q_eps"], rec["q_revenue"] = [], []

    try:
        a = t.income_stmt
        rec["a_eps"] = _series_to_records(a.loc["Diluted EPS"].dropna().sort_index()) if "Diluted EPS" in a.index else []
    except Exception:
        rec["a_eps"] = []

    return rec


def fetch_fundamentals(symbols: list[str], cache_dir: Path, refresh: bool = False) -> dict[str, dict]:
    """Fetch (or load cached) fundamentals for each symbol."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    to_fetch = []
    for sym in symbols:
        path = cache_dir / f"{sym}.json"
        if path.exists() and not refresh:
            rec = json.loads(path.read_text())
            if time.time() - rec.get("fetched_at", 0) < CACHE_MAX_AGE_DAYS * 86400:
                results[sym] = rec
                continue
        to_fetch.append(sym)

    if to_fetch:
        print(f"  fetching fundamentals for {len(to_fetch)} symbols ({len(results)} cached)", flush=True)
        # Yahoo calls can hang forever inside C code; enforce a global
        # deadline and abandon stragglers rather than blocking the run.
        deadline = 60 + 3 * len(to_fetch)
        pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        futures = {pool.submit(_fetch_one, s): s for s in to_fetch}
        done = 0
        try:
            for fut in as_completed(futures, timeout=deadline):
                sym = futures[fut]
                try:
                    rec = fut.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"  {sym}: fundamentals fetch failed ({exc})", flush=True)
                    continue
                (cache_dir / f"{sym}.json").write_text(json.dumps(rec))
                results[sym] = rec
                done += 1
                if done % 25 == 0:
                    print(f"  fundamentals {done}/{len(to_fetch)}", flush=True)
        except TimeoutError:
            missing = len(to_fetch) - done
            print(f"  deadline hit: abandoning {missing} unfinished fetches", flush=True)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    return results


def _yoy_growth(cur: float, prev: float) -> float:
    """YoY growth in %, IBD-style handling of <=0 values.

    A company still losing money scores -999 no matter how much the loss
    narrowed — IBD only rewards actually turning profitable (+999). Without
    this, loss-narrowing biotechs flood the top percentiles.
    """
    if prev is None or cur is None:
        return np.nan
    if cur <= 0:
        return -GROWTH_CAP
    if prev <= 0:
        return GROWTH_CAP  # turned profitable off a <=0 base
    return (cur - prev) / prev * 100


def _quarterly_yoy(records: list[list], n_quarters: int = 2) -> list[float]:
    """YoY growth for the latest n quarters, matching periods ~1 year apart."""
    if len(records) < 5:
        return []
    dates = [pd.Timestamp(d) for d, _ in records]
    vals = [v for _, v in records]
    growths = []
    for i in range(len(records) - 1, max(len(records) - 1 - n_quarters, -1), -1):
        target = dates[i] - pd.DateOffset(years=1)
        # closest earlier period within 45 days of one year back
        best, best_gap = None, pd.Timedelta(days=46)
        for j in range(i):
            gap = abs(dates[j] - target)
            if gap < best_gap:
                best, best_gap = j, gap
        if best is not None:
            growths.append(_yoy_growth(vals[i], vals[best]))
    return growths


def _cagr(first: float, last: float, years: float) -> float:
    if last <= 0:
        return -GROWTH_CAP  # currently unprofitable
    if first <= 0:
        return GROWTH_CAP  # turned profitable over the window
    return ((last / first) ** (1 / years) - 1) * 100


def _annual_growth(records: list[list]) -> float:
    """Annualized EPS growth over the last 3-4 fiscal years, in %."""
    vals = [v for _, v in records][-4:]
    if len(vals) < 2:
        return np.nan
    return _cagr(vals[0], vals[-1], len(vals) - 1)


def _ttm_growth(records: list[list]) -> float:
    """Annualized growth of trailing-twelve-month street EPS.

    GAAP annual EPS is distorted by one-time items (tax benefits,
    impairments) that IBD's operating-EPS database excludes; when we have
    8+ reported quarters, CAGR between the oldest and newest available TTM
    window is a cleaner annual-growth leg.
    """
    vals = [v for _, v in records]
    if len(vals) < 8:
        return np.nan
    first_ttm = sum(vals[:4])
    last_ttm = sum(vals[-4:])
    years = (len(vals) - 4) / 4
    return _cagr(first_ttm, last_ttm, years)


def _stability(records: list[list], max_quarters: int = 12) -> float:
    """Earnings stability, IBD-style: residual std of log quarterly EPS
    around its fitted trend line over the last 3 years. Lower = steadier.
    Any loss quarter in the window counts as maximally erratic; under 8
    quarters of history there is no basis to judge (NaN). A 3-year window
    (vs 4+) lets old losses age out — validated against the captured IBD
    list, which rates recovered names like MTZ at 85+ despite 2022-era
    losses."""
    vals = [v for _, v in records][-max_quarters:]
    if len(vals) < 8:
        return np.nan
    if min(vals) <= 0:
        return 999.0
    y = np.log(vals)
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    return float(resid.std())


def eps_metrics(rec: dict) -> dict:
    """Growth metrics + composite score for one ticker's fundamentals."""
    q_growths = _quarterly_yoy(rec.get("reported_eps") or [])
    eps_source = "reported"
    if not q_growths:
        q_growths = _quarterly_yoy(rec.get("q_eps") or [])
        eps_source = "diluted"

    annual = _ttm_growth(rec.get("reported_eps") or [])
    if pd.isna(annual):
        annual = _annual_growth(rec.get("a_eps") or [])
    sales_growths = _quarterly_yoy(rec.get("q_revenue") or [], n_quarters=1)

    stability_src = rec.get("reported_eps") or rec.get("q_eps") or []
    return {
        "symbol": rec["symbol"],
        "eps_q0_growth": q_growths[0] if len(q_growths) > 0 else np.nan,
        "eps_q1_growth": q_growths[1] if len(q_growths) > 1 else np.nan,
        "eps_annual_growth": annual,
        "eps_stability": _stability(stability_src),
        "sales_growth": sales_growths[0] if sales_growths else np.nan,
        "eps_source": eps_source,
    }


# Recent-quarters block vs annual-growth block. 0.6 was chosen by validating
# against a captured IBD 85-85 list: IBD demonstrably rates cyclical names
# with huge current quarters but flat multi-year records (DELL, TER, SIMO)
# at 85+, so the recent quarters must dominate the multi-year leg.
QUARTER_BLOCK_WEIGHT = 0.6

# How strongly erratic earnings drag the combined growth score down, in
# units of the combined [0,1] percentile scale. 0 disables the factor.
# 0.25 sits mid-plateau in the validation sweep against the captured IBD
# list, where the factor raised recall AND cut false extras simultaneously
# (IBD's 85+ names are steady growers; erratic ±999 names are not).
STABILITY_WEIGHT = 0.25


def _pct_vs_ref(values: pd.Series, ref_values: pd.Series) -> pd.Series:
    """Mid-rank ECDF percentile of each value within the reference sample.

    Mid-rank matters: growth off a <=0 base is capped at +-999, so a big
    slice of the market ties at the cap; side='left' would pin the whole
    tied block to the bottom of its span.
    """
    ref = np.sort(ref_values.dropna().to_numpy())
    if len(ref) < 30:
        raise ValueError(f"reference sample too small ({len(ref)}) for a stable ECDF")
    x = values.to_numpy(dtype=float)
    lo = np.searchsorted(ref, x, side="left")
    hi = np.searchsorted(ref, x, side="right")
    pct = (lo + hi) / 2 / len(ref)
    return pd.Series(pct, index=values.index).where(values.notna())


def eps_rating_vs_reference(fmetrics: pd.DataFrame, ref_symbols: set[str]) -> pd.Series:
    """EPS Rating 1-99, built from two blocks of percentile ranks.

    Block 1 (recent quarters): mean of the available latest/prior quarter
    YoY-growth percentiles. Block 2 (annual): multi-year growth percentile.
    Blocks are combined 50/50; a stock missing one block entirely is rated
    on the other alone. Keeping the quarters together as a block matters:
    renormalizing per-component would shift a missing prior-quarter's
    weight onto the annual leg, sinking exactly the accelerating-earnings
    stocks the screen is meant to find.
    """
    ref_mask = fmetrics["symbol"].isin(ref_symbols)

    def pct(col: str) -> pd.Series:
        try:
            return _pct_vs_ref(fmetrics[col], fmetrics.loc[ref_mask, col])
        except ValueError:  # component too sparse in the reference sample
            return pd.Series(np.nan, index=fmetrics.index)

    q_block = pd.concat([pct("eps_q0_growth"), pct("eps_q1_growth")], axis=1).mean(axis=1)
    annual = pct("eps_annual_growth")
    combined = (QUARTER_BLOCK_WEIGHT * q_block + (1 - QUARTER_BLOCK_WEIGHT) * annual)
    # A missing annual leg falls back to the quarters alone, but a missing
    # quarters block means no rating at all: without recent quarterly EPS
    # there is no evidence of current earnings power (this is what keeps
    # closed-end funds' and shell companies' annual-only figures out).
    combined = combined.fillna(q_block)

    if STABILITY_WEIGHT:
        # erratic-earnings percentile (1.0 = most erratic vs reference);
        # unknown stability is treated as market-median, i.e. no adjustment
        erratic = pct("eps_stability").fillna(0.5)
        combined = combined - STABILITY_WEIGHT * (erratic - 0.5)

    final_pct = _pct_vs_ref(combined, combined[ref_mask])
    return final_pct.map(
        lambda p: int(np.clip(math.ceil(p * 99), 1, 99)) if pd.notna(p) else pd.NA
    ).astype("Int64")
