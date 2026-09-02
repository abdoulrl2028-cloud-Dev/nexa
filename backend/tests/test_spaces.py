"""Grupos, círculos e eventos: CRUD, participação e posts do espaço."""
from tests.conftest import api, create_post, register


def test_group_lifecycle_and_posts(client):
    token = register(client, "ana")
    r = api(client, "POST", "/api/groups",
            {"name": "Devs Brasil", "description": "comunidade de devs", "visibility": "public"}, token=token)
    assert r.status_code == 201, r.text
    slug = r.json()["slug"]
    other = register(client, "bruno")
    assert api(client, "POST", f"/api/groups/{slug}/join", token=other).status_code == 200
    r = api(client, "POST", f"/api/groups/{slug}/posts",
            {"title": "Post do grupo", "content": "conteudo", "visibility": "public"}, token=other)
    assert r.status_code == 201, r.text
    r = api(client, "GET", f"/api/groups/{slug}/posts", token=other)
    assert r.status_code == 200 and len(r.json()["items"]) >= 1
    # não-membro não pode postar
    outsider = register(client, "carla")
    assert api(client, "POST", f"/api/groups/{slug}/posts",
               {"title": "invasor", "content": "x", "visibility": "public"}, token=outsider).status_code == 403
    # membros aparecem no detalhe
    r = api(client, "GET", f"/api/groups/{slug}/members", token=token)
    assert r.status_code == 200 and len(r.json()["items"]) >= 2


def test_circle_lifecycle(client):
    token = register(client, "ana")
    r = api(client, "POST", "/api/circles", {"name": "Fotografia", "visibility": "private"}, token=token)
    assert r.status_code == 201, r.text
    slug = r.json()["slug"]
    other = register(client, "bruno")
    assert api(client, "POST", f"/api/circles/{slug}/join", token=other).status_code == 200
    r = api(client, "POST", f"/api/circles/{slug}/posts",
            {"title": "Foto do dia", "content": "olha que foto", "visibility": "public"}, token=other)
    assert r.status_code == 201, r.text


def test_event_rsvp_and_participants(client):
    token = register(client, "ana")
    r = api(client, "POST", "/api/events",
            {"name": "Meetup NEXA", "description": "encontro",
             "location": "Online", "begins_at": "2026-11-01T19:00:00", "visibility": "public"}, token=token)
    assert r.status_code == 201, r.text
    slug = r.json()["slug"]
    other = register(client, "bruno")
    assert api(client, "POST", f"/api/events/{slug}/rsvp?status_value=going", token=other).status_code == 200
    r = api(client, "GET", f"/api/events/{slug}/participants")
    assert r.status_code == 200 and len(r.json()["items"]) >= 1