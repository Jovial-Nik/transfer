from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class CaseEventData:
    """One event found on a case card, before it is checked against the registry."""

    event_type: str
    event_date: date | None
    publish_date: date | None
    description: str
    document_url: str | None


@dataclass(frozen=True)
class HearingData:
    hearing_at: datetime | None
    court: str
    address: str
    room: str


@dataclass(frozen=True)
class CaseSnapshot:
    """Everything the KAD client could gather for one tracked case in this run."""

    case_number: str
    case_guid: str | None
    court: str
    judge: str
    is_finished: bool
    events: list[CaseEventData]
    hearings: list[HearingData]


@dataclass(frozen=True)
class ParcelEventData:
    operation: str
    operation_at: datetime | None
    location: str


@dataclass(frozen=True)
class ParcelSnapshot:
    """Everything the Pochta client could gather for one tracked parcel in this run."""

    barcode: str
    status: str
    delivered_at: date | None
    is_final: bool
    events: list[ParcelEventData]
