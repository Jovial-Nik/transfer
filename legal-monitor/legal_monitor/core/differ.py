from __future__ import annotations

import hashlib
from datetime import date, datetime


def _norm(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value).strip()


def case_event_hash(case_number: str, event_type: str, event_date: object, description: str) -> str:
    """Stable hash for a case event. Novelty is decided by hash presence, never by
    'checked since' timestamps, because KAD publishes events retroactively."""
    raw = "|".join([_norm(case_number), _norm(event_type), _norm(event_date), _norm(description)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def hearing_hash(case_number: str, hearing_at: object, court: str, room: str) -> str:
    raw = "|".join([_norm(case_number), _norm(hearing_at), _norm(court), _norm(room)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parcel_event_hash(barcode: str, operation: str, operation_at: object, location: str) -> str:
    raw = "|".join([_norm(barcode), _norm(operation), _norm(operation_at), _norm(location)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
