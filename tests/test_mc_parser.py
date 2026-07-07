"""Unit tests for the Phase 7 MC parser delta, exercised on synthetic text
via parse_docket_text (no PDF needed). Fictional surname Example and docket
MC-51-CR-0000000-2025 only; no real names or captions appear here.
"""

from __future__ import annotations

import pytest

from src.identity import assert_related_cases_clean
from src.parse.docket_parser import (
    detect_court_type,
    parse_docket_text,
    parse_related_cases,
)


def mc_page() -> str:
    """A minimal MC-shaped sheet with the four new sections. The related-cases
    row deliberately carries a fake caption so the test can prove it is
    dropped."""
    return "\n".join([
        "MUNICIPAL COURT OF PHILADELPHIA COUNTY",
        "DOCKET",
        "Docket Number: MC-51-CR-0000000-2025",
        "CASE INFORMATION",
        "Judge Assigned: Date Filed: 01/06/2025",
        "OTN: X 1234567-8",
        "Case Local Number Type(s) Case Local Number(s)",
        "District Control Number 9988776655",
        "RELATED CASES",
        "Docket Number Court Caption Association Reason",
        "CP-51-CR-0000000-2025 Court of Common Pleas "
        "Commonwealth v. Example, Adam Refiled",
        "STATUS INFORMATION",
        "Case Status: Open",
        "DEFENDANT INFORMATION",
        "Date Of Birth: 01/01/1990",
        "CASE PARTICIPANTS",
        "Participant Type Name",
        "Defendant Example, Chris",
        "CHARGES",
        "Seq. Statute Grade Description",
        "1 1 18 § 2701 M1 Simple Assault 01/01/2025 X1234567",
    ])


def cp_page() -> str:
    """A CP-shaped sheet with a Case Local Number(s) table and no related
    cases, to prove the delta leaves CP parsing intact."""
    return "\n".join([
        "COURT OF COMMON PLEAS OF PHILADELPHIA COUNTY",
        "DOCKET",
        "Docket Number: CP-51-CR-0000000-2025",
        "CASE INFORMATION",
        "Judge Assigned: Example, Judge A. Date Filed: 02/03/2025",
        "OTN: X 7654321-1",
        "Case Local Number Type(s) Case Local Number(s)",
        "District Control Number 1122334455",
        "STATUS INFORMATION",
        "Case Status: Active",
        "DEFENDANT INFORMATION",
        "Date Of Birth: 05/05/1985",
        "CASE PARTICIPANTS",
        "Participant Type Name",
        "Defendant Example, Dana",
        "CHARGES",
        "Seq. Statute Grade Description",
        "1 1 18 § 3502 F1 Burglary 02/01/2025 X7654321",
    ])


def test_court_type_detection_both_prefixes():
    assert detect_court_type("MC-51-CR-0000000-2025") == "Municipal Court"
    assert detect_court_type("CP-51-CR-0000000-2025") == "Common Pleas"


def test_mc_record_court_type_and_dc_number():
    record, _ = parse_docket_text("MC-51-CR-0000000-2025", [mc_page()])
    assert record["case"]["court_type"] == "Municipal Court"
    assert record["case"]["dc_number"] == "9988776655"


def test_cp_record_court_type_and_dc_number():
    record, _ = parse_docket_text("CP-51-CR-0000000-2025", [cp_page()])
    assert record["case"]["court_type"] == "Common Pleas"
    assert record["case"]["dc_number"] == "1122334455"
    assert record["related_cases"] == []


def test_related_cases_drops_caption():
    record, _ = parse_docket_text("MC-51-CR-0000000-2025", [mc_page()])
    rc = record["related_cases"]
    assert len(rc) == 1
    entry = rc[0]
    assert entry == {
        "docket_number": "CP-51-CR-0000000-2025",
        "court": "Common Pleas",
        "association_reason": "Refiled",
    }
    # The fake caption name must appear nowhere in the record.
    import json
    blob = json.dumps(record)
    assert "Adam" not in blob


def test_related_cases_parser_ignores_header_and_free_text():
    lines = [
        "Docket Number Court Caption Association Reason",
        "MC-51-CR-0000001-2025 Municipal Court "
        "Commonwealth v. Example, Blake Consolidated",
        "some unrelated free text with no docket number",
    ]
    out = parse_related_cases(lines)
    assert out == [{
        "docket_number": "MC-51-CR-0000001-2025",
        "court": "Municipal Court",
        "association_reason": "Consolidated",
    }]


def test_privacy_guard_rejects_extra_field():
    bad = {"related_cases": [{
        "docket_number": "MC-51-CR-0000000-2025",
        "court": "Municipal Court",
        "association_reason": "Refiled",
        "caption": "Example, Adam",
    }]}
    with pytest.raises(RuntimeError):
        assert_related_cases_clean(bad)


def test_privacy_guard_passes_clean_record():
    good = {"related_cases": [{
        "docket_number": "MC-51-CR-0000000-2025",
        "court": "Municipal Court",
        "association_reason": "Refiled",
    }]}
    assert_related_cases_clean(good) is None
