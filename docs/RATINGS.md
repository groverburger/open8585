# Three rating systems, and the evidence for what we know about them

This document compares three implementations of the same rating concepts: the
proprietary originals published by Investor's Business Daily® ("IBD"), the
commercial ratings published by Deepvue, and the open implementation in this
repository. Everything below rests on captured samples and controlled tests —
the raw data lives in [`validation/`](../validation/), and every number here
can be recomputed from it. Where the evidence is thin, that's stated; the
claims that matter are not.

*Written July 2026. Sample sizes are what they are — captured by hand from
commercial products — and marked throughout. Trademarks belong to their
owners; this is independent research, not affiliated with any of them.*

---

## First, the vocabulary

**RS Rating (1–99)** — a percentile rank of price momentum against the full
stock universe. 99 means the stock outperformed 99% of stocks.

**EPS Rating (1–99)** — a percentile rank of earnings growth quality: recent
quarterly growth blended with the multi-year record.

**A/D Rating (A+ to E−)** — a letter grade for institutional accumulation
(buying) versus distribution (selling), read from price/volume behavior.

**The 85-85 list** — stocks rated 85+ on both EPS and RS, priced $10+, within
15% of their 52-week high, with minimum liquidity. The methodology's core
screen; its highest-signal event is a stock's *first appearance* on it.

**Street vs. GAAP earnings — the fault line under everything.** GAAP EPS is
the audited, legally mandated figure and includes every one-time item; street
(adjusted) EPS strips those to represent operating earnings, and every data
vendor strips differently. Two facts measured in this project set the stakes:

1. GAAP is unusable for growth ratings on stock-comp-heavy companies — MRVL's
   same quarter is **−80% growth on GAAP, +29% on street**; PANW had a
   GAAP-negative quarter that street scored +6%.
2. Even street vendors split. Across 501 matched quarters from 140 symbols,
   Yahoo's source (SBC excluded) and NASDAQ's source (Zacks, SBC expensed)
   **agree to the penny 49% of the time and differ by more than 10% in 43%
   of quarters**, with sign flips on high-SBC names (SNOW: +0.32 vs −0.80,
   same quarter, both "street").

Any comparison of rating systems that ignores whose earnings database sits
underneath is measuring data vendors, not formulas. Keep that in mind for
every EPS claim below.

---

## The IBD system

IBD's formulas have been proprietary for four decades. What follows is what we
established empirically, validated against two kinds of captures: a full
85-85 weekly list (99 stocks) and per-stock Stock Checkup rating panels.

### RS Rating: the classic formula, still in production

The reconstruction documented in the public record since the 1990s is
twelve-month performance with the most recent quarter double-weighted:

```
raw = 2·(P/P₆₃) + (P/P₁₂₆) + (P/P₁₈₉) + (P/P₂₅₂)     → percentile 1–99
```

Our implementation of exactly that formula, ranked against ~5,400 listed US
stocks, matches IBD's **current** published RS ratings to a mean absolute
error of **1.1 points across 8 labeled samples spanning the full scale**
(21 to 99), maximum error 3:

| symbol | IBD | ours | | symbol | IBD | ours |
|---|---|---|---|---|---|---|
| MU | 99 | 99 | | MTSI | 95 | 94 |
| ALAB | 99 | 98 | | GOOGL | 85 | 85 |
| CRDO | 98 | 97 | | LLY | 85 | 82 |
| COHR | 96 | 96 | | GDDY | 21 | 24 |

Two conclusions follow, and the second is the interesting one. First, the RS
Rating is reproducible from public data to within rounding. Second, the
community folklore that *"IBD changed its formula years ago"* is not
supported: the classic formula reproduces IBD's ratings **today**. If IBD had
materially changed the computation, a thirty-year-old reconstruction would
not land within a point of current output across the whole scale.

Supporting evidence at list level: 85 of the 99 stocks on IBD's printed 85-85
list score ≥85 on our RS, with every miss in the 78–84 band, attributable to
compute-date timing (IBD fixes list membership at a weekly close; we proved
their capture date by showing all 99 printed prices match our data to the
penny, while several members sat 20–30% off their 52-week highs at *our*
compute date — they'd crashed after IBD's).

### EPS Rating: reconstructible in shape, vendor-limited in precision

IBD describes the inputs — the two most recent quarters' YoY growth and the
3–5 year growth record — but not the blend. Everything else we established by
testing against captures:

- **The earnings stability factor is real and load-bearing.** Adding it
  (residual of log quarterly EPS around its 3-year trend) to our
  reconstruction improved recall of IBD's list *and* cut false extras
  simultaneously (recall 46→56 of 81, extras 65→58) — the only change in the
  whole calibration with that signature. Uncalibrated tuning knobs trade one
  for the other; real components of the target formula improve both.
- **Recent quarters dominate the multi-year leg.** IBD demonstrably rates
  cyclicals with huge current quarters and flat multi-year records (DELL,
  TER, SIMO) at 85+; only a quarters-heavy blend reproduces that.
- **Their EPS %Chg arithmetic matches ours nearly exactly** where the vendor
  data agrees: DELL 213.5 vs their 214, PLOW 300 vs 300, MTZ 172.5 vs 173.
  The ±999 conventions (turned-profitable sentinel, display cap) match their
  printed tables (GEV, CARE).
- **The precision ceiling is the vendor database, not the formula.** 12 of 98
  names show >15-point differences between IBD's printed EPS %Chg and Yahoo
  street EPS (VICR: 271 vs 633) — different adjustment conventions, same
  class of disagreement we measured between Yahoo and NASDAQ. Per-stock, our
  EPS Rating lands within ~8 points of IBD's (8 samples), no directional
  bias. That ceiling cannot be broken with free data, and probably not with
  any single alternative vendor.
- Open questions, recorded not guessed: ALAB (IBD EPS 71 despite spectacular
  quarters) suggests a short-history penalty for recent IPOs; GEV (2024
  spinoff, on the 85-85 list) argues it isn't categorical. One sample each
  way; unimplemented.

### A/D Rating: direction-times-volume, not close location

Two formula families compete in the public lore. They are distinguishable on
data, and IBD's behavior picks one decisively:

- **Close-location money flow** (where in the day's *range* the stock closed,
  volume-weighted): rank correlation **+0.06** against 10 captured IBD grades
  — statistically nothing. Its structural blind spot: gap moves. A stock that
  gaps down 11% and closes mid-range reads as neutral-to-positive.
- **Day-over-day direction × relative volume, recency-weighted**: rank
  correlation **+0.67** on the same labels, every sample within about one
  letter grade.

The decisive case: CRDO fell −11.2% on 4.5× average volume on June 26, 2026 —
the heaviest volume day in its 13-week window — and chopped downward for two
weeks after. IBD's A/D: **C−**. The direction-times-volume formula: D+. The
close-location formula: A−. IBD's rating saw the distribution day; the
close-location family cannot. (Our worst miss is the mirror case: GDDY, where
IBD sees A+ accumulation into a declining stock and we say C+ — logged as an
open improvement.)

---

## The Deepvue system

Deepvue is a modern commercial screener whose ratings are described as
IBD-style, with a community reputation — repeated to us by a veteran
practitioner — of being *"more true to the original formula"* than modern
IBD. We tested that claim directly. Three findings, each independently
verifiable.

### 1. Their RS ratings diverge from IBD exactly where it matters most

A full per-timeframe capture (9 symbols × 4 windows, chosen to discriminate
between formula families — fresh gainers, stale gainers, mid-scale controls)
established that Deepvue's 1M/3M/6M ratings approximately track ordinary
window-return percentiles, and their 12M is a classic-family recency-weighted
composite. But the top of their 12M scale is **compressed**: eight elite
momentum names spanning our ranks 47–189 of 5,303 — rated 96–99 by the
classic formula and 98–99 by IBD where labeled — all print **87–92 on
Deepvue, six of them exactly 89**. Rank ordering among those leaders
correlates with the classic ordering at only Spearman 0.60.

We tested and **refuted** the innocent explanations with preregistered
predictions:

- *ETFs in the ranking pool*: adding all 4,933 US ETFs to our pool moves
  ratings the **opposite** direction (only 19 ETFs outrank ALAB's composite;
  ALAB rises to 99, GDDY falls to 16 — Deepvue shows 89 and 24).
- *Different window weights*: ALAB sits ≥98th percentile in every window
  longer than a month; only a 1-month-dominated weighting demotes it, and
  that same weighting would put GDDY near 65, not 24. No monotone combination
  fits both.
- *Volatility adjustment*: every variant tested (slope t-stat, Clenow,
  return/vol) crushes GDDY to 1–11. Deepvue shows 24.

Two mechanisms survive: a ranking pool roughly twice the listed-stock
universe (the implied count of instruments above every leader is eerily
constant at ~1,050), or a deliberately flattened top-of-scale mapping. The
nine captured points can't separate them — but both have the same practical
consequence: **Deepvue cannot distinguish an IBD-99 from an IBD-90; it
prints them both 89.** For a methodology whose entire selection logic lives
in the top 15 points of the scale, that's not a cosmetic difference. And the
folklore inverts: the *original* formula reproduces *current* IBD;
Deepvue's divergence is their own design, not fidelity to anything older.

### 2. Their 52-week-high data mishandles reverse splits

Four stocks passed a practitioner's Deepvue screen filtering for "within 15%
of 52-week high" while sitting **79–96% below their exchange-official
52-week highs**: CHAI (−96%, 1:4 reverse split), FRGT (−93%, three reverse
splits totaling 1:100 in 13 months), ROLR (−82%), BLSH (−79%). We verified
the real highs against NASDAQ's official 52-week high/low quote data, with a
clean control (GDDY matched to pennies). Collapsed micro-caps presented as
market leaders is the worst possible failure mode for a momentum screen, and
it is checkable by anyone in thirty seconds.

### 3. Their A/D rating is the close-location family

The close-location formula — the one that scores +0.06 against IBD's actual
grades — reproduces Deepvue's captured A/D grades within about one notch,
including rating CRDO **A+** straight through the −11.2%, 4.5×-volume
distribution day that IBD graded C−. For traders whose sell rule is "exit
when A/D drops below B," this is the difference between a rating that fires
and one that sleeps.

**Fairness notes.** Deepvue documents more of its methodology than IBD does,
and ranking against a broader database is a legitimate design choice — these
findings establish that their ratings are *different instruments*, not that
anyone is dishonest. But two things are not matters of taste: the reverse-
split data errors, and the fact that IBD-calibrated thresholds (RS > 84, A/D
≥ B) silently select a different universe when applied to Deepvue's scales.
A practitioner running "the same screen" on both platforms is not running
the same screen.

---

## The Open8585 system

Ours. The formulas are printed in full in the [README](../README.md); this
section is about *why* each constant is what it is, and what we know about
the system's accuracy.

**The calibration protocol.** No constant in this codebase was chosen by
feel. The procedure, applied repeatedly: capture samples of the commercial
target → form a hypothesis → write down what it predicts → test → keep or
revert. The record includes our own refuted hypotheses, kept deliberately:
the RS "pool inflation" model (refuted by per-stock checkup captures), the
close-location A/D formula (refuted by IBD grades, later revealing itself as
Deepvue's likely formula), the ETF-pool theory of Deepvue's compression
(refuted by direct counterfactual). A calibration story that contains no
dead ends should not be believed.

**Current measured state:**

| rating | agreement with IBD captures | basis |
|---|---|---|
| RS | MAE 1.1 pts, max 3, full scale | 8 per-stock labels |
| EPS | MAE ~8 pts, no directional bias | 8 per-stock labels |
| A/D | rank corr 0.67, ~1 letter | 10 per-stock labels |
| 85-85 membership | 58%, every miss traced | 99-stock list capture |

The 42 membership misses decompose completely: 18 RS timing (compute-date
offsets, all in the 78–84 band), 3 boundary/vendor cases on the off-high
filter, 11 EPS threshold-boundary cases, and 10 deep EPS misses of which one
is structural (IBD rates REITs on funds-from-operations), two-three are
vendor-database differences, and roughly six are a genuine residual — IBD
rewards steady-but-slow earners (FLXS at +1% growth carries an IBD EPS ≥85)
more than any pure growth percentile can. Nothing is unexplained; the
residual is named and bounded.

**Lessons that shaped the system, all learned from incidents:**

- *Sampling jitter*: EPS ratings percentiled against a 400-stock reference
  sample swing list membership by ±7 names on the sample seed alone. The
  system now ranks against the full universe — deterministic by
  construction.
- *Data provenance dominates formula fidelity*: an environment where street
  EPS silently degraded to GAAP churned 51 of 98 list names with zero code
  changes. The publish pipeline now hard-aborts if street-EPS coverage drops
  below 50%, and cached history can never be overwritten by an empty fetch.
- *Vendor conventions are not interchangeable*: cross-vendor merges are
  gated on measured agreement over overlapping quarters, because appending a
  Zacks-convention quarter onto Yahoo-convention history fabricates an
  earnings cliff for stock-comp-heavy names.

**Honest limitations.** The EPS Rating inherits the vendor noise floor
(~1 in 8 names disagree >15% across databases — including IBD's own vs
anyone else's). Industry group ranks use NASDAQ's ~150 classifications
against IBD's 197 proprietary groups and are only reliable at the top of the
scale. The A/D letter boundaries carry about two-thirds of a grade of noise.
And all IBD-agreement figures rest on samples captured in July 2026 —
single-digit-to-dozens of labels, not thousands. They are the best evidence
anyone outside these companies has published; they are still samples.

---

## The one-paragraph verdict

The RS Rating is a solved problem: the classic public formula reproduces
IBD's current output to about a point, which simultaneously validates this
implementation and falsifies the belief that IBD's formula changed. The EPS
Rating is reconstructible in structure — including the stability factor,
which the evidence strongly supports as a real component — but bounded in
precision by proprietary earnings databases that disagree with every public
source and with each other. The A/D Rating's formula family is identifiable
from data, and IBD's behavior matches direction-times-volume, not close
location — a distinction with direct trading consequences that at least one
commercial competitor appears to get wrong, alongside measurable data-quality
defects. Every claim above traces to files in `validation/`; when a claim
died on the evidence, it's documented next to the ones that survived.
