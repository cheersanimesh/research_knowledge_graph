"""Database connection and session management."""
import logging
from contextlib import contextmanager
from typing import Generator
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from config import Config
from pgvector.psycopg2 import register_vector

logger = logging.getLogger(__name__)


class DatabaseClient:
    """Manages PostgreSQL connections using a connection pool."""
    
    def __init__(self, database_url: str = None):
        """Initialize database client with connection pool."""
        self.database_url = Config.DATABASE_URL
        
        self.db_host = Config.DB_HOST
        self.db_port = Config.DB_PORT
        self.db_user = Config.DB_USER
        self.db_password = Config.DB_PASSWORD
        self.db_name = Config.DB_NAME

        self.pool: ThreadedConnectionPool = None
        self._initialize_pool()
    
    def _initialize_pool(self, min_conn: int = 1, max_conn: int = 10):
        """Initialize connection pool."""
        try:
            
            self.pool = ThreadedConnectionPool(
                min_conn,
                max_conn,
                user = self.db_user,
                password = self.db_password,
                host= self.db_host,
                port = self.db_port,
                dbname = self.db_name,
            )
            
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """Get a connection from the pool (context manager)."""
        conn = None
        try:
            conn = self.pool.getconn()
            register_vector(conn)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, dict_cursor: bool = True) -> Generator:
        """Get a cursor from the pool (context manager)."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor if dict_cursor else None)
            try:
                yield cursor
            finally:
                cursor.close()
    
    def execute_query(self, query: str, params: tuple = None) -> list:
        """Execute a SELECT query and return results."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return row count."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def close(self):
        """Close all connections in the pool."""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connection pool closed")

