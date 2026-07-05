# Status

**2026-07-05** — v0.2: validated against a captured IBD 85-85 list.

Overlap with IBD's 99-name list improved 5% → 45% over the session:

| change | overlap |
|---|---|
| naive first run (same-day prices, raw-growth EPS composite) | 5% |
| membership date = weekly compute date (2026-06-30), not print date | 25% |
| rank-based EPS composite (raw ±999 growth saturates percentiles) | 34% |
| street EPS backfill + loss-narrowing ≠ growth + ceil(99p) mapping | 34%* |
| closing (not intraday) 52-wk high, CEF exclusion, quarters-block required | 41% |
| quarters block weighted 60/40 vs multi-year leg | **45%** |

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

## Known gaps / next ideas

- Remaining IBD misses: ~15 RS near-misses (78–84, irreducible), ~35 EPS
  boundary/stability cases, plus IBD's editorial "industry group leaders"
  curation which no formula matches.
- No EPS stability factor yet (IBD penalizes erratic earnings) — likely the
  best remaining lever for cutting our ~65 extras.
- Reference-sample ECDF (n=400) has ±2-3 rating points of jitter at the 85
  boundary; a larger sample would stabilize it.
- Move street-EPS fetching into the package as subprocess-isolated serial
  fetch; decouple "fetch" from "screen" so the screen never blocks on
  network.
- SEC XBRL companyfacts for deeper GAAP history; SMR/Composite ratings;
  weekly GitHub Action publishing the list.
