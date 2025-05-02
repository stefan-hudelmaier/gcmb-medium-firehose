import sqlite3
from contextlib import contextmanager
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "posts.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the database with required tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Create posts table with an index on id
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Create index on id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_posts_id ON posts(id)
            """)
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()
    
    def add_post(self, post_id: str) -> bool:
        """
        Add a post to the database if it doesn't exist
        Returns True if post was added, False if it already existed
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO posts (id, timestamp) VALUES (?, ?)",
                    (post_id, datetime.now().isoformat())
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error adding post {post_id}: {str(e)}")
            return False
    
    def get_post(self, post_id: str) -> Optional[tuple[str, str]]:
        """Get a post by its ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, timestamp FROM posts WHERE id = ?",
                    (post_id,)
                )
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"Error getting post {post_id}: {str(e)}")
            return None
