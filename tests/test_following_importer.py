import json

from core.importers.instagram_export import load_follow_records


def test_load_follow_records_supports_title_and_u_path(tmp_path):
    following_dir = tmp_path / "connections" / "followers_and_following"
    following_dir.mkdir(parents=True)

    (following_dir / "following.json").write_text(
        json.dumps(
            {
                "relationships_following": [
                    {
                        "title": "demo_user",
                        "string_list_data": [
                            {
                                "href": "https://www.instagram.com/_u/demo_user",
                                "timestamp": 1772916491,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    records = load_follow_records(str(tmp_path))
    assert records
    assert records[0].username == "demo_user"
    assert records[0].followed_at == 1772916491
