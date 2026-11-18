from datetime import datetime, timedelta, timezone

import pytest

from app.db import get_conn, init_db
from app.followups import fmt, run_due, schedule_followups

START = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("CATCHLY_DB", str(tmp_path / "test.db"))
    init_db()


def make_lead(conn, name="Riya", interest="JEE batch"):
    cur = conn.execute(
        "INSERT INTO leads (business_id, name, phone, interest, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("c1", name, "9876543210", interest, fmt(START)),
    )
    lead_id = cur.lastrowid
    schedule_followups(conn, lead_id, START)
    return lead_id


def test_three_followups_are_scheduled(db):
    with get_conn() as conn:
        lead_id = make_lead(conn)
        rows = conn.execute(
            "SELECT due_at FROM followups WHERE lead_id = ? ORDER BY step",
            (lead_id,),
        ).fetchall()
    expected = [fmt(START + timedelta(hours=h)) for h in (24, 72, 168)]
    assert [r["due_at"] for r in rows] == expected


def test_nothing_is_due_before_24_hours(db):
    with get_conn() as conn:
        make_lead(conn)
        assert run_due(conn, "c1", START + timedelta(hours=23)) == []


def test_first_followup_is_due_after_24_hours(db):
    with get_conn() as conn:
        make_lead(conn)
        sent = run_due(conn, "c1", START + timedelta(hours=25))
    assert len(sent) == 1
    assert "Riya" in sent[0]["message"]
    assert "JEE batch" in sent[0]["message"]


def test_followup_is_never_sent_twice(db):
    with get_conn() as conn:
        make_lead(conn)
        later = START + timedelta(hours=25)
        assert len(run_due(conn, "c1", later)) == 1
        assert run_due(conn, "c1", later) == []


def test_overdue_steps_do_not_pile_up(db):
    with get_conn() as conn:
        lead_id = make_lead(conn)
        sent = run_due(conn, "c1", START + timedelta(days=9))
        statuses = [
            r["status"]
            for r in conn.execute(
                "SELECT status FROM followups WHERE lead_id = ? ORDER BY step",
                (lead_id,),
            ).fetchall()
        ]
    assert len(sent) == 1
    assert statuses == ["sent", "skipped", "skipped"]
