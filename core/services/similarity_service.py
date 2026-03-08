import re
from math import log1p
from typing import Dict, List


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_\u4e00-\u9fff]+")


def tokenize(text: str) -> List[str]:
    normalized = (text or "").lower()
    return TOKEN_PATTERN.findall(normalized)


def _record_text(record: Dict) -> str:
    return " ".join(
        [
            record.get("username", ""),
            record.get("full_name", ""),
            record.get("bio", ""),
            record.get("location", ""),
            record.get("profession", ""),
            record.get("inferred_region", ""),
            (record.get("collection_tags") or "").replace(",", " "),
        ]
    ).lower()


def score_record(record: Dict, query: str) -> float:
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0

    text = _record_text(record)
    record_tokens = set(tokenize(text))
    query_set = set(query_tokens)

    overlap = len(record_tokens.intersection(query_set))
    score = overlap * 1.5

    username = (record.get("username") or "").lower()
    profession = (record.get("profession") or "").lower()
    inferred_region = (record.get("inferred_region") or "").lower()
    collection_tags = (record.get("collection_tags") or "").lower()
    likes_count = int(record.get("likes_count") or 0)
    saved_count = int(record.get("saved_count") or 0)

    for token in query_set:
        if token in username:
            score += 1.2
        if token in profession:
            score += 1.5
        if token in inferred_region:
            score += 1.5
        if token in collection_tags:
            score += 1.8
        if token in text:
            score += 0.4

    # Interaction prior: accounts you engage with more are slightly preferred.
    score += log1p(likes_count) * 0.25
    score += log1p(saved_count) * 0.45

    # Mild normalization to avoid overly long profile text dominating.
    return score / (1.0 + (len(record_tokens) / 120))


def rank_by_similarity(records: List[Dict], query: str, limit: int = 100) -> List[Dict]:
    if not query.strip():
        return records[:limit]

    scored: List[Dict] = []
    for record in records:
        score = score_record(record, query)
        if score <= 0:
            continue
        enriched = dict(record)
        enriched["similarity_score"] = round(score, 3)
        scored.append(enriched)

    scored.sort(key=lambda r: r.get("similarity_score", 0), reverse=True)
    return scored[:limit]
