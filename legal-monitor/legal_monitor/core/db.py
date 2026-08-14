from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_number TEXT NOT NULL UNIQUE,
    case_guid TEXT,
    court TEXT,
    judge TEXT,
    counterparty TEXT,
    our_role TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    added_at TEXT NOT NULL,
    last_checked_at TEXT
);

CREATE TABLE IF NOT EXISTS case_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id),
    event_hash TEXT NOT NULL UNIQUE,
    event_type TEXT,
    event_date TEXT,
    publish_date TEXT,
    description TEXT,
    document_url TEXT,
    first_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_case_events_case_id ON case_events(case_id);

CREATE TABLE IF NOT EXISTS hearings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id),
    hearing_hash TEXT NOT NULL UNIQUE,
    hearing_at TEXT,
    court TEXT,
    address TEXT,
    room TEXT,
    first_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hearings_case_id ON hearings(case_id);

CREATE TABLE IF NOT EXISTS parcels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT NOT NULL UNIQUE,
    claim_ref TEXT,
    counterparty TEXT,
    sent_at TEXT,
    status TEXT,
    delivered_at TEXT,
    claim_response_days INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    added_at TEXT NOT NULL,
    last_checked_at TEXT
);

CREATE TABLE IF NOT EXISTS parcel_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parcel_id INTEGER NOT NULL REFERENCES parcels(id),
    event_hash TEXT NOT NULL UNIQUE,
    operation TEXT,
    operation_at TEXT,
    location TEXT,
    first_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_parcel_events_parcel_id ON parcel_events(parcel_id);

CREATE TABLE IF NOT EXISTS document_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_event_id INTEGER NOT NULL UNIQUE REFERENCES case_events(id),
    document_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    explicit_deadlines TEXT,
    rule_deadline TEXT,
    rule_deadline_basis TEXT,
    analyzed_at TEXT NOT NULL,
    analysis_error TEXT
);

CREATE TABLE IF NOT EXISTS run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    kad_ok INTEGER,
    pochta_ok INTEGER,
    new_items INTEGER,
    error TEXT
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
