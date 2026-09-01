from __future__ import annotations

import pickle
import sqlite3

from cache_gen import CacheStore
from migrate_cache import migrate


def test_cache_records_successful_download_and_persists(tmp_path):
    user_directory = tmp_path / "alice"
    cache = CacheStore(user_directory)

    assert cache.should_download("media-123") is True
    assert cache.add(
        "media-123",
        {
            "url": "https://pbs.twimg.com/media/media-123.jpg",
            "author_screen_name": "alice",
            "media_type": "Image",
        },
    ) is True
    assert cache.contains("media-123") is True
    assert cache.add("media-123") is False
    cache.close()

    reopened = CacheStore(user_directory)
    assert reopened.should_download("media-123") is False
    reopened.close()


def test_shared_cache_is_created_in_parent_directory(tmp_path):
    user_directory = tmp_path / "alice"
    cache = CacheStore(user_directory, is_share=True)
    cache.close()

    assert (tmp_path / "cache_data.db").exists()
    assert not (user_directory / "cache_data.db").exists()


def test_empty_hash_is_rejected(tmp_path):
    cache = CacheStore(tmp_path / "alice")
    try:
        assert cache.contains("") is False
        try:
            cache.add("")
        except ValueError as exc:
            assert "file_hash" in str(exc)
        else:
            raise AssertionError("empty hashes must be rejected")
    finally:
        cache.close()


def test_pickle_cache_migration(tmp_path):
    source = tmp_path / "cache_data.log"
    source.write_bytes(
        pickle.dumps(
            {
                "https://pbs.twimg.com/media/abc123.jpg?format=jpg&name=orig",
                "https://video.twimg.com/ext_tw_video/video456.mp4?tag=12",
            }
        )
    )

    assert migrate(source) is True
    database = tmp_path / "cache_data.db"
    with sqlite3.connect(database) as connection:
        rows = connection.execute("SELECT file_hash, url FROM downloaded ORDER BY file_hash").fetchall()

    assert rows == [
        ("abc123", "https://pbs.twimg.com/media/abc123.jpg"),
        ("video456", "https://video.twimg.com/ext_tw_video/video456.mp4"),
    ]
