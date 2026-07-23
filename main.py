import argparse
import os

from dotenv import load_dotenv

from gdrive_to_yandex.google_drive_client import GoogleDriveClient
from gdrive_to_yandex.migrator import Migrator
from gdrive_to_yandex.yandex_disk_client import YandexDiskClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Перенос файлов с Google Drive на Яндекс.Диск")
    parser.add_argument("--source-folder-id", default="root", help="ID папки Google Drive (по умолчанию - весь диск)")
    parser.add_argument("--dest-path", default="/GoogleDriveBackup", help="Путь на Яндекс.Диске, куда переносить файлы")
    parser.add_argument("--credentials", default="credentials.json", help="Файл credentials.json из Google Cloud Console")
    parser.add_argument("--token", default="token.json", help="Файл для хранения токена доступа Google")
    parser.add_argument("--state-file", default="migration_state.json", help="Файл прогресса переноса (для докачки после сбоя)")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    yandex_token = os.environ.get("YANDEX_TOKEN")
    if not yandex_token:
        raise SystemExit("Задайте переменную окружения YANDEX_TOKEN (см. README.md)")

    gdrive = GoogleDriveClient(args.credentials, args.token)
    yadisk = YandexDiskClient(yandex_token)
    migrator = Migrator(gdrive, yadisk, args.dest_path, args.state_file)
    migrator.run(args.source_folder_id)
    print("Перенос завершён.")


if __name__ == "__main__":
    main()
