import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    base_url: str = os.environ.get("KAD_BASE_URL", "https://kad.arbitr.ru")
    headless: bool = os.environ.get("KAD_HEADLESS", "1") != "0"
    # kad.arbitr.ru banит слишком частые запросы одним браузерным профилем -
    # между операциями выдерживается пауза.
    request_delay_seconds: float = float(os.environ.get("KAD_REQUEST_DELAY", "1.5"))
    navigation_timeout_ms: int = int(os.environ.get("KAD_NAV_TIMEOUT_MS", "30000"))
    # Одна и та же вкладка используется для всех запросов, чтобы не плодить
    # новые браузерные сессии (это быстрее и меньше похоже на бота).
    user_agent: str = os.environ.get(
        "KAD_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    )
    # Путь к файлу с cookies/localStorage сессии, пройденной человеком в
    # обычном браузере (см. kad_arbitr_api/import_cookies.py). Без него
    # запросы будут распознаны как автоматизированные и молча отклонены
    # антибот-защитой сайта (см. README).
    storage_state_path: str = os.environ.get("KAD_STORAGE_STATE", "kad_storage_state.json")


settings = Settings()
