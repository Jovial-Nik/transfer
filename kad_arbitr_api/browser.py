import asyncio
import logging

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from kad_arbitr_api.config import settings

logger = logging.getLogger(__name__)


class CaptchaDetected(Exception):
    """kad.arbitr.ru показал капчу/страницу проверки вместо ожидаемого контента."""


class KadBrowser:
    """
    Обёртка над одним переиспользуемым браузерным контекстом Playwright.

    kad.arbitr.ru отдаёт данные только при обычной браузерной навигации
    (прямые HTTP-запросы к его внутренним ручкам блокируются защитой от
    ботов), поэтому вместо requests используется headless-браузер. Все
    операции сериализуются одной блокировкой: параллельные вкладки с одного
    IP резко повышают шанс словить капчу.
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=settings.headless)
        self._context = await self._browser.new_context(user_agent=settings.user_agent)
        self._context.set_default_navigation_timeout(settings.navigation_timeout_ms)

    async def stop(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        if self._context is None:
            raise RuntimeError("KadBrowser не запущен, вызовите start() перед использованием")
        return await self._context.new_page()

    def lock(self) -> asyncio.Lock:
        return self._lock


kad_browser = KadBrowser()


async def check_for_captcha(page: Page) -> None:
    """
    kad.arbitr.ru держит в разметке скрытый JS-шаблон капчи
    (`<script type="x-jquery-tmpl" id="pravocaptcha_template">`) всегда, даже
    когда капча не показана, — поэтому искать подстроку "captcha" в HTML
    нельзя (ложные срабатывания на каждой странице). Реальная капча
    определяется по тому, что видимый контейнер `.b-pravocaptcha-modal_wrapper`
    (пустой в норме) действительно заполнен содержимым.
    """
    count = await page.locator(".b-pravocaptcha-modal_wrapper *").count()
    if count > 0:
        raise CaptchaDetected(
            "kad.arbitr.ru запросил проверку на робота (капчу). "
            "Автоматическое решение капчи не поддерживается — снизьте частоту "
            "запросов и повторите попытку позже."
        )
