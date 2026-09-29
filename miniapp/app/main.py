import asyncio
import logging
import random
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .shikimori import ShikimoriClient
from .storage import STATUSES, Storage
from .telegram_auth import AuthError, validate_init_data
from .tmdb import TmdbClient

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
MediaType = Literal["all", "anime", "movie", "tv"]

shikimori = ShikimoriClient(config.SHIKIMORI_URL)
tmdb = TmdbClient(config.TMDB_TOKEN, config.TMDB_REGION)
storage = Storage(config.DB_PATH)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await shikimori.close()
    await tmdb.close()


app = FastAPI(title="Media Mini App", lifespan=lifespan)


def current_user(authorization: str = Header(default="")) -> int:
    if authorization.startswith("tma "):
        try:
            user = validate_init_data(authorization[4:], config.BOT_TOKEN, config.INIT_DATA_MAX_AGE)
        except AuthError as error:
            raise HTTPException(401, f"Ошибка авторизации: {error}")
        user_id = int(user["id"])
    elif config.DEV_USER_ID:
        user_id = config.DEV_USER_ID
    else:
        raise HTTPException(401, "Откройте приложение через Telegram")

    if config.ALLOWED_USER_IDS and user_id not in config.ALLOWED_USER_IDS:
        raise HTTPException(403, "Доступ закрыт")
    return user_id


async def _safe(coroutine) -> list:
    try:
        return await coroutine
    except httpx.HTTPError as error:
        logging.warning("Каталог недоступен: %s", error)
        return []


def _interleave(*groups: list) -> list:
    result = []
    for index in range(max((len(group) for group in groups), default=0)):
        result.extend(group[index] for group in groups if index < len(group))
    return result


def _sources(media_type: MediaType) -> list[str]:
    types = ["anime", "movie", "tv"] if media_type == "all" else [media_type]
    return [t for t in types if t == "anime" or tmdb.enabled]


def _parse_key(key: str) -> tuple[str, int]:
    media_type, _, raw_id = key.partition(":")
    if media_type not in ("anime", "movie", "tv") or not raw_id.isdigit():
        raise HTTPException(400, "Неверный ключ")
    return media_type, int(raw_id)


@app.get("/api/config")
def get_config(_: int = Depends(current_user)):
    return {"sources": _sources("all"), "statuses": STATUSES}


@app.get("/api/search")
async def search(q: str = Query(min_length=1, max_length=100), type: MediaType = "all", _: int = Depends(current_user)):
    sources = _sources(type)
    tasks = []
    if "anime" in sources:
        tasks.append(_safe(shikimori.search(q)))
    if type == "all" and tmdb.enabled:
        tasks.append(_safe(tmdb.search(q)))
    elif type in ("movie", "tv") and tmdb.enabled:
        tasks.append(_safe(tmdb.search(q, type)))
    return {"items": _interleave(*await asyncio.gather(*tasks))}


@app.get("/api/trending")
async def trending(type: MediaType = "all", _: int = Depends(current_user)):
    tasks = [
        _safe(shikimori.trending()) if source == "anime" else _safe(tmdb.trending(source))
        for source in _sources(type)
    ]
    return {"items": _interleave(*await asyncio.gather(*tasks))}


@app.get("/api/random")
async def random_item(type: MediaType = "all", _: int = Depends(current_user)):
    sources = _sources(type)
    if not sources:
        raise HTTPException(404, "Источник не настроен")
    source = random.choice(sources)
    try:
        item = await (shikimori.random() if source == "anime" else tmdb.random(source))
    except httpx.HTTPError:
        raise HTTPException(502, "Каталог недоступен")
    if not item:
        raise HTTPException(404, "Ничего не нашлось")
    return item


@app.get("/api/media/{key}")
async def media(key: str, user_id: int = Depends(current_user)):
    media_type, item_id = _parse_key(key)
    if media_type != "anime" and not tmdb.enabled:
        raise HTTPException(404, "TMDB не настроен")
    try:
        item = await (shikimori.details(item_id) if media_type == "anime" else tmdb.details(media_type, item_id))
    except httpx.HTTPStatusError as error:
        raise HTTPException(404 if error.response.status_code == 404 else 502, "Не удалось загрузить")
    except httpx.HTTPError:
        raise HTTPException(502, "Каталог недоступен")
    item["entry"] = storage.get(user_id, key)
    return item


class EntryIn(BaseModel):
    title: str | None = None
    poster: str | None = None
    year: str | None = None
    status: Literal[STATUSES]  # type: ignore[valid-type]
    score: int | None = Field(default=None, ge=1, le=10)
    progress: int | None = Field(default=None, ge=0)


@app.get("/api/list")
def get_list(status: str | None = None, user_id: int = Depends(current_user)):
    return {"items": storage.list(user_id, status), "stats": storage.stats(user_id)}


@app.put("/api/list/{key}")
def put_entry(key: str, entry: EntryIn, user_id: int = Depends(current_user)):
    media_type, _ = _parse_key(key)
    return storage.upsert(user_id, {"key": key, "type": media_type, **entry.model_dump()})


@app.delete("/api/list/{key}")
def delete_entry(key: str, user_id: int = Depends(current_user)):
    _parse_key(key)
    storage.delete(user_id, key)
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
