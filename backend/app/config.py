"""Configuração por ambiente do NEXA.

Toda a configuração vem de variáveis de ambiente — nunca colocar secrets no código.
Ambientes: development | staging | production (NEXA_ENV).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: _env("NEXA_ENV", "development"))
    app_name: str = "NEXA"
    api_version: str = "v1"

    # URLs públicas (domínio configurável por ambiente — não assumir registro)
    site_url: str = field(default_factory=lambda: _env("SITE_URL", "http://localhost:8000"))
    www_host: str = field(default_factory=lambda: _env("WWW_HOST", "localhost"))  # ex.: www.nexa.com
    api_host: str = field(default_factory=lambda: _env("API_HOST", "localhost"))  # ex.: api.nexa.com

    # Segurança / auth
    secret_key: str = field(default_factory=lambda: _env("SECRET_KEY", ""))
    jwt_access_minutes: int = field(default_factory=lambda: int(_env("JWT_ACCESS_MINUTES", "30")))
    jwt_refresh_days: int = field(default_factory=lambda: int(_env("JWT_REFRESH_DAYS", "30")))

    # Banco de dados (default: SQLite local p/ desenvolvimento)
    database_url: str = field(default_factory=lambda: _env(
        "DATABASE_URL", f"sqlite:///{_BACKEND_DIR / 'nexa-dev.db'}"))

    # Redis (opcional). Sem REDIS_URL usa cache em memória (apenas 1 instância / dev).
    redis_url: str = field(default_factory=lambda: _env("REDIS_URL", ""))

    # Object storage: local (default) | s3 (requer boto3 + credenciais S3)
    storage_driver: str = field(default_factory=lambda: _env("STORAGE_DRIVER", "local"))
    storage_local_dir: Path = field(default_factory=lambda: Path(
        _env("STORAGE_LOCAL_DIR", str(_BACKEND_DIR / "data" / "uploads"))))
    s3_bucket: str = field(default_factory=lambda: _env("S3_BUCKET", ""))
    s3_region: str = field(default_factory=lambda: _env("S3_REGION", "us-east-1"))
    s3_endpoint: str = field(default_factory=lambda: _env("S3_ENDPOINT", ""))
    s3_public_base: str = field(default_factory=lambda: _env("S3_PUBLIC_BASE", ""))
    # Chaves S3 NUNCA no código — leitura via env (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)

    # Uploads
    max_upload_mb: int = field(default_factory=lambda: int(_env("MAX_UPLOAD_MB", "25")))

    # Registro aberto (fechar em produção p/ convites se desejado)
    allow_registration: bool = field(default_factory=lambda: _env("ALLOW_REGISTRATION", "true").lower() == "true")

    # CDN pública opcional (sirve assets /media via CDN quando configurada)
    media_cdn_base: str = field(default_factory=lambda: _env("MEDIA_CDN_BASE", ""))

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_dev(self) -> bool:
        return self.env == "development"

    def validate(self) -> None:
        if self.env in ("staging", "production") and not self.secret_key:
            raise RuntimeError("SECRET_KEY é obrigatória em staging/production")


def get_settings() -> Settings:
    return Settings()