import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Self


class CacheStore:
    """SQLite-backed record of media that was downloaded successfully."""

    def __init__(self, save_path: str | Path, is_share: bool = False) -> None:
        save_directory = Path(save_path).resolve()
        cache_directory = save_directory.parent if is_share else save_directory
        cache_directory.mkdir(parents=True, exist_ok=True)
        self.db_path = cache_directory / "cache_data.db"

        self.conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloaded (
                file_hash TEXT PRIMARY KEY,
                url TEXT,
                tweet_time INTEGER,
                author_screen_name TEXT,
                author_name TEXT,
                tweet_url TEXT,
                media_type TEXT,
                tweet_text TEXT,
                downloaded_at TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_author ON downloaded(author_screen_name)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_tweet_time ON downloaded(tweet_time)
        ''')
        self.conn.commit()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        connection = getattr(self, "conn", None)
        if connection is not None:
            connection.close()
            self.conn = None

    def add(self, file_hash: str, metadata: dict[str, Any] | None = None) -> bool:
        """Record a successful download and report whether a row was inserted."""
        if not file_hash:
            raise ValueError("file_hash cannot be empty")
        if metadata is None:
            metadata = {}

        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO downloaded
            (file_hash, url, tweet_time, author_screen_name, author_name, tweet_url, media_type, tweet_text, downloaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            file_hash,
            metadata.get('url'),
            metadata.get('tweet_time'),
            metadata.get('author_screen_name'),
            metadata.get('author_name'),
            metadata.get('tweet_url'),
            metadata.get('media_type'),
            metadata.get('tweet_text'),
            datetime.now().astimezone().isoformat(timespec="seconds"),
        ))
        self.conn.commit()
        return cursor.rowcount > 0

    def contains(self, file_hash: str) -> bool:
        if not file_hash:
            return False
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM downloaded WHERE file_hash = ?', (file_hash,))
        return cursor.fetchone() is not None

    def should_download(self, file_hash: str) -> bool:
        """Return true when a media resource is not present in the cache."""
        return not self.contains(file_hash)


# Backwards-compatible import used by the original downloader.
cache_gen = CacheStore
