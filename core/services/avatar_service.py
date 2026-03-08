import re
from html import unescape
from typing import Optional

import requests

from core.storage.sqlite_repo import SQLiteRepo


META_OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
    re.IGNORECASE,
)
IMG_AVATAR_PATTERN = re.compile(
    r'<img[^>]+(?:alt="[^"]*(?:头像|profile picture)[^"]*"[^>]*src="([^"]+)"|src="([^"]+)"[^>]*alt="[^"]*(?:头像|profile picture)[^"]*")',
    re.IGNORECASE,
)


class AvatarService:
    def __init__(self, repo: SQLiteRepo):
        self.repo = repo

    def get_avatar_url(self, username: str) -> Optional[str]:
        cached_ok = self.repo.get_avatar_cache(username=username, max_age_hours=72)
        if cached_ok and cached_ok.get("status") == "ok" and cached_ok.get("avatar_url"):
            return cached_ok.get("avatar_url") or None
        cached_fail = self.repo.get_avatar_cache(username=username, max_age_hours=2)
        if cached_fail and cached_fail.get("status") != "ok":
            return None

        profile_url = f"https://www.instagram.com/{username}/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        }
        try:
            response = requests.get(profile_url, headers=headers, timeout=8)
            if response.status_code != 200:
                self.repo.upsert_avatar_cache(username, "", f"http_{response.status_code}")
                return None

            match = META_OG_IMAGE_PATTERN.search(response.text)
            if match:
                avatar_url = unescape(match.group(1))
                self.repo.upsert_avatar_cache(username, avatar_url, "ok")
                return avatar_url

            fallback_match = IMG_AVATAR_PATTERN.search(response.text)
            if fallback_match:
                avatar_url = unescape(fallback_match.group(1) or fallback_match.group(2) or "")
                if avatar_url:
                    self.repo.upsert_avatar_cache(username, avatar_url, "ok")
                    return avatar_url

            if not match and not fallback_match:
                self.repo.upsert_avatar_cache(username, "", "missing_meta")
                return None
        except requests.RequestException:
            self.repo.upsert_avatar_cache(username, "", "network_error")
            return None
