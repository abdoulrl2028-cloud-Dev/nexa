"""Mensagens diretas: REST (conversa, thread, leitura) e WebSocket realtime.

A entrega WS→WS em cenário com DUAS conexões simultâneas num mesmo TestClient
trava por limitação do portal do TestClient (uma conexão por event loop).
Esse caminho é coberto por validação ao vivo com um servidor uvicorn real +
cliente `websockets` (ver docs/). Aqui validamos os caminhos que o TestClient
suporta fielmente: ping/pong, push REST→WS (mesmo event loop) e rejeição de
token inválido.
"""
import json

import pytest
from starlette.websockets import WebSocketDisconnect

from tests.conftest import api, register


def test_rest_message_flow_and_privacy(client):
    token_a = register(client, "ana")
    token_b = register(client, "bruno")
    outsider = register(client, "carla")
    assert api(client, "POST", "/api/messages",
               {"recipient": "bruno", "content": "Oi Bruno!"}, token=token_a).status_code == 201
    r = api(client, "GET", "/api/messages/conversations", token=token_a)
    assert r.status_code == 200 and len(r.json()) == 1
    cid = r.json()[0]["id"]
    r = api(client, "POST", "/api/messages",
            {"conversation_id": cid, "content": "Oi Ana!"}, token=token_b).status_code
    assert r == 201
    r = api(client, "GET", f"/api/messages/conversations/{cid}", token=token_b)
    assert r.status_code == 200 and len(r.json()) == 2
    # exclusão de terceiros
    r = api(client, "GET", f"/api/messages/conversations/{cid}", token=outsider)
    assert r.status_code == 403
    # marca leitura
    assert api(client, "POST", f"/api/messages/conversations/{cid}/read", token=token_b).status_code == 200
    r = api(client, "GET", "/api/messages/conversations", token=token_a)
    assert r.json()[0]["unread"] == 1


def test_ws_pingpong(client):
    token = register(client, "ana")
    with client.websocket_connect(f"/api/messages/ws?token={token}") as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"


def test_ws_receives_rest_push(client):
    """Usuário online no WS recebe em tempo real mensagens enviadas via REST."""
    token_a = register(client, "ana")
    token_b = register(client, "bruno")
    with client.websocket_connect(f"/api/messages/ws?token={token_a}") as ws:
        r = api(client, "POST", "/api/messages",
                {"recipient": "ana", "content": "push via REST"}, token=token_b)
        assert r.status_code == 201
        msg = ws.receive_json()
        assert msg["type"] == "message"
        assert msg["message"]["content"] == "push via REST"


def test_ws_rejects_bad_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/messages/ws?token=invalido") as ws:
            ws.receive_json()