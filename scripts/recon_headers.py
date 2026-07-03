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
