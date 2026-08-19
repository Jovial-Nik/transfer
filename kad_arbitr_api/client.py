import asyncio
import logging

from kad_arbitr_api import parser
from kad_arbitr_api.browser import KadBrowser, check_for_captcha
from kad_arbitr_api.config import settings
from kad_arbitr_api.models import CaseDetails, CaseDocument, SearchParams, SearchResult

logger = logging.getLogger(__name__)

# kad.arbitr.ru не проставляет полям формы поиска стабильные id (у части их
# вообще нет), поэтому поля идентифицируются по уникальному placeholder.
FORM_FIELD_MAP = {
    "participant": "textarea[placeholder='название, ИНН или ОГРН']",
    "judge": "input[placeholder='фамилия судьи']",
    "court": "input[placeholder='название суда']",
    "case_number": "input[placeholder='например, А50-5568/08']",
}
# Оба поля дат имеют одинаковый placeholder "дд.мм.гггг" — различаются
# только порядком на странице (первое - "с", второе - "по").
DATE_PLACEHOLDER_SELECTOR = "input[placeholder='дд.мм.гггг']"


class KadArbitrClient:
    def __init__(self, browser: KadBrowser) -> None:
        self._browser = browser

    async def search(self, params: SearchParams) -> SearchResult:
        async with self._browser.lock():
            page = await self._browser.new_page()
            try:
                await page.goto(settings.base_url)
                await check_for_captcha(page)

                for field, selector in FORM_FIELD_MAP.items():
                    value = getattr(params, field)
                    if value and await page.locator(selector).count():
                        await page.fill(selector, value)

                date_inputs = page.locator(DATE_PLACEHOLDER_SELECTOR)
                if params.date_from and await date_inputs.count() > 0:
                    await date_inputs.nth(0).fill(params.date_from)
                if params.date_to and await date_inputs.count() > 1:
                    await date_inputs.nth(1).fill(params.date_to)

                await page.click("#b-form-submit")
                await page.wait_for_selector("#b-cases", timeout=settings.navigation_timeout_ms)

                if params.page > 1:
                    await page.click(f"a[href='#page{params.page}']")
                    await page.wait_for_timeout(int(settings.request_delay_seconds * 1000))

                await check_for_captcha(page)
                html = await page.content()

                items = parser.parse_search_results(html)
                next_page = parser.has_next_page(html, params.page)
                return SearchResult(page=params.page, items=items, has_next_page=next_page)
            finally:
                await page.close()
                await asyncio.sleep(settings.request_delay_seconds)

    async def get_case(self, case_id: str) -> CaseDetails:
        async with self._browser.lock():
            page = await self._browser.new_page()
            try:
                await page.goto(f"{settings.base_url}/Card/{case_id}")
                await page.wait_for_load_state("networkidle")
                await check_for_captcha(page)
                html = await page.content()
                return parser.parse_case_card(html, case_id)
            finally:
                await page.close()
                await asyncio.sleep(settings.request_delay_seconds)

    async def list_documents(self, case_id: str) -> list[CaseDocument]:
        return (await self.get_case(case_id)).documents

    async def download_document(self, file_url: str) -> tuple[bytes, str]:
        """Возвращает (содержимое файла, content-type)."""
        async with self._browser.lock():
            page = await self._browser.new_page()
            try:
                response = await page.goto(file_url)
                if response is None:
                    raise RuntimeError(f"Не удалось получить документ: {file_url}")
                await check_for_captcha(page)
                body = await response.body()
                content_type = response.headers.get("content-type", "application/pdf")
                return body, content_type
            finally:
                await page.close()
                await asyncio.sleep(settings.request_delay_seconds)
