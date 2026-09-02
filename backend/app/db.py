"""Acesso a banco: SQLAlchemy 2.0 (sync).

- Desenvolvimento: SQLite (sem servidor externo).
- Produção: PostgreSQL via DATABASE_URL, com connection pooling (QueuePool).

Nunca expor o banco diretamente à internet: a API conversa com o banco apenas
através da rede interna/overlay; credenciais vêm de variáveis de ambiente.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    settings = get_settings()
    url = settings.database_url
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
        )
    else:
        # PostgreSQL: connection pooling para escala horizontal.
        # Pool size configurável por ambiente (defaults conservadores p/ dev).
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=10,
            max_overflow=20,
        )
    return engine


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Cria tabelas diretamente (dev). Em produção usar `alembic upgrade head`."""
    from app import models  # noqa: F401  (registra os modelos)

    Base.metadata.create_all(bind=engine)


__all__ = ["Base", "engine", "SessionLocal", "get_db", "init_db"]