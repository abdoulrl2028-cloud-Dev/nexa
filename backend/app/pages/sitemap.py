"""Sitemap dinâmico: URLs públicas somente.

Estrutura de exemplo: sitemap.xml (índice) → sitemap-users/posts/groups/events.
Páginas se paginam (50k URLs por arquivo, limite Google). Suporta milhões de
URLs sem gerar um arquivo gigantesco. URLs privadas/restringidas jamais entram.
"""
from __future__ import annotations

import itertools
import urllib.parse

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Circle, Event, Group, Post, User

router = APIRouter(include_in_schema=False)

PER_FILE = 50_000


def _site() -> str:
    return get_settings().site_url.rstrip("/")


def _loc(path: str) -> str:
    return _site() + path


def _xml_escape(text: str) -> str:
    return (
        str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


STATIC_URLS = [
    ("/", "weekly", "1.0"),
    ("/about", "monthly", "0.5"),
    ("/explore", "daily", "0.9"),
    ("/people", "daily", "0.8"),
    ("/groups", "daily", "0.8"),
    ("/circles", "daily", "0.8"),
    ("/events", "daily", "0.9"),
]


@router.get("/sitemap.xml")
def sitemap_index(db: Session = Depends(get_db)):
    def gen():
        yield '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        n_users = db.execute(select(func.count(User.id)).where(User.is_active.is_(True))).scalar() or 0
        n_posts = db.execute(
            select(func.count(Post.id)).where(Post.visibility == "public", Post.status == "published")).scalar() or 0
        n_groups = db.execute(
            select(func.count(Group.id)).where(Group.visibility == "public", Group.is_archived.is_(False))).scalar() or 0
        n_circles = db.execute(
            select(func.count(Circle.id)).where(Circle.visibility == "public", Circle.is_archived.is_(False))).scalar() or 0
        n_events = db.execute(
            select(func.count(Event.id)).where(Event.visibility == "public", Event.status != "cancelled")).scalar() or 0
        for entity, count in [("users", n_users), ("posts", n_posts), ("groups", n_groups),
                              ("circles", n_circles), ("events", n_events)]:
            for page in range(max(1, -(-count // PER_FILE))):
                yield (
                    f'  <sitemap><loc>{_loc(f"/sitemap-{entity}.xml?page={page}")}</loc></sitemap>\n'
                )
        yield "</sitemapindex>\n"

    return StreamingResponse(gen(), media_type="application/xml")


def _sitemap_rows(db: Session, entity: str, page: int) -> list[tuple[str, str]]:
    limit = PER_FILE
    offset = page * PER_FILE
    rows: list[tuple[str, str]] = []
    if entity == "users":
        users = db.execute(select(User).where(User.is_active.is_(True), User.is_private.is_(False))
                           .order_by(User.id).offset(offset).limit(limit)).scalars().all()
        for u in users:
            rows.append((f"/profile/{u.username}", u.created_at.isoformat() if u.created_at else ""))
    elif entity == "posts":
        posts = db.execute(
            select(Post).where(Post.visibility == "public", Post.status == "published")
            .order_by(Post.id).offset(offset).limit(limit)
        ).scalars().all()
        for p in posts:
            rows.append((f"/post/{p.slug}", p.updated_at.isoformat() if p.updated_at else ""))
    elif entity == "groups":
        groups = db.execute(select(Group).where(Group.visibility == "public", Group.is_archived.is_(False))
                            .order_by(Group.id).offset(offset).limit(limit)).scalars().all()
        for g in groups:
            rows.append((f"/groups/{g.slug}", g.created_at.isoformat() if g.created_at else ""))
    elif entity == "circles":
        circles = db.execute(select(Circle).where(Circle.visibility == "public", Circle.is_archived.is_(False))
                             .order_by(Circle.id).offset(offset).limit(limit)).scalars().all()
        for c in circles:
            rows.append((f"/circles/{c.slug}", c.created_at.isoformat() if c.created_at else ""))
    elif entity == "events":
        events = db.execute(select(Event).where(Event.visibility == "public", Event.status != "cancelled")
                            .order_by(Event.id).offset(offset).limit(limit)).scalars().all()
        for e in events:
            rows.append((f"/events/{e.slug}", e.created_at.isoformat() if e.created_at else ""))
    return rows


@router.get("/sitemap-{entity}.xml")
def sitemap_entity(entity: str, page: int = 0, db: Session = Depends(get_db)):
    if entity not in ("users", "posts", "groups", "circles", "events"):
        from fastapi import HTTPException

        raise HTTPException(status_code=404)
    rows = _sitemap_rows(db, entity, page)

    def gen():
        yield '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        for path, lastmod in rows:
            yield "  <url>\n"
            yield f"    <loc>{_xml_escape(_loc(path))}</loc>\n"
            if lastmod:
                yield f"    <lastmod>{lastmod[:10]}</lastmod>\n"
            yield "  </url>\n"
        yield "</urlset>\n"

    return StreamingResponse(gen(), media_type="application/xml")


__all__ = ["router"]