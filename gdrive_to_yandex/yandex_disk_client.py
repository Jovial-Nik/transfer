import time

import requests

API_BASE = "https://cloud-api.yandex.net/v1/disk"


class YandexDiskClient:
    def __init__(self, token: str):
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"OAuth {token}"})

    def ensure_folder(self, path: str) -> None:
        current = ""
        for part in (p for p in path.strip("/").split("/") if p):
            current += "/" + part
            self._create_folder(current)

    def _create_folder(self, path: str) -> None:
        response = self._session.put(f"{API_BASE}/resources", params={"path": path})
        if response.status_code not in (201, 409):
            response.raise_for_status()

    def upload_file(self, local_path: str, remote_path: str, overwrite: bool = True, retries: int = 3) -> None:
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                response = self._session.get(
                    f"{API_BASE}/resources/upload",
                    params={"path": remote_path, "overwrite": str(overwrite).lower()},
                )
                response.raise_for_status()
                upload_url = response.json()["href"]
                with open(local_path, "rb") as f:
                    upload_response = requests.put(upload_url, data=f)
                upload_response.raise_for_status()
                return
            except requests.RequestException as error:
                last_error = error
                if attempt < retries:
                    time.sleep(2**attempt)
        raise last_error
