"""
Read-only static HTML dashboard for the CP51 corpus.

This script queries the database read-only (mode=ro, SELECT only, via
src.analysis.corpus_queries) and writes one self-contained HTML file to
data/interim/dashboard.html. It contacts no portal, writes nothing to the
database, and makes no schema change. The output file embeds every chart as
a base64 PNG, so it references no external URL and opens with no internet
connection: no CDN, no external script, no external font.

Privacy: the dashboard shows only name-free data (counts, judge
name_normalized values which are public officials, category and disposition
labels, sentence lengths in days, dates). It never joins to or reads the
defendants table and never renders a defendant id or a case caption.

Sentence lengths are already stored in days (day=1, month=30, year=360
applied at parse time), so no conversion happens here. The sentencing judge
(charges.disposition_judge_id) and the assigned judge (cases.judge_id) are
kept distinct and labeled as such.

Usage (read-only, no portal contact):
  PYTHONPATH=. .venv/bin/python scripts/dashboard.py
  PYTHONPATH=. .venv/bin/python scripts/dashboard.py --min-cell 10
"""

from __future__ import annotations

import argparse
import base64
import html
import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # headless, no display, no external resource
import matplotlib.pyplot as plt  # noqa: E402

from src.analysis import corpus_queries as q  # noqa: E402
from src.config import INTERIM_DIR  # noqa: E402

OUTPUT_PATH = INTERIM_DIR / "dashboard.html"

# Fixed bucket order for the outcome-mix panel, so every category stacks in
# the same order and the non-sentence bucket lands last.
BUCKET_ORDER = [
    "Confinement",
    "Probation",
    "No Further Penalty",
    "ARD",
    "Fines and Costs",
    "No sentence (disposition only)",
]

# A stable, colorblind-safe-ish palette for the stacked bars.
BUCKET_COLORS = {
    "Confinement": "#b2182b",
    "Probation": "#2166ac",
    "No Further Penalty": "#7fbf7b",
    "ARD": "#f4a582",
    "Fines and Costs": "#d6a5c9",
    "No sentence (disposition only)": "#bdbdbd",
}


# -- small rendering helpers -------------------------------------------------

def esc(value) -> str:
    return html.escape(str(value))


def fig_to_img(fig) -> str:
    """Serialize a matplotlib figure to a base64 PNG <img> tag and close it,
    so the chart travels inside the HTML with no external reference."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f'<img alt="chart" src="data:image/png;base64,{encoded}">'


def empty_note(message: str = "no data yet") -> str:
    return f'<p class="empty">{esc(message)}</p>'


def table(headers, rows) -> str:
    """Render a simple HTML table. Numeric-looking cells are right aligned by
    the stylesheet class on their header position is not tracked, so we keep
    it plain and readable."""
    if not rows:
        return empty_note()
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def panel(title: str, body: str, caption: str = "") -> str:
    cap = f'<p class="caption">{esc(caption)}</p>' if caption else ""
    return f'<section class="panel"><h2>{esc(title)}</h2>{cap}{body}</section>'


# -- panels ------------------------------------------------------------------

def panel_progress(conn) -> str:
    t = q.corpus_totals(conn)
    complete = t["weeks_complete"]
    total = t["total_weeks"]
    pct = (complete / total * 100) if total else 0

    fig, ax = plt.subplots(figsize=(7, 0.9))
    ax.barh([0], [total], color="#e6e6e6")
    ax.barh([0], [complete], color="#2166ac")
    ax.set_xlim(0, total)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xlabel("weeks harvested out of 183")
    ax.text(total / 2, 0,
            f"{complete} of {total} weeks complete ({pct:.1f} percent)",
            ha="center", va="center", fontsize=10)
    img = fig_to_img(fig)

    rows = [
        ("cases", t["cases"]),
        ("charges", t["charges"]),
        ("sentences", t["sentences"]),
        ("judges", t["judges"]),
        ("weeks touched", t["weeks_touched"]),
        ("weeks complete", complete),
        ("weeks total", total),
        ("CP-51-CR rows seen", t["cp_rows_seen"]),
    ]
    return panel("1. Collection progress",
                 img + table(("metric", "count"), rows))


def panel_category(conn) -> str:
    rows = q.category_distribution(conn)
    if not rows:
        return panel("2. Category distribution", empty_note())
    labels = [r["category"] for r in rows]
    values = [r["n"] for r in rows]

    fig, ax = plt.subplots(figsize=(7, max(2.5, 0.4 * len(labels))))
    ax.barh(labels, values, color="#2166ac")
    ax.invert_yaxis()  # largest at the top
    ax.set_xlabel("charges")
    img = fig_to_img(fig)
    return panel("2. Category distribution",
                 img + table(("category", "charges"),
                             [(r["category"], r["n"]) for r in rows]))


def panel_disposition(conn) -> str:
    rows = q.disposition_breakdown(conn)
    if not rows:
        return panel("3. Disposition breakdown", empty_note())
    total = sum(n for _, n in rows)
    labels = [d for d, _ in rows]
    values = [n for _, n in rows]

    fig, ax = plt.subplots(figsize=(7, max(2.5, 0.4 * len(labels))))
    ax.barh(labels, values, color="#5aae61")
    ax.invert_yaxis()
    ax.set_xlabel("charges")
    img = fig_to_img(fig)

    table_rows = [
        (d, n, f"{(n / total * 100):.1f} percent" if total else "0")
        for d, n in rows
    ]
    return panel("3. Disposition breakdown",
                 img + table(("disposition", "charges", "share"), table_rows),
                 "Null disposition_category is bucketed as open charges.")


def panel_outcome_mix(conn) -> str:
    rows = q.outcome_mix(conn)
    if not rows:
        return panel("4. Outcome mix per charge category", empty_note())

    # Pivot into {category: {bucket: n}}.
    by_cat: dict = {}
    for r in rows:
        by_cat.setdefault(r["category"], {})[r["bucket"]] = r["n"]

    # Order categories by total volume, descending.
    categories = sorted(by_cat, key=lambda c: sum(by_cat[c].values()),
                        reverse=True)

    fig, ax = plt.subplots(figsize=(8, max(2.5, 0.5 * len(categories))))
    left = [0.0] * len(categories)
    for bucket in BUCKET_ORDER:
        shares = []
        for i, cat in enumerate(categories):
            total = sum(by_cat[cat].values()) or 1
            shares.append(by_cat[cat].get(bucket, 0) / total)
        ax.barh(range(len(categories)), shares, left=left,
                color=BUCKET_COLORS[bucket], label=bucket)
        left = [a + b for a, b in zip(left, shares)]
    ax.set_yticks(range(len(categories)))
    ax.set_yticklabels(categories)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("share of outcomes")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15),
              ncol=3, fontsize=8, frameon=False)
    img = fig_to_img(fig)

    # Underlying counts table: category, then a count per bucket, then total.
    headers = ["category"] + BUCKET_ORDER + ["total"]
    table_rows = []
    for cat in categories:
        counts = [by_cat[cat].get(b, 0) for b in BUCKET_ORDER]
        table_rows.append([cat] + counts + [sum(by_cat[cat].values())])
    caption = ("Shares of outcomes per category. Sentence-type counts are per "
               "sentence component (a charge can carry more than one). The "
               "non-sentence bucket counts charges with no sentence row.")
    return panel("4. Outcome mix per charge category",
                 img + table(headers, table_rows), caption)


def panel_length_by_type(conn) -> str:
    rows = q.sentence_length_by_type(conn)
    caption = ("Only Confinement and Probation carry a length. ARD, No "
               "Further Penalty, and Fines and Costs have no length, so they "
               "appear in panel 4 but not here.")
    if not rows:
        return panel("5. Sentence length by type", empty_note(), caption)

    # Grouped bar of avg min days by category, one bar per sentence type.
    cats = sorted({r[0] for r in rows})
    types = [t for t in q.LENGTH_TYPES if any(r[1] == t for r in rows)]
    lookup = {(r[0], r[1]): r for r in rows}
    fig, ax = plt.subplots(figsize=(8, max(2.5, 0.5 * len(cats))))
    bar_h = 0.8 / max(1, len(types))
    colors = {"Confinement": "#b2182b", "Probation": "#2166ac"}
    for ti, stype in enumerate(types):
        ys = [i + ti * bar_h for i in range(len(cats))]
        vals = [lookup.get((c, stype), (0, 0, 0, 0, 0))[3] for c in cats]
        ax.barh(ys, vals, height=bar_h, color=colors.get(stype, "#888888"),
                label=stype)
    ax.set_yticks([i + bar_h * (len(types) - 1) / 2 for i in range(len(cats))])
    ax.set_yticklabels(cats)
    ax.invert_yaxis()
    ax.set_xlabel("average minimum days")
    ax.legend(fontsize=8, frameon=False)
    img = fig_to_img(fig)

    table_rows = [
        (cat, stype, n, avg_min, avg_max)
        for (cat, stype, n, avg_min, avg_max) in rows
    ]
    return panel(
        "5. Sentence length by type",
        img + table(("category", "sentence type", "n",
                     "avg min days", "avg max days"), table_rows),
        caption)


def panel_length_by_judge(conn, min_cell: int) -> str:
    rows = q.sentence_length_by_judge(conn, min_cell)
    caption = (f"Confinement only, sentencing judge "
               f"(charges.disposition_judge_id), cells at or above {min_cell}.")
    if not rows:
        return panel("6. Sentence length by judge", empty_note(), caption)
    table_rows = [
        (judge, n, avg_min, avg_max)
        for (judge, n, avg_min, avg_max) in rows
    ]
    return panel(
        "6. Sentence length by judge",
        table(("judge (sentencing)", "n", "avg min days", "avg max days"),
              table_rows),
        caption)


def panel_judge_coverage(conn) -> str:
    rows = q.judge_coverage(conn)
    if not rows:
        return panel("7. Judge coverage", empty_note())
    labels = [r["judge"] for r in rows]
    values = [r["n"] for r in rows]
    fig, ax = plt.subplots(figsize=(8, max(2.5, 0.35 * len(labels))))
    ax.barh(labels, values, color="#762a83")
    ax.invert_yaxis()
    ax.set_xlabel("cases (assigned judge)")
    img = fig_to_img(fig)
    return panel(
        "7. Judge coverage",
        img + table(("judge (assigned)", "cases"),
                    [(r["judge"], r["n"]) for r in rows]),
        "Assigned judge (cases.judge_id), descending.")


def panel_thin_cells(conn, min_cell: int) -> str:
    rows = q.thin_cells(conn, min_cell)
    caption = (f"Category by assigned judge (cases.judge_id), cells at or "
               f"above {min_cell}. The phase 5 judge-signal readiness gauge.")
    if not rows:
        return panel("8. Thin-cell judge-signal readiness",
                     empty_note(), caption)
    body = (f'<p class="figure">{len(rows)} category-by-judge cells at or '
            f'above {min_cell}.</p>')
    body += table(("category", "judge (assigned)", "charges"),
                  [(r["category"], r["judge"], r["n"]) for r in rows])
    return panel("8. Thin-cell judge-signal readiness", body, caption)


def panel_time_to_disposition(conn, min_cell: int) -> str:
    by_cat = q.time_to_disposition_by_category(conn)
    by_judge = q.time_to_disposition_by_judge(conn, min_cell)
    caption = ("Survivorship-biased raw averages of filing-to-disposition "
               "days, not the phase 5 output. Only charges with both a filed "
               "date and a disposition date are counted.")
    cat_body = ('<h3>By category</h3>'
                + (table(("category", "avg days", "n"),
                         [(c, d, n) for (c, d, n) in by_cat])
                   if by_cat else empty_note()))
    judge_body = (f'<h3>By sentencing judge, cells at or above {min_cell}</h3>'
                  + (table(("judge (sentencing)", "avg days", "n"),
                           [(j, d, n) for (j, d, n) in by_judge])
                     if by_judge else empty_note()))
    return panel("9. Time to disposition", cat_body + judge_body, caption)


# -- page assembly -----------------------------------------------------------

STYLE = """
body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial,
       sans-serif; margin: 0; padding: 0 24px 48px; color: #1a1a1a;
       background: #fafafa; }
header { padding: 24px 0 8px; border-bottom: 2px solid #ddd;
         margin-bottom: 8px; }
h1 { margin: 0 0 4px; font-size: 22px; }
.subtle { color: #555; font-size: 13px; margin: 2px 0; }
.panel { background: #fff; border: 1px solid #e2e2e2; border-radius: 8px;
         padding: 16px 20px; margin: 18px 0; }
.panel h2 { font-size: 17px; margin: 0 0 8px; }
.panel h3 { font-size: 14px; margin: 14px 0 4px; }
.caption { color: #666; font-size: 12px; margin: 0 0 10px; font-style: italic; }
.figure { color: #333; font-size: 13px; margin: 4px 0; }
.empty { color: #999; font-style: italic; }
img { max-width: 100%; height: auto; display: block; margin: 6px 0 12px; }
table { border-collapse: collapse; font-size: 13px; margin: 6px 0; }
th, td { border: 1px solid #e2e2e2; padding: 4px 10px; text-align: left; }
th { background: #f0f0f0; }
"""


def build_page(conn, min_cell: int) -> str:
    t = q.corpus_totals(conn)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = (
        "<header>"
        "<h1>CP51 corpus dashboard</h1>"
        f'<p class="subtle">Generated {esc(generated)}. Read-only view, '
        "no defendant data.</p>"
        f'<p class="subtle">Corpus: {t["cases"]} cases, {t["charges"]} '
        f'charges, {t["sentences"]} sentences, {t["judges"]} judges. '
        f'{t["weeks_complete"]} of {t["total_weeks"]} weeks complete.</p>'
        "</header>"
    )
    panels = [
        panel_progress(conn),
        panel_category(conn),
        panel_disposition(conn),
        panel_outcome_mix(conn),
        panel_length_by_type(conn),
        panel_length_by_judge(conn, min_cell),
        panel_judge_coverage(conn),
        panel_thin_cells(conn, min_cell),
        panel_time_to_disposition(conn, min_cell),
    ]
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, "
        "initial-scale=1\">"
        "<title>CP51 corpus dashboard</title>"
        f"<style>{STYLE}</style></head><body>"
        + header + "".join(panels) + "</body></html>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only static HTML dashboard for the CP51 corpus.")
    parser.add_argument(
        "--min-cell", type=int, default=q.MIN_CELL,
        help=f"threshold for per-judge and thin-cell panels "
             f"(default {q.MIN_CELL})")
    args = parser.parse_args()

    conn = q.connect_readonly()
    try:
        page = build_page(conn, args.min_cell)
    finally:
        conn.close()

    OUTPUT_PATH.write_text(page, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
