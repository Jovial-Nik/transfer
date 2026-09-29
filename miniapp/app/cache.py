import time


class TTLCache:
    def __init__(self, ttl: int = 600, max_size: int = 2000):
        self._ttl = ttl
        self._max_size = max_size
        self._data: dict = {}

    def get(self, key):
        item = self._data.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at < time.monotonic():
            del self._data[key]
            return None
        return value

    def set(self, key, value) -> None:
        if len(self._data) >= self._max_size:
            self._data.clear()
        self._data[key] = (time.monotonic() + self._ttl, value)
