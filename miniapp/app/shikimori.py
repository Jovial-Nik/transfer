import re

import httpx

from .cache import TTLCache

KINDS = {
    "tv": "TV-сериал",
    "movie": "Фильм",
    "ova": "OVA",
    "ona": "ONA",
    "special": "Спешл",
    "tv_special": "TV-спешл",
    "music": "Клип",
    "pv": "Проморолик",
    "cm": "Реклама",
}
STATUSES = {"anons": "Анонс", "ongoing": "Онгоинг", "released": "Вышло"}
YOUTUBE_ID = re.compile(r"(?:v=|youtu\.be/|embed/)([\w-]{11})")
BBCODE = re.compile(r"\[/?[^\]]+\]")


class ShikimoriClient:
    def __init__(self, base_url: str):
        self._base_url = base_url
        self._client = httpx.AsyncClient(
            base_url=f"{base_url}/api",
            headers={"User-Agent": "media-miniapp"},
            timeout=15,
            follow_redirects=True,
        )
        self._cache = TTLCache()

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None):
        cache_key = (path, tuple(sorted((params or {}).items())))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        data = response.json()
        self._cache.set(cache_key, data)
        return data

    def _image(self, image: dict | None) -> str | None:
        path = (image or {}).get("original") or (image or {}).get("preview")
        if not path or "missing_" in path:
            return None
        return path if path.startswith("http") else f"{self._base_url}{path}"

    def _card(self, anime: dict) -> dict:
        aired_on = anime.get("aired_on") or ""
        return {
            "key": f"anime:{anime['id']}",
            "type": "anime",
            "title": anime.get("russian") or anime.get("name"),
            "original_title": anime.get("name"),
            "poster": self._image(anime.get("image")),
            "year": aired_on[:4] or None,
            "score": float(anime["score"]) if anime.get("score") not in (None, "0.0") else None,
            "kind": KINDS.get(anime.get("kind"), anime.get("kind")),
        }

    async def search(self, query: str, limit: int = 20) -> list[dict]:
        items = await self._get("/animes", {"search": query, "limit": limit, "order": "popularity"})
        return [self._card(item) for item in items]

    async def trending(self, limit: int = 20) -> list[dict]:
        items = await self._get("/animes", {"status": "ongoing", "limit": limit, "order": "popularity"})
        return [self._card(item) for item in items]

    async def random(self) -> dict | None:
        response = await self._client.get("/animes", params={"order": "random", "limit": 1, "score": 6})
        response.raise_for_status()
        items = response.json()
        return self._card(items[0]) if items else None

    async def details(self, anime_id: int) -> dict:
        anime = await self._get(f"/animes/{anime_id}")
        card = self._card(anime)
        trailers = []
        for video in anime.get("videos") or []:
            match = YOUTUBE_ID.search(video.get("url") or "")
            if match and video.get("kind") in ("pv", "op", "ed", "cm"):
                trailers.append({"name": video.get("name") or video["kind"].upper(), "youtube_id": match.group(1)})
        trailers.sort(key=lambda trailer: 0 if "PV" in trailer["name"].upper() else 1)

        links = [{"name": "Shikimori", "url": f"{self._base_url}{anime.get('url', '')}"}]
        if anime.get("myanimelist_id"):
            links.append({"name": "MyAnimeList", "url": f"https://myanimelist.net/anime/{anime['myanimelist_id']}"})

        details = {
            "description": BBCODE.sub("", anime.get("description") or "").strip() or None,
            "genres": [genre.get("russian") or genre.get("name") for genre in anime.get("genres") or []],
            "status": STATUSES.get(anime.get("status"), anime.get("status")),
            "episodes": anime.get("episodes") or anime.get("episodes_aired") or None,
            "duration": anime.get("duration") or None,
            "studios": [studio["name"] for studio in anime.get("studios") or []],
            "trailers": trailers[:5],
            "watch": [],
            "links": links,
        }
        return {**card, **details}
