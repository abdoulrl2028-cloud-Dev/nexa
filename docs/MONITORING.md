# Monitoramento e Observabilidade

Como operar e observar o NEXA em produção: métricas, logs, alertas e diagnósticos.

## Sinais de ouro

Monitore estes sinais por instância/endpoint:

| Sinal | Origem | Importância |
|-------|--------|-------------|
| Latência de resposta (p50/p95/p99) | proxy (Caddy) / uvicorn | Alta |
| Taxa de erro (5xx/4xx por rota) | logs / métricas | Alta |
| Disponibilidade (`/health` ou `/`) | uptime check | Crítica |
| Uso de CPU/RAM/PGCD | infra da VM/container | Média |
| Filas (Redis) e conexões de DB | Redis/PG | Média |
| Latência e falhas de WebSocket | app/websockets | Alta (realtime) |
| Volume de uploads e storage | S3/volume | Média |
| Registros/login malsucedidos | logs de auth | Média (segurança) |

## Endpoints úteis

- `/` — home pública (pagecheck básico).
- `/robots.txt` — integridade de SEO.
- `/manifest.json` — PWA (deve responder em prod).
- WebSocket `/api/messages/ws` — health realtime.

## Logs

- Uvicorn em stdout (conteinerizações) com formato JSON opcional.
- Estrutura: timestamp, level, app, rota, status, duração, user_id (se logado).
- Não logar senhas, tokens nem conteúdo de mensagens em texto completo.

## Alertas recomendados

1. **Downtime**: uptime probe (UptimeRobot/Healthchecks.io) no `/`.
2. **Erro 5xx > 1% em 5 min**: métricas agregadas (Prometheus/Grafana ou do
   provedor).
3. **Latência p95 > 500ms**: degradação; entrar em Redis/cache.
4. **Disk/storage próximo do fim** (uploads locais) e **DB connections altas**.
5. **Login de acesso anômalo** (falhas em rajada → possível brute force).

## Segurança operacional

- Revogar sessão: girar `SECRET_KEY` em incidente (invalida todos os tokens).
- Desativar conta problemática: `is_active=false`.
- Alertar subida súbita de registros novos (bots/spam) e de reports.

## Integrações (sugestão)

- **APM/erros**: Sentry (FastAPI) para exceptions com contexto de request.
- **Métricas**: Prometheus + Grafana (expor `/metrics`) ou o painel do provedor.
- **Logs**: agregar via provedor/Loki.
- **Uptime**: Healthchecks.io / UptimeRobot com alerta em Slack/e-mail.

## Ferramentas embutidas

- `run.sh test` — suíte regressiva (29 testes).
- `deploy/run.sh` — aplica migrações + arranca; falha rápido se DB estiver inválido.
- CI (`.github/workflows/ci.yml`) — build, teste e trufflehog (secrets).

## Runbooks rápidos

- **DB cheio/lento**: ver conectividade do pool; `alembic upgrade head` pode
  travar em tabelas grandes — preparar de manutenção antes.
- **Memória alta**: 1 instância + Redis fraca → cache em memória estourando; subir
  Redis.
- **Uploads falhando**: checar credencial S3 / disco local; subir `MAX_UPLOAD_MB`
  se legítima.
- **Realtime parado**: conferir Redis e conexões WS; sem Redis só 1 instância
  (senão mensagens não chegam entre instâncias).