import hashlib
import hmac
import os
import re
import secrets

from fastapi import HTTPException

SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    api_key_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def init_businesses(conn) -> None:
    conn.executescript(SCHEMA)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_api_key() -> str:
    return "ctl_" + secrets.token_urlsafe(32)


def make_business_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or "business"
    return f"{slug}-{secrets.token_hex(3)}"


def check_master_key(provided: str | None) -> None:
    master = os.environ.get("CATCHLY_ADMIN_KEY")
    if not master:
        raise HTTPException(503, "Admin key is not configured on the server.")
    if not provided or not hmac.compare_digest(provided.encode(), master.encode()):
        raise HTTPException(401, "Invalid admin key.")


def business_exists(conn, business_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM businesses WHERE id = ?", (business_id,)
    ).fetchone()
    return row is not None


def authorize(conn, business_id: str, api_key: str | None) -> None:
    """Same error for a wrong key and an unknown business."""
    row = conn.execute(
        "SELECT api_key_hash FROM businesses WHERE id = ?", (business_id,)
    ).fetchone()
    if (
        not api_key
        or row is None
        or not hmac.compare_digest(
            hash_key(api_key).encode(), row["api_key_hash"].encode()
        )
    ):
        raise HTTPException(401, "Invalid API key.")
