# Roadmap

> Status: living document. Update the status column as phases land; everything
> else changes only by decision (DECISIONS.md). Last updated 2026-07-02.

## Phases

| # | Phase | Status |
|---|---|---|
| 1 | Scaffold | complete (2026-07-02) |
| 2 | Acquisition layer | collector hardened (2026-07-02); collection running owner-paced |
| 3 | PDF parser | complete (2026-07-02) |
| 4 | Loader and pipeline | complete (2026-07-02) |
| 5 | Analysis and stats release | not started |
| 6 | API and forecaster frontend | not started |

Build order note, now historical: the parser was validated first, on a
31-docket fixture set collected by a minimal owner-directed fetcher
(scripts/fetch_fixtures.py: probe mode, politeness delays, cache-first,
ledger in raw_dockets), so progress was never blocked on the full scraper.
What remains of phase 2 is hardening that fetcher for the locked window
(filings 2023 forward, DECISIONS.md D-16): systematic year and sequence
enumeration, resume from the raw_dockets ledger, and unattended polite runs.

### Phase 1: Scaffold
Structure, config, schema v2, environment, first commit.

Acceptance: directory tree matches ARCHITECTURE.md; `schema.py` reflects
DATABASE.md v2 (the build spec delta applied before first init); `init_db`
creates all eight tables; `.env` populated locally with a real salt (set by
the owner, never by the agent); first commit pushed to the private repo.

### Phase 2: Acquisition layer
Playwright portal session, search by filter, download, caching, politeness.

Acceptance: given a docket number, fetches and caches the PDF exactly once
with the randomized delay active; records every fetch in `raw_dockets`;
survives a restart without refetching; a directed test run of a small batch
(owner-approved, per workspace rules) completes without portal pushback.

### Phase 3: PDF parser
`src/parse/docket_parser.py`, validated fixture-first.

Acceptance: on a validation set of at least 25 manually collected dockets
spanning years, dispositions, and multi-charge cases, the parser extracts
docket number, filed date, status, charges (statute, grade, disposition),
sentence components, and sentencing judge with at least 95% field-level
accuracy against a hand-audited answer key; failures degrade to
`parse_status=failed` with notes, never silent partial rows; no defendant
name appears in any interim output.

Met 2026-07-02: 31 of 31 fixtures parsed with zero failures; owner audit
passed; to_days extended for decimal quantities as printed on real dockets
("11.00 Months 15.00 Days"); privacy assertion held on every write.

### Phase 4: Loader and pipeline
`src/db/load.py` plus `scripts/run_pipeline.py`.

Acceptance: loads the full fixture set; judge alias resolution produces one
identity per real judge in the fixtures with the override map covering
ambiguity; disposition mapping covers at least 98% of fixture dispositions
with the remainder visible as `other`; defendant hashing verified (same
person, same hash; no name at rest anywhere); re-running the pipeline is a
no-op.

Met 2026-07-02: fixture set loaded with expected counts; idempotency proven by repeated runs.

### Phase 5: Analysis and stats release
Everything in METHODOLOGY.md, ending in `stats/v1/`.

Acceptance: distributions, gap, reduction, duration, judge offsets, and
variance decomposition computed with intervals and thresholds enforced; the
calibration backtest runs on a holdout and reports Brier plus quantile
coverage; the release builder emits every artifact API.md names, validated
against the contract shapes; a notebook reproduces the headline numbers from
the database independently of the builder.

### Phase 6: API and forecaster frontend
FastAPI reader over the release; React and TypeScript frontend; calibration
demo page.

Acceptance: every endpoint in API.md serves the v1 release per contract
including suppression behavior; the frontend renders the six outputs with n
and intervals visible and the disclaimer unremovable; the calibration page
renders the backtest; deployed behind rate limiting.

## Parked (deliberately not now)

- **Municipal Court coverage.** Many Philadelphia cases live entirely in MC;
  large scope expansion, revisit after CP is solid.
- **Court Summary parsing** for prior record context; unlocks better case-mix
  adjustment (METHODOLOGY.md) and a defendants column (DATABASE.md).
- **Attorney, prosecutor, and officer surfaces.** Dockets name counsel;
  comparable products prove the demand; parked until charge and judge are
  trustworthy.
- **Case-level sentence totals** (concurrent versus consecutive structure).
- **Postgres on Neon and Alembic**, together, when the web app needs them.
- **Any predictive layer** beyond the calibration backtest.
- **Monetization of any kind.** Nothing is designed for it; revisit only as a
  deliberate decision.