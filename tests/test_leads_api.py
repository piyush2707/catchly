def new_lead(client, business, phone="+91 98765 43210"):
    return client.post(
        "/leads",
        json={
            "business_id": business,
            "name": "Riya",
            "phone": phone,
            "interest": "JEE batch",
        },
    )


def stats(client, business, headers):
    return client.get(
        "/dashboard", params={"business_id": business}, headers=headers
    ).json()


def test_creating_a_lead_schedules_followups(client, make_business):
    biz, headers = make_business()
    assert new_lead(client, biz).status_code == 201
    data = stats(client, biz, headers)
    assert data["leads"]["new"] == 1
    assert data["followups"]["pending"] == 3


def test_bad_phone_number_is_rejected(client, make_business):
    biz, _ = make_business()
    assert new_lead(client, biz, phone="abc").status_code == 422


def test_replied_lead_stops_followups(client, make_business):
    biz, headers = make_business()
    lead_id = new_lead(client, biz).json()["lead_id"]
    res = client.patch(
        f"/leads/{lead_id}",
        json={"business_id": biz, "status": "replied"},
        headers=headers,
    )
    assert res.status_code == 200
    data = stats(client, biz, headers)
    assert data["followups"]["pending"] == 0
    assert data["followups"]["cancelled"] == 3
    assert data["leads"]["replied"] == 1


def test_other_business_cannot_update_a_lead(client, make_business):
    biz1, _ = make_business("One")
    biz2, headers2 = make_business("Two")
    lead_id = new_lead(client, biz1).json()["lead_id"]
    res = client.patch(
        f"/leads/{lead_id}",
        json={"business_id": biz2, "status": "lost"},
        headers=headers2,
    )
    assert res.status_code == 404


def test_leads_are_private_to_each_business(client, make_business):
    biz1, _ = make_business("One")
    biz2, headers2 = make_business("Two")
    new_lead(client, biz1)
    res = client.get("/leads", params={"business_id": biz2}, headers=headers2)
    assert res.json()["leads"] == []


def test_run_followups_sends_nothing_when_not_due(client, make_business):
    biz, headers = make_business()
    new_lead(client, biz)
    res = client.post(
        "/followups/run", params={"business_id": biz}, headers=headers
    )
    assert res.json()["count"] == 0
