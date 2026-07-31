import psycopg2
import psycopg2.extras
import psycopg2.pool
from contextlib import contextmanager
from typing import Generator

from src.config import DATABASE_URL

MAX_CONNECTIONS = 20

_pool = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            1, MAX_CONNECTIONS, DATABASE_URL, connect_timeout=10)
    return _pool


def get_connection():
    """Check out a pooled connection. Caller MUST return it via put_connection()."""
    return _get_pool().getconn()


def put_connection(conn):
    _get_pool().putconn(conn)


@contextmanager
def get_cursor(commit: bool = True) -> Generator:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            yield cur
            if commit:
                conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_connection(conn)


def init_database():
    import os
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        sql = f.read()
    with get_cursor() as cur:
        cur.execute(sql)
