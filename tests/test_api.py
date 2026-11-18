import pytest
from fastapi.testclient import TestClient

from app.main import app

FEES = "JEE batch fees are 45000 rupees per year. Classes run Monday to Friday."


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CATCHLY_DB", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def add_fees(client, business="centre1"):
    return client.post(
        "/documents",
        json={"business_id": business, "title": "Fee sheet", "text": FEES},
    )


def test_add_and_list_document(client):
    res = add_fees(client)
    assert res.status_code == 201
    assert res.json()["chunks"] == 1
    listing = client.get("/documents", params={"business_id": "centre1"})
    assert listing.json()["documents"][0]["title"] == "Fee sheet"


def test_empty_document_is_rejected(client):
    res = client.post(
        "/documents",
        json={"business_id": "centre1", "title": "Empty", "text": "   "},
    )
    assert res.status_code == 422


def test_question_is_answered_from_document(client):
    add_fees(client)
    res = client.post(
        "/ask",
        json={"business_id": "centre1", "question": "What are the JEE batch fees?"},
    )
    data = res.json()
    assert data["answered"] is True
    assert "45000" in data["answer"]
    assert data["sources"][0]["document"] == "Fee sheet"


def test_unknown_question_hands_off(client):
    add_fees(client)
    res = client.post(
        "/ask",
        json={"business_id": "centre1", "question": "Do you give scholarships?"},
    )
    data = res.json()
    assert data["answered"] is False
    assert data["handoff"] is True


def test_businesses_cannot_see_each_others_documents(client):
    add_fees(client, business="centre1")
    res = client.post(
        "/ask",
        json={"business_id": "centre2", "question": "What are the JEE batch fees?"},
    )
    assert res.json()["handoff"] is True
