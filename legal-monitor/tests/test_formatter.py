from datetime import date, datetime

from legal_monitor.core.models import CaseEventData, HearingData
from legal_monitor.notifier.formatter import (
    CaseEventDisplay,
    CaseUpdate,
    EventAnalysisDisplay,
    ParcelUpdate,
    RunSummary,
    build_messages,
)


def test_silent_when_nothing_changed_and_both_sources_ok() -> None:
    summary = RunSummary(run_date=date(2026, 8, 14), kad_ok=True, kad_error=None, pochta_ok=True, pochta_error=None)
    assert build_messages(summary) == []


def test_source_failure_alone_still_produces_a_message() -> None:
    summary = RunSummary(
        run_date=date(2026, 8, 14),
        kad_ok=False,
        kad_error="HTTP 451 после обновления cookies",
        pochta_ok=True,
        pochta_error=None,
    )
    messages = build_messages(summary)
    assert len(messages) == 1
    assert "КАД не ответил" in messages[0]
    assert "451" in messages[0]


def test_company_name_with_quotes_is_escaped() -> None:
    update = CaseUpdate(
        case_number="А07-12345/2025",
        counterparty='ООО "Ромашка" & Co <тест>',
        new_events=[
            CaseEventDisplay(
                event=CaseEventData(
                    event_type="Определение",
                    event_date=date(2026, 8, 13),
                    publish_date=date(2026, 8, 13),
                    description="Назначено заседание",
                    document_url=None,
                )
            )
        ],
    )
    summary = RunSummary(
        run_date=date(2026, 8, 14), kad_ok=True, kad_error=None, pochta_ok=True, pochta_error=None, case_updates=[update]
    )
    text = build_messages(summary)[0]
    assert "&amp;" in text
    assert "&lt;тест&gt;" in text
    assert "<b>А07-12345/2025</b>" in text  # our own tags stay unescaped


def test_parcel_delivery_shows_response_deadline() -> None:
    update = ParcelUpdate(
        claim_ref="Претензия №15",
        counterparty="ООО Ромашка",
        status="вручено",
        delivered_at=date(2026, 8, 13),
        response_deadline=date(2026, 9, 12),
    )
    summary = RunSummary(
        run_date=date(2026, 8, 14),
        kad_ok=True,
        kad_error=None,
        pochta_ok=True,
        pochta_error=None,
        parcel_updates=[update],
    )
    text = build_messages(summary)[0]
    assert "ВРУЧЕНО" in text
    assert "13.08.2026" in text
    assert "срок ответа истекает 12.09.2026" in text


def test_long_message_is_split_under_telegram_limit() -> None:
    many_updates = [
        CaseUpdate(
            case_number=f"А07-{i}/2025",
            counterparty="ООО Ромашка",
            new_events=[
                CaseEventDisplay(
                    event=CaseEventData(
                        event_type="Определение",
                        event_date=date(2026, 8, 13),
                        publish_date=date(2026, 8, 13),
                        description="Текст определения " * 20,
                        document_url=None,
                    )
                )
            ],
        )
        for i in range(60)
    ]
    summary = RunSummary(
        run_date=date(2026, 8, 14),
        kad_ok=True,
        kad_error=None,
        pochta_ok=True,
        pochta_error=None,
        case_updates=many_updates,
    )
    messages = build_messages(summary)
    assert len(messages) > 1
    assert all(len(m) <= 4096 for m in messages)


def test_document_analysis_rendering() -> None:
    update = CaseUpdate(
        case_number="А07-12345/2025",
        counterparty="ООО Ромашка",
        new_events=[
            CaseEventDisplay(
                event=CaseEventData(
                    event_type="Решение",
                    event_date=date(2026, 8, 13),
                    publish_date=date(2026, 8, 13),
                    description="Иск удовлетворён",
                    document_url="https://kad.arbitr.ru/doc.pdf",
                ),
                analysis=EventAnalysisDisplay(
                    summary="Суд удовлетворил иск полностью.",
                    deadline=date(2026, 9, 12),
                    deadline_basis="ст. 259 АПК РФ — 1 месяц со дня принятия решения в полном объёме",
                ),
            )
        ],
    )
    summary = RunSummary(
        run_date=date(2026, 8, 14), kad_ok=True, kad_error=None, pochta_ok=True, pochta_error=None, case_updates=[update]
    )
    text = build_messages(summary)[0]
    assert "Суд удовлетворил иск полностью." in text
    assert "12.09.2026" in text
    assert "ст. 259 АПК РФ" in text
    assert "проверьте вручную" in text


def test_hearing_rendering() -> None:
    update = CaseUpdate(
        case_number="А07-12345/2025",
        counterparty="ООО Ромашка",
        new_hearings=[HearingData(hearing_at=datetime(2026, 9, 5, 10, 30), court="АС РБ", address="", room="305")],
    )
    summary = RunSummary(
        run_date=date(2026, 8, 14), kad_ok=True, kad_error=None, pochta_ok=True, pochta_error=None, case_updates=[update]
    )
    text = build_messages(summary)[0]
    assert "05.09.2026, 10:30" in text
    assert "зал 305" in text
