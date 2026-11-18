from datetime import datetime, timedelta, timezone

# Hours after the lead is created. Max 3 follow-ups, so we never spam.
SCHEDULE_HOURS = [24, 72, 168]

TEMPLATES = [
    "Hi {name}, thanks for your enquiry{about}. "
    "Is there anything we can help you with?",
    "Hi {name}, just checking in{about}. "
    "Would you like to speak with our team?",
    "Hi {name}, this is our last reminder{about}. "
    "Reply anytime and we will be happy to help.",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def fmt(dt: datetime) -> str:
    """Fixed-format UTC string, so text comparison matches time order."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_message(name: str, interest: str | None, step: int) -> str:
    about = f" about {interest}" if interest else ""
    return TEMPLATES[step].format(name=name, about=about)


def schedule_followups(conn, lead_id: int, created_at: datetime) -> None:
    for step, hours in enumerate(SCHEDULE_HOURS):
        due = created_at + timedelta(hours=hours)
        conn.execute(
            "INSERT INTO followups (lead_id, step, due_at) VALUES (?, ?, ?)",
            (lead_id, step, fmt(due)),
        )


def cancel_pending(conn, lead_id: int) -> None:
    conn.execute(
        "UPDATE followups SET status = 'cancelled' "
        "WHERE lead_id = ? AND status = 'pending'",
        (lead_id,),
    )


def run_due(conn, business_id: str, now: datetime) -> list[dict]:
    """Mark due follow-ups as sent and return the messages.

    Only the earliest due step per lead is sent. Other overdue steps are
    skipped, so a lead never gets several messages at once (for example
    after the server was offline).
    """
    rows = conn.execute(
        "SELECT f.id AS followup_id, f.step, l.id AS lead_id, l.name, "
        "l.phone, l.interest "
        "FROM followups f JOIN leads l ON l.id = f.lead_id "
        "WHERE l.business_id = ? AND l.status = 'new' "
        "AND f.status = 'pending' AND f.due_at <= ? "
        "ORDER BY f.lead_id, f.step",
        (business_id, fmt(now)),
    ).fetchall()

    sent = []
    seen_leads = set()
    for r in rows:
        if r["lead_id"] in seen_leads:
            conn.execute(
                "UPDATE followups SET status = 'skipped' WHERE id = ?",
                (r["followup_id"],),
            )
            continue
        seen_leads.add(r["lead_id"])

        message = build_message(r["name"], r["interest"], r["step"])
        conn.execute(
            "UPDATE followups SET status = 'sent', message = ?, sent_at = ? "
            "WHERE id = ?",
            (message, fmt(now), r["followup_id"]),
        )
        sent.append(
            {
                "followup_id": r["followup_id"],
                "lead_id": r["lead_id"],
                "name": r["name"],
                "phone": r["phone"],
                "message": message,
            }
        )
    return sent
