#!/usr/bin/env sh
set -e
cd /srv/nexa/backend
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"