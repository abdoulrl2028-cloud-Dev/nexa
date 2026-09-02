# Arquitetura do NEXA

Visão de alto nível de como o NEXA está estruturado, suas camadas e decisões de
design. Leia este documento antes de contribuir.

## Visão geral

O NEXA é uma rede social **monolítica SSR** — um único servidor FastAPI entrega
API REST, páginas HTML indexáveis (SEO) e WebSocket realtime de mensagens. Não há
separação frontend/backend: o mesmo processo serve navegadores, PWA, mobile (TWA)
e uma janela desktop (Tauri) que apenas abre a URL.

```
                     ┌────────────────────────────────────────────┐
  Browser / PWA ────►│                                            │
  Android TWA ──────►│   FastAPI + SQLAlchemy + Jinja2 (1 app)    │
  Desktop (Tauri) ──►│                                            │
                     └───────┬───────────────┬────────────────────┘
                             │               │
                     ┌───────▼─────┐   ┌─────▼─────┐
                     │ DB (SQLite │   │ Redis     │
                     │ /PostgreSQL)│   │ (opcional)│
                     └─────────────┘   └───────────┘
```

## Camadas

- **`app/main.py`** — monta a app, middleware, rotas, tratamento 404, lifespan
  (chama `init_db()`).
- **`app/routers/`** — API REST.
- **`app/pages/`** — renderização SSR + SEO (`pages.py`) e sitemaps dinâmicos
  (`sitemap.py`).
- **`app/models.py`** — modelos ORM SQLAlchemy 2.0.
- **`app/db.py`** — engine/session (SQLite dev, PostgreSQL prod com pooling).
- **`app/security.py`** — senha PBKDF2-HMAC-SHA256, JWT HS256.
- **`app/config.py`** — configuração via variáveis de ambiente.
- **`app/storage.py`** — uploads (local ou S3).
- **`app/cache.py`** — cache (Redis ou memória).
- **`app/ws.py`**, **`app/notifier.py`** — WebSocket manager e notificações.
- **`templates/`**, **`static/`** — frontend PWA.

## Decisões de design

1. **SSR para SEO**: páginas públicas (`/`, `/post/{slug}`) são HTML renderizado
   no servidor com JSON-LD, canonical e robots. Conteúdo privado nunca é exposto
   (retorna 404 sem sessão).
2. **Duas camadas de autenticação**: cookie httpOnly (`nexa_session`) para SSR,
   Bearer JWT para API. O refresh gira o `jti` revogando o token antigo via cache.
3. **Visibilidade de posts**: `public` (todos), `private` (autor/admin),
   `friends` (follow mútuo). Valores inválidos → 422.
4. **WebSocket** em `/api/messages/ws` para mensagens diretas e digitação; push
   REST→WS no mesmo event loop (`await manager.send_to_user`).
5. **Feed com cursor** (keyset pagination) ao invés de offset, para escala.
6. **Composição por convenção**: rotas, templates e testes compartilham os nomes.

## Escalabilidade

- Leitura intensiva vai para PostgreSQL com índices em FKs, slugs e cursor.
- Redis opcional para cache/rate-limit/sessões (sem ele, usa memória — dev apenas).
- Uploads em object storage S3-compatível quando `STORAGE_DRIVER=s3`.

## Diretórios associados

- `../deploy/` — Docker, docker-compose, Caddy, CI/CD.
- `../desktop/` — cliente Tauri (scaffold).
- `../docs/` — documentação detalhada por área.
- `backend/tests/` — suíte pytest (29 testes).
- `backend/alembic/` — migrações (`run.sh migrate`).
