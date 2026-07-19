#!/usr/bin/env python3
"""Weekly publish pipeline: run the screen, render charts, and build the
static site artifacts for the GitHub Pages `site` branch.

Outputs:
  site/       index.html, ratings.html, charts/*.png, fonts/, data/*.csv
  archive/    one screen CSV per run (committed to master; also the
              dataset for the debut backtest and week-over-week diffs)

Usage:
  python3 scripts/publish.py                       # full run
  python3 scripts/publish.py --skip-backfill --max-charts 5   # quick test
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from open8585 import charts  # noqa: E402
from open8585.screen import ScreenConfig, run_screen  # noqa: E402


def street_eps_refresh(data_dir: Path, budget_minutes: float) -> None:
    """Refresh street EPS from Yahoo before rating, via killable
    subprocesses (the endpoint rate-limits under load and can hang;
    see validation/backfill_one.py).

    Two tiers, most-stale-first within each:
      1. symbols WITH street history whose newest quarter is >95 days old
         (their next report has likely landed - the real weekly work)
      2. symbols never successfully fetched, rechecked at most every 30
         days (most have no analyst coverage anywhere; the stamp keeps
         them from burning the budget weekly)
    """
    fund = data_dir / "fundamentals"
    now = time.time()
    tier1, tier2 = [], []
    for p in fund.glob("*.json"):
        rec = json.loads(p.read_text())
        reported = rec.get("reported_eps") or []
        if reported:
            age = (pd.Timestamp.now() - pd.Timestamp(reported[-1][0])).days
            if age > 95:
                tier1.append((age, p.stem))
        elif rec.get("q_eps"):
            if now - rec.get("street_checked_at", 0) > 30 * 86400:
                tier2.append((rec.get("street_checked_at", 0), p.stem))
    todo = [s for _, s in sorted(tier1, reverse=True)] + [s for _, s in sorted(tier2)]
    if not todo:
        print("[street] nothing due")
        return
    print(f"[street] {len(tier1)} stale + {len(tier2)} unchecked due; "
          f"budget {budget_minutes:.0f} min")
    deadline = time.time() + budget_minutes * 60
    done = filled = 0
    for s in todo:
        if time.time() > deadline:
            break
        try:
            out = subprocess.run(
                [sys.executable, str(ROOT / "validation" / "backfill_one.py"), s],
                capture_output=True, text=True, timeout=25, cwd=ROOT,
            )
            if "quarters" in out.stdout:
                filled += 1
        except subprocess.TimeoutExpired:
            pass
        done += 1
        time.sleep(1.2)
    print(f"[street] attempted {done}/{len(todo)}, refreshed {filled}")


def eps_ttm_series(symbol: str, data_dir: Path) -> pd.Series | None:
    """Trailing-twelve-month EPS by report date, from cached fundamentals."""
    p = data_dir / "fundamentals" / f"{symbol}.json"
    if not p.exists():
        return None
    rec = json.loads(p.read_text())
    records = rec.get("reported_eps") or rec.get("q_eps") or []
    if len(records) < 4:
        return None
    dates = [pd.Timestamp(d) for d, _ in records]
    vals = [v for _, v in records]
    ttm = [sum(vals[i - 3: i + 1]) for i in range(3, len(vals))]
    return pd.Series(ttm, index=dates[3:])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    ap.add_argument("--site-dir", type=Path, default=ROOT / "site")
    ap.add_argument("--archive-dir", type=Path, default=ROOT / "archive")
    ap.add_argument("--backfill-minutes", type=float, default=20)
    ap.add_argument("--skip-backfill", action="store_true")
    ap.add_argument("--max-charts", type=int, default=None, help="cap charts (testing)")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--allow-degraded", action="store_true",
                    help="publish even when most EPS ratings fell back to GAAP")
    args = ap.parse_args()

    if not args.skip_backfill:
        # refresh stale street EPS BEFORE rating, so quarters reported this
        # week are in this week's ratings
        street_eps_refresh(args.data_dir, args.backfill_minutes)

    cfg = ScreenConfig(data_dir=args.data_dir, refresh=args.refresh)
    screen, rated = run_screen(cfg)
    run_date = pd.Timestamp.now(tz="America/Los_Angeles").date().isoformat()

    # Data-quality gate: the EPS ratings were calibrated on street
    # (reported) EPS. If most of the list rated from the GAAP fallback,
    # the street-EPS pipeline is degraded (a missing lxml once made every
    # earnings-calendar call silently return empty in CI, churning half
    # the list) and publishing would reflect data damage, not the market.
    street_share = (screen["eps_source"] == "reported").mean() if len(screen) else 0.0
    print(f"[quality] street-EPS share of list: {street_share:.0%}")
    if street_share < 0.5 and not args.allow_degraded:
        sys.exit("ABORT: street-EPS share below 50% (expected ~85%) - the "
                 "fundamentals cache is degraded - check dependencies (lxml), "
                 "the data store, and rate limits, or pass --allow-degraded.")

    # Debuts are WEEK-over-week: "first appearance on the weekly list" is
    # the methodology's signal, so the baseline is the newest archive from
    # a PRIOR ISO week - mid-week or same-week reruns never eat a debut,
    # and with no prior-week data yet, nothing is marked NEW.
    args.archive_dir.mkdir(parents=True, exist_ok=True)
    this_week = pd.Timestamp(run_date).isocalendar()[:2]
    prior = sorted(
        p for p in args.archive_dir.glob("screen_*.csv")
        if pd.Timestamp(p.stem.split("_")[1]).isocalendar()[:2] < this_week
    )
    prev_symbols = set(pd.read_csv(prior[-1])["symbol"]) if prior else set()
    debuts = set(screen["symbol"]) - prev_symbols if prev_symbols else set()
    dropoffs = prev_symbols - set(screen["symbol"])
    screen.to_csv(args.archive_dir / f"screen_{run_date}.csv", index=False)
    print(f"[diff] {len(debuts)} debuts, {len(dropoffs)} drop-offs vs "
          f"{prior[-1].name if prior else '(no prior-week baseline yet)'}")

    print("[charts] rendering")
    prices = pd.read_parquet(args.data_dir / "prices.parquet")
    spx = charts.get_benchmark(args.data_dir / "benchmark.parquet")
    chart_dir = args.site_dir / "charts"
    # every list member must ship with a chart: --max-charts caps fresh
    # renders for testing, but members whose PNG is missing render anyway
    members = screen if args.max_charts is None else screen.head(args.max_charts)
    want = set(members["symbol"])
    want |= {s for s in screen["symbol"] if not (chart_dir / f"{s}.png").exists()}
    rendered = 0
    for _, row in screen[screen["symbol"].isin(want)].iterrows():
        daily = (prices[prices["symbol"] == row["symbol"]]
                 .set_index("date").sort_index())
        charts.render_chart(row["symbol"], str(row.get("name", "")), daily, spx,
                            chart_dir / f"{row['symbol']}.png",
                            eps_ttm=eps_ttm_series(row["symbol"], args.data_dir))
        rendered += 1
    # prune charts for symbols no longer on the list
    current = set(screen["symbol"])
    pruned = 0
    for png in chart_dir.glob("*.png"):
        if png.stem not in current:
            png.unlink()
            pruned += 1
    still_missing = [s for s in current if not (chart_dir / f"{s}.png").exists()]
    print(f"[charts] rendered {rendered}, pruned {pruned} orphans, "
          f"missing after build: {len(still_missing)}")
    if still_missing:
        sys.exit(f"ABORT: members without charts: {still_missing}")

    from open8585.site import build_pages_site  # noqa: E402
    run_stamp = pd.Timestamp.now(tz="America/Los_Angeles").strftime("%Y-%m-%d %H:%M %Z")
    build_pages_site(screen, rated, debuts, dropoffs, run_date, args.site_dir,
                     assets_dir=ROOT / "assets" / "fonts", run_stamp=run_stamp)
    print(f"[done] {len(screen)} stocks · site/ ready")


if __name__ == "__main__":
    main()
