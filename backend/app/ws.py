"""WebSocket realtime: chat, notificações e presença.

Conexões são mantidas por usuário. A escrita é persistida no PostgreSQL; o
WebSocket apenas entrega eventos em tempo real. Em produção pode escalar atrás
de um broker (Redis pub/sub) — ver docs/ARCHITECTURE.md.
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket

from app.cache import cache


class ConnectionManager:
    def __init__(self) -> None:
        self._conns: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._conns[user_id].add(ws)
        cache.set(f"online:{user_id}", "1", ttl=120)

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._conns.get(user_id, set()).discard(ws)
            if not self._conns[user_id]:
                self._conns.pop(user_id, None)
                cache.delete(f"online:{user_id}")

    async def send_to_user(self, user_id: int, event: dict) -> None:
        sockets = list(self._conns.get(user_id, set()))
        if not sockets:
            return
        payload = json.dumps(event, ensure_ascii=False, default=str)
        await asyncio.gather(*(s.send_text(payload) for s in sockets), return_exceptions=True)

    def is_online(self, user_id: int) -> bool:
        return bool(self._conns.get(user_id)) or cache.get(f"online:{user_id}") == "1"


manager = ConnectionManager()


__all__ = ["manager"]