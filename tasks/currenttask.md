# Current task: Phase 3, docket sheet parser

This file is self-contained. Everything needed for this task is here. Do not
consult other documents to perform it.

## Orientation (all the context you need)

CP51 builds a dataset of Philadelphia criminal court outcomes from public
Court of Common Pleas docket sheets. 31 fixture PDFs are already on disk in
data/raw/ (gitignored, local only), fetched in the previous task. This task
builds the parser that turns each PDF into one structured JSON record,
validates it against all 31 fixtures, and produces an audit pack the owner
checks by hand. No portal contact of any kind in this task. No database
loading (that is phase 4).

## Ground rules

- **Commands are ask-first.** Present the exact command(s) with a one line
  reason, stop, and wait. Related commands may be grouped as one logical
  block per ask. Run all python through .venv/bin/python.
- **Privacy, critical for this task.** The PDFs contain defendant names,
  dates of birth, and sometimes other personal names. Extracted text lives
  in memory only. Never print, log, or write extracted docket text anywhere
  except the whitelisted fields in the JSON schema below. Console output is
  docket numbers, counts, field names, and statuses only. The defendant's
  name and DOB exist transiently to compute a hash and are then discarded;
  a provided assertion verifies neither appears in any output file, and a
  failed assertion is a hard stop, not a warning. Free-text sentence
  conditions are NOT captured in v1 because conditions sometimes name
  people. ParseError messages name a section or field; they never quote
  docket text.
- **If the environment does not match this file's assumptions** (missing
  venv, wrong Python, unexpected files), stop and ask before adapting.
- **No em dashes anywhere.** Code, comments, commits, worklog entries.
- **Do not modify** README.md, docs/, PROJECT-INSTRUCTIONS.md, or this file.
  Report in tasks/worklog.md, append-only, format at the top of that file.

## Step 0: preflight

Verify, with approval:

```bash
.venv/bin/python --version
ls data/raw/*.pdf | wc -l
git log --oneline -3
```

Expect Python 3.12.x and 31 PDFs. If the most recent commit does not include
the fixture scripts from the previous task, commit them first ("Add fixture
acquisition scripts and environment repair") before any new work.

Then append pytest to requirements.txt (this task authorizes the addition)
and install it:

```text
pytest>=8.0
```

```bash
.venv/bin/pip install -r requirements.txt
```

## The output contract (interim JSON)

One file per docket at data/interim/{docket_number}.json, exactly this
shape. Unknown values are null, never guessed. An open case (no disposition
yet) is a SUCCESS with null dispositions and empty sentence lists, not a
failure. Dates are ISO YYYY-MM-DD strings or null.

```json
{
  "docket_number": "CP-51-CR-0000000-2024",
  "parser_version": 1,
  "parsed_at": "2026-07-02T12:00:00",
  "case": {
    "county": "Philadelphia",
    "court_type": "Common Pleas",
    "case_status": "Closed",
    "filed_date": "2024-03-14",
    "otn": "U1234567",
    "assigned_judge_raw": "Example, Anne",
    "defendant_hash": "64 hex chars"
  },
  "charges": [
    {
      "sequence": 1,
      "statute": "35 § 780-113 §§ A16",
      "grade": "M",
      "offense": "Int Poss Contr Subst By Per Not Reg",
      "disposition_raw": "Guilty Plea - Negotiated",
      "disposition_date": "2024-09-02",
      "disposition_judge_raw": "Example, Anne",
      "sentences": [
        {
          "sentence_type": "Probation",
          "min_days": 360,
          "max_days": 360,
          "program": "Probation 12 Months",
          "sentence_date": "2024-09-02",
          "raw_text": "Min of 12 Months, Max of 12 Months"
        }
      ]
    }
  ],
  "notes": []
}
```

Rules: raw_text on a sentence captures the type and length line only, never
conditions. notes[] records anything odd (legacy layout, unreadable section,
name-collision on the privacy assertion) in the parser's own words, never
quoting the PDF.

## Step 1: shared helpers (exact contents)

### src/identity.py

```python
"""
Pseudonymous identity: the only code that ever touches a defendant name or
DOB. The parser (phase 3) and the loader (phase 4) both import from here so
the hash is identical everywhere. Names exist in memory only; nothing in
this module logs, prints, or stores them.
"""

from __future__ import annotations

import hashlib
import re

from src.config import DEFENDANT_HASH_SALT


def normalize_name(name: str) -> str:
    lowered = name.lower()
    letters_only = re.sub(r"[^a-z\s]", " ", lowered)
    return re.sub(r"\s+", " ", letters_only).strip()


def hash_defendant(name: str, birth_year: int) -> str:
    basis = f"{DEFENDANT_HASH_SALT}|{normalize_name(name)}|{birth_year}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def assert_no_leak(sentinels: list[str], text: str) -> None:
    """Hard stop if any identifying string appears in output text.

    Sentinels are the defendant's printed name, its parts, and the DOB
    string. A collision (for example, a defendant who shares a surname with
    the judge) raises too; that is intentional. Investigate, record the
    collision in notes, and require owner confirmation before writing.
    """
    low = text.lower()
    for s in sentinels:
        s = s.strip()
        if len(s) >= 3 and s.lower() in low:
            raise RuntimeError(
                "privacy assertion failed: identifying string found in output"
            )
```

### src/parse/helpers.py

```python
"""Small, deterministic parsing helpers, unit tested before any PDF work."""

from __future__ import annotations

import re
from datetime import datetime

GRADES = {"F1", "F2", "F3", "F", "M1", "M2", "M3", "M", "S", "H1", "H2"}


class ParseError(Exception):
    """Raised when a docket cannot be parsed. Messages name the section or
    field only; they never quote docket text."""


def parse_date(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


_UNIT_DAYS = {"year": 360, "years": 360, "month": 30,
              "months": 30, "day": 1, "days": 1}


def to_days(length_text: str | None) -> int | None:
    """Convert '11 1/2 Months', '1 Year 6 Months', '90 Days' to days.

    Rule: year = 360, month = 30, half = 0.5 of the unit. Returns None when
    nothing parses (for example 'Life'); the caller keeps raw_text so
    nothing is lost.
    """
    if not length_text:
        return None
    length_text = length_text.replace("\u00bd", " 1/2")
    total = 0.0
    found = False
    pattern = re.compile(r"(\d+)(\s*1/2)?\s+(years?|months?|days?)",
                         re.IGNORECASE)
    for m in pattern.finditer(length_text):
        qty = float(m.group(1))
        if m.group(2):
            qty += 0.5
        total += qty * _UNIT_DAYS[m.group(3).lower()]
        found = True
    return int(round(total)) if found else None
```

## Step 2: unit tests (exact contents)

### tests/test_helpers.py

```python
import pytest

from src.identity import assert_no_leak, hash_defendant, normalize_name
from src.parse.helpers import parse_date, to_days


def test_parse_date():
    assert parse_date("03/14/2024") == "2024-03-14"
    assert parse_date("") is None
    assert parse_date("garbage") is None


def test_to_days_simple():
    assert to_days("23 Months") == 690


def test_to_days_compound():
    assert to_days("1 Year 6 Months") == 545


def test_to_days_half():
    assert to_days("11 1/2 Months") == 345


def test_to_days_unicode_half():
    assert to_days("11\u00bd Months") == 345


def test_to_days_days_only():
    assert to_days("90 Days") == 90


def test_to_days_unparseable():
    assert to_days("Life") is None


def test_normalize_name():
    assert normalize_name("  O'Brien,  Patrick J. ") == "o brien patrick j"


def test_hash_deterministic():
    assert hash_defendant("Smith, John", 1990) == hash_defendant("smith  john", 1990)


def test_leak_assertion_trips():
    with pytest.raises(RuntimeError):
        assert_no_leak(["Smith"], '{"judge": "smith, anne"}')
```

Run them:

```bash
.venv/bin/python -m pytest tests/ -q
```

All green before touching a PDF.

## Step 3: reconnaissance (exact contents)

Ground the extraction in the real layouts before writing it. This prints
only our own constant strings and counts.

### scripts/recon_headers.py

```python
"""Report which known section headers each fixture contains. Prints only
our own constants and counts, never PDF text."""

from __future__ import annotations

import pdfplumber

from src.config import RAW_DIR

HEADERS = [
    "CASE INFORMATION",
    "STATUS INFORMATION",
    "CALENDAR EVENTS",
    "DEFENDANT INFORMATION",
    "CHARGES",
    "DISPOSITION SENTENCING/PENALTIES",
    "COMMONWEALTH INFORMATION",
    "ATTORNEY INFORMATION",
    "ENTRIES",
]


def main() -> None:
    for path in sorted(RAW_DIR.glob("*.pdf")):
        with pdfplumber.open(path) as pdf:
            n_pages = len(pdf.pages)
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        missing = [h for h in HEADERS if h not in text]
        print(f"{path.stem}: pages={n_pages} "
              f"missing={', '.join(missing) if missing else 'none'}")


if __name__ == "__main__":
    main()
```

Run it, report the output, and adjust the header list if reality differs.
If any docket is missing CHARGES or CASE INFORMATION entirely, flag it as a
likely legacy layout and plan to fail it gracefully rather than force it.

## Step 4: the parser

### src/parse/docket_parser.py

Contract, fixed:

```python
def parse_docket(pdf_path: Path) -> tuple[dict, list[str]]:
    """Parse one docket sheet PDF.

    Returns (record, sentinels): record matches the JSON contract above;
    sentinels are the transient identifying strings (printed name, name
    parts, DOB text) for the caller's privacy assertion. Raises ParseError
    when the sheet cannot be read; error messages never quote docket text.
    """
```

Extraction targets, section by section:

| Section | Field | Lands in |
|---|---|---|
| Header/caption | docket number | docket_number (must equal filename stem) |
| CASE INFORMATION | Judge Assigned | case.assigned_judge_raw |
| CASE INFORMATION | Date Filed | case.filed_date |
| CASE INFORMATION | OTN | case.otn |
| STATUS INFORMATION | Case Status | case.case_status |
| DEFENDANT INFORMATION | name + DOB | case.defendant_hash only, via src.identity |
| CHARGES table | Seq, Grade, Statute, Statute Description | charges[].sequence, .grade, .statute, .offense |
| DISPOSITION SENTENCING/PENALTIES | per-charge offense disposition | charges[].disposition_raw |
| DISPOSITION SENTENCING/PENALTIES | disposition event date | charges[].disposition_date |
| DISPOSITION SENTENCING/PENALTIES | Sentencing Judge per event | charges[].disposition_judge_raw |
| DISPOSITION SENTENCING/PENALTIES | sentence components (type, program, Min of X Max of Y, date) | charges[].sentences[] via to_days |

Method, in order: build against three dockets first
(CP-51-CR-0001746-2022 for a clean negotiated plea, CP-51-CR-0000063-2024
for ARD, CP-51-CR-0005412-2023 for a jury trial with mixed outcomes), get
those three producing contract-valid JSON, then run the full batch. Never
guess: a field that cannot be located is null plus a notes[] entry. Grades
outside GRADES are kept as extracted and noted. Continuation pages repeat
headers; stitch by section, not by page.

## Step 5: batch runner (exact contents)

### scripts/parse_fixtures.py

```python
"""Batch-parse every fixture PDF into interim JSON. Console output is
docket numbers, counts, and statuses only, never extracted text."""

from __future__ import annotations

import json

from src.config import INTERIM_DIR, RAW_DIR
from src.db.schema import RawDocket
from src.db.session import SessionLocal, init_db
from src.identity import assert_no_leak
from src.parse.docket_parser import parse_docket
from src.parse.helpers import ParseError


def main() -> None:
    init_db()
    session = SessionLocal()
    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    ok = failed = 0
    print(f"{'docket':34} {'status':7} {'charges':>7} {'sentenced':>9} {'judge':>5}")
    for path in pdfs:
        docket = path.stem
        status, note = "parsed", None
        try:
            record, sentinels = parse_docket(path)
            text = json.dumps(record, indent=2, ensure_ascii=False)
            assert_no_leak(sentinels, text)
            (INTERIM_DIR / f"{docket}.json").write_text(text)
            n_ch = len(record["charges"])
            n_sent = sum(1 for c in record["charges"] if c["sentences"])
            has_judge = any(c["disposition_judge_raw"] for c in record["charges"])
            ok += 1
            print(f"{docket:34} {status:7} {n_ch:>7} {n_sent:>9} "
                  f"{'y' if has_judge else 'n':>5}")
        except (ParseError, RuntimeError) as exc:
            status, note = "failed", f"{type(exc).__name__}: {exc}"
            failed += 1
            print(f"{docket:34} {status:7} {'-':>7} {'-':>9} {'-':>5}")
        row = session.get(RawDocket, docket) or RawDocket(docket_number=docket)
        row.pdf_path = str(path)
        row.parse_status = status
        row.notes = note
        session.merge(row)
        session.commit()
    session.close()
    print(f"\ndone: {ok} parsed, {failed} failed of {len(pdfs)}")


if __name__ == "__main__":
    main()
```

Run with approval:

```bash
.venv/bin/python scripts/parse_fixtures.py
```

Target: 31 of 31 parsed (open cases count as parsed). Anything failed gets
investigated; if it is a genuine legacy layout, failed-with-notes is an
acceptable final state for at most 2 dockets, recorded in the worklog.

## Step 6: audit pack (exact contents)

### scripts/build_audit_pack.py

```python
"""Build the human audit pack: 10 stratified dockets with every extracted
field laid out for side-by-side checking against the PDFs. Contains no
names; the defendant appears only as a truncated hash."""

from __future__ import annotations

import json

from src.config import INTERIM_DIR

AUDIT_DOCKETS = [
    "CP-51-CR-0000063-2024",
    "CP-51-CR-0005412-2023",
    "CP-51-CR-0003972-2019",
    "CP-51-CR-0003400-2022",
    "CP-51-CR-0002515-2025",
    "CP-51-CR-0000267-2021",
    "CP-51-CR-0000871-2019",
    "CP-51-CR-0001746-2022",
    "CP-51-CR-0004427-2025",
    "CP-51-CR-0003030-2020",
]

HEADER = """# CP51 parser audit pack

Owner instructions: for each docket below, open the matching PDF at
data/raw/{docket}.pdf side by side with this file. Check every field line
against the PDF. If a line is wrong, change its [ ] to [x] and write the
correct value after it. Expect roughly 6 minutes per docket. When done,
report only the [x] lines (docket, field, correct value). Do not paste any
names anywhere.
"""


def line(label: str, value) -> str:
    shown = value if value not in (None, [], "") else "(null)"
    return f"- [ ] {label}: {shown}\n"


def main() -> None:
    out = [HEADER]
    audit_dir = INTERIM_DIR / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    for docket in AUDIT_DOCKETS:
        path = INTERIM_DIR / f"{docket}.json"
        if not path.exists():
            out.append(f"\n## {docket}\n\nNOT PARSED, see raw_dockets.notes\n")
            continue
        rec = json.loads(path.read_text())
        case = rec["case"]
        out.append(f"\n## {docket}\n\n")
        out.append(line("case_status", case["case_status"]))
        out.append(line("filed_date", case["filed_date"]))
        out.append(line("otn", case["otn"]))
        out.append(line("assigned_judge_raw", case["assigned_judge_raw"]))
        out.append(line("defendant_hash (first 8)",
                        (case["defendant_hash"] or "")[:8]))
        for c in rec["charges"]:
            out.append(f"\n### charge seq {c['sequence']}\n")
            out.append(line("statute", c["statute"]))
            out.append(line("grade", c["grade"]))
            out.append(line("offense", c["offense"]))
            out.append(line("disposition_raw", c["disposition_raw"]))
            out.append(line("disposition_date", c["disposition_date"]))
            out.append(line("disposition_judge_raw", c["disposition_judge_raw"]))
            for i, s in enumerate(c["sentences"], 1):
                out.append(line(f"sentence {i} type", s["sentence_type"]))
                out.append(line(f"sentence {i} min_days", s["min_days"]))
                out.append(line(f"sentence {i} max_days", s["max_days"]))
                out.append(line(f"sentence {i} date", s["sentence_date"]))
    (audit_dir / "audit_pack.md").write_text("".join(out))
    print(f"audit pack written: {audit_dir / 'audit_pack.md'}")


if __name__ == "__main__":
    main()
```

Run with approval, then hand off to the owner:

```bash
.venv/bin/python scripts/build_audit_pack.py
open data/interim/audit/audit_pack.md
```

## Step 7: the owner audit and the fix loop

Tell the owner, in these words: "The audit pack is ready. Your job
[yours, once this task, about an hour]: open the pack, check each docket's
fields against its PDF, mark wrong lines with [x] plus the correct value,
then paste me only the [x] lines. No names in the paste."

When corrections come back: fix the parser, re-run steps 5 and 6, and ask
the owner to re-check only the previously wrong fields. Repeat until the
owner reports 95% or more of checked fields correct. Wrong values found on
open-case dockets count too; nulls that should be nulls count as correct.

## Step 8: worklog, commit, push

Append the worklog entry (include: parse totals, audit pass rate, any
failed-with-notes dockets, deviations). Then, with approval:

```bash
git add .
git status
git commit -m "Add docket sheet parser with fixture validation and audit pack"
git push
```

Confirm in git status that nothing under data/ is staged except
data/lookups/ (interim JSON and PDFs stay local).

## Definition of done

- Helpers and tests in place; pytest green.
- Reconnaissance run and reported; extraction grounded in real layouts.
- All 31 fixtures parsed or failed-with-notes (at most 2 failures, legacy
  layouts only); zero silent failures.
- Every interim JSON matches the contract; privacy assertion enforced on
  every write; no name or DOB anywhere in any output or console line.
- Audit pack delivered; owner audit completed; 95% or more of checked
  fields correct after the fix loop.
- Worklog appended; one commit pushed; no loader work, no portal contact.
- Stop.