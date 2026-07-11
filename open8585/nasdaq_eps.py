"""Incremental street-EPS updates from NASDAQ's earnings-surprise API.

NASDAQ's endpoint works everywhere (probe from a GitHub runner: 39/40
filled) but only returns the last ~4 reported quarters. Yahoo's
earnings-calendar endpoint also works from CI (it needs lxml installed;
its absence once masqueraded as an IP block) and remains the fallback and
the local-run primary — but it rate-limits hard under bulk load, so the
gentle one-request-per-symbol path here is CI's primary. Four quarters is
exactly enough for incremental maintenance: given a seeded history, each
week only the quarters reported since the last run are new, and they're
always within the last 4.

Vendor note: NASDAQ's adjusted EPS can differ a few percent from Yahoo's
for the same quarter (different adjustment conventions). Appended records
carry that seam; over quarters the series becomes NASDAQ-consistent.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
STALE_DAYS = 95  # a symbol is "due" when its newest street quarter is older


def fetch_street_quarters(symbol: str, timeout: float = 10) -> list[tuple[str, float]]:
    """Reported (street) EPS for the last ~4 quarters: [(date, eps), ...]."""
    url = f"https://api.nasdaq.com/api/company/{symbol}/earnings-surprise"
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    rows = ((r.json().get("data") or {}).get("earningsSurpriseTable") or {}).get("rows") or []
    out = []
    for row in rows:
        try:
            date = pd.Timestamp(row["dateReported"]).date().isoformat()
            out.append((date, float(row["eps"])))
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(out)


def merge_quarters(rec: dict, quarters: list[tuple[str, float]]) -> int:
    """Append quarters not already in rec['reported_eps'] (±10-day match)."""
    existing = rec.get("reported_eps") or []
    dates = [pd.Timestamp(d) for d, _ in existing]
    added = 0
    for d, eps in quarters:
        ts = pd.Timestamp(d)
        if any(abs((ts - e).days) <= 10 for e in dates):
            continue
        existing.append([d, eps])
        dates.append(ts)
        added += 1
    if added:
        existing.sort(key=lambda r: r[0])
        rec["reported_eps"] = existing
    return added


def update_street_eps(symbols: list[str], cache_dir: Path, budget_minutes: float) -> None:
    """Refresh street EPS for symbols whose newest quarter looks stale.

    Priority order is the caller's (screen members first, then the
    universe). Time-bounded; each symbol is one HTTP request.
    """
    cache_dir = Path(cache_dir)
    now = pd.Timestamp.now()
    due = []
    for s in dict.fromkeys(symbols):  # dedupe, keep order
        path = cache_dir / f"{s}.json"
        if not path.exists():
            continue
        rec = json.loads(path.read_text())
        reported = rec.get("reported_eps") or []
        if not rec.get("q_eps") and not reported:
            continue  # no earnings data at all; nothing to maintain
        if not reported or (now - pd.Timestamp(reported[-1][0])).days > STALE_DAYS:
            due.append(s)
    if not due:
        print("[nasdaq-eps] nothing due")
        return

    print(f"[nasdaq-eps] {len(due)} symbols due; budget {budget_minutes:.0f} min")
    deadline = time.time() + budget_minutes * 60
    done = added_total = errors = 0
    for s in due:
        if time.time() > deadline:
            break
        try:
            quarters = fetch_street_quarters(s)
        except Exception:  # noqa: BLE001 - network; skip and move on
            errors += 1
            quarters = []
        if quarters:
            path = cache_dir / f"{s}.json"
            rec = json.loads(path.read_text())
            added_total += merge_quarters(rec, quarters)
            path.write_text(json.dumps(rec))
        done += 1
        time.sleep(0.3)
    print(f"[nasdaq-eps] attempted {done}/{len(due)}, quarters added {added_total}, errors {errors}")
