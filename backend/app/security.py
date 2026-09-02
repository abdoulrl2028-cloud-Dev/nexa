"""Segurança: hashing de senha (PBKDF2-HMAC-SHA256) e JWT (HMAC-SHA256).

Implementação com stdlib para não depender de binários nativos. As operações
são criptográficas de verdade: PBKDF2 com salt aleatório e JWT/HS256 com JSON
padding-safe, incluindo expiração e verificação de assinatura.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from app.config import get_settings

_ITERATIONS = 260_000
_SALT_BYTES = 16


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return _encode(salt) + "$" + _encode(dk)


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_b64, dk_b64 = stored.split("$", 1)
    except ValueError:
        return False
    try:
        salt = _decode(salt_b64)
        expected = _decode(dk_b64)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return hmac.compare_digest(dk, expected)


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# ---------------------------------------------------------------- JWT / HS256
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload_b64: str, key: bytes) -> str:
    return _b64url(hmac.new(key, payload_b64.encode("ascii"), hashlib.sha256).digest())


def create_token(payload: dict[str, Any], expires_seconds: int) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = dict(payload)
    body["iat"] = int(time.time())
    body["exp"] = int(time.time()) + expires_seconds
    body_b64 = _b64url(json.dumps(body, separators=(",", ":")).encode())
    signature = _sign(f"{header}.{body_b64}", _key())
    return f"{header}.{body_b64}.{signature}"


def decode_token(token: str, verify_exp: bool = True) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("token malformado")
    header_b64, body_b64, sig = parts
    if not hmac.compare_digest(sig, _sign(f"{header_b64}.{body_b64}", _key())):
        raise ValueError("assinatura inválida")
    try:
        body = json.loads(_b64url_decode(body_b64))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("payload inválido") from exc
    if verify_exp and int(body.get("exp", 0)) < int(time.time()):
        raise ValueError("token expirado")
    return body


def _key() -> bytes:
    secret = get_settings().secret_key
    if not secret:
        secret = "nexa-dev-insecure-key-altere-em-producao"
    return secret.encode("utf-8")


def generate_secret() -> str:
    return secrets.token_hex(32)


def new_token_id() -> str:
    return secrets.token_urlsafe(16)


__all__ = [
    "hash_password",
    "verify_password",
    "create_token",
    "decode_token",
    "generate_secret",
    "new_token_id",
]