from app.search import search

ROWS = [
    {"text": "JEE batch fees are 45000 rupees per year."},
    {"text": "Classes run Monday to Friday from 5 pm to 8 pm."},
]


def test_best_match_ranks_first():
    hits = search("What are the JEE batch fees?", ROWS)
    assert hits[0]["text"].startswith("JEE batch fees")
    assert hits[0]["coverage"] == 1.0


def test_unrelated_question_has_no_hits():
    assert search("Do you give scholarships?", ROWS) == []
