"""Stories: conteúdo audiovisual com expiração, visível para seguidores."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, get_optional_user, following_ids
from app.models import Follow, Media, Story, StoryView, User, utcnow
from app.routers.users import get_media_base
from app.schemas import StoryIn
from app.storage import media_url

router = APIRouter(prefix="/api/stories", tags=["stories"])


def _s_dict(db: Session, s: Story) -> dict:
    base = get_media_base(db)
    media = db.get(Media, s.media_id) if s.media_id else None
    owner = db.get(User, s.owner_id)
    return {
        "id": s.id,
        "owner": {
            "username": owner.username, "display_name": owner.display_name or owner.username,
            "avatar": media_url(owner.avatar_key),
        },
        "caption": s.caption,
        "media": media.to_dict(base) if media else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        "view_count": 0,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_story(payload: StoryIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.media_key:
        media = db.execute(select(Media).where(Media.key == payload.media_key, Media.owner_id == user.id)).scalar_one_or_none()
        if media is None:
            raise HTTPException(status_code=400, detail="Mídia não pertence ao usuário")
        media_id = media.id
    else:
        media_id = None
        if not payload.caption:
            raise HTTPException(status_code=400, detail="Story precisa de mídia ou texto")
    s = Story(
        owner_id=user.id, media_id=media_id, caption=payload.caption,
        expires_at=utcnow() + dt.timedelta(hours=payload.hours),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _s_dict(db, s)


@router.get("/home")
def home_stories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    followed = following_ids(db, user.id) | {user.id}
    now = utcnow()
    stories = db.execute(
        select(Story).where(Story.owner_id.in_(followed), Story.expires_at > now)
        .order_by(Story.created_at.desc()).limit(200)
    ).scalars().all()
    return [_s_dict(db, s) for s in stories]


@router.get("/users/{username}")
def user_stories(username: str, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    owner = db.execute(select(User).where(User.username == username.strip().lower())).scalar_one_or_none()
    if owner is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if owner.is_private:
        allowed = user and (user.id == owner.id or owner.id in following_ids(db, user.id) or user.is_admin)
        if not allowed:
            raise HTTPException(status_code=403, detail="Perfil privado")
    stories = db.execute(
        select(Story).where(Story.owner_id == owner.id, Story.expires_at > utcnow()).order_by(Story.created_at.desc())
    ).scalars().all()
    return [_s_dict(db, s) for s in stories]


@router.post("/{story_id}/view")
def view_story(story_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(Story, story_id)
    if s is None or s.expires_at <= utcnow():
        raise HTTPException(status_code=404, detail="Story não encontrado")
    if not db.execute(select(StoryView.id).where(StoryView.story_id == s.id, StoryView.viewer_id == user.id)).first():
        db.add(StoryView(story_id=s.id, viewer_id=user.id))
        db.commit()
    return {"viewed": True}


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_story(story_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(Story, story_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Story não encontrado")
    if s.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Sem permissão")
    db.delete(s)
    db.commit()


__all__ = ["router"]