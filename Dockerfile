FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py takeout_main.py ./
COPY gdrive_to_yandex ./gdrive_to_yandex

# По умолчанию запускается перенос Google Drive (main.py).
# Для переноса Google Фото из Takeout переопредели entrypoint:
#   docker run --entrypoint python gdrive2yadisk takeout_main.py ...
ENTRYPOINT ["python", "main.py"]
