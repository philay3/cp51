# Current task: Phase 2 scale-up, production collector

This file is self-contained. Everything needed for this task is here. Do not
consult other documents to perform it.

## Orientation (all the context you need)

CP51 builds a dataset of Philadelphia criminal court outcomes from public
Court of Common Pleas docket sheets. The pipeline is closed end to end:
scripts/fetch_fixtures.py fetches dockets from the UJS portal (its selector
code is proven against the live portal), the parser turns PDFs into contract
JSON, and the loader fills the database (currently 31 fixture cases). The
collection window is locked: filings 2023 forward.

This task turns the fixture fetcher into the production collector: systematic
year and sequence enumeration of `CP-51-CR-{seven digit sequence}-{year}`,
automatic resume from the raw_dockets ledger, batch caps, and abort on signs
of portal pushback. After this task, collection is an owner-run, repeatable,
budget-capped command, not an agent session. The agent's portal contact in
this task is exactly two directed validation runs and nothing else.

## Ground rules

- **Commands are ask-first.** Present the exact command(s) with a one line
  reason, stop, and wait. Grouped logical blocks are fine.
- **Portal authorization, scoped to this task:** one validation batch capped
  at 25 new lookups (step 6) and one resume proof capped at 5 new lookups
  (step 7). Every lookup is separated by the randomized MIN_DELAY to
  MAX_DELAY sleep. No other portal contact of any kind. All refactoring and
  testing before step 6 involves zero portal contact.
- **Worklog gate.** The task is not complete until its tasks/worklog.md
  entry exists, written BEFORE the final commit.
- **Privacy.** PDFs stay in data/raw/ (gitignored). Console output is docket
  numbers, counts, and statuses only.
- **Docs exception, narrow:** step 8 directs three exact documentation edits.
  Those three and nothing else; the do-not-modify rule covers everything
  else in README.md, docs/, and PROJECT-INSTRUCTIONS.md.
- **If the environment does not match this file's assumptions, stop and
  ask.** No em dashes anywhere.

## Step 0: preflight

```bash
.venv/bin/python -m pytest tests/ -q
sqlite3 data/processed/phl.db "SELECT parse_status, COUNT(*) FROM raw_dockets GROUP BY parse_status;"
git status -sb && git log --oneline -2
```

Expect green tests, 31 ledger rows all `parsed`, a clean tree on the phase 4
commit.

## Step 1: extract the proven portal code

Create `src/acquire/portal.py` by MOVING the working fetch function and its
selector helpers out of `scripts/fetch_fixtures.py`, unchanged: the function
that searches one docket number and returns the docket sheet PDF bytes or
None, plus anything it depends on (selector constants, helper functions).
That code is proven against the live portal DOM; do not redesign it, retitle
it, or "improve" it. Then update `scripts/fetch_fixtures.py` to import from
`src.acquire.portal` so the fixture script keeps working. Add a module
docstring to portal.py noting the selectors were validated against the live
portal and must not be changed without a directed probe run.

Verify with zero portal contact:

```bash
.venv/bin/python -c "from src.acquire.portal import fetch_docket_pdf; print('import ok')"
.venv/bin/python -m pytest tests/ -q
```

(If the function or its helpers carry different names in fetch_fixtures.py,
keep the existing names and adjust the import line above to match; report
the actual names in the worklog.)

## Step 2: config additions (exact edits)

Append to `src/config.py`:

```python
# Collection window (DECISIONS.md D-16): filings 2023 forward, extendable
# backward by changing this value alone.
COLLECTION_START_YEAR = int(os.getenv("COLLECTION_START_YEAR", "2023"))
```

Append to `.env.example`:

```text
COLLECTION_START_YEAR=2023
```

## Step 3: enumeration logic (exact contents)

### src/acquire/enumerate.py

```python
"""
Enumeration logic for the production collector, kept free of any portal or
database dependency so it is fully unit testable. The collector wires
walk_year to the live portal and the raw_dockets ledger.
"""

from __future__ import annotations

MISS_STREAK_YEAR_END = 25   # consecutive not-found means the year is exhausted
ERROR_STREAK_ABORT = 5      # consecutive errors means possible pushback, stop
SEQ_CEILING = 20000         # sanity ceiling far above real annual volume


def format_docket(year: int, seq: int) -> str:
    return f"CP-51-CR-{seq:07d}-{year}"


def walk_year(year: int, statuses: dict, budget: int, lookup) -> dict:
    """Walk one year's sequences ascending, skipping the ledger.

    statuses: docket_number -> "found" | "not_found" (the ledger; mutated
    in place as live results arrive). lookup(docket_number) returns
    "found" | "not_found" | "error" and performs the actual portal work.

    Stops when: budget new lookups are spent, the trailing miss streak
    reaches MISS_STREAK_YEAR_END (ledgered misses count toward it, so
    re-runs exhaust a finished year with zero lookups), ERROR_STREAK_ABORT
    consecutive errors occur, or SEQ_CEILING is hit. Errors are never
    written to statuses, so errored sequences are retried on the next run.
    """
    stats = {"lookups": 0, "found": 0, "not_found": 0, "errors": 0,
             "exhausted": False, "aborted": False}
    miss_streak = 0
    error_streak = 0
    seq = 1
    while seq <= SEQ_CEILING:
        d = format_docket(year, seq)
        known = statuses.get(d)
        if known == "found":
            miss_streak = 0
        elif known == "not_found":
            miss_streak += 1
        else:
            if stats["lookups"] >= budget:
                return stats
            result = lookup(d)
            stats["lookups"] += 1
            if result == "found":
                stats["found"] += 1
                statuses[d] = "found"
                miss_streak = 0
                error_streak = 0
            elif result == "not_found":
                stats["not_found"] += 1
                statuses[d] = "not_found"
                miss_streak += 1
                error_streak = 0
            else:
                stats["errors"] += 1
                error_streak += 1
                if error_streak >= ERROR_STREAK_ABORT:
                    stats["aborted"] = True
                    return stats
        if miss_streak >= MISS_STREAK_YEAR_END:
            stats["exhausted"] = True
            return stats
        seq += 1
    stats["exhausted"] = True
    return stats
```

## Step 4: the collector (exact contents)

### scripts/collect.py

```python
"""
Production collector for the locked window (filings COLLECTION_START_YEAR
forward). Owner-run and owner-paced: each invocation is one batch capped by
--limit new portal lookups. Resume is automatic via the raw_dockets ledger;
nothing already attempted is ever contacted again, with one exception: for
the current calendar year, not_found rows are cleared at startup and
re-probed, because a docket that does not exist today can be filed tomorrow.
Prior years' not_found rows are terminal.

Politeness is not optional: a randomized MIN_DELAY to MAX_DELAY sleep
follows every live lookup, and the run aborts on ERROR_STREAK_ABORT
consecutive errors (possible pushback) with a screenshot for diagnosis.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/collect.py --limit 25
  PYTHONPATH=. .venv/bin/python scripts/collect.py --limit 500
  PYTHONPATH=. .venv/bin/python scripts/collect.py --limit 500 --year 2024
"""

from __future__ import annotations

import argparse
import random
import time
from datetime import date, datetime

from playwright.sync_api import sync_playwright

from src.acquire.enumerate import walk_year
from src.acquire.portal import fetch_docket_pdf
from src.config import (COLLECTION_START_YEAR, INTERIM_DIR, MAX_DELAY,
                        MIN_DELAY, RAW_DIR)
from src.db.schema import RawDocket
from src.db.session import SessionLocal, init_db

BROWSER_RESTART_EVERY = 200  # lookups per browser session, guards memory


def load_statuses(session) -> dict:
    statuses = {}
    for row in session.query(RawDocket).all():
        statuses[row.docket_number] = (
            "not_found" if row.parse_status == "not_found" else "found"
        )
    return statuses


def clear_frontier_misses(session, year: int) -> int:
    rows = (session.query(RawDocket)
            .filter(RawDocket.parse_status == "not_found",
                    RawDocket.docket_number.like(f"%-{year}"))
            .all())
    for row in rows:
        session.delete(row)
    session.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25,
                        help="max new portal lookups this run")
    parser.add_argument("--year", type=int, default=None,
                        help="restrict to one filing year")
    args = parser.parse_args()

    init_db()
    session = SessionLocal()
    this_year = date.today().year
    years = [args.year] if args.year else list(
        range(COLLECTION_START_YEAR, this_year + 1))

    cleared = clear_frontier_misses(session, this_year)
    if cleared:
        print(f"frontier: re-probing {cleared} current-year misses")

    statuses = load_statuses(session)
    budget_left = args.limit
    state = {"browser": None, "page": None, "pw": None, "since_restart": 0}

    def fresh_page():
        if state["browser"] is not None:
            state["browser"].close()
        state["browser"] = state["pw"].chromium.launch(headless=False)
        state["page"] = state["browser"].new_page()
        state["since_restart"] = 0

    def lookup(docket: str) -> str:
        if state["since_restart"] >= BROWSER_RESTART_EVERY:
            fresh_page()
        state["since_restart"] += 1
        try:
            pdf = fetch_docket_pdf(state["page"], docket)
        except Exception as exc:
            print(f"error {docket}: {type(exc).__name__}")
            try:
                state["page"].screenshot(
                    path=str(INTERIM_DIR / "collect_abort.png"), full_page=True)
            except Exception:
                pass
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            return "error"
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
        if pdf is None:
            session.merge(RawDocket(docket_number=docket, pdf_path=None,
                                    fetched_at=datetime.now(),
                                    parse_status="not_found",
                                    notes="no docket sheet at portal"))
            session.commit()
            print(f"miss  {docket}")
            return "not_found"
        out = RAW_DIR / f"{docket}.pdf"
        out.write_bytes(pdf)
        session.merge(RawDocket(docket_number=docket, pdf_path=str(out),
                                fetched_at=datetime.now(),
                                parse_status="pending",
                                notes="collector"))
        session.commit()
        print(f"saved {docket}")
        return "found"

    with sync_playwright() as pw:
        state["pw"] = pw
        fresh_page()
        for year in years:
            if budget_left <= 0:
                break
            stats = walk_year(year, statuses, budget_left, lookup)
            budget_left -= stats["lookups"]
            print(f"{year}: {stats['lookups']} lookups, "
                  f"{stats['found']} saved, {stats['not_found']} misses, "
                  f"{stats['errors']} errors"
                  f"{', year exhausted' if stats['exhausted'] else ''}"
                  f"{', ABORTED on error streak' if stats['aborted'] else ''}")
            if stats["aborted"]:
                print("possible portal pushback: stopping the whole run; "
                      "see data/interim/collect_abort.png")
                break
        state["browser"].close()

    total = session.query(RawDocket).count()
    fetched = (session.query(RawDocket)
               .filter(RawDocket.pdf_path.isnot(None)).count())
    print(f"ledger: {total} rows, {fetched} PDFs on disk, "
          f"budget remaining {budget_left}")
    session.close()


if __name__ == "__main__":
    main()
```

## Step 5: unit tests (exact contents)

### tests/test_enumerate.py

```python
from src.acquire.enumerate import (ERROR_STREAK_ABORT, MISS_STREAK_YEAR_END,
                                   format_docket, walk_year)


def test_format_docket():
    assert format_docket(2023, 1) == "CP-51-CR-0000001-2023"
    assert format_docket(2026, 12345) == "CP-51-CR-0012345-2026"


def test_budget_stops_the_walk():
    stats = walk_year(2023, {}, budget=3, lookup=lambda d: "found")
    assert stats["lookups"] == 3 and stats["found"] == 3
    assert not stats["exhausted"] and not stats["aborted"]


def test_ledgered_dockets_cost_no_lookups():
    statuses = {format_docket(2023, s): "found" for s in range(1, 6)}
    seen = []

    def lookup(d):
        seen.append(d)
        return "found"

    walk_year(2023, statuses, budget=2, lookup=lookup)
    assert seen == [format_docket(2023, 6), format_docket(2023, 7)]


def test_year_exhausts_on_miss_streak():
    stats = walk_year(2023, {}, budget=10000, lookup=lambda d: "not_found")
    assert stats["exhausted"] is True
    assert stats["lookups"] == MISS_STREAK_YEAR_END


def test_ledgered_misses_exhaust_without_lookups():
    statuses = {format_docket(2023, s): "found" for s in range(1, 11)}
    statuses.update({format_docket(2023, s): "not_found"
                     for s in range(11, 11 + MISS_STREAK_YEAR_END)})
    stats = walk_year(2023, statuses, budget=100,
                      lookup=lambda d: "found")
    assert stats["exhausted"] is True and stats["lookups"] == 0


def test_error_streak_aborts_and_is_not_ledgered():
    statuses = {}
    stats = walk_year(2023, statuses, budget=100, lookup=lambda d: "error")
    assert stats["aborted"] is True
    assert stats["errors"] == ERROR_STREAK_ABORT
    assert statuses == {}
```

Run:

```bash
.venv/bin/python -m pytest tests/ -q
```

All green before any portal contact.

## Step 6: directed validation batch (portal, capped at 25)

```bash
PYTHONPATH=. .venv/bin/python scripts/collect.py --limit 25
```

Expected: the walk starts at 2023 sequence 1, skips every ledgered fixture
with zero refetches, performs exactly 25 new lookups (or aborts on an error
streak, which is a stop-and-report), saves most of them as PDFs, and the
ledger grows by exactly the number of lookups. Report the full console
output.

## Step 7: resume proof, then pipeline over everything

```bash
PYTHONPATH=. .venv/bin/python scripts/collect.py --limit 5
PYTHONPATH=. .venv/bin/python scripts/run_pipeline.py
```

The first command must continue where the batch left off with zero repeat
contacts. The second parses and loads everything on disk (31 fixtures plus
the new batch). New-layout parse failures are acceptable as
failed-with-notes; list any in the report and the worklog. Then:

```bash
sqlite3 data/processed/phl.db "SELECT parse_status, COUNT(*) FROM raw_dockets GROUP BY parse_status;"
sqlite3 data/processed/phl.db "SELECT 'cases', COUNT(*) FROM cases UNION ALL SELECT 'charges', COUNT(*) FROM charges UNION ALL SELECT 'sentences', COUNT(*) FROM sentences UNION ALL SELECT 'judges', COUNT(*) FROM judges;"
```

## Step 8: documentation row updates (exact edits, authorized)

1. docs/ROADMAP.md, status table: change the phase 2 row status to
   `collector hardened (2026-07-02); collection running owner-paced` and
   the phase 4 row status to `complete (2026-07-02)`.
2. docs/ROADMAP.md, end of the Phase 4 section, append:
   `Met 2026-07-02: fixture set loaded with expected counts; idempotency
   proven by repeated runs.`
3. docs/DATABASE.md, raw_dockets table, parse_status row: change the notes
   cell to `pending, parsed, failed, not_found`.

## Step 9: worklog, commit, push

Worklog entry first (include: validation batch results, resume proof, any
parse failures with notes, ledger totals). Then:

```bash
git add .
git status -sb
git commit -m "Add production collector with ledger resume and batch caps"
git push
```

Nothing under data/ staged except data/lookups/.

## Step 10: hand the keys to the owner

End the report with exactly this, so collection continues without any agent:

"Collection is now yours, repeatable any time [yours, repeat at will]:
`PYTHONPATH=. .venv/bin/python scripts/collect.py --limit 500`
(any --limit you like; it resumes automatically and stops itself on
pushback). After collecting, process what you gathered with
`PYTHONPATH=. .venv/bin/python scripts/run_pipeline.py`."

## Definition of done

- portal.py extracted with the proven fetch code unchanged; imports green.
- enumerate.py and collect.py exactly as given; all tests green.
- Validation batch completed within 25 lookups with zero fixture refetches;
  resume proof completed within 5 lookups with zero repeats.
- Pipeline run over the enlarged corpus; failures, if any, are
  failed-with-notes and listed.
- The three documentation edits applied, those three only.
- Worklog entry written before the final commit; commit pushed.
- The owner has the standing collection command. Stop.