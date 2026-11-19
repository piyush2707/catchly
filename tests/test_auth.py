from app.db import get_conn
from tests.conftest import ADMIN


def test_creating_a_business_needs_the_admin_key(client):
    assert client.post("/businesses", json={"name": "A"}).status_code == 401
    bad = client.post(
        "/businesses", json={"name": "A"}, headers={"X-Admin-Key": "wrong"}
    )
    assert bad.status_code == 401


def test_admin_key_not_configured_is_an_error(client, monkeypatch):
    monkeypatch.delenv("CATCHLY_ADMIN_KEY", raising=False)
    res = client.post(
        "/businesses", json={"name": "A"}, headers={"X-Admin-Key": ADMIN}
    )
    assert res.status_code == 503


def test_api_key_is_stored_only_as_a_hash(client, make_business):
    _, headers = make_business()
    key = headers["X-API-Key"]
    with get_conn() as conn:
        stored = conn.execute("SELECT api_key_hash FROM businesses").fetchone()
    assert stored["api_key_hash"] != key
    assert key not in stored["api_key_hash"]


def test_private_endpoints_need_a_key(client, make_business):
    biz, _ = make_business()
    assert client.get("/leads", params={"business_id": biz}).status_code == 401
    assert client.get("/dashboard", params={"business_id": biz}).status_code == 401
    assert client.get("/documents", params={"business_id": biz}).status_code == 401
    assert client.post("/followups/run", params={"business_id": biz}).status_code == 401
    post = client.post(
        "/documents", json={"business_id": biz, "title": "T", "text": "hello"}
    )
    assert post.status_code == 401


def test_a_wrong_key_is_rejected(client, make_business):
    biz, _ = make_business()
    res = client.get(
        "/leads", params={"business_id": biz}, headers={"X-API-Key": "ctl_wrong"}
    )
    assert res.status_code == 401


def test_one_business_key_does_not_open_another_business(client, make_business):
    biz1, _ = make_business("One")
    _, headers2 = make_business("Two")
    res = client.get("/leads", params={"business_id": biz1}, headers=headers2)
    assert res.status_code == 401


def test_lead_for_unknown_business_is_rejected(client):
    res = client.post(
        "/leads",
        json={"business_id": "nope", "name": "Riya", "phone": "9876543210"},
    )
    assert res.status_code == 404


def test_public_endpoints_are_rate_limited(client, make_business):
    biz, _ = make_business()
    codes = [
        client.post("/ask", json={"business_id": biz, "question": "fees?"}).status_code
        for _ in range(31)
    ]
    assert codes[:30] == [200] * 30
    assert codes[30] == 429


def test_widget_dashboard_and_demo_pages_are_served(client):
    widget = client.get("/widget.js")
    assert widget.status_code == 200
    assert "javascript" in widget.headers["content-type"]
    assert client.get("/panel").status_code == 200
    assert client.get("/demo").status_code == 200
