# Preregistered verification panel — 2026-07-13

Purpose: out-of-sample re-test of every public claim in docs/RATINGS.md
before publication. All predictions below are computed from the Friday
2026-07-10 close (the published weekly run, site/data/ratings_2026-07-11.csv,
already committed) and written down BEFORE any fresh captures. 12 of the 15
symbols have never been used in calibration or prior comparisons; ALAB and
GDDY repeat as consistency checks, CNXC is a targeted discriminator.

Capture window: IBD and Deepvue ratings roll after each close. Captures made
Monday 2026-07-13 before the close reflect Friday's close (direct
comparison); captures after Monday's close carry one session of drift —
expect RS +-2 points extra tolerance.

## Our values (fixed, from the published Friday run)

| symbol | RS | EPS | A/D |
|---|---|---|---|
| UCTT | 98 | 41 | B |
| GLW | 96 | 88 | C |
| PTGX | 93 | 31 | B |
| SANM | 91 | 95 | E- |
| CHRW | 84 | 47 | D+ |
| CASY | 81 | 90 | C+ |
| DE | 61 | 48 | D |
| EME | 65 | 90 | E |
| MCK | 44 | 84 | D- |
| COST | 38 | 63 | E+ |
| ACN | 12 | 72 | E- |
| COIN | 16 | 40 | D |
| ALAB | 98 | 96 | A- |
| GDDY | 25 | 85 | C+ |
| CNXC | 12 | 44 | E+ |

## Predictions

P1 — IBD RS tracks ours within +-3 points on all 15 names (claim: the
classic formula reproduces current IBD RS; MAE so far 1.1 on 8 samples).
FALSIFIED IF: any |IBD - ours| > 5, or MAE across the panel > 3.

P2 — IBD EPS lands within ~12 points of ours on profitable, analyst-covered
names (claim: structure right, vendor-DB noise floor ~8pts). Expect the
occasional larger miss on thin-coverage or recent-IPO names.
FALSIFIED IF: MAE > 15 or a systematic sign bias appears.

P3 — IBD A/D within ~1.5 letter grades of ours; specifically CNXC (big down
day on >3x volume last week; ours E+) grades D-or-worse at IBD.
FALSIFIED IF: IBD grades CNXC B- or better.

P4 — Deepvue RS 12M compresses the top: UCTT, GLW (ours 96-98; ALAB repeat
98) print 92 or below on Deepvue while IBD prints them 95+.
FALSIFIED IF: Deepvue prints any of them >= 95 (compression claim dies) or
IBD prints them <= 92 (our calibration claim weakens instead).

P5 — Deepvue A/D behaves close-location: CNXC (our E+, close-location raw
+0.11) grades C or BETTER on Deepvue despite the distribution week.
FALSIFIED IF: Deepvue grades CNXC D or E.

P6 — Deepvue's displayed "% off 52-week high" for FRGT and CHAI shows them
far closer to their highs than the exchange-official figures (FRGT true
-93%, CHAI true -96%, per NASDAQ official 52-week high/low).
FALSIFIED IF: Deepvue displays approximately the official figures — then
the earlier screen result had a different cause and the data-quality claim
must be retracted.

P7 — consistency: ALAB and GDDY captures land within +-2 (RS) of their
2026-07-10 captures (IBD 99/21, Deepvue 12M 89/25) after accounting for
market drift.

## What gets published where

The Deepvue-critical sections of docs/RATINGS.md ship only if P4-P6 hold.
If any falsify, the doc is corrected first - that is the point of this file.
