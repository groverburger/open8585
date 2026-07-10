#!/usr/bin/env python3
"""Weekly publish pipeline: run the screen, render charts, build the static
site artifacts, and (optionally) regenerate the groverburger.xyz project page.

Outputs:
  site/            index.html, ratings.html, charts/*.png, data/*.csv
  archive/         one screen CSV per run (committed to master; also the
                   dataset for the debut backtest and week-over-week diffs)
  --site-page P    write the self-contained groverburger.xyz page to P

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

from canslim import charts  # noqa: E402
from canslim.screen import ScreenConfig, run_screen  # noqa: E402


def street_eps_backfill(symbols: list[str], data_dir: Path, budget_minutes: float) -> None:
    """Serially backfill street EPS via killable subprocesses (Yahoo's
    earnings endpoint throttles and hangs; see validation/backfill_one.py).
    Time-bounded so CI runs converge over successive weeks."""
    fund = data_dir / "fundamentals"
    todo = []
    for s in symbols:
        p = fund / f"{s}.json"
        if not p.exists():
            continue
        rec = json.loads(p.read_text())
        if not rec.get("reported_eps") and rec.get("q_eps"):
            todo.append(s)
    if not todo:
        return
    print(f"[backfill] {len(todo)} symbols missing street EPS; budget {budget_minutes:.0f} min")
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
        time.sleep(0.5)
    print(f"[backfill] attempted {done}, filled {filled}")


def compute_index(prices: pd.DataFrame, members: list[str]) -> pd.Series:
    """Price-weighted index of current list members (Dow-style: sum of
    member closes, scaled to 100 a year ago). Uses current membership over
    the trailing window, so it's an approximation of IBD's weekly-
    reconstituted index — documented as such."""
    wide = prices[prices["symbol"].isin(members)].pivot(index="date", columns="symbol", values="close")
    wide = wide.tail(260).dropna(axis=1)
    idx = wide.sum(axis=1)
    return idx / idx.iloc[0] * 100


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    ap.add_argument("--site-dir", type=Path, default=ROOT / "site")
    ap.add_argument("--archive-dir", type=Path, default=ROOT / "archive")
    ap.add_argument("--site-page", type=Path, default=None,
                    help="also write the groverburger.xyz project page here")
    ap.add_argument("--backfill-minutes", type=float, default=20)
    ap.add_argument("--skip-backfill", action="store_true")
    ap.add_argument("--max-charts", type=int, default=None, help="cap charts (testing)")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    cfg = ScreenConfig(data_dir=args.data_dir, refresh=args.refresh)
    screen, rated = run_screen(cfg)
    run_date = pd.Timestamp.today().date().isoformat()

    if not args.skip_backfill:
        universe_rotation = rated["symbol"].sample(frac=1, random_state=hash(run_date) % 2**32).tolist()
        street_eps_backfill(screen["symbol"].tolist() + universe_rotation,
                            args.data_dir, args.backfill_minutes)

    # week-over-week diff vs the most recent archived screen
    args.archive_dir.mkdir(parents=True, exist_ok=True)
    prior = sorted(p for p in args.archive_dir.glob("screen_*.csv")
                   if p.stem.split("_")[1] < run_date)
    prev_symbols = set(pd.read_csv(prior[-1])["symbol"]) if prior else set()
    debuts = set(screen["symbol"]) - prev_symbols if prev_symbols else set()
    dropoffs = prev_symbols - set(screen["symbol"])
    screen.to_csv(args.archive_dir / f"screen_{run_date}.csv", index=False)
    print(f"[diff] {len(debuts)} debuts, {len(dropoffs)} drop-offs vs "
          f"{prior[-1].name if prior else '(no prior week)'}")

    print("[charts] rendering")
    prices = pd.read_parquet(args.data_dir / "prices.parquet")
    index = compute_index(prices, screen["symbol"].tolist())
    ma50 = index.rolling(50).mean()
    gate_on = bool(index.iloc[-1] >= ma50.iloc[-1])
    charts.render_index_chart(index, args.site_dir / "charts" / "_index.png")

    spx = charts.get_benchmark(args.data_dir / "benchmark.parquet")
    members = screen if args.max_charts is None else screen.head(args.max_charts)
    for _, row in members.iterrows():
        daily = (prices[prices["symbol"] == row["symbol"]]
                 .set_index("date").sort_index())
        charts.render_chart(row["symbol"], str(row.get("name", "")), daily, spx,
                            args.site_dir / "charts" / f"{row['symbol']}.png")
    print(f"[charts] {len(members)} member charts + index")

    from canslim.site import build_groverburger_page, build_pages_site  # noqa: E402
    build_pages_site(screen, rated, debuts, dropoffs, run_date, gate_on, args.site_dir)
    if args.site_page:
        args.site_page.parent.mkdir(parents=True, exist_ok=True)
        args.site_page.write_text(build_groverburger_page(screen, debuts, run_date, gate_on))
        print(f"[site] wrote {args.site_page}")
    print(f"[done] gate {'ON' if gate_on else 'OFF'} · {len(screen)} stocks · site/ ready")


if __name__ == "__main__":
    main()
