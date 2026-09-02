"""Entrypoint do NEXA para Vercel (Python runtime / funções serverless).

REST + SSR funcionam normalmente. LIMITAÇÃO: o WebSocket realtime de mensagens
(/api/messages/ws) NÃO roda em funções serverless sem sessão; para realtime use a
implantação AWS Fargate (ver ../terraform/README.md) ou um vhost persistente.
"""
import os
import sys

# Garante que o pacote `app` (em backend/) esteja no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import init_db  # noqa: E402

init_db()

from app.main import app  # noqa: E402

# Vercel exporta a ASGI app por padrão (variável `app`)