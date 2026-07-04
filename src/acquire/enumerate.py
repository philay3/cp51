"""
Enumeration logic for the production collector, kept free of any portal or
database dependency so it is fully unit testable. The collector wires
walk_year to the live portal and the raw_dockets ledger.
"""

from __future__ import annotations

MISS_STREAK_YEAR_END = 25   # consecutive not-found means the year is exhausted
ERROR_STREAK_ABORT = 5      # consecutive errors means possible pushback, stop
SEQ_CEILING = 20000         # sanity ceiling far above real annual volume


def format_docket(year: int, seq: int) -> str:
    return f"CP-51-CR-{seq:07d}-{year}"


def walk_year(year: int, statuses: dict, budget: int, lookup) -> dict:
    """Walk one year's sequences ascending, skipping the ledger.

    statuses: docket_number -> "found" | "not_found" (the ledger; mutated
    in place as live results arrive). lookup(docket_number) returns
    "found" | "not_found" | "error" and performs the actual portal work.

    Stops when: budget new lookups are spent, the trailing miss streak
    reaches MISS_STREAK_YEAR_END (ledgered misses count toward it, so
    re-runs exhaust a finished year with zero lookups), ERROR_STREAK_ABORT
    consecutive errors occur, or SEQ_CEILING is hit. Errors are never
    written to statuses, so errored sequences are retried on the next run.
    """
    stats = {"lookups": 0, "found": 0, "not_found": 0, "errors": 0,
             "exhausted": False, "aborted": False}
    miss_streak = 0
    error_streak = 0
    seq = 1
    while seq <= SEQ_CEILING:
        d = format_docket(year, seq)
        known = statuses.get(d)
        if known == "found":
            miss_streak = 0
        elif known == "not_found":
            miss_streak += 1
        else:
            if stats["lookups"] >= budget:
                return stats
            result = lookup(d)
            stats["lookups"] += 1
            if result == "found":
                stats["found"] += 1
                statuses[d] = "found"
                miss_streak = 0
                error_streak = 0
            elif result == "not_found":
                stats["not_found"] += 1
                statuses[d] = "not_found"
                miss_streak += 1
                error_streak = 0
            else:
                stats["errors"] += 1
                error_streak += 1
                if error_streak >= ERROR_STREAK_ABORT:
                    stats["aborted"] = True
                    return stats
        if miss_streak >= MISS_STREAK_YEAR_END:
            stats["exhausted"] = True
            return stats
        seq += 1
    stats["exhausted"] = True
    return stats
