# Segurança do NEXA

Modelo de ameaças, controles implementados e boas práticas de operação.

## Princípios

- **Nenhum secret no código** — tudo via `SECRET_KEY`, `DATABASE_URL` etc. em
  variáveis de ambiente (`.env`, compose, CI).
- **Defesa em profundidade**: validação no schema, autorização no caso de uso e
  verificação de propriedade em cada recurso.

## Autenticação

- Senhas com **PBKDF2-HMAC-SHA256** com salt único por usuário.
- Sessão por **JWT HS256** (`HS256`) assinado com `SECRET_KEY` (min. 32 bytes,
  obrigatória em staging/production — `config.validate()`).
- Acesso: curto (default 30 min); refresh: longo (default 30 dias).
- **Refresh rotation**: cada refresh gira o token e revoga o `jti` anterior via
  cache, impedindo reuso.
- **Logout** revoga o `refresh_token` informado (schema `RefreshIn`).

## Transporte de credencial

- SSR usa cookie **httpOnly** `nexa_session` (não acessível a JS).
- API aceita o mesmo cookie **ou** header `Authorization: Bearer <jwt>`.

## Autorização / visibilidade

- `public`: todos, incluindo anônimos (páginas indexáveis).
- `private`: apenas o autor e administradores.
- `friends`: apenas followers mútuos.
- Posts/recursos privados retornam **404** para quem não tem acesso (não expõem
  existência). Confirmado por teste (`test_private_post_page_noindex`).

## Prevenção de abuso

- **Rate limiting** por **Redis** quando `REDIS_URL` configurada (login, registro,
  uploads). Sem Redis (dev), limitação é desligada — ative em produção.
- **Uploads**: tamanho máx. (`MAX_UPLOAD_MB`), whitelist de MIME (rejeita → 415),
  vazio → 400, e verificação de propriedade (não pode usar mídia de outro usuário).
- **Reporte de posts**: 5 reports (com `reason` obrigatório) → post removido.
- **Usernames** normalizados (lowercase) e validados (3–32, alfanumérico + `_`).

## Headers HTTP

Aplicados via Caddy em produção:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy` restrita (somente `self`, `data:`, `blob:`, `wss://`)
- `Permissions-Policy` desativa câmera/mic/geolocalização desnecessárias.

## Banco de dados

- O app nunca expõe o banco à internet; fala via rede interna/overlay.
- Docker Compose expõe apenas a API; `db` e `redis` são internos.
- PostgreSQL em produção com connection pooling (QueuePool).

## Operação / hardening

- `SECRET_KEY` forte: `openssl rand -hex 32`.
- Nunca commitar `.env` (`.env.example` é só o template).
- Rodar `trufflehog` no CI para vazar secrets.
- Manter dependências atualizadas (`requirements.txt`).
- Em produção, considerar `ALLOW_REGISTRATION=false` para convite.

## Check-list de incidente

1. Rotacionar `SECRET_KEY` (invalida todos os tokens).
2. Verificar logs de auth/upload.
3. Revogar usuários suspeitos (`is_active=false`).
