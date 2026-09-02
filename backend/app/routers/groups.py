"""Grupos: criação, inscrição, posts dentro do grupo."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import can_view_group, get_current_user, get_optional_user, is_group_member
from app.models import Group, GroupMember, Media, Post, PostMedia, PostVisibility, User, unique_slug
from app.notifier import notify
from app.routers.posts import _serialize
from app.routers.users import get_media_base
from app.schemas import GroupIn, PostIn
from app.storage import media_url


def _new_post_payload(db: Session, user: User, payload: PostIn, group_id: int | None = None,
                      circle_id: int | None = None, event_id: int | None = None) -> Post:
    from app.models import unique_slug as usl

    taken = set(db.execute(select(Post.slug)).scalars())
    post = Post(
        author_id=user.id,
        group_id=group_id, circle_id=circle_id, event_id=event_id,
        title=payload.title,
        slug=usl(payload.title or payload.content[:60], taken),
        content=payload.content,
        visibility=payload.visibility,
    )
    if payload.media_keys:
        owned = set(db.execute(select(Media.key).where(Media.owner_id == user.id)).scalars())
        for i, key in enumerate(payload.media_keys):
            if key not in owned:
                raise HTTPException(status_code=400, detail=f"Mídia {key} não pertence ao usuário")
            media = db.execute(select(Media).where(Media.key == key)).scalar_one()
            db.add(PostMedia(post_id=post.id, media_id=media.id, position=i))
    return post

router = APIRouter(prefix="/api/groups", tags=["groups"])


def _g_dict(g: Group) -> dict:
    return {
        "slug": g.slug, "name": g.name, "description": g.description,
        "image": media_url(g.image_key), "visibility": g.visibility,
        "member_count": g.member_count, "is_archived": g.is_archived,
        "owner_id": g.owner_id,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "url": g.url,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_group(payload: GroupIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    taken = set(db.execute(select(Group.slug)).scalars())
    g = Group(
        owner_id=user.id, name=payload.name.strip(), slug=unique_slug(payload.name, taken),
        description=payload.description, visibility=payload.visibility, image_key=payload.image_key,
    )
    db.add(g)
    db.flush()
    db.add(GroupMember(group_id=g.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(g)
    return _g_dict(g)


@router.get("")
def list_groups(user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    groups = db.execute(
        select(Group).where(Group.is_archived.is_(False)).order_by(Group.member_count.desc()).limit(100)
    ).scalars().all()
    visible = [g for g in groups if can_view_group(g, user, db)]
    return [_g_dict(g) for g in visible]


@router.get("/{slug}")
def get_group(slug: str, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    g = db.execute(select(Group).where(Group.slug == slug)).scalar_one_or_none()
    if g is None or not can_view_group(g, user, db):
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    data = _g_dict(g)
    data["is_member"] = bool(user and is_group_member(db, g.id, user.id))
    return data


@router.get("/{slug}/posts")
def group_posts(slug: str, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    g = db.execute(select(Group).where(Group.slug == slug)).scalar_one_or_none()
    if g is None or not can_view_group(g, user, db):
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    posts = db.execute(
        select(Post).where(Post.group_id == g.id, Post.status == "published").order_by(Post.created_at.desc()).limit(100)
    ).scalars().all()
    return {"items": _serialize(db, list(posts), user.id if user else None)}


@router.get("/{slug}/members")
def group_members(slug: str, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    g = db.execute(select(Group).where(Group.slug == slug)).scalar_one_or_none()
    if g is None or not can_view_group(g, user, db):
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    rows = db.execute(
        select(GroupMember, User).join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == g.id).order_by(GroupMember.role.desc(), User.username)
    ).all()
    return {"items": [
        {"username": u.username, "display_name": u.display_name or u.username,
         "avatar": media_url(u.avatar_key), "role": gm.role}
        for gm, u in rows
    ]}


@router.post("/{slug}/posts", status_code=status.HTTP_201_CREATED)
def create_group_post(slug: str, payload: PostIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.execute(select(Group).where(Group.slug == slug)).scalar_one_or_none()
    if g is None or not can_view_group(g, user, db):
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    if not is_group_member(db, g.id, user.id):
        raise HTTPException(status_code=403, detail="Entre no grupo para postar")
    post = _new_post_payload(db, user, payload, group_id=g.id)
    db.add(post)
    db.commit()
    db.refresh(post)
    return _serialize(db, [post], user.id)[0]


@router.post("/{slug}/join")
def join_group(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.execute(select(Group).where(Group.slug == slug)).scalar_one_or_none()
    if g is None or g.is_archived:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    if not is_group_member(db, g.id, user.id):
        db.add(GroupMember(group_id=g.id, user_id=user.id, role="member"))
        g.member_count += 1
        db.flush()
        notify(db, g.owner_id, user.id, "group", f"{user.display_name or user.username} entrou no grupo {g.name}",
               entity_type="group", entity_id=g.slug)
        db.commit()
    return {"joined": True}


@router.delete("/{slug}/leave")
def leave_group(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.execute(select(Group).where(Group.slug == slug)).scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    if g.owner_id == user.id:
        raise HTTPException(status_code=400, detail="Dono não pode sair; cancele ou transfira o grupo")
    row = db.execute(select(GroupMember.id).where(GroupMember.group_id == g.id, GroupMember.user_id == user.id)).scalar_one_or_none()
    if row:
        db.execute(GroupMember.__table__.delete().where(GroupMember.id == row))
        g.member_count = max(0, g.member_count - 1)
        db.commit()
    return {"left": True}


@router.patch("/{slug}")
def update_group(slug: str, payload: GroupIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.execute(select(Group).where(Group.slug == slug)).scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    if g.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Somente o dono edita")
    g.name = payload.name.strip()
    g.description = payload.description
    g.visibility = payload.visibility
    if payload.image_key:
        g.image_key = payload.image_key
    db.commit()
    db.refresh(g)
    return _g_dict(g)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.execute(select(Group).where(Group.slug == slug)).scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    if g.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Somente o dono remove")
    g.is_archived = True
    db.commit()


__all__ = ["router", "_g_dict"]