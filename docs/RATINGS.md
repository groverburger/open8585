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
stocks, matches IBD's **current** published RS ratings closely across 23
labeled samples captured on three different days — including a preregistered
15-stock out-of-sample panel. Rank agreement is near-perfect (Spearman 0.98);
scale agreement is MAE 1.1 on the first 8 famous-name samples and ~4 points
on the stratified panel, tightest exactly where the methodology operates:
every name IBD rates 84+ matched within 0–6 points, most within 4. Mid-scale
names disagree more (worst: 11 points) — that's where the composition of the
ranking universe shifts percentiles most, and IBD's universe is larger than
ours. First 8 samples:

| symbol | IBD | ours | | symbol | IBD | ours |
|---|---|---|---|---|---|---|
| MU | 99 | 99 | | MTSI | 95 | 94 |
| ALAB | 99 | 98 | | GOOGL | 85 | 85 |
| CRDO | 98 | 97 | | LLY | 85 | 82 |
| COHR | 96 | 96 | | GDDY | 21 | 24 |

Two conclusions follow, and the second is the interesting one. First, the RS
Rating is reproducible from public data — to within rounding at the top of
the scale, within a few points elsewhere. Second, the
community folklore that *"IBD changed its formula years ago"* is not
supported: the classic formula reproduces IBD's ratings **today**. If IBD had
materially changed the computation, a thirty-year-old reconstruction would
not land within a point of current output at the top of the scale and within
rank-equivalence everywhere.

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
  EPS Rating lands within ~9 points of IBD's across 23 labels (slight
  positive bias on the out-of-sample panel), with rare 20+ point outliers on
  erratic earners (COIN) and recent IPOs (ALAB — twice now, at the same gap,
  supporting a short-history penalty in IBD's formula). For calibration:
  Deepvue's EPS ratings, captured on the same 15 names the same day, land
  17.1 points from IBD's on average — roughly twice our distance. The vendor
  ceiling cannot be broken with free data, and apparently not with
  commercial data either.
- Open questions, recorded not guessed: ALAB (IBD EPS 71 despite spectacular
  quarters) suggests a short-history penalty for recent IPOs; GEV (2024
  spinoff, on the 85-85 list) argues it isn't categorical. One sample each
  way; unimplemented.

### A/D Rating: the least reproducible rating — an open problem

This is where honest reporting matters most, because our first conclusion
did not survive out-of-sample testing, and we're keeping both the original
claim and its failure on the record.

On the first 10 captured IBD grades, a day-over-day direction × volume
formula correlated at +0.67 while close-location money flow scored +0.06,
and a dramatic case (CRDO: −11.2% on 4.5× volume; IBD C−, direction-formula
D+, close-location A−) seemed decisive. On the preregistered 15-stock panel,
that identification **collapsed**: our formula's correlation with IBD's
grades fell to ~0.4–0.5, mean distance 3.3 letter notches, and the targeted
prediction failed outright — CNXC, fresh off an −8% day on 3× volume, drew a
**B** from IBD against our E+.

The panel also shows IBD's A/D doing things no momentum-flavored formula
does: A+ on GDDY and B on CNXC (beaten-down names), E on SANM and GLW
(strong uptrends). Whatever IBD measures, it appears partly *contrarian* —
possibly volume-versus-price divergence (accumulation into weakness) rather
than volume-with-price confirmation. That's a hypothesis for future work,
not a claim.

Where that leaves the evidence: across 25 labels, no formula we tested
reproduces IBD's A/D reliably; the three systems' A/D grades correlate
pairwise at only ~0.16–0.49 on the fresh panel. **Treat every cross-vendor
A/D comparison — including ours — as low-confidence.** Our published A/D
remains the direction-times-volume construction (it at least beat
close-location on pooled labels and has a defensible economic reading), but
it is the one rating in this project we cannot claim tracks IBD.

## The Deepvue system

Deepvue is a modern commercial screener whose ratings are described as
IBD-style, with a community reputation — repeated to us by a veteran
practitioner — of being *"more true to the original formula"* than modern
IBD. We tested that claim directly. Three findings, each independently
verifiable.

### 1. Their RS scale is compressed from both ends — replicated out-of-sample

Two independent captures, ten days apart, the second a preregistered
15-stock panel with symbols never used in any prior comparison, establish
the same pattern. Deepvue's 12M RS *ranks* stocks almost identically to IBD
(Spearman 0.987 on the panel) — but its *scale* is squashed toward the
middle: on names IBD rates 80+, Deepvue prints **8.4 points lower** on
average (ALAB: IBD 98, Deepvue 88; SANM: 93 vs 81); on names IBD rates 40
and below, Deepvue prints **5.2 points higher** (ACN: IBD 6, Deepvue 14).
In the first capture, six elite names spanning distinct ranks all printed
exactly 89.

We tested and refuted the mechanistic explanations we could check with
preregistered predictions — ETFs in the ranking pool (adding all 4,933 US
ETFs moves ratings the *opposite* direction), alternative window weightings
(no monotone combination fits both ALAB and GDDY), volatility adjustment
(crushes low-vol decliners far below Deepvue's actual values). What survives
is some combination of a larger ranking universe and/or a flattened rating
mapping — indistinguishable from outside, and practically equivalent:

**Deepvue cannot distinguish an IBD-99 from an IBD-90 (it prints both
~87–89), and it lifts the bottom of the scale.** A methodology whose
selection logic lives in the top 15 points of the scale, run with
IBD-calibrated thresholds (RS > 84) on Deepvue's numbers, selects a
different universe. And the community folklore inverts: the *original*
formula reproduces *current* IBD's scale; Deepvue's rescaling is their own
design, not fidelity to anything older.

### 2. Their 52-week-high data mishandles reverse splits

Four stocks passed a practitioner's Deepvue screen filtering for "within 15%
of 52-week high" while sitting **79–96% below their exchange-official
52-week highs**: CHAI (−96%, 1:4 reverse split), FRGT (−93%, three reverse
splits totaling 1:100 in 13 months), ROLR (−82%), BLSH (−79%). We verified
the real highs against NASDAQ's official 52-week high/low quote data, with a
clean control (GDDY matched to pennies). Collapsed micro-caps presented as
market leaders is the worst possible failure mode for a momentum screen, and
it is checkable by anyone in thirty seconds.

### 3. Their A/D rating: attribution withdrawn

In the first capture round, the close-location formula reproduced Deepvue's
three A/D grades within a notch — including an A+ on CRDO straight through
a −11.2% distribution day — and we published a tentative identification. The
preregistered panel falsified it: Deepvue graded CNXC **D** where the
close-location family predicts C-or-better, and across 15 names their A/D
correlates with IBD's at only 0.16 and with ours at 0.38. The honest
statement is the same one we now apply to ourselves: nobody's A/D
reproduces anybody's, and the formula families behind these ratings remain
unidentified. What stands is narrower: on the specific CRDO episode,
Deepvue's A+ through a heavy-volume crash disagreed with both IBD (C−) and
the tape's plain reading — worth knowing if A/D-based sell rules are part of
your process.

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
| RS | Spearman 0.98; ±0–6 in the top band, MAE ~4 full scale | 23 labels incl. preregistered panel |
| EPS | MAE ~9, rare 20+ outliers (erratic/IPO names) | 23 labels |
| A/D | weak: 0.4–0.7 across capture rounds — open problem | 25 labels |
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

The RS Rating is essentially solved: the classic public formula reproduces
IBD's current rankings at Spearman 0.98 and IBD's scale within a few points
— tightest in the top band where the methodology actually operates — which
simultaneously validates this implementation and falsifies the belief that
IBD's formula changed. The EPS Rating is reconstructible in structure
(including the stability factor, which uniquely improved recall and
precision together) but bounded near ±9 points by proprietary earnings
databases that disagree with every public source and each other — a bound
Deepvue's own EPS ratings, twice as far from IBD's on identical names, make
concrete. The A/D Rating is the honest failure: our initial formula
identification did not survive a preregistered out-of-sample panel, no
tested formula reproduces IBD's grades, and the three systems' A/D letters
barely correlate — it is reported here as an open problem, not a solved one.
Deepvue's RS is a monotone rescaling of the same ordering everyone computes,
compressed from both ends, which silently breaks IBD-calibrated thresholds.
Every claim above traces to files in `validation/`, including the
preregistration where two of our own predictions died; when a claim fails
the evidence, it's documented next to the ones that survived.
