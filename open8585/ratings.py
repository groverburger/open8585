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
    A coefficient-free EMA conviction balance. Meaningful up and down days on
    above-normal volume contribute evidence according to the day's relative
    volume and price move in ATR units. Separate accumulation and distribution
    EMAs fade with a 20-session half-life; their normalized balance is mapped
    through frozen 2024-2025 boundaries to A+ .. E.

Industry Group Rank
    Industry groups ranked 1..N by the median RS rating of their members
    (groups with fewer than 3 rated members are unranked). IBD ranks its
    197 proprietary groups the same way; we use NASDAQ's ~150 industries.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

import numpy as np
import pandas as pd

RS_WINDOWS = (63, 126, 189, 252)
RS_WEIGHTS = (2.0, 1.0, 1.0, 1.0)
MIN_HISTORY_DAYS = 63
# Published summary-table scale, best first. O'Neil uses a single E bucket.
GRADE_SCALE = ("A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "E")


def grade_rank(grade: str) -> int:
    """Position on the 13-point published A/D scale (0 = A+, 12 = E)."""
    return GRADE_SCALE.index(grade)


def percentile_1_99(series: pd.Series) -> pd.Series:
    """Cross-sectional percentile rank scaled to integers 1..99.

    ceil(99p) so that "rating >= 85" means exactly "top 15%": a stock at
    the 85th percentile gets 85, the single best stock gets 99.
    """
    pct = series.rank(pct=True, na_option="keep")
    return np.ceil(pct * 99).clip(1, 99)


@lru_cache(maxsize=1)
def _ad_model() -> dict:
    """Load the frozen production model without any validation-data dependency."""
    return json.loads(Path(__file__).with_name("ad_model.json").read_text())


def _ad_raw_history(frame: pd.DataFrame) -> np.ndarray:
    """Return the EMA conviction-balance state for every session.

    This is the single production implementation used by both current and
    historical A/D ratings.  It intentionally mirrors the frozen research
    equation and contains no fitted signal coefficients.
    """
    frame = frame.sort_values("date")
    model = _ad_model()
    close, high, low, volume = (
        frame[column].to_numpy(float) for column in ("close", "high", "low", "volume")
    )
    observations = len(frame)
    if observations < 2:
        return np.full(observations, np.nan)

    previous_close = np.r_[np.nan, close[:-1]]
    change = close - previous_close
    returns = np.divide(
        change,
        previous_close,
        out=np.full(observations, np.nan),
        where=previous_close > 0,
    )

    volume_lookback = int(model["volume_lookback"])
    prior_volume = (
        pd.Series(volume)
        .rolling(volume_lookback, min_periods=volume_lookback)
        .mean()
        .shift(1)
        .to_numpy()
    )
    relative_volume = np.divide(
        volume,
        prior_volume,
        out=np.full(observations, np.nan),
        where=prior_volume > 0,
    )

    true_range = np.maximum.reduce([
        high - low,
        np.abs(high - previous_close),
        np.abs(low - previous_close),
    ])
    atr_lookback = int(model["atr_lookback"])
    atr = (
        pd.Series(true_range)
        .rolling(atr_lookback, min_periods=atr_lookback)
        .mean()
        .to_numpy()
    )
    atr_move = np.divide(
        change,
        atr,
        out=np.full(observations, np.nan),
        where=atr > 0,
    )
    atr_move = np.clip(atr_move, -float(model["atr_move_cap"]), float(model["atr_move_cap"]))

    qualifies = (
        (np.abs(returns) >= float(model["minimum_absolute_return"]))
        & (relative_volume > float(model["minimum_relative_volume"]))
    )
    robust_volume = np.log2(1.0 + relative_volume)
    evidence = np.where(
        qualifies,
        robust_volume * (1.0 + np.abs(atr_move)),
        0.0,
    )

    half_life = float(model["half_life_sessions"])
    alpha = 1.0 - 0.5 ** (1.0 / half_life)
    positive = pd.Series(np.where(returns > 0, evidence, 0.0)).ewm(
        alpha=alpha, adjust=False
    ).mean().to_numpy()
    negative = pd.Series(np.where(returns < 0, evidence, 0.0)).ewm(
        alpha=alpha, adjust=False
    ).mean().to_numpy()
    total = positive + negative
    return np.divide(
        100.0 * (positive - negative),
        total,
        out=np.zeros(observations),
        where=total > 0,
    )


def _ad_raw_score(frame: pd.DataFrame) -> float:
    """Evaluate the frozen EMA conviction balance for the final session."""
    raw = _ad_raw_history(frame)
    if not len(raw):
        return np.nan
    return float(raw[-1])


def _ad_numeric_grades(raw: np.ndarray, model: dict) -> np.ndarray:
    """Convert raw states to ordinal grades using the active frozen mapping."""
    if "grade_thresholds" in model:
        return np.searchsorted(np.asarray(model["grade_thresholds"], dtype=float), raw, side="right")
    calibrated = np.interp(
        raw,
        np.asarray(model["calibration_x"], dtype=float),
        np.asarray(model["calibration_y"], dtype=float),
    )
    return np.clip(np.rint(calibrated), 0, 12).astype(int)


def ad_score_history(frame: pd.DataFrame, min_history: int = MIN_HISTORY_DAYS) -> pd.DataFrame:
    """Return the frozen EMA conviction-balance state and grade by session."""
    frame = frame.sort_values("date")
    if len(frame) < max(2, min_history):
        return pd.DataFrame(columns=["date", "ad_raw", "ad_rating"])

    model = _ad_model()
    raw = _ad_raw_history(frame)
    eligible = np.arange(1, len(frame) + 1) >= min_history
    raw = raw[eligible]
    grade_values = np.asarray(model["grade_values"], dtype=object)
    grades = grade_values[_ad_numeric_grades(raw, model)]
    return pd.DataFrame({
        "date": frame["date"].to_numpy()[eligible],
        "ad_raw": raw,
        "ad_rating": grades,
    })


def compute_price_metrics(prices: pd.DataFrame) -> pd.DataFrame:
    """Per-symbol metrics from long-format daily OHLCV.

    Returns one row per symbol: last close, RS raw score, % off 52-week
    high, 50-day and 3-month (63-day) average volume, A/D raw score, weekly price % change,
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
            # A zero close is invalid vendor data for a return calculation;
            # letting it through would create an infinite RS score and distort
            # the whole cross-sectional percentile ranking.
            if not np.isfinite(base) or base <= 0 or not np.isfinite(last) or last <= 0:
                raw = np.nan
                break
            raw += weight * (last / base)

        # closing high, not intraday: empirically matches IBD's "within 15%
        # of 52-week high" boundary cases better
        high_52w = g["close"].tail(252).max()
        adv50 = g["volume"].tail(50).mean()
        adv3m = g["volume"].tail(63).mean()  # ~3 months of sessions
        vol_last = g["volume"].iloc[-1]

        price_day_chg = (last / close[-2] - 1) * 100 if n >= 2 else np.nan

        ad_raw = _ad_raw_score(g)

        rows.append(
            {
                "symbol": sym,
                "price": last,
                "rs_raw": raw,
                "pct_off_high": (last / high_52w - 1) * 100,
                "adv50": adv50,
                "adv3m": adv3m,
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
    """Map the model state to A+ .. E using the frozen monotonic calibration."""
    metrics = metrics.copy()
    model = _ad_model()
    valid = metrics["ad_raw"].notna()
    values = _ad_numeric_grades(metrics.loc[valid, "ad_raw"].to_numpy(float), model)
    ascending_grades = np.asarray(model["grade_values"], dtype=object)
    metrics["ad_rating"] = pd.Series(None, index=metrics.index, dtype=object)
    metrics.loc[valid, "ad_rating"] = ascending_grades[values]
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
        return ("A", "B", "C", "D", "E")[quintile] + sign

    return pct.map(grade)
