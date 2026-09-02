"""Notificações: persistência + push realtime."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Notification, utcnow
from app.ws import manager


def notify(
    db: Session,
    user_id: int,
    actor_id: int | None,
    type_: str,
    message: str,
    entity_type: str = "",
    entity_id: str = "",
) -> Notification:
    if user_id == actor_id:
        return None  # não notificar a si mesmo
    n = Notification(
        user_id=user_id,
        actor_id=actor_id,
        type_=type_,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(n)
    db.flush()
    _push(user_id, n)
    return n


def _push(user_id: int, n: Notification) -> None:
    import asyncio

    payload = {
        "type": "notification",
        "notification": {
            "id": n.id,
            "type": n.type_,
            "message": n.message,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        },
    }
    try:
        asyncio.get_running_loop().create_task(manager.send_to_user(user_id, payload))
    except RuntimeError:
        pass  # fora de loop async (ex.: scripts/testes)


def unread_count(db: Session, user_id: int) -> int:
    from sqlalchemy import func, select

    return db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.read_at.is_(None)
        )
    ).scalar() or 0


__all__ = ["notify", "unread_count"]