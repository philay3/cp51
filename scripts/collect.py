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

from src.acquire.guard import AbortGuard
from src.acquire.portal import PORTAL, pdf_from_href
from src.acquire.windows import week_windows
from src.config import (COLLECTION_START_YEAR, INTERIM_DIR, MAX_DELAY,
                         MIN_DELAY, RAW_DIR)
from src.db.schema import HarvestWindow, RawDocket
from src.db.session import SessionLocal, init_db

BROWSER_RESTART_EVERY = 150   # fetches per browser session, guards memory
CP_CRIM_RE = re.compile(r"CP-51-CR-\d{7}-\d{4}")


def polite_sleep() -> None:
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def screenshot(page) -> None:
    """Best-effort diagnostic screenshot; never raises into the fetch loop."""
    try:
        page.screenshot(path=str(INTERIM_DIR / "collect_abort.png"),
                        full_page=True)
    except Exception:
        pass


def run_search(page, start: date, end: date) -> None:
    """Drive the Date Filed search for Philadelphia over one weekly window."""
    page.goto(PORTAL, wait_until="networkidle")
    page.locator("select[title='Search By']").select_option("DateFiled")
    page.wait_for_timeout(800)
    page.locator("input[name='AdvanceSearch']").check()
    page.wait_for_timeout(800)
    page.locator("select[title='County']").select_option(label="Philadelphia")
    page.locator("input[name='FiledStartDate']").fill(start.strftime("%Y-%m-%d"))
    page.locator("input[name='FiledEndDate']").fill(end.strftime("%Y-%m-%d"))
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
        if cells.count() <= 2:
            continue
        text = cells.nth(2).inner_text() or ""
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
    # One guard for the whole run: throttling spans week boundaries, so the
    # no-pdf and error streaks must persist across weeks, not reset per week.
    guard = AbortGuard()
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
                    screenshot(state["page"])
                    budget -= 1
                    state["since_restart"] += 1
                    polite_sleep()
                    if guard.record("error"):
                        aborted = True
                        break
                    continue
                budget -= 1
                state["since_restart"] += 1
                polite_sleep()
                if pdf is None:
                    print(f"no pdf {docket}")
                    if guard.record("no_pdf"):
                        screenshot(state["page"])
                        print(f"no-pdf streak hit {guard.nopdf_abort}: "
                              "possible throttling")
                        aborted = True
                        break
                    continue
                out = RAW_DIR / f"{docket}.pdf"
                out.write_bytes(pdf)
                session.merge(RawDocket(
                    docket_number=docket, pdf_path=str(out),
                    fetched_at=datetime.now(), parse_status="pending",
                    notes="collector"))
                session.commit()
                have_pdf.add(docket)
                guard.record("saved")
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
