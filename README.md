# CP51

**What actually happens in Philadelphia criminal court.**

Named for the four characters that begin every Philadelphia Court of Common Pleas
criminal docket number (CP-51, where 51 is Philadelphia's county code).

> Status: Phase 1 (scaffold) ready to execute. Nothing is built yet.
> This README and everything in docs/ is the target design. Last updated 2026-07-02.

## What this is

Most people facing a criminal charge decide whether to accept a plea with almost
no sense of what actually happens to charges like theirs. The system has that
information. The individual does not.

CP51 builds a case-level dataset of Philadelphia Court of Common Pleas criminal
cases from public docket sheets, then shows defendants and public defenders the
realistic distribution of outcomes for a charge: how often it is dismissed, pled,
or tried, the sentence spread for convictions, the plea versus trial gap, and how
the assigned judge tends to sentence relative to the court. The judge dimension
is the core differentiator. Every figure carries its sample size and uncertainty.

CP51 is descriptive, not predictive. It reports what has happened in real cases.
It is information, not legal advice, and it is an independent project with no
affiliation to the First Judicial District, the AOPC, or any court.

## Pipeline

1. **Acquire.** Pull public docket sheets from the Pennsylvania UJS portal with a
   real browser, cached, at a polite rate.
2. **Parse.** Turn each docket PDF into structured records: case, charges with
   grade and disposition, sentence components, judges, dates.
3. **Store.** Load into a normalized SQLite database at the charge grain, with
   judges as a first class entity and defendants stored only as salted hashes.
4. **Analyze and serve.** Compute distributions and judge effects, publish them
   as a versioned stats release, and serve them through a read-only API and a
   React frontend, with a calibration backtest as the honesty demo.

## Documentation

| Doc | Covers |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Stages, components, data flow, folder map, stack rationale |
| [docs/DATABASE.md](docs/DATABASE.md) | Schema v2 (authoritative), grain, privacy model, delta from build spec v1 |
| [docs/DATA_SOURCE.md](docs/DATA_SOURCE.md) | UJS portal, docket sheet anatomy, acquisition policy, parser field mapping |
| [docs/FEATURES.md](docs/FEATURES.md) | The six outputs and the product rules they obey |
| [docs/METHODOLOGY.md](docs/METHODOLOGY.md) | Denominators, intervals, the judge model, calibration, limitations |
| [docs/API.md](docs/API.md) | The read-only forecaster contract (target spec) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phases, acceptance criteria, current status, parked ideas |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Locked decisions and open questions |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env        # then set a long random DEFENDANT_HASH_SALT yourself
python -m src.db.session    # creates data/processed/phl.db with all tables
```

## Data and privacy

Raw PDFs and the database stay local and out of version control. Defendant names
are never stored in the analytical tables; linking a person across cases uses a
salted hash only. The public product publishes aggregates only: no defendant
names, no individual case pages, no docket numbers. See docs/DATABASE.md and
docs/DECISIONS.md (D-05).

## Source

Pennsylvania UJS Web Portal, public Court of Common Pleas criminal docket
sheets, free to the public. See docs/DATA_SOURCE.md for the acquisition policy.