# Roadmap

> Status: living document. Update the status column as phases land; everything
> else changes only by decision (DECISIONS.md). Last updated 2026-07-06.

## Phases

| # | Phase | Status |
|---|---|---|
| 1 | Scaffold | complete (2026-07-02) |
| 2 | Acquisition layer | collector hardened (2026-07-02); collection running owner-paced |
| 3 | PDF parser | complete (2026-07-02) |
| 4 | Loader and pipeline | complete (2026-07-02) |
| 5 | Analysis and stats release | not started |
| 6 | API and forecaster frontend | not started |
| 7 | Municipal Court expansion | next (runs before Phase 5) |

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

### Phase 7: Municipal Court expansion (scheduled next, before Phase 5)

Extends acquisition, parsing, and loading to the MC-51-CR docket series under
D-18 and D-19. Recon on real MC sheets confirmed the CP parser runs with a
small bounded delta; MC gets no separate parse path.

Stages:
1. Parser delta: skip the MUNICIPAL COURT OF PHILADELPHIA COUNTY banner;
   register RELATED CASES, CASE PARTICIPANTS, BAIL INFORMATION, and CASE
   FINANCIAL INFORMATION as sections so RELATED CASES third-party captions
   stop folding into CASE INFORMATION; extract District Control Number from
   the Case Local Number(s) table; parse RELATED CASES docket number, court,
   and association reason while never storing its caption column.
2. MC fixture validation, the gate: a hand-picked MC fixture set that must
   include at least one case closed by conviction (verifies plea versus trial
   labeling), one sentenced or AMP-diverted case (verifies the sentence and
   diversion rendering), and one held-for-court case (verifies how the CP
   docket surfaces). These three renderings are unverified by recon and block
   collection until proven.
3. Loader and schema: populate cases.court_type with Municipal Court, add
   cases.dc_number, implement the consolidated-sibling grouping and the de
   novo outcome-of-record rule.
4. Collector: harvest MC-51-CR rows from the same search results (same
   CpDocketSheet link pattern, confirmed by recon), same caption privacy
   rule, window per D-19.
5. Stats layer filter: published outputs restrict to filings 2025 forward for
   both courts.

Acceptance: MC fixtures parse with zero privacy sentinels and correct fields
for all three unverified renderings; a collection batch loads MC cases with
court_type, dc_number, and sibling groups populated; no SU, MD, or traffic
docket enters the database; the published-stats filter excludes pre-2025
filings; idempotency holds across a repeated run.

## Parked (deliberately not now)

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