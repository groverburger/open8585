# canslim-8585

An open-source reconstruction of the IBD (Investor's Business Daily / William
O'Neil) **CANSLIM 85-85 list**: a weekly screen of industry group leaders with
**Earnings Per Share and Relative Price Strength ratings of 85 or higher**,
priced $10+, within 15% of their 52-week high, with average daily volume of at
least 10,000 shares. It also includes an open reconstruction of IBD's
**Accumulation/Distribution Rating** (A–E).

IBD's exact rating formulas are proprietary. This project implements the
publicly documented reconstructions, computes every rating as a percentile
rank against the *full* US stock universe (as IBD does), and uses only free
data sources — so anyone can run it, audit it, and improve it.

## Quick start

```bash
pip install -r requirements.txt
python3 run_screen.py                 # full universe; first run ~15-30 min
python3 run_screen.py --limit 500     # quick test on top 500 by market cap
python3 run_screen.py --refresh       # ignore caches, re-download everything
```

Results land in `output/screen_<date>.csv` and `output/screen_<date>.md`, plus
`output/ratings_<date>.csv` containing the full universe with RS and A/D
ratings for your own analysis. Data caches live in `data/` (universe JSON,
prices parquet, per-ticker fundamentals JSON) so re-runs are fast.

## Data sources (all free, no API keys)

| Data | Source | Notes |
|---|---|---|
| Universe + industry groups | NASDAQ screener API | ~7,000 NYSE/NASDAQ/AMEX stocks, ~150 industry groups, one request |
| Daily OHLCV (14 months) | Yahoo Finance via `yfinance` | adjusted prices, chunked bulk download |
| Quarterly reported EPS | Yahoo earnings calendar | street EPS, ~8 quarters |
| Quarterly GAAP EPS + revenue | Yahoo income statements | fallback EPS source; sales growth |
| Annual EPS | Yahoo income statements | up to 5 fiscal years |

Preferred shares, warrants, rights, units, and SPAC shells are excluded from
the universe by name/symbol heuristics.

## Methodology

### Relative Strength (RS) Rating — 1 to 99

The widely documented reconstruction of IBD's formula: 12-month price
performance with the most recent quarter double-weighted,

```
raw = 2·(P/P₆₃) + (P/P₁₂₆) + (P/P₁₈₉) + (P/P₂₅₂)
```

where `Pₙ` is the adjusted close *n* trading days ago. Raw scores are
percentile-ranked across every stock with at least 63 sessions of history and
scaled to 1–99. Stocks with under a year of history use their earliest
available price for the missing legs (a recent IPO's since-IPO return stands
in for the longer windows).

### EPS Rating — 1 to 99

IBD combines the two most recent quarters' EPS growth (vs the same quarters a
year earlier) with the 3–5 year annual growth rate. We reconstruct it
**rank-based**: each growth component is percentile-ranked against a market
reference sample (mid-rank for ties), the percentiles are combined in two
blocks,

```
quarters block = mean(pct(latest quarter YoY), pct(prior quarter YoY))
combined       = 0.6 · quarters block + 0.4 · pct(multi-year growth)
```

and the combined score is percentiled once more into 1–99.

- Reported (street) EPS is preferred — it excludes one-time items, closest to
  what IBD uses; GAAP diluted EPS is the fallback. The multi-year leg uses
  trailing-twelve-month street EPS CAGR when 8+ reported quarters exist,
  else GAAP annual EPS CAGR (3–4 fiscal years).
- Growth off a zero/negative base follows IBD's convention: displayed as ±999.
  A company still losing money scores −999 however much the loss narrowed —
  only actually turning profitable earns +999. Ranking per component (rather
  than averaging raw growth rates) keeps the mass of ±999 ties from
  saturating the composite — with raw averaging an 85+ rating is literally
  unreachable.
- A missing multi-year leg falls back to the quarters block alone; a missing
  quarters block means **no rating** (this keeps closed-end funds and shell
  companies with only annual figures off the list).
- The 60/40 block weighting was validated against a captured IBD list: IBD
  demonstrably rates cyclicals with huge current quarters but flat multi-year
  records (DELL, TER, SIMO) at 85+, so recent quarters must dominate.

**Percentile trick:** fetching fundamentals for all ~7,000 stocks every week
is slow, so the screen fetches them only for stocks that already passed the
price filters *plus a random reference sample of ~400 liquid stocks*. The
reference sample's composite-growth distribution estimates the full market's,
and every stock is rated by its percentile within that reference ECDF. This
keeps ratings anchored to "beats X% of the market" instead of "beats X% of
stocks that already passed a momentum screen" (which would be far stricter
than IBD's 85).

### Accumulation/Distribution Rating — A+ to E−

Volume-weighted close-location money flow over the last 13 weeks (65
sessions):

```
score = Σ volume·((C−L)−(H−C))/(H−L)  ÷  Σ volume
```

Days that close near their high on big volume push the score up
(accumulation); closes near the low push it down (distribution). Scores are
percentile-ranked across the universe and mapped to quintile letter grades
A–E with +/− thirds within each quintile. A = heavy institutional buying,
C = neutral, E = heavy selling.

### Industry Group Rank

Industry groups are ranked 1..N by the **median RS rating of their members**
(minimum 3 rated members). IBD ranks its 197 proprietary groups the same way;
we use NASDAQ's ~150 industry classifications, so ranks are comparable in
spirit but the group definitions differ.

### The screen

A stock makes the list when all of these hold:

1. RS Rating ≥ 85
2. EPS Rating ≥ 85
3. Price ≥ $10
4. Within 15% of its 52-week high (highest daily *close* — empirically what
   IBD's boundary cases imply)
5. 50-day average daily volume ≥ 10,000 shares

Output columns mirror the investors.com table: symbol, company, industry
group rank, price, weekly price % change, volume % change vs the 50-day
average, latest-quarter EPS % change, latest-quarter sales % change — plus
the RS, EPS, and A/D ratings themselves.

## How close is this to IBD's list?

Validated against a captured IBD 85-85 list (99 stocks, early July 2026;
`validation/`): our screen recovers **45 of IBD's 99 names** with ~65 extra
names IBD doesn't print. For context on the gap:

- **RS ratings** track IBD closely — 85 of IBD's 99 names score ≥ 85 on our
  RS, and every miss is in the 78–84 band (proprietary universe/formula
  noise). The formula reconstruction is well established and prices are
  public.
- **EPS ratings** differ more: IBD uses its own earnings database, applies a
  stability factor, and weights things it doesn't disclose. Reported-EPS
  history from Yahoo is shallower (~2 years), so the annual-growth leg leans
  on GAAP diluted EPS.
- **Industry group ranks** use different group definitions (~150 NASDAQ
  industries vs IBD's 197 proprietary groups), so the numbers won't match
  even when the ordering is similar.
- IBD additionally curates its printed list ("industry group leaders"), which
  can drop names that technically pass the numeric screen.

## Project layout

```
canslim/
  universe.py       # NASDAQ screener universe + industry groups
  prices.py         # chunked yfinance bulk download, parquet cache
  ratings.py        # RS rating, A/D rating, industry ranks, price metrics
  fundamentals.py   # EPS/sales fetch + EPS rating vs reference sample
  screen.py         # the funnel pipeline + display formatting
run_screen.py       # CLI entry point
```

## Disclaimer

Not investment advice. "CAN SLIM", "IBD", and the ratings names are
trademarks of their respective owners; this is an independent educational
reconstruction based on publicly documented descriptions of the methodology.
