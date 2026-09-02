"""Busca global: usuários, posts, grupos, círculos e eventos públicos."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_optional_user
from app.models import Circle, Event, Group, Post, User
from app.routers.posts import _serialize
from app.routers.users import get_media_base
from app.storage import media_url

router = APIRouter(prefix="/api/search", tags=["search"])

MAX = 25


def _like(term: str, column):
    return column.ilike(f"%{term}%")


@router.get("")
def search(
    q: str = "",
    scope: str = "all",  # all|users|posts|groups|circles|events
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    term = q.strip()
    if not term:
        return {"users": [], "posts": [], "groups": [], "circles": [], "events": []}
    result: dict = {}

    if scope in ("all", "users"):
        users = db.execute(
            select(User).where(
                or_(_like(term, User.username), _like(term, User.display_name), _like(term, User.bio)),
                User.is_active.is_(True),
            ).limit(MAX)
        ).scalars().all()
        result["users"] = [
            {"username": u.username, "display_name": u.display_name, "avatar": media_url(u.avatar_key),
             "is_private": u.is_private, "url": u.url}
            for u in users if not u.is_private
        ]
    if scope in ("all", "posts"):
        posts = db.execute(
            select(Post).where(
                or_(_like(term, Post.title), _like(term, Post.content)),
                Post.visibility == "public", Post.status == "published",
            ).order_by(Post.created_at.desc()).limit(MAX)
        ).scalars().all()
        result["posts"] = _serialize(db, list(posts), user.id if user else None)
    if scope in ("all", "groups"):
        groups = db.execute(
            select(Group).where(
                or_(_like(term, Group.name), _like(term, Group.description)),
                Group.visibility == "public", Group.is_archived.is_(False),
            ).limit(MAX)
        ).scalars().all()
        result["groups"] = [_g(g) for g in groups]
    if scope in ("all", "circles"):
        circles = db.execute(
            select(Circle).where(
                or_(_like(term, Circle.name), _like(term, Circle.description)),
                Circle.visibility == "public", Circle.is_archived.is_(False),
            ).limit(MAX)
        ).scalars().all()
        result["circles"] = [_c(c) for c in circles]
    if scope in ("all", "events"):
        events = db.execute(
            select(Event).where(
                or_(_like(term, Event.name), _like(term, Event.description)),
                Event.visibility == "public", Event.status != "cancelled",
            ).order_by(Event.begins_at.desc()).limit(MAX)
        ).scalars().all()
        result["events"] = [_e(e) for e in events]

    return result


def _g(g: Group) -> dict:
    return {"slug": g.slug, "name": g.name, "description": g.description,
            "image": media_url(g.image_key), "member_count": g.member_count, "url": g.url}


def _c(c: Circle) -> dict:
    return {"slug": c.slug, "name": c.name, "description": c.description,
            "image": media_url(c.image_key), "member_count": c.member_count, "url": c.url}


def _e(e: Event) -> dict:
    return {"slug": e.slug, "name": e.name, "location": e.location, "status": e.status,
            "begins_at": e.begins_at.isoformat() if e.begins_at else None, "url": e.url}


__all__ = ["router"]