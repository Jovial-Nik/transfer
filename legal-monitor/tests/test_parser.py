from pathlib import Path

from legal_monitor.kad_client.parser import parse_search_response

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_html_response() -> None:
    html = (FIXTURES / "kad_search_synthetic.html").read_text(encoding="utf-8")
    headers = parse_search_response(html, content_type="text/html; charset=utf-8")
    assert len(headers) == 2
    first = headers[0]
    assert first.case_number == "А07-12345/2025"
    assert first.case_guid == "a1b2c3d4"
    assert first.court == "Арбитражный суд Республики Башкортостан"
    assert first.judge == "Иванова И.И."
    assert first.plaintiff_name == 'ООО "Ромашка"'
    assert first.plaintiff_inn == "0276000000"
    assert first.defendant_inn == "0264000001"
    assert first.register_date is not None and first.register_date.isoformat() == "2026-08-13"


def test_parses_json_response() -> None:
    raw = (FIXTURES / "kad_search_synthetic.json").read_text(encoding="utf-8")
    headers = parse_search_response(raw, content_type="application/json; charset=utf-8")
    assert len(headers) == 2
    second = headers[1]
    assert second.case_number == "А40-67890/2025"
    assert second.case_guid == "e5f6a7b8"
    assert second.defendant_name == 'ООО "Лабторг"'


def test_json_detected_without_content_type_header() -> None:
    raw = (FIXTURES / "kad_search_synthetic.json").read_text(encoding="utf-8")
    headers = parse_search_response(raw, content_type="")
    assert len(headers) == 2
