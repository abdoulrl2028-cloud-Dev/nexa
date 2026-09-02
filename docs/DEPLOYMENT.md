# Deployment do NEXA

Como fazer deploy do NEXA nos ambientes: development, staging e production,
incluindo o pipeline de CI/CD.

## Ambientes

| Env | `NEXA_ENV` | Uso | Regras |
|-----|-----------|-----|--------|
| development | `development` | dev local | SQLite, sem `SECRET_KEY`, `robots: Disallow /` |
| staging | `staging` | pré-prod | exige `SECRET_KEY`, DB/Redis de staging |
| production | `production` | público | exige `SECRET_KEY`, hardening total |

## Local (development)

```bash
cp .env.example .env        # ajuste se preciso
./run.sh migrate            # aplica migrações (opcional; init_db cria em dev)
./run.sh                    # uvicorn :8000 com reload
```

Testes:

```bash
./run.sh test
```

## Via Docker / docker-compose

Na pasta `deploy/`:

```bash
cd deploy
SECRET_KEY=<forte> docker compose up --build
```

O compose sobe `db` (PostgreSQL 16), `redis` (7) e `api` (do `Dockerfile`),
aplicando migrações e expondo a API na porta configurada.

## Produção com proxy

- Use `deploy/Caddyfile` para TLS automático + headers de segurança + cache de
  estáticos.
- Aponte o domínio para a instância.
- Configure `.env` de produção (ver `docs/CLOUD.md`).

## CI/CD (GitHub Actions)

Pipeline em `../.github/workflows/ci.yml`:

```
push -> test -> build -> security -> [staging -> approve -> production]
```

- **test**: instala deps e roda `pytest tests` (29 testes).
- **lint**: Ruff (se configurado).
- **build**: Docker Buildx (com cache GHA) — garante imagem monta.
- **security**: TruffleHog — detecta secrets vazados no repo.
- **deploy-staging**: roda ao push em `staging`.
- **approve-prod**: gate manual (environment)
- **deploy-prod**: roda após aprovação.

## Migrações

Gerenciadas por Alembic (`backend/alembic/`).

```bash
./run.sh migrate                 # aplica `upgrade head`
./run.sh migrate -- --revision   # avançar/voltar versões específicas
```

Nova migração (desenvolvedores):

```bash
cd backend
.venv/bin/python -m alembic revision --autogenerate -m "descrição"
```

Sempre rode `./run.sh migrate` + `./run.sh test` antes de subir staging/prod.

## Rollback

Migrações têm `downgrade`. Após um deploy ruim:

1. `./run.sh migrate -- --downgrade -1` (ou a revisão alvo).
2. Restaure a versão anterior da imagem.
3. Verifique health-checks.

## Índice de arquivos

- `../deploy/Dockerfile`, `run.sh`, `docker-compose.yml`, `Caddyfile`
- `../.github/workflows/ci.yml`
- `../run.sh` (arranque/migração/teste no host)
- `backend/alembic.ini` e `backend/alembic/`
