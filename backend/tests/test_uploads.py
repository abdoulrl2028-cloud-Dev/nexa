"""Uploads: autenticação, mime permitido, tamanho, servição local e mídia em posts."""
import io
import os

from tests.conftest import api, create_post, register


def _upload(client, token, filename, content_type, data):
    return client.post("/api/upload",
                       files={"file": (filename, io.BytesIO(data), content_type)},
                       headers={"Authorization": f"Bearer {token}"})


def test_upload_requires_auth(client):
    assert client.post("/api/upload",
                       files={"file": ("a.png", io.BytesIO(b"x"), "image/png")}).status_code == 401


def test_upload_jpg_and_serve(client):
    token = register(client, "ana")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    r = _upload(client, token, "foto.png", "image/png", png)
    assert r.status_code == 201, r.text
    key = r.json()["key"]
    assert r.json()["url"]
    # servido via /media
    r2 = client.get(f"/media/{key}")
    assert r2.status_code == 200


def test_upload_rejects_disallowed_type(client):
    token = register(client, "ana")
    r = _upload(client, token, "malware.exe", "application/x-msdownload", b"MZxxxx")
    assert r.status_code == 415


def test_upload_to_post_and_message(client):
    token = register(client, "ana")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    r = _upload(client, token, "p.png", "image/png", png)
    key = r.json()["key"]
    post = api(client, "POST", "/api/posts",
               {"title": "com foto", "content": "x", "visibility": "public", "media_keys": [key]}, token=token)
    assert post.status_code == 201, post.text
    assert len(post.json()["media"]) == 1
    other = register(client, "bruno")
    r = api(client, "POST", "/api/messages",
            {"recipient": "bruno", "content": "attachment", "media_key": key}, token=token)
    assert r.status_code == 201, r.text
    assert r.json()["media"] is not None


def test_upload_rejects_foreign_key_in_message(client):
    token = register(client, "ana")
    other = register(client, "bruno")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    r = _upload(client, token, "p.png", "image/png", png)
    key = r.json()["key"]
    # bruno não pode anexar mídia da ana
    r = api(client, "POST", "/api/messages",
            {"recipient": "ana", "content": "x", "media_key": key}, token=other)
    assert r.status_code == 400