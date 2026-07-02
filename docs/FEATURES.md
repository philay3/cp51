# Features

> Status: target design and delivery checklist. An output is checked only when
> all three are true: computed in the stats release per METHODOLOGY.md, served
> per API.md, and rendered with its n and interval visible. Product rules are
> checked when they hold everywhere and cannot be violated by a client.
> Last updated 2026-07-02.

## The interaction

A person enters a charge (by plain-language category or specific statute and
grade) and, where known, the assigned judge. CP51 returns the six outputs
below, computed from real Philadelphia Common Pleas cases. Everything is
descriptive of what has happened, shown with its sample size and uncertainty,
so it informs a decision without pretending to predict any one person's fate.

## The six outputs

- [ ] **1. Disposition breakdown.** Of resolved cases carrying this charge,
  the share that ended dismissed, in diversion, by plea, convicted at trial,
  and acquitted at trial. Denominator: resolved charges only (pending
  excluded). Shown as percentages with Wilson intervals and the n underneath.

- [ ] **2. Sentence picture.** For convictions on this charge: the sentence
  type mix (confinement, probation, IPP, no further penalty), the probability
  of confinement given conviction, and for confinement the spread of minimum
  terms shown as a distribution: P10, P25, median, P75, P90. Never a single
  expected number; sentence lengths are skewed and a mean would mislead.

- [ ] **3. Plea versus trial gap.** For comparable charges (same statute and
  grade), how sentences differ between plea convictions and trial convictions:
  the difference in confinement rate and in median minimum term, with a
  bootstrap interval. Labeled clearly as descriptive: cases that go to trial
  differ from cases that plead, so the gap is what happened, not what would
  happen to any one person who switched paths. This output stands on a data
  advantage: Philadelphia dockets label the disposition method on every
  charge, so plea and trial convictions separate cleanly.

- [ ] **4. Charge reduction rate.** How often the top charge is reduced before
  disposition: the share of resolved cases where the most serious convicted
  grade is lower than the most serious filed grade (including cases where the
  top charge fell away entirely and a lesser resolved). With interval and n.

- [ ] **5. Judge signal.** How the assigned judge sentences relative to the
  court baseline for comparable charges, as two numbers, each a tendency with
  a 95% interval and never a point prediction: the confinement-rate offset
  (how much more or less often this judge imposes confinement on convictions
  like these) and the length offset (how much longer or shorter this judge's
  minimum terms run, as a ratio to the court median). Estimates come from a
  multilevel model with partial pooling, so low-volume judges shrink toward
  the court average, and no judge appears at all below the case threshold.
  Language is regulated: "sentenced 15% above the court median for similar
  charges, 95% interval 4% to 27%", never "is a harsh judge".

- [ ] **6. Time to disposition.** Median days from filing to final
  disposition for this charge, with the P25-P75 range, cohorted by filing
  year. It answers the question every defendant asks first: how long will
  this hang over me.

## Product rules (every output obeys all of these)

- [ ] **Thresholds, then intervals.** A charge page requires at least
  `N_PAGE_MIN` resolved cases (initial value 20). Any individual metric
  requires `N_METRIC_MIN` (initial 30) or it is suppressed with an explicit
  reason. A judge estimate requires `N_JUDGE_MIN` sentenced cases in the
  comparison group (initial 40). Pages in the 20-29 band carry a visible
  small-sample caveat. Thin data says so instead of pretending.
- [ ] **Every number carries its n** and its interval. No orphan percentages.
- [ ] **Every response carries as_of** (the data window and release version).
- [ ] **Aggregates only.** No defendant names, no docket numbers, no
  case-level pages anywhere in the product.
- [ ] **Information, not legal advice.** Fixed framing on every surface: this
  describes past cases, it does not predict yours, talk to your lawyer. The
  disclaimer text is part of the API payload so no client can forget it.

## Explicitly out of scope for v1

- **Person or name search.** Structurally impossible by design: the database
  contains no names (DATABASE.md). This is a feature, not a gap.
- **Per-case lookup pages.** The product is distributions, not records.
- **Officer, prosecutor, and attorney profiles.** Dockets name counsel and
  comparable products profile officers; both are parked in ROADMAP as
  possible future surfaces, after charge and judge are solid.
- **Attorney lead generation.** Comparable products monetize by routing
  visitors to defense attorneys. CP51 does not; it sits badly next to the
  information-not-advice framing. Revisit only as a deliberate decision.
- **Predictive modeling.** The descriptive distribution is the product. Any
  predictive layer is optional polish, and the calibration backtest
  (METHODOLOGY.md) is the honest version of that ambition.