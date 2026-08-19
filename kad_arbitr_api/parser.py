import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from kad_arbitr_api.config import settings
from kad_arbitr_api.models import CaseDetails, CaseDocument, CaseParty, CaseSummary

CASE_ID_RE = re.compile(r"/Card/([0-9a-fA-F-]{36})")


def _text(node) -> str | None:
    if node is None:
        return None
    # Разделитель обязателен: в исходном HTML между соседними тегами часто
    # нет пробельных символов, и без separator их текст склеивается
    # (например, ФИО + "Данные скрыты" + ИНН превращаются в одну строку).
    value = node.get_text(separator=" ", strip=True)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def _rollover_names(block) -> list[str]:
    """
    Извлекает видимые имена участников дела из блока plaintiff/respondent.

    Каждое имя обёрнуто в span.js-rollover, внутри которого спрятан ещё один
    span.js-rolloverHtml (display:none) с полным ФИО + адресом + ИНН для
    всплывающей подсказки. Нужен только видимый текст - первая строка до
    вложенного тултипа.
    """
    if block is None:
        return []
    spans = block.find_all(class_="js-rollover") or [block]
    names = []
    for span in spans:
        name = next(span.stripped_strings, None)
        if name:
            names.append(name)
    return names


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
        # У kad.arbitr.ru нет отдельной колонки "дата регистрации" в
        # компактной таблице результатов - единственная дата, которая
        # изредка встречается, это дата заседания по делам о банкротстве
        # (значок "bankruptcy"), поэтому это не всегда точная дата
        # регистрации дела, а лучшее доступное приближение.
        bankruptcy_node = row.find(class_="bankruptcy")

        court_text = _text(court_node)
        judge_text = _text(judge_node)
        # class="judge" - это вложенный элемент внутри ячейки с судом, из-за
        # этого имя судьи попадает и в текст суда. Раз оно уже извлечено
        # отдельно, вырезаем его из начала строки с судом.
        if court_text and judge_text and court_text.startswith(judge_text):
            court_text = court_text[len(judge_text):].strip() or None

        registration_date = None
        if bankruptcy_node is not None and bankruptcy_node.get("title"):
            registration_date = bankruptcy_node["title"].split()[0]

        plaintiffs = _rollover_names(row.find(class_="plaintiff"))
        defendants = _rollover_names(row.find(class_="respondent"))

        results.append(
            CaseSummary(
                case_id=case_id,
                case_number=_text(case_link) or "",
                court=court_text,
                judge=judge_text,
                plaintiffs=plaintiffs,
                defendants=defendants,
                registration_date=registration_date,
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
