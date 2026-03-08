from dataclasses import dataclass
from typing import Optional


@dataclass
class FollowRecord:
    username: str
    followed_at: Optional[int] = None
    profile_url: Optional[str] = None
    bio: str = ""
    full_name: str = ""
    location: str = ""
    profession: str = ""
    inferred_region: str = ""
    source_file: str = ""
    likes_count: int = 0
    saved_count: int = 0
    collection_tags: str = ""
