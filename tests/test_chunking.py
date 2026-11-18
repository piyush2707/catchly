from app.chunking import chunk_text


def test_empty_text_gives_no_chunks():
    assert chunk_text("   ") == []


def test_short_text_is_one_chunk():
    assert chunk_text("fees are 45000") == ["fees are 45000"]


def test_chunks_overlap():
    text = " ".join(f"w{i}" for i in range(300))
    chunks = chunk_text(text, max_words=120, overlap=20)
    assert len(chunks) == 3
    assert len(chunks[0].split()) == 120
    assert chunks[1].split()[0] == "w100"
