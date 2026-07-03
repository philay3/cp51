"""Batch-parse every fixture PDF into interim JSON. Console output is
docket numbers, counts, and statuses only, never extracted text."""

from __future__ import annotations

import json

from src.config import INTERIM_DIR, RAW_DIR
from src.db.schema import RawDocket
from src.db.session import SessionLocal, init_db
from src.identity import assert_no_leak
from src.parse.docket_parser import parse_docket
from src.parse.helpers import ParseError


def main() -> None:
    init_db()
    session = SessionLocal()
    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    ok = failed = 0
    print(f"{'docket':34} {'status':7} {'charges':>7} {'sentenced':>9} {'judge':>5}")
    for path in pdfs:
        docket = path.stem
        status, note = "parsed", None
        try:
            record, sentinels = parse_docket(path)
            text = json.dumps(record, indent=2, ensure_ascii=False)
            assert_no_leak(sentinels, text)
            (INTERIM_DIR / f"{docket}.json").write_text(text)
            n_ch = len(record["charges"])
            n_sent = sum(1 for c in record["charges"] if c["sentences"])
            has_judge = any(c["disposition_judge_raw"] for c in record["charges"])
            ok += 1
            print(f"{docket:34} {status:7} {n_ch:>7} {n_sent:>9} "
                  f"{'y' if has_judge else 'n':>5}")
        except (ParseError, RuntimeError) as exc:
            status, note = "failed", f"{type(exc).__name__}: {exc}"
            failed += 1
            print(f"{docket:34} {status:7} {'-':>7} {'-':>9} {'-':>5}")
        row = session.get(RawDocket, docket) or RawDocket(docket_number=docket)
        row.pdf_path = str(path)
        row.parse_status = status
        row.notes = note
        session.merge(row)
        session.commit()
    session.close()
    print(f"\ndone: {ok} parsed, {failed} failed of {len(pdfs)}")


if __name__ == "__main__":
    main()
