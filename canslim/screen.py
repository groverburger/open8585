"""The 85-85 screen pipeline.

Funnel design: the cheap price-based filters run on the full universe
first (price >= $10, within 15% of the 52-week high, ADV >= 10k shares,
RS rating >= 85). Fundamentals are then fetched only for those survivors
plus a random reference sample of the universe, so EPS ratings are
percentiled against the market rather than against the survivors.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import fundamentals as fnd
from . import ratings
from .prices import download_prices
from .universe import load_universe


@dataclass
class ScreenConfig:
    data_dir: Path = Path("data")
    min_price: float = 10.0
    max_pct_off_high: float = 15.0
    min_adv: float = 10_000
    min_rs: int = 85
    min_eps: int = 85
    # Owen Cupp / Fred Richards-style overlays on the 85-85 list:
    # aggressive screen = --min-ad B- (A or B rating) with min_eps_rs 180,
    # conservative     = --min-ad A- with min_eps_rs 190.
    min_ad: str | None = None  # e.g. "B-" keeps B- and better
    min_eps_rs: int | None = None  # minimum EPS rating + RS rating sum
    # None = fetch fundamentals for the whole universe and percentile
    # against all of it (IBD-faithful; first run is slow). An integer runs
    # in quick mode against a random reference sample instead - expect
    # several rating points of sampling jitter at the 85 boundary.
    ref_sample_size: int | None = None
    ref_seed: int = 8585
    refresh: bool = False
    limit: int | None = None  # cap universe size, for testing
    as_of: str | None = None  # compute price metrics as of this date (YYYY-MM-DD)
    rs_pool_size: int | None = None  # model IBD's larger RS universe (e.g. 8000)


def run_screen(cfg: ScreenConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the full pipeline.

    Returns (screen, rated): the final 85-85 list, and the full universe
    with price-based ratings attached (for inspection/analysis).
    """
    data_dir = Path(cfg.data_dir)

    print("[1/6] loading universe (NASDAQ screener)")
    universe = load_universe(data_dir / "universe.json", refresh=cfg.refresh)
    if cfg.limit:
        universe = universe.sort_values("market_cap", ascending=False).head(cfg.limit)
    print(f"  {len(universe)} common stocks")

    print("[2/6] downloading daily prices")
    prices = download_prices(
        universe["symbol"].tolist(), data_dir / "prices.parquet", refresh=cfg.refresh
    )
    print(f"  {prices['symbol'].nunique()} symbols with price history")
    if cfg.as_of:
        prices = prices[prices["date"] <= pd.Timestamp(cfg.as_of)]
        print(f"  truncated to {prices['date'].max().date()} (as-of {cfg.as_of})")

    print("[3/6] computing RS / A-D ratings and price metrics")
    metrics = ratings.compute_price_metrics(prices)
    metrics = ratings.add_rs_rating(metrics, pool_size=cfg.rs_pool_size)
    metrics = ratings.add_ad_rating(metrics)
    rated = metrics.merge(universe, on="symbol", how="left")

    ind_ranks = ratings.industry_ranks(metrics, universe)
    rated["industry_rank"] = rated["industry"].map(ind_ranks).astype("Int64")
    rated["group_grade"] = rated["industry"].map(ratings.group_grade(ind_ranks))

    print("[4/6] price-based filters")
    survivors = rated[
        (rated["price"] >= cfg.min_price)
        & (rated["pct_off_high"] >= -cfg.max_pct_off_high)
        & (rated["adv50"] >= cfg.min_adv)
        & (rated["rs_rating"] >= cfg.min_rs)
    ].copy()
    print(f"  {len(survivors)} survivors of price/RS filters")

    pool = rated["symbol"].tolist()
    if cfg.ref_sample_size:
        # quick mode: percentile against a uniform random sample of the
        # universe (uniform, not liquid-only: IBD percentiles against its
        # whole database, so a liquid-only reference over-tightens the bar)
        print(f"[5/6] fundamentals for survivors + {cfg.ref_sample_size}-stock reference sample")
        rng = random.Random(cfg.ref_seed)
        ref_syms = set(rng.sample(pool, min(cfg.ref_sample_size, len(pool))))
        fetch_syms = sorted(set(survivors["symbol"]) | ref_syms)
    else:
        # IBD-faithful mode: percentile against every rated stock
        print("[5/6] fundamentals for the full universe")
        ref_syms = set(pool)
        fetch_syms = sorted(pool)
    records = fnd.fetch_fundamentals(fetch_syms, data_dir / "fundamentals", refresh=cfg.refresh)

    fmetrics = pd.DataFrame([fnd.eps_metrics(r) for r in records.values()])
    fmetrics["eps_rating"] = fnd.eps_rating_vs_reference(fmetrics, ref_syms & set(fmetrics["symbol"]))

    print("[6/6] final EPS filter")
    screen = survivors.merge(fmetrics, on="symbol", how="left")
    screen = screen[(screen["eps_rating"] >= cfg.min_eps).fillna(False)]
    screen["eps_rs_sum"] = screen["eps_rating"] + screen["rs_rating"]

    if cfg.min_ad:
        max_rank = ratings.grade_rank(cfg.min_ad)
        keep = screen["ad_rating"].map(
            lambda g: ratings.grade_rank(g) <= max_rank if pd.notna(g) else False
        )
        screen = screen[keep]
        print(f"  A/D filter >= {cfg.min_ad}: {len(screen)} remain")
    if cfg.min_eps_rs:
        screen = screen[(screen["eps_rs_sum"] >= cfg.min_eps_rs).fillna(False)]
        print(f"  EPS+RS filter >= {cfg.min_eps_rs}: {len(screen)} remain")

    # One line per company: when multiple share classes pass (e.g. BELFA and
    # BELFB), keep the class with the higher average daily volume.
    base_name = (
        screen["name"]
        .str.lower()
        .str.replace(r"\s+(class|cl\.?)\s+[a-c]\b.*$", "", regex=True)
        .str.replace(r"\s+(common stock|common shares|ordinary shares).*$", "", regex=True)
        .str.strip()
    )
    screen = screen.loc[screen.groupby(base_name)["adv50"].idxmax()]

    screen = screen.sort_values(["industry_rank", "symbol"], na_position="last")
    print(f"  {len(screen)} stocks pass the 85-85 screen")

    return screen.reset_index(drop=True), rated


DISPLAY_COLUMNS = {
    "symbol": "Symbol",
    "name": "Company",
    "industry": "Industry Group",
    "industry_rank": "Grp Rank",
    "price": "Price",
    "price_day_chg": "Price %Chg",
    "vol_pct_chg": "Vol %Chg",
    "eps_q0_growth": "EPS %Chg",
    "sales_growth": "Sales %Chg",
    "rs_rating": "RS",
    "eps_rating": "EPS",
    "eps_rs_sum": "EPS+RS",
    "ad_rating": "A/D",
}


def format_screen(screen: pd.DataFrame) -> pd.DataFrame:
    """Human-readable table in the style of the investors.com list."""
    out = screen[list(DISPLAY_COLUMNS)].rename(columns=DISPLAY_COLUMNS).copy()
    out["Company"] = out["Company"].str.replace(
        r"\s+(Common Stock|Class [A-C] Common Stock|Ordinary Shares|Common Shares|"
        r"American Depositary Shares(?: \(ADS\))?|Depositary Shares).*$",
        "",
        regex=True,
    )
    out["Price"] = out["Price"].map("{:.2f}".format)
    for col in ("Price %Chg", "Vol %Chg"):
        out[col] = out[col].map(lambda x: f"{x:+.1f}" if pd.notna(x) else "N/A")
    for col in ("EPS %Chg", "Sales %Chg"):
        out[col] = out[col].map(lambda x: f"{min(x, 999):.0f}" if pd.notna(x) else "N/A")
    return out
