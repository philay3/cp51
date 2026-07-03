from src.db.load import categorize_statute, collapse_ws, slugify

EXACT = {"35 § 780-113 §§ A30": "drug-delivery"}
PREFIX = {"35 § 780-113": "drug-possession", "18 § 3502": "burglary"}


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
