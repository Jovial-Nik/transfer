"""Builds the daily Telegram summary. Silence by default is the whole point:
build_messages() returns an empty list when nothing changed and both sources
answered, and the orchestrator must not call the sender in that case.

Uses Telegram's HTML parse mode rather than MarkdownV2: company names carry
quotes and other MarkdownV2-special characters that would otherwise need
escaping on every field; HTML only needs '&', '<', '>' escaped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from html import escape

from legal_monitor.core.models import CaseEventData, HearingData

TELEGRAM_MESSAGE_LIMIT = 4096


@dataclass
class CaseUpdate:
    case_number: str
    counterparty: str
    new_events: list[CaseEventData] = field(default_factory=list)
    new_hearings: list[HearingData] = field(default_factory=list)


@dataclass
class ParcelUpdate:
    claim_ref: str
    counterparty: str
    status: str
    delivered_at: date | None
    response_deadline: date | None


@dataclass
class RunSummary:
    run_date: date
    kad_ok: bool
    kad_error: str | None
    pochta_ok: bool
    pochta_error: str | None
    case_updates: list[CaseUpdate] = field(default_factory=list)
    parcel_updates: list[ParcelUpdate] = field(default_factory=list)

    @property
    def has_content(self) -> bool:
        return bool(self.case_updates or self.parcel_updates or not self.kad_ok or not self.pochta_ok)


def _fmt_date(d: date | None, fmt: str = "%d.%m.%Y") -> str:
    return d.strftime(fmt) if d else "—"


def _fmt_dt(dt: datetime | None) -> str:
    return dt.strftime("%d.%m.%Y, %H:%M") if dt else "—"


def _render_case_block(update: CaseUpdate) -> str:
    lines = [f"<b>{escape(update.case_number)}</b> ({escape(update.counterparty)})"]
    for event in update.new_events:
        header = f"  • {escape(event.event_type)} от {_fmt_date(event.event_date, '%d.%m')} — {escape(event.description)}"
        lines.append(header)
        if event.document_url:
            lines.append(f'    <a href="{escape(event.document_url)}">[PDF]</a>')
    for hearing in update.new_hearings:
        place = escape(hearing.court)
        if hearing.address:
            place += f", {escape(hearing.address)}"
        if hearing.room:
            place += f", зал {escape(hearing.room)}"
        lines.append(f"  • Заседание назначено на {_fmt_dt(hearing.hearing_at)}")
        lines.append(f"    {place}")
    return "\n".join(lines)


def _render_parcel_block(update: ParcelUpdate) -> str:
    line = f"{escape(update.claim_ref)} ({escape(update.counterparty)}) — {escape(update.status.upper())}"
    if update.delivered_at:
        line += f" {_fmt_date(update.delivered_at)}"
    lines = [line]
    if update.response_deadline:
        lines.append(f"  → срок ответа истекает {_fmt_date(update.response_deadline)}")
    return "\n".join(lines)


def build_messages(summary: RunSummary) -> list[str]:
    """Returns [] when there is nothing worth sending."""
    if not summary.has_content:
        return []

    blocks: list[str] = [f"📅 {_fmt_date(summary.run_date)}"]

    if not summary.kad_ok:
        blocks.append(f"⚠️ КАД не ответил ({escape(summary.kad_error or 'причина неизвестна')})")
    if not summary.pochta_ok:
        blocks.append(f"⚠️ Почта России не ответила ({escape(summary.pochta_error or 'причина неизвестна')})")

    if summary.case_updates:
        case_blocks = "\n\n".join(_render_case_block(u) for u in summary.case_updates)
        blocks.append(f"⚖️ СУДЫ\n{case_blocks}")

    if summary.parcel_updates:
        parcel_blocks = "\n\n".join(_render_parcel_block(u) for u in summary.parcel_updates)
        blocks.append(f"📮 ПРЕТЕНЗИИ\n{parcel_blocks}")

    full_text = "\n\n".join(blocks)
    return _split_message(full_text)


def _split_message(text: str) -> list[str]:
    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        return [text]

    messages: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= TELEGRAM_MESSAGE_LIMIT:
            current = candidate
            continue
        if current:
            messages.append(current)
            current = ""
        if len(block) <= TELEGRAM_MESSAGE_LIMIT:
            current = block
        else:
            # a single block (e.g. one case with many events) exceeds the limit on its own
            for line in block.split("\n"):
                candidate_line = f"{current}\n{line}" if current else line
                if len(candidate_line) > TELEGRAM_MESSAGE_LIMIT:
                    if current:
                        messages.append(current)
                    current = line
                else:
                    current = candidate_line
    if current:
        messages.append(current)
    return messages
