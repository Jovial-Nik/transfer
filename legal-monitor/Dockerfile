FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY legal_monitor ./legal_monitor

ENTRYPOINT ["python", "-m", "legal_monitor"]
CMD ["list"]
