"""
缓存迁移工具：将旧的 cache_data.log (pickle) 迁移到 cache_data.db (SQLite)

用法：
    python migrate_cache.py <cache_data.log路径>

示例：
    python migrate_cache.py ./output/username/cache_data.log
"""

import os
import sys
import sqlite3
import pickle


def init_db(db_path):
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


def extract_file_hash(url):
    if '?' in url:
        url = url.split('?')[0]
    return url.split('/')[-1].split('.')[0]


def migrate(log_path):
    if not os.path.exists(log_path):
        print(f"错误: 找不到 {log_path}")
        return False

    db_path = os.path.splitext(log_path)[0] + '.db'
    if os.path.exists(db_path):
        print(f"错误: 目标数据库已存在 {db_path}")
        print("如需重新迁移，请先删除该文件")
        return False

    try:
        with open(log_path, 'rb') as f:
            old_data = pickle.load(f)
    except Exception as e:
        print(f"错误: 读取失败 - {e}")
        return False

    if not old_data:
        print("旧缓存为空，无需迁移")
        return False

    conn = init_db(db_path)
    cursor = conn.cursor()

    migrated = 0
    for url in old_data:
        file_hash = extract_file_hash(url)
        url_clean = url.split('?')[0] if '?' in url else url
        try:
            cursor.execute(
                'INSERT OR IGNORE INTO downloaded (file_hash, url) VALUES (?, ?)',
                (file_hash, url_clean)
            )
            migrated += cursor.rowcount
        except Exception as e:
            print(f"警告: 迁移失败 [{url}] - {e}")

    conn.commit()
    conn.close()

    print(f"迁移完成: {migrated}/{len(old_data)} 条 -> {db_path}")
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    migrate(sys.argv[1])


if __name__ == '__main__':
    main()
