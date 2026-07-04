"""
Fixture acquisition: fetch a small, polite batch of Philadelphia CP docket
sheet PDFs to serve as the parser's validation set.

Standalone by design; phase 2 proper refactors this into src/acquire/.
Run only when the owner directs it. Politeness is not optional: a randomized
MIN_DELAY to MAX_DELAY sleep separates every attempt, success or failure.

Usage:
  python scripts/fetch_fixtures.py --probe   # exactly one known docket
  python scripts/fetch_fixtures.py           # batch: stop at 30 saved or 60 tries
"""

from __future__ import annotations

import random
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from src.config import MIN_DELAY, MAX_DELAY, RAW_DIR, INTERIM_DIR
from src.db.session import SessionLocal, init_db
from src.db.schema import RawDocket
from src.acquire.portal import fetch_docket_pdf

PROBE_DOCKET = "CP-51-CR-0000001-2023"

TARGET_SAVED = 30   # stop after this many PDFs are on disk
MAX_ATTEMPTS = 60   # hard cap on portal lookups for this run
YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
SEQ_RANGE = (1, 6000)  # conservative; Philadelphia files far more per year


def candidate_dockets(n: int) -> list[str]:
    """Spread candidates across years with random sequences, no duplicates.

    Seeded so a re-run proposes the same batch and cached hits are skipped.
    """
    rng = random.Random(51)
    seen: set[str] = set()
    out: list[str] = []
    while len(out) < n:
        year = rng.choice(YEARS)
        seq = rng.randint(*SEQ_RANGE)
        docket = f"CP-51-CR-{seq:07d}-{year}"
        if docket not in seen:
            seen.add(docket)
            out.append(docket)
    return out


def polite_sleep() -> None:
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def main() -> None:
    probe = "--probe" in sys.argv
    init_db()
    session = SessionLocal()
    saved = 0
    attempts = 0
    target = 1 if probe else TARGET_SAVED
    candidates = [PROBE_DOCKET] if probe else candidate_dockets(MAX_ATTEMPTS)

    with sync_playwright() as p:
        # Headful on purpose: friendlier to the portal's bot checks.
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        for docket in candidates:
            if saved >= target or attempts >= MAX_ATTEMPTS:
                break
            out_path = RAW_DIR / f"{docket}.pdf"
            if out_path.exists():
                print(f"cached, skipping: {docket}")
                continue
            attempts += 1
            try:
                pdf = fetch_docket_pdf(page, docket)
            except PWTimeout:
                pdf = None
            except Exception as exc:  # keep the run alive; log type only
                print(f"error on {docket}: {type(exc).__name__}")
                pdf = None
            if pdf:
                out_path.write_bytes(pdf)
                saved += 1
                session.merge(RawDocket(
                    docket_number=docket,
                    pdf_path=str(out_path),
                    fetched_at=datetime.now(),
                    parse_status="pending",
                    notes="fixture batch 1",
                ))
                session.commit()
                print(f"saved {saved}: {docket}")
            else:
                print(f"no docket sheet: {docket}")
                if probe:
                    shot = INTERIM_DIR / "probe_failure.png"
                    page.screenshot(path=str(shot), full_page=True)
                    print(f"screenshot saved: {shot}")
            polite_sleep()
        browser.close()
    session.close()
    print(f"done: {saved} saved, {attempts} attempts")


if __name__ == "__main__":
    main()
