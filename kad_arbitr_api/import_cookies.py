"""
Импортирует cookies сессии kad.arbitr.ru, пройденной человеком в обычном
браузере (Chrome/Firefox), в формат Playwright storage_state — так сервис
переиспользует уже подтверждённую сессию вместо того, чтобы пытаться
проходить антибот-защиту сайта автоматизированным браузером (что сайт
целенаправленно блокирует).

Как получить исходный файл:
1. В обычном браузере (НЕ через этот сервис) откройте https://kad.arbitr.ru
   и вручную выполните поиск дел — убедитесь, что результаты показываются.
2. Установите расширение "Cookie-Editor" (доступно для Chrome и Firefox).
3. На странице kad.arbitr.ru откройте Cookie-Editor -> Export -> Export as
   JSON, скопируйте содержимое в файл (по умолчанию ожидается
   cookies_export.json в текущей директории).
4. Запустите: python -m kad_arbitr_api.import_cookies [путь_к_файлу]

Сессия действует ограниченное время — при появлении ошибок "антибот
отклонил запрос" повторите экспорт.
"""

import json
import sys

from kad_arbitr_api.config import settings

SAME_SITE_MAP = {
    "no_restriction": "None",
    "unspecified": "Lax",
    "lax": "Lax",
    "strict": "Strict",
    "none": "None",
}


def convert(raw_cookies: list[dict]) -> dict:
    cookies = []
    for c in raw_cookies:
        expires = c.get("expirationDate")
        same_site_raw = str(c.get("sameSite", "unspecified")).lower()
        cookies.append(
            {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c.get("path", "/"),
                "expires": expires if expires is not None else -1,
                "httpOnly": bool(c.get("httpOnly", False)),
                "secure": bool(c.get("secure", False)),
                "sameSite": SAME_SITE_MAP.get(same_site_raw, "Lax"),
            }
        )
    return {"cookies": cookies, "origins": []}


def main() -> None:
    source_path = sys.argv[1] if len(sys.argv) > 1 else "cookies_export.json"

    with open(source_path, encoding="utf-8") as f:
        raw_cookies = json.load(f)

    if not isinstance(raw_cookies, list) or not raw_cookies:
        raise SystemExit(
            f"{source_path} должен содержать непустой JSON-массив cookies "
            "(экспорт из Cookie-Editor: Export -> Export as JSON)"
        )

    storage_state = convert(raw_cookies)
    with open(settings.storage_state_path, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, ensure_ascii=False, indent=2)

    print(
        f"Сохранено {len(storage_state['cookies'])} cookies в "
        f"{settings.storage_state_path}. Перезапустите сервер, чтобы он подхватил сессию."
    )


if __name__ == "__main__":
    main()
