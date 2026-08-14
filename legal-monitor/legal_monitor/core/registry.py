from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

from legal_monitor.core import differ
from legal_monitor.core.models import CaseEventData, HearingData, ParcelEventData


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- cases -----------------------------------------------------------------


def add_case(conn: sqlite3.Connection, case_number: str, counterparty: str, our_role: str) -> bool:
    """Idempotent: returns False if the case is already tracked."""
    try:
        conn.execute(
            "INSERT INTO cases (case_number, counterparty, our_role, is_active, added_at) "
            "VALUES (?, ?, ?, 1, ?)",
            (case_number, counterparty, our_role, _now()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def list_cases(conn: sqlite3.Connection, active_only: bool = True) -> list[sqlite3.Row]:
    if active_only:
        return conn.execute("SELECT * FROM cases WHERE is_active = 1 ORDER BY case_number").fetchall()
    return conn.execute("SELECT * FROM cases ORDER BY case_number").fetchall()


def update_case_meta(
    conn: sqlite3.Connection,
    case_number: str,
    case_guid: str | None,
    court: str,
    judge: str,
    is_active: bool,
) -> None:
    conn.execute(
        "UPDATE cases SET case_guid = ?, court = ?, judge = ?, is_active = ?, last_checked_at = ? "
        "WHERE case_number = ?",
        (case_guid, court, judge, int(is_active), _now(), case_number),
    )
    conn.commit()


def record_case_event(
    conn: sqlite3.Connection, case_id: int, case_number: str, event: CaseEventData
) -> bool:
    """Returns True if this is a genuinely new event (not seen before)."""
    event_hash = differ.case_event_hash(case_number, event.event_type, event.event_date, event.description)
    try:
        conn.execute(
            "INSERT INTO case_events "
            "(case_id, event_hash, event_type, event_date, publish_date, description, document_url, first_seen_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                case_id,
                event_hash,
                event.event_type,
                event.event_date.isoformat() if event.event_date else None,
                event.publish_date.isoformat() if event.publish_date else None,
                event.description,
                event.document_url,
                _now(),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def record_hearing(conn: sqlite3.Connection, case_id: int, case_number: str, hearing: HearingData) -> bool:
    h_hash = differ.hearing_hash(case_number, hearing.hearing_at, hearing.court, hearing.room)
    try:
        conn.execute(
            "INSERT INTO hearings (case_id, hearing_hash, hearing_at, court, address, room, first_seen_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                case_id,
                h_hash,
                hearing.hearing_at.isoformat() if hearing.hearing_at else None,
                hearing.court,
                hearing.address,
                hearing.room,
                _now(),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


# --- parcels -----------------------------------------------------------------


def add_parcel(
    conn: sqlite3.Connection,
    barcode: str,
    claim_ref: str,
    counterparty: str,
    response_days: int | None = None,
) -> bool:
    """Idempotent: returns False if the barcode is already tracked."""
    try:
        conn.execute(
            "INSERT INTO parcels (barcode, claim_ref, counterparty, status, claim_response_days, is_active, added_at) "
            "VALUES (?, ?, ?, 'зарегистрировано', ?, 1, ?)",
            (barcode, claim_ref, counterparty, response_days, _now()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def list_parcels(conn: sqlite3.Connection, active_only: bool = True) -> list[sqlite3.Row]:
    if active_only:
        return conn.execute("SELECT * FROM parcels WHERE is_active = 1 ORDER BY barcode").fetchall()
    return conn.execute("SELECT * FROM parcels ORDER BY barcode").fetchall()


def update_parcel_status(
    conn: sqlite3.Connection,
    barcode: str,
    status: str,
    delivered_at: date | None,
    is_active: bool,
) -> None:
    conn.execute(
        "UPDATE parcels SET status = ?, delivered_at = ?, is_active = ?, last_checked_at = ? WHERE barcode = ?",
        (status, delivered_at.isoformat() if delivered_at else None, int(is_active), _now(), barcode),
    )
    conn.commit()


def record_parcel_event(
    conn: sqlite3.Connection, parcel_id: int, barcode: str, event: ParcelEventData
) -> bool:
    """Returns True if this is a genuinely new operation (not seen before)."""
    event_hash = differ.parcel_event_hash(barcode, event.operation, event.operation_at, event.location)
    try:
        conn.execute(
            "INSERT INTO parcel_events (parcel_id, event_hash, operation, operation_at, location, first_seen_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                parcel_id,
                event_hash,
                event.operation,
                event.operation_at.isoformat() if event.operation_at else None,
                event.location,
                _now(),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


# --- run log -----------------------------------------------------------------


def start_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute("INSERT INTO run_log (started_at) VALUES (?)", (_now(),))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    kad_ok: bool,
    pochta_ok: bool,
    new_items: int,
    error: str | None,
) -> None:
    conn.execute(
        "UPDATE run_log SET finished_at = ?, kad_ok = ?, pochta_ok = ?, new_items = ?, error = ? WHERE id = ?",
        (_now(), int(kad_ok), int(pochta_ok), new_items, error, run_id),
    )
    conn.commit()
