# API contract

> Status: target design for phase 6, written now because it defines what the
> phase 5 analysis must produce. Nothing here is implemented. All numbers in
> examples are synthetic. Last updated 2026-07-02.

## Design decisions

- **Read-only, aggregates only.** The API serves the versioned stats release
  produced by the analysis phase. It never queries the database, never sees a
  docket number, and has no write surface. This makes the privacy model
  enforceable at an architectural boundary and every response cacheable.
- **Precomputed over live.** The analysis phase writes
  `data/processed/stats/v{N}/` as JSON artifacts keyed by charge and judge.
  The API is a thin reader over that release. Consequence: the API could be
  replaced by static hosting of the artifacts without changing the contract.
- **Framework penciled, not locked.** FastAPI is the assumed implementation;
  the contract is framework agnostic (DECISIONS.md D-09).
- **Thresholds are server-side.** Suppression per METHODOLOGY.md happens in
  the stats release builder, so no client can accidentally display a number
  that should not exist.
- **The disclaimer ships in the payload.** Information-not-advice framing is
  part of every forecast response, so no client can forget it.
- **No auth for v1.** Public read-only data. Rate limiting at the edge.
  Versioned under `/api/v1/`; breaking changes bump the version.

## Common envelope

Every response:

```json
{
  "data_version": "v3",
  "as_of": "2026-06-30",
  "window": {"filed_from": "2019-01-01", "filed_to": "2026-06-30"},
  "thresholds": {"page_min": 20, "metric_min": 30, "judge_min": 40},
  "data": { }
}
```

Every published statistic inside `data` is an object, never a bare number:

```json
{"value": 0.42, "ci_low": 0.36, "ci_high": 0.48, "n": 261}
```

or, when suppressed:

```json
{"suppressed": true, "reason": "n below metric_min", "n": 17}
```

## Endpoints

### GET /api/v1/meta
Dataset coverage: case and charge counts, date range, release version, refresh
cadence, threshold values. Powers the transparency footer.

### GET /api/v1/charges
The charge picker. Returns categories and, within each, the statute-grade
combinations that clear `page_min`, with resolved-case counts. Supports
`?q=` substring search over names and statutes.

### GET /api/v1/charges/{slug}
The full bundle for one charge (category slug like `drug-possession`, or a
statute-grade slug like `35-780-113-a16-m`): disposition breakdown, sentence
picture, plea versus trial gap, reduction rate, duration. 404 if the slug is
unknown; 200 with a top-level small-sample caveat if n is in the 20-29 band.

### GET /api/v1/charges/{slug}/judges
Judges with a publishable estimate for this charge group: slug, name, n, and
summary offsets. Judges below `judge_min` for this group are absent, not
zeroed.

### GET /api/v1/judges
Directory of judges with any publishable estimate: slug, name, total sentenced
cases in window, overall offsets.

### GET /api/v1/judges/{slug}
One judge: overall confinement-rate and length offsets with intervals, then
per-category offsets where each clears `judge_min`, suppressed entries marked.

### GET /api/v1/forecast?charge={slug}&judge={slug}
The composed answer the UI renders: the charge bundle plus the judge block.
`judge` is optional; when absent or below threshold, `judge` is null with a
reason and the baseline stands alone. This is the primary product endpoint.

### GET /api/v1/calibration
The current backtest: holdout window, calibration curve points, Brier score
against the no-judge baseline, and quantile coverage per charge group. Powers
the demo page.

## Worked example (synthetic)

`GET /api/v1/forecast?charge=drug-possession&judge=example-a`

```json
{
  "data_version": "v3",
  "as_of": "2026-06-30",
  "window": {"filed_from": "2019-01-01", "filed_to": "2026-06-30"},
  "thresholds": {"page_min": 20, "metric_min": 30, "judge_min": 40},
  "data": {
    "charge": {
      "slug": "drug-possession",
      "name": "Drug Possession",
      "statutes": ["35 § 780-113 §§ A16", "35 § 780-113 §§ A31"],
      "n_resolved": 1842,
      "small_sample_caveat": false
    },
    "disposition": {
      "dismissed":       {"value": 0.38, "ci_low": 0.36, "ci_high": 0.40, "n": 1842},
      "diversion":       {"value": 0.11, "ci_low": 0.10, "ci_high": 0.13, "n": 1842},
      "plea":            {"value": 0.44, "ci_low": 0.42, "ci_high": 0.46, "n": 1842},
      "trial_convicted": {"value": 0.04, "ci_low": 0.03, "ci_high": 0.05, "n": 1842},
      "trial_acquitted": {"value": 0.02, "ci_low": 0.01, "ci_high": 0.03, "n": 1842},
      "other":           {"value": 0.01, "ci_low": 0.01, "ci_high": 0.02, "n": 1842}
    },
    "sentence_picture": {
      "denominator": "convictions",
      "n_convictions": 884,
      "p_confinement": {"value": 0.31, "ci_low": 0.28, "ci_high": 0.34, "n": 884},
      "type_mix": {
        "confinement": 0.31, "probation": 0.52, "ipp": 0.06,
        "no_further_penalty": 0.09, "fines_costs_only": 0.02
      },
      "confinement_min_days": {
        "n": 274,
        "p10": 30, "p25": 90, "p50": 180, "p75": 349, "p90": 540
      }
    },
    "plea_trial_gap": {
      "denominator": "convictions, same statute and grade",
      "confinement_rate_diff": {"value": 0.19, "ci_low": 0.08, "ci_high": 0.31, "n_plea": 811, "n_trial": 73},
      "median_min_days_diff": {"value": 150, "ci_low": 60, "ci_high": 270, "n_plea": 233, "n_trial": 41},
      "framing": "descriptive gap between populations, not a causal penalty"
    },
    "reduction": {
      "rate": {"value": 0.27, "ci_low": 0.24, "ci_high": 0.30, "n": 903},
      "definition": "top convicted grade below top filed grade"
    },
    "duration_days": {
      "cohort": "filed 2019-2024",
      "n": 1655, "p25": 148, "p50": 262, "p75": 431,
      "censoring_caveat": false
    },
    "judge": {
      "slug": "example-a",
      "name": "Example, Anne",
      "n_group": 112,
      "confinement_rate_offset": {
        "value": 0.06, "ci_low": -0.01, "ci_high": 0.13,
        "reading": "6 points above court baseline; interval crosses zero"
      },
      "length_ratio": {
        "value": 1.15, "ci_low": 1.04, "ci_high": 1.27,
        "reading": "minimum terms run 1.15x the court median for similar charges"
      },
      "method": "partial pooling; see /methodology"
    },
    "disclaimers": [
      "CP51 describes what happened in past Philadelphia cases. It does not predict your case.",
      "This is information, not legal advice. Talk to your lawyer or public defender.",
      "Every number above is computed only from cases that meet minimum sample thresholds."
    ]
  }
}
```

When the judge is unknown or below threshold:

```json
"judge": {"slug": "example-b", "available": false,
          "reason": "fewer than 40 sentenced cases in this charge group"}
```

## Errors

| status | when |
|---|---|
| 404 | unknown charge or judge slug |
| 200 + suppressed blocks | known entity, insufficient n for some metrics |
| 400 | malformed query |

Unknown-but-plausible slugs return 404 with a hint pointing at `/charges`.
There is no distinction between "never existed" and "below page threshold";
both 404, so thin pages are not enumerable.

## What the analysis phase owes this contract

Phase 5's stats release builder must emit, per release: `meta.json`,
`charges/{slug}.json` (the full bundle), `judges/{slug}.json`,
`charges/{slug}/judges.json`, and `calibration.json`, all shaped exactly as
above. That list is the acceptance criterion linking phase 5 to phase 6
(ROADMAP.md).