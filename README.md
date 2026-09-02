# NEXA

Rede social multiplataforma. Um único backend **FastAPI** serve a mesma base em
quatro superfícies: **Web/PWA**, **Android (TWA)**, **Desktop (Tauri)** e
**Tablet** — com SSR + SEO, API REST e WebSocket realtime de mensagens.

```
Browser / PWA ──► FastAPI (REST + SSR/SEO + WS) ◄── Desktop (Tauri)
Android TWA   ──►        │                         ▲
                     DB (SQLite/PostgreSQL)         ┆  mesmo código
                     Redis (opcional)               ┘
```

## Sobre

- **Backend**: Python 3 + FastAPI + SQLAlchemy 2.0 + Jinja2 (SSR).
- **Frontend**: JS/CSS vanilla, PWA instalável (manifest + service worker + ícones).
- **Auth**: PBKDF2-HMAC-SHA256, JWT HS256, cookie httpOnly + Bearer.
- **Recursos**: posts (public/private/friends), feed com cursor, follow, grupos,
  círculos, eventos, stories, mensagens diretas com WebSocket realtime,
  notificações, pesquisa, uploads, admin e reports (5 → remoção).
- **Testes**: suíte pytest (`backend/tests/`, 29 testes) rodada no CI.

## Estrutura

```
nexa/
├── backend/
│   ├── app/            # FastAPI: routers/, pages/ (SSR+SEO), modelos, deps
│   ├── templates/      # Jinja2 (público + área logada)
│   ├── static/         # CSS, JS, sw.js, manifest, ícones
│   ├── alembic/        # migrações de banco
│   ├── tests/          # suíte pytest (29 testes)
│   └── requirements.txt
├── desktop/            # wrapper Tauri v2 (scaffold — requer Rust)
├── deploy/             # Dockerfile, docker-compose, Caddyfile, run.sh
├── docs/               # 10 documentos (arquitetura, segurança, SEO, cloud…)
├── .github/workflows/  # CI/CD (test → build → security → staging → prod)
├── .env.example
└── run.sh              # arranque/migração/teste
```

## Pré-requisitos

- Python 3.12+ (recomendado 3.12/3.14).
- (Opcional) Redis para cache/rate-limit; (opcional) PostgreSQL para produção.

## Início rápido

```bash
cd nexa
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt

cp .env.example .env     # ajuste SECRET_KEY etc. se preciso

./run.sh migrate         # aplica migrações Alembic
./run.sh                 # uvicorn em http://localhost:8000  (reload)

# em outro terminal:
./run.sh test            # pytest (30 testes)
```

Abra `http://localhost:8000`: registre-se e use como app.

## Uso de `run.sh`

| Comando | Efeito |
|---|---|
| `./run.sh` | sobe uvicorn :8000 (recarga) |
| `./run.sh migrate` | `alembic upgrade head` |
| `./run.sh test` | roda a suíte pytest |
| `PORT=9000 ./run.sh` | muda a porta |

Variáveis: `NEXA_ENV`, `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `STORAGE_DRIVER`
(ver `.env.example`).

## Cybersecurity — comandos de segurança

Escaneie o app localmente antes de publicar. Rode da raiz do projeto.

| Ferramenta | O que detecta | Comando |
|---|---|---|
| **TruffleHog** | secrets em todo o histórico git (tokens, chaves) | `docker run --rm -v "$PWD:/pwd" ghcr.io/trufflesecurity/trufflehog:latest git file:///pwd --only-verified` |
| **Gitleaks** | segredos/info expostos no repo | `docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8 detect --source=/repo --verbose` |
| **Bandit** | vulnerabilidades estáticas em Python | `cd backend && .venv/bin/pip install bandit && .venv/bin/bandit -r app/` |
| **pip-audit** | dependências Python com CVEs | `cd backend && .venv/bin/pip install pip-audit && .venv/bin/pip-audit -r requirements.txt` |
| **Ruff** | lint + suspeitas (incl. import deadlock) | `cd backend && .venv/bin/pip install ruff && .venv/bin/ruff check app/` |
| **Semgrep** | padrões de vulnerabilidade (auto) | `docker run --rm -v "$PWD:/src" returntocorp/semgrep semgrep scan --config=auto /src/backend/app` |
| **Trivy (imagem)** | CVEs na imagem Docker | `docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --severity HIGH,CRITICAL <imagem>` |
| **Headers HTTP** | verifica hardening em produção | `curl -sI https://SEU-DOMINIO/ \| grep -iE "x-content-type|x-frame|content-security|referrer"` |

Sequência mínima antes de cada release:

```bash
gitleaks detect --source=. --verbose
bandit -r backend/app -q
pip-audit -r backend/requirements.txt
pytest -q        # via ./run.sh test
```

O CI (`.github/workflows/ci.yml`) já roda **TruffleHog** em todo push. Em `docs/SECURITY.md`
estão o modelo de ameaças, PBKDF2/JWT, visibilidade de posts, rate limit e runbooks.

## Deploy automático no Vercel

O `backend/` já contém integração com Vercel: `vercel.json` + `api/index.py`
(função serverless ASGI do FastAPI). Com a raiz do deploy apontando para
`backend`, **cada push/PR publica automaticamente** (preview + produção).

1. **Suba o projeto ao GitHub** (ver “Publicar” abaixo).
2. No painel da Vercel: **Add New → Project → Import** do repositório do NEXA.
3. Em *Project Settings*: **Root Directory = `backend`**.
4. Adicione as variáveis de ambiente (Settings → Environment Variables):

   ```
   NEXA_ENV=production
   SECRET_KEY=<openssl rand -hex 32>
   DATABASE_URL=postgresql+psycopg://...@...:5432/nexa   # Neon / RDS / Aiven
   REDIS_URL=redis://...:6379/0                          # Upstash/Redis (opcional)
   STORAGE_DRIVER=s3
   S3_BUCKET=<bucket-s3>
   S3_REGION=us-east-1
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   ```
5. **Deploy**. A partir daqui, todo push na branch principal (ou PR) deploga
   automaticamente (preview para PRs).

> **Limitação**: o WebSocket realtime de mensagens (`/api/messages/ws`) **não**
> roda em funções serverless. No Vercel, REST + SSR + polling funcionam; para
> realtime use a implantação **AWS Fargate** (`terraform/`, com RDS+Redis+S3 e
> ALB) — ambos já prontos.

## Documentação

| Documento | Área |
|---|---|
| `docs/ARCHITECTURE.md` | arquitetura e decisões |
| `docs/SECURITY.md` | segurança e modelo de ameaças |
| `docs/SEO.md` | indexação/SSR |
| `docs/PWA.md` | instalabilidade offline |
| `docs/TABLET.md` | responsividade |
| `docs/GOOGLE-PLAY.md` | publicar na Play (TWA) |
| `docs/DESKTOP.md` | aplicação desktop |
| `docs/CLOUD.md` | nuvem/provedor |
| `docs/DEPLOYMENT.md` | deploy + CI/CD |
| `docs/MONITORING.md` | observabilidade |

## Rotas principais

- **Público**: `/`, `/login`, `/register`, `/post/{slug}`, `/profile/{username}`,
  sitemaps, `robots.txt`, `manifest.json`.
- **API** (`/api/*`): auth, users, posts, feed, search, groups, circles, events,
  stories, messages (+ WebSocket `/api/messages/ws`), notifications, uploads,
  admin.
- **Área logada** (`/app/*`): feed, mensagens, publicar, grupos, eventos, stories.

## Contribuir / validar

- Rodar sempre `./run.sh test` antes de subir mudanças.
- Add migração com `cd backend && .venv/bin/python -m alembic revision --autogenerate -m "..."`.
- O CI exige testes verdes, imagem buildável e sem secrets no diff.
- Rodar a suíte de cybersecurity (seção acima) antes de publicar.

## Publicar

1. **GitHub**: `git init -b main && git add -A && git commit -m "feat: NEXA v0.1"`,
   crie o repo (por ex. via `gh repo create nexa --public --source . --push`) e
   suba.
2. **Vercel**: importe o repo com Root Directory = `backend` — deploys automáticos
   em cada push (seção acima).
3. **AWS (produção com realtime)**: `terraform/` — veja `terraform/README.md`
   (`terraform apply` → ECS Fargate + RDS + Redis + S3 + ALB), e `./ecr-push.sh`
   para publicar a imagem.

## Licença

Projeto de portfólio de aprendizado. Todos os dados são fictícios.