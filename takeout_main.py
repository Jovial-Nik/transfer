import argparse
import os

from dotenv import load_dotenv

from gdrive_to_yandex.takeout_importer import TakeoutImporter
from gdrive_to_yandex.yandex_disk_client import YandexDiskClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Перенос Google Takeout (Google Фото) на Яндекс.Диск")
    parser.add_argument("--source-dir", default="/app/data/takeout", help="Папка с .zip-архивами Google Takeout")
    parser.add_argument("--dest-path", default="/GooglePhotosBackup", help="Путь на Яндекс.Диске, куда переносить фото")
    parser.add_argument("--state-file", default="/app/data/takeout_state.json", help="Файл прогресса переноса")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    yandex_token = os.environ.get("YANDEX_TOKEN")
    if not yandex_token:
        raise SystemExit("Задайте переменную окружения YANDEX_TOKEN (см. README.md)")

    yadisk = YandexDiskClient(yandex_token)
    importer = TakeoutImporter(yadisk, args.dest_path, args.state_file)
    importer.run(args.source_dir)
    print("Перенос Google Фото завершён.")


if __name__ == "__main__":
    main()
