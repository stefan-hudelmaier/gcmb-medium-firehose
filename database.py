import os
import psycopg2
from psycopg2.extras import DictCursor
from contextlib import contextmanager
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class Subscription:
    """Represents a WebSub subscription with its lease information"""
    topic_url: str
    hub_url: str
    subscribed_at: datetime
    lease_expires: datetime

    @classmethod
    def from_row(cls, row: tuple) -> 'Subscription':
        """Create a Subscription from a database row"""
        return cls(
            topic_url=row[0],
            hub_url=row[1],
            subscribed_at=row[2],
            lease_expires=row[3]
        )

class Database:
    def __init__(self):
        self.db_params = {
            'dbname': os.getenv('POSTGRES_DB', 'medium'),
            'user': os.getenv('POSTGRES_USER'),
            'password': os.getenv('POSTGRES_PASSWORD'),
            'host': os.getenv('POSTGRES_HOST'),
            'port': os.getenv('POSTGRES_PORT', '5432')
        }
        self._init_db()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection"""
        conn = psycopg2.connect(**self.db_params)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
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
                    subscribed_at TIMESTAMP NOT NULL,
                    lease_expires TIMESTAMP NOT NULL
                )
            """)
            # Create index on lease_expires for efficient expiration checking
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_subscriptions_lease 
                ON subscriptions(lease_expires)
            """)
    
    def add_post(self, post_id: str) -> bool:
        """
        Add a post to the database if it doesn't exist
        Returns True if post was added, False if it already existed
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO posts (id, timestamp) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                    (post_id, datetime.now().isoformat())
                )
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
                    "SELECT id, timestamp FROM posts WHERE id = %s",
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
            now = datetime.now()
            expires = now + timedelta(seconds=lease_seconds)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO subscriptions 
                    (topic_url, hub_url, subscribed_at, lease_expires) 
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (topic_url) DO UPDATE SET
                        hub_url = EXCLUDED.hub_url,
                        subscribed_at = EXCLUDED.subscribed_at,
                        lease_expires = EXCLUDED.lease_expires
                """, (topic_url, hub_url, now.isoformat(), expires.isoformat()))
                return True
        except Exception as e:
            logger.error(f"Error adding subscription for {topic_url}: {str(e)}")
            return False

    def get_subscription(self, topic_url: str) -> Optional[Subscription]:
        """Get subscription details by topic URL"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT topic_url, hub_url, subscribed_at, lease_expires 
                    FROM subscriptions 
                    WHERE topic_url = %s
                """, (topic_url,))
                row = cursor.fetchone()
                if row:
                    return Subscription.from_row(row)
                return None
        except Exception as e:
            logger.error(f"Error getting subscription for {topic_url}: {str(e)}")
            return None

    def get_expiring_subscriptions(self, within_minutes: int = 5) -> List[Subscription]:
        """Get subscriptions that will expire within the specified number of minutes"""
        try:
            expiry_threshold = datetime.now() + timedelta(minutes=within_minutes)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT topic_url, hub_url, subscribed_at, lease_expires 
                    FROM subscriptions 
                    WHERE lease_expires <= %s
                """, (expiry_threshold.isoformat(),))
                return [Subscription.from_row(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting expiring subscriptions: {str(e)}")
            return []
