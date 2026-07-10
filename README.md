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

## The published weekly list

A GitHub Action recomputes everything every Saturday after the weekly close:

- **[The open 85-85 list](https://groverburger.github.io/canslim-8585/)** —
  this week's screen with debuts marked and weekly charts per stock.
- **[Full ratings table](https://groverburger.github.io/canslim-8585/ratings.html)**
  — RS, EPS, and A/D ratings for all ~5,400 rated US stocks, sortable.
- Each week's list is archived in [`archive/`](archive/) — over time this
  becomes the dataset for backtesting list-debut performance.

To publish locally (e.g. if a CI run fails): `python3 scripts/publish.py`.

## Quick start

```bash
pip install -r requirements.txt
python3 run_screen.py                 # full universe; first run ~15-30 min
python3 run_screen.py --limit 500     # quick test on top 500 by market cap
python3 run_screen.py --refresh       # ignore caches, re-download everything
```

The A/D rating and the EPS+RS sum can be applied as filters on top of the
85-85 list, matching the Fred Richards screens used by practitioners of the
O'Neil methodology:

```bash
python3 run_screen.py --min-ad B-                    # accumulation B or better
python3 run_screen.py --min-ad B- --min-eps-rs 180   # "aggressive" screen
python3 run_screen.py --min-ad A- --min-eps-rs 190   # "conservative" screen
```

Results land in `output/screen_<date>.csv` and `output/screen_<date>.md`, plus
`output/ratings_<date>.csv` containing the full universe with RS and A/D
ratings for your own analysis. Data caches live in `data/` (universe JSON,
prices parquet, per-ticker fundamentals JSON) so re-runs are fast.

## Data sources (all free, no API keys)

| Data | Source | Notes |
|---|---|---|
| Universe + industry groups | NASDAQ screener API | ~7,000 NYSE/NASDAQ/AMEX stocks, ~150 industry groups, one request |
| Daily OHLCV (~3 years) | Yahoo Finance via `yfinance` | adjusted prices, chunked bulk download |
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
combined      -= 0.25 · (pct(earnings instability) − 0.5)
```

and the combined score is percentiled once more into 1–99.

The last term is IBD's **earnings stability factor**: the residual standard
deviation of log quarterly EPS around its fitted trend line over the last
3–4 years (any loss quarter counts as maximally erratic; under 8 quarters of
history the adjustment is neutral). Steady growers get a boost, erratic
earners a haircut. In validation this factor improved recall of IBD's names
*and* cut false extras at the same time — it is the single most
IBD-distinctive part of the rating.

- Reported (street) EPS is preferred — it excludes one-time items, closest to
  what IBD uses; GAAP diluted EPS is the fallback. The multi-year leg uses
  trailing-twelve-month street EPS CAGR when 8+ reported quarters exist,
  else GAAP annual EPS CAGR (3–4 fiscal years).
- Growth off a zero/negative base follows IBD's convention: displayed as ±999.
  A company still losing money scores −999 however much the loss narrowed —
  only actually turning profitable earns +999. A displayed 999 can therefore
  mean either "turned profitable" (a percentage off a non-positive base is
  not meaningful) or genuine growth beyond 999%, display-capped — the
  published tables carry a hover tooltip on these cells. Ranking per component (rather
  than averaging raw growth rates) keeps the mass of ±999 ties from
  saturating the composite — with raw averaging an 85+ rating is literally
  unreachable.
- A missing multi-year leg falls back to the quarters block alone; a missing
  quarters block means **no rating** (this keeps closed-end funds and shell
  companies with only annual figures off the list).
- The 60/40 block weighting was validated against a captured IBD list: IBD
  demonstrably rates cyclicals with huge current quarters but flat multi-year
  records (DELL, TER, SIMO) at 85+, so recent quarters must dominate.

**Full-universe percentiles by default:** EPS ratings are percentiled against
every rated stock, exactly like IBD. The first run fetches fundamentals for
the whole universe (slow — roughly an hour; cached for 7 days thereafter).
`--ref-sample 400` runs in quick mode against a uniform random sample of the
universe instead — fine for exploration, but expect several rating points of
sampling jitter at the 85 boundary (we measured overlap with IBD's list
swinging ±7 names on the sample seed alone, which is why full-universe is
the default).

### Accumulation/Distribution Rating — A+ to E−

Day-over-day price direction on volume over the last 13 weeks (65 sessions):

```
score = Σ clip(daily return, ±10%) · (volume ÷ avg volume) · decay  ÷  Σ decay
```

with a ~1-month half-life recency decay. Up days on heavy volume push the
score up (accumulation); down days on heavy volume push it down. Scores are
percentile-ranked across the universe and mapped to quintile letter grades
A–E with +/− thirds within each quintile. A = heavy institutional buying,
C = neutral, E = heavy selling.

Day-over-day direction matters: an intraday close-location formula (where in
the day's range the stock closed) misses gap moves entirely — validated
against captured IBD A/D grades it scored near-zero rank correlation, vs
+0.67 for this formula, with every sample within about one letter grade.

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
`validation/`): our screen recovers **57 of IBD's 99 names** (deterministic,
full-universe percentiles) with ~59 extra names IBD doesn't print. Every
remaining miss traces to a measured cause — universe breadth (RS), vendor
EPS-database differences, REIT FFO accounting, or threshold-boundary cases;
none are unexplained. For context on the gap:

- **RS ratings are calibrated to IBD's**: on five captured IBD Stock
  Checkup values, our native RS matched four within 1 point (MTSI 94/95,
  GOOGL 85/85, MU 99/99, COHR 96/96) and the fifth within 3. The 85-85
  list's RS near-misses (all 78–84) therefore look like compute-date
  timing rather than rating error. `--rs-pool 8000` models a larger IBD
  universe but overshot on the same test — treat it as an experiment, not
  a fix.
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
