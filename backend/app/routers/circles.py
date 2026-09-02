"""Círculos (comunidades): criação, inscrição, posts dentro do círculo."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import can_view_circle, get_current_user, get_optional_user, is_circle_member
from app.models import Circle, CircleMember, Post, User, unique_slug
from app.notifier import notify
from app.routers.groups import _new_post_payload
from app.routers.posts import _serialize
from app.routers.users import get_media_base
from app.schemas import CircleIn, PostIn
from app.storage import media_url

router = APIRouter(prefix="/api/circles", tags=["circles"])


def _c_dict(c: Circle) -> dict:
    return {
        "slug": c.slug, "name": c.name, "description": c.description,
        "image": media_url(c.image_key), "visibility": c.visibility,
        "member_count": c.member_count, "is_archived": c.is_archived,
        "owner_id": c.owner_id,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "url": c.url,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_circle(payload: CircleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    taken = set(db.execute(select(Circle.slug)).scalars())
    c = Circle(
        owner_id=user.id, name=payload.name.strip(), slug=unique_slug(payload.name, taken),
        description=payload.description, visibility=payload.visibility, image_key=payload.image_key,
    )
    db.add(c)
    db.flush()
    db.add(CircleMember(circle_id=c.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(c)
    return _c_dict(c)


@router.get("")
def list_circles(user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    circles = db.execute(
        select(Circle).where(Circle.is_archived.is_(False)).order_by(Circle.member_count.desc()).limit(100)
    ).scalars().all()
    visible = [c for c in circles if can_view_circle(c, user, db)]
    return [_c_dict(c) for c in visible]


@router.get("/{slug}")
def get_circle(slug: str, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    c = db.execute(select(Circle).where(Circle.slug == slug)).scalar_one_or_none()
    if c is None or not can_view_circle(c, user, db):
        raise HTTPException(status_code=404, detail="Círculo não encontrado")
    data = _c_dict(c)
    data["is_member"] = bool(user and is_circle_member(db, c.id, user.id))
    return data


@router.get("/{slug}/posts")
def circle_posts(slug: str, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    c = db.execute(select(Circle).where(Circle.slug == slug)).scalar_one_or_none()
    if c is None or not can_view_circle(c, user, db):
        raise HTTPException(status_code=404, detail="Círculo não encontrado")
    posts = db.execute(
        select(Post).where(Post.circle_id == c.id, Post.status == "published").order_by(Post.created_at.desc()).limit(100)
    ).scalars().all()
    return {"items": _serialize(db, list(posts), user.id if user else None)}


@router.post("/{slug}/posts", status_code=status.HTTP_201_CREATED)
def create_circle_post(slug: str, payload: PostIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.execute(select(Circle).where(Circle.slug == slug)).scalar_one_or_none()
    if c is None or not can_view_circle(c, user, db):
        raise HTTPException(status_code=404, detail="Círculo não encontrado")
    if not is_circle_member(db, c.id, user.id):
        raise HTTPException(status_code=403, detail="Entre no círculo para postar")
    post = _new_post_payload(db, user, payload, circle_id=c.id)
    db.add(post)
    db.commit()
    db.refresh(post)
    return _serialize(db, [post], user.id)[0]


@router.post("/{slug}/join")
def join_circle(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.execute(select(Circle).where(Circle.slug == slug)).scalar_one_or_none()
    if c is None or c.is_archived:
        raise HTTPException(status_code=404, detail="Círculo não encontrado")
    if not is_circle_member(db, c.id, user.id):
        db.add(CircleMember(circle_id=c.id, user_id=user.id, role="member"))
        c.member_count += 1
        db.flush()
        notify(db, c.owner_id, user.id, "group", f"{user.display_name or user.username} entrou no círculo {c.name}",
               entity_type="circle", entity_id=c.slug)
        db.commit()
    return {"joined": True}


@router.delete("/{slug}/leave")
def leave_circle(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.execute(select(Circle).where(Circle.slug == slug)).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Círculo não encontrado")
    if c.owner_id == user.id:
        raise HTTPException(status_code=400, detail="Dono não pode sair")
    row = db.execute(select(CircleMember.id).where(CircleMember.circle_id == c.id, CircleMember.user_id == user.id)).scalar_one_or_none()
    if row:
        db.execute(CircleMember.__table__.delete().where(CircleMember.id == row))
        c.member_count = max(0, c.member_count - 1)
        db.commit()
    return {"left": True}


@router.patch("/{slug}")
def update_circle(slug: str, payload: CircleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.execute(select(Circle).where(Circle.slug == slug)).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Círculo não encontrado")
    if c.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Somente o dono edita")
    c.name = payload.name.strip()
    c.description = payload.description
    c.visibility = payload.visibility
    if payload.image_key:
        c.image_key = payload.image_key
    db.commit()
    db.refresh(c)
    return _c_dict(c)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_circle(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.execute(select(Circle).where(Circle.slug == slug)).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Círculo não encontrado")
    if c.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Somente o dono remove")
    c.is_archived = True
    db.commit()


__all__ = ["router"]