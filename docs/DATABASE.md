# Database

> Status: target design, authoritative. This document defines **schema v2**,
> which supersedes the schema in the build spec (v1). Apply the delta at the
> bottom to `src/db/schema.py` during phase 1, before the first `init_db`, so
> the database is never created on the old shape. Last updated 2026-07-02.

## Grain and shape

The analytical unit is the **charge**, not the case, because one case carries
several charges that can each resolve differently, and both the trial penalty
and the judge analysis need that granularity. Cases group charges. Sentences
attach to charges, one to many, because a single charge routinely carries
multiple sentence components (confinement plus a consecutive probation tail).
Judges are a first class entity so that name variants resolve to one identity
and model estimates can attach to it. Defendants exist only as salted hashes.

```
 judges 1──* cases 1──* charges *──1 charge_categories
                │           │
                │           1
 defendants 1──*            │
                            *
                        sentences          raw_dockets (pipeline ledger)
```

## Tables

### judges

One row per resolved judge identity. Raw name variants live on a separate
alias table so "Example, A.", "A. Example", and "Judge Anne Example" all point
to one judge.

| column | type | notes |
|---|---|---|
| id | int PK | |
| name_normalized | str(200), unique, indexed | canonical "Last, First M." |
| slug | str(80), unique | URL identity for the API, e.g. `example-a` |
| first_seen | date, null | earliest sentence date observed |
| last_seen | date, null | latest sentence date observed |

### judge_aliases

| column | type | notes |
|---|---|---|
| id | int PK | |
| judge_id | FK judges.id | |
| name_raw | str(200), unique, indexed | exactly as printed on a docket |

Resolution algorithm (runs in the loader): exact match on a known alias wins;
otherwise merge unambiguous initial-form variants of an existing normalized
name; otherwise create a new judge and alias. A small manual override map in
`data/lookups/judge_overrides.yaml` settles the genuinely ambiguous cases and
is versioned in git. This mirrors the alias playbook proven by comparable
sites for attorney names and is the foundation the judge model rests on.

### defendants

Pseudonymous by construction. No names, no dates of birth, no attributes in
v2. The id is `sha256(DEFENDANT_HASH_SALT + normalized_name + year_of_birth)`;
name and DOB are read from the docket, hashed, and discarded in memory.

| column | type | notes |
|---|---|---|
| id | str(64) PK | the salted hash |

Future column, not yet added: `prior_record_context`, populated if Court
Summary reports are ever parsed (ROADMAP, parked).

### cases

One row per docket.

| column | type | notes |
|---|---|---|
| docket_number | str(40) PK | `CP-51-CR-#######-YYYY` |
| county | str(40) | default Philadelphia |
| court_type | str(40) | Common Pleas or Municipal Court (D-18) |
| case_status | str(40), null | Closed, Active, etc., raw |
| filed_date | date, null | |
| otn | str(40), null | offense tracking number |
| dc_number | str(40), null | District Control Number, from the Case Local Number(s) table; with otn, keys consolidated sibling groups (D-18). Added in Phase 7 |
| judge_id | FK judges.id, null | **the sentencing judge**: modal judge across this case's sentenced charges. Convenience denormalization; charge-level truth lives on charges.disposition_judge_id |
| assigned_judge_raw | text, null | the "Judge Assigned" string from the case header, raw only, kept for assignment analysis |
| defendant_id | FK defendants.id, null | |
| source_url | text, null | |
| scraped_at | datetime | server default now |

### charge_categories

The plain-language taxonomy. Defendants search "drug possession", not a
statute cite, so every charge maps to one category. The statute-to-category
rules live in `data/lookups/charge_categories.yaml`, versioned in git, applied
at load time. Unmapped statutes go to `other` and the share of `other` is
tracked honestly (METHODOLOGY.md).

| column | type | notes |
|---|---|---|
| id | int PK | |
| slug | str(60), unique | e.g. `drug-possession` |
| name | str(120) | e.g. Drug Possession |

Initial category set (extend as data demands): drug possession, drug delivery
(PWID), DUI, simple assault, aggravated assault, robbery, burglary, theft,
retail theft, firearms (VUFA), criminal trespass, terroristic threats, fraud
and forgery, sexual offenses, homicide, other.

### charges

One row per charge on a docket.

| column | type | notes |
|---|---|---|
| id | int PK | |
| docket_number | FK cases.docket_number | |
| sequence | int, null | as printed |
| statute | str(60), null | e.g. `35 § 780-113 §§ A16` as printed |
| grade | str(10), null | F1, F2, F3, M1, M2, M3, S, or blank |
| offense | text, null | statute description as printed |
| category_id | FK charge_categories.id, null | derived at load |
| disposition_raw | str(120), null | exactly as printed, never overwritten |
| disposition_category | str(30), null | derived at load, see mapping below |
| disposition_date | date, null | |
| disposition_judge_id | FK judges.id, null | the sentencing judge named on this charge's disposition event |

`disposition_category` values and the mapping from raw PA disposition text
(maintained in `data/lookups/disposition_map.yaml`, versioned):

| category | raw examples |
|---|---|
| dismissed | Nolle Prossed, Withdrawn, Dismissed, Quashed, Dismissed LOP |
| diversion | ARD, ARD - County, Probation Without Verdict, other program dispositions |
| plea | Guilty Plea - Negotiated, Guilty Plea - Non-Negotiated, Nolo Contendere |
| trial_convicted | Guilty (bench or jury verdict) |
| trial_acquitted | Not Guilty |
| other | Transferred, Mistrial, Moved to Inactive, anything unmapped |

Charges on open cases keep a null category and are excluded from all outcome
denominators (METHODOLOGY.md).

### sentences

One row per sentence **component**. One charge, many components: a charge can
carry confinement plus consecutive probation plus a fine, each its own row.

| column | type | notes |
|---|---|---|
| id | int PK | |
| charge_id | FK charges.id | one to many |
| sentence_type | str(80), null | Confinement, Probation, IPP, No Further Penalty, Fines and Costs, raw normalized lightly |
| min_days | int, null | PA sentences are indeterminate min-max ranges |
| max_days | int, null | |
| program | str(120), null | program or condition text if printed |
| sentence_date | date, null | |
| raw_text | text, null | the component as printed, for audit |

### raw_dockets

The pipeline ledger, unchanged from v1: fetch and parse tracking so every
stage is reproducible and idempotent.

| column | type | notes |
|---|---|---|
| docket_number | str(40) PK | |
| pdf_path | text, null | |
| fetched_at | datetime, null | |
| parse_status | str(20) | pending, parsed, failed, not_found |
| notes | text, null | |

## Privacy model

Three rules, enforced by shape rather than discipline:

1. **No names in the database.** Defendant names and DOBs are hashed in memory
   at load and never written anywhere: not to tables, logs, interim JSON,
   fixtures, or commit messages. Interim parse JSON stores the hash, not the
   name, so `data/interim/` is as clean as the database.
2. **Aggregates only in public.** The database holds docket numbers because
   the pipeline needs them, but the stats release (the only artifact the
   serving layer sees) contains no docket numbers, no case-level rows, and
   nothing about any individual. See DECISIONS.md D-05.
3. **Judges are the named entities.** Judges are public officials acting in a
   public role; they are named, but only ever next to numbers that clear the
   thresholds in METHODOLOGY.md.

## Example rows (synthetic)

The docket number below is a synthetic placeholder (sequence 0000000 is never
issued) and the judge is fictional.

```
cases:      CP-51-CR-0000000-2024 | Philadelphia | Common Pleas | Closed | 2024-03-14 | judge_id=1
charges:    id=1 | CP-51-CR-0000000-2024 | seq=1 | 35 § 780-113 §§ A16 | M | Int Poss Contr Subst
            | category=drug-possession | disposition_raw="Guilty Plea - Negotiated" | plea | 2024-09-02 | disposition_judge_id=1
sentences:  id=1 | charge_id=1 | Probation | min=365 | max=365 | 2024-09-02
judges:     id=1 | "Example, Anne" | slug=example-a
```

## Migration posture

No migrations framework yet. Until real data exists, schema changes are made
by editing `src/db/schema.py` and re-initializing. Alembic is adopted at the
same moment as Postgres (DECISIONS.md D-08).

## Delta from build spec v1

Apply these edits to `src/db/schema.py` in phase 1:

1. `Sentence.charge` relationship: remove `uselist=False`; a charge now has
   `sentences: list[Sentence]`. Add `raw_text` column.
2. `Charge`: rename `disposition` to `disposition_raw`; add
   `disposition_category`, `category_id` (FK charge_categories), and
   `disposition_judge_id` (FK judges).
3. New table `charge_categories`.
4. New table `judge_aliases`; `judges` gains `slug`, `first_seen`,
   `last_seen`; `name_raw` moves to the alias table and `name_normalized`
   becomes unique and non-null.
5. `Case`: add `assigned_judge_raw`; document `judge_id` as the sentencing
   judge.
6. `Defendant`: unchanged (hash-only), with the future prior-record column
   noted in a comment only.