from datetime import datetime
from typing import Dict, List, Optional


def _to_dt(ts: Optional[int]) -> Optional[datetime]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts)


def filter_records(
    records: List[Dict],
    region: str = "",
    text_keyword: str = "",
    collection_keyword: str = "",
    interacted_only: bool = False,
    date_start: Optional[datetime] = None,
    date_end: Optional[datetime] = None,
) -> List[Dict]:
    keyword = (text_keyword or "").strip().lower()
    collection_kw = (collection_keyword or "").strip().lower()
    expected_region = (region or "").strip().lower()

    out: List[Dict] = []
    for r in records:
        followed_dt = _to_dt(r.get("followed_at"))
        if date_start and (not followed_dt or followed_dt.date() < date_start.date()):
            continue
        if date_end and (not followed_dt or followed_dt.date() > date_end.date()):
            continue

        if expected_region and (r.get("inferred_region") or "").lower() != expected_region:
            continue

        if interacted_only:
            if int(r.get("likes_count") or 0) <= 0 and int(r.get("saved_count") or 0) <= 0:
                continue

        if keyword:
            haystack = " ".join(
                [
                    r.get("username", ""),
                    r.get("full_name", ""),
                    r.get("bio", ""),
                    r.get("location", ""),
                    r.get("profession", ""),
                    r.get("inferred_region", ""),
                ]
            ).lower()
            if keyword not in haystack:
                continue

        if collection_kw:
            tags = (r.get("collection_tags") or "").lower()
            if collection_kw not in tags:
                continue

        out.append(r)
    return out
