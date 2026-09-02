"""Usuários, perfis públicos e seguidores."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import can_view_profile, get_current_user, get_optional_user
from app.models import Follow, Post, User, utcnow
from app.notifier import notify
from app.storage import media_url

router = APIRouter(prefix="/api", tags=["users"])


def _profile_dict(user: User, me: int | None, db: Session, include_private: bool) -> dict:
    followers = db.execute(select(func.count(Follow.id)).where(Follow.following_id == user.id)).scalar() or 0
    following = db.execute(select(func.count(Follow.id)).where(Follow.follower_id == user.id)).scalar() or 0
    me_follows = False
    is_blocked = False  # pré-preparado p/ regra de bloqueio
    if me and me != user.id:
        me_follows = bool(
            db.execute(select(Follow.id).where(Follow.follower_id == me, Follow.following_id == user.id)).first()
        )
    data = {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "bio": user.bio,
        "avatar": media_url(user.avatar_key),
        "cover": media_url(user.cover_key),
        "is_private": user.is_private,
        "is_verified": user.is_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "counts": {"followers": followers, "following": following},
        "viewer_follows": me_follows,
        "is_viewer": (me == user.id),
        "is_blocked": is_blocked,
    }
    if user.is_private and not include_private:
        data["bio"] = ""
        data.pop("counts", None)
    return data


@router.get("/users/{username}")
def get_profile(username: str, me: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.username == username.strip().lower())).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if not can_view_profile(user, me, db):
        raise HTTPException(status_code=403, detail="Perfil privado")
    return _profile_dict(user, me.id if me else None, db, include_private=True)


@router.get("/users/{username}/posts")
def get_user_posts(username: str, me: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.username == username.strip().lower())).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if not can_view_profile(user, me, db):
        raise HTTPException(status_code=403, detail="Perfil privado")
    posts = db.execute(
        select(Post)
        .where(Post.author_id == user.id, or_(Post.visibility == "public", Post.visibility == "friends"))
        .order_by(Post.created_at.desc())
        .limit(50)
    ).scalars().all()
    return [p.to_dict(get_media_base(db)) for p in posts]


def get_media_base(db: Session) -> str:
    from app.config import get_settings

    return get_settings().media_cdn_base or get_settings().site_url


@router.get("/users/{username}/followers")
def followers(username: str, me: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    user = require_visible(db, username, me)
    ids = db.execute(select(Follow.follower_id).where(Follow.following_id == user.id)).scalars().all()
    return [_mini(u) for u in db.execute(select(User).where(User.id.in_(ids))).scalars()]


@router.get("/users/{username}/following")
def following(username: str, me: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    user = require_visible(db, username, me)
    ids = db.execute(select(Follow.following_id).where(Follow.follower_id == user.id)).scalars().all()
    return [_mini(u) for u in db.execute(select(User).where(User.id.in_(ids))).scalars()]


def require_visible(db: Session, username: str, me: User | None) -> User:
    user = db.execute(select(User).where(User.username == username.strip().lower())).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if not can_view_profile(user, me, db):
        raise HTTPException(status_code=403, detail="Perfil privado")
    return user


def _mini(user: User) -> dict:
    return {
        "username": user.username,
        "display_name": user.display_name or user.username,
        "avatar": media_url(user.avatar_key),
        "is_verified": user.is_verified,
    }


@router.post("/users/{username}/follow")
def follow_user(
    username: str,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = require_visible(db, username, me)
    if me.id == target.id:
        raise HTTPException(status_code=400, detail="Você não pode seguir a si mesmo")
    exists = bool(db.execute(select(Follow.id).where(Follow.follower_id == me.id, Follow.following_id == target.id)).first())
    if not exists:
        db.add(Follow(follower_id=me.id, following_id=target.id))
        db.flush()
        notify(
            db, target.id, me.id, "follow",
            f"{me.display_name or me.username} começou a seguir você",
            entity_type="user", entity_id=str(me.id),
        )
        db.commit()
    return {"following": True}


@router.delete("/users/{username}/follow")
def unfollow_user(username: str, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = require_visible(db, username, me)
    row = db.execute(select(Follow.id).where(Follow.follower_id == me.id, Follow.following_id == target.id)).scalar_one_or_none()
    if row:
        db.execute(Follow.__table__.delete().where(Follow.id == row))
        db.commit()
    return {"following": False}


__all__ = ["router"]