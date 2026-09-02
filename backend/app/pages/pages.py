"""Páginas SSR: conteúdo público indexável + rotas da aplicação.

SEO legítimo: páginas públicas indexadas; conteúdo privado recebe noindex
(meta e header X-Robots-Tag). Nada é manipulado artificialmente.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import (
    SESSION_COOKIE,
    can_view_circle,
    can_view_event,
    can_view_group,
    can_view_post,
    can_view_profile,
    get_optional_user,
)
from app.models import Circle, Event, Group, Post, User, utcnow
from app.routers.posts import _serialize
from app.routers.users import get_media_base
from app.storage import media_url

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(__import__("pathlib").Path(__file__).resolve().parent.parent.parent / "templates"))
templates.env.globals["css_ver"] = "1.0.0"
templates.env.globals["js_ver"] = "1.0.0"


def _pretty_datetime(value) -> str:
    import datetime as _dt

    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return value
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    now = _dt.datetime.utcnow()
    delta = now - value
    secs = delta.total_seconds()
    if secs < 60:
        return "agora"
    mins = int(secs // 60)
    if mins < 60:
        return f"há {mins} min"
    hours = int(mins // 60)
    if hours < 24:
        return f"há {hours} h"
    days = int(hours // 24)
    if days < 7:
        return f"há {days} d"
    return value.strftime("%d/%m/%Y")


templates.env.filters["pretty"] = _pretty_datetime

DEFAULT_DESCRIPTION = "NEXA — a rede social multiplataforma: web, Android, tablets e desktop."


def _site() -> str:
    return get_settings().site_url.rstrip("/")


def _seo_context(
    title: str,
    *,
    description: str = DEFAULT_DESCRIPTION,
    canonical: str = "",
    indexable: bool = True,
    image: str | None = None,
    type_: str = "website",
    json_ld: dict | None = None,
    keywords: str = "",
) -> dict:
    if not canonical:
        canonical = _site() + "/"
    return {
        "title": title,
        "description": description[:300],
        "canonical": canonical,
        "indexable": indexable,
        "robots": "" if indexable else "noindex,nofollow",
        "og_type": type_,
        "og_image": image or f"{_site()}/static/icons/icon-512.png",
        "site_url": _site(),
        "json_ld": json_ld,
        "keywords": keywords,
    }


def _page_seo(opts: dict) -> dict:
    return {**{"title": "", "description": DEFAULT_DESCRIPTION, "canonical": "", "indexable": True,
               "robots": "", "og_type": "website", "og_image": "", "site_url": _site(), "json_ld": None, "keywords": ""},
            **opts}


def _render(request: Request, name: str, ctx: dict, seo: dict, current_user: User | None):
    ctx["seo"] = _page_seo(seo)
    ctx["current_user"] = current_user
    if ctx.get("app"):
        for _k, _v in ctx["app"].items():
            ctx.setdefault(_k, _v)
    ctx["ws_url"] = _site().replace("https", "wss").replace("http", "ws") + "/api/messages/ws"
    ctx["session_token"] = request.cookies.get(SESSION_COOKIE, "")
    resp = templates.TemplateResponse(request, name, ctx)
    if not seo.get("indexable", True):
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


def _entity_ctx(show: bool) -> dict:
    return {"not_indexable": not show}


def _app_context(request: Request, user: User, db: Session) -> dict:
    from app.notifier import unread_count

    return {
        "page": request.url.path,
        "me": _user_me_dict(user),
        "unread_notifications": unread_count(db, user.id),
    }


def _user_me_dict(user: User) -> dict:
    return {
        "username": user.username,
        "display_name": user.display_name,
        "avatar": media_url(user.avatar_key),
        "is_verified": user.is_verified,
        "bio": user.bio,
        "is_private": user.is_private,
    }


# ------------------------------------------------------------------ público
@router.get("/")
def home(request: Request, current_user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    posts = db.execute(
        select(Post).where(Post.visibility == "public", Post.status == "published")
        .order_by(Post.created_at.desc()).limit(9)
    ).scalars().all()
    title = "NEXA — rede social multiplataforma"
    ctx = {
        "feed": _serialize(db, list(posts), current_user.id if current_user else None),
        "stats": {
            "groups": db.execute(select(func.count(Group.id)).where(Group.visibility == "public", Group.is_archived.is_(False))).scalar() or 0,
            "events": db.execute(select(func.count(Event.id)).where(Event.visibility == "public")).scalar() or 0,
            "people": db.execute(select(func.count(User.id)).where(User.is_active.is_(True))).scalar() or 0},
        **({"app": _app_context(request, current_user, db)} if current_user else {}),
    }
    seo = _seo_context(title, canonical=_site() + "/", keywords="rede social, nexa, comunidade")
    return _render(request, "home.html", ctx, seo, current_user)


@router.get("/about")
def about(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    seo = _seo_context("Sobre o NEXA", canonical=_site() + "/about")
    return _render(request, "about.html", {}, seo, current_user)


@router.get("/explore")
def explore(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    posts = db.execute(
        select(Post).where(Post.visibility == "public", Post.status == "published")
        .order_by(Post.created_at.desc()).limit(30)
    ).scalars().all()
    seo = _seo_context("Explorar | NEXA", canonical=_site() + "/explore")
    return _render(request, "explore.html", {"feed": _serialize(db, list(posts), current_user.id if current_user else None)},
                   seo, current_user)


@router.get("/people")
def people(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    users = db.execute(
        select(User).where(User.is_active.is_(True), User.is_private.is_(False))
        .order_by(User.created_at.desc()).limit(60)
    ).scalars().all()
    people = [
        {"username": u.username, "display_name": u.display_name or u.username,
         "avatar": media_url(u.avatar_key), "bio": u.bio, "is_verified": u.is_verified}
        for u in users
    ]
    seo = _seo_context("Pessoas | NEXA", canonical=_site() + "/people")
    return _render(request, "people.html", {"people": people}, seo, current_user)


@router.get("/groups")
def groups_page(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    groups = db.execute(
        select(Group).where(Group.visibility == "public", Group.is_archived.is_(False))
        .order_by(Group.member_count.desc()).limit(60)
    ).scalars().all()
    seo = _seo_context("Grupos | NEXA", canonical=_site() + "/groups")
    return _render(
        request, "groups.html",
        {"groups": [{"slug": g.slug, "name": g.name, "description": g.description,
                     "image": media_url(g.image_key), "member_count": g.member_count} for g in groups]},
        seo, current_user,
    )


@router.get("/circles")
def circles_page(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    circles = db.execute(
        select(Circle).where(Circle.visibility == "public", Circle.is_archived.is_(False))
        .order_by(Circle.member_count.desc()).limit(60)
    ).scalars().all()
    seo = _seo_context("Círculos | NEXA", canonical=_site() + "/circles")
    return _render(
        request, "circles.html",
        {"circles": [{"slug": c.slug, "name": c.name, "description": c.description,
                      "image": media_url(c.image_key), "member_count": c.member_count} for c in circles]},
        seo, current_user,
    )


@router.get("/events")
def events_page(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    events = db.execute(
        select(Event).where(Event.visibility == "public", Event.status != "cancelled")
        .order_by(Event.begins_at.asc()).limit(60)
    ).scalars().all()
    seo = _seo_context("Eventos | NEXA", canonical=_site() + "/events")
    return _render(
        request, "events.html",
        {"events": [{"slug": e.slug, "name": e.name, "location": e.location,
                     "begins_at": e.begins_at.isoformat() if e.begins_at else None,
                     "participant_count": e.participant_count} for e in events]},
        seo, current_user,
    )


@router.get("/profile/{username}")
def profile_page(username: str, request: Request, db: Session = Depends(get_db),
                 current_user: User | None = Depends(get_optional_user)):
    user = db.execute(select(User).where(User.username == username.strip().lower())).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Não encontrado")
    indexable = can_view_profile(user, current_user, db)  # público quando não privado
    name = user.display_name or user.username
    seo = _seo_context(
        f"{name} | NEXA",
        description=f"Perfil público de {name} no NEXA." if indexable else "Perfil privado no NEXA.",
        canonical=_site() + f"/profile/{user.username}",
        indexable=indexable,
        image=media_url(user.avatar_key),
        type_="profile",
        json_ld={
            "@context": "https://schema.org", "@type": "ProfilePage",
            "name": name, "url": _site() + f"/profile/{user.username}",
            "description": user.bio if indexable else "",
            "image": media_url(user.avatar_key),
        },
    )
    posts = []
    if indexable:
        posts_db = db.execute(
            select(Post).where(Post.author_id == user.id, Post.visibility == "public", Post.status == "published")
            .order_by(Post.created_at.desc()).limit(20)
        ).scalars().all()
        posts = _serialize(db, list(posts_db), current_user.id if current_user else None)
    ctx = {
        "profile": {"username": user.username, "display_name": name, "bio": user.bio if indexable else "",
                    "avatar": media_url(user.avatar_key), "cover": media_url(user.cover_key),
                    "is_private": user.is_private, "is_verified": user.is_verified,
                    "created_at": user.created_at.isoformat() if user.created_at else None},
        "posts": posts,
        "is_viewer": bool(current_user and current_user.id == user.id and indexable),
        "not_indexable": not indexable,
    }
    return _render(request, "profile.html", ctx, seo, current_user)


@router.get("/post/{slug}")
def post_page(slug: str, request: Request, db: Session = Depends(get_db),
              current_user: User | None = Depends(get_optional_user)):
    post = db.execute(select(Post).where(Post.slug == slug)).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post não encontrado")
    indexable = post.visibility == "public" and post.status == "published"
    visible = can_view_post(post, current_user, db)
    if not visible:
        raise HTTPException(status_code=404, detail="Post não encontrado")
    title = post.title or (post.content[:40] if post.content else "Post")
    post_data = _serialize(db, [post], current_user.id if current_user else None)[0]
    comments = []
    if visible:
        from app.models import Comment

        rows = db.execute(
            select(Comment).where(Comment.post_id == post.id, Comment.is_deleted.is_(False))
            .order_by(Comment.created_at.asc()).limit(100)
        ).scalars()
        comments = [{"id": c.id, "content": c.content,
                     "author": c.author.display_name or c.author.username,
                     "created_at": c.created_at.isoformat() if c.created_at else None} for c in rows]
    summary = _plain_summary(post.content) if post.content else ""
    seo = _seo_context(
        f"{title} | NEXA",
        description=summary[:160] if (indexable and summary) else "Post no NEXA.",
        canonical=_site() + f"/post/{post.slug}",
        indexable=indexable,
        image=post_data["media"][0]["url"] if post_data.get("media") else None,
        type_="article",
        json_ld=({
            "@context": "https://schema.org", "@type": "BlogPosting",
            "headline": title, "url": _site() + f"/post/{post.slug}",
            "datePublished": post.created_at.isoformat() if post.created_at else None,
            "author": {"@type": "Person", "name": post.author.display_name or post.author.username},
            "description": summary[:160],
        } if indexable else None),
    )
    return _render(request, "post.html", {"post": post_data, "comments": comments, "not_indexable": not indexable},
                   seo, current_user)


def _plain_summary(text: str) -> str:
    import re

    return re.sub(r"\s+", " ", text).strip()


@router.get("/groups/{slug}")
def group_page_detail(slug: str, request: Request, db: Session = Depends(get_db),
                      current_user: User | None = Depends(get_optional_user)):
    g = db.execute(select(Group).where(Group.slug == slug)).scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    indexable = g.visibility == "public" and not g.is_archived
    visible = can_view_group(g, current_user, db)
    if not visible:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    seo = _seo_context(f"{g.name} | NEXA", description=(g.description or "")[:160], canonical=_site() + f"/groups/{g.slug}",
                       indexable=indexable, image=media_url(g.image_key))
    from app.deps import is_group_member

    ctx = {"space": {"slug": g.slug, "name": g.name, "description": g.description,
                     "image": media_url(g.image_key), "member_count": g.member_count,
                     "is_member": bool(current_user and is_group_member(db, g.id, current_user.id))},
           "kind": "group", "not_indexable": not indexable, "url_api": f"/api/groups/{g.slug}"}
    posts = db.execute(
        select(Post).where(Post.group_id == g.id, Post.visibility == "public", Post.status == "published")
        .order_by(Post.created_at.desc()).limit(20)
    ).scalars().all()
    ctx["posts"] = _serialize(db, list(posts), current_user.id if current_user else None)
    return _render(request, "space.html", ctx, seo, current_user)


@router.get("/circles/{slug}")
def circle_page_detail(slug: str, request: Request, db: Session = Depends(get_db),
                       current_user: User | None = Depends(get_optional_user)):
    c = db.execute(select(Circle).where(Circle.slug == slug)).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Círculo não encontrado")
    indexable = c.visibility == "public" and not c.is_archived
    visible = can_view_circle(c, current_user, db)
    if not visible:
        raise HTTPException(status_code=404, detail="Círculo não encontrado")
    seo = _seo_context(f"{c.name} | NEXA", description=(c.description or "")[:160], canonical=_site() + f"/circles/{c.slug}",
                       indexable=indexable, image=media_url(c.image_key))
    from app.deps import is_circle_member

    ctx = {"space": {"slug": c.slug, "name": c.name, "description": c.description,
                     "image": media_url(c.image_key), "member_count": c.member_count,
                     "is_member": bool(current_user and is_circle_member(db, c.id, current_user.id))},
           "kind": "circle", "not_indexable": not indexable, "url_api": f"/api/circles/{c.slug}"}
    posts = db.execute(
        select(Post).where(Post.circle_id == c.id, Post.visibility == "public", Post.status == "published")
        .order_by(Post.created_at.desc()).limit(20)
    ).scalars().all()
    ctx["posts"] = _serialize(db, list(posts), current_user.id if current_user else None)
    return _render(request, "space.html", ctx, seo, current_user)


@router.get("/events/{slug}")
def event_page_detail(slug: str, request: Request, db: Session = Depends(get_db),
                      current_user: User | None = Depends(get_optional_user)):
    e = db.execute(select(Event).where(Event.slug == slug)).scalar_one_or_none()
    if e is None:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    indexable = e.visibility == "public" and e.status != "cancelled"
    visible = can_view_event(e, current_user, db)
    if not visible:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    seo = _seo_context(
        f"{e.name} | NEXA", description=(e.description or "")[:160],
        canonical=_site() + f"/events/{e.slug}", indexable=indexable, image=media_url(e.image_key), type_="event",
        json_ld=({
            "@context": "https://schema.org", "@type": "Event",
            "name": e.name, "description": (e.description or "")[:200],
            "startDate": e.begins_at.isoformat() if e.begins_at else None,
            "location": {"@type": "Place", "name": e.location or "Online"},
        } if indexable else None),
    )
    ctx = {"event": {"slug": e.slug, "name": e.name, "description": e.description, "location": e.location,
                     "image": media_url(e.image_key), "begins_at": e.begins_at.isoformat() if e.begins_at else None,
                     "participant_count": e.participant_count},
           "not_indexable": not indexable, "url_api": f"/api/events/{e.slug}"}
    return _render(request, "event.html", ctx, seo, current_user)


# ------------------------------------------------------------------ auth
@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    if current_user:
        from fastapi.responses import RedirectResponse

        return RedirectResponse("/app", status_code=302)
    return _render(request, "login.html", {}, _seo_context("Entrar | NEXA", indexable=False, canonical=_site() + "/login"),
                   None)


@router.get("/register")
def register_page(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    if current_user:
        from fastapi.responses import RedirectResponse

        return RedirectResponse("/app", status_code=302)
    return _render(request, "register.html", {}, _seo_context("Criar conta | NEXA", indexable=False, canonical=_site() + "/register"),
                   None)


# ------------------------------------------------------------------ aplicação
def _require_user(current_user: User | None):
    if current_user is None:
        from fastapi.responses import RedirectResponse

        return RedirectResponse("/login", status_code=302)
    return current_user


def _redirect_or_user(current_user: User | None):
    user = _require_user(current_user)
    if isinstance(user, User):
        return user
    return user  # RedirectResponse


@router.get("/app")
def app_home(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    user = _redirect_or_user(current_user)
    if not isinstance(user, User):
        return user
    from app.models import Follow

    followed = {r[0] for r in db.execute(select(Follow.following_id).where(Follow.follower_id == user.id)).all()} | {user.id}
    posts = db.execute(
        select(Post).where(Post.author_id.in_(followed), Post.visibility.in_(("public", "friends")),
                           Post.status == "published").order_by(Post.created_at.desc()).limit(30)
    ).scalars().all()
    from app.models import Story

    now = utcnow()
    stories_rows = db.execute(
        select(Story).where(Story.owner_id.in_(followed), Story.expires_at > now).order_by(Story.created_at.desc()).limit(50)
    ).scalars().all()
    stories = []
    for s in stories_rows:
        owner = db.get(User, s.owner_id)
        from app.routers.stories import _s_dict

        stories.append(_s_dict(db, s))
        # marca nome do autor p/ exibição
    ctx = {
        "feed": _serialize(db, list(posts), user.id),
        "stories": stories,
        "app": _app_context(request, user, db),
    }
    return _render(request, "app_home.html", ctx, _seo_context("Início | NEXA", indexable=False), user)


@router.get("/app/messages")
def app_messages(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    user = _redirect_or_user(current_user)
    if not isinstance(user, User):
        return user
    ctx = {"app": _app_context(request, user, db)}
    return _render(request, "app_messages.html", ctx, _seo_context("Mensagens | NEXA", indexable=False), user)


@router.get("/app/notifications")
def app_notifications(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    user = _redirect_or_user(current_user)
    if not isinstance(user, User):
        return user
    from app.models import Notification

    rows = db.execute(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(60)
    ).scalars().all()
    ctx = {"app": _app_context(request, user, db), "items": [
        {"id": n.id, "type": n.type_, "message": n.message, "read": n.read_at is not None,
         "created_at": n.created_at.isoformat() if n.created_at else None} for n in rows]}
    return _render(request, "app_notifications.html", ctx, _seo_context("Notificações | NEXA", indexable=False), user)


@router.get("/app/search")
def app_search(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    user = _redirect_or_user(current_user)
    if not isinstance(user, User):
        return user
    ctx = {"app": _app_context(request, user, db)}
    return _render(request, "app_search.html", ctx, _seo_context("Buscar | NEXA", indexable=False), user)


@router.get("/app/settings")
def app_settings(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    user = _redirect_or_user(current_user)
    if not isinstance(user, User):
        return user
    ctx = {"app": _app_context(request, user, db)}
    return _render(request, "app_settings.html", ctx, _seo_context("Configurações | NEXA", indexable=False), user)


@router.get("/app/me")
def app_me(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    user = _redirect_or_user(current_user)
    if not isinstance(user, User):
        return user
    posts = db.execute(
        select(Post).where(Post.author_id == user.id, Post.status == "published").order_by(Post.created_at.desc()).limit(30)
    ).scalars().all()
    ctx = {"app": _app_context(request, user, db), "feed": _serialize(db, list(posts), user.id)}
    return _render(request, "app_me.html", ctx, _seo_context("Meu perfil | NEXA", indexable=False), user)


@router.get("/app/create-group")
def app_create_group(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    user = _redirect_or_user(current_user)
    if not isinstance(user, User):
        return user
    return _render(request, "app_create_group.html", {"app": _app_context(request, user, db)},
                   _seo_context("Criar grupo | NEXA", indexable=False), user)


@router.get("/app/create-circle")
def app_create_circle(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    user = _redirect_or_user(current_user)
    if not isinstance(user, User):
        return user
    return _render(request, "app_create_circle.html", {"app": _app_context(request, user, db)},
                   _seo_context("Criar círculo | NEXA", indexable=False), user)


@router.get("/app/create-event")
def app_create_event(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    user = _redirect_or_user(current_user)
    if not isinstance(user, User):
        return user
    return _render(request, "app_create_event.html", {"app": _app_context(request, user, db)},
                   _seo_context("Criar evento | NEXA", indexable=False), user)


@router.get("/app/story")
def app_story(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    user = _redirect_or_user(current_user)
    if not isinstance(user, User):
        return user
    return _render(request, "app_story.html", {"app": _app_context(request, user, db)},
                   _seo_context("Stories | NEXA", indexable=False), user)


@router.get("/healthz")
def healthz(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}


# ------------------------------------------------------------------ SEO / infra
@router.get("/robots.txt")
def robots(request: Request):
    from fastapi.responses import PlainTextResponse

    site = _site()
    settings = get_settings()
    if settings.env in ("staging", "production"):
        body = (
            f"User-agent: *\n"
            f"Allow: /\n"
            f"Disallow: /app/\n"
            f"Disallow: /login\n"
            f"Disallow: /register\n"
            f"Disallow: /api/\n"
            f"Disallow: /media/\n"
            f"Sitemap: {site}/sitemap.xml\n"
        )
    else:
        body = "User-agent: *\nDisallow: /\n"
    return PlainTextResponse(body, media_type="text/plain")


@router.get("/manifest.webmanifest")
def manifest():
    from fastapi.responses import JSONResponse

    settings = get_settings()
    site = _site()
    return JSONResponse({
        "name": "NEXA",
        "short_name": "NEXA",
        "description": "Rede social multiplataforma",
        "start_url": "/app",
        "scope": "/",
        "display": "standalone",
        "background_color": "#0f1117",
        "theme_color": "#0f1117",
        "lang": "pt-BR",
        "orientation": "any",
        "categories": ["social"],
        "icons": [
            {"src": f"{site}/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": f"{site}/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    })


@router.get("/sw.js")
def service_worker():
    from fastapi.responses import Response

    Path = __import__("pathlib").Path
    path = Path(__file__).resolve().parent.parent.parent / "static" / "sw.js"
    return Response(
        path.read_bytes(),
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@router.get("/favicon.ico")
def favicon():
    from fastapi.responses import RedirectResponse

    return RedirectResponse("/static/icons/icon-512.png")


@router.get("/static/manifest.webmanifest")
def static_manifest_redirect():
    from fastapi.responses import RedirectResponse

    return RedirectResponse("/manifest.webmanifest")


__all__ = ["router", "_render", "_seo_context"]