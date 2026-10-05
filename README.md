<p align="center">
  <img src="https://raw.githubusercontent.com/abdoulrl2028-cloud-Dev/abdoulrl2028-cloud-Dev/main/assets/projects/nexa.jpg" alt="NEXA social network" width="100%">
</p>

# NEXA

A cross-platform social network. One **FastAPI** backend serves four surfaces: **Web/PWA**, **Android (TWA)**, **Desktop (Tauri)**, and **Tablet**, with SSR, SEO, a REST API, and realtime messages over WebSocket.

```
Browser / PWA ──► FastAPI (REST + SSR/SEO + WS) ◄── Desktop (Tauri)
Android TWA   ──►        │                         ▲
                     DB (SQLite/PostgreSQL)         ┆  same code
                     Redis (optional)               ┘
```

## About

- **Backend:** Python 3, FastAPI, SQLAlchemy 2.0, and Jinja2 (SSR).
- **Frontend:** vanilla JS/CSS, installable PWA (manifest, service worker, and icons).
- **Auth:** PBKDF2-HMAC-SHA256, JWT HS256, httpOnly cookie, and Bearer tokens.
- **Features:** posts (public, private, friends), cursor feed, follow, groups, circles, events, stories, direct messages with realtime WebSocket, notifications, search, uploads, admin, and reports (5 reports remove a post).
- **Tests:** pytest suite in `backend/tests/` (29 tests) running in CI.

## Layout

```
nexa/
├── backend/            # FastAPI, templates, static files, Alembic, tests
├── desktop/            # Tauri v2 wrapper (needs Rust)
├── deploy/             # Dockerfile, docker-compose, Caddyfile, run.sh
├── docs/               # architecture, security, SEO, cloud, and more
├── .github/workflows/  # CI/CD
├── .env.example
└── run.sh
```

## Requirements

- Python 3.12+ (3.12 or 3.14 recommended).
- Optional Redis for cache and rate limits. Optional PostgreSQL for production.

## Quick start

```bash
cd nexa
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env
./run.sh migrate
./run.sh
```

`./run.sh` starts uvicorn on your computer at port 8000. That address is local only. In another terminal, run `./run.sh test`.

## `run.sh`

| Command | Effect |
| --- | --- |
| `./run.sh` | Start uvicorn on port 8000 with reload |
| `./run.sh migrate` | `alembic upgrade head` |
| `./run.sh test` | Run pytest |
| `PORT=9000 ./run.sh` | Change the port |

Environment variables: `NEXA_ENV`, `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `STORAGE_DRIVER` (see `.env.example`).

## Security checks before release

Scan the app locally before publishing. Run these from the project root.

| Tool | What it finds | Command |
| --- | --- | --- |
| **TruffleHog** | Secrets in git history | `docker run --rm -v "$PWD:/pwd" ghcr.io/trufflesecurity/trufflehog:latest git file:///pwd --only-verified` |
| **Gitleaks** | Exposed secrets | `docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8 detect --source=/repo --verbose` |
| **Bandit** | Static issues in Python | `cd backend && .venv/bin/bandit -r app/` |
| **pip-audit** | Python dependencies with CVEs | `cd backend && .venv/bin/pip-audit -r requirements.txt` |
| **Ruff** | Lint | `cd backend && .venv/bin/ruff check app/` |
| **Semgrep** | Vulnerability patterns | `docker run --rm -v "$PWD:/src" returntocorp/semgrep semgrep scan --config=auto /src/backend/app` |
| **Trivy** | CVEs in the Docker image | `docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --severity HIGH,CRITICAL <image>` |

Minimum sequence before each release:

```bash
gitleaks detect --source=. --verbose
bandit -r backend/app -q
pip-audit -r backend/requirements.txt
./run.sh test
```

CI (`.github/workflows/ci.yml`) already runs **TruffleHog** on every push. `docs/SECURITY.md` covers the threat model, PBKDF2/JWT, post visibility, rate limits, and runbooks.

## Automatic deploy on Vercel

`backend/` includes `vercel.json` and `api/index.py` (ASGI serverless function). Set the deploy root to `backend`. Each push publishes a preview or production deployment.

1. Push the project to GitHub.
2. In Vercel: **Add New → Project → Import** the NEXA repository.
3. Set **Root Directory** to `backend`.
4. Add environment variables: `NEXA_ENV`, `SECRET_KEY`, `DATABASE_URL`, optional `REDIS_URL`, and S3 settings if you use object storage.
5. Deploy.

The realtime WebSocket (`/api/messages/ws`) does not run on serverless functions. On Vercel, REST, SSR, and polling work. For realtime, use the **AWS Fargate** setup in `terraform/` (RDS, Redis, S3, and an ALB).

## Docs

| Document | Topic |
| --- | --- |
| `docs/ARCHITECTURE.md` | Architecture and decisions |
| `docs/SECURITY.md` | Security and threat model |
| `docs/SEO.md` | Indexing and SSR |
| `docs/PWA.md` | Offline install |
| `docs/TABLET.md` | Responsive layout |
| `docs/GOOGLE-PLAY.md` | Play Store (TWA) |
| `docs/DESKTOP.md` | Desktop app |
| `docs/CLOUD.md` | Cloud provider |
| `docs/DEPLOYMENT.md` | Deploy and CI/CD |
| `docs/MONITORING.md` | Observability |

## Main routes

- **Public:** `/`, `/login`, `/register`, `/post/{slug}`, `/profile/{username}`, sitemaps, `robots.txt`, `manifest.json`.
- **API** (`/api/*`): auth, users, posts, feed, search, groups, circles, events, stories, messages, notifications, uploads, and admin.
- **Signed-in area** (`/app/*`): feed, messages, publishing, groups, events, and stories.

## Publish

1. Push the repository to GitHub.
2. Import it in Vercel with Root Directory `backend`.
3. For production with realtime, use `terraform/` (`terraform apply` for ECS Fargate, RDS, Redis, S3, and an ALB) and `./ecr-push.sh` for the image.

## License

Learning portfolio project. All sample data is fictional.
