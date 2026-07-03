"""
Loader: interim JSON records into the database.

Idempotent by construction: each docket is delete-and-replace at the case
grain (ORM cascades remove its charges and sentences), while judges,
defendants, and categories are upserts that are never deleted. Running the
loader twice produces identical row counts.

Console output prints only whitelisted values: docket numbers, counts,
judge names (public officials), disposition strings, statutes, and hashes.
Interim JSON is guaranteed name-free by the parser's privacy assertion.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date

import yaml

from src.config import INTERIM_DIR, LOOKUPS_DIR
from src.db.schema import (
    Case,
    Charge,
    ChargeCategory,
    Defendant,
    Judge,
    JudgeAlias,
    Sentence,
)
from src.db.session import SessionLocal, init_db


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown"


def iso(text):
    return date.fromisoformat(text) if text else None


def load_lookups() -> dict:
    dispo = yaml.safe_load((LOOKUPS_DIR / "disposition_map.yaml").read_text())
    cats = yaml.safe_load((LOOKUPS_DIR / "charge_categories.yaml").read_text())
    overrides = yaml.safe_load((LOOKUPS_DIR / "judge_overrides.yaml").read_text())
    statute_map = cats.get("statute_map") or {}
    return {
        "dispo_map": {collapse_ws(k): v for k, v in (dispo.get("map") or {}).items()},
        "categories": cats.get("categories") or [],
        "statute_exact": statute_map.get("exact") or {},
        "statute_prefix": statute_map.get("prefix") or {},
        "judge_overrides": overrides.get("overrides") or {},
    }


def categorize_statute(statute, exact: dict, prefix: dict) -> str:
    """Exact statute string wins, then the longest matching prefix, else other."""
    if not statute:
        return "other"
    s = collapse_ws(statute)
    if s in exact:
        return exact[s]
    best, best_cat = "", "other"
    for p, cat in prefix.items():
        if s.startswith(p) and len(p) > len(best):
            best, best_cat = p, cat
    return best_cat


class JudgeResolver:
    """Raw sentencing-judge string to one Judge identity.

    Resolution order: exact alias, owner override map, exact match on an
    existing normalized name, conservative initial-form merge (the raw uses
    a bare initial and exactly one existing judge shares surname plus first
    initial), else a new judge. Every resolved raw gains an alias row.
    """

    def __init__(self, session, overrides: dict):
        self.session = session
        self.overrides = {collapse_ws(k): collapse_ws(v)
                          for k, v in overrides.items()}

    def _get_or_create(self, normalized: str) -> Judge:
        judge = (self.session.query(Judge)
                 .filter_by(name_normalized=normalized).one_or_none())
        if judge is None:
            judge = Judge(name_normalized=normalized, slug=slugify(normalized))
            self.session.add(judge)
            self.session.flush()
        return judge

    def _initial_match(self, raw: str):
        m = re.match(r"^([^,]+),\s*([A-Za-z])\.?$", raw)
        if not m:
            return None
        surname = m.group(1).strip().lower()
        initial = m.group(2).lower()
        candidates = []
        for judge in self.session.query(Judge).all():
            parts = judge.name_normalized.split(",")
            if len(parts) < 2:
                continue
            if (parts[0].strip().lower() == surname
                    and parts[1].strip().lower().startswith(initial)):
                candidates.append(judge)
        return candidates[0] if len(candidates) == 1 else None

    def resolve(self, raw: str) -> Judge:
        raw = collapse_ws(raw)
        alias = (self.session.query(JudgeAlias)
                 .filter_by(name_raw=raw).one_or_none())
        if alias:
            return alias.judge
        if raw in self.overrides:
            judge = self._get_or_create(self.overrides[raw])
        else:
            judge = (self.session.query(Judge)
                     .filter_by(name_normalized=raw).one_or_none())
            if judge is None:
                judge = self._initial_match(raw)
            if judge is None:
                judge = self._get_or_create(raw)
        self.session.add(JudgeAlias(judge_id=judge.id, name_raw=raw))
        self.session.flush()
        return judge


def touch_seen(judge: Judge, d) -> None:
    if d is None:
        return
    if judge.first_seen is None or d < judge.first_seen:
        judge.first_seen = d
    if judge.last_seen is None or d > judge.last_seen:
        judge.last_seen = d


def upsert_categories(session, categories) -> dict:
    ids = {}
    for c in categories:
        row = (session.query(ChargeCategory)
               .filter_by(slug=c["slug"]).one_or_none())
        if row is None:
            row = ChargeCategory(slug=c["slug"], name=c["name"])
            session.add(row)
            session.flush()
        ids[row.slug] = row.id
    return ids


def load_record(session, record, lookups, cat_ids, resolver, stats) -> None:
    docket = record["docket_number"]
    existing = session.get(Case, docket)
    if existing:
        session.delete(existing)
        session.flush()

    case_data = record["case"]
    d_hash = case_data.get("defendant_hash")
    if d_hash:
        session.merge(Defendant(id=d_hash))

    case = Case(
        docket_number=docket,
        county=case_data.get("county") or "Philadelphia",
        court_type=case_data.get("court_type") or "Common Pleas",
        case_status=case_data.get("case_status"),
        filed_date=iso(case_data.get("filed_date")),
        otn=case_data.get("otn"),
        assigned_judge_raw=case_data.get("assigned_judge_raw"),
        defendant_id=d_hash,
    )
    session.add(case)

    judge_tally: Counter = Counter()
    for c in record["charges"]:
        raw_dispo = c.get("disposition_raw")
        if raw_dispo is None:
            dispo_cat = None
            stats["dispo_null"] += 1
        else:
            key = collapse_ws(raw_dispo)
            dispo_cat = lookups["dispo_map"].get(key)
            if dispo_cat is None:
                dispo_cat = "other"
                stats["dispo_other"] += 1
                stats[f"unmapped::{key}"] += 1
            else:
                stats["dispo_mapped"] += 1

        cat_slug = categorize_statute(c.get("statute"),
                                      lookups["statute_exact"],
                                      lookups["statute_prefix"])

        judge_id = None
        j_raw = c.get("disposition_judge_raw")
        if j_raw:
            judge = resolver.resolve(j_raw)
            judge_id = judge.id
            judge_tally[judge_id] += 1
            touch_seen(judge, iso(c.get("disposition_date")))

        charge = Charge(
            docket_number=docket,
            sequence=c.get("sequence"),
            statute=c.get("statute"),
            grade=c.get("grade"),
            offense=c.get("offense"),
            category_id=cat_ids.get(cat_slug),
            disposition_raw=raw_dispo,
            disposition_category=dispo_cat,
            disposition_date=iso(c.get("disposition_date")),
            disposition_judge_id=judge_id,
        )
        for s in c.get("sentences", []):
            charge.sentences.append(Sentence(
                sentence_type=s.get("sentence_type"),
                min_days=s.get("min_days"),
                max_days=s.get("max_days"),
                program=s.get("program"),
                sentence_date=iso(s.get("sentence_date")),
                raw_text=s.get("raw_text"),
            ))
            stats["sentences"] += 1
        case.charges.append(charge)
        stats["charges"] += 1
        stats[f"cat::{cat_slug}"] += 1

    if judge_tally:
        case.judge_id = judge_tally.most_common(1)[0][0]
    stats["cases"] += 1


def main() -> None:
    init_db()
    session = SessionLocal()
    lookups = load_lookups()
    cat_ids = upsert_categories(session, lookups["categories"])
    resolver = JudgeResolver(session, lookups["judge_overrides"])
    stats: Counter = Counter()

    files = sorted(INTERIM_DIR.glob("CP-*.json"))
    for f in files:
        record = json.loads(f.read_text())
        load_record(session, record, lookups, cat_ids, resolver, stats)
        session.commit()

    non_null = stats["dispo_mapped"] + stats["dispo_other"]
    print(f"loaded: {stats['cases']} cases, {stats['charges']} charges, "
          f"{stats['sentences']} sentence components")
    print(f"judges: {session.query(Judge).count()}, "
          f"defendants: {session.query(Defendant).count()}")
    if non_null:
        pct = 100.0 * stats["dispo_mapped"] / non_null
        print(f"disposition mapping: {stats['dispo_mapped']} of {non_null} "
              f"mapped ({pct:.1f}%), {stats['dispo_other']} to other, "
              f"{stats['dispo_null']} null (open charges)")
    for key in sorted(stats):
        if key.startswith("unmapped::"):
            print(f"  unmapped disposition ({stats[key]}x): "
                  f"{key.split('::', 1)[1]}")
    print("category distribution:")
    for key, n in stats.most_common():
        if key.startswith("cat::"):
            print(f"  {n:>3}  {key.split('::', 1)[1]}")
    session.close()


if __name__ == "__main__":
    main()
