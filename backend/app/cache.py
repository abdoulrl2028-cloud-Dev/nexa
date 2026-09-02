"""Camada de cache/sessão entre instâncias.

- Redis quando REDIS_URL definida (produção, múltiplas instâncias).
- Fallback em memória (desenvolvimento / 1 instância).

Usado para: online status, token blacklist (JWT refresh), limite de taxa e
cache de leitura. Nada de sessão "só na memória" em produção.
"""
from __future__ import annotations

import time
from typing import Any

from app.config import get_settings


class CacheBackend:
    def __init__(self) -> None:
        self._mem: dict[str, tuple[float, Any]] = {}
        self._redis = None
        settings = get_settings()
        if settings.redis_url:
            try:
                import redis  # noqa: PLC0415
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("REDIS_URL definida exige `pip install redis`") from exc
            self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    @property
    def use_redis(self) -> bool:
        return self._redis is not None

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        if self._redis:
            self._redis.set(key, value, ex=ttl)
            return
        self._mem[key] = (time.time() + (ttl or 60), value)

    def get(self, key: str) -> str | None:
        if self._redis:
            return self._redis.get(key)
        entry = self._mem.get(key)
        if not entry:
            return None
        expires, value = entry
        if expires < time.time():
            self._mem.pop(key, None)
            return None
        return value

    def delete(self, key: str) -> None:
        if self._redis:
            self._redis.delete(key)
            return
        self._mem.pop(key, None)

    def incr(self, key: str, ttl: int | None = None) -> int:
        if self._redis:
            pipe = self._redis.pipeline()
            pipe.incr(key)
            if ttl:
                pipe.expire(key, ttl)
            return int(pipe.execute()[0])
        n = int(self.get(key) or 0) + 1
        self.set(key, str(n), ttl)
        return n

    def expire(self, key: str, ttl: int) -> None:
        if self._redis:
            self._redis.expire(key, ttl)


cache = CacheBackend()


__all__ = ["cache"]