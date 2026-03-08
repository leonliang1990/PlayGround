import json

from core.importers.instagram_export import load_interest_signals


def test_load_interest_signals_from_likes_and_saved(tmp_path):
    likes_dir = tmp_path / "likes"
    likes_dir.mkdir(parents=True)
    saved_dir = tmp_path / "saved"
    saved_dir.mkdir(parents=True)

    (likes_dir / "liked_posts.json").write_text(
        json.dumps(
            {
                "likes_media_likes": [
                    {
                        "title": "Liked posts",
                        "string_list_data": [{"href": "https://www.instagram.com/example_user/"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    (saved_dir / "saved_collection.json").write_text(
        json.dumps(
            {
                "name": "Branding",
                "items": [{"href": "https://www.instagram.com/example_user/"}],
            }
        ),
        encoding="utf-8",
    )

    signals = load_interest_signals(str(tmp_path))
    assert "example_user" in signals
    assert signals["example_user"]["likes_count"] >= 1
    assert signals["example_user"]["saved_count"] >= 1
    assert "branding" in str(signals["example_user"]["collection_tags"])


def test_load_interest_signals_extracts_username_from_title(tmp_path):
    saved_dir = tmp_path / "saved"
    saved_dir.mkdir(parents=True)

    (saved_dir / "saved_posts.json").write_text(
        json.dumps(
            {
                "saved_saved_media": [
                    {
                        "title": "title_user",
                        "string_map_data": {
                            "Saved on": {
                                "href": "https://www.instagram.com/p/DIpHMantzmD/",
                                "timestamp": 1772916968,
                            }
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    signals = load_interest_signals(str(tmp_path))
    assert "title_user" in signals
    assert signals["title_user"]["saved_count"] >= 1
