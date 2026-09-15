"""Robust spreadsheet parsing for .xlsx / .xls / .csv.

Detects Name / Phone / Email / Department columns from common header variants
without assuming exact names, normalizes phone numbers, flags validation
issues, and preserves any extra columns.
"""
from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

from .phone import normalize_phone

# Header variants -> canonical field. Matched case-insensitively as substrings.
_COLUMN_ALIASES: dict[str, list[str]] = {
    "name": ["name", "full name", "student name", "fullname", "contact name",
             "person", "candidate", "customer name"],
    "phone": ["phone", "phone number", "mobile", "mobile number", "contact",
              "contact number", "number", "cell", "whatsapp", "phone no", "mob"],
    "email": ["email", "e-mail", "email address", "mail"],
    "department": ["department", "dept", "branch", "team", "division",
                   "course", "class"],
}


def _clean_numeric_cell(s: str) -> str:
    """Repair phone values that a spreadsheet stored as NUMBERS.

    Excel shows a 12-digit phone as 9.18779E+11 and stores it as a float, so the
    cell can arrive as '918778948875.0' or '9.18779e+11' — both of which would
    corrupt the number once non-digits are stripped. Convert those back to the
    plain integer string.
    """
    s = (s or "").strip()
    if re.fullmatch(r"\d+\.0+", s):          # 918778948875.0
        return s.split(".")[0]
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?[eE][+-]?\d+", s):  # scientific notation
        try:
            return str(int(float(s)))
        except (ValueError, OverflowError):
            return s
    return s


def _match_column(header: str) -> str | None:
    h = str(header).strip().lower()
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if h == alias:
                return canonical
    # Second pass: substring match (looser) — exact matches win above.
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in h:
                return canonical
    return None


def _read_dataframe(filename: str, content: bytes) -> pd.DataFrame:
    name = (filename or "").lower()
    buf = io.BytesIO(content)
    if name.endswith(".csv"):
        return pd.read_csv(buf, dtype=str, keep_default_na=False)
    if name.endswith(".xls"):
        return pd.read_excel(buf, dtype=str, engine="xlrd")
    # default: xlsx / xlsm
    return pd.read_excel(buf, dtype=str, engine="openpyxl")


def parse_contacts(filename: str, content: bytes, region: str | None = None) -> dict[str, Any]:
    """Parse a spreadsheet into normalized contact rows.

    Returns a dict:
      {
        "columns": [...original headers...],
        "mapping": {"name": <col>, "phone": <col>, ...},   # detected
        "contacts": [ {name, phone, phone_valid, email, department, extra}, ...],
        "stats": {total, valid, invalid, duplicates},
        "errors": [...row-level messages...],
      }
    """
    df = _read_dataframe(filename, content)
    df = df.fillna("")
    original_columns = [str(c) for c in df.columns]

    # Build detected mapping canonical -> original header.
    mapping: dict[str, str] = {}
    for col in original_columns:
        canonical = _match_column(col)
        if canonical and canonical not in mapping:
            mapping[canonical] = col

    contacts: list[dict] = []
    errors: list[str] = []
    seen_phones: set[str] = set()
    duplicates = 0
    valid = 0

    mapped_originals = set(mapping.values())

    for i, row in df.iterrows():
        rownum = int(i) + 2  # human-friendly (header = row 1)
        raw_phone = _clean_numeric_cell(str(row.get(mapping["phone"], ""))) if "phone" in mapping else ""
        name = str(row.get(mapping["name"], "")).strip() if "name" in mapping else ""

        phone, is_valid = normalize_phone(raw_phone, region) if raw_phone else ("", False)

        if not raw_phone:
            errors.append(f"Row {rownum}: missing phone number — skipped.")
            continue
        if not is_valid:
            errors.append(f"Row {rownum}: '{raw_phone}' is not a valid phone number.")

        is_dup = phone in seen_phones
        if is_dup:
            duplicates += 1
            errors.append(f"Row {rownum}: duplicate number {phone} — skipped.")
            continue
        if phone:
            seen_phones.add(phone)
        if is_valid:
            valid += 1

        extra = {
            col: str(row.get(col, "")).strip()
            for col in original_columns
            if col not in mapped_originals and str(row.get(col, "")).strip()
        }

        contacts.append({
            "name": name,
            "phone": phone,
            "phone_valid": is_valid,
            "email": str(row.get(mapping["email"], "")).strip() if "email" in mapping else None,
            "department": str(row.get(mapping["department"], "")).strip() if "department" in mapping else None,
            "extra": extra,
        })

    return {
        "columns": original_columns,
        "mapping": mapping,
        "contacts": contacts,
        "stats": {
            "total": len(contacts),
            "valid": valid,
            "invalid": len(contacts) - valid,
            "duplicates": duplicates,
        },
        "errors": errors[:100],  # cap to keep responses lean
    }
