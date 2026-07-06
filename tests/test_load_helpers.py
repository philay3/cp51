from src.db.load import (
    categorize_charge,
    categorize_statute,
    collapse_ws,
    load_lookups,
    slugify,
)

EXACT = {"35 § 780-113 §§ A30": "drug-delivery"}
PREFIX = {"35 § 780-113": "drug-possession", "18 § 3502": "burglary"}

# Tests below exercise the shipped taxonomy so ordering and coverage of the
# real charge_categories.yaml are proven, not a fixture copy of it.
_LK = load_lookups()
_EX, _PF, _INCH = _LK["statute_exact"], _LK["statute_prefix"], _LK["inchoate"]


def cc(statute, offense=""):
    return categorize_charge(statute, offense, _EX, _PF, _INCH)


def test_slugify():
    assert slugify("Shaffer, Zachary C.") == "shaffer-zachary-c"
    assert slugify("DeFino-Nastasi, Rose") == "defino-nastasi-rose"
    assert slugify("Meehan, William Austin Jr.") == "meehan-william-austin-jr"


def test_collapse_ws():
    assert collapse_ws("  Shaffer,   Zachary  C. ") == "Shaffer, Zachary C."


def test_categorize_exact_beats_prefix():
    assert categorize_statute("35 § 780-113 §§ A30", EXACT, PREFIX) == "drug-delivery"


def test_categorize_prefix():
    assert categorize_statute("35 § 780-113 §§ A16", EXACT, PREFIX) == "drug-possession"
    assert categorize_statute("18 § 3502 §§ A1I", EXACT, PREFIX) == "burglary"


def test_categorize_unknown_and_null():
    assert categorize_statute("18 § 903", EXACT, PREFIX) == "other"
    assert categorize_statute(None, EXACT, PREFIX) == "other"


def test_new_dedicated_categories():
    assert cc("18 § 907 §§ A") == "possessing-instrument-of-crime"
    assert cc("18 § 2705") == "reckless-endangerment"
    assert cc("18 § 3304 §§ A5") == "criminal-mischief"
    assert cc("18 § 7512 §§ A") == "communication-facility"
    assert cc("18 § 3301 §§ A1I") == "arson"


def test_remaps_into_existing():
    assert cc("18 § 3928 §§ A") == "theft"  # unauthorized use of vehicle
    assert cc("18 § 6312 §§ D") == "sexual-offenses"
    assert cc("75 § 3714") == "other-traffic"
    assert cc("23 § 6114 §§ A") == "public-order"


def test_inchoate_named_target():
    assert cc("18 § 901 §§ A", "Criminal Attempt - Murder") == "homicide"
    assert cc("18 § 903", "Conspiracy - Robbery Of Motor Vehicle") == "robbery"


def test_inchoate_bare_falls_to_inchoate():
    assert cc("18 § 903", "Conspiracy") == "inchoate"
    assert cc("18 § 901 §§ A", "Criminal Attempt") == "inchoate"


def test_inchoate_specific_before_general():
    # retail theft must win over theft
    assert cc("18 § 903", "Conspiracy - Retail Theft-Take Mdse") == "retail-theft"
    # aggravated assault must win over simple assault
    assert cc(
        "18 § 903", "Conspiracy - Aggravated Assault - Attempts to cause SBI"
    ) == "aggravated-assault"
