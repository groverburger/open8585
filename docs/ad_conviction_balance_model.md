# A/D EMA conviction-balance model

Status: promoted into the local application runtime on 2026-09-22. This note
documents the model in `open8585/ratings.py` and `open8585/ad_model.json`.
Promotion into the local runtime is not the same thing as publishing a new
GitHub Pages list; deployment remains a separate operation.

## Purpose

The A/D rating is intended to summarize whether a stock is showing evidence of
institutional accumulation or distribution. The implementation is deliberately
a technical indicator, not a regression model: it has no fitted signal
coefficients, symbol effects, residual correction, shock overlay, or market
regime adjustment. Twelve fixed boundaries translate one continuous technical
state into the thirteen displayed grades from E through A+.

The design question is: over recent history, has meaningful high-participation
price movement contained more evidence of demand or supply?

## Exact daily equation

For session `t`:

```text
return[t] = (close[t] - close[t-1]) / close[t-1]

prior_volume10[t] = mean(volume[t-10] ... volume[t-1])
relative_volume[t] = volume[t] / prior_volume10[t]

true_range[t] = max(
    high[t] - low[t],
    abs(high[t] - close[t-1]),
    abs(low[t] - close[t-1])
)

ATR20[t] = mean(true_range[t-19] ... true_range[t])
atr_move[t] = clip((close[t] - close[t-1]) / ATR20[t], -1, +1)

qualifies[t] =
    abs(return[t]) >= 0.002
    and relative_volume[t] > 1.0

evidence[t] =
    log2(1 + relative_volume[t]) * (1 + abs(atr_move[t]))
    if qualifies[t]
    else 0
```

The direction of the close-to-close return assigns that evidence to one of two
ledgers:

```text
up_evidence[t]   = evidence[t] if return[t] > 0 else 0
down_evidence[t] = evidence[t] if return[t] < 0 else 0
```

Each ledger is a true exponential moving average with a 20-session half-life:

```text
alpha = 1 - 0.5 ** (1 / 20)

U[t] = alpha * up_evidence[t]   + (1-alpha) * U[t-1]
D[t] = alpha * down_evidence[t] + (1-alpha) * D[t-1]
```

The continuous state is the bounded balance between accumulated demand and
supply evidence:

```text
score[t] = 100 * (U[t] - D[t]) / (U[t] + D[t])
```

When neither ledger contains evidence, the score is zero. The score is bounded
from -100 to +100. Positive values mean accumulation evidence has dominated;
negative values mean distribution evidence has dominated.

## Why these ingredients survived

### Close-to-close direction

The rating needs to recognize gaps and overnight repricing. Close-location and
open-to-close formulas can call a stock accumulated after it gaps sharply down
and merely closes near the top of that day's range. In the larger extracted
label panel, multiplying the event by close location or candle body reduced
stock accuracy and weakened the market stress series. Close-to-close direction
was the cleanest assignment of evidence to accumulation or distribution.

### A 0.2% minimum move

Very small closes are often noise or rounding. Requiring a move of at least
0.2% prevents unchanged sessions from casting institutional votes.

### Volume above the preceding 10-session mean

The previous ten sessions establish a short, causal participation baseline;
the current session is not included in its own comparison. The 10-session
reference was consistently more informative than longer volume baselines.
Requiring above-normal participation makes the measure about institutional
evidence rather than ordinary drift.

### Logarithmic relative volume

Linear relative volume lets one exceptional print dominate weeks of evidence.
`log2(1 + relative_volume)` preserves ordering and gives normal volume a
natural scale of one while compressing the extreme tail.

### ATR-normalized result strength

A qualifying session receives a base vote even when its price result is
modest. A larger move relative to the stock's normal true range strengthens
that vote. Capping the ATR move at one prevents a single price shock from
overwhelming the persistent state.

### Separate accumulation and distribution memories

Keeping U and D separately retains the balance of positive and negative
institutional evidence. A single EMA of signed flow loses information when
strong accumulation and distribution coexist.

### A true EMA rather than a 65-session cutoff

The preceding robust-conviction ledger retained exactly 65 sessions and then
dropped an observation abruptly. The true EMA keeps the same interpretable
20-session half-life without an arbitrary cliff: an event's influence becomes
progressively negligible but never disappears in one step. This change
improved individual-stock ranking and tightened the error distribution in both
the 2025 and valid-2026 comparisons.

### Bounded balance rather than log odds

The previous score was `log((U + 2) / (D + 2))`. The `+2` pseudo-count was a
stabilizer invented during reconstruction, not an O'Neil-supported concept.
The bounded balance is simpler, needs no prior, has an intuitive -100 to +100
scale, and performed at least as well. An ablation also showed that absolute
net pressure `U-D` was inferior to normalizing by total evidence `U+D`.

## From the original implementation to this model

The investigation passed through several distinct stages:

1. **Original live formula.** A 65-session sum of clipped return times volume,
   cross-sectionally split into fixed percentiles. It could not reproduce the
   varying proportions in the official market-wide A/B/C/D/E series.
2. **Large fitted models.** Price/volume states, multiple memories, asymmetric
   factors, contraction/expansion events, and isotonic calibration reached
   stronger fits, but one candidate required hundreds of coefficients. It was
   useful for discovering ingredients, not acceptable as the desired clean
   technical indicator.
3. **Traditional event ledgers.** Counting meaningful up/down sessions on
   elevated volume reproduced market stress surprisingly well and established
   that institutional participation should be the core unit of evidence.
4. **Robust conviction ledger.** Log-compressed relative volume and
   ATR-normalized result strength materially improved stock separation. A
   65-session exponentially weighted log-odds state became the first clean
   production candidate.
5. **Aggregation ablation.** With daily evidence frozen, finite-window bounded
   pressure, net pressure, and true-EMA pressure were compared. The true EMA
   removed the cutoff, while bounded normalization removed the pseudo-count.
6. **Timestamp correction.** Global Laggards labels printed on a Thursday
   generally reflected the preceding completed Wednesday U.S. bar. Matching
   individual labels to that prior session materially improved rank agreement.
   The daily aggregate workbook is already dated to its market session and is
   not shifted.
7. **Internal-grade calibration.** The official workbook supervises only the
   broad A/B/C/D/E boundaries. Individual Global Laggards labels supervise the
   plus/base/minus boundaries. The selected `c_observed_share_75pct` adjustment
   widened the central C band to reduce the artificial C-/C+ split while
   preserving all four broad-letter boundaries exactly.

The B- concentration remains a known internal-boundary issue. A B-band plateau
alternative was studied but not promoted. Steve's workbook cannot resolve it
because it contains only total B, not B-, B, and B+ separately, while Global
Laggards is a laggard-selected source with relatively few upper-grade examples.

## Ground truth and calibration protocol

Two sources supervise different parts of the mapping:

- `validation/oneil_ad_summary_labels.csv`: 74,304 extracted stock/date letter
  labels across 3,267 symbols and 271 Global Laggards report dates. The matched
  liquid panel supplies individual ordering and internal subgrade boundaries.
- Steve's workbook, `20260806 AD Spreadsheet A and B Chart normal download.xlsx`:
  daily whole-universe A/B/C/D/E counts and percentages. It supplies the four
  coarse boundaries and market-distribution validation, but no ticker labels
  and no plus/minus breakdown.

The validation universe requires close >= $5 and trailing 20-session average
dollar volume >= $1 million. That screen materially improves comparison with
the institutional-stock universe represented by the official series. Runtime
scores themselves are absolute technical states; they are not daily percentile
buckets.

The source ground-truth system broke beginning 2026-04-27. No observation on
or after that date may be used for model fitting or an accuracy claim.

The temporal protocol was:

```text
2024: fit candidate boundaries
2025: validate/select the indicator family and calibration approach
2024+2025: refit the final fixed boundaries
2026 through 2026-04-24: out-of-time audit
```

Because several successive hypotheses were examined after seeing valid-2026
results, 2026 is an out-of-time audit rather than a pristine untouched holdout.
Independent repaired ground truth is required for a genuinely fresh test.

## Frozen validation evidence

The timestamp-aligned EMA signal, followed by the selected C-band internal
calibration, produced these individual-label results:

| Period | Observations | Raw rank | Exact subgrade | Within one | MAE (subgrades) |
|---|---:|---:|---:|---:|---:|
| 2025 | 11,795 | 0.719 | 32.1% | 68.7% | 1.187 |
| Valid 2026 through Apr 24 | 4,053 | 0.645 | 30.5% | 64.9% | 1.312 |

Before the internal C-only redistribution, broad market-share MAE was 2.004
percentage points in 2025 and 1.895 points in valid 2026. The C-only change
does not alter broad A/B/C/D/E membership, so those broad-share metrics remain
the applicable frozen aggregate evidence. Valid-2026 B/D/E daily correlations
were 0.961, 0.978, and 0.958.

These numbers describe aggregate agreement and selected-stock label agreement;
they do not mean that approximately 95% of individual stocks have the correct
letter. The two questions are different.

## Frozen grade boundaries

The score crosses the following thresholds in ascending order:

```text
E / D-   -30.6840102099
D- / D   -22.7782461966
D / D+   -15.0582816204
D+ / C-  -11.8788026611
C- / C    -3.8535151920
C / C+     2.2851098463
C+ / B-    5.1110675444
B- / B     20.5321926927
B / B+     24.0940603325
B+ / A-    37.0425407903
A- / A     46.3976972808
A / A+     59.5336313677
```

These values are runtime constants. The application never reads the PDFs or
spreadsheet and never refits boundaries while generating a list.

## Runtime and reproducibility

- Runtime equation: `open8585/ratings.py`
- Frozen runtime parameters: `open8585/ad_model.json`
- Reproducible exporter: `validation/export_ad_production_model.py`
- Core experiment: `validation/ad_clean_effort_result_experiments.py`
- Core results: `validation/ad_clean_effort_result_experiments.json`
- Internal-boundary experiment: `validation/ad_internal_grade_calibration.py`
- Timestamp evidence: `validation/ad_timestamp_alignment_report.md`
- Source catalog: `docs/oneil_pdf_library.md`
- Immutable production snapshot:
  `validation/production_models/ad_ema_conviction_balance_v1/`

The breadth chart script imports the application's scoring function rather
than carrying a second copy. A parity test independently recomputes the full
equation and checks the runtime output, reducing the chance that research
charts and application grades silently diverge again.

## Limitations

- Global Laggards is intentionally biased toward weak stocks and has sparse
  A/B examples. It is strong supervision for the lower half of the scale but
  imperfect for upper-grade sub-boundaries.
- Steve's workbook covers a larger universe than the Yahoo liquid universe and
  cannot identify which stocks received each grade.
- Absolute thresholds can drift if the vendor's adjusted price/volume history
  changes materially.
- Daily bars can reveal close-to-close direction, range, and participation but
  cannot reveal true intraday institutional order flow.
- The A/D rating remains a reconstruction, not the proprietary O'Neil formula.
