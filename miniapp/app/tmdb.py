import random

import httpx

from .cache import TTLCache

IMAGE_BASE = "https://image.tmdb.org/t/p"
LANGUAGE = "ru-RU"


class TmdbClient:
    def __init__(self, token: str, region: str):
        self.enabled = bool(token)
        self._region = region
        self._client = httpx.AsyncClient(
            base_url="https://api.themoviedb.org/3",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=15,
        )
        self._cache = TTLCache()

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None):
        params = {"language": LANGUAGE, **(params or {})}
        cache_key = (path, tuple(sorted(params.items())))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        data = response.json()
        self._cache.set(cache_key, data)
        return data

    @staticmethod
    def _card(item: dict, media_type: str) -> dict:
        date = item.get("release_date") or item.get("first_air_date") or ""
        poster = item.get("poster_path")
        return {
            "key": f"{media_type}:{item['id']}",
            "type": media_type,
            "title": item.get("title") or item.get("name"),
            "original_title": item.get("original_title") or item.get("original_name"),
            "poster": f"{IMAGE_BASE}/w342{poster}" if poster else None,
            "year": date[:4] or None,
            "score": round(item["vote_average"], 1) if item.get("vote_average") else None,
            "kind": "Фильм" if media_type == "movie" else "Сериал",
        }

    async def search(self, query: str, media_type: str | None = None) -> list[dict]:
        if media_type:
            data = await self._get(f"/search/{media_type}", {"query": query})
            return [self._card(item, media_type) for item in data.get("results", [])]
        data = await self._get("/search/multi", {"query": query})
        return [
            self._card(item, item["media_type"])
            for item in data.get("results", [])
            if item.get("media_type") in ("movie", "tv")
        ]

    async def trending(self, media_type: str) -> list[dict]:
        data = await self._get(f"/trending/{media_type}/week")
        return [self._card(item, media_type) for item in data.get("results", [])]

    async def random(self, media_type: str) -> dict | None:
        data = await self._get(
            f"/discover/{media_type}",
            {"page": random.randint(1, 30), "sort_by": "popularity.desc", "vote_count.gte": 300},
        )
        results = data.get("results", [])
        return self._card(random.choice(results), media_type) if results else None

    async def details(self, media_type: str, item_id: int) -> dict:
        item = await self._get(
            f"/{media_type}/{item_id}",
            {"append_to_response": "videos,watch/providers,external_ids", "include_video_language": "ru,en,null"},
        )
        card = self._card(item, media_type)

        videos = [
            video
            for video in (item.get("videos") or {}).get("results", [])
            if video.get("site") == "YouTube" and video.get("type") in ("Trailer", "Teaser")
        ]
        videos.sort(key=lambda video: (video.get("iso_639_1") != "ru", video.get("type") != "Trailer"))
        trailers = [{"name": video["name"], "youtube_id": video["key"]} for video in videos[:5]]

        providers = ((item.get("watch/providers") or {}).get("results") or {}).get(self._region) or {}
        watch = []
        seen = set()
        for offer_type, label in (("flatrate", "Подписка"), ("free", "Бесплатно"), ("ads", "С рекламой"), ("rent", "Аренда"), ("buy", "Покупка")):
            for provider in providers.get(offer_type, []):
                if provider["provider_id"] in seen:
                    continue
                seen.add(provider["provider_id"])
                logo = provider.get("logo_path")
                watch.append({
                    "name": provider["provider_name"],
                    "offer": label,
                    "logo": f"{IMAGE_BASE}/w92{logo}" if logo else None,
                    "url": providers.get("link"),
                })

        links = [{"name": "TMDB", "url": f"https://www.themoviedb.org/{media_type}/{item_id}"}]
        imdb_id = (item.get("external_ids") or {}).get("imdb_id") or item.get("imdb_id")
        if imdb_id:
            links.append({"name": "IMDb", "url": f"https://www.imdb.com/title/{imdb_id}/"})

        runtime = item.get("runtime") or (item.get("episode_run_time") or [None])[0]
        details = {
            "description": item.get("overview") or None,
            "genres": [genre["name"] for genre in item.get("genres") or []],
            "status": item.get("status"),
            "episodes": item.get("number_of_episodes"),
            "seasons": item.get("number_of_seasons"),
            "duration": runtime,
            "studios": [company["name"] for company in (item.get("networks") or item.get("production_companies") or [])[:3]],
            "trailers": trailers,
            "watch": watch,
            "links": links,
        }
        return {**card, **details}
