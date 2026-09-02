"""Painel administrativo: moderação e saúde do sistema.

Protegido por muitas camadas: ⚠️ páginas de admin NUNCA são indexáveis (noindex).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Group, Post, Report, User, utcnow

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Somente administradores")


@router.get("/stats")
def stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(user)
    counts = {
        "users": db.execute(select(func.count(User.id))).scalar() or 0,
        "posts": db.execute(select(func.count(Post.id))).scalar() or 0,
        "reports_open": db.execute(select(func.count(Report.id)).where(Report.status == "open")).scalar() or 0,
        "groups": db.execute(select(func.count(Group.id)).where(Group.is_archived.is_(False))).scalar() or 0,
    }
    return counts


@router.get("/users")
def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(user)
    rows = db.execute(
        select(User).order_by(User.created_at.desc()).limit(200)
    ).scalars().all()
    return [{"id": u.id, "username": u.username, "display_name": u.display_name,
             "is_private": u.is_private, "is_active": u.is_active, "is_admin": u.is_admin,
             "created_at": u.created_at.isoformat() if u.created_at else None} for u in rows]


@router.get("/reports")
def list_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(user)
    rows = db.execute(select(Report).where(Report.status == "open").order_by(Report.created_at.desc()).limit(200)).scalars().all()
    return [{"id": r.id, "target_type": r.target_type, "target_id": r.target_id,
             "reason": r.reason, "reporter_id": r.reporter_id,
             "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]


@router.post("/posts/{post_id}/moderate")
def moderate_post(post_id: int, action: str = "remove", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(user)
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post não encontrado")
    if action == "remove":
        post.status = "removed"  # sai da indexação e do site
    elif action == "restore":
        post.status = "published"
    else:
        raise HTTPException(status_code=400, detail="Ação inválida")
    db.commit()
    return {"status": post.status}


@router.post("/groups/{group_id}/moderate")
def moderate_group(group_id: int, action: str = "archive", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(user)
    g = db.get(Group, group_id)
    if g is None:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    g.is_archived = (action == "archive")
    db.commit()
    return {"is_archived": g.is_archived}


@router.post("/reports/{report_id}/resolve")
def resolve_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(user)
    r = db.get(Report, report_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Denúncia não encontrada")
    r.status = "resolved"
    db.commit()
    return {"status": r.status}


__all__ = ["router"]