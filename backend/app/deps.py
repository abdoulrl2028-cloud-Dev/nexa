"""Dependências FastAPI: autenticação, autorização e visibilidade."""
from __future__ import annotations

from fastapi import Cookie, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Circle, CircleMember, Event, Follow, Group, GroupMember, Post, PostVisibility, User
from app.security import decode_token

SESSION_COOKIE = "nexa_session"

_GroupMember = GroupMember
_CircleMember = CircleMember


def _user_from_token(token: str | None, db: Session) -> User | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
    except ValueError:
        return None
    if payload.get("type") != "access":
        return None
    uid = payload.get("sub")
    if uid is None:
        return None
    return db.get(User, int(uid))


def _extract_token(authorization: str | None, cookie: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return cookie


def get_current_user(
    authorization: str | None = Header(default=None),
    nexa_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    user = _user_from_token(_extract_token(authorization, nexa_session), db)
    if user is None:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Conta desativada")
    return user


def get_optional_user(
    authorization: str | None = Header(default=None),
    nexa_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User | None:
    return _user_from_token(_extract_token(authorization, nexa_session), db)


# ------------------------------------------------------------- visibilidade
def following_ids(db: Session, user_id: int) -> set[int]:
    rows = db.execute(select(Follow.following_id).where(Follow.follower_id == user_id)).all()
    return {r[0] for r in rows}


def are_mutual(db: Session, a: int, b: int) -> bool:
    a_follows_b = db.execute(
        select(Follow.id).where(Follow.follower_id == a, Follow.following_id == b)
    ).first()
    b_follows_a = db.execute(
        select(Follow.id).where(Follow.follower_id == b, Follow.following_id == a)
    ).first()
    return bool(a_follows_b and b_follows_a)


def can_view_post(post: Post, viewer: User | None, db: Session, following: set[int] | None = None) -> bool:
    if post.status in ("removed", "blocked"):
        return False
    if post.visibility == PostVisibility.PUBLIC.value:
        return True
    if viewer is None:
        return False
    if viewer.id == post.author_id or getattr(viewer, "is_admin", False):
        return True
    if post.visibility == PostVisibility.PRIVATE.value:
        return False
    if post.visibility == PostVisibility.FRIENDS.value:
        if following is None:
            following = following_ids(db, viewer.id)
        return post.author_id in following and are_mutual(db, viewer.id, post.author_id)
    return False


def can_view_profile(profile_user: User, viewer: User | None, db: Session) -> bool:
    if not profile_user.is_private:
        return True
    if viewer is None:
        return False
    if viewer.id == profile_user.id or getattr(viewer, "is_admin", False):
        return True
    return are_mutual(db, viewer.id, profile_user.id)


def is_group_member(db: Session, group_id: int, user_id: int) -> bool:
    return bool(
        db.execute(select(_GroupMember.id).where(_GroupMember.group_id == group_id, _GroupMember.user_id == user_id)).first()
    )


def is_circle_member(db: Session, circle_id: int, user_id: int) -> bool:
    return bool(
        db.execute(select(_CircleMember.id).where(_CircleMember.circle_id == circle_id, _CircleMember.user_id == user_id)).first()
    )


def can_view_group(group: Group, viewer: User | None, db: Session) -> bool:
    if group.is_archived:
        return False
    if group.visibility == "public":
        return True
    if viewer is None:
        return False
    return is_group_member(db, group.id, viewer.id)


def can_view_circle(circle: Circle, viewer: User | None, db: Session) -> bool:
    if circle.is_archived:
        return False
    if circle.visibility == "public":
        return True
    if viewer is None:
        return False
    return is_circle_member(db, circle.id, viewer.id)


def can_view_event(event: Event, viewer: User | None, db: Session) -> bool:
    if event.status == "cancelled":
        return False
    if event.visibility == "public":
        return True
    if viewer is None:
        return False
    return event.owner_id == viewer.id


def pagination(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> tuple[int, str | None]:
    return limit, cursor


__all__ = [
    "get_current_user",
    "get_optional_user",
    "SESSION_COOKIE",
    "following_ids",
    "are_mutual",
    "can_view_post",
    "can_view_profile",
    "can_view_group",
    "can_view_circle",
    "can_view_event",
    "is_group_member",
    "is_circle_member",
    "pagination",
]