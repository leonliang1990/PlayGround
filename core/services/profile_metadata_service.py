import csv
import re
import time
from html import unescape
from pathlib import Path
from typing import Dict, List

import requests


OG_TITLE_PATTERN = re.compile(
    r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
    re.IGNORECASE,
)
OG_DESC_PATTERN = re.compile(
    r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"',
    re.IGNORECASE,
)
BIO_JSON_PATTERN = re.compile(r'"biography":"(.*?)"', re.IGNORECASE)
FULLNAME_JSON_PATTERN = re.compile(r'"full_name":"(.*?)"', re.IGNORECASE)
LOCATION_HINT_PATTERN = re.compile(
    r"\b(milan|milano|rome|roma|paris|berlin|tokyo|seoul|london|amsterdam|barcelona|madrid|new york|nyc)\b",
    re.IGNORECASE,
)
PROFESSION_HINT_PATTERN = re.compile(
    r"\b(designer|director|artist|photographer|illustrator|animator|developer|studio|architect|stylist)\b",
    re.IGNORECASE,
)


def _clean_json_escaped_text(raw: str) -> str:
    text = raw.encode("utf-8").decode("unicode_escape")
    return unescape(text).strip()


def _extract_line_by_hint(text: str, pattern: re.Pattern[str]) -> str:
    for line in [ln.strip() for ln in text.splitlines() if ln.strip()]:
        if pattern.search(line):
            return line
    return ""


class ProfileMetadataService:
    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        }

    def fetch_metadata(self, username: str) -> Dict[str, str]:
        profile_url = f"https://www.instagram.com/{username}/"
        response = requests.get(profile_url, headers=self.headers, timeout=10)
        if response.status_code != 200:
            return {"username": username, "bio": "", "full_name": "", "location": "", "profession": ""}

        html = response.text

        full_name = ""
        bio = ""

        full_name_match = FULLNAME_JSON_PATTERN.search(html)
        if full_name_match:
            full_name = _clean_json_escaped_text(full_name_match.group(1))
        else:
            og_title_match = OG_TITLE_PATTERN.search(html)
            if og_title_match:
                og_title = unescape(og_title_match.group(1))
                # Pattern commonly looks like "Name (@username) • Instagram..."
                full_name = og_title.split("(@")[0].strip()

        bio_match = BIO_JSON_PATTERN.search(html)
        if bio_match:
            bio = _clean_json_escaped_text(bio_match.group(1))
        else:
            og_desc_match = OG_DESC_PATTERN.search(html)
            if og_desc_match:
                og_desc = unescape(og_desc_match.group(1))
                bio = og_desc.split("Followers")[0].strip()

        location = _extract_line_by_hint(bio, LOCATION_HINT_PATTERN)
        profession = _extract_line_by_hint(bio, PROFESSION_HINT_PATTERN)

        return {
            "username": username,
            "bio": bio,
            "full_name": full_name,
            "location": location,
            "profession": profession,
        }

    def generate_metadata_csv(
        self,
        usernames: List[str],
        output_path: str,
        *,
        max_accounts: int = 300,
        delay_seconds: float = 0.8,
    ) -> Dict[str, int | str]:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        rows: List[Dict[str, str]] = []
        attempted = 0
        success = 0

        deduped: List[str] = []
        seen = set()
        for name in usernames:
            norm = (name or "").strip().lstrip("@").lower()
            if norm and norm not in seen:
                seen.add(norm)
                deduped.append(norm)

        for username in deduped[:max_accounts]:
            attempted += 1
            try:
                row = self.fetch_metadata(username)
                if row.get("bio") or row.get("full_name") or row.get("location") or row.get("profession"):
                    success += 1
                rows.append(row)
            except requests.RequestException:
                rows.append({"username": username, "bio": "", "full_name": "", "location": "", "profession": ""})
            time.sleep(delay_seconds)

        with target.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["username", "bio", "full_name", "location", "profession"])
            writer.writeheader()
            writer.writerows(rows)

        return {"attempted": attempted, "success": success, "output_path": str(target)}
