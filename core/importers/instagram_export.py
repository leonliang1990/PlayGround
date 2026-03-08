import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from core.models import FollowRecord

USERNAME_URL_PATTERN = re.compile(r"instagram\.com/(?:_u/)?([a-zA-Z0-9._]+)/?")


def _is_probable_username(value: str) -> bool:
    if not value:
        return False
    candidate = value.strip().lstrip("@")
    if " " in candidate:
        return False
    return 1 <= len(candidate) <= 30


def _extract_username_entries(node, source_file: str, result: List[Tuple[str, Optional[int], str]]) -> None:
    if isinstance(node, dict):
        value = node.get("value")
        timestamp = node.get("timestamp")
        if isinstance(value, str) and _is_probable_username(value):
            username = value.strip().lstrip("@").lower()
            ts = timestamp if isinstance(timestamp, int) else None
            result.append((username, ts, source_file))

        # Newer Instagram export structure in following.json:
        # { "title": "<username>", "string_list_data": [{"href": ".../_u/<username>", "timestamp": ...}] }
        title = node.get("title")
        if isinstance(title, str) and _is_probable_username(title):
            username = title.strip().lstrip("@").lower()
            ts = None
            string_list = node.get("string_list_data")
            if isinstance(string_list, list):
                for entry in string_list:
                    if isinstance(entry, dict) and isinstance(entry.get("timestamp"), int):
                        ts = entry.get("timestamp")
                        break
            if ts is None and isinstance(timestamp, int):
                ts = timestamp
            result.append((username, ts, source_file))

        href = node.get("href")
        if isinstance(href, str):
            extracted = _extract_username_from_url(href)
            if extracted:
                ts = timestamp if isinstance(timestamp, int) else None
                result.append((extracted, ts, source_file))

        for child in node.values():
            _extract_username_entries(child, source_file, result)
    elif isinstance(node, list):
        for child in node:
            _extract_username_entries(child, source_file, result)


def _discover_following_files(input_path: Path) -> List[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() == ".json" else []

    patterns = [
        "**/followers_and_following/following*.json",
        "**/connections/followers_and_following/following*.json",
        "**/following*.json",
    ]
    discovered: List[Path] = []
    for pattern in patterns:
        discovered.extend(input_path.glob(pattern))
    # De-duplicate and keep deterministic order.
    unique = sorted({p.resolve() for p in discovered})
    return [Path(p) for p in unique]


def _discover_interest_files(input_path: Path) -> List[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() == ".json" else []

    patterns = [
        "**/likes/**/*.json",
        "**/likes*.json",
        "**/saved/**/*.json",
        "**/*saved*.json",
        "**/collections/**/*.json",
    ]
    discovered: List[Path] = []
    for pattern in patterns:
        discovered.extend(input_path.glob(pattern))
    unique = sorted({p.resolve() for p in discovered})
    return [Path(p) for p in unique]


def _extract_username_from_url(url: str) -> Optional[str]:
    if not isinstance(url, str):
        return None
    match = USERNAME_URL_PATTERN.search(url)
    if not match:
        return None
    segment = (match.group(1) or "").strip().lower().lstrip("@")
    # Ignore post/reel/story path roots.
    if segment in {"p", "reel", "reels", "stories", "explore", "tv"}:
        return None
    if _is_probable_username(segment):
        return segment
    return None


def _extract_collection_hint(value: str) -> Optional[str]:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if not candidate:
        return None
    if _is_probable_username(candidate):
        return None
    if candidate.startswith("http://") or candidate.startswith("https://"):
        return None
    if len(candidate) > 64:
        return None
    return candidate


def _scan_interest_node(
    node,
    *,
    username_counts: Dict[str, Dict[str, int]],
    collection_tags: Dict[str, Set[str]],
    context_tags: Set[str],
    source_kind: str,
) -> None:
    if isinstance(node, dict):
        local_tags = set(context_tags)
        for key in ("title", "name", "collection_name"):
            hint = _extract_collection_hint(node.get(key, ""))
            if hint:
                local_tags.add(hint)

        for k, v in node.items():
            if isinstance(k, str):
                hint = _extract_collection_hint(k)
                if hint and isinstance(v, (dict, list)):
                    local_tags.add(hint)

            if k == "href" and isinstance(v, str):
                maybe_username = _extract_username_from_url(v)
                if maybe_username:
                    counters = username_counts.setdefault(maybe_username, {"likes_count": 0, "saved_count": 0})
                    counters[source_kind] += 1
                    if local_tags:
                        tags = collection_tags.setdefault(maybe_username, set())
                        tags.update(local_tags)
            elif k == "value" and isinstance(v, str) and _is_probable_username(v):
                maybe_username = v.strip().lstrip("@").lower()
                counters = username_counts.setdefault(maybe_username, {"likes_count": 0, "saved_count": 0})
                counters[source_kind] += 1
                if local_tags:
                    tags = collection_tags.setdefault(maybe_username, set())
                    tags.update(local_tags)

            _scan_interest_node(
                v,
                username_counts=username_counts,
                collection_tags=collection_tags,
                context_tags=local_tags,
                source_kind=source_kind,
            )

        # Many saved/liked exports put username in "title" while href points to /p/ or /reel/.
        title = node.get("title")
        if isinstance(title, str) and _is_probable_username(title):
            maybe_username = title.strip().lstrip("@").lower()
            counters = username_counts.setdefault(maybe_username, {"likes_count": 0, "saved_count": 0})
            counters[source_kind] += 1
            if local_tags:
                tags = collection_tags.setdefault(maybe_username, set())
                tags.update(local_tags)
    elif isinstance(node, list):
        for child in node:
            _scan_interest_node(
                child,
                username_counts=username_counts,
                collection_tags=collection_tags,
                context_tags=context_tags,
                source_kind=source_kind,
            )


def load_follow_records(input_path: str) -> List[FollowRecord]:
    path = Path(input_path).expanduser()
    files = _discover_following_files(path)
    if not files:
        raise FileNotFoundError(
            "No matching following JSON files found. Expected paths like followers_and_following/following*.json"
        )

    merged: Dict[str, FollowRecord] = {}

    for file_path in files:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        extracted: List[Tuple[str, Optional[int], str]] = []
        _extract_username_entries(payload, str(file_path), extracted)

        for username, timestamp, source_file in extracted:
            existing = merged.get(username)
            profile_url = f"https://www.instagram.com/{username}/"
            if not existing:
                merged[username] = FollowRecord(
                    username=username,
                    followed_at=timestamp,
                    profile_url=profile_url,
                    source_file=source_file,
                )
                continue

            # Keep earliest known timestamp as the best approximation of first follow time.
            if timestamp is not None:
                if existing.followed_at is None or timestamp < existing.followed_at:
                    existing.followed_at = timestamp

    return sorted(merged.values(), key=lambda r: (r.followed_at or 0, r.username))


def load_interest_signals(input_path: str) -> Dict[str, Dict[str, str | int]]:
    path = Path(input_path).expanduser()
    files = _discover_interest_files(path)
    if not files:
        return {}

    username_counts: Dict[str, Dict[str, int]] = {}
    collection_tags: Dict[str, Set[str]] = {}

    for file_path in files:
        lower_name = file_path.name.lower()
        source_kind = "likes_count" if "like" in lower_name else "saved_count"

        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        base_tags = {file_path.stem.lower().replace("_", " ")} if "saved" in lower_name or "collection" in lower_name else set()
        _scan_interest_node(
            payload,
            username_counts=username_counts,
            collection_tags=collection_tags,
            context_tags=base_tags,
            source_kind=source_kind,
        )

    output: Dict[str, Dict[str, str | int]] = {}
    for username, counts in username_counts.items():
        tags = sorted(collection_tags.get(username, set()))
        output[username] = {
            "likes_count": int(counts.get("likes_count", 0)),
            "saved_count": int(counts.get("saved_count", 0)),
            "collection_tags": ",".join(tags),
        }
    return output


def load_metadata_csv(csv_path: str) -> Dict[str, Dict[str, str]]:
    path = Path(csv_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {csv_path}")

    merged: Dict[str, Dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"username"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("Metadata CSV must include a 'username' column.")

        for row in reader:
            raw_username = (row.get("username") or "").strip().lstrip("@").lower()
            if not raw_username:
                continue
            merged[raw_username] = {
                "bio": (row.get("bio") or "").strip(),
                "full_name": (row.get("full_name") or "").strip(),
                "location": (row.get("location") or "").strip(),
                "profession": (row.get("profession") or "").strip(),
            }
    return merged
