# Task: Phase 2, search-form production collector

## Orientation

You are the coding agent for CP51. Your world is the workspace rules, this
file, and the repo. This task replaces the retired sequence-enumeration
collector with a search-form collector.

Why the change: the old collector walked docket sequence numbers, wasted most
lookups on non-existent sequences, and the portal began rate-limiting near 20
lookups per run. The replacement searches by Date Filed for Philadelphia in
weekly Monday-to-Friday windows across the locked window (filings 2023 forward,
DECISIONS.md D-16), reads the results grid, harvests only Common Pleas criminal
docket numbers (the CP-51-CR pattern), and fetches each docket sheet PDF inside
the same browser session. Every docket it touches is a real case, so no lookup
is wasted.

The search form and results structure were confirmed by directed read-only
probes. The selectors and facts below are given; do not rediscover them and do
not contact the portal during this task (see Ground rules).

## Ground rules

- Follow the workspace rules on posting an implementation plan for approval
  before running anything, and on maintaining your task artifact as you work.
- **Privacy, sharpest edge in the project.** The results grid has a Case
  Caption column containing defendant names ("Comm. v. LastName, FirstName").
  The collector reads only the docket-number cell (column 0) and the
  docket-sheet anchor. It never reads, prints, logs, stores, or commits a
  caption. The `harvest` function below is written to honor this; do not add
  any full-row text read, any caption cell read, or any debug print of row
  contents.
- **Do not contact the portal in this task.** Writing the collector and
  running it against the live portal are separate events (DECISIONS.md D-15).
  Your definition of done is fully offline: unit tests, an offline window
  dry-run, an import check, and a schema check. The owner runs the first live
  validation separately, after your work is committed.
- Commands are ask-first, run as `PYTHONPATH=. .venv/bin/python ...` from the
  repo root.
- No em dashes anywhere (code, comments, commit, worklog). Use periods,
  commas, parentheses, colons.
- Do not modify README.md, docs/, or the Project Instructions in this task.
  Schema and code only. The docs update is handled at close-out by the owner.

## Confirmed portal facts (given, do not rediscover)

Search form on https://ujsportal.pacourts.us/CaseSearch :

- Search By control: `select[title='Search By']`, choose value `DateFiled`.
- Advanced Search toggle: `input[name='AdvanceSearch']` (checkbox). Checking
  it reveals the County control.
- County control: `select[title='County']`, select by label `Philadelphia`
  (its options carry no value attribute, so label selection is required).
- Date range: `input[name='FiledStartDate']` and `input[name='FiledEndDate']`,
  filled as mm/dd/yyyy.
- Search button: `#btnSearch`.

Results grid:

- No desktop pagination: the full week is returned at once in one table.
- Column 0 is the docket number. CP-51-CR rows carry a docket-sheet anchor
  `a[href*='CpDocketSheet']` whose href holds a one-time hash valid only in the
  session that produced it (so harvest and fetch happen in the same session).
- Docket Type is not filterable on a Date Filed search, so the CP-51-CR pattern
  is the filter, applied in our code.

## Step 0: preflight (ask-first)

```bash
.venv/bin/python -m pytest tests/ -q
git status -sb
```

Expect green tests and a clean tree. If dirty, stop and report. Note:
`tasks/currenttask.md` may show as modified (it is this file); that is expected.

## Step 1: read, do not change yet

Read `src/acquire/portal.py`, `src/acquire/enumerate.py`, `scripts/collect.py`,
`src/db/schema.py`, and `src/db/session.py` to confirm the current shapes match
what this task edits. Change nothing in this step.

## Step 2: exact file contents

### 2a. Replace `src/acquire/portal.py` with exactly this

```python
"""
Selectors and interaction logic for the Pennsylvania UJS Case Search portal.

The CSS selectors and workflow here were validated against the live portal DOM
and must not be changed without a directed probe run.
"""

from __future__ import annotations

PORTAL = "https://ujsportal.pacourts.us/CaseSearch"


def pdf_from_href(page, href: str) -> bytes | None:
    """Fetch a docket-sheet PDF from its results-row href inside the current
    session. The href carries a one-time hash, so it is only valid in the same
    browser session as the search that produced it. Returns PDF bytes, or None
    if the response is missing or is not a PDF."""
    url = href if href.startswith("http") else f"https://ujsportal.pacourts.us{href}"
    resp = page.context.request.get(url)
    if not resp.ok:
        return None
    body = resp.body()
    if not body.startswith(b"%PDF"):
        return None
    return body


def fetch_docket_pdf(page, docket: str) -> bytes | None:
    """Search one docket number; return the docket sheet PDF bytes or None.
    Retained for the fixture fetcher and single-docket use. The production
    collector uses pdf_from_href directly on harvested result rows."""
    page.goto(PORTAL, wait_until="networkidle")
    page.locator("select[title='Search By']").select_option("DocketNumber")
    page.locator("input[name='DocketNumber']").fill(docket)
    page.locator("#btnSearch").click()
    page.wait_for_load_state("networkidle")

    links = page.locator("a[href*='CpDocketSheet']")
    if links.count() == 0:
        return None
    href = links.first.get_attribute("href")
    if not href:
        return None
    return pdf_from_href(page, href)
```

### 2b. Create `src/acquire/windows.py` with exactly this

```python
"""
Pure weekly-window generation for the search-form collector. No portal or
database dependency, so it is fully unit testable. The collector walks these
Monday-to-Friday windows across the locked collection window (filings
COLLECTION_START_YEAR forward, DECISIONS.md D-16).
"""

from __future__ import annotations

from datetime import date, timedelta


def week_windows(collection_start: date, today: date) -> list[tuple[date, date]]:
    """Return (start, end) search windows, Monday to Friday, covering every
    week from collection_start through today, oldest first.

    A week is included when its Friday is on or after collection_start and its
    Monday is on or before today. The first and last windows are clamped so the
    search range never runs before collection_start or after today. No filing
    date in range is skipped except genuine Saturday or Sunday dates, which
    Monday-to-Friday windows do not cover.
    """
    monday = collection_start - timedelta(days=collection_start.weekday())
    out: list[tuple[date, date]] = []
    while monday <= today:
        friday = monday + timedelta(days=4)
        if friday >= collection_start:
            start = max(monday, collection_start)
            end = min(friday, today)
            if start <= end:
                out.append((start, end))
        monday += timedelta(days=7)
    return out
```

### 2c. Create `tests/test_windows.py` with exactly this

```python
from datetime import date

from src.acquire.windows import week_windows


def test_first_window_matches_recon():
    w = week_windows(date(2023, 1, 1), date(2023, 1, 20))
    assert w[0] == (date(2023, 1, 2), date(2023, 1, 6))


def test_no_window_before_collection_start():
    w = week_windows(date(2023, 1, 1), date(2023, 1, 20))
    assert all(start >= date(2023, 1, 1) for start, _ in w)


def test_last_window_clamped_to_today():
    w = week_windows(date(2023, 1, 1), date(2023, 1, 18))
    assert w[-1] == (date(2023, 1, 16), date(2023, 1, 18))


def test_windows_are_ordered_and_weekly_when_monday_aligned():
    w = week_windows(date(2023, 1, 1), date(2023, 2, 28))
    for (s1, _), (s2, _) in zip(w, w[1:]):
        assert (s2 - s1).days == 7


def test_partial_first_week_has_no_year_boundary_gap():
    # 2025-01-01 is a Wednesday. The first window must start on Jan 1, not the
    # following Monday, so Wednesday-to-Friday filings are not skipped.
    w = week_windows(date(2025, 1, 1), date(2025, 1, 31))
    assert w[0] == (date(2025, 1, 1), date(2025, 1, 3))


def test_window_shape_never_exceeds_five_days():
    w = week_windows(date(2023, 1, 1), date(2023, 3, 1))
    for start, end in w:
        assert end >= start
        assert (end - start).days <= 4
```

### 2d. Replace `scripts/collect.py` with exactly this

```python
"""
Search-form production collector for the locked window (filings
COLLECTION_START_YEAR forward, DECISIONS.md D-16). Replaces the retired
sequence-enumeration collector.

Strategy: walk Monday-to-Friday weekly windows from 2023 forward. For each
week, run one Date Filed search scoped to Philadelphia, read the results grid,
harvest only Common Pleas criminal docket numbers (the CP-51-CR pattern) and
their docket-sheet links, and fetch each PDF inside the same session (the
sheet link carries a one-time hash). Only real cases are ever touched, so no
lookup is wasted on a non-existent sequence.

Privacy: the results grid has a Case Caption column with defendant names. This
collector reads only the docket-number cell and the docket-sheet anchor. It
never reads, prints, logs, or stores a caption.

Resume: the harvest_windows ledger records each week's status. A week marked
complete is skipped on later runs. A partial week (budget ran out or the run
aborted mid-week) is re-searched next time (fresh links) and only its missing
dockets are fetched. The raw_dockets ledger skips any docket already on disk,
so re-searching a partial week re-fetches nothing already saved. A prior
not_found docket that reappears in real results is re-fetched, which cleans up
the enumeration era's rate-limit false negatives.

Politeness is not optional: a randomized MIN_DELAY to MAX_DELAY sleep follows
every live fetch, and the run aborts on ERROR_STREAK_ABORT consecutive errors
(possible pushback) with a screenshot for diagnosis.

Owner-run and owner-paced. --limit caps new PDF fetches per run.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/collect.py --limit 5
  PYTHONPATH=. .venv/bin/python scripts/collect.py --limit 100
  PYTHONPATH=. .venv/bin/python scripts/collect.py --limit 100 --start-year 2024
"""

from __future__ import annotations

import argparse
import random
import re
import time
from datetime import date, datetime

from playwright.sync_api import sync_playwright

from src.acquire.portal import PORTAL, pdf_from_href
from src.acquire.windows import week_windows
from src.config import (COLLECTION_START_YEAR, INTERIM_DIR, MAX_DELAY,
                        MIN_DELAY, RAW_DIR)
from src.db.schema import HarvestWindow, RawDocket
from src.db.session import SessionLocal, init_db

ERROR_STREAK_ABORT = 5        # consecutive errors means possible pushback
BROWSER_RESTART_EVERY = 150   # fetches per browser session, guards memory
CP_CRIM_RE = re.compile(r"CP-51-CR-\d{7}-\d{4}")


def polite_sleep() -> None:
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def run_search(page, start: date, end: date) -> None:
    """Drive the Date Filed search for Philadelphia over one weekly window."""
    page.goto(PORTAL, wait_until="networkidle")
    page.locator("select[title='Search By']").select_option("DateFiled")
    page.wait_for_timeout(800)
    page.locator("input[name='AdvanceSearch']").check()
    page.wait_for_timeout(800)
    page.locator("select[title='County']").select_option(label="Philadelphia")
    page.locator("input[name='FiledStartDate']").fill(start.strftime("%m/%d/%Y"))
    page.locator("input[name='FiledEndDate']").fill(end.strftime("%m/%d/%Y"))
    page.locator("#btnSearch").click()
    page.wait_for_load_state("networkidle")


def harvest(page) -> tuple[int, list[tuple[str, str | None]]]:
    """Return (total_row_count, [(docket, sheet_href_or_None), ...]) for the
    CP-51-CR rows only. Reads only the docket-number cell (column 0) and the
    docket-sheet anchor. Never touches the caption cell."""
    rows = page.locator("table tbody tr")
    total = rows.count()
    found: list[tuple[str, str | None]] = []
    for i in range(total):
        row = rows.nth(i)
        cells = row.locator("td")
        if cells.count() == 0:
            continue
        text = cells.first.inner_text() or ""
        m = CP_CRIM_RE.search(text)
        if not m:
            continue
        docket = m.group(0)
        sheet = row.locator("a[href*='CpDocketSheet']")
        href = sheet.first.get_attribute("href") if sheet.count() else None
        found.append((docket, href))
    return total, found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25,
                        help="max new PDF fetches this run")
    parser.add_argument("--start-year", type=int, default=None,
                        help="override the first filing year to walk")
    args = parser.parse_args()

    init_db()
    session = SessionLocal()
    today = date.today()
    start_year = args.start_year or COLLECTION_START_YEAR
    windows = week_windows(date(start_year, 1, 1), today)

    complete = {w.week_start for w in session.query(HarvestWindow)
                .filter(HarvestWindow.status == "complete").all()}
    have_pdf = {r.docket_number for r in session.query(RawDocket)
                .filter(RawDocket.pdf_path.isnot(None)).all()}

    budget = args.limit
    aborted = False
    state = {"pw": None, "browser": None, "page": None, "since_restart": 0}

    def fresh_browser() -> None:
        if state["browser"] is not None:
            state["browser"].close()
        state["browser"] = state["pw"].chromium.launch(headless=False)
        state["page"] = state["browser"].new_page()
        state["since_restart"] = 0

    with sync_playwright() as pw:
        state["pw"] = pw
        fresh_browser()

        for start, end in windows:
            if budget <= 0 or aborted:
                break
            if start in complete:
                continue
            if state["since_restart"] >= BROWSER_RESTART_EVERY:
                fresh_browser()

            run_search(state["page"], start, end)
            total, rows = harvest(state["page"])
            cp_n = len(rows)

            error_streak = 0
            for docket, href in rows:
                if budget <= 0:
                    break
                if docket in have_pdf:
                    continue
                if href is None:
                    print(f"no sheet link {docket}")
                    continue
                try:
                    pdf = pdf_from_href(state["page"], href)
                except Exception as exc:
                    print(f"error {docket}: {type(exc).__name__}")
                    try:
                        state["page"].screenshot(
                            path=str(INTERIM_DIR / "collect_abort.png"),
                            full_page=True)
                    except Exception:
                        pass
                    budget -= 1
                    state["since_restart"] += 1
                    error_streak += 1
                    polite_sleep()
                    if error_streak >= ERROR_STREAK_ABORT:
                        aborted = True
                        break
                    continue
                budget -= 1
                state["since_restart"] += 1
                polite_sleep()
                if pdf is None:
                    print(f"no pdf {docket}")
                    error_streak = 0
                    continue
                out = RAW_DIR / f"{docket}.pdf"
                out.write_bytes(pdf)
                session.merge(RawDocket(
                    docket_number=docket, pdf_path=str(out),
                    fetched_at=datetime.now(), parse_status="pending",
                    notes="collector"))
                session.commit()
                have_pdf.add(docket)
                error_streak = 0
                print(f"saved {docket}")

            remaining = [d for d, h in rows
                         if h is not None and d not in have_pdf]
            status = "complete" if (not remaining and not aborted) else "partial"
            session.merge(HarvestWindow(
                week_start=start, week_end=end, total_rows=total,
                cp_criminal_rows=cp_n, status=status,
                searched_at=datetime.now(),
                notes=None if status == "complete"
                else f"{len(remaining)} dockets not yet fetched"))
            session.commit()
            print(f"week {start.isoformat()} to {end.isoformat()}: "
                  f"{total} rows, {cp_n} CP-51-CR, {status}, "
                  f"budget left {budget}")
            if status == "complete":
                complete.add(start)

        state["browser"].close()

    if aborted:
        print("possible portal pushback: run stopped; "
              "see data/interim/collect_abort.png")

    total_rows = session.query(RawDocket).count()
    on_disk = session.query(RawDocket).filter(
        RawDocket.pdf_path.isnot(None)).count()
    weeks_done = session.query(HarvestWindow).filter(
        HarvestWindow.status == "complete").count()
    print(f"ledger: {total_rows} docket rows, {on_disk} PDFs on disk, "
          f"{weeks_done} weeks complete, budget remaining {budget}")
    session.close()


if __name__ == "__main__":
    main()
```

### 2e. Edit `src/db/schema.py`: add the HarvestWindow table

Append this class to the end of the file, after the `RawDocket` class. Every
type it uses (Date, DateTime, Integer, String, Text, Optional, date, datetime)
is already imported at the top of the file, so add no imports.

```python
class HarvestWindow(Base):
    """One row per weekly search window: the collector's resume ledger and a
    per-week row-count log for spotting a truncated (capped) result page."""
    __tablename__ = "harvest_windows"

    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    week_end: Mapped[date] = mapped_column(Date)
    total_rows: Mapped[Optional[int]] = mapped_column(Integer)
    cp_criminal_rows: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    searched_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)
```

## Step 3: retire the enumeration collector

Confirm nothing still imports it (expect no hits other than the files being
removed):

```bash
grep -rn "enumerate" src/ scripts/ tests/
```

Then remove it and its test:

```bash
git rm src/acquire/enumerate.py tests/test_enumerate.py
```

## Step 4: offline verification (ask-first, no portal contact)

```bash
.venv/bin/python -m pytest tests/ -q
```
Expect green. `tests/test_windows.py` adds 6 tests; `tests/test_enumerate.py`
is gone. The existing parser and loader tests still pass.

```bash
.venv/bin/python -c "from src.db.session import init_db; init_db(); print('init ok')"
sqlite3 data/processed/phl.db ".tables"
sqlite3 data/processed/phl.db "SELECT count(*) FROM cases; SELECT count(*) FROM judges;"
```
Expect: `.tables` now lists `harvest_windows` alongside the existing tables;
cases count is 54 and judges count is 22, both unchanged (init_db creates only
missing tables and never drops data).

```bash
.venv/bin/python -c "from datetime import date; from src.acquire.windows import week_windows; w = week_windows(date(2023,1,1), date.today()); print(len(w), w[0], w[-1])"
```
Expect a plausible window count with the first window printed as
`(datetime.date(2023, 1, 2), datetime.date(2023, 1, 6))`.

```bash
.venv/bin/python -c "import scripts.collect; print('import ok')"
```
Expect `import ok` (importing must not launch a browser or hit the portal;
the main loop is guarded by `if __name__ == '__main__'`).

## Definition of done

1. `src/acquire/portal.py`, `src/acquire/windows.py`, `tests/test_windows.py`,
   `scripts/collect.py`, and the `HarvestWindow` addition to `src/db/schema.py`
   all match Step 2 exactly.
2. `src/acquire/enumerate.py` and `tests/test_enumerate.py` are removed and
   nothing imports them.
3. All Step 4 checks pass: pytest green, `harvest_windows` created, cases 54
   and judges 22 unchanged, window dry-run correct, `scripts.collect` imports.
4. No portal contact occurred during this task.
5. The worklog entry (below) is written before the final commit, so the commit
   contains it.
6. Staging is correct: source, schema, tests, and worklog only. Do not stage
   `data/processed/phl.db`, anything under `data/raw/`, or `data/interim/`.
7. Commit pushed.

## Worklog entry (write before the final commit)

Use the template in `tasks/worklog.md`. Title it
`Phase 2, search-form collector`. Record the files built and removed, each
approved command with its one-line result, deviations (none expected), and for
the next agent: the collector is built and offline-verified but has not
contacted the portal; the owner runs the first directed validation.

## After the agent finishes (owner action, not for the agent)

The owner runs the first live validation separately, one week at a time with a
tiny budget and eyes on the output, before any scaled collection.