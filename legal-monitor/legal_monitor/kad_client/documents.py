"""Downloads a document PDF from KAD using the same cookies as everything else.

UNVERIFIED — no real document_url was ever obtained (see docs/kad-endpoints.md).
KAD document links may require a different cookie set, a signed/expiring token,
or point through a redirect; adjust once a real URL is available to test against.
"""

from __future__ import annotations

import httpx


class DocumentDownloadFailed(Exception):
    pass


def download_document(url: str, cookies: dict[str, str], user_agent: str, timeout: float = 30.0) -> bytes:
    try:
        response = httpx.get(url, cookies=cookies, headers={"user-agent": user_agent}, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise DocumentDownloadFailed(f"{url}: {exc}") from exc
    return response.content
