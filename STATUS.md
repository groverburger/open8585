# Status

**2026-07-05** — v0.3: validated against a captured IBD 85-85 list.

Overlap with IBD's 99-name list improved 5% → 56% over the session:

| change | overlap |
|---|---|
| naive first run (same-day prices, raw-growth EPS composite) | 5% |
| membership date = weekly compute date (2026-06-30), not print date | 25% |
| rank-based EPS composite (raw ±999 growth saturates percentiles) | 34% |
| street EPS backfill + loss-narrowing ≠ growth + ceil(99p) mapping | 34%* |
| closing (not intraday) 52-wk high, CEF exclusion, quarters-block required | 41% |
| quarters block weighted 60/40 vs multi-year leg | 45% |
| earnings stability factor (log-trend residual std, weight 0.25) | 56%* |
| full-universe percentiles, 3yr stability window, debt exclusion | **58%** |

*sampled-reference runs carry ±7 names of seed jitter; 58% is deterministic.

*same overlap, but component data became correct (DELL's +214% quarter
matched IBD exactly); the blend, not the data, was then the bottleneck.

Key empirical findings (all verified against the captured list):
- IBD computes list membership at the weekly close but prints daily-updated
  prices; validation must be as-of the compute date.
- IBD's Price %Chg / Vol %Chg columns are the daily change and volume vs
  50-day average (matched to the hundredth).
- 85/99 of IBD's names score ≥85 on our RS reconstruction; all misses are
  78–84.
- GAAP diluted EPS is unusable for stock-comp-heavy names (MRVL: −80% GAAP
  vs +29% street); street EPS is the critical data dependency.
- Yahoo's earnings-calendar endpoint rate-limits hard, returns *empty* (not
  errors) when throttled, and can hang inside C code where SIGALRM can't
  fire. Only subprocess isolation with a hard kill is reliable
  (`validation/backfill_one.py`); threaded bulk fetch works for income
  statements only.

The stability factor was the biggest single-change win: it raised recall
(46→56 of the names reaching the EPS stage) and cut extras (65→58)
simultaneously, and upgraded the remaining extras from erratic ±999 names
to steady industrials that plausibly sit just under IBD's bar.

## Difference decomposition (2026-07-05 investigation)

Every remaining divergence from IBD's list traced to a measured cause:

- **RS: fully explained by universe breadth.** Min RS across all 99 IBD
  names is 78; every near-miss (15 names, 78–84) flips to ≥85 at a modeled
  pool of 7,900 stocks — IBD rates ~8,000–10,000 incl. OTC vs our ~5,400
  listed. `--rs-pool 8000` models this (opt-in; it grows the list ~30%).
- **EPS deep misses: three causes.** (1) Reference-pool composition — IBD
  ranks against its whole junky database; a liquid-only reference
  over-tightens our bar (fixed: uniform, then full-universe default).
  (2) Stability window — 4yr window let 2022-era losses nuke recovered
  names IBD rates 85+ (MTZ, CAKE, BJRI); 3yr window fixed. (3) Vendor EPS
  databases — 12 of 98 names have printed EPS %Chg differing >15pts from
  Yahoo street EPS (VICR 271 vs 633, IHG's Yahoo earnings calendar ends in
  2013). Irreducible with free data, ~12% noise floor.
- **Reference-sample jitter was contaminating tuning decisions**: with a
  400-stock sample, IBD-overlap swings ±7 names on the sample seed alone
  (44–59 across five seeds). Full-universe percentiles (now default)
  eliminate the sampling entirely; --ref-sample N remains as quick mode.
- **No look-ahead**: all fundamentals used in the as-of validation were
  reported before IBD's compute date (verified per symbol).
- Also fixed: exchange-traded debt (baby bonds) had leaked into the
  universe/reference (GPJA-style "% Junior Subordinated Notes" listings).

Final miss decomposition (42 of 99, all causes measured, none unknown):
18 RS near-misses (pool breadth, all flip at --rs-pool 8000), 3 off-high
boundary/vendor cases, 11 EPS boundary (75–84), 10 EPS deep — of which PEB
is structural (IBD rates REITs on FFO), CARE/SMTC are vendor EPS-database
differences, and ~6 (MTZ, WLFC, BJRI, OPLN, ILMN, FLXS, NHC at 58–74) are
the residual formula difference: IBD rewards steady-but-slow earners more
than pure growth percentiles imply.

**A/D EMA conviction balance promoted locally (2026-09-22)**: the application
runtime now uses `ad_ema_conviction_balance_v1`. It retains the clean qualified
daily evidence discovered by the robust ledger, but replaces the hard
65-session window and `log((U+2)/(D+2))` stabilization with separate true EMAs
and the bounded score `100*(U-D)/(U+D)`. Both ledgers use a 20-session
half-life. The signal has zero fitted coefficients; fixed 2024-2025 boundaries
map -100..+100 pressure to A+ through E. Timestamp-aligned individual-label
rank agreement is 0.719 in 2025 and 0.645 in valid 2026; after the selected
C-only internal-boundary calibration, 68.7%/64.9% fall within one subgrade.
The exact equation, research path, calibration sources, failure modes, and
deployment distinction are recorded in `docs/ad_conviction_balance_model.md`.
The chart implementation now calls the application scorer directly. This is a
local working-tree promotion; publishing the GitHub Pages list is separate.

**Previous A/D robust-conviction ledger (promoted 2026-08-11)**: production used
`ad_robust_conviction_ledger_v1`, a coefficient-free technical indicator.
Meaningful up/down sessions qualify only above the prior 10-session mean
volume; their evidence is `log2(1 + relative volume) × (1 + |ATR move|)` and
decays over a 65-session ledger with a 20-session half-life. Twelve frozen
2024-2025 boundaries map the state to A+ through E. Held-out 2025 results are
0.685 stock-rank agreement, 66.0% within one subgrade, and 2.05 pp market
grade-share MAE. Valid 2026 through April 24 is 0.606, 63.1%, and 1.82 pp.
The outgoing 282-coefficient model remains byte-for-byte archived under
`validation/production_models/` for rollback.

**Previous A/D production model (2026-08-10 through 2026-08-11)**: the earlier nine-label model
below has been replaced by `ad_multi_volume_contraction_spike_v1`, fitted on
22,282 matched 2024-2025 Global Laggards table observations. It combines
asymmetric daily-bar pressure, 10/20/50/100-session relative volume, six EWM
memories, and a volume spike following five-session contraction. The frozen
runtime artifact is `open8585/ad_model.json`; production never reads training
labels or refits it. The originally reported through-August 2026 metrics were
later found to include broken source ratings after 2026-04-24 and are
superseded by the valid-period evaluation below.

**Previous A/D market-wide recalibration (2026-08-11)**: exact daily O'Neil universe
counts showed that the signal's timing was strong but the laggard-trained
isotonic mapping produced far too few B grades and too many D grades. The
282-feature signal remains frozen; production now uses 12 stable grade
thresholds whose four coarse boundaries were fitted on 2025 market-wide grade
shares. On 78 pre-break 2026 dates, aggregate A-E MAE improves from 8.78 to
2.54 percentage points. The source rating system broke beginning 2026-04-27;
all source labels and aggregate percentages from that date forward are
excluded from accuracy claims.

**Earlier A/D rating validation (2026-07-05)**: against 9 captured IBD
grades, the original close-location (intraday range) formula was
uncorrelated (Spearman +0.06) — it misses gap moves, so crash-on-volume
names (COHR, MTSI, GOOGL) read as accumulation. Replaced with capped daily
return × relative volume, recency-weighted (~1-month half-life) over 13
weeks: Spearman +0.67, every sample within ~1 letter grade
(`validation/ibd_ad_samples_2026-07.txt`).

**Per-stock IBD Checkup calibration (2026-07-05,
`validation/ibd_checkup_2026-07.txt`)**: five full rating vectors captured.
- RS: native pool matches IBD nearly exactly (4/5 within 1 pt) — the
  --rs-pool inflation hypothesis is refuted as a *rating* fix; the 85-85
  list RS near-misses were likely compute-date timing.
- EPS: MAE ~8 pts, no systematic bias (COHR −13 worst, consistent with its
  vendor EPS data gap).
- A/D: raw-score ordering right (Spearman ~0.67 on 10 labels), letter
  boundaries carry ~2/3-letter MAE; boundary refitting overfits 10 samples
  and was rejected — remaining error is in the raw score.
- Group RS letters added (`group_grade`): exact at the top (MU/COHR A+),
  harsh in the mid/low ranks where IBD's 197 proprietary groups diverge
  from NASDAQ's 146 buckets.
- SMR: not built (needs margins + ROE from balance sheets); the 5 captured
  SMR labels (4 A's, 1 B) are recorded for when it exists.

**Project goals (clarified 2026-07-05)**: (1) open-source the proprietary
IBD rating methodology; (2) support an Owen Cupp / Fred Richards-style
workflow: 85-85 list + A/D filter as the primary screen, pocket-pivot
entries layered on top. Priorities are RS, EPS, and A/D; SMR/Composite are
nice-to-have. `--min-ad` and `--min-eps-rs` implement the Richards
aggressive (B-, 180) and conservative (A-, 190) screens. Lecture
transcript: ~/Documents/projects/pocket-pivots/downloads/
2020-ibd-joint-day1-owen/.

**Three-way triangulation vs Deepvue (2026-07-10,
`validation/deepvue_samples_2026-07.txt` + checkup batch 2)**

RS on 8 IBD-labeled names spanning 21-99: ours MAE 1.1 (max 3) vs current
IBD; Deepvue MAE 8.0 (max 11) on its 3 shared names. ALAB/CRDO sit >=87th
percentile in every return window (1/3/6/12mo), so NO window-weighted
percentile — original-formula or otherwise — can produce Deepvue's 87-89
over a stock universe; their divergence is the ranking pool (likely ETFs/
everything-in-DB) or a non-price adjustment, not formula vintage. The
community claim that "IBD changed its formula and Deepvue keeps the
original" is not supported: our implementation of the *classic documented*
formula matches current IBD to ~1 point, which is evidence IBD's RS is
still rank-equivalent to the classic formula.

A/D: on the contested CRDO call (June 26: -11.2% on 4.5x volume), IBD's
C- sides with our D+ against Deepvue's A+. GDDY is our worst A/D miss
(ours C+, IBD A+): accumulation-into-decline, which our direction-times-
volume formula underweights — open improvement.

EPS: pairwise MAEs ~8-16 among all three vendors; we're closest to IBD on
2 of 3. ALAB (IBD 71 vs ours 96 with stellar quarters) suggests IBD
penalizes short earnings history (2024 IPO, no 3yr annual record) rather
than renormalizing like we do — but GEV (2024 spinoff) made IBD's 85-85
list, so the penalty isn't categorical. One data point each way; not
implemented.

Deepvue data-quality finding: CHAI/FRGT/ROLR/BLSH passed their "within
15% of 52-wk high" filter while 67-97% below adjusted 52-wk closing highs
(reverse-split artifacts on their side).

**Deepvue reverse-engineering (2026-07-10, preregistered tests)**

- H2 CONFIRMED (their data mishandles reverse splits): NASDAQ's official
  52-wk highs agree with ours — CHAI -96%, FRGT -93% (1:100 cumulative
  reverse splits), ROLR -82%, BLSH -79% off high — yet all four passed
  Deepvue's "<15% off 52-wk high" screen filter. Control (GDDY) matches
  the exchange to pennies on our side.
- H3 SUPPORTED (their A/D is a close-location/money-flow variant): the
  CLV formula we discarded (+0.06 rank corr vs IBD grades) reproduces
  Deepvue's three A/D grades within ~1 notch, including "accumulation"
  through CRDO's -11.2% on 4.5x volume. IBD's C- sides with our D+.
- H1 REFUTED (ETFs in the RS pool): only 19 of 4,933 ETFs outrank ALAB's
  weighted composite; adding the full ETF universe moves ALAB UP (99) and
  GDDY DOWN (16) — the opposite signature. Also refuted: all monotone
  window weightings (ALAB >=98th pctile in every window >1mo, so only
  1M-dominated weights demote it, which would put GDDY ~65 not 24) and
  vol-adjusted variants (slope t-stat, Clenow, return/vol — all crush
  GDDY to 1-11).
- RESOLVED by the full timeframe panel (9 names x 4 windows): Deepvue's
  1M/3M/6M ratings roughly track ordinary window-return percentiles
  (+-day-of-data drift), and their 12M is a recency-weighted composite in
  the classic family (fresh gainer STFS with a bottom-quartile 12-month
  return still rates 89; stale gainer LITE also 89 — the classic 40%%-
  recent-quarter balance, same as ours which rates both 98-99). BUT their
  12M is COMPRESSED AT THE TOP: eight elite-momentum names spanning our
  ranks 47-189 (ratings 96-99, IBD-confirmed 98-99 where labeled) all
  read 87-92 on Deepvue, six of them exactly 89. Implied mechanism:
  either an "everything" pool ~2x listed stocks (a consistent ~1,050
  instruments above every leader) or a deliberately flattened top-of-
  scale mapping — not separable from 9 points, same practical effect.
  Spearman of their 12M vs the classic ordering among these names: 0.60.
  Verdict on "Deepvue keeps the original formula": false at the top of
  the scale, where CANSLIM lives — the original formula reproduces
  current IBD to +-1 point; Deepvue reads 8-11 points cooler, so
  IBD-calibrated cutoffs (RS>84) silently exclude names IBD rates 90-95.

**Correction (2026-07-10): the "Yahoo blocks CI" diagnosis was wrong.**
The degraded CI run traced to a missing `lxml` dependency — yfinance's
get_earnings_dates silently returns empty without it, and both yfinance
and our fetch layer swallowed the ImportError. A controlled probe from a
fresh runner with lxml installed filled 12/12 symbols with full 24-quarter
histories. Fixes: lxml added to requirements; ImportError now raises
instead of being swallowed (a missing dependency is a config error, not a
data gap); all comments/docs corrected. The private-store + NASDAQ
incremental architecture stays as CI's street-EPS primary — it's gentler
than bulk earnings-calendar calls (which rate-limit under load from any
IP) and durable against vendor changes — with Yahoo now a working CI
fallback. Lesson recorded: silent exception-swallowing turned a one-line
dependency bug into a false architectural conclusion; probes must
distinguish error classes.

**One vendor per domain (2026-07-18).** The NASDAQ street-EPS path
(nasdaq_eps.py, the vendor-compatibility gate, --street-source) is removed:
NASDAQ is now solely the directory (universe + industries), Yahoo is every
number. CI street maintenance is a paced serial Yahoo pass (two tiers:
stale-covered names first, then 30-day rechecks of never-covered ones);
bulk threaded street calls are disabled in CI (OPEN8585_SKIP_BULK_STREET)
so they can't burn the rate budget. Data handling: the store's pre-purge
state is tagged `pre-yahoo-purge` (history preserved); all 385 symbols
whose street series diverged from the Yahoo-pure seed were re-sourced
fresh from Yahoo, with empty refetches falling back to the last Yahoo-pure
version rather than stripping data. Ratings verified unchanged for current
list members. The cross-vendor study and the SBC convention findings
remain in docs/RATINGS.md as research results; they're simply no longer a
production dependency.

## Known gaps / next ideas

- **85-85 index** (from the lecture): price-weighted index of list
  members, regenerated weekly; its 50-day MA cross is used as a
  margin-on/off market gate. Buildable from our weekly lists.
- **Earnings stability display**: IBD publishes stability 1-99 (<25 =
  stable enough for the PE-expansion model); we compute the raw metric
  already — expose it as a column.
- **Pocket pivot detection** on list members (entry timing) — likely its
  own module or project.
- 25%-advance-in-6-months claim for list debuts is backtestable with our
  --as-of machinery.

- The ~6-name residual: IBD's exact treatment of steady slow-growers
  (FLXS gets IBD EPS ≥85 with +1% growth). Possibly a stronger stability
  interaction or floor; needs more captured weeks to fit without
  overfitting.
- REIT FFO-based EPS (fixes PEB-class misses).
- Reference-sample ECDF (n=400) has ±2-3 rating points of jitter at the 85
  boundary; a larger sample would stabilize it.
- Move street-EPS fetching into the package as subprocess-isolated serial
  fetch; decouple "fetch" from "screen" so the screen never blocks on
  network.
- SEC XBRL companyfacts for deeper GAAP history; SMR/Composite ratings;
  weekly GitHub Action publishing the list.
