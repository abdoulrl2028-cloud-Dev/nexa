"""Object storage para mídia (imagens, vídeos, avatares, capas, stories, anexos).

- `local`: filesystem (desenvolvimento / single-node). Nunca é onde ficam os
  dados definitivos em produção.
- `s3`: qualquer object storage S3-compatível (AWS S3, MinIO, R2, Backblaze…).
  Requer boto3 instalado e credenciais via ambiente (AWS_ACCESS_KEY_ID,
  AWS_SECRET_ACCESS_KEY). NUNCA colocar credenciais no código.

O banco (PostgreSQL) guarda apenas metadados (chave do objeto, tipo, tamanho).
"""
from __future__ import annotations

import datetime as dt
import mimetypes
import os
import re
import urllib.parse
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import get_settings


class StorageBackend(ABC):
    driver: str = "abstract"

    @abstractmethod
    def save_bytes(self, data: bytes, key: str, content_type: str) -> None: ...

    @abstractmethod
    def read_bytes(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def public_url(self, key: str, base: str) -> str: ...


class LocalStorage(StorageBackend):
    driver = "local"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # chaves internas geradas por nós: sem traversal
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("key inválida")
        return path

    def save_bytes(self, data: bytes, key: str, content_type: str = "") -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def public_url(self, key: str, base: str) -> str:
        return f"{base}/media/{urllib.parse.quote(key)}"


class S3Storage(StorageBackend):
    """S3-compatível (requer boto3). O `public_url` usa S3_PUBLIC_BASE quando
    houver CDN pública; caso contrário a API redireciona para o próprio S3."""

    driver = "s3"

    def __init__(self) -> None:
        try:
            import boto3  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "STORAGE_DRIVER=s3 exige `pip install boto3` e credenciais AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY"
            ) from exc
        settings = get_settings()
        kwargs = {"region_name": settings.s3_region}
        if settings.s3_endpoint:
            kwargs["endpoint_url"] = settings.s3_endpoint
        self.client = boto3.client("s3", **kwargs)
        self.bucket = settings.s3_bucket
        if not self.bucket:
            raise RuntimeError("S3_BUCKET é obrigatório com STORAGE_DRIVER=s3")
        self._public_base = settings.s3_public_base or ""

    def _obj(self, key: str) -> str:
        if key.startswith(self.bucket + "/"):
            return key.split("/", 1)[1]
        return key

    def save_bytes(self, data: bytes, key: str, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=self._obj(key), Body=data, ContentType=content_type or "application/octet-stream"
        )

    def read_bytes(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=self._obj(key))
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._obj(key))
            return True
        except Exception:  # noqa: BLE001
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._obj(key))

    def public_url(self, key: str, base: str) -> str:
        if self._public_base:
            return f"{self._public_base.rstrip('/')}/{urllib.parse.quote(self._obj(key))}"
        return f"{base}/media/{urllib.parse.quote(self._obj(key))}"


def _storage() -> StorageBackend:
    settings = get_settings()
    if settings.storage_driver == "s3":
        return S3Storage()
    return LocalStorage(settings.storage_local_dir)


def new_key(kind: str, original_filename: str = "") -> str:
    ext = os.path.splitext(original_filename or "")[1].lower()
    ext = re.sub(r"[^a-zA-Z0-9.]", "", ext)[:10]
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm", ".mov", ".mp3", ".wav", ".pdf", ".zip"}:
        ext = ""
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y/%m")
    return f"{kind}/{today}/{uuid.uuid4().hex}{ext}"


def guess_content_type(key: str, fallback: str = "application/octet-stream") -> str:
    return mimetypes.guess_type(key)[0] or fallback


def media_url(key: str | None) -> str | None:
    """URL pública (CDN ou própria API) para uma chave de mídia."""
    if not key:
        return None
    settings = get_settings()
    base = settings.media_cdn_base or settings.site_url
    return _storage().public_url(key, base)


__all__ = [
    "StorageBackend",
    "LocalStorage",
    "S3Storage",
    "_storage",
    "new_key",
    "guess_content_type",
    "media_url",
]