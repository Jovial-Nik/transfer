"""Parses the response of POST /Kad/SearchInstances.

IMPORTANT — unverified against a live response, read before touching this file:
This module has not been exercised against a real, cookie-authenticated response
from kad.arbitr.ru (see docs/kad-endpoints.md for why). The project brief asserts
the endpoint returns HTML; independent knowledge of this site says it has
historically returned JSON. Rather than commit to either, this module detects
the actual shape of the response and parses accordingly, and raises loudly
(KadResponseFormatUnknown) if it recognises neither — see the module docstring
in exceptions.py for why that matters more than a best-effort guess.

Before relying on this in production: run `python -m legal_monitor.kad_client.capture_fixture`
(see docs/kad-endpoints.md) once real cookies are obtainable, save the raw response
into tests/fixtures/, and adjust whichever branch below turns out to be wrong.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

from bs4 import BeautifulSoup

from legal_monitor.kad_client.exceptions import KadResponseFormatUnknown


@dataclass(frozen=True)
class CaseHeader:
    case_number: str
    case_guid: str | None
    court: str
    judge: str
    plaintiff_name: str
    plaintiff_inn: str
    defendant_name: str
    defendant_inn: str
    register_date: date | None


def parse_search_response(raw_text: str, content_type: str) -> list[CaseHeader]:
    stripped = raw_text.strip()
    looks_like_json = "json" in content_type.lower() or stripped.startswith("{") or stripped.startswith("[")
    if looks_like_json:
        try:
            return _parse_json(stripped)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    if "<html" in stripped.lower() or "<table" in stripped.lower() or "<tr" in stripped.lower():
        return _parse_html(stripped)
    raise KadResponseFormatUnknown(f"unrecognised SearchInstances response, content-type={content_type!r}")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        return None


def _parse_json(text: str) -> list[CaseHeader]:
    data = json.loads(text)
    items = data.get("Result", {}).get("Items", []) if isinstance(data, dict) else data
    headers: list[CaseHeader] = []
    for item in items:
        courts = item.get("Courts") or []
        judges = item.get("Judges") or []
        plaintiffs = item.get("Plaintiffs") or []
        respondents = item.get("Respondents") or []
        headers.append(
            CaseHeader(
                case_number=item.get("CaseNumber", ""),
                case_guid=item.get("CaseId") or item.get("Id"),
                court=(courts[0].get("Name", "") if courts else ""),
                judge=(judges[0].get("Name", "") if judges else ""),
                plaintiff_name=(plaintiffs[0].get("Name", "") if plaintiffs else ""),
                plaintiff_inn=(plaintiffs[0].get("Inn", "") if plaintiffs else ""),
                defendant_name=(respondents[0].get("Name", "") if respondents else ""),
                defendant_inn=(respondents[0].get("Inn", "") if respondents else ""),
                register_date=_parse_date(item.get("DateRegister")),
            )
        )
    return headers


def _text(node) -> str:
    return node.get_text(strip=True) if node else ""


def _parse_html(html: str) -> list[CaseHeader]:
    soup = BeautifulSoup(html, "html.parser")
    headers: list[CaseHeader] = []
    for row in soup.select("tr.b-korpKadMainRow, tr.case-row, table#tableResult tr[data-caseid]"):
        case_link = row.select_one("a.num_case, a.case-number, td.num_case a")
        if case_link is None:
            continue
        case_number = _text(case_link)
        href = str(case_link.get("href", ""))
        case_guid = href.rstrip("/").rsplit("/", 1)[-1] if "/Card/" in href else None

        court = _text(row.select_one(".court, td.court"))
        judge = _text(row.select_one(".judge, td.judge"))

        plaintiff_cell = row.select_one(".plaintiff, td.plaintiff")
        defendant_cell = row.select_one(".respondent, td.respondent")
        plaintiff_name, plaintiff_inn = _split_name_inn(_text(plaintiff_cell))
        defendant_name, defendant_inn = _split_name_inn(_text(defendant_cell))

        date_cell = _text(row.select_one(".date, td.date"))
        headers.append(
            CaseHeader(
                case_number=case_number,
                case_guid=case_guid,
                court=court,
                judge=judge,
                plaintiff_name=plaintiff_name,
                plaintiff_inn=plaintiff_inn,
                defendant_name=defendant_name,
                defendant_inn=defendant_inn,
                register_date=_parse_date(date_cell) if date_cell else None,
            )
        )
    return headers


def _split_name_inn(text: str) -> tuple[str, str]:
    """'ООО "Ромашка" (ИНН 0276000000)' -> ('ООО "Ромашка"', '0276000000')"""
    if "ИНН" not in text:
        return text, ""
    name, _, tail = text.partition("(ИНН")
    inn = tail.strip(" )")
    return name.strip(), inn
