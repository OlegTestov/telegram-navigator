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
    peer_id INTEGER,
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
CREATE INDEX IF NOT EXISTS idx_ct_posts_channel_date ON ct_posts(channel_id, post_date DESC);

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

CREATE TABLE IF NOT EXISTS ct_user_subscriptions (
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL REFERENCES ct_channels(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, channel_id)
);

CREATE TABLE IF NOT EXISTS ct_channel_digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES ct_channels(id) ON DELETE CASCADE,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    content TEXT NOT NULL,
    post_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(channel_id, period_start)
);
CREATE INDEX IF NOT EXISTS idx_ct_channel_digests_period ON ct_channel_digests(period_end DESC);

CREATE TABLE IF NOT EXISTS ct_digest_deliveries (
    user_id INTEGER NOT NULL,
    digest_id INTEGER NOT NULL REFERENCES ct_channel_digests(id) ON DELETE CASCADE,
    sent_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, digest_id)
);
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
        self._vec_enabled = False
        try:
            import sqlite_vec
            self.conn.enable_load_extension(True)
            sqlite_vec.load(self.conn)
            self.conn.enable_load_extension(False)
            self._vec_enabled = True
            logger.info("sqlite-vec extension loaded")
        except (ImportError, Exception) as e:
            logger.warning("sqlite-vec not available, vector search disabled: %s", e)
        self._init_schema()
        logger.info("SQLite database initialized at %s", db_path)

    def _init_schema(self):
        self.conn.executescript(SCHEMA_SQL)
        # Migrations
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(ct_channels)").fetchall()]
        if "peer_id" not in cols:
            self.conn.execute("ALTER TABLE ct_channels ADD COLUMN peer_id INTEGER")
        if "cached_toc" not in cols:
            self.conn.execute("ALTER TABLE ct_channels ADD COLUMN cached_toc TEXT")
        if "toc_updated_at" not in cols:
            self.conn.execute("ALTER TABLE ct_channels ADD COLUMN toc_updated_at TEXT")
        # Vector embeddings table
        if self._vec_enabled:
            self.conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS ct_post_embeddings "
                "USING vec0(post_id INTEGER PRIMARY KEY, embedding float[1536])"
            )
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

    def update_channel_peer_id(self, channel_id: int, peer_id: int):
        self.conn.execute(
            "UPDATE ct_channels SET peer_id = ? WHERE id = ?", (peer_id, channel_id)
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

    def save_cached_toc(self, channel_id: int, toc: str):
        self.conn.execute(
            "UPDATE ct_channels SET cached_toc = ?, toc_updated_at = ? WHERE id = ?",
            (toc, datetime.now(timezone.utc).isoformat(), channel_id),
        )
        self.conn.commit()

    def has_new_posts_since_toc(self, channel_id: int) -> bool:
        """Check if there are posts newer than last TOC generation."""
        row = self.conn.execute(
            "SELECT toc_updated_at FROM ct_channels WHERE id = ?", (channel_id,)
        ).fetchone()
        if not row or not row["toc_updated_at"]:
            return True  # no TOC yet → needs generation
        newest = self.conn.execute(
            "SELECT MAX(created_at) as newest FROM ct_posts WHERE channel_id = ?",
            (channel_id,),
        ).fetchone()
        if not newest or not newest["newest"]:
            return False
        return newest["newest"] > row["toc_updated_at"]

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

    def get_unclassified_count(self, channel_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM ct_posts WHERE channel_id = ? AND classified_at IS NULL",
            (channel_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    def get_unclassified_posts(self, channel_id: int, limit: int = 200) -> list[Post]:
        rows = self.conn.execute(
            """SELECT * FROM ct_posts
               WHERE channel_id = ? AND classified_at IS NULL
               ORDER BY message_id LIMIT ?""",
            (channel_id, limit),
        ).fetchall()
        return [Post.from_dict(_row_to_dict(r)) for r in rows]

    def get_posts_since(self, channel_id: int, since_iso: str) -> list[Post]:
        """Get all classified posts since a date (ISO format)."""
        rows = self.conn.execute(
            """SELECT * FROM ct_posts
               WHERE channel_id = ? AND post_date >= ? AND classified_at IS NOT NULL
               ORDER BY score DESC""",
            (channel_id, since_iso),
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

    # --- Embeddings & Hybrid Search ---

    def get_posts_without_embeddings(self, channel_id: int, limit: int = 500) -> list[Post]:
        if not self._vec_enabled:
            return []
        rows = self.conn.execute(
            """SELECT p.* FROM ct_posts p
               WHERE p.channel_id = ? AND p.classified_at IS NOT NULL
               AND p.id NOT IN (SELECT post_id FROM ct_post_embeddings)
               ORDER BY p.id LIMIT ?""",
            (channel_id, limit),
        ).fetchall()
        return [Post.from_dict(_row_to_dict(r)) for r in rows]

    def upsert_embeddings(self, embeddings: list[tuple[int, bytes]]):
        if not self._vec_enabled or not embeddings:
            return
        self.conn.executemany(
            "INSERT OR REPLACE INTO ct_post_embeddings(post_id, embedding) VALUES (?, ?)",
            embeddings,
        )
        self.conn.commit()

    def vector_search(self, query_embedding: bytes, limit: int = 50) -> list[tuple[int, float]]:
        if not self._vec_enabled:
            return []
        rows = self.conn.execute(
            """SELECT post_id, distance
               FROM ct_post_embeddings
               WHERE embedding MATCH ?
               ORDER BY distance LIMIT ?""",
            (query_embedding, limit),
        ).fetchall()
        return [(row[0], row[1]) for row in rows]

    def hybrid_search(
        self,
        channel_id: int,
        query: str,
        query_embedding: bytes | None = None,
        limit: int = 20,
    ) -> list[Post]:
        """Hybrid vector + keyword search."""
        scores: dict[int, dict] = {}

        # Vector search
        if query_embedding and self._vec_enabled:
            vec_results = self.vector_search(query_embedding, limit=50)
            for post_id, distance in vec_results:
                # OpenAI embeddings are L2-normalized, so:
                # cosine_similarity = 1 - (L2_distance² / 2)
                cosine_sim = max(0, 1.0 - (distance ** 2) / 2)
                scores[post_id] = {"vector": cosine_sim, "keyword": 0.0}

        # Keyword search
        pattern = f"%{query}%"
        kw_rows = self.conn.execute(
            """SELECT id, score FROM ct_posts
               WHERE channel_id = ? AND (text LIKE ? OR description LIKE ?)
               ORDER BY score DESC LIMIT 50""",
            (channel_id, pattern, pattern),
        ).fetchall()
        for row in kw_rows:
            pid = row["id"]
            if pid not in scores:
                scores[pid] = {"vector": 0.0, "keyword": 0.0}
            scores[pid]["keyword"] = 1.0

        if not scores:
            return []

        # Fetch full posts
        post_ids = list(scores.keys())
        placeholders = ",".join("?" * len(post_ids))
        post_rows = self.conn.execute(
            f"SELECT * FROM ct_posts WHERE id IN ({placeholders}) AND channel_id = ?",
            post_ids + [channel_id],
        ).fetchall()
        posts_by_id = {r["id"]: Post.from_dict(_row_to_dict(r)) for r in post_rows}

        # Rank
        ranked = []
        for pid, s in scores.items():
            if pid not in posts_by_id:
                continue
            post = posts_by_id[pid]
            final = s["vector"] * 0.6 + s["keyword"] * 0.2 + post.score * 0.2
            ranked.append((final, post))

        ranked.sort(key=lambda x: x[0], reverse=True)
        return [post for _, post in ranked[:limit]]

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

    def get_tags_for_posts(self, channel_id: int) -> dict[int, list[str]]:
        """Get tags for all posts in a channel. Returns {message_id: [tag1, tag2, ...]}."""
        rows = self.conn.execute(
            """SELECT p.message_id, t.name
               FROM ct_posts p
               JOIN ct_post_topics pt ON p.id = pt.post_id
               JOIN ct_topics t ON pt.topic_id = t.id
               WHERE p.channel_id = ?
               ORDER BY p.message_id""",
            (channel_id,),
        ).fetchall()
        result: dict[int, list[str]] = {}
        for row in rows:
            mid = row["message_id"]
            if mid not in result:
                result[mid] = []
            result[mid].append(row["name"])
        return result

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

    # --- Subscriptions ---

    def subscribe_user(self, user_id: int, channel_id: int):
        self.conn.execute(
            "INSERT OR IGNORE INTO ct_user_subscriptions (user_id, channel_id) VALUES (?, ?)",
            (user_id, channel_id),
        )
        self.conn.commit()

    def unsubscribe_user(self, user_id: int, channel_id: int):
        self.conn.execute(
            "DELETE FROM ct_user_subscriptions WHERE user_id = ? AND channel_id = ?",
            (user_id, channel_id),
        )
        self.conn.commit()

    def is_user_subscribed(self, user_id: int, channel_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM ct_user_subscriptions WHERE user_id = ? AND channel_id = ?",
            (user_id, channel_id),
        ).fetchone()
        return row is not None

    def get_user_subscriptions(self, user_id: int) -> list[Channel]:
        rows = self.conn.execute(
            """SELECT c.* FROM ct_channels c
               JOIN ct_user_subscriptions s ON c.id = s.channel_id
               WHERE s.user_id = ? AND c.is_active = 1
               ORDER BY c.username""",
            (user_id,),
        ).fetchall()
        return [Channel.from_dict(_row_to_dict(r)) for r in rows]

    def get_all_subscribers_with_channels(self) -> dict[int, list[int]]:
        """Returns {user_id: [channel_id, ...]} for all subscriptions."""
        rows = self.conn.execute(
            """SELECT s.user_id, s.channel_id FROM ct_user_subscriptions s
               JOIN ct_channels c ON c.id = s.channel_id
               WHERE c.is_active = 1"""
        ).fetchall()
        result: dict[int, list[int]] = {}
        for row in rows:
            uid = row["user_id"]
            if uid not in result:
                result[uid] = []
            result[uid].append(row["channel_id"])
        return result

    # --- Digests ---

    def get_posts_for_digest(
        self, channel_id: int, period_start: str, period_end: str, limit: int = 20
    ) -> list[Post]:
        rows = self.conn.execute(
            """SELECT * FROM ct_posts
               WHERE channel_id = ? AND post_date >= ? AND post_date < ?
               AND classified_at IS NOT NULL AND description IS NOT NULL
               ORDER BY score DESC LIMIT ?""",
            (channel_id, period_start, period_end, limit),
        ).fetchall()
        return [Post.from_dict(_row_to_dict(r)) for r in rows]

    def count_posts_for_digest(
        self, channel_id: int, period_start: str, period_end: str,
    ) -> int:
        row = self.conn.execute(
            """SELECT COUNT(*) as cnt FROM ct_posts
               WHERE channel_id = ? AND post_date >= ? AND post_date < ?
               AND classified_at IS NOT NULL AND description IS NOT NULL""",
            (channel_id, period_start, period_end),
        ).fetchone()
        return row["cnt"] if row else 0

    def save_channel_digest(
        self, channel_id: int, period_start: str, period_end: str,
        content: str, post_count: int,
    ) -> int:
        cursor = self.conn.execute(
            """INSERT INTO ct_channel_digests (channel_id, period_start, period_end, content, post_count)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(channel_id, period_start) DO UPDATE SET
                 content=excluded.content, post_count=excluded.post_count""",
            (channel_id, period_start, period_end, content, post_count),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_latest_digest_period_end(self) -> Optional[str]:
        row = self.conn.execute(
            "SELECT MAX(period_end) as latest FROM ct_channel_digests"
        ).fetchone()
        return row["latest"] if row and row["latest"] else None

    def get_channel_digests_for_period(self, period_start: str) -> list[dict]:
        """Get all digests generated for a specific period_start."""
        rows = self.conn.execute(
            "SELECT * FROM ct_channel_digests WHERE period_start = ?",
            (period_start,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def record_digest_delivery(self, user_id: int, digest_id: int):
        self.conn.execute(
            "INSERT OR IGNORE INTO ct_digest_deliveries (user_id, digest_id) VALUES (?, ?)",
            (user_id, digest_id),
        )
        self.conn.commit()

    def get_undelivered_digest_ids(self, user_id: int, digest_ids: list[int]) -> list[int]:
        """Return digest_ids from the list that haven't been delivered to user."""
        if not digest_ids:
            return []
        placeholders = ",".join("?" * len(digest_ids))
        rows = self.conn.execute(
            f"""SELECT digest_id FROM ct_digest_deliveries
                WHERE user_id = ? AND digest_id IN ({placeholders})""",
            [user_id] + digest_ids,
        ).fetchall()
        delivered = {row["digest_id"] for row in rows}
        return [did for did in digest_ids if did not in delivered]

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
