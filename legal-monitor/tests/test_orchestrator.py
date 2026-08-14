from datetime import date

import pytest

from legal_monitor.core import db, orchestrator, registry
from legal_monitor.core.models import CaseEventData
from legal_monitor.kad_client.card import CaseCardData
from legal_monitor.kad_client.parser import CaseHeader
from legal_monitor.pochta_client.client import PochtaUnavailable


class FakeKadClient:
    def __init__(self, headers):
        self._headers = headers

    def search(self, case_numbers):
        return [h for h in self._headers if h.case_number in case_numbers]


class FakeCardFetcher:
    def __init__(self, card_by_guid):
        self._card_by_guid = card_by_guid

    def fetch(self, guid):
        return self._card_by_guid[guid]


class FakePochtaClient:
    def __init__(self, fail=False):
        self.fail = fail

    def get_operation_history(self, barcode):
        if self.fail:
            raise PochtaUnavailable("лимит запросов исчерпан")
        from legal_monitor.core.models import ParcelSnapshot

        return ParcelSnapshot(barcode=barcode, status="доставлено", delivered_at=None, is_final=False, events=[])


class FakeDocAnalysisRunner:
    def __init__(self, analysis):
        self._analysis = analysis
        self.calls = 0

    def analyze(self, document_url):
        self.calls += 1
        return self._analysis


class FakeTelegram:
    def __init__(self):
        self.sent: list[list[str]] = []

    def send(self, messages):
        self.sent.append(messages)


@pytest.fixture()
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    db.init_db(connection)
    yield connection
    connection.close()


def test_second_run_same_day_sends_nothing_new(conn) -> None:
    registry.add_case(conn, "А07-12345/2025", "ООО Ромашка", "plaintiff")

    header = CaseHeader(
        case_number="А07-12345/2025",
        case_guid="guid-1",
        court="АС РБ",
        judge="Иванова",
        plaintiff_name="",
        plaintiff_inn="",
        defendant_name="",
        defendant_inn="",
        register_date=date(2026, 8, 1),
    )
    event = CaseEventData(
        event_type="Определение",
        event_date=date(2026, 8, 13),
        publish_date=date(2026, 8, 13),
        description="Назначено заседание",
        document_url=None,
    )
    card = CaseCardData(events=[event], hearings=[], is_finished=False)

    kad_client = FakeKadClient([header])
    card_fetcher = FakeCardFetcher({"guid-1": card})
    pochta_client = FakePochtaClient()
    telegram = FakeTelegram()

    summary1 = orchestrator.run_once(conn, kad_client, card_fetcher, pochta_client, telegram, default_claim_response_days=30)
    assert len(summary1.case_updates) == 1
    assert len(summary1.case_updates[0].new_events) == 1
    assert len(telegram.sent) == 1

    summary2 = orchestrator.run_once(conn, kad_client, card_fetcher, pochta_client, telegram, default_claim_response_days=30)
    assert summary2.case_updates == []
    assert len(telegram.sent) == 1  # no second send — nothing new, silence by default


def test_pochta_failure_does_not_block_kad_results(conn) -> None:
    registry.add_case(conn, "А07-1/2025", "ООО Ромашка", "plaintiff")
    registry.add_parcel(conn, "80082806838014", "Претензия №1", "ООО Ромашка")

    header = CaseHeader(
        case_number="А07-1/2025",
        case_guid="guid-1",
        court="АС РБ",
        judge="Иванова",
        plaintiff_name="",
        plaintiff_inn="",
        defendant_name="",
        defendant_inn="",
        register_date=date(2026, 8, 1),
    )
    event = CaseEventData(
        event_type="Определение", event_date=date(2026, 8, 13), publish_date=date(2026, 8, 13), description="Новое", document_url=None
    )
    card = CaseCardData(events=[event], hearings=[], is_finished=False)

    kad_client = FakeKadClient([header])
    card_fetcher = FakeCardFetcher({"guid-1": card})
    pochta_client = FakePochtaClient(fail=True)
    telegram = FakeTelegram()

    summary = orchestrator.run_once(conn, kad_client, card_fetcher, pochta_client, telegram, default_claim_response_days=30)
    assert summary.kad_ok is True
    assert len(summary.case_updates) == 1
    assert summary.pochta_ok is False
    assert telegram.sent  # still sent, because KAD had new content + pochta failure is itself notable


def test_document_with_url_gets_analyzed_and_deadline_computed(conn) -> None:
    from legal_monitor.doc_analyzer.schemas import DocumentAnalysis, DocumentType

    registry.add_case(conn, "А07-9/2025", "ООО Ромашка", "plaintiff")

    header = CaseHeader(
        case_number="А07-9/2025",
        case_guid="guid-9",
        court="АС РБ",
        judge="Иванова",
        plaintiff_name="",
        plaintiff_inn="",
        defendant_name="",
        defendant_inn="",
        register_date=date(2026, 8, 1),
    )
    event = CaseEventData(
        event_type="Решение",
        event_date=date(2026, 8, 13),
        publish_date=date(2026, 8, 13),
        description="Иск удовлетворён",
        document_url="https://kad.arbitr.ru/doc.pdf",
    )
    card = CaseCardData(events=[event], hearings=[], is_finished=False)

    kad_client = FakeKadClient([header])
    card_fetcher = FakeCardFetcher({"guid-9": card})
    pochta_client = FakePochtaClient()
    telegram = FakeTelegram()
    analysis = DocumentAnalysis(document_type=DocumentType.RESHENIE_OBSHEE, summary="Иск удовлетворён полностью.")
    doc_runner = FakeDocAnalysisRunner(analysis)

    summary = orchestrator.run_once(
        conn, kad_client, card_fetcher, pochta_client, telegram, default_claim_response_days=30, doc_analysis_runner=doc_runner
    )

    assert doc_runner.calls == 1
    event_display = summary.case_updates[0].new_events[0]
    assert event_display.analysis.summary == "Иск удовлетворён полностью."
    assert event_display.analysis.deadline == date(2026, 9, 12)  # +30 days, ст. 259 АПК РФ
    assert "259" in event_display.analysis.deadline_basis

    row = conn.execute("SELECT * FROM document_analysis").fetchone()
    assert row["document_type"] == "решение_обычное_производство"
    assert row["rule_deadline"] == "2026-09-12"

    # second run: event already seen, must not re-download/re-analyze
    summary2 = orchestrator.run_once(
        conn, kad_client, card_fetcher, pochta_client, telegram, default_claim_response_days=30, doc_analysis_runner=doc_runner
    )
    assert summary2.case_updates == []
    assert doc_runner.calls == 1
