"""Eventos: criação, listagem, RSVP, encerramento."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import can_view_event, get_current_user, get_optional_user
from app.models import Event, EventParticipant, EventStatus, Post, User, unique_slug, utcnow
from app.notifier import notify
from app.routers.groups import _new_post_payload
from app.routers.posts import _serialize
from app.routers.users import get_media_base
from app.schemas import EventIn, PostIn
from app.storage import media_url

router = APIRouter(prefix="/api/events", tags=["events"])


def _e_dict(db: Session, e: Event, me: int | None) -> dict:
    data = {
        "slug": e.slug, "name": e.name, "description": e.description, "location": e.location,
        "image": media_url(e.image_key), "visibility": e.visibility, "status": e.status,
        "participant_count": e.participant_count,
        "begins_at": e.begins_at.isoformat() if e.begins_at else None,
        "ends_at": e.ends_at.isoformat() if e.ends_at else None,
        "owner_id": e.owner_id,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "url": e.url, "is_online": _is_running(e),
    }
    data["my_rsvp"] = None
    if me:
        row = db.execute(
            select(EventParticipant.status).where(EventParticipant.event_id == e.id, EventParticipant.user_id == me)
        ).first()
        data["my_rsvp"] = row[0] if row else None
    return data


def _is_running(e: Event) -> bool:
    now = utcnow()
    return bool(e.begins_at and e.begins_at <= now and (e.ends_at is None or e.ends_at > now))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_event(payload: EventIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    taken = set(db.execute(select(Event.slug)).scalars())
    e = Event(
        owner_id=user.id, name=payload.name.strip(), slug=unique_slug(payload.name, taken),
        description=payload.description, location=payload.location,
        begins_at=payload.begins_at.replace(tzinfo=None), ends_at=payload.ends_at.replace(tzinfo=None) if payload.ends_at else None,
        visibility=payload.visibility, image_key=payload.image_key,
        status=EventStatus.UPCOMING.value,
    )
    if e.ends_at and e.ends_at <= e.begins_at:
        raise HTTPException(status_code=400, detail="ends_at deve ser após begins_at")
    db.add(e)
    db.flush()
    db.add(EventParticipant(event_id=e.id, user_id=user.id, status="going"))
    e.participant_count = 1
    db.commit()
    db.refresh(e)
    return _e_dict(db, e, user.id)


@router.get("")
def list_events(user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    events = db.execute(
        select(Event).where(Event.status != EventStatus.CANCELLED.value).order_by(Event.begins_at.asc()).limit(100)
    ).scalars().all()
    visible = [e for e in events if can_view_event(e, user, db)]
    return [_e_dict(db, e, user.id if user else None) for e in visible]


@router.get("/{slug}")
def get_event(slug: str, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    e = db.execute(select(Event).where(Event.slug == slug)).scalar_one_or_none()
    if e is None or not can_view_event(e, user, db):
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    return _e_dict(db, e, user.id if user else None)


@router.get("/{slug}/participants")
def event_participants(slug: str, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    e = db.execute(select(Event).where(Event.slug == slug)).scalar_one_or_none()
    if e is None or not can_view_event(e, user, db):
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    rows = db.execute(
        select(EventParticipant, User).join(User, User.id == EventParticipant.user_id)
        .where(EventParticipant.event_id == e.id)
    ).all()
    return {"items": [
        {"username": u.username, "display_name": u.display_name or u.username,
         "avatar": media_url(u.avatar_key), "status": ep.status}
        for ep, u in rows
    ]}


@router.get("/{slug}/posts")
def event_posts(slug: str, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    e = db.execute(select(Event).where(Event.slug == slug)).scalar_one_or_none()
    if e is None or not can_view_event(e, user, db):
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    posts = db.execute(
        select(Post).where(Post.event_id == e.id, Post.status == "published").order_by(Post.created_at.desc()).limit(100)
    ).scalars().all()
    return {"items": _serialize(db, list(posts), user.id if user else None)}


@router.post("/{slug}/posts", status_code=status.HTTP_201_CREATED)
def create_event_post(slug: str, payload: PostIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = db.execute(select(Event).where(Event.slug == slug)).scalar_one_or_none()
    if e is None or not can_view_event(e, user, db):
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    participant = db.execute(
        select(EventParticipant.id).where(EventParticipant.event_id == e.id, EventParticipant.user_id == user.id)
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="Confirme presença para postar")
    post = _new_post_payload(db, user, payload, event_id=e.id)
    db.add(post)
    db.commit()
    db.refresh(post)
    return _serialize(db, [post], user.id)[0]


@router.post("/{slug}/rsvp")
def rsvp_event(slug: str, status_value: str = "going", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = db.execute(select(Event).where(Event.slug == slug)).scalar_one_or_none()
    if e is None or not can_view_event(e, user, db):
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    if status_value not in ("going", "maybe", "interested"):
        raise HTTPException(status_code=400, detail="status inválido")
    row = db.execute(select(EventParticipant.id).where(EventParticipant.event_id == e.id, EventParticipant.user_id == user.id)).scalar_one_or_none()
    if row:
        db.execute(EventParticipant.__table__.update().where(EventParticipant.id == row).values(status=status_value))
    else:
        db.add(EventParticipant(event_id=e.id, user_id=user.id, status=status_value))
        e.participant_count += 1
        db.flush()
        notify(db, e.owner_id, user.id, "event", f"{user.display_name or user.username} confirmou presença em {e.name}",
               entity_type="event", entity_id=e.slug)
    db.commit()
    return {"status": status_value, "participant_count": e.participant_count}


@router.delete("/{slug}/rsvp")
def cancel_rsvp(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = db.execute(select(Event).where(Event.slug == slug)).scalar_one_or_none()
    if e is None:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    row = db.execute(select(EventParticipant.id).where(EventParticipant.event_id == e.id, EventParticipant.user_id == user.id)).scalar_one_or_none()
    if row:
        db.execute(EventParticipant.__table__.delete().where(EventParticipant.id == row))
        e.participant_count = max(0, e.participant_count - 1)
        db.commit()
    return {"status": None}


@router.patch("/{slug}")
def update_event(slug: str, payload: EventIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = db.execute(select(Event).where(Event.slug == slug)).scalar_one_or_none()
    if e is None:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    if e.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Somente o dono edita")
    e.name = payload.name.strip()
    e.description = payload.description
    e.location = payload.location
    e.begins_at = payload.begins_at.replace(tzinfo=None)
    e.ends_at = payload.ends_at.replace(tzinfo=None) if payload.ends_at else None
    e.visibility = payload.visibility
    if payload.image_key:
        e.image_key = payload.image_key
    db.commit()
    db.refresh(e)
    return _e_dict(db, e, user.id)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = db.execute(select(Event).where(Event.slug == slug)).scalar_one_or_none()
    if e is None:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    if e.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Somente o dono remove")
    e.status = EventStatus.CANCELLED.value
    db.commit()


__all__ = ["router"]