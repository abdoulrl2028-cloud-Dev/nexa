"""Feed inicial (seguidos + seu) e Discover (público global)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, get_optional_user
from app.models import Follow, Post, User
from app.routers.posts import _serialize
from app.routers.users import get_media_base

router = APIRouter(prefix="/api/feed", tags=["feed"])


def _decode_cursor(cursor: str | None) -> str | None:
    if not cursor:
        return None
    try:
        return cursor  # timestamp ISO na base da consulta
    except Exception:  # noqa: BLE001
        return None


def _apply_cursor(query, cursor: str | None):
    from app.models import Post as P

    if cursor:
        query = query.where(P.created_at < cursor)
    return query.order_by(P.created_at.desc())


def _next_cursor(rows: list, limit: int) -> str | None:
    if len(rows) < limit:
        return None
    last = rows[-1]
    return last.created_at.isoformat() if last.created_at else None


@router.get("/home")
def home_feed(
    limit: int = 20,
    cursor: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    followed = set(db.execute(select(Follow.following_id).where(Follow.follower_id == user.id)).scalars())
    # seguidores mútuos (para posts com visibilidade "friends")
    my_followers = set(db.execute(select(Follow.follower_id).where(Follow.following_id == user.id)).scalars())
    mutual = {f for f in followed if f in my_followers}
    authors_public = followed | {user.id}
    authors_friends = mutual | {user.id}
    q = select(Post).where(
        or_(
            and_(Post.author_id.in_(authors_public), Post.visibility == "public"),
            and_(Post.author_id.in_(authors_friends), Post.visibility == "friends"),
        ),
        Post.status == "published",
    )
    q = _apply_cursor(q, _decode_cursor(cursor)).limit(limit)
    posts = db.execute(q).scalars().all()
    return {"items": _serialize(db, list(posts), user.id), "next_cursor": _next_cursor(list(posts), limit)}


@router.get("/discover")
def discover(
    limit: int = 20,
    cursor: str | None = None,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    q = select(Post).where(Post.visibility == "public", Post.status == "published")
    q = _apply_cursor(q, _decode_cursor(cursor)).limit(limit)
    posts = db.execute(q).scalars().all()
    return {"items": _serialize(db, list(posts), user.id if user else None), "next_cursor": _next_cursor(list(posts), limit)}


__all__ = ["router"]