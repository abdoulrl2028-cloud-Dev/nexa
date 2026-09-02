"""Schemas Pydantic (validação de entrada/saída da API)."""
from __future__ import annotations

import datetime as dt
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,32}$")


class RegisterIn(BaseModel):
    username: str
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=64)
    email: str | None = Field(default=None, max_length=255)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip().lower()
        if not USERNAME_RE.match(v):
            raise ValueError("username: 3-32 caracteres, minúsculo, letras/números/_")
        return v


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshIn(BaseModel):
    refresh_token: str


class UserUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    bio: str | None = Field(default=None, max_length=500)
    is_private: bool | None = None
    avatar_key: str | None = None
    cover_key: str | None = None


class PostIn(BaseModel):
    title: str = Field(default="", max_length=160)
    content: str = Field(default="", max_length=100_000)
    visibility: str = Field(default="public")
    media_keys: list[str] = Field(default_factory=list)

    @field_validator("visibility")
    @classmethod
    def _vis(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("public", "private", "friends"):
            raise ValueError("visibilidade inválida")
        return v


class CommentIn(BaseModel):
    content: str = Field(min_length=1, max_length=2_000)


class GroupIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=5_000)
    visibility: str = Field(default="public")
    image_key: str | None = None

    @field_validator("visibility")
    @classmethod
    def _vis(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("public", "private"):
            raise ValueError("visibilidade inválida")
        return v


class CircleIn(GroupIn):
    pass


class EventIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=10_000)
    location: str = Field(default="", max_length=255)
    begins_at: dt.datetime
    ends_at: dt.datetime | None = None
    visibility: str = Field(default="public")
    image_key: str | None = None

    @field_validator("visibility")
    @classmethod
    def _vis(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("public", "private"):
            raise ValueError("visibilidade inválida")
        return v


class StoryIn(BaseModel):
    caption: str = Field(default="", max_length=240)
    media_key: str | None = None
    hours: int = Field(default=24, ge=1, le=168)


class MessageIn(BaseModel):
    content: str = Field(default="", max_length=4_000)
    media_key: str | None = None
    conversation_id: int | None = None
    recipient: str | None = None


class ReportIn(BaseModel):
    reason: str = Field(max_length=400)


class DocsIn(BaseModel):
    model_config = ConfigDict(from_attributes=True)