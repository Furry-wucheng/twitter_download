import os
import sqlite3


class cache_gen():

    def __init__(self, save_path, is_share=False) -> None:
        if is_share:
            self.db_path = os.path.dirname(save_path) + os.sep + "cache_data.db"
        else:
            self.db_path = save_path + os.sep + "cache_data.db"

        self.conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self):
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
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_author ON downloaded(author_screen_name)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_tweet_time ON downloaded(tweet_time)
        ''')
        self.conn.commit()

    def __del__(self):
        self.close()

    def close(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            self.conn = None

    def add(self, file_hash, metadata=None):
        if metadata is None:
            metadata = {}

        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO downloaded
            (file_hash, url, tweet_time, author_screen_name, author_name, tweet_url, media_type, tweet_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            file_hash,
            metadata.get('url'),
            metadata.get('tweet_time'),
            metadata.get('author_screen_name'),
            metadata.get('author_name'),
            metadata.get('tweet_url'),
            metadata.get('media_type'),
            metadata.get('tweet_text')
        ))
        self.conn.commit()

    def is_present(self, file_hash):
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM downloaded WHERE file_hash = ?', (file_hash,))
        result = cursor.fetchone()
        return result is None
