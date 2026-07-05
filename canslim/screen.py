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
    ref_sample_size: int = 400
    ref_seed: int = 8585
    refresh: bool = False
    limit: int | None = None  # cap universe size, for testing
    as_of: str | None = None  # compute price metrics as of this date (YYYY-MM-DD)


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
    metrics = ratings.add_rs_rating(metrics)
    metrics = ratings.add_ad_rating(metrics)
    rated = metrics.merge(universe, on="symbol", how="left")

    ind_ranks = ratings.industry_ranks(metrics, universe)
    rated["industry_rank"] = rated["industry"].map(ind_ranks).astype("Int64")

    print("[4/6] price-based filters")
    survivors = rated[
        (rated["price"] >= cfg.min_price)
        & (rated["pct_off_high"] >= -cfg.max_pct_off_high)
        & (rated["adv50"] >= cfg.min_adv)
        & (rated["rs_rating"] >= cfg.min_rs)
    ].copy()
    print(f"  {len(survivors)} survivors of price/RS filters")

    print("[5/6] fundamentals for survivors + reference sample")
    rng = random.Random(cfg.ref_seed)
    liquid = rated[rated["adv50"] >= cfg.min_adv]["symbol"].tolist()
    ref_syms = rng.sample(liquid, min(cfg.ref_sample_size, len(liquid)))
    fetch_syms = sorted(set(survivors["symbol"]) | set(ref_syms))
    records = fnd.fetch_fundamentals(fetch_syms, data_dir / "fundamentals", refresh=cfg.refresh)

    fmetrics = pd.DataFrame([fnd.eps_metrics(r) for r in records.values()])
    fmetrics["eps_rating"] = fnd.eps_rating_vs_reference(fmetrics, set(ref_syms))

    print("[6/6] final EPS filter")
    screen = survivors.merge(fmetrics, on="symbol", how="left")
    screen = screen[(screen["eps_rating"] >= cfg.min_eps).fillna(False)]

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
