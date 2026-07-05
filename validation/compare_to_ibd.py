#!/usr/bin/env python3
"""Compare our screen output against a captured IBD 85-85 list.

Reports: overlap/recall on membership, where the IBD names we missed fell
out of our funnel (no data / price filters / RS / EPS), and precision
context for our extra names.

Usage: python3 validation/compare_to_ibd.py output/screen_<date>.csv output/ratings_<date>.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SAMPLE = Path(__file__).parent / "ibd_sample_2026-07.txt"


def load_sample() -> pd.DataFrame:
    rows = []
    for line in SAMPLE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        rows.append({"symbol": parts[0], "ibd_grp_rank": int(parts[1]), "ibd_price": float(parts[2])})
    return pd.DataFrame(rows)


def main() -> None:
    screen = pd.read_csv(sys.argv[1])
    rated = pd.read_csv(sys.argv[2])
    ibd = load_sample()

    ours = set(screen["symbol"])
    theirs = set(ibd["symbol"])
    hit = theirs & ours
    print(f"IBD list: {len(theirs)} | ours: {len(ours)} | overlap: {len(hit)} "
          f"({len(hit)/len(theirs):.0%} of IBD's list)")

    missed = ibd[~ibd["symbol"].isin(ours)].merge(rated, on="symbol", how="left")
    reasons = []
    for _, r in missed.iterrows():
        if pd.isna(r.get("price")):
            reasons.append("no price data")
        elif r["price"] < 10:
            reasons.append("price < $10")
        elif r["pct_off_high"] < -15:
            reasons.append(f"off high {r['pct_off_high']:.0f}%")
        elif r["adv50"] < 10_000:
            reasons.append("volume")
        elif r["rs_rating"] < 85:
            reasons.append(f"RS {r['rs_rating']:.0f}")
        else:
            eps_row = screen[screen["symbol"] == r["symbol"]]
            reasons.append("EPS rating < 85" if eps_row.empty else "?")
    missed = missed.assign(reason=reasons)
    print("\nIBD names we missed:")
    for _, r in missed.iterrows():
        print(f"  {r['symbol']:6s} {r['reason']}")

    extra = sorted(ours - theirs)
    print(f"\nExtra names we have that IBD doesn't ({len(extra)}): {', '.join(extra)}")

    both = screen[screen["symbol"].isin(hit)]
    if not both.empty and "rs_rating" in both:
        print(f"\nFor overlapping names: our RS range {both['rs_rating'].min()}-{both['rs_rating'].max()}, "
              f"EPS range {both['eps_rating'].min()}-{both['eps_rating'].max()}")


if __name__ == "__main__":
    main()
