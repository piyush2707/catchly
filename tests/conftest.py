import pytest
from fastapi.testclient import TestClient

from app.main import app, limiter

ADMIN = "test-admin-key"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CATCHLY_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("CATCHLY_ADMIN_KEY", ADMIN)
    limiter.reset()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def make_business(client):
    def _make(name="Test Centre"):
        res = client.post(
            "/businesses", json={"name": name}, headers={"X-Admin-Key": ADMIN}
        )
        assert res.status_code == 201
        data = res.json()
        return data["business_id"], {"X-API-Key": data["api_key"]}

    return _make
