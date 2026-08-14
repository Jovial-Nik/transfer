"""Fetches and caches the pr_fp/wasm cookie pair kad.arbitr.ru's anti-bot layer
(DDoS-Guard + a WASM challenge) requires. A real browser is the only thing that
can solve the challenge; everything downstream (kad_client) reuses the cookies
over plain httpx until they stop working.

NOT LIVE-VERIFIED: in the sandbox this was built in, Chromium's TLS ClientHello
gets reset by the sandbox's own outbound TLS-intercepting proxy before it ever
reaches kad.arbitr.ru (confirmed via chrome --log-net-log: SOCKET_READ_ERROR
net_error=-101/ECONNRESET immediately after the ClientHello — httpx/curl through
the same proxy work fine, so this is a proxy/Chromium TLS compatibility gap
specific to the sandbox, not a kad.arbitr.ru block). The customer's own server
has no such proxy in front of it. Run this module standalone
(`python -m legal_monitor.cookie_service`) as the very first real-world check,
before trusting anything else in this project — see docs/kad-endpoints.md.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

KAD_URL = "https://kad.arbitr.ru/"
REQUIRED_COOKIES = ("pr_fp", "wasm")
MIN_FORCE_REFRESH_INTERVAL_SECONDS = 60
COOKIE_WAIT_MAX_SECONDS = 10

BLOCKED_HOST_FRAGMENTS = ("yandex", "mail.ru", "vk.com", "google-analytics", "googletagmanager")

CHROMIUM_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--enable-features=WebAssembly",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--window-size=1280,720",
]

WEBDRIVER_OVERRIDE_SCRIPT = "Object.defineProperty(navigator, 'webdriver', {get: () => false});"


class CookieFetchFailed(Exception):
    pass


@dataclass
class CookieCache:
    cookies: dict[str, str]
    fetched_at: float

    def has_required(self) -> bool:
        return all(name in self.cookies for name in REQUIRED_COOKIES)


class CookieService:
    def __init__(self, cache_path: Path, user_agent: str, executable_path: str | None = None) -> None:
        self.cache_path = cache_path
        self.user_agent = user_agent
        self.executable_path = executable_path

    def get_cookies(self, force: bool = False) -> dict[str, str]:
        """Returns a cookie dict. On any failure to refresh, falls back to the
        last known-good cache rather than raising, unless there is no cache at all."""
        cached = self._load_cache()

        if not force and cached is not None and cached.has_required():
            return cached.cookies

        if force and cached is not None:
            age = time.time() - cached.fetched_at
            if age < MIN_FORCE_REFRESH_INTERVAL_SECONDS:
                logger.warning(
                    "cookie refresh requested %.0fs after the last one (min %ds) — reusing cache instead",
                    age,
                    MIN_FORCE_REFRESH_INTERVAL_SECONDS,
                )
                return cached.cookies

        try:
            fresh = asyncio.run(self._fetch_via_browser())
        except Exception:
            logger.exception("cookie refresh via Playwright failed")
            if cached is not None:
                logger.warning("falling back to cached cookies fetched at %s", cached.fetched_at)
                return cached.cookies
            raise CookieFetchFailed("no cached cookies available and the browser fetch failed")

        self._save_cache(fresh)
        return fresh

    def _load_cache(self) -> CookieCache | None:
        if not self.cache_path.exists():
            return None
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return CookieCache(cookies=data["cookies"], fetched_at=data["fetched_at"])
        except (json.JSONDecodeError, KeyError, OSError):
            logger.warning("cookie cache at %s is unreadable, ignoring it", self.cache_path)
            return None

    def _save_cache(self, cookies: dict[str, str]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"cookies": cookies, "fetched_at": time.time()}
        self.cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    async def _fetch_via_browser(self) -> dict[str, str]:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            launch_kwargs: dict = {"headless": True, "args": CHROMIUM_ARGS}
            if self.executable_path:
                launch_kwargs["executable_path"] = self.executable_path
            browser = await p.chromium.launch(**launch_kwargs)
            try:
                context = await browser.new_context(
                    locale="ru-RU",
                    timezone_id="Europe/Moscow",
                    user_agent=self.user_agent,
                    viewport={"width": 1280, "height": 720},
                    extra_http_headers={"Wasm-Support": "true"},
                )
                await context.add_init_script(WEBDRIVER_OVERRIDE_SCRIPT)
                await context.route("**/*", _block_trackers)

                page = await context.new_page()
                await page.goto(KAD_URL, wait_until="domcontentloaded", timeout=30000)

                cookies = await self._wait_for_required_cookies(context)
                return cookies
            finally:
                await browser.close()

    @staticmethod
    async def _wait_for_required_cookies(context) -> dict[str, str]:
        delay = 0.5
        elapsed = 0.0
        cookies_by_name: dict[str, str] = {}
        while elapsed < COOKIE_WAIT_MAX_SECONDS:
            raw_cookies = await context.cookies()
            cookies_by_name = {c["name"]: c["value"] for c in raw_cookies}
            if all(name in cookies_by_name for name in REQUIRED_COOKIES):
                return cookies_by_name
            await asyncio.sleep(delay)
            elapsed += delay
            delay = min(delay * 2, COOKIE_WAIT_MAX_SECONDS - elapsed) if elapsed < COOKIE_WAIT_MAX_SECONDS else 0

        missing = [n for n in REQUIRED_COOKIES if n not in cookies_by_name]
        raise CookieFetchFailed(f"required cookies not present after {COOKIE_WAIT_MAX_SECONDS}s: {missing}")


async def _block_trackers(route) -> None:
    if any(fragment in route.request.url for fragment in BLOCKED_HOST_FRAGMENTS):
        await route.abort()
    else:
        await route.continue_()


def _cli() -> None:
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from legal_monitor.config import get_settings

    settings = get_settings()
    service = CookieService(cache_path=settings.cookies_cache_path, user_agent=settings.kad_user_agent)
    force = "--force" in sys.argv
    cookies = service.get_cookies(force=force)
    print(json.dumps(cookies, ensure_ascii=False, indent=2))
    missing = [n for n in REQUIRED_COOKIES if n not in cookies]
    if missing:
        print(f"WARNING: missing required cookies: {missing}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
