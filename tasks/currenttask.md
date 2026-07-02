# Current task: Phase 1, scaffold CP51

This file is self-contained. Everything needed for this task is here. The
docs/ folder in this repo is content to commit, not required reading. Do not
consult other documents to perform this task.

## Orientation (all the context you need)

CP51 builds a dataset of Philadelphia criminal court outcomes from public
docket sheets, and a forecaster on top of it. This task creates the project
skeleton: directories, config, database schema, seeded lookup files,
environment, and the first commit. No scraping, no parsing, no analysis.

## Ground rules

- **Commands are ask-first.** Per the global rules: present the exact
  command(s) with a one line reason, stop, and wait. Related setup commands
  may be grouped as one logical block per ask. Never assume an outcome you
  have not seen.
- **No em dashes anywhere.** Code, comments, YAML, commit messages, worklog
  entries. Use periods, commas, parentheses, or colons.
- **Already in this folder, do not modify:** README.md, docs/,
  PROJECT-INSTRUCTIONS.md, and this file. worklog.md is where you report,
  append-only, format at the top of that file.
- **The salt.** After copying .env.example to .env, stop there: the owner
  sets DEFENDANT_HASH_SALT personally. Never generate, read, or print it.
  Database initialization does not need it.
- **Scope.** Scaffold only. No acquisition code, no parser code, no contact
  with any court website. Stop at the definition of done.

## Step 1: directory structure

Create inside the current folder (it already contains README.md, docs/, and
the task files):

```bash
mkdir -p data/{raw,interim,processed,lookups} src/{acquire,parse,db,analysis} notebooks scripts tests
touch src/__init__.py src/acquire/__init__.py src/parse/__init__.py src/db/__init__.py src/analysis/__init__.py
```

## Step 2: files to create (exact contents)

### .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/

# Env and secrets
.env

# Data stays local (lookups are the tracked exception)
data/raw/
data/interim/
data/processed/
*.db
*.sqlite

# Notebooks
.ipynb_checkpoints/

# OS
.DS_Store
```

### requirements.txt

PyYAML is included now because the lookup files below are YAML and the
phase 4 loader reads them.

```text
playwright>=1.44
pdfplumber>=0.11
SQLAlchemy>=2.0
pandas>=2.2
python-dotenv>=1.0
tenacity>=8.2
PyYAML>=6.0
```

### .env.example

```text
# Copy to .env and fill in. Never commit .env.
DATABASE_URL=sqlite:///data/processed/phl.db
MIN_DELAY=3
MAX_DELAY=7
DEFENDANT_HASH_SALT=set-a-long-random-string-here
```

### src/config.py

```python
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
LOOKUPS_DIR = DATA_DIR / "lookups"

for d in (RAW_DIR, INTERIM_DIR, PROCESSED_DIR, LOOKUPS_DIR):
    d.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROCESSED_DIR / 'phl.db'}")

# Scrape politeness. Randomized delay between requests, in seconds.
MIN_DELAY = float(os.getenv("MIN_DELAY", "3"))
MAX_DELAY = float(os.getenv("MAX_DELAY", "7"))

# Target scope.
TARGET_COUNTY = "Philadelphia"
TARGET_COURT_TYPE = "Common Pleas"

# Salt for pseudonymous defendant hashing. Set a real value in .env, never commit it.
DEFENDANT_HASH_SALT = os.getenv("DEFENDANT_HASH_SALT", "change-me-in-env")
```

### src/db/schema.py

```python
"""
Database schema for CP51, schema v2.

Authoritative reference: docs/DATABASE.md. Grain:
- cases: one row per docket (one criminal case).
- charges: one row per charge on a docket (a case usually has several).
- sentences: one row per sentence component; a single charge can carry
  several (confinement plus a consecutive probation tail, for example).
- judges and judge_aliases: raw name variants resolve to one identity.
- charge_categories: plain-language taxonomy defendants actually search by.
- defendants: pseudonymous. Names are never stored; only a salted hash.
"""

from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Judge(Base):
    __tablename__ = "judges"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_normalized: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    slug: Mapped[str | None] = mapped_column(String(80), unique=True)
    first_seen: Mapped[date | None] = mapped_column(Date)
    last_seen: Mapped[date | None] = mapped_column(Date)

    aliases: Mapped[list["JudgeAlias"]] = relationship(
        back_populates="judge", cascade="all, delete-orphan"
    )
    cases: Mapped[list["Case"]] = relationship(back_populates="judge")


class JudgeAlias(Base):
    __tablename__ = "judge_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    judge_id: Mapped[int] = mapped_column(ForeignKey("judges.id"))
    name_raw: Mapped[str] = mapped_column(String(200), unique=True, index=True)

    judge: Mapped["Judge"] = relationship(back_populates="aliases")


class Defendant(Base):
    __tablename__ = "defendants"

    # Salted hash of normalized name plus year of birth, never the name.
    # Future column, deliberately not added yet: prior_record_context
    # (requires Court Summary parsing; see docs/ROADMAP.md, parked).
    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    cases: Mapped[list["Case"]] = relationship(back_populates="defendant")


class Case(Base):
    __tablename__ = "cases"

    docket_number: Mapped[str] = mapped_column(String(40), primary_key=True)
    county: Mapped[str] = mapped_column(String(40), default="Philadelphia")
    court_type: Mapped[str] = mapped_column(String(40), default="Common Pleas")
    case_status: Mapped[str | None] = mapped_column(String(40))
    filed_date: Mapped[date | None] = mapped_column(Date)
    otn: Mapped[str | None] = mapped_column(String(40))

    # judge_id is the sentencing judge: the modal judge across this case's
    # sentenced charges. Charge-level truth is charges.disposition_judge_id.
    judge_id: Mapped[int | None] = mapped_column(ForeignKey("judges.id"))
    # The "Judge Assigned" string from the case header, kept raw only.
    assigned_judge_raw: Mapped[str | None] = mapped_column(Text)
    defendant_id: Mapped[str | None] = mapped_column(ForeignKey("defendants.id"))

    source_url: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    judge: Mapped["Judge | None"] = relationship(back_populates="cases")
    defendant: Mapped["Defendant | None"] = relationship(back_populates="cases")
    charges: Mapped[list["Charge"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class ChargeCategory(Base):
    __tablename__ = "charge_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))

    charges: Mapped[list["Charge"]] = relationship(back_populates="category")


class Charge(Base):
    __tablename__ = "charges"

    id: Mapped[int] = mapped_column(primary_key=True)
    docket_number: Mapped[str] = mapped_column(ForeignKey("cases.docket_number"))
    sequence: Mapped[int | None] = mapped_column(Integer)
    statute: Mapped[str | None] = mapped_column(String(60))
    grade: Mapped[str | None] = mapped_column(String(10))  # F1..F3, M1..M3, S
    offense: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("charge_categories.id"))

    disposition_raw: Mapped[str | None] = mapped_column(String(120))
    # Derived at load time from data/lookups/disposition_map.yaml:
    # dismissed, diversion, plea, trial_convicted, trial_acquitted, other.
    disposition_category: Mapped[str | None] = mapped_column(String(30))
    disposition_date: Mapped[date | None] = mapped_column(Date)
    disposition_judge_id: Mapped[int | None] = mapped_column(ForeignKey("judges.id"))

    case: Mapped["Case"] = relationship(back_populates="charges")
    category: Mapped["ChargeCategory | None"] = relationship(back_populates="charges")
    disposition_judge: Mapped["Judge | None"] = relationship(
        foreign_keys=[disposition_judge_id]
    )
    sentences: Mapped[list["Sentence"]] = relationship(
        back_populates="charge", cascade="all, delete-orphan"
    )


class Sentence(Base):
    __tablename__ = "sentences"

    # One row per sentence component, one to many with charges.
    id: Mapped[int] = mapped_column(primary_key=True)
    charge_id: Mapped[int] = mapped_column(ForeignKey("charges.id"))
    sentence_type: Mapped[str | None] = mapped_column(String(80))
    min_days: Mapped[int | None] = mapped_column(Integer)  # PA min-max ranges
    max_days: Mapped[int | None] = mapped_column(Integer)
    program: Mapped[str | None] = mapped_column(String(120))
    sentence_date: Mapped[date | None] = mapped_column(Date)
    raw_text: Mapped[str | None] = mapped_column(Text)  # component as printed

    charge: Mapped["Charge"] = relationship(back_populates="sentences")


class RawDocket(Base):
    """Fetch and parse tracking, so the pipeline is reproducible and idempotent."""
    __tablename__ = "raw_dockets"

    docket_number: Mapped[str] = mapped_column(String(40), primary_key=True)
    pdf_path: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    parse_status: Mapped[str] = mapped_column(String(20), default="pending")
    notes: Mapped[str | None] = mapped_column(Text)
```

### src/db/session.py

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import DATABASE_URL
from src.db.schema import Base

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
```

### data/lookups/charge_categories.yaml

```yaml
# Plain-language charge taxonomy. The phase 4 loader maps statutes to these
# categories; slugs are stable identifiers, do not rename casually.
categories:
  - {slug: drug-possession, name: Drug Possession}
  - {slug: drug-delivery, name: Drug Delivery (PWID)}
  - {slug: dui, name: DUI}
  - {slug: simple-assault, name: Simple Assault}
  - {slug: aggravated-assault, name: Aggravated Assault}
  - {slug: robbery, name: Robbery}
  - {slug: burglary, name: Burglary}
  - {slug: theft, name: Theft}
  - {slug: retail-theft, name: Retail Theft}
  - {slug: firearms, name: Firearms (VUFA)}
  - {slug: criminal-trespass, name: Criminal Trespass}
  - {slug: terroristic-threats, name: Terroristic Threats}
  - {slug: fraud-forgery, name: Fraud and Forgery}
  - {slug: sexual-offenses, name: Sexual Offenses}
  - {slug: homicide, name: Homicide}
  - {slug: other, name: Other}
```

### data/lookups/disposition_map.yaml

```yaml
# Raw PA disposition text to analysis category. This is a starting seed;
# it is extended in phase 4 as real dockets surface new strings. Unmapped
# strings fall to other and the unmapped share is tracked.
categories: [dismissed, diversion, plea, trial_convicted, trial_acquitted, other]
map:
  "Nolle Prossed": dismissed
  "Withdrawn": dismissed
  "Dismissed": dismissed
  "Quashed": dismissed
  "Dismissed - LOP": dismissed
  "ARD": diversion
  "Probation Without Verdict": diversion
  "Guilty Plea - Negotiated": plea
  "Guilty Plea - Non-Negotiated": plea
  "Guilty Plea": plea
  "Nolo Contendere": plea
  "Guilty": trial_convicted
  "Not Guilty": trial_acquitted
  "Transferred to Another Jurisdiction": other
  "Mistrial": other
  "Moved to Inactive": other
```

### data/lookups/judge_overrides.yaml

```yaml
# Manual resolution map for ambiguous judge name variants. The phase 4
# loader consults this after exact-alias and unambiguous-initial matching.
# Format:
#   "Raw Name As Printed": "Normalized Last, First M."
# Keep empty until real ambiguity appears. Never invent entries.
overrides: {}
```

## Step 3: environment and database

Present as one grouped ask:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
python -m src.db.session
```

After this block: report that .env exists and is awaiting the owner's salt,
then verify the schema with an approved command:

```bash
sqlite3 data/processed/phl.db ".tables"
```

Expected output, exactly these eight tables: cases, charge_categories,
charges, defendants, judge_aliases, judges, raw_dockets, sentences.

## Step 4: worklog, then git

Append your worklog.md entry first (format at the top of that file), so it is
included in the commit. Note in the entry that commit and push are the final
approved commands after the entry is written. Then:

```bash
git init
git add .
git commit -m "Scaffold CP51: structure, schema v2, docs, and lookups"
gh repo create cp51 --private --source=. --remote=origin --push
```

If gh is unavailable, the manual path (flag the push as a remote action):

```bash
git remote add origin git@github.com:philay3/cp51.git
git branch -M main
git push -u origin main
```

## Definition of done

- Directory tree created; the pre-existing README.md, docs/, and task files
  untouched.
- All files above created with exactly the given contents.
- Virtual environment ready, requirements installed, Chromium installed.
- .env in place, salt flagged as owner-pending, value never touched.
- Database exists with exactly the eight tables listed above.
- Worklog entry appended.
- One commit, pushed to github.com/philay3/cp51.
- Stop. Do not begin acquisition or parsing work of any kind.