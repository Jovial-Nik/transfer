import os
import sqlite3
import threading
import time

STATUSES = ("planned", "watching", "completed", "on_hold", "dropped")


class Storage:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS list_entries (
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                type TEXT NOT NULL,
                title TEXT,
                poster TEXT,
                year TEXT,
                status TEXT NOT NULL,
                score INTEGER,
                progress INTEGER,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, key)
            )
            """
        )
        self._db.commit()

    def list(self, user_id: int, status: str | None = None) -> list[dict]:
        query = "SELECT * FROM list_entries WHERE user_id = ?"
        params: list = [user_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        with self._lock:
            rows = self._db.execute(query + " ORDER BY updated_at DESC", params).fetchall()
        return [dict(row) for row in rows]

    def get(self, user_id: int, key: str) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM list_entries WHERE user_id = ? AND key = ?", (user_id, key)
            ).fetchone()
        return dict(row) if row else None

    def upsert(self, user_id: int, entry: dict) -> dict:
        entry = {**entry, "user_id": user_id, "updated_at": int(time.time())}
        with self._lock:
            self._db.execute(
                """
                INSERT INTO list_entries (user_id, key, type, title, poster, year, status, score, progress, updated_at)
                VALUES (:user_id, :key, :type, :title, :poster, :year, :status, :score, :progress, :updated_at)
                ON CONFLICT (user_id, key) DO UPDATE SET
                    title = excluded.title, poster = excluded.poster, year = excluded.year,
                    status = excluded.status, score = excluded.score, progress = excluded.progress,
                    updated_at = excluded.updated_at
                """,
                entry,
            )
            self._db.commit()
        return entry

    def delete(self, user_id: int, key: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM list_entries WHERE user_id = ? AND key = ?", (user_id, key))
            self._db.commit()

    def stats(self, user_id: int) -> dict:
        with self._lock:
            rows = self._db.execute(
                "SELECT status, COUNT(*) AS count FROM list_entries WHERE user_id = ? GROUP BY status", (user_id,)
            ).fetchall()
        return {row["status"]: row["count"] for row in rows}
