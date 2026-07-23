import os
from typing import Iterator

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

FOLDER_MIME = "application/vnd.google-apps.folder"

# Нативные форматы Google Workspace нельзя скачать напрямую - их нужно
# экспортировать в один из офисных форматов.
GOOGLE_EXPORT_MIME_MAP = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
    "application/vnd.google-apps.drawing": ("image/png", ".png"),
}


class GoogleDriveClient:
    def __init__(self, credentials_path: str, token_path: str):
        self._service = build(
            "drive", "v3", credentials=self._authenticate(credentials_path, token_path)
        )

    @staticmethod
    def _authenticate(credentials_path: str, token_path: str) -> Credentials:
        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                port = int(os.environ.get("GOOGLE_OAUTH_PORT", "8080"))
                # bind_addr="0.0.0.0" нужен, чтобы локальный сервер авторизации был
                # доступен снаружи контейнера при пробросе портов в Docker; для
                # redirect_uri при этом используется host="localhost", как того
                # требует loopback-схема OAuth у Google.
                creds = flow.run_local_server(
                    host="localhost",
                    port=port,
                    bind_addr="0.0.0.0",
                    open_browser=False,
                )
            with open(token_path, "w") as f:
                f.write(creds.to_json())
        return creds

    def list_children(self, folder_id: str) -> Iterator[dict]:
        page_token = None
        query = f"'{folder_id}' in parents and trashed = false"
        fields = "nextPageToken, files(id, name, mimeType, size)"
        while True:
            response = (
                self._service.files()
                .list(
                    q=query,
                    fields=fields,
                    pageToken=page_token,
                    pageSize=1000,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            yield from response.get("files", [])
            page_token = response.get("nextPageToken")
            if not page_token:
                break

    @staticmethod
    def is_folder(item: dict) -> bool:
        return item["mimeType"] == FOLDER_MIME

    def download_file(self, item: dict, destination: str) -> str:
        """Скачивает файл в destination. Возвращает итоговый путь (с добавленным
        расширением для экспортированных Google-документов) либо "" для
        неподдерживаемых нативных типов (формы, сайты и т.п.)."""
        mime_type = item["mimeType"]
        if mime_type in GOOGLE_EXPORT_MIME_MAP:
            export_mime, suffix = GOOGLE_EXPORT_MIME_MAP[mime_type]
            request = self._service.files().export_media(fileId=item["id"], mimeType=export_mime)
            destination = destination + suffix
        elif mime_type.startswith("application/vnd.google-apps."):
            return ""
        else:
            request = self._service.files().get_media(fileId=item["id"], supportsAllDrives=True)

        with open(destination, "wb") as f:
            downloader = MediaIoBaseDownload(f, request, chunksize=10 * 1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return destination
