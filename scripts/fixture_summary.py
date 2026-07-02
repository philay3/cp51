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
