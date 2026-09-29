import os

from dotenv import load_dotenv

load_dotenv()


def _ids(value: str) -> set[int]:
    return {int(part) for part in value.replace(" ", "").split(",") if part}


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TMDB_TOKEN = os.getenv("TMDB_TOKEN", "")
TMDB_REGION = os.getenv("TMDB_REGION", "RU")
SHIKIMORI_URL = os.getenv("SHIKIMORI_URL", "https://shikimori.io").rstrip("/")
DB_PATH = os.getenv("DB_PATH", "data/miniapp.db")
ALLOWED_USER_IDS = _ids(os.getenv("ALLOWED_USER_IDS", ""))
DEV_USER_ID = int(os.getenv("DEV_USER_ID", "0") or 0)
INIT_DATA_MAX_AGE = int(os.getenv("INIT_DATA_MAX_AGE", "86400"))
