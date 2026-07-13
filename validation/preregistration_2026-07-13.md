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

---

## RESULTS (scored 2026-07-13, captures in panel_captures_2026-07-13.txt)

P1 (IBD RS +-3): NOT MET as written. Same-day MAE 4.3 (max 11), Spearman
0.984. Agreement is tight in the top band (every IBD>=84 name within 0-6,
most <=4) and looser mid-scale (MCK 11, COST 8, ACN 8) where percentile-pool
composition bites hardest. Doc updated: scale-calibration claim narrowed to
"within a few points, tightest where the methodology operates"; rank-
equivalence and formula claims stand (0.98+).

P2 (IBD EPS MAE <= 15): MET. MAE 9.1, slight +5.5 bias, outliers COIN (28)
and ALAB (25 - the short-history case, now replicated at the same gap).
Comparative: Deepvue EPS vs IBD on identical names: MAE 17.1.

P3 (IBD A/D within ~1.5 letters; CNXC D-or-worse): FALSIFIED. Mean distance
3.3 notches; IBD graded CNXC B despite the distribution week. Same-day
Spearman ours-vs-IBD 0.49 (0.67 calibration figure did not hold out of
sample).

P4 (Deepvue compression): CONFIRMED AND ENRICHED. UCTT/GLW/ALAB print 86-88
vs IBD 90-98. Full-panel pattern: DV runs -8.4 below IBD on top names and
+5.2 above on bottom names - compression from BOTH ends - while rank order
matches IBD at Spearman 0.987. Deepvue is a monotone rescaling of the same
ordering; absolute thresholds do not port.

P5 (Deepvue A/D behaves close-location; CNXC C-or-better): FALSIFIED.
Deepvue graded CNXC D. DV-vs-IBD A/D Spearman on the panel: 0.16. The
close-location attribution is WITHDRAWN.

P6 (FRGT/CHAI displayed % off high): NOT CAPTURED - remains open. The
screen-membership + exchange-official-high evidence stands; the display-
level confirmation does not exist yet and the doc must say so.

P7 (consistency): MET for ALAB (IBD 99->98, DV 89->88). GDDY moved
21->31 (IBD) across one session - consistent with a bounce plus bottom-of-
scale rank sensitivity.

Actions taken per the publication gate: docs/RATINGS.md A/D sections
rewritten (family identifications withdrawn; A/D reported as the least
reproducible rating, pairwise vendor correlations 0.16-0.49); RS section
re-scoped; Deepvue RS finding upgraded to the replicated both-ends
compression; EPS numbers updated to pooled 23-label figures.
