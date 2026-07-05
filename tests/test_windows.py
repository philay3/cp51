from datetime import date

from src.acquire.windows import week_windows


def test_first_window_matches_recon():
    w = week_windows(date(2023, 1, 1), date(2023, 1, 20))
    assert w[0] == (date(2023, 1, 2), date(2023, 1, 6))


def test_no_window_before_collection_start():
    w = week_windows(date(2023, 1, 1), date(2023, 1, 20))
    assert all(start >= date(2023, 1, 1) for start, _ in w)


def test_last_window_clamped_to_today():
    w = week_windows(date(2023, 1, 1), date(2023, 1, 18))
    assert w[-1] == (date(2023, 1, 16), date(2023, 1, 18))


def test_windows_are_ordered_and_weekly_when_monday_aligned():
    w = week_windows(date(2023, 1, 1), date(2023, 2, 28))
    for (s1, _), (s2, _) in zip(w, w[1:]):
        assert (s2 - s1).days == 7


def test_partial_first_week_has_no_year_boundary_gap():
    # 2025-01-01 is a Wednesday. The first window must start on Jan 1, not the
    # following Monday, so Wednesday-to-Friday filings are not skipped.
    w = week_windows(date(2025, 1, 1), date(2025, 1, 31))
    assert w[0] == (date(2025, 1, 1), date(2025, 1, 3))


def test_window_shape_never_exceeds_five_days():
    w = week_windows(date(2023, 1, 1), date(2023, 3, 1))
    for start, end in w:
        assert end >= start
        assert (end - start).days <= 4
