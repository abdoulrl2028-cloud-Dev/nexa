# ===== NEXA — imagem da API (multi-estágio) =====
# Prod run: app roda com HOST 0.0.0.0; o CMD aplica migrações Alembic e arranca uvicorn.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/nexa

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Dependências em camada própria (cache de build)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --upgrade pip && pip install -r backend/requirements.txt \
    && pip install "psycopg[binary]>=3.2.0" redis>=5.0.0 boto3>=1.34.0

# Código + migrações
COPY backend ./backend
COPY deploy/run.sh ./run.sh
RUN chmod +x ./run.sh

EXPOSE 8000

CMD ["./run.sh"]