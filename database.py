import sqlite3
from contextlib import contextmanager
import logging
from datetime import datetime, timedelta
from typing import Optional, List

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
            # Create subscriptions table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    topic_url TEXT PRIMARY KEY,
                    hub_url TEXT NOT NULL,
                    lease_expires TIMESTAMP NOT NULL
                )
            """)
            # Create index on lease_expires for efficient expiration checking
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_subscriptions_lease 
                ON subscriptions(lease_expires)
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

    def count_posts(self) -> int:
        """Get the total number of posts in the database"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM posts")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error counting posts: {str(e)}")
            return 0

    def add_subscription(self, topic_url: str, hub_url: str, lease_seconds: int) -> bool:
        """Add or update a subscription with its lease time"""
        try:
            expires = datetime.now() + timedelta(seconds=lease_seconds)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO subscriptions 
                    (topic_url, hub_url, lease_expires) 
                    VALUES (?, ?, ?)
                """, (topic_url, hub_url, expires.isoformat()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding subscription for {topic_url}: {str(e)}")
            return False

    def get_subscription(self, topic_url: str) -> Optional[tuple[str, str, datetime]]:
        """Get subscription details by topic URL"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT topic_url, hub_url, lease_expires 
                    FROM subscriptions 
                    WHERE topic_url = ?
                """, (topic_url,))
                row = cursor.fetchone()
                if row:
                    return row[0], row[1], datetime.fromisoformat(row[2])
                return None
        except Exception as e:
            logger.error(f"Error getting subscription for {topic_url}: {str(e)}")
            return None

    def get_expiring_subscriptions(self, within_minutes: int = 5) -> List[tuple[str, str, datetime]]:
        """Get subscriptions that will expire within the specified number of minutes"""
        try:
            expiry_threshold = datetime.now() + timedelta(minutes=within_minutes)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT topic_url, hub_url, lease_expires 
                    FROM subscriptions 
                    WHERE lease_expires <= ?
                """, (expiry_threshold.isoformat(),))
                return [(row[0], row[2], datetime.fromisoformat(row[3]))
                       for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting expiring subscriptions: {str(e)}")
            return []
