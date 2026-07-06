"""
Shared read-only corpus queries for CP51.

Every function here runs SELECT statements only against a read-only
(mode=ro) connection and returns plain row lists. Nothing in this module
writes to the database, calls init_db, changes the schema, or contacts a
portal. It is the single source of truth for the dashboard's numbers.

Privacy: no function joins to or reads from the defendants table, and none
selects a defendant id or a case caption. The judge dimension uses two
distinct keys that must not be conflated: cases.judge_id is the assigned
judge, charges.disposition_judge_id is the sentencing judge.

Sentence lengths are stored pre-normalized in days in sentences.min_days
and sentences.max_days (day=1, month=30, year=360 applied at parse time),
so the averages here are taken directly over those columns, no conversion.
"""

from __future__ import annotations

import sqlite3

from src.config import PROCESSED_DIR

# Total weeks in the collection window (the progress-meter denominator).
TOTAL_WEEKS = 183

# Thin-cell threshold: a category-by-judge (or per-judge) cell must carry at
# least this many rows to be shown. Matches scripts/explore.py's MIN_CELL.
MIN_CELL = 5

# The sentence types that carry a length. ARD, No Further Penalty, and Fines
# and Costs have no length and are excluded from the length panels.
LENGTH_TYPES = ("Confinement", "Probation")

DB_PATH = PROCESSED_DIR / "phl.db"


def connect_readonly() -> sqlite3.Connection:
    """Open the database read-only. mode=ro guarantees no write can occur and
    fails cleanly if the file is missing rather than creating an empty one."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def scalar(conn: sqlite3.Connection, sql: str) -> int:
    value = conn.execute(sql).fetchone()[0]
    return value if value is not None else 0


def corpus_totals(conn: sqlite3.Connection) -> dict:
    """Progress-meter numbers: corpus counts and harvest-window coverage."""
    return {
        "cases": scalar(conn, "SELECT count(*) FROM cases"),
        "charges": scalar(conn, "SELECT count(*) FROM charges"),
        "judges": scalar(conn, "SELECT count(*) FROM judges"),
        "sentences": scalar(conn, "SELECT count(*) FROM sentences"),
        "weeks_touched": scalar(conn, "SELECT count(*) FROM harvest_windows"),
        "weeks_complete": scalar(
            conn,
            "SELECT count(*) FROM harvest_windows WHERE status = 'complete'"),
        "cp_rows_seen": scalar(
            conn, "SELECT sum(cp_criminal_rows) FROM harvest_windows"),
        "total_weeks": TOTAL_WEEKS,
    }


def category_distribution(conn: sqlite3.Connection):
    """Charge count per category, descending. Rows: (category, n)."""
    return conn.execute(
        """
        SELECT cc.name AS category, count(*) AS n
        FROM charges ch
        JOIN charge_categories cc ON ch.category_id = cc.id
        GROUP BY cc.id
        ORDER BY n DESC, cc.name
        """
    ).fetchall()


def disposition_breakdown(conn: sqlite3.Connection):
    """Overall disposition_category shares, null bucketed as open charges.
    Rows: (disposition_label, n)."""
    rows = conn.execute(
        """
        SELECT disposition_category AS disposition, count(*) AS n
        FROM charges
        GROUP BY disposition_category
        ORDER BY n DESC, disposition_category
        """
    ).fetchall()
    return [
        (r["disposition"] if r["disposition"] is not None
         else "(null: open charges)", r["n"])
        for r in rows
    ]


def outcome_mix(conn: sqlite3.Connection):
    """Per category, the count of each sentence type plus a non-sentence
    bucket for charges that carry no sentence row. The grain is mixed on
    purpose: sentence-type counts are per sentence component (a charge can
    carry more than one), the non-sentence bucket is per charge. Rows:
    (category, bucket, n). The caller pivots into shares."""
    return conn.execute(
        """
        SELECT cc.name AS category, s.sentence_type AS bucket, count(*) AS n
        FROM sentences s
        JOIN charges ch ON s.charge_id = ch.id
        JOIN charge_categories cc ON ch.category_id = cc.id
        GROUP BY cc.id, s.sentence_type
        UNION ALL
        SELECT cc.name AS category,
               'No sentence (disposition only)' AS bucket,
               count(*) AS n
        FROM charges ch
        JOIN charge_categories cc ON ch.category_id = cc.id
        WHERE NOT EXISTS (
            SELECT 1 FROM sentences s WHERE s.charge_id = ch.id)
        GROUP BY cc.id
        ORDER BY category
        """
    ).fetchall()


def sentence_length_by_type(conn: sqlite3.Connection):
    """Average min and max length in days by category, for the two sentence
    types that carry a length (Confinement, Probation). min_days not null so
    the count matches the rows feeding the averages. Rows:
    (category, sentence_type, n, avg_min, avg_max)."""
    rows = conn.execute(
        """
        SELECT cc.name AS category,
               s.sentence_type AS sentence_type,
               count(*) AS n,
               round(avg(s.min_days)) AS avg_min,
               round(avg(s.max_days)) AS avg_max
        FROM sentences s
        JOIN charges ch ON s.charge_id = ch.id
        JOIN charge_categories cc ON ch.category_id = cc.id
        WHERE s.sentence_type IN ('Confinement', 'Probation')
          AND s.min_days IS NOT NULL
        GROUP BY cc.id, s.sentence_type
        ORDER BY cc.name, s.sentence_type
        """
    ).fetchall()
    return [
        (r["category"], r["sentence_type"], r["n"],
         int(r["avg_min"]), int(r["avg_max"]))
        for r in rows
    ]


def sentence_length_by_judge(conn: sqlite3.Connection, min_cell: int):
    """Average min and max confinement days per sentencing judge
    (charges.disposition_judge_id), cells at or above min_cell. Rows:
    (judge, n, avg_min, avg_max)."""
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
    return [
        (r["judge"], r["n"], int(r["avg_min"]), int(r["avg_max"]))
        for r in rows
    ]


def judge_coverage(conn: sqlite3.Connection):
    """Cases per assigned judge (cases.judge_id), descending. Rows:
    (judge, n)."""
    return conn.execute(
        """
        SELECT j.name_normalized AS judge, count(*) AS n
        FROM cases c
        JOIN judges j ON c.judge_id = j.id
        GROUP BY j.id
        ORDER BY n DESC, j.name_normalized
        """
    ).fetchall()


def thin_cells(conn: sqlite3.Connection, min_cell: int):
    """Category by assigned judge (cases.judge_id) counts at or above
    min_cell, the judge-signal readiness view. Rows: (category, judge, n)."""
    return conn.execute(
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


def time_to_disposition_by_category(conn: sqlite3.Connection):
    """Average filing-to-disposition days by category, over charges with both
    a filed_date and a disposition_date. Survivorship-biased raw average, not
    the phase 5 output. Rows: (category, avg_days, n)."""
    rows = conn.execute(
        """
        SELECT cc.name AS category,
               round(avg(julianday(ch.disposition_date)
                         - julianday(c.filed_date))) AS avg_days,
               count(*) AS n
        FROM charges ch
        JOIN cases c ON ch.docket_number = c.docket_number
        JOIN charge_categories cc ON ch.category_id = cc.id
        WHERE ch.disposition_date IS NOT NULL
          AND c.filed_date IS NOT NULL
        GROUP BY cc.id
        ORDER BY n DESC, cc.name
        """
    ).fetchall()
    return [(r["category"], int(r["avg_days"]), r["n"]) for r in rows]


def time_to_disposition_by_judge(conn: sqlite3.Connection, min_cell: int):
    """Average filing-to-disposition days by sentencing judge
    (charges.disposition_judge_id), cells at or above min_cell. Same
    survivorship caveat as the by-category cut. Rows: (judge, avg_days, n)."""
    rows = conn.execute(
        """
        SELECT j.name_normalized AS judge,
               round(avg(julianday(ch.disposition_date)
                         - julianday(c.filed_date))) AS avg_days,
               count(*) AS n
        FROM charges ch
        JOIN cases c ON ch.docket_number = c.docket_number
        JOIN judges j ON ch.disposition_judge_id = j.id
        WHERE ch.disposition_date IS NOT NULL
          AND c.filed_date IS NOT NULL
        GROUP BY j.id
        HAVING n >= ?
        ORDER BY n DESC, j.name_normalized
        """,
        (min_cell,),
    ).fetchall()
    return [(r["judge"], int(r["avg_days"]), r["n"]) for r in rows]
