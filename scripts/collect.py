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
