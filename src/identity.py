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


RELATED_CASE_KEYS = {"docket_number", "court", "association_reason"}


def assert_related_cases_clean(record: dict) -> None:
    """Structural half of the privacy assertion for Phase 7 MC sheets.

    A related-cases row carries a caption column with third-party names. The
    parser captures only docket number, court, and association reason. This
    guard fails the write if any entry carries a field beyond those three, so a
    caption (or any other stray value) can never reach interim JSON.
    """
    for entry in record.get("related_cases", []):
        extra = set(entry.keys()) - RELATED_CASE_KEYS
        if extra:
            raise RuntimeError(
                "privacy assertion failed: related case entry carries "
                "unexpected fields"
            )
