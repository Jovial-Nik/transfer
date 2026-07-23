FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY gdrive_to_yandex ./gdrive_to_yandex

ENTRYPOINT ["python", "main.py"]
