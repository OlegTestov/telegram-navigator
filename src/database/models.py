"""Data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Channel:
    id: int
    username: str
    title: Optional[str]
    added_by: int
    is_active: bool = True
    pinned_message_id: Optional[int] = None
    pinned_chat_id: Optional[int] = None
    pinned_content_hash: Optional[str] = None
    last_fetched_message_id: int = 0
    last_run_at: Optional[datetime] = None
    total_posts_indexed: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "Channel":
        return cls(
            id=data["id"],
            username=data["username"],
            title=data.get("title"),
            added_by=data["added_by"],
            is_active=data.get("is_active", True),
            pinned_message_id=data.get("pinned_message_id"),
            pinned_chat_id=data.get("pinned_chat_id"),
            pinned_content_hash=data.get("pinned_content_hash"),
            last_fetched_message_id=data.get("last_fetched_message_id", 0),
            last_run_at=data.get("last_run_at"),
            total_posts_indexed=data.get("total_posts_indexed", 0),
        )


@dataclass
class Post:
    id: int
    channel_id: int
    message_id: int
    text: str
    description: Optional[str]
    post_date: datetime
    post_url: str
    has_media: bool = False
    views: int = 0
    forwards: int = 0
    reactions_count: int = 0
    usefulness_score: float = 0.5
    score: float = 0.0
    topics: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Post":
        return cls(
            id=data["id"],
            channel_id=data["channel_id"],
            message_id=data["message_id"],
            text=data["text"],
            description=data.get("description"),
            post_date=data["post_date"],
            post_url=data["post_url"],
            has_media=data.get("has_media", False),
            views=data.get("views", 0),
            forwards=data.get("forwards", 0),
            reactions_count=data.get("reactions_count", 0),
            usefulness_score=data.get("usefulness_score", 0.5),
            score=data.get("score", 0.0),
        )


@dataclass
class Topic:
    id: int
    channel_id: int
    name: str
    slug: str
    emoji: str = ""
    summary: Optional[str] = None
    post_count: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "Topic":
        return cls(
            id=data["id"],
            channel_id=data["channel_id"],
            name=data["name"],
            slug=data["slug"],
            emoji=data.get("emoji", ""),
            summary=data.get("summary"),
            post_count=data.get("post_count", 0),
        )
