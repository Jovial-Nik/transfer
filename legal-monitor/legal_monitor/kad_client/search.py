"""POST /Kad/SearchInstances — the only bulk endpoint we use for case headers.
One POST carries every tracked case number (paginated in batches of 25), so a
watchlist of 20 cases costs one request, not twenty.
"""

from __future__ import annotations

import logging

import httpx

from legal_monitor.cookie_service.service import CookieFetchFailed, CookieService
from legal_monitor.kad_client.exceptions import KadResponseFormatUnknown, KadUnavailable
from legal_monitor.kad_client.parser import CaseHeader, parse_search_response

logger = logging.getLogger(__name__)

SEARCH_URL = "https://kad.arbitr.ru/Kad/SearchInstances"
PAGE_SIZE = 25


def _headers(user_agent: str) -> dict[str, str]:
    return {
        "accept": "*/*",
        "accept-language": "ru,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "origin": "https://kad.arbitr.ru",
        "referer": "https://kad.arbitr.ru",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-date-format": "iso",
        "x-requested-with": "XMLHttpRequest",
        "user-agent": user_agent,
    }


def _payload(case_numbers: list[str], page: int) -> dict:
    return {
        "Page": page,
        "Count": PAGE_SIZE,
        "Courts": [],
        "DateFrom": None,
        "DateTo": None,
        "Sides": [],
        "Judges": [],
        "CaseNumbers": case_numbers,
        "WithVKSInstances": False,
    }


class KadClient:
    def __init__(
        self,
        cookie_service: CookieService,
        user_agent: str,
        http_client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._cookie_service = cookie_service
        self._user_agent = user_agent
        self._http_client = http_client or httpx.Client(timeout=timeout)

    def search(self, case_numbers: list[str]) -> list[CaseHeader]:
        """Fetches headers for every case number, paginating in batches of 25.
        Raises KadUnavailable if the site still rejects us after one cookie
        refresh — callers must not retry further within the same run."""
        if not case_numbers:
            return []

        results: list[CaseHeader] = []
        for start in range(0, len(case_numbers), PAGE_SIZE):
            batch = case_numbers[start : start + PAGE_SIZE]
            results.extend(self._search_batch(batch))
        return results

    def _search_batch(self, batch: list[str]) -> list[CaseHeader]:
        try:
            cookies = self._cookie_service.get_cookies(force=False)
            response = self._post(batch, cookies)

            if response.status_code == 451:
                logger.warning("KAD returned 451 (cookies likely expired) — refreshing cookies and retrying once")
                cookies = self._cookie_service.get_cookies(force=True)
                response = self._post(batch, cookies)
        except CookieFetchFailed as exc:
            raise KadUnavailable(f"не удалось получить cookies: {exc}") from exc

        if response.status_code == 451:
            logger.error("KAD returned 451 again after a cookie refresh — giving up on this run")
            raise KadUnavailable("HTTP 451 после обновления cookies")

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise KadUnavailable(f"HTTP {response.status_code} от KAD") from exc

        logger.info("KAD search: %d case number(s) requested, HTTP %d", len(batch), response.status_code)
        try:
            return parse_search_response(response.text, response.headers.get("content-type", ""))
        except KadResponseFormatUnknown as exc:
            raise KadUnavailable(str(exc)) from exc

    def _post(self, batch: list[str], cookies: dict[str, str]) -> httpx.Response:
        return self._http_client.post(
            SEARCH_URL,
            json=_payload(batch, page=1),
            headers=_headers(self._user_agent),
            cookies=cookies,
        )
