"""Phone number normalization and validation.

India-first (the exhibition context) but international-ready via the
`phonenumbers` library. Falls back to a permissive heuristic if the library
is unavailable so the app never hard-crashes on import.
"""
from __future__ import annotations

import re

from ..config import settings

try:
    import phonenumbers  # type: ignore

    _HAS_PHONENUMBERS = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_PHONENUMBERS = False


def normalize_phone(raw: str, region: str | None = None) -> tuple[str, bool]:
    """Return (E.164 phone, is_valid).

    Accepts messy spreadsheet input: spaces, dashes, parentheses, leading 0,
    missing country code (assumed from region, default IN / +91).
    """
    region = region or settings.DEFAULT_REGION
    if raw is None:
        return "", False
    s = str(raw).strip()
    if not s:
        return "", False

    if _HAS_PHONENUMBERS:
        try:
            parsed = phonenumbers.parse(s, region)
            if phonenumbers.is_valid_number(parsed):
                return (
                    phonenumbers.format_number(
                        parsed, phonenumbers.PhoneNumberFormat.E164
                    ),
                    True,
                )
        except Exception:
            pass
        # Fall through to heuristic on any parse failure.

    return _heuristic_normalize(s, region)


def _heuristic_normalize(s: str, region: str) -> tuple[str, bool]:
    # Keep a leading + then strip all non-digits.
    has_plus = s.strip().startswith("+")
    digits = re.sub(r"\D", "", s)
    if not digits:
        return "", False

    if has_plus:
        e164 = "+" + digits
        return e164, 8 <= len(digits) <= 15

    # India defaults for the exhibition; general fallback otherwise.
    if region.upper() == "IN":
        digits = digits.lstrip("0")
        if len(digits) == 10:
            return "+91" + digits, True
        if len(digits) == 12 and digits.startswith("91"):
            return "+" + digits, True
        return "+" + digits, 10 <= len(digits) <= 13

    return "+" + digits, 8 <= len(digits) <= 15


def mask_phone(phone: str) -> str:
    """Mask the middle digits for privacy-friendly logging/display."""
    if not phone or len(phone) < 6:
        return phone
    return phone[:3] + "*" * (len(phone) - 5) + phone[-2:]
