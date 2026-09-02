#!/usr/bin/env bash
# ===== NEXA — arranque local/despliegue =====
# Uso:
#   ./run.sh            arranque en desarrollo (uvicorn, recarga, :8000)
#   ./run.sh migrate    aplica migraciones Alembic (útil antes de arrancar)
#   ./run.sh test       ejecuta la suite de pruebas
#   PORT=9000 ./run.sh  cambia el puerto
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

export PYTHONPATH="$DIR/backend"
export NEXA_ENV="${NEXA_ENV:-development}"
export PORT="${PORT:-8000}"

PY="$DIR/backend/.venv/bin/python"
[ -x "$PY" ] || PY=python3

# Carga DATABASE_URL / SECRET_KEY desde .env si existe
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

case "${1:-up}" in
  migrate)
    cd "$DIR/backend"
    "$PY" -m alembic upgrade head
    ;;
  test)
    cd "$DIR/backend"
    "$PY" -m pytest tests -q --no-header
    ;;
  *)
    "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload
    ;;
esac