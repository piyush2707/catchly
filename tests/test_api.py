FEES = "JEE batch fees are 45000 rupees per year. Classes run Monday to Friday."


def add_fees(client, business, headers):
    return client.post(
        "/documents",
        json={"business_id": business, "title": "Fee sheet", "text": FEES},
        headers=headers,
    )


def test_add_and_list_document(client, make_business):
    biz, headers = make_business()
    res = add_fees(client, biz, headers)
    assert res.status_code == 201
    assert res.json()["chunks"] == 1
    listing = client.get("/documents", params={"business_id": biz}, headers=headers)
    assert listing.json()["documents"][0]["title"] == "Fee sheet"


def test_empty_document_is_rejected(client, make_business):
    biz, headers = make_business()
    res = client.post(
        "/documents",
        json={"business_id": biz, "title": "Empty", "text": "   "},
        headers=headers,
    )
    assert res.status_code == 422


def test_question_is_answered_from_document(client, make_business):
    biz, headers = make_business()
    add_fees(client, biz, headers)
    res = client.post(
        "/ask", json={"business_id": biz, "question": "What are the JEE batch fees?"}
    )
    data = res.json()
    assert data["answered"] is True
    assert "45000" in data["answer"]
    assert data["sources"][0]["document"] == "Fee sheet"


def test_unknown_question_hands_off(client, make_business):
    biz, headers = make_business()
    add_fees(client, biz, headers)
    res = client.post(
        "/ask", json={"business_id": biz, "question": "Do you give scholarships?"}
    )
    data = res.json()
    assert data["answered"] is False
    assert data["handoff"] is True


def test_businesses_cannot_see_each_others_documents(client, make_business):
    biz1, headers1 = make_business("One")
    biz2, _ = make_business("Two")
    add_fees(client, biz1, headers1)
    res = client.post(
        "/ask", json={"business_id": biz2, "question": "What are the JEE batch fees?"}
    )
    assert res.json()["handoff"] is True
