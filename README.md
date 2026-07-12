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

The screen: RS Rating ≥ 85, EPS Rating ≥ 85, price ≥ $10, within 15% of the
52-week closing high, 50-day average volume ≥ 10,000 shares. Tighter overlays
used by practitioners of the methodology:

```bash
python3 run_screen.py --min-ad B-                    # accumulation B or better
python3 run_screen.py --min-ad B- --min-eps-rs 180   # "aggressive"
python3 run_screen.py --min-ad A- --min-eps-rs 190   # "conservative"
```

Results go to `output/`, data caches to `data/`. To rebuild the published
site by hand: `python3 scripts/publish.py`.

## The ratings

All three are percentile ranks, 1–99, against the full US stock universe —
about 5,400 names after dropping preferreds, warrants, units, SPAC shells,
closed-end funds, and exchange-traded debt.

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

**Accumulation/Distribution Rating.** Day-over-day direction on volume over
13 weeks, recency-weighted with a ~1-month half-life, graded A+ through E−:

```
score = Σ clip(daily return, ±10%) · (volume ÷ avg volume) · decay ÷ Σ decay
```

Up days on heavy volume read as institutional buying, down days as selling.
The tempting alternative — where in the day's *range* the stock closed —
turns out to be nearly uncorrelated with the commercial grades, because it
can't see gap moves. This one lands within about a letter.

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
| A/D | within ~1 letter, rank correlation 0.67 |
| list membership | 58% of a captured weekly list, every miss traced |

Most of the remaining gap is data, not formulas: the commercial products run
their own earnings databases, which disagree with free street-EPS sources on
about 1 in 8 names. For calibration, two commercial screeners we compared
disagree with *each other* about as much.

## Data sources

Free, no API keys. NASDAQ's screener API supplies the universe and industry
groups in one request; Yahoo Finance supplies ~3 years of daily prices and
the earnings history. Yahoo's earnings-calendar endpoint rate-limits hard and
occasionally hangs mid-connection — the fetch layer isolates it in killable
subprocesses and converges over successive runs, and the weekly GitHub Action
keeps the cache warm between Fridays.

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
validation/         # captured commercial samples + comparison scripts
```

## License

MIT. See the note up top — this is an educational reconstruction of a
methodology, not a product or advice.
