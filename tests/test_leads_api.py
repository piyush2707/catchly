import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CATCHLY_DB", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def new_lead(client, business="centre1", phone="+91 98765 43210"):
    return client.post(
        "/leads",
        json={
            "business_id": business,
            "name": "Riya",
            "phone": phone,
            "interest": "JEE batch",
        },
    )


def test_creating_a_lead_schedules_followups(client):
    res = new_lead(client)
    assert res.status_code == 201
    data = client.get("/dashboard", params={"business_id": "centre1"}).json()
    assert data["leads"]["new"] == 1
    assert data["followups"]["pending"] == 3


def test_bad_phone_number_is_rejected(client):
    assert new_lead(client, phone="abc").status_code == 422


def test_replied_lead_stops_followups(client):
    lead_id = new_lead(client).json()["lead_id"]
    res = client.patch(
        f"/leads/{lead_id}",
        json={"business_id": "centre1", "status": "replied"},
    )
    assert res.status_code == 200
    data = client.get("/dashboard", params={"business_id": "centre1"}).json()
    assert data["followups"]["pending"] == 0
    assert data["followups"]["cancelled"] == 3
    assert data["leads"]["replied"] == 1


def test_other_business_cannot_update_a_lead(client):
    lead_id = new_lead(client).json()["lead_id"]
    res = client.patch(
        f"/leads/{lead_id}",
        json={"business_id": "centre2", "status": "lost"},
    )
    assert res.status_code == 404


def test_leads_are_private_to_each_business(client):
    new_lead(client, business="centre1")
    res = client.get("/leads", params={"business_id": "centre2"})
    assert res.json()["leads"] == []


def test_run_followups_sends_nothing_when_not_due(client):
    new_lead(client)
    res = client.post("/followups/run", params={"business_id": "centre1"})
    assert res.json()["count"] == 0
