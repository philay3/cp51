from src.acquire.enumerate import (ERROR_STREAK_ABORT, MISS_STREAK_YEAR_END,
                                   format_docket, walk_year)


def test_format_docket():
    assert format_docket(2023, 1) == "CP-51-CR-0000001-2023"
    assert format_docket(2026, 12345) == "CP-51-CR-0012345-2026"


def test_budget_stops_the_walk():
    stats = walk_year(2023, {}, budget=3, lookup=lambda d: "found")
    assert stats["lookups"] == 3 and stats["found"] == 3
    assert not stats["exhausted"] and not stats["aborted"]


def test_ledgered_dockets_cost_no_lookups():
    statuses = {format_docket(2023, s): "found" for s in range(1, 6)}
    seen = []

    def lookup(d):
        seen.append(d)
        return "found"

    walk_year(2023, statuses, budget=2, lookup=lookup)
    assert seen == [format_docket(2023, 6), format_docket(2023, 7)]


def test_year_exhausts_on_miss_streak():
    stats = walk_year(2023, {}, budget=10000, lookup=lambda d: "not_found")
    assert stats["exhausted"] is True
    assert stats["lookups"] == MISS_STREAK_YEAR_END


def test_ledgered_misses_exhaust_without_lookups():
    statuses = {format_docket(2023, s): "found" for s in range(1, 11)}
    statuses.update({format_docket(2023, s): "not_found"
                     for s in range(11, 11 + MISS_STREAK_YEAR_END)})
    stats = walk_year(2023, statuses, budget=100,
                      lookup=lambda d: "found")
    assert stats["exhausted"] is True and stats["lookups"] == 0


def test_error_streak_aborts_and_is_not_ledgered():
    statuses = {}
    stats = walk_year(2023, statuses, budget=100, lookup=lambda d: "error")
    assert stats["aborted"] is True
    assert stats["errors"] == ERROR_STREAK_ABORT
    assert statuses == {}
