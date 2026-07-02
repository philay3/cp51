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
from typing import Optional
from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Judge(Base):
    __tablename__ = "judges"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_normalized: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    slug: Mapped[Optional[str]] = mapped_column(String(80), unique=True)
    first_seen: Mapped[Optional[date]] = mapped_column(Date)
    last_seen: Mapped[Optional[date]] = mapped_column(Date)

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
    case_status: Mapped[Optional[str]] = mapped_column(String(40))
    filed_date: Mapped[Optional[date]] = mapped_column(Date)
    otn: Mapped[Optional[str]] = mapped_column(String(40))

    # judge_id is the sentencing judge: the modal judge across this case's
    # sentenced charges. Charge-level truth is charges.disposition_judge_id.
    judge_id: Mapped[Optional[int]] = mapped_column(ForeignKey("judges.id"))
    # The "Judge Assigned" string from the case header, kept raw only.
    assigned_judge_raw: Mapped[Optional[str]] = mapped_column(Text)
    defendant_id: Mapped[Optional[str]] = mapped_column(ForeignKey("defendants.id"))

    source_url: Mapped[Optional[str]] = mapped_column(Text)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    judge: Mapped[Optional[Judge]] = relationship(back_populates="cases")
    defendant: Mapped[Optional[Defendant]] = relationship(back_populates="cases")
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
    sequence: Mapped[Optional[int]] = mapped_column(Integer)
    statute: Mapped[Optional[str]] = mapped_column(String(60))
    grade: Mapped[Optional[str]] = mapped_column(String(10))  # F1..F3, M1..M3, S
    offense: Mapped[Optional[str]] = mapped_column(Text)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("charge_categories.id"))

    disposition_raw: Mapped[Optional[str]] = mapped_column(String(120))
    # Derived at load time from data/lookups/disposition_map.yaml:
    # dismissed, diversion, plea, trial_convicted, trial_acquitted, other.
    disposition_category: Mapped[Optional[str]] = mapped_column(String(30))
    disposition_date: Mapped[Optional[date]] = mapped_column(Date)
    disposition_judge_id: Mapped[Optional[int]] = mapped_column(ForeignKey("judges.id"))

    case: Mapped["Case"] = relationship(back_populates="charges")
    category: Mapped[Optional[ChargeCategory]] = relationship(back_populates="charges")
    disposition_judge: Mapped[Optional[Judge]] = relationship(
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
    sentence_type: Mapped[Optional[str]] = mapped_column(String(80))
    min_days: Mapped[Optional[int]] = mapped_column(Integer)  # PA min-max ranges
    max_days: Mapped[Optional[int]] = mapped_column(Integer)
    program: Mapped[Optional[str]] = mapped_column(String(120))
    sentence_date: Mapped[Optional[date]] = mapped_column(Date)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)  # component as printed

    charge: Mapped["Charge"] = relationship(back_populates="sentences")


class RawDocket(Base):
    """Fetch and parse tracking, so the pipeline is reproducible and idempotent."""
    __tablename__ = "raw_dockets"

    docket_number: Mapped[str] = mapped_column(String(40), primary_key=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(Text)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    parse_status: Mapped[str] = mapped_column(String(20), default="pending")
    notes: Mapped[Optional[str]] = mapped_column(Text)
