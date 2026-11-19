from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.businesses import (
    authorize,
    business_exists,
    check_master_key,
    hash_key,
    init_businesses,
    make_business_id,
    new_api_key,
)
from app.chunking import chunk_text
from app.db import get_conn, init_db
from app.followups import (
    cancel_pending,
    fmt,
    run_due,
    schedule_followups,
    utcnow,
)
from app.ratelimit import RateLimiter
from app.search import search

STATIC = Path(__file__).parent / "static"

# A passage must contain at least this share of the question's key words.
MIN_COVERAGE = 0.6
NOT_FOUND_MESSAGE = (
    "I don't have that information yet. I'll pass your question to our team."
)
LEAD_STATUSES = ("new", "replied", "converted", "lost")
FOLLOWUP_STATUSES = ("pending", "sent", "cancelled", "skipped")

# Public endpoints (the chat widget): 30 calls per minute per visitor.
limiter = RateLimiter(max_calls=30, window_seconds=60)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def public_rate_limit(request: Request) -> None:
    if not limiter.allow(f"{request.url.path}:{client_ip(request)}"):
        raise HTTPException(
            status_code=429, detail="Too many requests. Please try again soon."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with get_conn() as conn:
        init_businesses(conn)
    yield


app = FastAPI(title="Catchly", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


class BusinessIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class DocumentIn(BaseModel):
    business_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=200_000)


class AskIn(BaseModel):
    business_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=1000)


class LeadIn(BaseModel):
    business_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(pattern=r"^[0-9+\-\s()]{7,20}$")
    interest: str | None = Field(default=None, max_length=200)


class LeadStatusIn(BaseModel):
    business_id: str = Field(min_length=1, max_length=64)
    status: Literal["new", "replied", "converted", "lost"]


# ---------- public ----------


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "catchly"}


@app.get("/widget.js", include_in_schema=False)
def widget_js():
    return FileResponse(STATIC / "widget.js", media_type="application/javascript")


@app.get("/panel", include_in_schema=False)
def panel():
    return FileResponse(STATIC / "dashboard.html", media_type="text/html")


@app.get("/demo", include_in_schema=False)
def demo():
    return FileResponse(STATIC / "demo.html", media_type="text/html")


@app.post("/ask", dependencies=[Depends(public_rate_limit)])
def ask(body: AskIn) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.text AS text, d.title AS document_title "
            "FROM chunks c JOIN documents d ON d.id = c.document_id "
            "WHERE c.business_id = ?",
            (body.business_id,),
        ).fetchall()

    hits = search(body.question, [dict(r) for r in rows])

    if not hits or hits[0]["coverage"] < MIN_COVERAGE:
        return {
            "answered": False,
            "handoff": True,
            "answer": NOT_FOUND_MESSAGE,
            "sources": [],
        }

    return {
        "answered": True,
        "handoff": False,
        "answer": hits[0]["text"],
        "sources": [
            {
                "document": h["document_title"],
                "text": h["text"],
                "coverage": round(h["coverage"], 2),
            }
            for h in hits
        ],
    }


@app.post("/leads", status_code=201, dependencies=[Depends(public_rate_limit)])
def create_lead(body: LeadIn) -> dict:
    now = utcnow()
    with get_conn() as conn:
        if not business_exists(conn, body.business_id):
            raise HTTPException(status_code=404, detail="Unknown business.")
        cur = conn.execute(
            "INSERT INTO leads (business_id, name, phone, interest, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (body.business_id, body.name, body.phone, body.interest, fmt(now)),
        )
        lead_id = cur.lastrowid
        schedule_followups(conn, lead_id, now)
    return {"lead_id": lead_id, "status": "new", "followups_scheduled": 3}


# ---------- admin (server owner) ----------


@app.post("/businesses", status_code=201)
def create_business(
    body: BusinessIn, x_admin_key: str | None = Header(default=None)
) -> dict:
    check_master_key(x_admin_key)
    business_id = make_business_id(body.name)
    api_key = new_api_key()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO businesses (id, name, api_key_hash, created_at) "
            "VALUES (?, ?, ?, ?)",
            (business_id, body.name, hash_key(api_key), fmt(utcnow())),
        )
    return {
        "business_id": business_id,
        "name": body.name,
        "api_key": api_key,
        "note": "Save this API key now. It is shown only once.",
    }


# ---------- private (business API key) ----------


@app.post("/documents", status_code=201)
def add_document(
    body: DocumentIn, x_api_key: str | None = Header(default=None)
) -> dict:
    with get_conn() as conn:
        authorize(conn, body.business_id, x_api_key)
        chunks = chunk_text(body.text)
        if not chunks:
            raise HTTPException(status_code=422, detail="Document text is empty.")
        cur = conn.execute(
            "INSERT INTO documents (business_id, title) VALUES (?, ?)",
            (body.business_id, body.title),
        )
        doc_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO chunks (document_id, business_id, position, text) "
            "VALUES (?, ?, ?, ?)",
            [(doc_id, body.business_id, i, c) for i, c in enumerate(chunks)],
        )
    return {"document_id": doc_id, "title": body.title, "chunks": len(chunks)}


@app.get("/documents")
def list_documents(
    business_id: str, x_api_key: str | None = Header(default=None)
) -> dict:
    with get_conn() as conn:
        authorize(conn, business_id, x_api_key)
        rows = conn.execute(
            "SELECT id, title, created_at FROM documents "
            "WHERE business_id = ? ORDER BY id",
            (business_id,),
        ).fetchall()
    return {"documents": [dict(r) for r in rows]}


@app.get("/leads")
def list_leads(
    business_id: str, x_api_key: str | None = Header(default=None)
) -> dict:
    with get_conn() as conn:
        authorize(conn, business_id, x_api_key)
        rows = conn.execute(
            "SELECT id, name, phone, interest, status, created_at "
            "FROM leads WHERE business_id = ? ORDER BY id DESC",
            (business_id,),
        ).fetchall()
    return {"leads": [dict(r) for r in rows]}


@app.patch("/leads/{lead_id}")
def update_lead(
    lead_id: int,
    body: LeadStatusIn,
    x_api_key: str | None = Header(default=None),
) -> dict:
    with get_conn() as conn:
        authorize(conn, body.business_id, x_api_key)
        lead = conn.execute(
            "SELECT id FROM leads WHERE id = ? AND business_id = ?",
            (lead_id, body.business_id),
        ).fetchone()
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found.")

        conn.execute(
            "UPDATE leads SET status = ? WHERE id = ?", (body.status, lead_id)
        )
        if body.status != "new":
            cancel_pending(conn, lead_id)
    return {"lead_id": lead_id, "status": body.status}


@app.post("/followups/run")
def run_followups(
    business_id: str, x_api_key: str | None = Header(default=None)
) -> dict:
    """Return follow-up messages that are due, and mark them as sent.

    Catchly does not deliver them. The panel gives staff a WhatsApp link
    with the text ready to send.
    """
    with get_conn() as conn:
        authorize(conn, business_id, x_api_key)
        sent = run_due(conn, business_id, utcnow())
    return {"count": len(sent), "messages": sent}


@app.get("/dashboard")
def dashboard(
    business_id: str, x_api_key: str | None = Header(default=None)
) -> dict:
    with get_conn() as conn:
        authorize(conn, business_id, x_api_key)
        lead_rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM leads "
            "WHERE business_id = ? GROUP BY status",
            (business_id,),
        ).fetchall()
        followup_rows = conn.execute(
            "SELECT f.status AS status, COUNT(*) AS n "
            "FROM followups f JOIN leads l ON l.id = f.lead_id "
            "WHERE l.business_id = ? GROUP BY f.status",
            (business_id,),
        ).fetchall()
        docs = conn.execute(
            "SELECT COUNT(*) AS n FROM documents WHERE business_id = ?",
            (business_id,),
        ).fetchone()["n"]

    leads = {s: 0 for s in LEAD_STATUSES}
    leads.update({r["status"]: r["n"] for r in lead_rows})
    followups = {s: 0 for s in FOLLOWUP_STATUSES}
    followups.update({r["status"]: r["n"] for r in followup_rows})
    return {"leads": leads, "followups": followups, "documents": docs}
