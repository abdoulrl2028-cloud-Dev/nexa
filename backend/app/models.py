"""Modelos ORM do NEXA (SQLAlchemy 2.0).

PostgreSQL em produção / SQLite em desenvolvimento. Tudo é mapeado com índices
para consultas que crescem: FKs, slugs anunciados, cursor de feed e mensagens.
"""
from __future__ import annotations

import datetime as dt
import re
import secrets
import unicodedata
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base


def utcnow() -> dt.datetime:
    """Datetime UTC naive (armazenamento consistente entre SQLite e PG)."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def slugify(text: str, limit: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = ("".join(c for c in text if not unicodedata.combining(c))).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:limit].rstrip("-") or "item"


def unique_slug(desired: str, taken: set[str]) -> str:
    slug = slugify(desired)
    base, n = slug, 1
    while slug in taken:
        n += 1
        slug = f"{base}-{n}"
    return slug


def _json_default() -> dict:
    return {}


# ------------------------------------------------------------------ usuários
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(64), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    avatar_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cover_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    posts: Mapped[list["Post"]] = relationship(back_populates="author")

    @property
    def url(self) -> str:
        return f"{get_settings().site_url}/profile/{self.username}"

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "bio": self.bio,
            "avatar": self.avatar_key,
            "cover": self.cover_key,
            "is_private": self.is_private,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("follower_id", "following_id", name="uq_follow"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    follower_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    following_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


# ------------------------------------------------------------------ mídia
class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="file")  # image|video|audio|file
    mime: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)
    key: Mapped[str] = mapped_column(String(512), unique=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    def to_dict(self, base_url: str) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "kind": self.kind,
            "mime": self.mime,
            "size": self.size,
            "width": self.width,
            "height": self.height,
            "url": f"{base_url}/media/{self.key}",
        }


# ------------------------------------------------------------------ posts
class PostVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    FRIENDS = "friends"  # seguidores mútuos


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True, index=True)
    circle_id: Mapped[int | None] = mapped_column(ForeignKey("circles.id"), nullable=True, index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(160), default="")
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    visibility: Mapped[str] = mapped_column(String(16), default=PostVisibility.PUBLIC.value)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="published")  # published|removed|blocked
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    author: Mapped["User"] = relationship(back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post", order_by="Comment.created_at")

    @property
    def url(self) -> str:
        return f"{get_settings().site_url}/post/{self.slug}"

    def to_dict(self, base_url: str) -> dict:
        return {
            "id": self.id,
            "author": _author_dict(self, base_url),
            "title": self.title,
            "slug": self.slug,
            "content": self.content,
            "visibility": self.visibility,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "url": self.url,
        }


class PostMedia(Base):
    __tablename__ = "post_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)

    author: Mapped["User"] = relationship()
    post: Mapped["Post"] = relationship(back_populates="comments")


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_like_post_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


Index("ix_posts_feed", Post.author_id, Post.created_at.desc())


# ------------------------------------------------------------------ grupos
class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(130), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    image_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), default="public")  # public|private
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    member_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def url(self) -> str:
        return f"{get_settings().site_url}/groups/{self.slug}"


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")  # owner|admin|member
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


# ------------------------------------------------------------------ círculos
class Circle(Base):
    __tablename__ = "circles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(130), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    image_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), default="public")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    member_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def url(self) -> str:
        return f"{get_settings().site_url}/circles/{self.slug}"


class CircleMember(Base):
    __tablename__ = "circle_members"
    __table_args__ = (UniqueConstraint("circle_id", "user_id", name="uq_circle_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    circle_id: Mapped[int] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


# ------------------------------------------------------------------ eventos
class EventStatus(str, Enum):
    UPCOMING = "upcoming"
    LIVE = "live"
    ENDED = "ended"
    CANCELLED = "cancelled"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(170), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    begins_at: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), default="public")
    image_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    participant_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default=EventStatus.UPCOMING.value)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def url(self) -> str:
        return f"{get_settings().site_url}/events/{self.slug}"


class EventParticipant(Base):
    __tablename__ = "event_participants"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_participant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="going")  # going|maybe|interested
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


# ------------------------------------------------------------------ stories
class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media.id"), nullable=True)
    caption: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)


class StoryView(Base):
    __tablename__ = "story_views"
    __table_args__ = (UniqueConstraint("story_id", "viewer_id", name="uq_story_view"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id", ondelete="CASCADE"), index=True)
    viewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    viewed_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


# ------------------------------------------------------------------ mensagens
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    __table_args__ = (UniqueConstraint("conversation_id", "user_id", name="uq_conv_participant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    last_read_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conv_created", "conversation_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


# ------------------------------------------------------------------ notificações
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # destinatário
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    type_: Mapped[str] = mapped_column(String(40))  # follow|like|comment|message|group|event|system
    entity_type: Mapped[str] = mapped_column(String(40), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)


Index("ix_notifications_user_read", Notification.user_id, Notification.read_at)


# ------------------------------------------------------------------ denúncias
class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(24))  # post|user|group|circle|event
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    reason: Mapped[str] = mapped_column(String(400), default="")
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|resolved|removed
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)


# Utilitários p/ serialização (evitar import circular)
def _author_dict(post: "Post", base_url: str) -> dict:
    a = post.author
    return {
        "id": a.id,
        "username": a.username,
        "display_name": a.display_name or a.username,
        "avatar": a.avatar_key,
        "url": f"{base_url}/profile/{a.username}",
    }


__all__ = [
    "User", "Follow", "Media", "Post", "PostMedia", "Comment", "Like",
    "Group", "GroupMember", "Circle", "CircleMember",
    "Event", "EventParticipant", "Story", "StoryView",
    "Conversation", "ConversationParticipant", "Message",
    "Notification", "Report", "PostVisibility", "slugify", "unique_slug", "utcnow",
]