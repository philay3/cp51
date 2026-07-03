"""Build the human audit pack: 10 stratified dockets with every extracted
field laid out for side-by-side checking against the PDFs. Contains no
names; the defendant appears only as a truncated hash."""

from __future__ import annotations

import json

from src.config import INTERIM_DIR

AUDIT_DOCKETS = [
    "CP-51-CR-0000063-2024",
    "CP-51-CR-0005412-2023",
    "CP-51-CR-0003972-2019",
    "CP-51-CR-0003400-2022",
    "CP-51-CR-0002515-2025",
    "CP-51-CR-0000267-2021",
    "CP-51-CR-0000871-2019",
    "CP-51-CR-0001746-2022",
    "CP-51-CR-0004427-2025",
    "CP-51-CR-0003030-2020",
]

HEADER = """# CP51 parser audit pack

Owner instructions: for each docket below, open the matching PDF at
data/raw/{docket}.pdf side by side with this file. Check every field line
against the PDF. If a line is wrong, change its [ ] to [x] and write the
correct value after it. Expect roughly 6 minutes per docket. When done,
report only the [x] lines (docket, field, correct value). Do not paste any
names anywhere.
"""


def line(label: str, value) -> str:
    shown = value if value not in (None, [], "") else "(null)"
    return f"- [ ] {label}: {shown}\n"


def main() -> None:
    out = [HEADER]
    audit_dir = INTERIM_DIR / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    for docket in AUDIT_DOCKETS:
        path = INTERIM_DIR / f"{docket}.json"
        if not path.exists():
            out.append(f"\n## {docket}\n\nNOT PARSED, see raw_dockets.notes\n")
            continue
        rec = json.loads(path.read_text())
        case = rec["case"]
        out.append(f"\n## {docket}\n\n")
        out.append(line("case_status", case["case_status"]))
        out.append(line("filed_date", case["filed_date"]))
        out.append(line("otn", case["otn"]))
        out.append(line("assigned_judge_raw", case["assigned_judge_raw"]))
        out.append(line("defendant_hash (first 8)",
                        (case["defendant_hash"] or "")[:8]))
        for c in rec["charges"]:
            out.append(f"\n### charge seq {c['sequence']}\n")
            out.append(line("statute", c["statute"]))
            out.append(line("grade", c["grade"]))
            out.append(line("offense", c["offense"]))
            out.append(line("disposition_raw", c["disposition_raw"]))
            out.append(line("disposition_date", c["disposition_date"]))
            out.append(line("disposition_judge_raw", c["disposition_judge_raw"]))
            for i, s in enumerate(c["sentences"], 1):
                out.append(line(f"sentence {i} type", s["sentence_type"]))
                out.append(line(f"sentence {i} min_days", s["min_days"]))
                out.append(line(f"sentence {i} max_days", s["max_days"]))
                out.append(line(f"sentence {i} date", s["sentence_date"]))
    (audit_dir / "audit_pack.md").write_text("".join(out))
    print(f"audit pack written: {audit_dir / 'audit_pack.md'}")


if __name__ == "__main__":
    main()
