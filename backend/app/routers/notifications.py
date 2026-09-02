"""Notificações: lista, leitura e contagem de não lidas."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Notification, User, utcnow
from app.notifier import unread_count

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _n_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type_,
        "message": n.message,
        "entity_type": n.entity_type,
        "entity_id": n.entity_id,
        "read": n.read_at is not None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("")
def list_notifications(
    limit: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Notification).where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc()).limit(limit)
    ).scalars().all()
    return {"items": [_n_dict(n) for n in rows], "unread": unread_count(db, user.id)}


@router.get("/unread-count")
def count_unread(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"unread": unread_count(db, user.id)}


@router.post("/{notification_id}/read")
def mark_one_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    n.read_at = n.read_at or utcnow()
    db.commit()
    return {"read": True}


@router.post("/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(
        Notification.__table__.update()
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    db.commit()
    return {"read": True}


@router.delete("/{notification_id}", status_code=204)
def delete_notification(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    db.delete(n)
    db.commit()


__all__ = ["router"]