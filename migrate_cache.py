"""
缓存迁移工具：将旧的 cache_data.log (pickle) 迁移到 cache_data.db (SQLite)

用法：
    python migrate_cache.py <cache_data.log路径>

示例：
    python migrate_cache.py ./output/username/cache_data.log
"""

import argparse
import pickle
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
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
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_author ON downloaded(author_screen_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_time ON downloaded(tweet_time)')
    conn.commit()
    return conn


def extract_file_hash(url: str) -> str:
    return Path(urlsplit(url).path).stem


def migrate(log_path: str | Path) -> bool:
    source = Path(log_path).expanduser().resolve()
    if not source.exists():
        print(f"错误: 找不到 {log_path}")
        return False

    db_path = source.with_suffix('.db')
    if db_path.exists():
        print(f"错误: 目标数据库已存在 {db_path}")
        print("如需重新迁移，请先删除该文件")
        return False

    try:
        # Pickle is only safe for a cache file created by this application.
        with source.open('rb') as file:
            old_data: Any = pickle.load(file)
    except (OSError, pickle.PickleError, EOFError) as exc:
        print(f"错误: 读取失败 - {exc}")
        return False

    if not isinstance(old_data, (set, list, tuple)) or not old_data:
        print("旧缓存为空，无需迁移")
        return False

    conn = init_db(db_path)
    cursor = conn.cursor()

    migrated = 0
    for value in old_data:
        if not isinstance(value, str):
            print(f"警告: 跳过非 URL 缓存项 [{value!r}]")
            continue
        url = value
        file_hash = extract_file_hash(url)
        if not file_hash:
            print(f"警告: 无法识别资源文件名 [{url}]")
            continue
        url_clean = url.split('?', 1)[0]
        try:
            cursor.execute(
                'INSERT OR IGNORE INTO downloaded (file_hash, url) VALUES (?, ?)',
                (file_hash, url_clean)
            )
            migrated += cursor.rowcount
        except sqlite3.Error as exc:
            print(f"警告: 迁移失败 [{url}] - {exc}")

    conn.commit()
    conn.close()

    print(f"迁移完成: {migrated}/{len(old_data)} 条 -> {db_path}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="将旧的 pickle 缓存迁移到 SQLite")
    parser.add_argument("cache_file", type=Path, help="cache_data.log 的路径")
    args = parser.parse_args()
    return 0 if migrate(args.cache_file) else 1


if __name__ == '__main__':
    raise SystemExit(main())
