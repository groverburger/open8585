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
    Day-over-day price direction on volume over the last 13 weeks:
    each session contributes clip(daily return, ±10%) x (volume / average
    volume), recency-weighted with a ~1-month half-life. The sum is
    percentile-ranked and mapped to A+ .. E- (A = heavy institutional
    buying, E = heavy selling). Day-over-day direction matters: a
    close-location (intraday range) formula misses gap moves entirely and
    scored near-zero rank correlation against IBD's published A/D grades,
    vs +0.73 for this one (9-sample validation, see validation/).

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
# full grade scale, best first
GRADE_SCALE = tuple(f"{letter}{sign}" for letter in AD_GRADES for sign in ("+", "", "-"))


def grade_rank(grade: str) -> int:
    """Position of a letter grade on the 15-point scale (0 = A+, 14 = E-)."""
    return GRADE_SCALE.index(grade)


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

        tail = g.tail(AD_LOOKBACK + 1)  # +1: day-over-day changes need a prior close
        c_ad, v_ad = tail["close"].to_numpy(float), tail["volume"].to_numpy(float)
        rets = np.clip(np.diff(c_ad) / c_ad[:-1], -0.10, 0.10)
        v1 = v_ad[1:]
        mean_v = v1.mean()
        if len(rets) and mean_v > 0:
            decay = 0.5 ** (np.arange(len(rets))[::-1] / 20)
            ad_raw = float((rets * (v1 / mean_v) * decay).sum() / decay.sum())
        else:
            ad_raw = np.nan

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


def add_rs_rating(metrics: pd.DataFrame, pool_size: int | None = None) -> pd.DataFrame:
    """RS rating 1-99 by percentile of the raw score.

    pool_size models a larger rating universe (IBD percentiles against
    ~8,000-10,000 stocks incl. OTC vs our ~5,500 listed): the extra
    hypothetical members are assumed to rank below every real one, which
    lifts everyone's percentile. Off by default - it makes ratings more
    IBD-comparable but strictly more generous than our own universe
    justifies.
    """
    metrics = metrics.copy()
    if pool_size and pool_size > metrics["rs_raw"].notna().sum():
        rank = metrics["rs_raw"].rank(ascending=False, method="min")
        metrics["rs_rating"] = np.ceil(99 * (1 - rank / pool_size)).clip(1, 99).astype("Int64")
    else:
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


def group_grade(rank: pd.Series) -> pd.Series:
    """Letter-grade industry group ranks A+ .. E- (IBD's Group RS scale):
    quintiles of the group-rank distribution with +/- thirds."""
    n = rank.max()
    pct = 1 - (rank - 1) / n  # 1.0 = best group

    def grade(p: float) -> str | None:
        if pd.isna(p):
            return None
        quintile = min(int((1 - p) * 5), 4)
        within = (1 - p) * 5 - quintile
        sign = "+" if within < 1 / 3 else ("" if within < 2 / 3 else "-")
        return AD_GRADES[quintile] + sign

    return pct.map(grade)
