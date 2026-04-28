"""Single on-disk cache for fetched HTML/JSON.

Schema:
    cache(key TEXT PRIMARY KEY, fetched_at INTEGER, body BLOB)

A row's freshness is `now - fetched_at < ttl_seconds`, where ttl is provided
by the *caller* on each `get_or_fetch` (so individual sources can pick their
own policy without the cache knowing).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Callable


class Cache:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    fetched_at INTEGER NOT NULL,
                    body BLOB NOT NULL
                )
                """
            )

    def get_or_fetch(
        self,
        key: str,
        ttl_seconds: int,
        fetcher: Callable[[], str],
        force_refresh: bool = False,
    ) -> str:
        now = int(time.time())
        if not force_refresh:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT body, fetched_at FROM cache WHERE key = ?", (key,)
                ).fetchone()
            if row is not None:
                body, fetched_at = row
                if now - fetched_at < ttl_seconds:
                    return body if isinstance(body, str) else body.decode("utf-8")

        body = fetcher()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache(key, fetched_at, body) VALUES (?, ?, ?)",
                (key, now, body),
            )
        return body

    def invalidate_prefix(self, prefix: str) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM cache WHERE key LIKE ?", (prefix + "%",))
            return cur.rowcount

    def invalidate_all(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM cache")
            return cur.rowcount
