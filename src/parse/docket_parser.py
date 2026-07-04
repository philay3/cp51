from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pdfplumber

from src.identity import hash_defendant
from src.parse.helpers import parse_date, to_days, ParseError, GRADES

HEADERS = [
    "CASE INFORMATION",
    "STATUS INFORMATION",
    "CALENDAR EVENTS",
    "DEFENDANT INFORMATION",
    "CHARGES",
    "DISPOSITION SENTENCING/PENALTIES",
    "COMMONWEALTH INFORMATION",
    "ATTORNEY INFORMATION",
    "ENTRIES",
]

DISPO_SKIP_HEADERS = {
    "DISPOSITION SENTENCING/PENALTIES",
    "Disposition",
    "Case Event Disposition Date Final Disposition",
    "Sequence/Description Offense Disposition Grade Section",
    "Sentencing Judge Sentence Date Credit For Time Served",
    "Sentence/Diversion Program Type Incarceration/Diversionary Period Start Date",
    "Sentence Conditions"
}


def is_statute_token(tok: str) -> bool:
    tok_clean = tok.strip()
    if not tok_clean:
        return True
    if "§" in tok_clean:
        return True
    # Contains a digit
    if re.search(r"\d", tok_clean):
        return True
    # Length 1 (e.g. single letters like A, or symbols like -)
    if len(tok_clean) == 1:
        return True
    # Roman numerals (case-insensitive)
    if tok_clean.lower() in ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"):
        return True
    # Check for parenthesized subsections like (a), (1)
    if tok_clean.startswith("(") and tok_clean.endswith(")"):
        return True
    return False


def parse_docket(pdf_path: Path) -> tuple[dict, list[str]]:
    """Parse one docket sheet PDF.

    Returns (record, sentinels): record matches the JSON contract;
    sentinels are the transient identifying strings (printed name, name
    parts, DOB text) for the privacy check. Raises ParseError when the sheet
    cannot be read; error messages never quote docket text.
    """
    docket_number = pdf_path.stem

    # Extract text and split by line
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text is None:
                    text = ""
                pages_text.append(text)
    except Exception as exc:
        raise ParseError(f"Failed to open/read PDF file: {type(exc).__name__}")

    # Gather transient names from page headers (under "v.")
    v_names = set()
    raw_lines = []

    for text in pages_text:
        page_lines = text.splitlines()
        skip_next = False
        for i, line in enumerate(page_lines):
            line_str = line.strip()
            if skip_next:
                if line_str:
                    v_names.add(line_str)
                skip_next = False
                continue
            if line_str.lower() in ("v.", "v"):
                skip_next = True
                continue
            raw_lines.append(line)

    # Filter out header/footer lines and organize into sections
    sections = {h: [] for h in HEADERS}
    current_section = None

    for line in raw_lines:
        line_str = line.strip()
        if not line_str:
            continue

        # Skip page headers, footers, and disclaimers
        if line_str == "COURT OF COMMON PLEAS OF PHILADELPHIA COUNTY":
            continue
        if line_str == "DOCKET":
            continue
        if line_str.startswith("Docket Number:"):
            continue
        if line_str == "CRIMINAL DOCKET":
            continue
        if line_str == "Court Case":
            continue
        if line_str == "Commonwealth of Pennsylvania":
            continue
        if re.match(r"^Page \d+ of \d+$", line_str):
            continue
        if re.match(r"^CPCMS .* Printed:.*$", line_str, re.IGNORECASE):
            continue
        if "Recent entries made in the court" in line_str:
            continue
        if "Neither the courts of the Unified Judicial" in line_str:
            continue
        if "System of the Commonwealth of Pennsylvania" in line_str:
            continue
        if "data, errors or omissions on these reports" in line_str:
            continue
        if "only be provided by the Pennsylvania State Police" in line_str:
            continue
        if "Moreover an employer who does not comply" in line_str:
            continue
        if "Information Act may be subject to civil liability" in line_str:
            continue

        if line_str in HEADERS:
            current_section = line_str
        elif current_section is not None:
            sections[current_section].append(line)

    # Extract Defendant Name and Date of Birth
    defendant_name = None
    dob_str = None

    # Find DOB in DEFENDANT INFORMATION
    for line in sections.get("DEFENDANT INFORMATION", []):
        if "Date Of Birth:" in line or "Date of Birth:" in line:
            m_dob = re.search(r"Date\s+of\s+Birth:\s*([\d/]+)", line, re.IGNORECASE)
            if m_dob:
                dob_str = m_dob.group(1).strip()
                break

    # Find Defendant Name in CASE PARTICIPANTS (part of DEFENDANT INFORMATION section)
    for line in sections.get("DEFENDANT INFORMATION", []):
        m_def = re.match(r"^Defendant\s+(.*)$", line.strip())
        if m_def:
            defendant_name = m_def.group(1).strip()
            break

    # Fallback to v_names if defendant_name is not in CASE PARTICIPANTS
    if not defendant_name and v_names:
        defendant_name = sorted(list(v_names))[0]

    if not defendant_name or not dob_str:
        raise ParseError("Missing defendant name or date of birth")

    try:
        birth_year = int(dob_str.split("/")[-1])
    except Exception:
        raise ParseError("Invalid date of birth format")

    defendant_hash = hash_defendant(defendant_name, birth_year)

    # Compile privacy sentinels
    sentinels = [dob_str, defendant_name]
    for part in re.split(r"[^a-zA-Z]", defendant_name):
        if len(part) >= 3:
            sentinels.append(part)
    for name in v_names:
        sentinels.append(name)
        for part in re.split(r"[^a-zA-Z]", name):
            if len(part) >= 3:
                sentinels.append(part)
    sentinels = sorted(list(set(sentinels)))

    # Parse Case status
    case_status = None
    for line in sections.get("STATUS INFORMATION", []):
        m = re.search(r"Case\s+Status:\s*(.*?)(?:\s+Status\s+Date|\s+Processing|\s+Arrest|$)", line, re.IGNORECASE)
        if m:
            case_status = m.group(1).strip()
            break

    # Parse Case Filed Date, Assigned Judge, OTN
    filed_date = None
    assigned_judge_raw = None
    otn = None
    for line in sections.get("CASE INFORMATION", []):
        if "Judge Assigned:" in line or "Date Filed:" in line:
            m_judge = re.search(r"Judge\s+Assigned:\s*(.*?)\s+Date\s+Filed:", line, re.IGNORECASE)
            if m_judge:
                assigned_judge_raw = m_judge.group(1).strip()
            m_date = re.search(r"Date\s+Filed:\s*([\d/]+)", line, re.IGNORECASE)
            if m_date:
                filed_date = parse_date(m_date.group(1))
        if "OTN:" in line:
            m_otn = re.search(r"OTN:\s*([A-Za-z0-9\s-]+?)(?:\s+LOTN:|\s+Originating|$)", line, re.IGNORECASE)
            if m_otn:
                otn = m_otn.group(1).strip()

    # Parse Charges
    parsed_charges = {}
    active_charge = None

    for line in sections.get("CHARGES", []):
        line_str = line.strip()
        if not line_str:
            continue
        if "Seq." in line_str and "Statute" in line_str:
            continue
        
        m_seq = re.match(r"^(\d+)\s+(\d+)\s+(.*)$", line_str)
        if m_seq:
            seq = int(m_seq.group(1))
            rest = m_seq.group(3).strip()
            
            tokens = rest.split()
            if not tokens:
                continue
                
            grade = None
            if tokens[0] in GRADES:
                grade = tokens[0]
                tokens = tokens[1:]
                
            date_idx = -1
            for idx in range(len(tokens) - 1, -1, -1):
                if re.match(r"^\d{2}/\d{2}/\d{4}$", tokens[idx]):
                    date_idx = idx
                    break
                    
            offense_date = None
            otn_val = None
            statute_tokens = []
            offense_tokens = []
            
            if date_idx != -1:
                offense_date = parse_date(tokens[date_idx])
                if date_idx + 1 < len(tokens):
                    otn_val = " ".join(tokens[date_idx + 1:])
                left_tokens = tokens[:date_idx]
                
                first_offense_idx = len(left_tokens)
                for idx, tok in enumerate(left_tokens):
                    if not is_statute_token(tok):
                        first_offense_idx = idx
                        break
                statute_tokens = left_tokens[:first_offense_idx]
                offense_tokens = left_tokens[first_offense_idx:]
            else:
                first_offense_idx = len(tokens)
                for idx, tok in enumerate(tokens):
                    if not is_statute_token(tok):
                        first_offense_idx = idx
                        break
                statute_tokens = tokens[:first_offense_idx]
                offense_tokens = tokens[first_offense_idx:]
                
            statute_str = " ".join(statute_tokens)
            offense_str = " ".join(offense_tokens)
            
            active_charge = {
                "sequence": seq,
                "statute": statute_str if statute_str else None,
                "grade": grade,
                "offense": offense_str if offense_str else None,
                "disposition_raw": None,
                "disposition_date": None,
                "disposition_judge_raw": None,
                "sentences": []
            }
            parsed_charges[seq] = active_charge
        else:
            if active_charge:
                if active_charge["offense"]:
                    active_charge["offense"] = active_charge["offense"] + " " + line_str
                else:
                    active_charge["offense"] = line_str

    # Parse Dispositions and Sentences
    current_charge_seq = None
    expecting_judge_line = False
    current_sentence_comp = None
    in_valid_event = False
    current_event_name = ""

    def save_current_sentence():
        nonlocal current_sentence_comp
        if current_sentence_comp and current_charge_seq is not None:
            raw_text = ", ".join(current_sentence_comp["raw_text_parts"])
            
            min_days = None
            max_days = None
            type_lower = current_sentence_comp["sentence_type"].lower()
            
            if type_lower not in ("no further penalty", "fines and costs"):
                min_match = re.search(r"Min of\s+(.*?)(?:Max of|$|,)", raw_text, re.IGNORECASE)
                max_match = re.search(r"Max of\s+(.*?)(?:Min of|$|,)", raw_text, re.IGNORECASE)
                
                if min_match:
                    min_days = to_days(min_match.group(1).replace(".00", ""))
                if max_match:
                    max_days = to_days(max_match.group(1).replace(".00", ""))
                    
                if min_days is None and max_days is None:
                    flat_days = to_days(raw_text.replace(".00", ""))
                    if flat_days is not None:
                        min_days = flat_days
                        max_days = flat_days
                elif min_days is None and max_days is not None:
                    min_days = max_days
                elif max_days is None and min_days is not None:
                    max_days = min_days
                    
            parsed_charges[current_charge_seq]["sentences"].append({
                "sentence_type": current_sentence_comp["sentence_type"],
                "min_days": min_days,
                "max_days": max_days,
                "program": current_sentence_comp["program"],
                "sentence_date": current_sentence_comp["sentence_date"],
                "raw_text": raw_text
            })
            current_sentence_comp = None

    disposition_lines = sections.get("DISPOSITION SENTENCING/PENALTIES", [])
    for idx, line in enumerate(disposition_lines):
        line_str = line.strip()
        if not line_str:
            continue
            
        if line_str in DISPO_SKIP_HEADERS:
            continue
            
        # Check if the next line is an event date line (lookahead)
        is_event_header = False
        if idx + 1 < len(disposition_lines):
            next_line = disposition_lines[idx + 1].strip()
            if re.search(r"(Final Disposition|Not Final)$", next_line):
                is_event_header = True
                
        if is_event_header:
            save_current_sentence()
            current_charge_seq = None
            current_event_name = line_str
            continue
            
        date_line_match = re.search(r"(Final Disposition|Not Final)$", line_str)
        if date_line_match:
            save_current_sentence()
            current_charge_seq = None
            if date_line_match.group(1) == "Final Disposition" or "ard" in current_event_name.lower():
                in_valid_event = True
            else:
                in_valid_event = False
            continue
            
        charge_match = re.match(r"^(\d+)\s*/\s*(.*)$", line_str)
        if charge_match:
            save_current_sentence()
            if not in_valid_event:
                current_charge_seq = None
                continue
            seq = int(charge_match.group(1))
            current_charge_seq = seq
            expecting_judge_line = True
            
            text = charge_match.group(2).strip()
            if seq in parsed_charges:
                charge = parsed_charges[seq]
                offense = charge["offense"] or ""
                matched_prefix = ""
                for i in range(len(offense), 0, -1):
                    prefix = offense[:i].strip()
                    if text.startswith(prefix):
                        matched_prefix = prefix
                        break
                remaining = text[len(matched_prefix):].strip()
                
                statute = charge["statute"] or ""
                if statute and remaining.endswith(statute):
                    remaining = remaining[:-len(statute)].strip()
                grade = charge["grade"] or ""
                if grade and remaining.endswith(grade):
                    remaining = remaining[:-len(grade)].strip()
                    
                charge["disposition_raw"] = remaining if remaining else None
            continue
            
        if current_charge_seq is not None and expecting_judge_line:
            if re.search(r"\d{2}/\d{2}/\d{4}$", line_str):
                judge_match = re.match(r"^(.*?)\s+(\d{2}/\d{2}/\d{4})$", line_str)
                if judge_match:
                    judge_name = judge_match.group(1).strip()
                    disp_date = parse_date(judge_match.group(2))
                    if current_charge_seq in parsed_charges:
                        parsed_charges[current_charge_seq]["disposition_judge_raw"] = judge_name
                        parsed_charges[current_charge_seq]["disposition_date"] = disp_date
                    expecting_judge_line = False
                    continue
            else:
                is_sent_type = False
                for stype in ("Confinement", "Probation", "ARD", "IPP", "No Further Penalty", "Fines and Costs"):
                    if line_str.lower().startswith(stype.lower()):
                        is_sent_type = True
                        break
                if is_sent_type:
                    expecting_judge_line = False
                else:
                    continue

        if current_charge_seq is not None and not expecting_judge_line:
            matched_type = None
            for stype in ("Confinement", "Probation", "ARD", "IPP", "No Further Penalty", "Fines and Costs"):
                if line_str.lower().startswith(stype.lower()):
                    matched_type = stype
                    break
                    
            if matched_type:
                save_current_sentence()
                charge = parsed_charges[current_charge_seq]
                current_sentence_comp = {
                    "sentence_type": matched_type,
                    "program": line_str,
                    "sentence_date": charge["disposition_date"],
                    "raw_text_parts": [line_str]
                }
            elif current_sentence_comp:
                is_continuation = (
                    any(u in line_str.lower() for u in ("year", "month", "day", "\u00bd")) and 
                    any(c.isdigit() for c in line_str)
                ) or line_str.lower().startswith("min of") or line_str.lower().startswith("max of")
                
                if is_continuation:
                    current_sentence_comp["raw_text_parts"].append(line_str)
                else:
                    save_current_sentence()

    save_current_sentence()

    # Format charges as list
    charges_list = sorted(list(parsed_charges.values()), key=lambda x: x["sequence"])

    record = {
        "docket_number": docket_number,
        "parser_version": 1,
        "parsed_at": datetime.now().replace(microsecond=0).isoformat(),
        "case": {
            "county": "Philadelphia",
            "court_type": "Common Pleas",
            "case_status": case_status,
            "filed_date": filed_date,
            "otn": otn,
            "assigned_judge_raw": assigned_judge_raw,
            "defendant_hash": defendant_hash,
        },
        "charges": charges_list,
        "notes": [],
    }

    return record, sentinels
