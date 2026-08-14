from datetime import date

import pytest

from legal_monitor.core import db, registry
from legal_monitor.core.models import CaseEventData, ParcelEventData


@pytest.fixture()
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    db.init_db(connection)
    yield connection
    connection.close()


def _event(desc: str, d: date = date(2026, 8, 13)) -> CaseEventData:
    return CaseEventData(event_type="Определение", event_date=d, publish_date=d, description=desc, document_url=None)


def test_add_case_is_idempotent(conn) -> None:
    assert registry.add_case(conn, "А07-12345/2025", "ООО Ромашка", "plaintiff") is True
    assert registry.add_case(conn, "А07-12345/2025", "ООО Ромашка", "plaintiff") is False
    assert len(registry.list_cases(conn)) == 1


def test_new_event_recorded_once_repeat_run_gives_no_duplicate(conn) -> None:
    registry.add_case(conn, "А07-12345/2025", "ООО Ромашка", "plaintiff")
    case_id = registry.list_cases(conn)[0]["id"]

    first_pass = registry.record_case_event(conn, case_id, "А07-12345/2025", _event("Назначено заседание"))
    second_pass_same_run = registry.record_case_event(conn, case_id, "А07-12345/2025", _event("Назначено заседание"))
    assert first_pass is not None
    assert second_pass_same_run is None

    events = conn.execute("SELECT * FROM case_events WHERE case_id = ?", (case_id,)).fetchall()
    assert len(events) == 1


def test_backdated_event_is_still_new_if_hash_unseen(conn) -> None:
    registry.add_case(conn, "А07-1/2025", "ООО Ромашка", "plaintiff")
    case_id = registry.list_cases(conn)[0]["id"]

    registry.record_case_event(conn, case_id, "А07-1/2025", _event("свежее событие", date(2026, 8, 13)))
    is_new = registry.record_case_event(conn, case_id, "А07-1/2025", _event("опубликовано задним числом", date(2026, 1, 1)))
    assert is_new is not None


def test_parcel_event_dedup(conn) -> None:
    from datetime import datetime

    registry.add_parcel(conn, "80082806838014", "Претензия №15", "ООО Ромашка")
    parcel_id = registry.list_parcels(conn)[0]["id"]

    event = ParcelEventData(operation="Вручено", operation_at=datetime(2026, 8, 13, 12, 0), location="Уфа")
    assert registry.record_parcel_event(conn, parcel_id, "80082806838014", event) is True
    assert registry.record_parcel_event(conn, parcel_id, "80082806838014", event) is False


def test_document_analysis_round_trip(conn) -> None:
    registry.add_case(conn, "А07-1/2025", "ООО Ромашка", "plaintiff")
    case_id = registry.list_cases(conn)[0]["id"]
    event_id = registry.record_case_event(conn, case_id, "А07-1/2025", _event("Решение"))
    assert event_id is not None

    registry.record_document_analysis(
        conn,
        event_id,
        document_type="решение_обычное_производство",
        summary="Иск удовлетворён полностью.",
        explicit_deadlines_json="[]",
        rule_deadline=date(2026, 9, 13),
        rule_deadline_basis="ст. 259 АПК РФ",
    )
    row = conn.execute("SELECT * FROM document_analysis WHERE case_event_id = ?", (event_id,)).fetchone()
    assert row["document_type"] == "решение_обычное_производство"
    assert row["rule_deadline"] == "2026-09-13"


def test_run_log_lifecycle(conn) -> None:
    run_id = registry.start_run(conn)
    registry.finish_run(conn, run_id, kad_ok=True, pochta_ok=False, new_items=2, error="Почта не ответила")
    row = conn.execute("SELECT * FROM run_log WHERE id = ?", (run_id,)).fetchone()
    assert row["kad_ok"] == 1
    assert row["pochta_ok"] == 0
    assert row["new_items"] == 2
