#!/usr/bin/env python3
"""Run the open-source CANSLIM 85-85 screen.

Examples:
    python3 run_screen.py                    # full universe (first run ~15-30 min)
    python3 run_screen.py --limit 500        # top 500 by market cap, quick test
    python3 run_screen.py --refresh          # force re-download of all data
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from canslim.screen import ScreenConfig, format_screen, run_screen


def main() -> None:
    parser = argparse.ArgumentParser(description="Open-source CANSLIM 85-85 screen")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).parent / "data")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "output")
    parser.add_argument("--min-rs", type=int, default=85, help="minimum RS rating (default 85)")
    parser.add_argument("--min-eps", type=int, default=85, help="minimum EPS rating (default 85)")
    parser.add_argument("--min-price", type=float, default=10.0)
    parser.add_argument("--max-off-high", type=float, default=15.0, help="max %% below 52-week high")
    parser.add_argument("--min-adv", type=float, default=10_000, help="min avg daily volume, shares")
    parser.add_argument("--ref-sample", type=int, default=400, help="reference sample size for EPS percentiles")
    parser.add_argument("--limit", type=int, default=None, help="cap universe to top N by market cap (testing)")
    parser.add_argument("--as-of", type=str, default=None, help="compute screen as of this date (YYYY-MM-DD)")
    parser.add_argument("--refresh", action="store_true", help="ignore caches and re-download")
    args = parser.parse_args()

    cfg = ScreenConfig(
        data_dir=args.data_dir,
        min_price=args.min_price,
        max_pct_off_high=args.max_off_high,
        min_adv=args.min_adv,
        min_rs=args.min_rs,
        min_eps=args.min_eps,
        ref_sample_size=args.ref_sample,
        refresh=args.refresh,
        limit=args.limit,
        as_of=args.as_of,
    )
    screen, rated = run_screen(cfg)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = args.as_of or pd.Timestamp.today().date().isoformat()
    raw_path = args.output_dir / f"screen_{stamp}.csv"
    screen.to_csv(raw_path, index=False)
    rated.to_csv(args.output_dir / f"ratings_{stamp}.csv", index=False)

    table = format_screen(screen)
    md_path = args.output_dir / f"screen_{stamp}.md"
    md_path.write_text(
        f"# CANSLIM 85-85 screen — {stamp}\n\n"
        f"{len(table)} stocks: RS ≥ {cfg.min_rs}, EPS ≥ {cfg.min_eps}, "
        f"price ≥ ${cfg.min_price:.0f}, within {cfg.max_pct_off_high:.0f}% of 52-wk high, "
        f"ADV ≥ {cfg.min_adv:,.0f} shares.\n\n" + table.to_markdown(index=False) + "\n"
    )

    pd.set_option("display.max_rows", None, "display.width", 200)
    print()
    print(table.to_string(index=False))
    print(f"\nSaved: {raw_path}\n       {md_path}")


if __name__ == "__main__":
    main()
