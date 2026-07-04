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

# Collection window (DECISIONS.md D-16): filings 2023 forward, extendable
# backward by changing this value alone.
COLLECTION_START_YEAR = int(os.getenv("COLLECTION_START_YEAR", "2023"))

