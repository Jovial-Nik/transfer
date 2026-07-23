import json
import os
import tempfile

from tqdm import tqdm

from .google_drive_client import GoogleDriveClient
from .yandex_disk_client import YandexDiskClient


class Migrator:
    def __init__(
        self,
        gdrive: GoogleDriveClient,
        yadisk: YandexDiskClient,
        dest_root: str,
        state_path: str,
    ):
        self._gdrive = gdrive
        self._yadisk = yadisk
        self._dest_root = dest_root.rstrip("/") or "/"
        self._state_path = state_path
        self._done_ids = self._load_state()

    def _load_state(self) -> set:
        if os.path.exists(self._state_path):
            with open(self._state_path) as f:
                return set(json.load(f))
        return set()

    def _save_state(self) -> None:
        with open(self._state_path, "w") as f:
            json.dump(sorted(self._done_ids), f)

    def run(self, source_folder_id: str = "root") -> None:
        self._yadisk.ensure_folder(self._dest_root)
        self._migrate_folder(source_folder_id, self._dest_root)

    def _migrate_folder(self, folder_id: str, dest_path: str) -> None:
        items = list(self._gdrive.list_children(folder_id))
        for item in tqdm(items, desc=dest_path, leave=False):
            item_dest = f"{dest_path}/{self._safe_name(item['name'])}"
            if self._gdrive.is_folder(item):
                self._yadisk.ensure_folder(item_dest)
                self._migrate_folder(item["id"], item_dest)
            else:
                self._migrate_file(item, item_dest)

    def _migrate_file(self, item: dict, dest_path: str) -> None:
        if item["id"] in self._done_ids:
            return
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_path = os.path.join(tmp_dir, "download")
            actual_local_path = self._gdrive.download_file(item, local_path)
            if not actual_local_path:
                return
            if actual_local_path != local_path:
                dest_path += os.path.splitext(actual_local_path)[1]
            self._yadisk.upload_file(actual_local_path, dest_path)
        self._done_ids.add(item["id"])
        self._save_state()

    @staticmethod
    def _safe_name(name: str) -> str:
        return name.replace("/", "_").replace("\\", "_")
