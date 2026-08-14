from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    pochta_login: str = ""
    pochta_password: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"

    kad_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    db_path: Path = Path("./data/monitor.db")
    log_level: str = "INFO"
    default_claim_response_days: int = 30
    cookies_cache_path: Path = Path("./data/cookies_cache.json")


def get_settings() -> Settings:
    return Settings()
