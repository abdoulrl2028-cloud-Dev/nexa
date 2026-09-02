"""Upload de mídia: imagens, vídeos, áudios e anexos.

Fluxo: App → API → Object Storage (local em dev, S3 em produção). O banco guarda
apenas metadados. Vídeos grandes nunca vão para o PostgreSQL.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Media, User
from app.storage import _storage, guess_content_type, media_url, new_key

router = APIRouter()

ALLOWED_KINDS: dict[str, set[str]] = {
    "image": {"image/jpeg", "image/png", "image/gif", "image/webp", "image/avif"},
    "video": {"video/mp4", "video/webm", "video/quicktime"},
    "audio": {"audio/mpeg", "audio/wav", "audio/ogg"},
    "file": {"application/pdf", "application/zip", "text/plain", "application/json"},
}

SAFE_KEY = re.compile(r"^[a-zA-Z0-9._/-]+$")


@router.post("/api/upload", status_code=status.HTTP_201_CREATED)
async def upload_media(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    settings = get_settings()
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Arquivo vazio")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Limite de {settings.max_upload_mb}MB excedido")

    mime = (file.content_type or guess_content_type(file.filename or "")).lower()
    kind = next((k for k, v in ALLOWED_KINDS.items() if mime in v), None)
    if kind is None:
        raise HTTPException(status_code=415, detail=f"Tipo não suportado: {mime}")

    key = new_key(kind, file.filename or "")
    _storage().save_bytes(data, key, mime)
    media = Media(owner_id=user.id, kind=kind, mime=mime, size=len(data), key=key)
    db.add(media)
    db.commit()
    db.refresh(media)
    return media.to_dict(settings.site_url)


@router.get("/media/{key:path}")
def get_media(key: str):
    if not SAFE_KEY.match(key):
        raise HTTPException(status_code=400, detail="Chave inválida")
    settings = get_settings()
    store = _storage()
    if store.driver == "local":
        path = settings.storage_local_dir / key
        if not path.exists():
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        return FileResponse(path, media_type=guess_content_type(key))
    # S3: URL pública ou redirecionamento
    url = store.public_url(key, settings.site_url)
    if store and store.driver == "s3" and not settings.s3_public_base:
        from botocore.exceptions import ClientError  # type: ignore[import-not-found]

        try:
            presigned = store.client.generate_presigned_url(
                "get_object", Params={"Bucket": store.bucket, "Key": store._obj(key)}, ExpiresIn=3600
            )
            return RedirectResponse(presigned)
        except ClientError:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado") from None
    return RedirectResponse(url)


__all__ = ["router", "media_url"]