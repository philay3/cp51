"""
Read-only corpus explorer for CP51. Prints the shape of the collected data so
the owner can watch it grow without hand-writing SQL.

This script is strictly read-only. It opens the database with a read-only URI
connection (mode=ro), runs SELECT queries only, and never issues an INSERT,
UPDATE, DELETE, schema change, or init_db. It contacts no portal and creates no
files other than itself.

Privacy: it prints only name-free data (docket counts, judge names which are
public officials, statute and category labels, dispositions, dates, counts). It
never joins to or reads from the defendants table, and it never prints a
defendant id or a case caption.

Sections printed, in order:
  1. Corpus totals: the progress meter (cases, charges, judges, and the
     harvest_windows week counts and CP-51-CR rows seen).
  2. Judge coverage: each judge with case count, the judge-signal health check.
  3. Category depth: each charge category with charge count, so real volume is
     visible where it sits.
  4. Thin-cell view: charge category by judge, for cells at or above a
     threshold, showing which pairings approach a usable sample.
  5. Disposition breakdown: disposition_category counts, including open charges
     (a null disposition_category).
  6. Sentence length by category: for confinement sentences, the category, the
     count of sentenced charges, and the average min and max length in days.
  7. Sentence length by judge: the same, grouped by the sentencing judge
     (charges.disposition_judge_id), for cells at or above MIN_CELL.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/explore.py
  PYTHONPATH=. .venv/bin/python scripts/explore.py --min-cell 10
"""

from __future__ import annotations

import argparse
import sqlite3

from src.config import PROCESSED_DIR

# Thin-cell threshold: a category-by-judge cell must have at least this many
# charges to be shown. Raise it as the corpus grows. Overridable with
# --min-cell.
MIN_CELL = 5

DB_PATH = PROCESSED_DIR / "phl.db"


def connect_readonly() -> sqlite3.Connection:
    """Open the database read-only. mode=ro guarantees no write can occur and
    fails cleanly if the file is missing rather than creating an empty one."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def print_header(title: str) -> None:
    print()
    print(title)
    print("=" * len(title))


def print_two_column(rows, left_label: str, right_label: str) -> None:
    """Print (label, count) rows as two aligned columns, count right-aligned.
    Prints a 'no rows yet' line when the section is empty."""
    if not rows:
        print("  no rows yet")
        return
    left_width = max(len(left_label), max(len(str(r[0])) for r in rows))
    right_width = max(len(right_label), max(len(str(r[1])) for r in rows))
    print(f"  {left_label:<{left_width}}  {right_label:>{right_width}}")
    print(f"  {'-' * left_width}  {'-' * right_width}")
    for label, count in rows:
        print(f"  {str(label):<{left_width}}  {count:>{right_width}}")


def print_three_column(rows, c1: str, c2: str, c3: str) -> None:
    """Print (a, b, count) rows as three aligned columns, count right-aligned.
    Prints a 'no rows yet' line when the section is empty."""
    if not rows:
        print("  no rows yet")
        return
    w1 = max(len(c1), max(len(str(r[0])) for r in rows))
    w2 = max(len(c2), max(len(str(r[1])) for r in rows))
    w3 = max(len(c3), max(len(str(r[2])) for r in rows))
    print(f"  {c1:<{w1}}  {c2:<{w2}}  {c3:>{w3}}")
    print(f"  {'-' * w1}  {'-' * w2}  {'-' * w3}")
    for a, b, count in rows:
        print(f"  {str(a):<{w1}}  {str(b):<{w2}}  {count:>{w3}}")


def print_four_column(rows, c1: str, c2: str, c3: str, c4: str) -> None:
    """Print (label, count, avg_min, avg_max) rows as four aligned columns, the
    three numeric columns right-aligned. Prints a 'no rows yet' line when the
    section is empty."""
    if not rows:
        print("  no rows yet")
        return
    w1 = max(len(c1), max(len(str(r[0])) for r in rows))
    w2 = max(len(c2), max(len(str(r[1])) for r in rows))
    w3 = max(len(c3), max(len(str(r[2])) for r in rows))
    w4 = max(len(c4), max(len(str(r[3])) for r in rows))
    print(f"  {c1:<{w1}}  {c2:>{w2}}  {c3:>{w3}}  {c4:>{w4}}")
    print(f"  {'-' * w1}  {'-' * w2}  {'-' * w3}  {'-' * w4}")
    for a, count, avg_min, avg_max in rows:
        print(f"  {str(a):<{w1}}  {count:>{w2}}  "
              f"{avg_min:>{w3}}  {avg_max:>{w4}}")


def scalar(conn: sqlite3.Connection, sql: str) -> int:
    value = conn.execute(sql).fetchone()[0]
    return value if value is not None else 0


def section_corpus_totals(conn: sqlite3.Connection) -> None:
    print_header("Corpus totals (progress meter)")
    cases = scalar(conn, "SELECT count(*) FROM cases")
    charges = scalar(conn, "SELECT count(*) FROM charges")
    judges = scalar(conn, "SELECT count(*) FROM judges")
    weeks_touched = scalar(conn, "SELECT count(*) FROM harvest_windows")
    weeks_complete = scalar(
        conn, "SELECT count(*) FROM harvest_windows WHERE status = 'complete'")
    cp_rows_seen = scalar(
        conn, "SELECT sum(cp_criminal_rows) FROM harvest_windows")
    rows = [
        ("cases", cases),
        ("charges", charges),
        ("judges", judges),
        ("weeks touched", weeks_touched),
        ("weeks complete", weeks_complete),
        ("CP-51-CR rows seen", cp_rows_seen),
    ]
    print_two_column(rows, "metric", "count")


def section_judge_coverage(conn: sqlite3.Connection) -> None:
    print_header("Judge coverage (judge-signal health check)")
    rows = conn.execute(
        """
        SELECT j.name_normalized AS judge, count(*) AS n
        FROM cases c
        JOIN judges j ON c.judge_id = j.id
        GROUP BY j.id
        ORDER BY n DESC, j.name_normalized
        """
    ).fetchall()
    print_two_column(rows, "judge", "cases")


def section_category_depth(conn: sqlite3.Connection) -> None:
    print_header("Category depth (where real volume sits)")
    rows = conn.execute(
        """
        SELECT cc.name AS category, count(*) AS n
        FROM charges ch
        JOIN charge_categories cc ON ch.category_id = cc.id
        GROUP BY cc.id
        ORDER BY n DESC, cc.name
        """
    ).fetchall()
    print_two_column(rows, "category", "charges")


def section_thin_cells(conn: sqlite3.Connection, min_cell: int) -> None:
    print_header(f"Thin-cell view: category by judge, cells >= {min_cell}")
    rows = conn.execute(
        """
        SELECT cc.name AS category, j.name_normalized AS judge, count(*) AS n
        FROM charges ch
        JOIN cases c ON ch.docket_number = c.docket_number
        JOIN judges j ON c.judge_id = j.id
        JOIN charge_categories cc ON ch.category_id = cc.id
        GROUP BY cc.id, j.id
        HAVING n >= ?
        ORDER BY n DESC, cc.name, j.name_normalized
        """,
        (min_cell,),
    ).fetchall()
    print_three_column(rows, "category", "judge", "charges")


def section_disposition_breakdown(conn: sqlite3.Connection) -> None:
    print_header("Disposition breakdown (raw outcome mix)")
    rows = conn.execute(
        """
        SELECT disposition_category AS disposition, count(*) AS n
        FROM charges
        GROUP BY disposition_category
        ORDER BY n DESC, disposition_category
        """
    ).fetchall()
    display = [
        (r["disposition"] if r["disposition"] is not None
         else "(null: open charges)", r["n"])
        for r in rows
    ]
    print_two_column(display, "disposition", "charges")


def section_sentence_length_by_category(conn: sqlite3.Connection) -> None:
    print_header("Sentence length by category (confinement only, days)")
    # Confinement sentences only, so probation-only or fine-only dispositions
    # do not dilute the length. min_days and max_days are already stored in
    # days (day=1, month=30, year=360 applied at parse time), so no conversion
    # is needed here. Require min_days not null so the count matches the rows
    # that feed the averages.
    rows = conn.execute(
        """
        SELECT cc.name AS category,
               count(*) AS n,
               round(avg(s.min_days)) AS avg_min,
               round(avg(s.max_days)) AS avg_max
        FROM sentences s
        JOIN charges ch ON s.charge_id = ch.id
        JOIN charge_categories cc ON ch.category_id = cc.id
        WHERE s.sentence_type = 'Confinement'
          AND s.min_days IS NOT NULL
        GROUP BY cc.id
        ORDER BY n DESC, cc.name
        """
    ).fetchall()
    display = [
        (r["category"], r["n"], int(r["avg_min"]), int(r["avg_max"]))
        for r in rows
    ]
    print_four_column(
        display, "category", "charges", "avg min days", "avg max days")


def section_sentence_length_by_judge(conn: sqlite3.Connection,
                                     min_cell: int) -> None:
    print_header(
        f"Sentence length by judge (confinement only, days, cells >= "
        f"{min_cell})")
    # Keyed on the charge's disposition_judge_id (the sentencing judge), unlike
    # the judge-coverage and thin-cell sections which key on cases.judge_id
    # (the assigned judge). Confinement only, lengths already in days.
    rows = conn.execute(
        """
        SELECT j.name_normalized AS judge,
               count(*) AS n,
               round(avg(s.min_days)) AS avg_min,
               round(avg(s.max_days)) AS avg_max
        FROM sentences s
        JOIN charges ch ON s.charge_id = ch.id
        JOIN judges j ON ch.disposition_judge_id = j.id
        WHERE s.sentence_type = 'Confinement'
          AND s.min_days IS NOT NULL
        GROUP BY j.id
        HAVING n >= ?
        ORDER BY n DESC, j.name_normalized
        """,
        (min_cell,),
    ).fetchall()
    display = [
        (r["judge"], r["n"], int(r["avg_min"]), int(r["avg_max"]))
        for r in rows
    ]
    print_four_column(
        display, "judge", "charges", "avg min days", "avg max days")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only corpus explorer for CP51.")
    parser.add_argument(
        "--min-cell", type=int, default=MIN_CELL,
        help=f"thin-cell threshold for the category-by-judge view "
             f"(default {MIN_CELL})")
    args = parser.parse_args()

    conn = connect_readonly()
    try:
        section_corpus_totals(conn)
        section_judge_coverage(conn)
        section_category_depth(conn)
        section_thin_cells(conn, args.min_cell)
        section_disposition_breakdown(conn)
        section_sentence_length_by_category(conn)
        section_sentence_length_by_judge(conn, args.min_cell)
        print()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
