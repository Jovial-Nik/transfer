"""Case card scraping — https://kad.arbitr.ru/Card/{guid}.

STATUS: the AJAX endpoint the card page uses to load its events/hearings block
was never identified. The brief is explicit that this endpoint must be found
by recording real network traffic in a headful Playwright session against a
real case (see docs/kad-endpoints.md) and never guessed — and a real session
against kad.arbitr.ru could not be established from this sandbox (Chromium's
TLS handshake gets reset by the sandbox's own outbound proxy; see
cookie_service/service.py's module docstring for the diagnosis). That
reconnaissance step is therefore still open and belongs at the top of the
customer's punch list.

What ships here instead is the brief's own documented fallback: render the
card with Playwright and scrape the resulting DOM. It works regardless of
which internal endpoint the page calls, at the cost of one browser page load
per case (acceptable — the brief itself says so — for ~20 cases once a day).
The CSS selectors below are a best-effort guess at KAD's typical markup and
are UNVERIFIED against a live page. Expect to adjust them after the first
real run; `python -m legal_monitor.kad_client.card <guid>` dumps the raw
scraped structure for that purpose.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

from legal_monitor.core.models import CaseEventData, HearingData

logger = logging.getLogger(__name__)

CARD_URL_TEMPLATE = "https://kad.arbitr.ru/Card/{guid}"
CARD_LOAD_TIMEOUT_MS = 30000


class CaseCardData:
    def __init__(self, events: list[CaseEventData], hearings: list[HearingData], is_finished: bool) -> None:
        self.events = events
        self.hearings = hearings
        self.is_finished = is_finished


def _parse_ru_date(text: str) -> date | None:
    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if not match:
        return None
    d, m, y = match.groups()
    return date(int(y), int(m), int(d))


def _parse_ru_datetime(text: str) -> datetime | None:
    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\D+(\d{1,2}):(\d{2})", text)
    if not match:
        d = _parse_ru_date(text)
        return datetime(d.year, d.month, d.day) if d else None
    day, month, year, hour, minute = match.groups()
    return datetime(int(year), int(month), int(day), int(hour), int(minute))


async def fetch_card(guid: str, cookies: dict[str, str], user_agent: str, executable_path: str | None = None) -> CaseCardData:
    from playwright.async_api import async_playwright

    from legal_monitor.cookie_service.service import CHROMIUM_ARGS, WEBDRIVER_OVERRIDE_SCRIPT, _block_trackers

    async with async_playwright() as p:
        launch_kwargs: dict = {"headless": True, "args": CHROMIUM_ARGS}
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        browser = await p.chromium.launch(**launch_kwargs)
        try:
            context = await browser.new_context(
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                user_agent=user_agent,
                extra_http_headers={"Wasm-Support": "true"},
            )
            await context.add_init_script(WEBDRIVER_OVERRIDE_SCRIPT)
            await context.route("**/*", _block_trackers)
            await context.add_cookies(
                [{"name": k, "value": v, "domain": "kad.arbitr.ru", "path": "/"} for k, v in cookies.items()]
            )

            page = await context.new_page()
            await page.goto(CARD_URL_TEMPLATE.format(guid=guid), wait_until="networkidle", timeout=CARD_LOAD_TIMEOUT_MS)

            return await _scrape_page(page)
        finally:
            await browser.close()


async def _scrape_page(page) -> CaseCardData:
    events: list[CaseEventData] = []
    hearing_rows = await page.query_selector_all(".b-instanceEvents tr, .instance-events tr, .case-events tr")
    for row in hearing_rows:
        text = (await row.inner_text()).strip()
        if not text:
            continue
        event_date_el = await row.query_selector(".date, .event-date")
        desc_el = await row.query_selector(".content, .event-text, .desc")
        pdf_el = await row.query_selector("a[href$='.pdf']")

        event_date = _parse_ru_date(await event_date_el.inner_text()) if event_date_el else _parse_ru_date(text)
        description = (await desc_el.inner_text()).strip() if desc_el else text
        document_url = await pdf_el.get_attribute("href") if pdf_el else None
        event_type = description.split(".")[0][:120] if description else "Событие"

        events.append(
            CaseEventData(
                event_type=event_type,
                event_date=event_date,
                publish_date=event_date,
                description=description,
                document_url=document_url,
            )
        )

    hearings: list[HearingData] = []
    hearing_cal_rows = await page.query_selector_all(".b-hearings tr, .hearings-calendar tr, .case-hearings tr")
    for row in hearing_cal_rows:
        text = (await row.inner_text()).strip()
        if not text:
            continue
        court_el = await row.query_selector(".court")
        address_el = await row.query_selector(".address")
        room_el = await row.query_selector(".room, .hall")

        hearings.append(
            HearingData(
                hearing_at=_parse_ru_datetime(text),
                court=(await court_el.inner_text()).strip() if court_el else "",
                address=(await address_el.inner_text()).strip() if address_el else "",
                room=(await room_el.inner_text()).strip() if room_el else "",
            )
        )

    page_text = (await page.inner_text("body")).lower()
    is_finished = any(marker in page_text for marker in ("дело завершено", "производство по делу прекращено", "решение вступило в законную силу"))

    return CaseCardData(events=events, hearings=hearings, is_finished=is_finished)


async def _cli(guid: str) -> None:
    import json
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO)
    from legal_monitor.config import get_settings
    from legal_monitor.cookie_service.service import CookieService

    settings = get_settings()
    service = CookieService(cache_path=settings.cookies_cache_path, user_agent=settings.kad_user_agent)
    cookies = service.get_cookies()
    card = await fetch_card(guid, cookies, settings.kad_user_agent)
    print(
        json.dumps(
            {
                "events": [e.__dict__ for e in card.events],
                "hearings": [h.__dict__ for h in card.hearings],
                "is_finished": card.is_finished,
            },
            default=str,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) != 2:
        print("usage: python -m legal_monitor.kad_client.card <case_guid>", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(_cli(sys.argv[1]))
