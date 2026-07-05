"""
Consecutive-failure abort logic for the search-form collector, kept portal-free
so it can be unit-tested offline (no Playwright, no network).

Two failure signatures mean possible portal pushback:
  - a run of thrown exceptions (hard errors: timeouts, transport failures)
  - a run of "no pdf" results (a 429 or a "slow down" page returned as a normal
    HTTP response, which pdf_from_href reports as None rather than raising)

Only a clean save resets the streaks: a save is the only positive proof the
portal is still serving real sheets. An isolated genuine missing sheet nudges
the no-pdf streak but cannot reach the threshold on its own.
"""

from __future__ import annotations

ERROR_STREAK_ABORT = 5    # consecutive thrown exceptions -> abort
NO_PDF_STREAK_ABORT = 8   # consecutive "no pdf" responses -> abort (softer
                          # signal than an exception, so a higher bar)


class AbortGuard:
    def __init__(self, error_abort: int = ERROR_STREAK_ABORT,
                 nopdf_abort: int = NO_PDF_STREAK_ABORT) -> None:
        self.error_abort = error_abort
        self.nopdf_abort = nopdf_abort
        self.error_streak = 0
        self.nopdf_streak = 0

    def record(self, outcome: str) -> bool:
        """Record one fetch outcome; return True if the run should abort.

        outcome is one of "saved", "no_pdf", "error".
        """
        if outcome == "saved":
            self.error_streak = 0
            self.nopdf_streak = 0
            return False
        if outcome == "error":
            self.error_streak += 1
            return self.error_streak >= self.error_abort
        if outcome == "no_pdf":
            self.nopdf_streak += 1
            return self.nopdf_streak >= self.nopdf_abort
        raise ValueError(f"unknown outcome: {outcome!r}")
