import os
import sqlite3
from contextlib import contextmanager


def db_path() -> str:
    return os.environ.get("CATCHLY_DB", "catchly.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES documents(id),
                business_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                text TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_business
                ON chunks(business_id);
            """
        )
