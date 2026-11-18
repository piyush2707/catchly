import math
import re
from collections import Counter

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "of", "to", "in", "on",
    "at", "for", "and", "or", "do", "does", "you", "your", "i", "we", "it",
    "this", "that", "what", "when", "where", "how", "which", "who", "can",
    "will", "with", "from", "by", "be", "as", "me", "my",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.lower()) if t not in STOPWORDS]


def bm25_scores(query: str, texts: list[str], k1: float = 1.5, b: float = 0.75):
    q_terms = set(tokenize(query))
    docs = [tokenize(t) for t in texts]
    n = len(docs)
    if n == 0 or not q_terms:
        return [0.0] * n

    avg_len = (sum(len(d) for d in docs) / n) or 1.0
    doc_freq = Counter()
    for d in docs:
        for term in set(d):
            doc_freq[term] += 1

    scores = []
    for d in docs:
        tf = Counter(d)
        length = len(d)
        score = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (n - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            f = tf[term]
            score += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * length / avg_len))
        scores.append(score)
    return scores


def search(query: str, rows: list[dict], top_k: int = 3) -> list[dict]:
    """Rank rows (each has a 'text' key). Adds 'score' and 'coverage'.

    coverage = share of the question's meaningful words found in the passage.
    """
    q_terms = set(tokenize(query))
    if not q_terms or not rows:
        return []

    scores = bm25_scores(query, [r["text"] for r in rows])
    hits = []
    for row, score in zip(rows, scores):
        if score <= 0:
            continue
        matched = q_terms & set(tokenize(row["text"]))
        hits.append(
            {**row, "score": round(score, 4), "coverage": len(matched) / len(q_terms)}
        )
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:top_k]
