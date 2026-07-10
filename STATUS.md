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

**A/D rating validated and fixed (2026-07-05)**: against 9 captured IBD
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
