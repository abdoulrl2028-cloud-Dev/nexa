"""NEXA — API e aplicação web.

Um único serviço (API + SSR + estáticos) consumido por web, mobile e desktop.
Em produção roda atrás de Caddy/Nginx (TLS) + CDN/WAF + load balancer.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db
from app.pages.pages import router as pages_router
from app.pages.sitemap import router as sitemap_router
from app.routers import (
    admin,
    auth,
    circles,
    events,
    feed,
    groups,
    messages,
    notifications,
    posts,
    search,
    stories,
    uploads,
    users,
)

settings = get_settings()
settings.validate()

_APP_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _APP_DIR.parent / "static"


def settings_env(name: str, default: str) -> str:
    import os

    return os.environ.get(name, default)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="NEXA API",
    description="Rede social multiplataforma — web, Android, tablet e desktop compartilham a mesma API.",
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


cors_origins = [o.strip() for o in settings_env("NEXA_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob: https:; media-src 'self' blob: https:; "
            "style-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self' wss: https:; "
            "worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        )
    if request.url.path.startswith(("/app/", "/app", "/login", "/register", "/api/")):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    path = request.url.path
    if path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": "recurso não encontrado"})
    templates = _get_templates()
    response = templates.TemplateResponse(
        request, "404.html",
        {"seo": {"indexable": False, "title": "Não encontrado | NEXA", "description": "", "canonical": ""}},
    )
    response.status_code = 404
    return response


def _get_templates():
    from fastapi.templating import Jinja2Templates
    from pathlib import Path

    return Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


# ---------------------------------------------------------------- routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(feed.router)
app.include_router(search.router)
app.include_router(groups.router)
app.include_router(circles.router)
app.include_router(events.router)
app.include_router(stories.router)
app.include_router(messages.router)
app.include_router(notifications.router)
app.include_router(uploads.router)
app.include_router(admin.router)

app.include_router(sitemap_router)
app.include_router(pages_router)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/api")
def api_root():
    return {
        "service": "NEXA API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "endpoints_prefix": "/api",
    }