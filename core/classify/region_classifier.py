import json
import re
from pathlib import Path
from typing import Dict, List

from core.models import FollowRecord


DEFAULT_REGION_KEYWORDS: Dict[str, List[str]] = {
    "korea": ["korea", "korean", "seoul", "busan", "kr", "대한민국", "한국", "서울", "부산"],
    "japan": ["japan", "japanese", "tokyo", "osaka", "jp", "日本", "東京", "大阪"],
    "china": ["china", "chinese", "beijing", "shanghai", "cn", "中国", "北京", "上海"],
    "taiwan": ["taiwan", "taipei", "tw", "台灣", "台湾", "台北"],
    "hong_kong": ["hong kong", "hk", "香港"],
    "singapore": ["singapore", "sg"],
    "usa": [
        "usa",
        "united states",
        "us",
        "new york",
        "la",
        "los angeles",
        "california",
        "nyc",
        "sf",
    ],
    "uk": ["uk", "united kingdom", "london", "england"],
    "germany": ["germany", "berlin", "deutschland", "de"],
    "france": ["france", "paris", "fr"],
    "italy": ["italy", "italian", "milan", "milano", "rome", "roma", "torino", "turin"],
    "spain": ["spain", "spanish", "madrid", "barcelona", "valencia"],
    "netherlands": ["netherlands", "dutch", "amsterdam", "rotterdam", "utrecht"],
}


class RegionClassifier:
    def __init__(self, region_keywords: Dict[str, List[str]] | None = None, keyword_file: str = "data/region_keywords.json"):
        self.region_keywords = region_keywords or self._load_from_file(keyword_file) or DEFAULT_REGION_KEYWORDS

    def _load_from_file(self, keyword_file: str) -> Dict[str, List[str]]:
        path = Path(keyword_file)
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {}
            normalized: Dict[str, List[str]] = {}
            for k, v in payload.items():
                if isinstance(k, str) and isinstance(v, list):
                    normalized[k] = [str(x) for x in v]
            return normalized
        except (json.JSONDecodeError, OSError):
            return {}

    def infer_region(self, text: str) -> str:
        normalized = (text or "").lower()
        if not normalized:
            return ""

        best_region = ""
        best_score = 0.0
        for region, keywords in self.region_keywords.items():
            score = 0.0
            for kw in keywords:
                if self._keyword_match(normalized, kw.lower()):
                    # Longer phrases/city names are stronger region hints than short abbreviations.
                    score += 2.0 if len(kw) >= 4 else 1.0
            if score > best_score:
                best_region = region
                best_score = score
        return best_region

    def _keyword_match(self, text: str, keyword: str) -> bool:
        if not keyword:
            return False
        # CJK and spaced phrases are checked by substring.
        if any("\u4e00" <= ch <= "\u9fff" for ch in keyword) or " " in keyword:
            return keyword in text
        # For latin words, use word boundary to avoid false positives like "la" in unrelated words.
        pattern = rf"(?<![a-z0-9_]){re.escape(keyword)}(?![a-z0-9_])"
        return re.search(pattern, text) is not None

    def infer_for_record(self, record: FollowRecord) -> str:
        text = " ".join(
            [
                record.username or "",
                record.full_name or "",
                record.bio or "",
                record.location or "",
                record.profession or "",
            ]
        )
        return self.infer_region(text)
