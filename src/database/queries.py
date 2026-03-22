"""Database queries for content-table."""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from src.database.client import SupabaseClient
from src.database.models import Channel, Post, Topic
from src.utils.helpers import slugify
from src.config.constants import FRESHNESS_HALF_LIFE_DAYS, POSTS_PER_PAGE

logger = logging.getLogger(__name__)


class DatabaseQueries:
    """All database operations."""

    def __init__(self, db: SupabaseClient):
        self.db = db

    # --- Channels ---

    def add_channel(self, username: str, added_by: int, title: str = None) -> Channel:
        result = self.db.execute(
            lambda: self.db.client.table("ct_channels")
            .upsert(
                {"username": username, "added_by": added_by, "title": title},
                on_conflict="username",
            )
            .execute()
        )
        return Channel.from_dict(result.data[0])

    def get_active_channels(self) -> list[Channel]:
        result = self.db.execute(
            lambda: self.db.client.table("ct_channels")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        return [Channel.from_dict(row) for row in result.data]

    def get_channel_by_username(self, username: str) -> Optional[Channel]:
        result = self.db.execute(
            lambda: self.db.client.table("ct_channels")
            .select("*")
            .eq("username", username)
            .maybe_single()
            .execute()
        )
        return Channel.from_dict(result.data) if result.data else None

    def get_channel_by_id(self, channel_id: int) -> Optional[Channel]:
        result = self.db.execute(
            lambda: self.db.client.table("ct_channels")
            .select("*")
            .eq("id", channel_id)
            .maybe_single()
            .execute()
        )
        return Channel.from_dict(result.data) if result.data else None

    def update_channel_title(self, channel_id: int, title: str):
        self.db.execute(
            lambda: self.db.client.table("ct_channels")
            .update({"title": title})
            .eq("id", channel_id)
            .execute()
        )

    def update_channel_sync(
        self, channel_id: int, last_message_id: int, total_indexed: int
    ):
        self.db.execute(
            lambda: self.db.client.table("ct_channels")
            .update(
                {
                    "last_fetched_message_id": last_message_id,
                    "last_run_at": datetime.now(timezone.utc).isoformat(),
                    "total_posts_indexed": total_indexed,
                }
            )
            .eq("id", channel_id)
            .execute()
        )

    def set_channel_pinned(
        self, channel_id: int, chat_id: int, message_id: int
    ):
        self.db.execute(
            lambda: self.db.client.table("ct_channels")
            .update(
                {"pinned_chat_id": chat_id, "pinned_message_id": message_id}
            )
            .eq("id", channel_id)
            .execute()
        )

    def update_pinned_hash(self, channel_id: int, hash_val: str):
        self.db.execute(
            lambda: self.db.client.table("ct_channels")
            .update({"pinned_content_hash": hash_val})
            .eq("id", channel_id)
            .execute()
        )

    def clear_channel_pinned(self, channel_id: int):
        self.db.execute(
            lambda: self.db.client.table("ct_channels")
            .update({"pinned_message_id": None, "pinned_chat_id": None, "pinned_content_hash": None})
            .eq("id", channel_id)
            .execute()
        )

    def delete_channel(self, channel_id: int):
        self.db.execute(
            lambda: self.db.client.table("ct_channels")
            .delete()
            .eq("id", channel_id)
            .execute()
        )

    # --- Posts ---

    def upsert_posts(self, channel_id: int, posts: list[dict]) -> int:
        """Upsert posts, returns count of new posts."""
        if not posts:
            return 0
        rows = [
            {
                "channel_id": channel_id,
                "message_id": p["message_id"],
                "text": p["text"],
                "post_date": p["post_date"],
                "post_url": p["post_url"],
                "has_media": p.get("has_media", False),
                "views": p.get("views", 0),
                "forwards": p.get("forwards", 0),
                "reactions_count": p.get("reactions_count", 0),
            }
            for p in posts
        ]
        result = self.db.execute(
            lambda: self.db.client.table("ct_posts")
            .upsert(rows, on_conflict="channel_id,message_id", ignore_duplicates=True)
            .execute()
        )
        return len(result.data)

    def get_unclassified_posts(self, channel_id: int, limit: int = 200) -> list[Post]:
        result = self.db.execute(
            lambda: self.db.client.table("ct_posts")
            .select("*")
            .eq("channel_id", channel_id)
            .is_("classified_at", "null")
            .order("message_id")
            .limit(limit)
            .execute()
        )
        return [Post.from_dict(row) for row in result.data]

    def set_post_classification(
        self, post_id: int, description: str, usefulness: float
    ):
        self.db.execute(
            lambda: self.db.client.table("ct_posts")
            .update(
                {
                    "description": description,
                    "usefulness_score": usefulness / 10.0,
                    "classified_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", post_id)
            .execute()
        )

    def clear_post_classification(self, channel_id: int, message_id: int):
        """Mark a post as unclassified (for reclassification)."""
        self.db.execute(
            lambda: self.db.client.table("ct_posts")
            .update({"classified_at": None})
            .eq("channel_id", channel_id)
            .eq("message_id", message_id)
            .execute()
        )
        # Remove old topic associations
        post = self._get_post_by_message(channel_id, message_id)
        if post:
            self.db.execute(
                lambda: self.db.client.table("ct_post_topics")
                .delete()
                .eq("post_id", post.id)
                .execute()
            )

    def _get_post_by_message(self, channel_id: int, message_id: int) -> Optional[Post]:
        result = self.db.execute(
            lambda: self.db.client.table("ct_posts")
            .select("*")
            .eq("channel_id", channel_id)
            .eq("message_id", message_id)
            .maybe_single()
            .execute()
        )
        return Post.from_dict(result.data) if result.data else None

    def get_posts_by_topic(
        self, topic_id: int, page: int = 0, limit: int = POSTS_PER_PAGE
    ) -> list[Post]:
        result = self.db.execute(
            lambda: self.db.client.table("ct_post_topics")
            .select("post_id, ct_posts(*)")
            .eq("topic_id", topic_id)
            .order("post_id", desc=True)
            .range(page * limit, (page + 1) * limit - 1)
            .execute()
        )
        posts = []
        for row in result.data:
            if row.get("ct_posts"):
                posts.append(Post.from_dict(row["ct_posts"]))
        # Sort by score descending
        posts.sort(key=lambda p: p.score, reverse=True)
        return posts

    def get_top_posts_by_topic(self, topic_id: int, limit: int = 3) -> list[Post]:
        """Get top-scored posts for a topic (for compact TOC)."""
        result = self.db.execute(
            lambda: self.db.client.table("ct_post_topics")
            .select("post_id, ct_posts(*)")
            .eq("topic_id", topic_id)
            .execute()
        )
        posts = []
        for row in result.data:
            if row.get("ct_posts"):
                posts.append(Post.from_dict(row["ct_posts"]))
        posts.sort(key=lambda p: p.score, reverse=True)
        return posts[:limit]

    def search_posts(self, channel_id: int, query: str, limit: int = 20) -> list[Post]:
        """Search posts by keyword in text and description."""
        pattern = f"%{query}%"
        result = self.db.execute(
            lambda: self.db.client.table("ct_posts")
            .select("*")
            .eq("channel_id", channel_id)
            .or_(f"text.ilike.{pattern},description.ilike.{pattern}")
            .order("score", desc=True)
            .limit(limit)
            .execute()
        )
        return [Post.from_dict(row) for row in result.data]

    def get_channel_post_count(self, channel_id: int) -> int:
        result = self.db.execute(
            lambda: self.db.client.table("ct_posts")
            .select("id", count="exact")
            .eq("channel_id", channel_id)
            .execute()
        )
        return result.count or 0

    def recalculate_scores(self, channel_id: int):
        """Recalculate scores for all posts in a channel."""
        result = self.db.execute(
            lambda: self.db.client.table("ct_posts")
            .select("id, views, forwards, reactions_count, post_date, usefulness_score")
            .eq("channel_id", channel_id)
            .execute()
        )
        if not result.data:
            return

        # Find max engagement for normalization
        max_eng = 1.0
        now = datetime.now(timezone.utc)
        for row in result.data:
            eng = math.log(max(row["views"] or 0, 1)) * 0.5 + (row["forwards"] or 0) * 2 + (row["reactions_count"] or 0)
            if eng > max_eng:
                max_eng = eng

        for row in result.data:
            eng = math.log(max(row["views"] or 0, 1)) * 0.5 + (row["forwards"] or 0) * 2 + (row["reactions_count"] or 0)
            engagement_norm = min(1.0, eng / max_eng)

            post_date = row["post_date"]
            if isinstance(post_date, str):
                post_date = datetime.fromisoformat(post_date.replace("Z", "+00:00"))
            days_old = (now - post_date).total_seconds() / 86400
            freshness = math.exp(-days_old / FRESHNESS_HALF_LIFE_DAYS)

            usefulness = row.get("usefulness_score") or 0.5

            score = engagement_norm * 0.4 + freshness * 0.3 + usefulness * 0.3

            post_id = row["id"]
            self.db.execute(
                lambda pid=post_id, s=score: self.db.client.table("ct_posts")
                .update({"score": round(s, 4)})
                .eq("id", pid)
                .execute()
            )

    # --- Topics ---

    def get_or_create_topic(self, channel_id: int, name: str) -> Topic:
        slug = slugify(name)
        result = self.db.execute(
            lambda: self.db.client.table("ct_topics")
            .select("*")
            .eq("channel_id", channel_id)
            .eq("slug", slug)
            .maybe_single()
            .execute()
        )
        if result.data:
            return Topic.from_dict(result.data)

        result = self.db.execute(
            lambda: self.db.client.table("ct_topics")
            .insert({"channel_id": channel_id, "name": name, "slug": slug})
            .execute()
        )
        return Topic.from_dict(result.data[0])

    def get_topics(self, channel_id: int) -> list[Topic]:
        result = self.db.execute(
            lambda: self.db.client.table("ct_topics")
            .select("*")
            .eq("channel_id", channel_id)
            .order("post_count", desc=True)
            .execute()
        )
        return [Topic.from_dict(row) for row in result.data]

    def get_topic_by_slug(self, channel_id: int, slug: str) -> Optional[Topic]:
        result = self.db.execute(
            lambda: self.db.client.table("ct_topics")
            .select("*")
            .eq("channel_id", channel_id)
            .eq("slug", slug)
            .maybe_single()
            .execute()
        )
        return Topic.from_dict(result.data) if result.data else None

    def link_post_topic(self, post_id: int, topic_id: int):
        self.db.execute(
            lambda: self.db.client.table("ct_post_topics")
            .upsert(
                {"post_id": post_id, "topic_id": topic_id},
                on_conflict="post_id,topic_id",
            )
            .execute()
        )

    def update_topic_counts(self, channel_id: int):
        """Recalculate post_count for all topics in a channel."""
        topics = self.get_topics(channel_id)
        for topic in topics:
            result = self.db.execute(
                lambda tid=topic.id: self.db.client.table("ct_post_topics")
                .select("post_id", count="exact")
                .eq("topic_id", tid)
                .execute()
            )
            count = result.count or 0
            if count != topic.post_count:
                self.db.execute(
                    lambda tid=topic.id, c=count: self.db.client.table("ct_topics")
                    .update({"post_count": c})
                    .eq("id", tid)
                    .execute()
                )
            # Delete topics with 0 posts
            if count == 0:
                self.db.execute(
                    lambda tid=topic.id: self.db.client.table("ct_topics")
                    .delete()
                    .eq("id", tid)
                    .execute()
                )

    def update_topic_summary(self, topic_id: int, summary: str):
        self.db.execute(
            lambda: self.db.client.table("ct_topics")
            .update({"summary": summary})
            .eq("id", topic_id)
            .execute()
        )

    def get_topic_post_count(self, topic_id: int) -> int:
        result = self.db.execute(
            lambda: self.db.client.table("ct_post_topics")
            .select("post_id", count="exact")
            .eq("topic_id", topic_id)
            .execute()
        )
        return result.count or 0

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
