from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.chunking import chunk_text
from app.db import get_conn, init_db
from app.search import search

# A passage must contain at least this share of the question's key words.
MIN_COVERAGE = 0.6
NOT_FOUND_MESSAGE = (
    "I don't have that information yet. I'll pass your question to our team."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Catchly", version="0.2.0", lifespan=lifespan)


class DocumentIn(BaseModel):
    business_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=200_000)


class AskIn(BaseModel):
    business_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=1000)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "catchly"}


@app.post("/documents", status_code=201)
def add_document(body: DocumentIn) -> dict:
    chunks = chunk_text(body.text)
    if not chunks:
        raise HTTPException(status_code=422, detail="Document text is empty.")

    with get_conn() as conn:
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
def list_documents(business_id: str) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at FROM documents "
            "WHERE business_id = ? ORDER BY id",
            (business_id,),
        ).fetchall()
    return {"documents": [dict(r) for r in rows]}


@app.post("/ask")
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
