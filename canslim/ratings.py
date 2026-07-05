"""Rating computations: Relative Strength, Accumulation/Distribution,
industry group rank, and the price-derived screen metrics.

All ratings are cross-sectional percentile ranks over the full universe,
scaled to 1-99 like IBD's, so an 85 means "beats 85% of all stocks".

RS Rating
    Weighted price performance with the most recent quarter double-weighted
    (the widely documented reconstruction of IBD's formula):
        raw = 2 * P/P63 + P/P126 + P/P189 + P/P252
    where P_n is the adjusted close n trading days ago. Stocks with less
    than a year of history use their earliest available price for the
    missing legs (a new issue's since-IPO return stands in for the longer
    windows, mirroring how IBD still rates recent IPOs).

Accumulation/Distribution Rating
    Volume-weighted close-location money flow over the last 13 weeks
    (65 sessions): each day contributes volume * ((C-L)-(H-C))/(H-L);
    the sum is normalized by total volume, percentile-ranked, and mapped
    to A+ .. E- (A = heavy institutional buying, E = heavy selling).

Industry Group Rank
    Industry groups ranked 1..N by the median RS rating of their members
    (groups with fewer than 3 rated members are unranked). IBD ranks its
    197 proprietary groups the same way; we use NASDAQ's ~150 industries.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RS_WINDOWS = (63, 126, 189, 252)
RS_WEIGHTS = (2.0, 1.0, 1.0, 1.0)
MIN_HISTORY_DAYS = 63
AD_LOOKBACK = 65
AD_GRADES = ("A", "B", "C", "D", "E")


def percentile_1_99(series: pd.Series) -> pd.Series:
    """Cross-sectional percentile rank scaled to integers 1..99.

    ceil(99p) so that "rating >= 85" means exactly "top 15%": a stock at
    the 85th percentile gets 85, the single best stock gets 99.
    """
    pct = series.rank(pct=True, na_option="keep")
    return np.ceil(pct * 99).clip(1, 99)


def compute_price_metrics(prices: pd.DataFrame) -> pd.DataFrame:
    """Per-symbol metrics from long-format daily OHLCV.

    Returns one row per symbol: last close, RS raw score, % off 52-week
    high, 50-day average volume, A/D raw score, weekly price % change,
    and volume % change vs the 50-day average.
    """
    rows = []
    for sym, g in prices.groupby("symbol", sort=False):
        g = g.sort_values("date")
        close = g["close"].to_numpy()
        n = len(close)
        if n < MIN_HISTORY_DAYS:
            continue
        last = close[-1]

        raw = 0.0
        for w, weight in zip(RS_WINDOWS, RS_WEIGHTS):
            base = close[max(0, n - 1 - w)]
            raw += weight * (last / base)

        # closing high, not intraday: empirically matches IBD's "within 15%
        # of 52-week high" boundary cases better
        high_52w = g["close"].tail(252).max()
        adv50 = g["volume"].tail(50).mean()
        vol_last = g["volume"].iloc[-1]

        price_day_chg = (last / close[-2] - 1) * 100 if n >= 2 else np.nan

        tail = g.tail(AD_LOOKBACK)
        h, l, c, v = (tail[k].to_numpy(float) for k in ("high", "low", "close", "volume"))
        rng = h - l
        with np.errstate(divide="ignore", invalid="ignore"):
            mult = np.where(rng > 0, ((c - l) - (h - c)) / rng, 0.0)
        total_v = v.sum()
        ad_raw = float((mult * v).sum() / total_v) if total_v > 0 else np.nan

        rows.append(
            {
                "symbol": sym,
                "price": last,
                "rs_raw": raw,
                "pct_off_high": (last / high_52w - 1) * 100,
                "adv50": adv50,
                "vol_pct_chg": (vol_last / adv50 - 1) * 100 if adv50 > 0 else np.nan,
                "price_day_chg": price_day_chg,
                "ad_raw": ad_raw,
                "history_days": n,
            }
        )
    return pd.DataFrame(rows)


def add_rs_rating(metrics: pd.DataFrame) -> pd.DataFrame:
    metrics = metrics.copy()
    metrics["rs_rating"] = percentile_1_99(metrics["rs_raw"]).astype("Int64")
    return metrics


def add_ad_rating(metrics: pd.DataFrame) -> pd.DataFrame:
    """Map A/D raw score percentile to letter grades A+ .. E-."""
    metrics = metrics.copy()
    pct = metrics["ad_raw"].rank(pct=True, na_option="keep")

    def grade(p: float) -> str | None:
        if pd.isna(p):
            return None
        quintile = min(int((1 - p) * 5), 4)  # 0 = top quintile
        letter = AD_GRADES[quintile]
        within = (1 - p) * 5 - quintile  # 0 = top of quintile
        sign = "+" if within < 1 / 3 else ("" if within < 2 / 3 else "-")
        return letter + sign

    metrics["ad_rating"] = pct.map(grade)
    return metrics


def industry_ranks(metrics: pd.DataFrame, universe: pd.DataFrame, min_members: int = 3) -> pd.Series:
    """Rank industry groups 1..N by median member RS rating."""
    merged = metrics.merge(universe[["symbol", "industry"]], on="symbol", how="left")
    merged = merged[merged["industry"].notna() & (merged["industry"] != "")]
    grouped = merged.groupby("industry")["rs_rating"].agg(["median", "count"])
    ranked = grouped[grouped["count"] >= min_members]["median"]
    return ranked.rank(ascending=False, method="min").astype(int)
