from core.services.similarity_service import rank_by_similarity


def test_similarity_ranking_prefers_profession_match():
    records = [
        {"username": "alpha", "profession": "designer", "bio": "", "location": "", "inferred_region": ""},
        {"username": "beta", "profession": "developer", "bio": "", "location": "", "inferred_region": ""},
    ]
    result = rank_by_similarity(records, "designer", limit=10)
    assert result
    assert result[0]["username"] == "alpha"


def test_similarity_ranking_uses_collection_and_interaction_signals():
    records = [
        {
            "username": "ux_a",
            "profession": "",
            "bio": "",
            "location": "",
            "inferred_region": "",
            "collection_tags": "ux,design,product",
            "likes_count": 12,
            "saved_count": 18,
        },
        {
            "username": "ux_b",
            "profession": "",
            "bio": "",
            "location": "",
            "inferred_region": "",
            "collection_tags": "",
            "likes_count": 0,
            "saved_count": 0,
        },
    ]
    result = rank_by_similarity(records, "ux", limit=10)
    assert result
    assert result[0]["username"] == "ux_a"
