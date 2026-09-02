"""Autenticação: registro, login, refresh, logout e validações."""
from tests.conftest import api, register


def test_register_login_refresh_logout(client):
    token = register(client, "ana")
    assert token
    # login
    r = api(client, "POST", "/api/auth/login", {"username": "ana", "password": "senha12345"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    # refresh rotaciona
    r2 = api(client, "POST", "/api/auth/refresh", {"refresh_token": body["refresh_token"]})
    assert r2.status_code == 200, r2.text
    new_refresh = r2.json()["refresh_token"]
    old = r2.json()["access_token"]
    # logout revoga o refresh (não pode ser reutilizado) e limpa cookie
    r3 = api(client, "POST", "/api/auth/logout", {"refresh_token": new_refresh}, token=old)
    assert r3.status_code == 200
    assert any("nexa_session" in c.lower() for c in r3.headers.get_list("set-cookie"))
    r4 = api(client, "POST", "/api/auth/refresh", {"refresh_token": new_refresh})
    assert r4.status_code == 401


def test_register_validations(client):
    r = register_attempt(client, "ab", "senha12345")
    assert r == 422  # curto demais
    r = register_attempt(client, "9zinho", "curta")
    assert r == 422  # senha curta
    # maiúsculas são normalizadas para minúsculo
    r = register_attempt(client, "NomeBacana", "senha12345")
    assert r == 201
    r = register_attempt(client, "nomebacana", "outrasenha")
    assert r == 409


def register_attempt(client, user, password, display=None):
    r = api(client, "POST", "/api/auth/register",
            {"username": user, "password": password, "display_name": display or user})
    return r.status_code


def test_login_wrong_password(client):
    register(client, "zoe")
    r = api(client, "POST", "/api/auth/login", {"username": "zoe", "password": "errada123"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert api(client, "GET", "/api/auth/me").status_code == 401
    r = api(client, "GET", "/api/auth/me",
            headers={"Authorization": "Bearer token.invalido.xyz"})
    assert r.status_code == 401