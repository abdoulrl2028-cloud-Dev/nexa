# Cloud / Deploy no provedor de nuvem

Guia de implantação do NEXA em nuvem. O objetivo é uma instância resiliente e
escalável com banco gerenciado, cache e storage, servida por HTTPS com Caddy.

## Pré-requisitos

- Conta no provedor (AWS, GCP, Azure, DigitalOcean, Fly.io, Railway…).
- Docker (ou uso do `deploy/docker-compose.yml`).
- Chave `SECRET_KEY` (`openssl rand -hex 32`).
- Domínio configurado (ex.: `nexa.example.com`), apontando para a máquina/IP.

## Topologia recomendada (prod)

```
Internet ──► Caddy (443, TLS auto) ──► API (FastAPI, replicas)
                                          │
                     ┌────────────────────┼──────────────────┐
                     ▼                    ▼                  ▼
               PostgreSQL          Redis (cache/         Object storage
               (managed,           rate-limit,           (S3-compatível,
                HA)                sessões)              uploads)
```

## Passos

### 1. Provisionar a infraestrutura

- **DB**: PostgreSQL gerenciado (RDS, Cloud SQL, Supabase…). Guarde a URL.
- **Redis**: gerenciado (ElastiCache, Upstash, Redis Cloud…) ou o container do compose.
- **Storage**: bucket S3-compatível para uploads (ou volume local).
- **Compute**: uma VM/VPS ou um container runtime (Fly/Railway/Render).

### 2. Configurar o ambiente

Copie `../.env.example` para `.env` (ou set vars no painel/CI):

```env
NEXA_ENV=production
SITE_URL=https://nexa.example.com
WWW_HOST=nexa.example.com
API_HOST=api.nexa.example.com
SECRET_KEY=<forte>
DATABASE_URL=postgresql+psycopg://usuario:senha@host:5432/nexa
REDIS_URL=rediss://user:pass@host:6379/0
STORAGE_DRIVER=s3
S3_BUCKET=nexa-media
S3_REGION=us-east-1
```

Credenciais S3: `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (nunca no código).

### 3. Aplicar migrações

```bash
./run.sh migrate   # roda `alembic upgrade head`
```

Ou durante o boot do container (o `deploy/run.sh` já aplica migrações antes de
subir o uvicorn).

### 4. Rodar com Caddy

Use o `deploy/Caddyfile` (exemplos `www.nexa-example.com`). Caddy obtém TLS
automático via Let's Encrypt.

### 5. Escalar

- Suba réplicas do container da API atrás do Caddy (load balancer).
- Para 1+ réplica, **Redis é obrigatório** (cache/sessões/rate-limit são
  stateful). Sem Redis, só rode 1 instância.

## Plataformas específicas

- **Fly.io / Railway / Render** — definem `PORT`; use o `deploy/run.sh` que lê
  `$PORT`. Containerize com `deploy/Dockerfile`.
- **Kubernetes** — os mesmos containers; publique apenas o serviço da API, com
  `db`/`redis` como serviços internos (ou gerenciados fora do cluster).

## Verificação pós-deploy

- `curl -sI https://nexa.example.com/` → 200.
- `curl -s https://nexa.example.com/robots.txt` → regras de produção + Sitemap.
- Suba um usuário, crie post público → confira canonical/JSON-LD.
- Teste WebSocket realtime (mensagens) via uma sessão logada.

## Health-checks

`deploy/run.sh` usa `alembic upgrade head` antes de servir; o container falha
rápido se o banco estiver inacessível (bom para restart com backoff).
