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
