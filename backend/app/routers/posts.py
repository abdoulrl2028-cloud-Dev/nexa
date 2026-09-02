"""Posts: criação, leitura pública/privada, likes, comentários, denúncias."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import can_view_post, get_current_user, get_optional_user
from app.models import (
    Comment,
    Group,
    Circle,
    Event,
    Like,
    Media,
    Post,
    PostMedia,
    PostVisibility,
    Report,
    User,
    unique_slug,
    utcnow,
)
from app.notifier import notify
from app.routers.users import get_media_base
from app.schemas import CommentIn, PostIn, ReportIn
from app.storage import media_url

router = APIRouter(prefix="/api/posts", tags=["posts"])


def _taken_slugs(db: Session) -> set[str]:
    return set(db.execute(select(Post.slug)).scalars().all())


def _serialize(db: Session, posts: list[Post], me: int | None) -> list[dict]:
    result = []
    for p in posts:
        data = p.to_dict(get_media_base(db))
        data["author"]["avatar"] = media_url(p.author.avatar_key)
        post_media = db.execute(
            select(Media).join(PostMedia, PostMedia.media_id == Media.id)
            .where(PostMedia.post_id == p.id).order_by(PostMedia.position)
        ).scalars().all()
        data["media"] = [m.to_dict(get_media_base(db)) for m in post_media]
        if me:
            data["liked"] = bool(
                db.execute(select(Like.id).where(Like.post_id == p.id, Like.user_id == me)).first()
            )
        else:
            data["liked"] = False
        result.append(data)
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_post(payload: PostIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    taken = _taken_slugs(db)
    slug = unique_slug(payload.title or payload.content[:60], taken)
    post = Post(
        author_id=user.id,
        title=payload.title,
        slug=slug,
        content=payload.content,
        visibility=payload.visibility,
    )
    db.add(post)
    db.flush()
    if payload.media_keys:
        owned = set(db.execute(select(Media.key).where(Media.owner_id == user.id)).scalars())
        for i, key in enumerate(payload.media_keys):
            if key not in owned:
                raise HTTPException(status_code=400, detail=f"Mídia {key} não pertence ao usuário")
            media = (db.execute(select(Media).where(Media.key == key)).scalar_one())
            db.add(PostMedia(post_id=post.id, media_id=media.id, position=i))
    db.commit()
    db.refresh(post)
    return _serialize(db, [post], user.id)[0]


@router.get("/{slug}")
def get_post(slug: str, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    post = db.execute(select(Post).where(Post.slug == slug)).scalar_one_or_none()
    if post is None or not can_view_post(post, user, db):
        raise HTTPException(status_code=404, detail="Post não encontrado")
    return {"post": _serialize(db, [post], user.id if user else None)[0], "public": post.visibility == "public"}


@router.patch("/{slug}")
def update_post(slug: str, payload: PostIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.execute(select(Post).where(Post.slug == slug)).scalar_one_or_none()
    if post is None or post.status != "published":
        raise HTTPException(status_code=404, detail="Post não encontrado")
    if post.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Sem permissão")
    post.title = payload.title
    post.content = payload.content
    post.visibility = payload.visibility
    post.updated_at = utcnow()
    if payload.media_keys:
        db.execute(PostMedia.__table__.delete().where(PostMedia.post_id == post.id))
        owned = set(db.execute(select(Media.key).where(Media.owner_id == user.id)).scalars())
        for i, key in enumerate(payload.media_keys):
            if key not in owned:
                raise HTTPException(status_code=400, detail=f"Mídia {key} não pertence ao usuário")
            media = db.execute(select(Media).where(Media.key == key)).scalar_one()
            db.add(PostMedia(post_id=post.id, media_id=media.id, position=i))
    db.commit()
    db.refresh(post)
    return _serialize(db, [post], user.id)[0]


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.execute(select(Post).where(Post.slug == slug)).scalar_one_or_none()
    if post is None or post.status != "published":
        raise HTTPException(status_code=404, detail="Post não encontrado")
    if post.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Sem permissão")
    db.delete(post)
    db.commit()


@router.post("/{slug}/like")
def like_post(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.execute(select(Post).where(Post.slug == slug)).scalar_one_or_none()
    if post is None or not can_view_post(post, user, db):
        raise HTTPException(status_code=404, detail="Post não encontrado")
    if not db.execute(select(Like.id).where(Like.post_id == post.id, Like.user_id == user.id)).first():
        db.add(Like(user_id=user.id, post_id=post.id))
        post.like_count += 1
        db.flush()
        notify(
            db, post.author_id, user.id, "like",
            f"{user.display_name or user.username} curtiu seu post",
            entity_type="post", entity_id=post.slug,
        )
        db.commit()
    return {"liked": True, "like_count": post.like_count}


@router.delete("/{slug}/like")
def unlike_post(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.execute(select(Post).where(Post.slug == slug)).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post não encontrado")
    row = db.execute(select(Like.id).where(Like.post_id == post.id, Like.user_id == user.id)).scalar_one_or_none()
    if row:
        db.execute(Like.__table__.delete().where(Like.id == row))
        post.like_count = max(0, post.like_count - 1)
        db.commit()
    return {"liked": False, "like_count": post.like_count}


@router.get("/{slug}/comments")
def list_comments(slug: str, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    post = db.execute(select(Post).where(Post.slug == slug)).scalar_one_or_none()
    if post is None or not can_view_post(post, user, db):
        raise HTTPException(status_code=404, detail="Post não encontrado")
    comments = db.execute(
        select(Comment).where(Comment.post_id == post.id, Comment.is_deleted.is_(False))
        .order_by(Comment.created_at.asc()).limit(200)
    ).scalars()
    return [
        {
            "id": c.id,
            "post_id": c.post_id,
            "author": {
                "username": c.author.username,
                "display_name": c.author.display_name or c.author.username,
                "avatar": c.author.avatar_key,
            },
            "content": c.content,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comments
    ]


@router.post("/{slug}/comments", status_code=status.HTTP_201_CREATED)
def create_comment(slug: str, payload: CommentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.execute(select(Post).where(Post.slug == slug)).scalar_one_or_none()
    if post is None or not can_view_post(post, user, db):
        raise HTTPException(status_code=404, detail="Post não encontrado")
    c = Comment(post_id=post.id, author_id=user.id, content=payload.content.strip())
    post.comment_count += 1
    db.add(c)
    db.flush()
    notify(
        db, post.author_id, user.id, "comment",
        f"{user.display_name or user.username} comentou em seu post",
        entity_type="post", entity_id=post.slug,
    )
    db.commit()
    db.refresh(c)
    return {
        "id": c.id,
        "post_id": c.post_id,
        "content": c.content,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.delete("/{slug}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(slug: str, comment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comentário não encontrado")
    if comment.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Sem permissão")
    comment.is_deleted = True
    post = db.get(Post, comment.post_id)
    if post:
        post.comment_count = max(0, post.comment_count - 1)
    db.commit()


@router.post("/{slug}/report", status_code=status.HTTP_201_CREATED)
def report_post(slug: str, payload: ReportIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.execute(select(Post).where(Post.slug == slug)).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post não encontrado")
    post.report_count += 1
    db.add(Report(reporter_id=user.id, target_type="post", target_id=post.id, reason=payload.reason))
    if post.report_count >= 5:
        post.status = "removed"  # política: removido da indexação e do site
    db.commit()
    return {"reported": True}


__all__ = ["router", "_serialize"]