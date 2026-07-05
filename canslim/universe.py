"""US common-stock universe with industry classification.

Uses NASDAQ's free screener API, which returns every NYSE/NASDAQ/AMEX
listed stock with name, last price, market cap, sector, and industry in a
single request. The industry field (~150 groups) stands in for IBD's 197
proprietary industry groups.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Name fragments that mark non-common-stock listings we exclude.
EXCLUDE_NAME_FRAGMENTS = (
    "warrant",
    " right",
    " rights",
    " unit ",
    " units",
    "preferred",
    "preference share",
    "acquisition corp",
    "acquisition co",
    "blank check",
)

CACHE_MAX_AGE_DAYS = 3


def _fetch_screener() -> list[dict]:
    resp = requests.get(
        SCREENER_URL,
        params={"tableonly": "true", "limit": "25000", "download": "true"},
        headers=HEADERS,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["data"]["rows"]


def _parse_number(text: str | None) -> float:
    if not text:
        return float("nan")
    try:
        return float(str(text).replace("$", "").replace(",", "").replace("%", ""))
    except ValueError:
        return float("nan")


def to_yahoo_symbol(symbol: str) -> str:
    """NASDAQ uses BRK/A and AAIC^B style symbols; Yahoo uses BRK-A / AAIC-PB."""
    symbol = symbol.strip()
    if "^" in symbol:
        base, _, series = symbol.partition("^")
        return f"{base}-P{series}" if series else base
    return symbol.replace("/", "-")


def load_universe(cache_path: Path, refresh: bool = False) -> pd.DataFrame:
    """Return the listed-stock universe as a DataFrame.

    Columns: symbol (Yahoo format), name, sector, industry, market_cap,
    country, ipo_year. Cached as JSON; refetched when older than
    CACHE_MAX_AGE_DAYS or on refresh=True.
    """
    cache_path = Path(cache_path)
    stale = True
    if cache_path.exists() and not refresh:
        age_days = (time.time() - cache_path.stat().st_mtime) / 86400
        stale = age_days > CACHE_MAX_AGE_DAYS
    if stale or refresh:
        rows = _fetch_screener()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(rows))
    else:
        rows = json.loads(cache_path.read_text())

    df = pd.DataFrame(rows)
    df = df.rename(columns={"marketCap": "market_cap", "ipoyear": "ipo_year"})
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df["name"] = df["name"].astype(str).str.strip()
    df["industry"] = df["industry"].astype(str).str.strip()
    df["sector"] = df["sector"].astype(str).str.strip()
    df["market_cap"] = df["market_cap"].map(_parse_number)
    df["last_sale"] = df["lastsale"].map(_parse_number)

    # Drop preferred shares / warrants / rights / units / SPAC shells.
    name_lower = df["name"].str.lower()
    mask = pd.Series(True, index=df.index)
    for frag in EXCLUDE_NAME_FRAGMENTS:
        mask &= ~name_lower.str.contains(frag, regex=False)
    mask &= ~df["symbol"].str.contains("^", regex=False)  # preferred series
    # Closed-end funds are not operating companies (their fund-accounting
    # "earnings" would still earn EPS ratings). REITs stay: only the word
    # "fund" and NASDAQ's generic trusts bucket are excluded, not "trust".
    mask &= ~name_lower.str.contains(r"\bfundo?\b", regex=True)
    mask &= df["industry"] != "Trusts Except Educational Religious and Charitable"
    # Multi-class common (BRK/A) is fine; five-letter NASDAQ suffixes for
    # warrants/rights/units (W, R, U endings on SPACs) are caught by name.
    df = df[mask].copy()

    df["symbol"] = df["symbol"].map(to_yahoo_symbol)
    df = df.drop_duplicates(subset="symbol")
    keep = ["symbol", "name", "sector", "industry", "market_cap", "last_sale", "country", "ipo_year"]
    return df[keep].reset_index(drop=True)
