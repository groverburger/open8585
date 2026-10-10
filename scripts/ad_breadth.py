#!/usr/bin/env python3
"""Daily A/D breadth: append new sessions to archive/ad_breadth.csv and
redraw archive/ad_breadth.png (see open8585/breadth.py).

    python3 scripts/ad_breadth.py                    # append new sessions
    python3 scripts/ad_breadth.py --rebuild --start 2025-01-02
    python3 scripts/ad_breadth.py --site-dir site    # also refresh breadth.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from open8585 import breadth  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Append daily A/D letter-grade shares")
    parser.add_argument("--prices", type=Path, default=ROOT / "data" / "prices.parquet")
    parser.add_argument("--output", type=Path, default=ROOT / "archive" / "ad_breadth.csv")
    parser.add_argument("--start", type=pd.Timestamp, default=breadth.BACKFILL_START,
                        help="backfill start when the CSV is new or --rebuild (default 2025-01-02)")
    parser.add_argument("--rebuild", action="store_true", help="recompute every row from --start")
    parser.add_argument("--site-dir", type=Path, help="also write breadth.html + assets into this site dir")
    args = parser.parse_args()

    history, added = breadth.update(pd.read_parquet(args.prices), args.output, args.start, args.rebuild)
    print(f"{added} new session(s) through {history['date'].max():%Y-%m-%d}; "
          f"saved {args.output} and {args.output.with_suffix('.png')}")
    if args.site_dir:
        from open8585.site import build_breadth_page
        build_breadth_page(args.output, args.site_dir)
        print(f"wrote {args.site_dir / 'breadth.html'}")


if __name__ == "__main__":
    main()
