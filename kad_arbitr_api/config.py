import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    ofdata_base_url: str = os.environ.get("OFDATA_BASE_URL", "https://api.ofdata.ru/v2")
    ofdata_api_key: str = os.environ.get("OFDATA_API_KEY", "")
    request_timeout_seconds: float = float(os.environ.get("OFDATA_TIMEOUT", "15"))


settings = Settings()
