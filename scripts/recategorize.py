"""Re-apply charge categorization to the existing database in place.

Reuses the same YAML taxonomy and mapper as the loader, recomputing each
charge's category from its stored statute and offense text. Idempotent by
construction: the category is a pure function of fields already in the row, so
running twice leaves every count identical. Touches only charges.category_id;
reads nothing but statute, offense, and category, so the caption and
defendant-name privacy invariant is untouched.

Console output prints only statutes, category slugs, and counts.
"""

from __future__ import annotations

from collections import Counter

from src.db.load import categorize_charge, load_lookups, upsert_categories
from src.db.schema import Charge
from src.db.session import SessionLocal, init_db


def main() -> None:
    init_db()
    session = SessionLocal()
    lookups = load_lookups()
    cat_ids = upsert_categories(session, lookups["categories"])

    stats: Counter = Counter()
    changed = 0
    for charge in session.query(Charge).all():
        slug = categorize_charge(charge.statute, charge.offense,
                                 lookups["statute_exact"],
                                 lookups["statute_prefix"],
                                 lookups["inchoate"])
        new_id = cat_ids.get(slug)
        if charge.category_id != new_id:
            charge.category_id = new_id
            changed += 1
        stats[slug] += 1
    session.commit()

    total = sum(stats.values())
    print(f"recategorized: {total} charges, {changed} reassigned")
    print("category distribution:")
    for slug, n in stats.most_common():
        print(f"  {n:>4}  {slug}")
    session.close()


if __name__ == "__main__":
    main()
