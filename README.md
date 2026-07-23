# Перенос данных с Google Drive на Яндекс.Диск

Консольная программа на Python, которая рекурсивно копирует файлы и папки
из Google Drive на Яндекс.Диск, сохраняя структуру каталогов.

Возможности:

- рекурсивный обход всех папок и подпапок;
- Google-документы (Docs/Sheets/Slides/Drawings) автоматически
  экспортируются в форматы `.docx` / `.xlsx` / `.pptx` / `.png`, так как
  их нельзя скачать в исходном виде;
- обычные файлы скачиваются и заливаются как есть, потоково, без
  загрузки всего файла в память;
- при сбое или повторном запуске уже перенесённые файлы не переносятся
  повторно (прогресс хранится в `migration_state.json`).

## Установка

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Настройка доступа к Google Drive

1. Зайдите в [Google Cloud Console](https://console.cloud.google.com/),
   создайте проект (или выберите существующий).
2. В разделе "APIs & Services" включите **Google Drive API**.
3. В разделе "OAuth consent screen" настройте экран согласия (тип
   "External", добавьте свой email в тестовые пользователи).
4. В разделе "Credentials" создайте **OAuth client ID** типа
   "Desktop app" и скачайте JSON — сохраните его как `credentials.json`
   в корне проекта.
5. При первом запуске программы откроется браузер для авторизации —
   после подтверждения токен сохранится в `token.json` и повторно
   вводить логин/пароль не потребуется.

## Настройка доступа к Яндекс.Диску

1. Зайдите на https://oauth.yandex.ru/client/new и создайте приложение.
2. В разделе доступа отметьте **Яндекс.Диск REST API**: чтение и запись
   (`cloud_api:disk.read`, `cloud_api:disk.write`, либо весь диск —
   `cloud_api:disk.app_folder` если нужна только папка приложения).
3. Получите OAuth-токен по ссылке вида
   `https://oauth.yandex.ru/authorize?response_type=token&client_id=<ID приложения>`.
4. Скопируйте `.env.example` в `.env` и впишите токен:

   ```
   YANDEX_TOKEN=ваш_токен
   ```

## Запуск

```bash
python main.py
```

По умолчанию переносится весь Google Drive в папку `/GoogleDriveBackup`
на Яндекс.Диске. Доступные параметры:

```bash
python main.py \
  --source-folder-id root \        # ID папки Google Drive (root = весь диск)
  --dest-path /GoogleDriveBackup \ # путь на Яндекс.Диске
  --credentials credentials.json \
  --token token.json \
  --state-file migration_state.json
```

ID конкретной папки Google Drive можно взять из её URL:
`https://drive.google.com/drive/folders/<этот_id>`.

Если перенос прервался (сеть, лимиты API и т.п.) — просто запустите
`python main.py` ещё раз с теми же параметрами, программа продолжит с
того места, где остановилась.

## Запуск в Docker (чтобы потом легко всё снести)

Удобно, если не хочется ставить Python и зависимости на VDS напрямую —
после переноса просто удаляешь образ и контейнер, и от программы не
остаётся следов в системе.

1. Создай на хосте папку для файлов, которые должны пережить контейнер
   (`credentials.json`, `token.json` с авторизацией, `.env` и файл
   прогресса `migration_state.json`):

   ```bash
   mkdir data
   cp credentials.json data/
   cp .env.example data/.env   # впиши туда YANDEX_TOKEN
   ```

2. Собери образ:

   ```bash
   docker build -t gdrive2yadisk .
   ```

3. Запусти контейнер. Порт 8080 нужен для одноразовой OAuth-авторизации
   Google (ссылку для входа нужно будет открыть в браузере на своей
   машине — в консоли она распечатается):

   ```bash
   docker run --rm -it \
     -p 8080:8080 \
     -v "$(pwd)/data:/app/data" \
     --env-file data/.env \
     gdrive2yadisk \
     --credentials /app/data/credentials.json \
     --token /app/data/token.json \
     --state-file /app/data/migration_state.json
   ```

   Если VDS без графического окружения — просто скопируй ссылку,
   которую программа выведет в консоль, и открой её в браузере на своём
   компьютере (не на сервере). После подтверждения доступа токен
   сохранится в `data/token.json`, и повторно логиниться не придётся.

4. Если перенос прервался, просто выполни ту же команду `docker run`
   ещё раз — прогресс лежит в `data/migration_state.json` на хосте и
   переживёт удаление контейнера.

5. Когда всё перенесено — сносим всё, что связано с программой:

   ```bash
   docker rmi gdrive2yadisk   # контейнер и так удалился благодаря --rm
   rm -rf data/               # удаляет token.json, credentials.json и прогресс
   ```

   На VDS после этого не останется ни образа, ни контейнера, ни
   сохранённых токенов.

## Ограничения

- Файлы нестандартных типов Google (Формы, Сайты, Jamboard и т.п.) не
  поддерживают экспорт в обычный файл и будут пропущены.
- Общие диски (Shared Drives) поддерживаются, но для них может
  потребоваться передавать ID общего диска как `--source-folder-id`.
- Учитываются лимиты API Google Drive и Яндекс.Диска — при очень
  больших объёмах данных перенос может занять продолжительное время.
