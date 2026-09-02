"""Mensagens diretas (REST + WebSocket realtime).

Persistência no PostgreSQL; entrega em tempo real via WebSocket. O mesmo
restful + realtime é consumido pelo web, desktop e mobile.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.deps import get_current_user
from app.models import Conversation, ConversationParticipant, Message, User, utcnow
from app.notifier import notify
from app.routers.users import get_media_base
from app.schemas import MessageIn
from app.security import decode_token
from app.storage import media_url
from app.ws import manager

router = APIRouter(prefix="/api/messages", tags=["messages"])


def get_or_create_conversation(db: Session, a: int, b: int) -> Conversation:
    existing = db.execute(
        select(Conversation.id)
        .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
        .where(ConversationParticipant.user_id == a)
    ).scalars().all()
    for conv_id in existing:
        other = db.execute(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == conv_id,
                ConversationParticipant.user_id != a,
            )
        ).scalars().all()
        if b in other:
            return db.get(Conversation, conv_id)
    conv = Conversation()
    db.add(conv)
    db.flush()
    db.add_all([
        ConversationParticipant(conversation_id=conv.id, user_id=a),
        ConversationParticipant(conversation_id=conv.id, user_id=b),
    ])
    return conv


def _conversation_dict(db: Session, conv: Conversation, me: int) -> dict:
    rows = db.execute(
        select(ConversationParticipant).where(ConversationParticipant.conversation_id == conv.id)
    ).scalars().all()
    other_id = next((rp.user_id for rp in rows if rp.user_id != me), None)
    other = db.get(User, other_id) if other_id else None
    last = db.execute(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at.desc()).limit(1)
    ).scalar_one_or_none()
    unread = 0
    my_participant = next(rp for rp in rows if rp.user_id == me)
    if my_participant.last_read_at:
        unread = db.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id == conv.id, Message.sender_id != me,
                Message.created_at > my_participant.last_read_at,
            )
        ).scalar() or 0
    return {
        "id": conv.id,
        "other": {
            "username": other.username, "display_name": other.display_name or other.username,
            "avatar": media_url(other.avatar_key), "online": manager.is_online(other.id) if other else False,
        },
        "last_message": last.content if last else "",
        "last_at": last.created_at.isoformat() if last else None,
        "unread": unread,
    }


@router.get("/conversations")
def conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv_ids = db.execute(
        select(ConversationParticipant.conversation_id).where(ConversationParticipant.user_id == user.id)
    ).scalars().all()
    convs = [db.get(Conversation, c) for c in conv_ids if db.get(Conversation, c)]
    convs.sort(key=lambda c: _last_at(db, c), reverse=True)
    return [_conversation_dict(db, c, user.id) for c in convs]


def _last_at(db: Session, conv: Conversation):
    last = db.execute(
        select(Message.created_at).where(Message.conversation_id == conv.id).order_by(Message.created_at.desc()).limit(1)
    ).scalar_one_or_none()
    return last or conv.created_at


@router.get("/conversations/{conv_id}")
def conversation_messages(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    participant = db.execute(
        select(ConversationParticipant.id).where(
            ConversationParticipant.conversation_id == conv_id, ConversationParticipant.user_id == user.id
        )
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="Sem acesso")
    msgs = db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at.desc()).limit(100)
    ).scalars().all()
    msgs.reverse()
    return [
        {"id": m.id, "sender_id": m.sender_id, "content": m.content, "media": _media_dict(db, m.media_id),
         "created_at": m.created_at.isoformat() if m.created_at else None, "read": m.read_at is not None}
        for m in msgs
    ]


def _media_dict(db: Session, media_id: int | None):
    if not media_id:
        return None
    from app.models import Media

    m = db.get(Media, media_id)
    return m.to_dict(get_media_base(db)) if m else None


@router.post("", status_code=status.HTTP_201_CREATED)
async def send_message(payload: MessageIn, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    if not payload.recipient and not payload.conversation_id:
        raise HTTPException(status_code=400, detail="Informe recipient ou conversation_id")
    if not payload.content and not payload.media_key:
        raise HTTPException(status_code=400, detail="Mensagem vazia")

    conv = None
    if payload.conversation_id:
        conv = db.get(Conversation, payload.conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
        participant = db.execute(
            select(ConversationParticipant.id).where(
                ConversationParticipant.conversation_id == conv.id, ConversationParticipant.user_id == user.id
            )
        ).first()
        if not participant:
            raise HTTPException(status_code=403, detail="Sem acesso")
    else:
        target = db.execute(select(User).where(User.username == payload.recipient.strip().lower())).scalar_one_or_none()
        if target is None or target.id == user.id or not target.is_active:
            raise HTTPException(status_code=404, detail="Destinatário inválido")
        conv = get_or_create_conversation(db, user.id, target.id)

    media_id = None
    if payload.media_key:
        from app.models import Media

        media = db.execute(select(Media).where(Media.key == payload.media_key, Media.owner_id == user.id)).scalar_one_or_none()
        if media is None:
            raise HTTPException(status_code=400, detail="Mídia inválida")
        media_id = media.id

    msg = Message(conversation_id=conv.id, sender_id=user.id, content=payload.content[:4000], media_id=media_id)
    db.add(msg)
    db.flush()
    other_id = _other_id(db, conv, user.id)
    _mark_read(db, conv.id, user.id)
    db.commit()

    event = {
        "type": "message",
        "message": {"id": msg.id, "conversation_id": conv.id, "sender_id": user.id,
                    "content": msg.content, "media": _media_dict(db, msg.media_id),
                    "created_at": msg.created_at.isoformat()},
    }
    if other_id:
        await manager.send_to_user(other_id, event)
        notify(db, other_id, user.id, "message", f"{user.display_name or user.username}: {msg.content[:120]}",
               entity_type="conversation", entity_id=str(conv.id))
    return event["message"]


def _other_id(db: Session, conv: Conversation, me: int) -> int | None:
    rows = db.execute(
        select(ConversationParticipant.user_id).where(ConversationParticipant.conversation_id == conv.id)
    ).scalars().all()
    return next((r for r in rows if r != me), None)


def _mark_read(db: Session, conv_id: int, user_id: int) -> None:
    db.execute(
        ConversationParticipant.__table__.update()
        .where(ConversationParticipant.conversation_id == conv_id, ConversationParticipant.user_id == user_id)
        .values(last_read_at=utcnow())
    )


@router.post("/conversations/{conv_id}/read")
def read_messages(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    participant = db.execute(
        select(ConversationParticipant.id).where(
            ConversationParticipant.conversation_id == conv_id, ConversationParticipant.user_id == user.id
        )
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="Sem acesso")
    _mark_read(db, conv_id, user.id)
    db.execute(
        Message.__table__.update()
        .where(Message.conversation_id == conv_id, Message.sender_id != user.id, Message.read_at.is_(None))
        .values(read_at=utcnow())
    )
    db.commit()
    return {"read": True}


# ------------------------------------------------------------------ WebSocket
@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str | None = Query(default=None)):
    token = token or (websocket.cookies or {}).get("nexa_session")
    user = _ws_user(token)
    if user is None:
        await websocket.close(code=4401)
        return
    await manager.connect(user.id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            kind = data.get("type")
            if kind == "ping":
                await websocket.send_json({"type": "pong"})
            elif kind == "message":
                await ws_send_message(user.id, data)
            elif kind == "typing":
                recipient = data.get("recipient")
                conv_id = data.get("conversation_id")
                other = _ws_other(user.id, recipient, conv_id)
                if other:
                    await manager.send_to_user(other, {"type": "typing", "conversation_id": conv_id,
                                                       "from": user.id})
            elif kind == "read":
                conv_id = data.get("conversation_id")
                await _ws_mark_read(user.id, conv_id)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(user.id, websocket)


def _ws_user(token: str) -> User | None:
    try:
        payload = decode_token(token)
    except ValueError:
        return None
    if payload.get("type") != "access":
        return None
    db = SessionLocal()
    try:
        return db.get(User, int(payload["sub"]))
    except Exception:  # noqa: BLE001
        return None
    finally:
        db.close()


def _ws_other(user_id: int, recipient: str | None, conv_id: int | None) -> int | None:
    db = SessionLocal()
    try:
        if conv_id:
            return _other_id(db, db.get(Conversation, conv_id), user_id)
        if recipient:
            u = db.execute(select(User).where(User.username == recipient.strip().lower())).scalar_one_or_none()
            return u.id if u else None
        return None
    finally:
        db.close()


async def ws_send_message(user_id: int, data: dict) -> None:
    recipient = data.get("recipient")
    conv_id = data.get("conversation_id")
    content = (data.get("content") or "").strip()
    media_key = data.get("media_key")

    db = SessionLocal()
    try:
        me = db.get(User, user_id)
        target = None
        if recipient:
            target = db.execute(select(User).where(User.username == recipient.strip().lower())).scalar_one_or_none()
            if target is None or target.id == me.id:
                return
        conv = db.get(Conversation, int(conv_id)) if conv_id else None
        if conv is None and target:
            conv = get_or_create_conversation(db, me.id, target.id)
        if conv is None:
            return
        participant = db.execute(
            select(ConversationParticipant.id).where(
                ConversationParticipant.conversation_id == conv.id, ConversationParticipant.user_id == me.id)
        ).first()
        if not participant:
            return
        if not content and not media_key:
            return
        media = None
        if media_key:
            from app.models import Media

            media = db.execute(select(Media).where(Media.key == media_key, Media.owner_id == me.id)).scalar_one_or_none()
        msg = Message(conversation_id=conv.id, sender_id=me.id, content=content[:4000],
                      media_id=media.id if media else None)
        db.add(msg)
        db.flush()
        db.commit()
        other_id = _other_id(db, conv, me.id)
        event = {"type": "message",
                 "message": {"id": msg.id, "conversation_id": conv.id, "sender_id": me.id,
                             "content": msg.content, "media": _media_dict(db, msg.media_id),
                             "created_at": msg.created_at.isoformat()}}
        if other_id:
            await manager.send_to_user(other_id, event)
            notify(db, other_id, me.id, "message", f"{me.display_name or me.username}: {msg.content[:120]}",
                   entity_type="conversation", entity_id=str(conv.id))
    finally:
        db.close()


async def _ws_mark_read(user_id: int, conv_id: int) -> None:
    db = SessionLocal()
    try:
        participant = db.execute(
            select(ConversationParticipant.id).where(
                ConversationParticipant.conversation_id == conv_id, ConversationParticipant.user_id == user_id)
        ).first()
        if participant:
            _mark_read(db, conv_id, user_id)
            db.commit()
            other = _other_id(db, db.get(Conversation, conv_id), user_id)
            if other:
                await manager.send_to_user(other, {"type": "read", "conversation_id": conv_id, "by": user_id})
    finally:
        db.close()


__all__ = ["router"]