"""Configuração dos testes do NEXA.

Ambiente isolado: SQLite em arquivo temporário + storage local temporário.
Rodar com: `.venv/bin/python -m pytest tests -q` a partir de `nexa/backend`.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="nexa-test-"))
os.environ["NEXA_ENV"] = "development"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["STORAGE_LOCAL_DIR"] = str(_TMP / "uploads")
os.environ["SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.db import SessionLocal, engine, init_db  # noqa: E402

init_db()


def clean_tables() -> None:
    with engine.begin() as conn:
        for table in reversed(models.Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture()
def client():
    clean_tables()
    from app.main import app

    with TestClient(app) as c:
        yield c


def api(client: TestClient, method: str, path: str, body=None, headers=None, token=None):
    h = {**(headers or {})}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return client.request(method, path, json=body if body is not None else None, headers=h)


def register(client: TestClient, username: str, password: str = "senha12345", display_name: str | None = None) -> str:
    r = api(client, "POST", "/api/auth/register",
            {"username": username, "password": password, "display_name": display_name or username.title()})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def create_post(client, token: str, title: str, content: str = "conteúdo", visibility: str = "public") -> dict:
    r = api(client, "POST", "/api/posts", {"title": title, "content": content, "visibility": visibility}, token=token)
    assert r.status_code == 201, r.text
    return r.json()