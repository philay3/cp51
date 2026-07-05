import pytest

from src.acquire.guard import (AbortGuard, ERROR_STREAK_ABORT,
                               NO_PDF_STREAK_ABORT)


def test_isolated_no_pdf_never_aborts():
    g = AbortGuard()
    for _ in range(50):                     # genuine misses scattered among saves
        assert g.record("no_pdf") is False
        assert g.record("saved") is False


def test_consecutive_no_pdf_aborts_at_threshold():
    g = AbortGuard()
    for _ in range(NO_PDF_STREAK_ABORT - 1):
        assert g.record("no_pdf") is False
    assert g.record("no_pdf") is True       # the Nth fires


def test_save_resets_no_pdf_streak():
    g = AbortGuard()
    for _ in range(NO_PDF_STREAK_ABORT - 1):
        g.record("no_pdf")
    assert g.record("saved") is False       # one clean save clears it
    for _ in range(NO_PDF_STREAK_ABORT - 1):
        assert g.record("no_pdf") is False
    assert g.record("no_pdf") is True


def test_consecutive_errors_still_abort():
    g = AbortGuard()
    for _ in range(ERROR_STREAK_ABORT - 1):
        assert g.record("error") is False
    assert g.record("error") is True


def test_no_pdf_does_not_reset_error_streak():
    g = AbortGuard()
    for _ in range(ERROR_STREAK_ABORT - 1):
        g.record("error")
    g.record("no_pdf")                       # softer signal doesn't clear a hard-error run
    assert g.record("error") is True


def test_unknown_outcome_raises():
    with pytest.raises(ValueError):
        AbortGuard().record("bogus")
