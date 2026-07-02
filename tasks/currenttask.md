# Current task: environment repair and fixture acquisition

This file is self-contained. Everything needed for this task is here. Do not
consult other documents to perform it.

## Orientation (all the context you need)

CP51 builds a dataset of Philadelphia criminal court outcomes from public
Court of Common Pleas docket sheets. Phase 1 (scaffold, schema, first commit)
is done; see tasks/worklog.md. This task does three things: repairs the
environment (a stray IDE setting and a Python 3.9 runtime), acquires roughly
30 real docket sheet PDFs as the parser's validation fixtures, and summarizes
what was fetched. No parsing logic is built in this task.

## Ground rules

- **Commands are ask-first.** Present the exact command(s) with a one line
  reason, stop, and wait. Related commands may be grouped as one logical
  block per ask. Never assume an outcome you have not seen.
- **Portal authorization, scoped to this task.** The owner directs the
  following and nothing more: up to 3 single-docket probe lookups, then one
  batch run capped at 60 lookups total. Every lookup is separated by the
  randomized MIN_DELAY to MAX_DELAY sleep, success or failure. If anything
  suggests blocking (repeated failures, challenge pages), stop immediately
  and report. No other portal contact of any kind.
- **Privacy.** Docket PDFs contain defendant names. Never print, log, or
  commit extracted docket text. PDFs stay in data/raw/, which is gitignored.
  Never read, print, or verify the value of DEFENDANT_HASH_SALT.
- **No em dashes anywhere.** Code, comments, commits, worklog entries.
- **Do not modify** README.md, docs/, PROJECT-INSTRUCTIONS.md, or this file.
  Report in tasks/worklog.md, append-only, format at the top of that file.

## Step 0: remove the env-injection setting

1. Delete .vscode/settings.json (it enables terminal environment file
   injection, which would surface .env values, including the salt, in every
   IDE terminal; config.py already loads .env at runtime so nothing needs it).
   If the file contains unrelated settings, remove only the env injection
   keys and say so in the worklog.
2. Append this block to .gitignore:

```gitignore

# IDE
.vscode/
```

3. Then tell the owner: "Step 0 done, safe to set the salt now." The owner
   sets it out of band. Never ask what it is. You may confirm it is set with
   exactly this command and nothing else (it prints no values):

```bash
grep -q "set-a-long-random-string-here" .env && echo "salt NOT set yet" || echo "salt set"
```

## Step 1: rebuild the runtime on Python 3.12+

Python 3.9 is end of life and the phase 5 analysis stack (current scipy and
statsmodels) no longer supports it. Keep the typing.Optional annotations in
schema.py exactly as they are (they run everywhere); only the interpreter
changes.

Check what exists:

```bash
python3.13 --version || python3.12 --version
```

If neither is present, propose (flag it as a system-level install):

```bash
brew install python@3.12
```

Then rebuild the environment (adjust python3.12 to whichever version exists):

```bash
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python -m src.db.session
python -c "import sqlalchemy, pdfplumber, yaml, playwright; import sys; print('env ok on', sys.version)"
```

## Step 2: create the fixture fetcher (exact contents)

### scripts/fetch_fixtures.py

```python
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

PORTAL = "https://ujsportal.pacourts.us/CaseSearch"
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


def fetch_docket_pdf(page, docket: str) -> bytes | None:
    """Search one docket number; return the docket sheet PDF bytes or None."""
    page.goto(PORTAL, wait_until="networkidle")
    page.get_by_label("Search By").select_option(label="Docket Number")
    page.get_by_label("Docket Number").fill(docket)
    page.get_by_role("button", name="Search").click()
    page.wait_for_load_state("networkidle")

    # The results row exposes a docket sheet link whose href carries a
    # one-time hash, so capture the href and fetch it inside this session.
    links = page.locator("a[href*='CpDocketSheet']")
    if links.count() == 0:
        return None
    href = links.first.get_attribute("href")
    if not href:
        return None
    url = href if href.startswith("http") else f"https://ujsportal.pacourts.us{href}"
    resp = page.context.request.get(url)
    if not resp.ok:
        return None
    body = resp.body()
    if not body.startswith(b"%PDF"):
        return None
    return body


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
```

### scripts/fixture_summary.py

```python
"""
Coverage summary for fixture PDFs: which disposition and sentence keywords
appear in each docket, so fixture variety can be judged at a glance.

Heuristic only ("Guilty Plea" also contains "Guilty"; treat counts as
approximate). Prints docket numbers and matched keywords ONLY. Never prints
extracted docket text: docket sheets contain defendant names and this
project keeps names out of consoles, logs, and files.
"""

from __future__ import annotations

from collections import Counter

import pdfplumber

from src.config import RAW_DIR

KEYWORDS = [
    "Nolle Prossed", "Withdrawn", "Dismissed",
    "Guilty Plea - Negotiated", "Guilty Plea - Non-Negotiated",
    "Guilty Plea", "Nolo Contendere", "Not Guilty", "ARD",
    "Probation Without Verdict", "Confinement", "Probation",
    "Jury Trial", "Bench Trial", "Migrated",
]


def main() -> None:
    totals: Counter = Counter()
    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    for path in pdfs:
        try:
            with pdfplumber.open(path) as pdf:
                text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
        except Exception as exc:
            print(f"{path.stem}: unreadable ({type(exc).__name__})")
            continue
        hits = [k for k in KEYWORDS if k in text]
        for k in hits:
            totals[k] += 1
        print(f"{path.stem}: {', '.join(hits) if hits else 'no keywords found'}")
    print(f"\ncoverage across {len(pdfs)} dockets:")
    for k in KEYWORDS:
        print(f"  {k}: {totals[k]}")


if __name__ == "__main__":
    main()
```

## Step 3: probe run (one docket)

Run, with owner approval:

```bash
python scripts/fetch_fixtures.py --probe
```

- If it saves the PDF: proceed to step 4.
- If it fails: read data/interim/probe_failure.png, adjust the selectors in
  fetch_docket_pdf to match what the page actually shows, and probe again.
  Maximum 3 probes total. If still failing after 3, stop, write a blocked
  worklog entry describing exactly what the page showed, and end the task.

## Step 4: batch run

Run, with owner approval:

```bash
python scripts/fetch_fixtures.py
```

Expect a slow run by design (30 saves at 3 to 7 seconds between lookups,
plus misses). Report the final "saved / attempts" line.

## Step 5: coverage summary

```bash
python scripts/fixture_summary.py
```

Paste the summary output (docket numbers and keywords only) into the chat
and include the coverage totals in the worklog entry. If fewer than 20 PDFs
saved, say so; the owner decides whether to direct a second batch.

## Step 6: worklog, commit, push

Append the worklog entry first (format at the top of tasks/worklog.md), then,
with approval:

```bash
git add .
git status
git commit -m "Repair environment and add fixture acquisition scripts"
git push
```

Confirm in git status that nothing under data/ is staged except
data/lookups/ (PDFs and the database are gitignored and must stay local).

## Definition of done

- .vscode env injection removed and .vscode/ gitignored.
- Owner confirmed able to set the salt (its value never touched or shown).
- .venv rebuilt on Python 3.12 or newer; env ok check passed.
- Both scripts created with exactly the given contents (selector fixes from
  the probe step are the one permitted deviation; note them in the worklog).
- Probe succeeded; batch run completed within the 60 lookup cap.
- Coverage summary produced with keywords only, no docket text.
- Worklog entry appended; one commit pushed; no PDFs or database committed.
- Stop. No parser code, no further portal contact.