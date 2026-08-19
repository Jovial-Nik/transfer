import httpx

from kad_arbitr_api.config import settings
from kad_arbitr_api.models import LegalCasesQuery, LegalCasesResult


class OfdataError(Exception):
    """ofdata.ru вернул ошибку (неверный ключ, исчерпан баланс, неверные параметры и т.п.)."""


class OfdataClient:
    def __init__(self) -> None:
        if not settings.ofdata_api_key:
            raise RuntimeError(
                "Не задан OFDATA_API_KEY. Получите ключ на https://ofdata.ru "
                "и передайте его через переменную окружения OFDATA_API_KEY."
            )
        self._client = httpx.AsyncClient(
            base_url=settings.ofdata_base_url, timeout=settings.request_timeout_seconds
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def legal_cases(self, query: LegalCasesQuery) -> LegalCasesResult:
        params = query.model_dump(exclude_none=True)
        params["key"] = settings.ofdata_api_key

        response = await self._client.get("/legal-cases", params=params)
        payload = response.json()

        meta = payload.get("meta", {})
        if meta.get("status") != "ok" and response.status_code != 200:
            raise OfdataError(meta.get("message") or f"ofdata.ru вернул статус {response.status_code}")
        if meta.get("status") not in (None, "ok"):
            raise OfdataError(meta.get("message") or "ofdata.ru вернул ошибку")

        data = payload.get("data")
        if not data:
            raise OfdataError("ofdata.ru не вернул данные по указанной компании/ИП")

        return LegalCasesResult.model_validate(data)


ofdata_client: OfdataClient | None = None
