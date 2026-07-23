import json
import os
import zipfile

from tqdm import tqdm

from .yandex_disk_client import YandexDiskClient

SKIP_SUFFIXES = (".json",)


class TakeoutImporter:
    """Переносит на Яндекс.Диск фото и видео из архивов Google Takeout
    (раздел "Google Фото"). Архивы (.zip) должны лежать в source_dir -
    импортер сам их распакует и загрузит содержимое, сохраняя структуру
    альбомов."""

    def __init__(self, yadisk: YandexDiskClient, dest_root: str, state_path: str):
        self._yadisk = yadisk
        self._dest_root = dest_root.rstrip("/") or "/"
        self._state_path = state_path
        self._done = self._load_state()

    def _load_state(self) -> set:
        if os.path.exists(self._state_path):
            with open(self._state_path) as f:
                return set(json.load(f))
        return set()

    def _save_state(self) -> None:
        with open(self._state_path, "w") as f:
            json.dump(sorted(self._done), f)

    def run(self, source_dir: str) -> None:
        extracted_dir = self._extract_archives(source_dir)
        photos_root = self._find_photos_root(extracted_dir)
        self._yadisk.ensure_folder(self._dest_root)
        self._upload_tree(photos_root)

    def _extract_archives(self, source_dir: str) -> str:
        extracted_dir = os.path.join(source_dir, "_extracted")
        os.makedirs(extracted_dir, exist_ok=True)
        archives = sorted(
            name
            for name in os.listdir(source_dir)
            if name.lower().endswith(".zip") and os.path.isfile(os.path.join(source_dir, name))
        )
        for archive_name in tqdm(archives, desc="Распаковка архивов Takeout"):
            archive_path = os.path.join(source_dir, archive_name)
            marker = archive_path + ".extracted"
            if os.path.exists(marker):
                continue
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(extracted_dir)
            open(marker, "w").close()
        return extracted_dir if archives else source_dir

    @staticmethod
    def _find_photos_root(extracted_dir: str) -> str:
        for root, dirs, _ in os.walk(extracted_dir):
            if "Google Photos" in dirs:
                return os.path.join(root, "Google Photos")
        return extracted_dir

    def _upload_tree(self, photos_root: str) -> None:
        for dirpath, _, filenames in os.walk(photos_root):
            media_files = [f for f in filenames if not f.lower().endswith(SKIP_SUFFIXES)]
            if not media_files:
                continue
            rel_dir = os.path.relpath(dirpath, photos_root)
            dest_dir = self._dest_root if rel_dir == "." else f"{self._dest_root}/{rel_dir.replace(os.sep, '/')}"
            self._yadisk.ensure_folder(dest_dir)
            for filename in tqdm(media_files, desc=dest_dir, leave=False):
                rel_key = os.path.relpath(os.path.join(dirpath, filename), photos_root)
                if rel_key in self._done:
                    continue
                local_path = os.path.join(dirpath, filename)
                remote_path = f"{dest_dir}/{filename}"
                self._yadisk.upload_file(local_path, remote_path)
                self._done.add(rel_key)
                self._save_state()
