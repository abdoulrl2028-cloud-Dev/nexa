"""Autenticação: registro, login, refresh, logout, perfil atual.

Tokens JWT (HMAC-SHA256). Refresh token com revogação via cache/Redis.
HTTP-only cookie para o website; Bearer para apps (mobile/desktop/web).
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cache import cache
from app.config import get_settings
from app.db import get_db
from app.deps import SESSION_COOKIE, get_current_user
from app.models import Follow, User, utcnow
from app.schemas import LoginIn, RegisterIn, RefreshIn, TokenOut, UserUpdateIn
from app.security import create_token, decode_token, hash_password, new_token_id, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 dias


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "bio": user.bio,
        "avatar": user.avatar_key,
        "cover": user.cover_key,
        "is_private": user.is_private,
        "is_verified": user.is_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _issue_tokens(user: User) -> dict:
    settings = get_settings()
    jti = new_token_id()
    access = create_token({"sub": str(user.id), "type": "access", "jti": jti}, settings.jwt_access_minutes * 60)
    refresh_jti = new_token_id()
    refresh = create_token({"sub": str(user.id), "type": "refresh", "jti": refresh_jti}, settings.jwt_refresh_days * 86400)
    # armazena jti do refresh para revogação em logout
    cache.set(f"jti:{refresh_jti}", str(user.id), ttl=settings.jwt_refresh_days * 86400)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "user": _user_dict(user)}


def _set_cookie(resp: Response, access: str) -> None:
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=access,
        max_age=settings_max_age(),
        httponly=True,
        secure=get_settings().is_production,
        samesite="lax",
        path="/",
    )


def settings_max_age() -> int:
    return get_settings().jwt_access_minutes * 60


def _counts(db: Session, user_id: int) -> dict:
    followers = db.execute(select(func.count(Follow.id)).where(Follow.following_id == user_id)).scalar() or 0
    following = db.execute(select(func.count(Follow.id)).where(Follow.follower_id == user_id)).scalar() or 0
    return {"followers": followers, "following": following}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, response: Response, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail="Registro fechado neste ambiente")
    exists = db.execute(select(User).where(
        (User.username == payload.username) | (User.email == (payload.email or ""))
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Usuário ou email já cadastrado")
    user = User(
        username=payload.username,
        email=payload.email or None,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip() or payload.username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    tokens = _issue_tokens(user)
    _set_cookie(response, tokens["access_token"])
    return tokens


@router.post("/login")
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.username == payload.username.strip().lower())).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Conta desativada")
    tokens = _issue_tokens(user)
    _set_cookie(response, tokens["access_token"])
    return tokens


@router.post("/refresh")
def refresh(payload: RefreshIn, response: Response, db: Session = Depends(get_db)):
    try:
        body = decode_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Refresh inválido") from exc
    if body.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token não é de refresh")
    jti = body.get("jti", "")
    if not cache.get(f"jti:{jti}"):
        raise HTTPException(status_code=401, detail="Refresh revogado")
    user = db.get(User, int(body["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuário inválido")
    cache.delete(f"jti:{jti}")  # rotação
    tokens = _issue_tokens(user)
    _set_cookie(response, tokens["access_token"])
    return tokens


@router.post("/logout")
def logout(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    payload: RefreshIn | None = None,
):
    if payload and payload.refresh_token:
        try:
            body = decode_token(payload.refresh_token)
            cache.delete(f"jti:{body.get('jti', '')}")
        except ValueError:
            pass  # token já expirado/inválido — logout segue normalmente
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = _user_dict(user)
    data["counts"] = _counts(db, user.id)
    return data


@router.patch("/me")
def update_me(payload: UserUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user, field, value)
    user.updated_at = utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    data = _user_dict(user)
    data["counts"] = _counts(db, user.id)
    return data


__all__ = ["router", "_user_dict", "_set_cookie"]