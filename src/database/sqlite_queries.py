"""SQLite implementation of DatabaseQueries."""

import logging
import math
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from src.database.models import Channel, Post, Topic
from src.utils.helpers import slugify
from src.config.constants import FRESHNESS_HALF_LIFE_DAYS, POSTS_PER_PAGE

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ct_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    title TEXT,
    added_by INTEGER NOT NULL,
    is_active INTEGER DEFAULT 1,
    pinned_message_id INTEGER,
    pinned_chat_id INTEGER,
    pinned_content_hash TEXT,
    last_fetched_message_id INTEGER DEFAULT 0,
    last_run_at TEXT,
    total_posts_indexed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ct_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES ct_channels(id) ON DELETE CASCADE,
    message_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    description TEXT,
    post_date TEXT NOT NULL,
    post_url TEXT NOT NULL,
    has_media INTEGER DEFAULT 0,
    views INTEGER DEFAULT 0,
    forwards INTEGER DEFAULT 0,
    reactions_count INTEGER DEFAULT 0,
    usefulness_score REAL DEFAULT 0.5,
    score REAL DEFAULT 0,
    classified_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(channel_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_ct_posts_channel ON ct_posts(channel_id);
CREATE INDEX IF NOT EXISTS idx_ct_posts_score ON ct_posts(channel_id, score DESC);

CREATE TABLE IF NOT EXISTS ct_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES ct_channels(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    emoji TEXT DEFAULT '',
    summary TEXT,
    post_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(channel_id, slug)
);

CREATE TABLE IF NOT EXISTS ct_post_topics (
    post_id INTEGER REFERENCES ct_posts(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES ct_topics(id) ON DELETE CASCADE,
    PRIMARY KEY (post_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_ct_post_topics_topic ON ct_post_topics(topic_id);
"""


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


class SQLiteQueries:
    """SQLite implementation with the same interface as DatabaseQueries."""

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()
        logger.info("SQLite database initialized at %s", db_path)

    def _init_schema(self):
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    # --- Channels ---

    def add_channel(self, username: str, added_by: int, title: str = None) -> Channel:
        self.conn.execute(
            """INSERT INTO ct_channels (username, added_by, title)
               VALUES (?, ?, ?)
               ON CONFLICT(username) DO UPDATE SET title=excluded.title""",
            (username, added_by, title),
        )
        self.conn.commit()
        return self.get_channel_by_username(username)

    def get_active_channels(self) -> list[Channel]:
        rows = self.conn.execute(
            "SELECT * FROM ct_channels WHERE is_active = 1"
        ).fetchall()
        return [Channel.from_dict(_row_to_dict(r)) for r in rows]

    def get_channel_by_username(self, username: str) -> Optional[Channel]:
        row = self.conn.execute(
            "SELECT * FROM ct_channels WHERE username = ?", (username,)
        ).fetchone()
        return Channel.from_dict(_row_to_dict(row)) if row else None

    def get_channel_by_id(self, channel_id: int) -> Optional[Channel]:
        row = self.conn.execute(
            "SELECT * FROM ct_channels WHERE id = ?", (channel_id,)
        ).fetchone()
        return Channel.from_dict(_row_to_dict(row)) if row else None

    def update_channel_sync(
        self, channel_id: int, last_message_id: int, total_indexed: int
    ):
        self.conn.execute(
            """UPDATE ct_channels
               SET last_fetched_message_id = ?, last_run_at = ?, total_posts_indexed = ?
               WHERE id = ?""",
            (last_message_id, datetime.now(timezone.utc).isoformat(), total_indexed, channel_id),
        )
        self.conn.commit()

    def update_channel_title(self, channel_id: int, title: str):
        self.conn.execute(
            "UPDATE ct_channels SET title = ? WHERE id = ?", (title, channel_id)
        )
        self.conn.commit()

    def set_channel_pinned(self, channel_id: int, chat_id: int, message_id: int):
        self.conn.execute(
            "UPDATE ct_channels SET pinned_chat_id = ?, pinned_message_id = ? WHERE id = ?",
            (chat_id, message_id, channel_id),
        )
        self.conn.commit()

    def update_pinned_hash(self, channel_id: int, hash_val: str):
        self.conn.execute(
            "UPDATE ct_channels SET pinned_content_hash = ? WHERE id = ?",
            (hash_val, channel_id),
        )
        self.conn.commit()

    def clear_channel_pinned(self, channel_id: int):
        self.conn.execute(
            "UPDATE ct_channels SET pinned_message_id = NULL, pinned_chat_id = NULL, pinned_content_hash = NULL WHERE id = ?",
            (channel_id,),
        )
        self.conn.commit()

    def delete_channel(self, channel_id: int):
        self.conn.execute("DELETE FROM ct_channels WHERE id = ?", (channel_id,))
        self.conn.commit()

    # --- Posts ---

    def upsert_posts(self, channel_id: int, posts: list[dict]) -> int:
        if not posts:
            return 0
        count = 0
        for p in posts:
            cursor = self.conn.execute(
                """INSERT OR IGNORE INTO ct_posts
                   (channel_id, message_id, text, post_date, post_url, has_media, views, forwards, reactions_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    channel_id, p["message_id"], p["text"], p["post_date"],
                    p["post_url"], int(p.get("has_media", False)),
                    p.get("views", 0), p.get("forwards", 0), p.get("reactions_count", 0),
                ),
            )
            count += cursor.rowcount
        self.conn.commit()
        return count

    def get_unclassified_posts(self, channel_id: int, limit: int = 200) -> list[Post]:
        rows = self.conn.execute(
            """SELECT * FROM ct_posts
               WHERE channel_id = ? AND classified_at IS NULL
               ORDER BY message_id LIMIT ?""",
            (channel_id, limit),
        ).fetchall()
        return [Post.from_dict(_row_to_dict(r)) for r in rows]

    def set_post_classification(self, post_id: int, description: str, usefulness: float):
        self.conn.execute(
            """UPDATE ct_posts
               SET description = ?, usefulness_score = ?, classified_at = ?
               WHERE id = ?""",
            (description, usefulness / 10.0, datetime.now(timezone.utc).isoformat(), post_id),
        )
        self.conn.commit()

    def clear_post_classification(self, channel_id: int, message_id: int):
        self.conn.execute(
            "UPDATE ct_posts SET classified_at = NULL WHERE channel_id = ? AND message_id = ?",
            (channel_id, message_id),
        )
        row = self.conn.execute(
            "SELECT id FROM ct_posts WHERE channel_id = ? AND message_id = ?",
            (channel_id, message_id),
        ).fetchone()
        if row:
            self.conn.execute("DELETE FROM ct_post_topics WHERE post_id = ?", (row["id"],))
        self.conn.commit()

    def get_posts_by_topic(
        self, topic_id: int, page: int = 0, limit: int = POSTS_PER_PAGE
    ) -> list[Post]:
        rows = self.conn.execute(
            """SELECT p.* FROM ct_posts p
               JOIN ct_post_topics pt ON p.id = pt.post_id
               WHERE pt.topic_id = ?
               ORDER BY p.score DESC
               LIMIT ? OFFSET ?""",
            (topic_id, limit, page * limit),
        ).fetchall()
        return [Post.from_dict(_row_to_dict(r)) for r in rows]

    def get_top_posts_by_topic(self, topic_id: int, limit: int = 3) -> list[Post]:
        rows = self.conn.execute(
            """SELECT p.* FROM ct_posts p
               JOIN ct_post_topics pt ON p.id = pt.post_id
               WHERE pt.topic_id = ?
               ORDER BY p.score DESC LIMIT ?""",
            (topic_id, limit),
        ).fetchall()
        return [Post.from_dict(_row_to_dict(r)) for r in rows]

    def search_posts(self, channel_id: int, query: str, limit: int = 20) -> list[Post]:
        pattern = f"%{query}%"
        rows = self.conn.execute(
            """SELECT * FROM ct_posts
               WHERE channel_id = ? AND (text LIKE ? OR description LIKE ?)
               ORDER BY score DESC LIMIT ?""",
            (channel_id, pattern, pattern, limit),
        ).fetchall()
        return [Post.from_dict(_row_to_dict(r)) for r in rows]

    def get_channel_post_count(self, channel_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM ct_posts WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        return row["cnt"] if row else 0

    def recalculate_scores(self, channel_id: int):
        rows = self.conn.execute(
            "SELECT id, views, forwards, reactions_count, post_date, usefulness_score FROM ct_posts WHERE channel_id = ?",
            (channel_id,),
        ).fetchall()
        if not rows:
            return

        now = datetime.now(timezone.utc)
        max_eng = 1.0
        engagements = []
        for row in rows:
            eng = math.log(max(row["views"] or 0, 1)) * 0.5 + (row["forwards"] or 0) * 2 + (row["reactions_count"] or 0)
            engagements.append(eng)
            if eng > max_eng:
                max_eng = eng

        updates = []
        for i, row in enumerate(rows):
            engagement_norm = min(1.0, engagements[i] / max_eng)
            post_date = row["post_date"]
            if isinstance(post_date, str):
                post_date = datetime.fromisoformat(post_date.replace("Z", "+00:00"))
            days_old = (now - post_date).total_seconds() / 86400
            freshness = math.exp(-days_old / FRESHNESS_HALF_LIFE_DAYS)
            usefulness = row["usefulness_score"] or 0.5
            score = round(engagement_norm * 0.4 + freshness * 0.3 + usefulness * 0.3, 4)
            updates.append((score, row["id"]))

        self.conn.executemany("UPDATE ct_posts SET score = ? WHERE id = ?", updates)
        self.conn.commit()

    # --- Topics ---

    def get_or_create_topic(self, channel_id: int, name: str) -> Topic:
        slug = slugify(name)
        row = self.conn.execute(
            "SELECT * FROM ct_topics WHERE channel_id = ? AND slug = ?",
            (channel_id, slug),
        ).fetchone()
        if row:
            return Topic.from_dict(_row_to_dict(row))

        self.conn.execute(
            "INSERT INTO ct_topics (channel_id, name, slug) VALUES (?, ?, ?)",
            (channel_id, name, slug),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM ct_topics WHERE channel_id = ? AND slug = ?",
            (channel_id, slug),
        ).fetchone()
        return Topic.from_dict(_row_to_dict(row))

    def get_topics(self, channel_id: int) -> list[Topic]:
        rows = self.conn.execute(
            "SELECT * FROM ct_topics WHERE channel_id = ? ORDER BY post_count DESC",
            (channel_id,),
        ).fetchall()
        return [Topic.from_dict(_row_to_dict(r)) for r in rows]

    def get_topic_by_slug(self, channel_id: int, slug: str) -> Optional[Topic]:
        row = self.conn.execute(
            "SELECT * FROM ct_topics WHERE channel_id = ? AND slug = ?",
            (channel_id, slug),
        ).fetchone()
        return Topic.from_dict(_row_to_dict(row)) if row else None

    def link_post_topic(self, post_id: int, topic_id: int):
        self.conn.execute(
            "INSERT OR IGNORE INTO ct_post_topics (post_id, topic_id) VALUES (?, ?)",
            (post_id, topic_id),
        )
        self.conn.commit()

    def update_topic_counts(self, channel_id: int):
        topics = self.get_topics(channel_id)
        for topic in topics:
            row = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM ct_post_topics WHERE topic_id = ?",
                (topic.id,),
            ).fetchone()
            count = row["cnt"] if row else 0
            if count != topic.post_count:
                self.conn.execute(
                    "UPDATE ct_topics SET post_count = ? WHERE id = ?",
                    (count, topic.id),
                )
            if count == 0:
                self.conn.execute("DELETE FROM ct_topics WHERE id = ?", (topic.id,))
        self.conn.commit()

    def update_topic_summary(self, topic_id: int, summary: str):
        self.conn.execute(
            "UPDATE ct_topics SET summary = ? WHERE id = ?", (summary, topic_id)
        )
        self.conn.commit()

    def get_topic_post_count(self, topic_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM ct_post_topics WHERE topic_id = ?", (topic_id,)
        ).fetchone()
        return row["cnt"] if row else 0

    # --- Stats ---

    def get_stats(self) -> dict:
        channels = self.get_active_channels()
        total_posts = 0
        total_topics = 0
        for ch in channels:
            total_posts += self.get_channel_post_count(ch.id)
            total_topics += len(self.get_topics(ch.id))
        return {
            "channels": len(channels),
            "total_posts": total_posts,
            "total_topics": total_topics,
        }
