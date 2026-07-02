# Methodology

> Status: target design for phase 5. This document is the statistical contract:
> anything the product displays must be computable under these rules. Initial
> threshold values are stated and expected to be tuned once real data lands.
> Last updated 2026-07-02.

## Principles

Descriptive, auditable statistics over an unexplainable model. Every figure
carries its sample size and an honest interval. Thin data is suppressed, not
smoothed over. Judge estimates are shrunk, bounded, and worded as tendencies.
The forecaster is validated in public against held-out real cases.

## Denominators

Getting denominators right is most of the honesty in this kind of product.

- **Resolved charges only.** A charge enters outcome statistics only when it
  has a final disposition. Pending charges are excluded from every rate.
- **One denominator per statistic, never mixed.** Dismissal rate is dismissed
  over resolved. Confinement rate is confinement over convictions. Trial
  conviction rate is trial convictions over trials. Each figure states its
  denominator in the payload.
- **Disposition categories are fixed** and mapped from raw text via the
  versioned lookup (DATABASE.md): dismissed, diversion, plea, trial_convicted,
  trial_acquitted, other. Diversion (ARD and program dispositions) is its own
  category: it is neither a conviction nor a dismissal and folding it into
  either would distort both.
- **The other and unmapped shares are published.** If the mapping cannot place
  a disposition, that mass is visible, not silently dropped.

## Proportions and intervals

All rates are reported with 95% Wilson score intervals, which behave properly
at small n and near 0 or 1, where the normal approximation lies. Exact
(Clopper-Pearson) intervals are the fallback for very small cells. Implemented
via `statsmodels.stats.proportion.proportion_confint`.

## Sentence lengths

Sentence length is a skewed distribution and is treated as one. Confinement
minimums are described by quantiles (P10, P25, P50, P75, P90), never a mean
alone. The minimum term is the headline number because in Pennsylvania's
indeterminate system it is the number closest to time actually served before
parole eligibility. Analyses of length are run on log(min_days) where a
symmetric scale is needed. Quantile uncertainty comes from the bootstrap
(percentile method, 2000 resamples).

Aggregation rule: analysis runs at the charge grain. Case-level total
sentences require concurrent-versus-consecutive structure that dockets state
inconsistently, so case-level totals are out of scope for v1 and flagged as a
limitation rather than approximated.

## The plea versus trial gap

Estimand: among convictions on the same statute and grade (and filing-year
band), the difference between plea convictions and trial convictions in (a)
confinement rate and (b) median minimum term. Reported with bootstrap
intervals.

Framing is regulated: this is a descriptive gap between two populations that
chose differently under different facts, not the causal penalty any one
person would face by switching paths. Selection into trial is real and the
product says so wherever the gap is shown.

## Charge reduction rate

Grade ranking: F1 > F2 > F3 > F(ungraded) > M1 > M2 > M3 > M(ungraded) > S.
A resolved case counts as reduced when its most serious convicted grade is
lower than its most serious filed grade, including the case where the top
charge fell away entirely and a lesser charge (possibly added later, which
appears as an additional charge row) resolved. Reported per top-filed
category with Wilson intervals.

## The judge model

The statistical core, handled with care because raw comparisons would confuse
a harsh judge with a judge who drew harder cases.

**Two outcomes per judge, estimated separately:**

1. **Confinement-rate offset.** P(confinement | conviction), judge versus
   court baseline within comparison groups (statute-grade cells, or category
   cells where statutes are thin). v1 estimator: empirical Bayes
   beta-binomial shrinkage of each judge's cell rates toward the court cell
   rate, pooled across cells by case weight. Transparent, fast, and
   defensible. A full logistic mixed model is the upgrade path if the
   shrinkage estimator proves too coarse (open item O-2 in DECISIONS.md).
2. **Length offset.** log(min_days) for confinement sentences, via a linear
   mixed model (`statsmodels` MixedLM): fixed effects for statute-grade and
   filing-year band, random intercept per judge. The judge effect
   exponentiates to a ratio versus the court median ("runs 1.15x the court
   median, 95% interval 1.04x to 1.27x").

**Partial pooling, in plain language.** Judges with few cases are pulled
toward the court average and only judges with enough cases carry their own
estimate. This is what stops a judge with nine cases and one unusual sentence
from looking extreme.

**Thresholds.** No judge estimate is published below `N_JUDGE_MIN` (initial
40) sentenced cases in the comparison group, and intervals accompany every
published offset. No judge is ever placed next to a number the data cannot
support.

**Case-mix adjustment and its limits.** Estimates condition on statute, grade,
and year. They do not condition on facts, criminal history (until Court
Summary data exists), or plea terms, and the product says so.

## Variance decomposition

The headline research question: how much of sentence variation is explained by
the charge, how much by the judge, and how much is unexplained. Answered as an
intraclass correlation from the mixed model: the share of residual log-length
variance attributable to the judge random effect after charge and year fixed
effects. The judge share, with its uncertainty, is a central published result.

## Calibration: the honesty check

The forecaster is validated by pretending the most recent data does not exist,
forecasting it, and grading the forecasts.

- **Holdout.** The most recent 6 to 12 months of resolved cases are held out;
  all distributions and judge effects are fit on earlier data only.
- **Disposition probabilities** are graded with calibration curves (predicted
  versus observed frequency by decile) and the Brier score, against a
  no-judge-information baseline so the judge layer's contribution is
  measurable.
- **Sentence quantiles** are graded by coverage: the P10-P90 band should
  contain roughly 80% of held-out sentences, per charge group.
- The backtest is rerun with every stats release and its results ship in the
  release (API.md `/calibration`), doubling as the live demo.

## Identification caveat

Judge estimates are cleanest where cases are assigned to judges at random.
Philadelphia's First Judicial District uses random judicial assignment in at
least some criminal programs precisely to prevent judge shopping, which helps.
Where assignment is not random, estimates are adjusted for observable case
characteristics and reported as descriptive tendencies, never as causal
effects. The product never claims what a different judge would have done in a
specific case.

## Known limitations (published alongside results)

- **The pandemic cohort.** 2020-2021 filings moved through a disrupted court.
  Year effects are always in the models, duration statistics are cohorted by
  filing year, and the window of each release is explicit.
- **Right censoring.** Recently filed cases that resolved quickly are
  overrepresented among recent resolved cases. Duration and outcome statistics
  for recent cohorts carry a censoring caveat until the cohort matures.
- **What dockets do not contain.** Plea terms, evidence, counsel quality,
  detention status, and (for now) prior record. The numbers condition on what
  the docket shows.
- **Case-level totals** are out of scope for v1 (concurrency, above).
- **Municipal Court is out of scope.** Many Philadelphia cases begin and end
  in Municipal Court; CP51 covers Common Pleas only for now (ROADMAP).

## Threshold constants (initial values, tunable)

| constant | value | governs |
|---|---|---|
| N_PAGE_MIN | 20 | resolved cases required for a charge bundle to exist |
| N_CAVEAT_BAND | 20-29 | bundle exists but carries a small-sample warning |
| N_METRIC_MIN | 30 | any individual published metric |
| N_JUDGE_MIN | 40 | sentenced cases in group for a judge estimate |
| BOOTSTRAP_B | 2000 | resamples for bootstrap intervals |