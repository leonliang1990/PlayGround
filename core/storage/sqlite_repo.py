import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from core.models import FollowRecord


class SQLiteRepo:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS follows (
                    username TEXT PRIMARY KEY,
                    followed_at INTEGER,
                    profile_url TEXT,
                    bio TEXT DEFAULT '',
                    full_name TEXT DEFAULT '',
                    location TEXT DEFAULT '',
                    profession TEXT DEFAULT '',
                    inferred_region TEXT DEFAULT '',
                    likes_count INTEGER DEFAULT 0,
                    saved_count INTEGER DEFAULT 0,
                    collection_tags TEXT DEFAULT '',
                    source_file TEXT DEFAULT '',
                    ingested_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS avatar_cache (
                    username TEXT PRIMARY KEY,
                    avatar_url TEXT,
                    status TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "follows", "likes_count", "INTEGER DEFAULT 0")
            self._ensure_column(conn, "follows", "saved_count", "INTEGER DEFAULT 0")
            self._ensure_column(conn, "follows", "collection_tags", "TEXT DEFAULT ''")
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {r["name"] for r in rows}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

    def upsert_records(self, records: List[FollowRecord]) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                r.username,
                r.followed_at,
                r.profile_url or f"https://www.instagram.com/{r.username}/",
                r.bio,
                r.full_name,
                r.location,
                r.profession,
                r.inferred_region,
                r.likes_count,
                r.saved_count,
                r.collection_tags,
                r.source_file,
                now_iso,
            )
            for r in records
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO follows (
                    username, followed_at, profile_url, bio, full_name, location,
                    profession, inferred_region, likes_count, saved_count, collection_tags,
                    source_file, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    followed_at=COALESCE(excluded.followed_at, follows.followed_at),
                    profile_url=excluded.profile_url,
                    bio=CASE WHEN excluded.bio != '' THEN excluded.bio ELSE follows.bio END,
                    full_name=CASE WHEN excluded.full_name != '' THEN excluded.full_name ELSE follows.full_name END,
                    location=CASE WHEN excluded.location != '' THEN excluded.location ELSE follows.location END,
                    profession=CASE WHEN excluded.profession != '' THEN excluded.profession ELSE follows.profession END,
                    inferred_region=CASE WHEN excluded.inferred_region != '' THEN excluded.inferred_region ELSE follows.inferred_region END,
                    likes_count=MAX(COALESCE(excluded.likes_count, 0), COALESCE(follows.likes_count, 0)),
                    saved_count=MAX(COALESCE(excluded.saved_count, 0), COALESCE(follows.saved_count, 0)),
                    collection_tags=CASE
                        WHEN excluded.collection_tags != '' THEN excluded.collection_tags
                        ELSE follows.collection_tags
                    END,
                    source_file=excluded.source_file,
                    ingested_at=excluded.ingested_at
                """
                ,
                rows,
            )
            conn.commit()

    def list_records(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT username, followed_at, profile_url, bio, full_name, location,
                       profession, inferred_region, likes_count, saved_count, collection_tags,
                       source_file, ingested_at
                FROM follows
                ORDER BY COALESCE(followed_at, 0) DESC, username ASC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def get_avatar_cache(self, username: str, max_age_hours: int = 24) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT username, avatar_url, status, fetched_at FROM avatar_cache WHERE username = ?",
                (username,),
            ).fetchone()
        if not row:
            return None
        fetched_at = datetime.fromisoformat(row["fetched_at"])
        if datetime.now(timezone.utc) - fetched_at > timedelta(hours=max_age_hours):
            return None
        return dict(row)

    def upsert_avatar_cache(self, username: str, avatar_url: str, status: str) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO avatar_cache (username, avatar_url, status, fetched_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    avatar_url=excluded.avatar_url,
                    status=excluded.status,
                    fetched_at=excluded.fetched_at
                """,
                (username, avatar_url, status, now_iso),
            )
            conn.commit()
