# Media Mini App для Telegram

Telegram Mini App — каталог аниме, фильмов и сериалов:

- поиск и «Популярное сейчас» по аниме ([Shikimori](https://shikimori.io)) и фильмам/сериалам ([TMDB](https://www.themoviedb.org));
- фильтр по типу, кнопка «Случайное»;
- карточка тайтла: описание, жанры, студия, эпизоды, рейтинг, трейлеры с YouTube, ссылки на Shikimori / MyAnimeList / TMDB / IMDb;
- «Где посмотреть» — легальные площадки (подписка, аренда, покупка) из данных JustWatch через TMDB;
- личный список: «Смотрю», «В планах», «Просмотрено», «Отложено», «Брошено», оценка 1–10, счётчик эпизодов;
- вход без регистрации — по подписи Telegram, тема оформления берётся из Telegram.

Приложение не воспроизводит и не встраивает сторонние видео — только каталог, трейлеры и ссылки на официальные сервисы.

## Устройство

```
miniapp/
├── app/               # FastAPI: API каталога, проверка initData, списки (SQLite)
│   ├── main.py
│   ├── shikimori.py
│   ├── tmdb.py
│   ├── storage.py
│   └── telegram_auth.py
└── frontend/          # index.html + app.js + style.css, раздаётся тем же сервером
```

Сервер один: он отдаёт и фронтенд, и `/api/*`.

## Запуск

1. В [@BotFather](https://t.me/BotFather): `/newbot` — получить токен. Бот нужен Telegram только как «владелец» Mini App, код бота писать не нужно.
2. Получить API Read Access Token на https://www.themoviedb.org/settings/api (без него работает только аниме).
3. Заполнить `.env`:
   ```bash
   cp .env.example .env
   ```
4. Запустить:
   ```bash
   docker compose up -d --build
   ```
   Без Docker: `pip install -r requirements.txt && uvicorn app.main:app --port 8000`.
5. Опубликовать по HTTPS — Telegram открывает Mini App только по `https://`. Варианты: свой домен + nginx/Caddy перед портом 8000, или для теста туннель:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
6. В @BotFather: `/newapp` → выбрать бота → указать HTTPS-адрес. Приложение откроется по ссылке `https://t.me/<бот>/<имя_приложения>`. Дополнительно можно поставить его на кнопку меню: `/mybots` → бот → Bot Settings → Menu Button.

## Отладка в браузере

Задайте `DEV_USER_ID=1` в `.env` и откройте http://localhost:8000 — запросы без подписи Telegram будут идти от этого пользователя. На сервере `DEV_USER_ID` оставляйте пустым.

## Доступ

`ALLOWED_USER_IDS=123,456` — пускать только перечисленных пользователей Telegram. Пусто — доступ всем.
