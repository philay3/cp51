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
