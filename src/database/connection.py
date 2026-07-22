import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from typing import Generator

from src.config import DATABASE_URL


def get_connection():
    return psycopg2.connect(DATABASE_URL)


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
        conn.close()


def init_database():
    import os
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        sql = f.read()
    with get_cursor() as cur:
        cur.execute(sql)
