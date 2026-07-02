# Architecture

> Status: target design. Phases 1-4 define the pipeline half, phases 5-6 the
> serving half. Nothing is built yet. Last updated 2026-07-02.

## The system in one view

```
                        LOCAL PIPELINE (phases 1-5)
 ┌──────────┐   PDFs   ┌──────────┐  records  ┌──────────┐  rows   ┌──────────┐
 │ acquire   │ ───────> │  parse   │ ────────> │   load   │ ──────> │  SQLite  │
 │ Playwright│  data/raw│pdfplumber│data/interim│SQLAlchemy│         │ phl.db   │
 └──────────┘          └──────────┘           └──────────┘         └────┬─────┘
      ^                                                                  │
      │ raw_dockets table tracks every fetch and parse status            │
      │                                                                  v
      │                                                          ┌──────────────┐
      │                                                          │   analysis   │
      │                                                          │pandas, stats │
      │                                                          └──────┬───────┘
      │                                                                 │ writes
      │                        SERVING (phase 6)                        v
 ┌────┴─────┐            ┌───────────┐   reads   ┌──────────────────────────────┐
 │ UJS      │            │ React web │ <──────── │ stats release (versioned     │
 │ portal   │            │ frontend  │   JSON    │ JSON artifacts) via read-only│
 └──────────┘            └───────────┘           │ API (FastAPI, penciled)      │
                                                 └──────────────────────────────┘
```

The pipeline runs locally and produces two things: the analytical database and,
from it, a versioned **stats release** (precomputed aggregate JSON). The serving
layer never touches the database; it reads the stats release only. That boundary
is what makes the privacy model enforceable (see DATABASE.md) and keeps the API
trivially cacheable, cheap, and even hostable statically if needed.

## Stages

**1. Acquire (`src/acquire/`).** A Playwright Chromium session drives the UJS
portal, fetches docket sheet PDFs into `data/raw/`, and records every fetch in
the `raw_dockets` table. Cache-first: a docket already on disk is never
refetched. Politeness is not optional: a randomized delay between `MIN_DELAY`
and `MAX_DELAY` seconds separates requests. The portal is contacted only in
runs the owner explicitly directs (workspace rule). Fallback if blocked: a
formal bulk data request to the AOPC.

**2. Parse (`src/parse/`).** `docket_parser.py` turns one PDF into structured
records: case header, charges with grade and disposition, sentence components,
the sentencing judge per disposition event, and key dates. Output goes to
`data/interim/` as JSON, one file per docket, so parsing is inspectable and
re-runnable without refetching. The parser is validated on a hand-collected
fixture set before the scraper ever scales (see ROADMAP.md phase 3).

**3. Load (`src/db/load.py`).** Inserts parsed records into SQLite. This is
where the three normalization jobs live: judge name resolution (raw variants
map to one judge identity, see DATABASE.md), disposition categorization (raw
disposition text maps to an analysis category), and defendant hashing (name
plus year of birth becomes a salted hash, then the name is discarded). Loads
are idempotent: re-running on the same interim files produces the same rows.

**4. Analyze (`src/analysis/`, `notebooks/`).** Computes everything in
FEATURES.md under the rules in METHODOLOGY.md, then writes the stats release to
`data/processed/stats/v{N}/`. The release is the only artifact the serving
layer ever sees.

**5. Serve (`api/`, `web/`, future).** A read-only API (FastAPI penciled in)
serves the stats release per the contract in API.md. A React and TypeScript
frontend renders the forecaster. Neither exists yet; both directories are
created when phase 6 begins.

## Folder map

```
cp51/
├── README.md
├── .gitignore
├── requirements.txt
├── .env.example              # copy to .env; never commit .env
├── docs/                     # this documentation set
├── data/
│   ├── lookups/              # versioned in git: category, disposition, and judge override maps
│   ├── raw/                  # local only: docket PDFs as fetched
│   ├── interim/              # local only: parsed JSON, one file per docket
│   └── processed/            # local only: phl.db and stats releases (stats/v{N}/)
├── src/
│   ├── config.py             # paths, delays, salt, scope constants
│   ├── acquire/              # portal session, search, download
│   ├── parse/                # pdf to structured records
│   ├── db/                   # schema.py, session.py, load.py
│   └── analysis/             # stats, models, stats release builder
├── notebooks/                # exploration; nothing load-bearing lives here
├── scripts/                  # run_pipeline.py and operational entry points
├── tests/                    # fixtures are synthetic or fully redacted
├── api/                      # phase 6, does not exist yet
└── web/                      # phase 6, does not exist yet
```

## Stack and rationale

Python carries acquisition, parsing, and analysis because the analysis
libraries decide the language. Playwright with Chromium is used for acquisition
because the portal is JavaScript driven and resists plain HTTP. pdfplumber
extracts text from the docket PDFs. SQLAlchemy 2.0 over SQLite gives a zero
setup single file store that pandas reads directly; the schema is written to
port to Postgres on Neon when the web app needs concurrent access (see
DECISIONS.md D-08). pandas, statsmodels, and scipy arrive in phase 5 so the
early environment stays light. The serving layer is FastAPI plus a React and
TypeScript frontend, both penciled rather than locked (D-09).

## Cross-cutting principles

- **Idempotent and resumable.** Every stage can be re-run safely. `raw_dockets`
  is the ledger: fetched, parsed, failed, with notes.
- **Raw is preserved.** Raw disposition text, raw judge strings, and raw PDFs
  are kept alongside every normalized value, so normalization bugs are always
  recoverable.
- **Config over constants.** Delays, paths, and the salt live in `.env`;
  `src/config.py` is the single reader.
- **The stats release is the contract.** Analysis and serving meet only at the
  versioned JSON artifacts defined in API.md. Either side can change internally
  without breaking the other.