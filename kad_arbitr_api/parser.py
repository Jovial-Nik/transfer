import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from kad_arbitr_api.config import settings
from kad_arbitr_api.models import CaseDetails, CaseDocument, CaseParty, CaseSummary

CASE_ID_RE = re.compile(r"/Card/([0-9a-fA-F-]{36})")


def _text(node) -> str | None:
    if node is None:
        return None
    value = node.get_text(strip=True)
    return value or None


def parse_search_results(html: str) -> list[CaseSummary]:
    """Разбирает таблицу результатов поиска (контейнер id="b-cases")."""
    soup = BeautifulSoup(html, "lxml")
    container = soup.find(id="b-cases")
    if container is None:
        return []

    results: list[CaseSummary] = []
    for row in container.select("tr"):
        case_link = row.find("a", class_="num_case")
        if case_link is None or not case_link.get("href"):
            continue

        match = CASE_ID_RE.search(case_link["href"])
        if match is None:
            continue
        case_id = match.group(1)
        case_url = urljoin(settings.base_url, case_link["href"])

        court_node = row.find(class_="court")
        judge_node = row.find(class_="judge")
        date_node = row.find(class_="b-date")

        plaintiffs: list[str] = []
        defendants: list[str] = []
        plaintiff_block = row.find(class_="plaintiff")
        if plaintiff_block is not None:
            names = plaintiff_block.find_all(class_="js-rolloverHtml") or [plaintiff_block]
            plaintiffs = [t for n in names if (t := _text(n))]
        defendant_block = row.find(class_="respondent")
        if defendant_block is not None:
            names = defendant_block.find_all(class_="js-rolloverHtml") or [defendant_block]
            defendants = [t for n in names if (t := _text(n))]

        results.append(
            CaseSummary(
                case_id=case_id,
                case_number=_text(case_link) or "",
                court=_text(court_node),
                judge=_text(judge_node),
                plaintiffs=plaintiffs,
                defendants=defendants,
                registration_date=_text(date_node),
                url=case_url,
            )
        )
    return results


def has_next_page(html: str, current_page: int) -> bool:
    soup = BeautifulSoup(html, "lxml")
    pager = soup.find(class_="b-pagination")
    if pager is None:
        return False
    return any(
        link.get_text(strip=True) == str(current_page + 1) for link in pager.find_all("a")
    )


def parse_case_card(html: str, case_id: str) -> CaseDetails:
    soup = BeautifulSoup(html, "lxml")
    url = urljoin(settings.base_url, f"/Card/{case_id}")

    case_number_node = soup.find(class_="case-number") or soup.find(class_="b-case-number")
    court_node = soup.find(class_="case_type") or soup.find(class_="court")
    judge_node = soup.find(class_="judge")
    case_type_node = soup.find(class_="casetype")

    parties: list[CaseParty] = []
    for party_block in soup.select(".persons-wrap .participant, .b-party"):
        role_node = party_block.find(class_="role") or party_block.find(class_="p_type")
        name_node = party_block.find(class_="js-rolloverHtml") or party_block.find(class_="name")
        role = _text(role_node)
        name = _text(name_node)
        if name:
            parties.append(CaseParty(role=role or "участник", name=name))

    documents: list[CaseDocument] = []
    for idx, link in enumerate(soup.select("a[href$='.pdf'], a.js-pdf")):
        href = link.get("href")
        if not href:
            continue
        file_url = urljoin(settings.base_url, href)
        title = _text(link) or f"Документ {idx + 1}"
        row = link.find_parent(class_="instance") or link.find_parent("tr") or link.parent
        date_node = row.find(class_="date") if row else None
        instance_node = row.find(class_="instance-name") if row else None
        documents.append(
            CaseDocument(
                document_id=f"{case_id}:{idx}",
                title=title,
                document_date=_text(date_node),
                instance=_text(instance_node),
                file_url=file_url,
            )
        )

    return CaseDetails(
        case_id=case_id,
        case_number=_text(case_number_node) or "",
        court=_text(court_node),
        judge=_text(judge_node),
        case_type=_text(case_type_node),
        parties=parties,
        documents=documents,
        url=url,
    )
