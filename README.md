# open8585

A weekly screen for stocks rated 85 or better on both earnings growth and
relative price strength — the "85-85 list" growth traders have used for
decades — rebuilt in the open from free data.

**[The list](https://groverburger.github.io/open8585/)** regenerates every
Friday after the close, with weekly charts for every stock on it.
**[Full ratings](https://groverburger.github.io/open8585/ratings.html)** for
all ~5,400 US stocks, sortable and filterable. Each week's list lands in
[`archive/`](archive/), which doubles as a dataset for backtesting.

The ratings this screen depends on have been proprietary black boxes for
forty years. Every formula here is reconstructed from the public record,
calibrated against captured samples of the commercial ratings, and printed
below. If you disagree with a number, you can read the code that produced it.

*The 85-85 method and these rating concepts were popularized by Investor's
Business Daily® and William O'Neil's* How to Make Money in Stocks. *This is
an independent educational reconstruction — not affiliated with or endorsed
by IBD or William O'Neil + Co. Not investment advice.*

## Run it

```bash
pip install -r requirements.txt
python3 run_screen.py                 # full universe; first run ~1hr, then cached
python3 run_screen.py --limit 500     # quick test, top 500 by market cap
```

The screen: RS Rating ≥ 85, EPS Rating ≥ 85, price ≥ $15, within 15% of the
52-week closing high, 3-month average daily volume ≥ 500,000 shares. Tighter overlays
used by practitioners of the methodology:

```bash
python3 run_screen.py --min-ad B-                    # accumulation B or better
python3 run_screen.py --min-ad B- --min-eps-rs 180   # "aggressive"
python3 run_screen.py --min-ad A- --min-eps-rs 190   # "conservative"
```

Results go to `output/`, data caches to `data/`. To rebuild the published
site by hand: `python3 scripts/publish.py`.

## The ratings

RS and EPS are percentile ranks, 1–99, against the full US stock universe —
about 5,400 names after dropping preferreds, warrants, units, SPAC shells,
closed-end funds, and exchange-traded debt. A/D is an absolute technical state
mapped to letter grades; it is not a cross-sectional percentile bucket.

**RS Rating.** Twelve-month price performance with the most recent quarter
double-weighted:

```
raw = 2·(P/P₆₃) + (P/P₁₂₆) + (P/P₁₈₉) + (P/P₂₅₂)
```

Stocks with under a year of history use their earliest price for the missing
legs.

**EPS Rating.** Recent quarterly earnings growth blended with the multi-year
record. Each component is percentile-ranked before combining, because raw
growth rates can't be averaged — too many stocks tie at ±999:

```
quarters block = mean(pct(latest qtr YoY), pct(prior qtr YoY))
combined       = 0.6·quarters block + 0.4·pct(multi-year growth)
combined      -= 0.25·(pct(earnings instability) − 0.5)
```

Street (reported) EPS where available, GAAP diluted as fallback. The
instability term is the residual of log quarterly EPS around its 3-year
trend: steady growers get a boost, erratic earners a haircut. A company still
losing money scores −999 no matter how much the loss narrowed, and a stock
with no recent quarterly data gets no rating at all — that's what keeps
shells and funds off the list. A displayed 999 means either "turned
profitable" or genuine growth past 999%; hover the cell on the site.

**Accumulation/Distribution Rating.** A coefficient-free daily price/volume
conviction balance, graded A+ through E. A session qualifies when price moves at least
0.2% and volume exceeds the preceding 10-session mean. Its vote is strengthened
by logarithmic relative volume and by price movement in 20-session ATR units:

```
evidence = log2(1 + relative volume) · (1 + |ATR-normalized move|)
U, D     = separate up/down evidence EMAs with a 20-session half-life
score    = 100 · (U − D) / (U + D)
grade    = frozen 2024-2025 boundaries(score)
```

There are zero fitted signal coefficients. Only the twelve fixed letter
boundaries are calibrated, using 2024-2025 Global Laggards labels and official
daily market-wide grade shares. On valid 2026 observations through April 24,
64.9% of individual predictions land within one subgrade and the frozen broad
market grade-distribution error is 1.90 percentage points. The full equation,
lineage, and limitations are documented in
[`docs/ad_conviction_balance_model.md`](docs/ad_conviction_balance_model.md).

**Industry group rank** orders the ~150 industry groups by median member RS.
It's the least faithful piece; the commercial products use their own group
taxonomy.

## How close is it?

Every constant above was set against captured samples of the commercial
ratings, never by feel. **[docs/RATINGS.md](docs/RATINGS.md) is the full
evidence file** — the three-way comparison of IBD's, Deepvue's, and this
system's ratings, with every claim traced to captured data. Change history
in [STATUS.md](STATUS.md). Where it stands:

| rating | agreement with captured samples |
|---|---|
| RS | within ~1 point, 8 samples spanning 21–99 |
| EPS | ~8 points mean error, no directional bias |
| A/D | 64.9% within one subgrade; market grade-share MAE 1.90 pp on valid 2026 data |
| list membership | 58% of a captured weekly list, every miss traced |

Most of the remaining gap is data, not formulas: the commercial products run
their own earnings databases, which disagree with free street-EPS sources on
about 1 in 8 names. For calibration, two commercial screeners we compared
disagree with *each other* about as much.

## Data sources

Free, no API keys — and strictly **one vendor per domain**: NASDAQ's
screener API is the *directory* (which stocks exist and their industry
groups — no numbers), Yahoo Finance is *every number* (prices, volume,
street EPS, GAAP statements). No cross-vendor reconciliation exists
anywhere in the pipeline; within Yahoo, street EPS is preferred and GAAP is
the labeled per-symbol fallback for the ~70% of micro-caps no analyst
covers. Yahoo's earnings-calendar endpoint rate-limits hard and
occasionally hangs mid-connection — the fetch layer isolates it in killable
subprocesses, refreshes stale symbols on a paced weekly pass, and the
publish gate aborts rather than ship a list where street coverage has
degraded.

## Layout

```
open8585/
  universe.py       # universe + industry groups
  prices.py         # chunked price download, parquet cache
  ratings.py        # RS, A/D, group ranks, price metrics
  fundamentals.py   # EPS fetch + EPS rating
  screen.py         # the funnel
  charts.py         # weekly PNG charts for the site
  site.py           # static pages
run_screen.py       # CLI
scripts/publish.py  # weekly build (also run by the GitHub Action)
scripts/ad_breadth.py  # daily % of universe per A/D letter -> archive/ad_breadth.{csv,png}
validation/         # captured commercial samples + comparison scripts
```

## License

MIT. See the note up top — this is an educational reconstruction of a
methodology, not a product or advice.
