"""Posts: criação, visibilidade (público/privado/mutual), likes, comentários e reports."""
from tests.conftest import api, create_post, register


def test_post_create_and_public_read(client):
    token = register(client, "ana")
    post = create_post(client, token, "Hello NEXA", "primeiro post")
    assert post["slug"] == "hello-nexa"
    r = api(client, "GET", f"/api/posts/{post['slug']}")
    assert r.status_code == 200
    assert r.json()["post"]["title"] == "Hello NEXA"


def test_private_post_hidden_from_non_follower(client):
    token = register(client, "ana")
    post = create_post(client, token, "Segredo", "privado", visibility="private")
    assert post["visibility"] == "private"
    other = register(client, "bruno")
    r = api(client, "GET", f"/api/posts/{post['slug']}", token=other)
    assert r.status_code == 404
    # dono ainda vê
    r = api(client, "GET", f"/api/posts/{post['slug']}", token=token)
    assert r.status_code == 200


def test_private_post_is_author_only(client):
    token = register(client, "ana")
    post = create_post(client, token, "Segredo", "privado", visibility="private")
    assert post["visibility"] == "private"
    # autor vê
    assert api(client, "GET", f"/api/posts/{post['slug']}", token=token).status_code == 200
    # não-followers não veem
    guest = register(client, "bruno")
    assert api(client, "GET", f"/api/posts/{post['slug']}", token=guest).status_code == 404
    # visitantes anônimos não veem
    assert api(client, "GET", f"/api/posts/{post['slug']}").status_code == 404


def test_friends_post_requires_mutual(client):
    token = register(client, "ana")
    post = create_post(client, token, "Só amigos", "mutual", visibility="friends")
    carla = register(client, "carla")
    # um follow só não basta
    assert api(client, "POST", "/api/users/ana/follow", token=carla).status_code == 200
    assert api(client, "GET", f"/api/posts/{post['slug']}", token=carla).status_code == 404
    # ana segue de volta -> amizade recíproca -> visível
    assert api(client, "POST", f"/api/users/carla/follow", token=token).status_code == 200
    assert api(client, "GET", f"/api/posts/{post['slug']}", token=carla).status_code == 200


def test_like_unlike_and_comment(client):
    token = register(client, "ana")
    post = create_post(client, token, "Engajamento", "texto")
    other = register(client, "duda")
    r = api(client, "POST", f"/api/posts/{post['slug']}/like", token=other)
    assert r.status_code == 200 and r.json()["like_count"] == 1
    r = api(client, "POST", f"/api/posts/{post['slug']}/comments", {"content": "muito bom"}, token=other)
    assert r.status_code == 201
    # unlike (DELETE) — POST é idempotente por design
    r = api(client, "DELETE", f"/api/posts/{post['slug']}/like", token=other)
    assert r.json()["like_count"] == 0
    r = api(client, "POST", f"/api/posts/{post['slug']}/like", token=other)
    assert r.json()["like_count"] == 1
    r = api(client, "GET", f"/api/posts/{post['slug']}")
    assert r.json()["post"]["comment_count"] == 1


def test_reports_remove_post(client):
    token = register(client, "ana")
    post = create_post(client, token, "Spam", "denunciável")
    reporters = [register(client, f"rep{i}") for i in range(5)]
    for t in reporters:
        assert api(client, "POST", f"/api/posts/{post['slug']}/report",
                   {"reason": "spam"}, token=t).status_code in (200, 201)
    r = api(client, "GET", f"/api/posts/{post['slug']}")
    assert r.status_code == 404  # removido após 5 denúncias


def test_feed_cursor_and_visibility(client):
    token = register(client, "ana")
    for i in range(3):
        create_post(client, token, f"Post {i}", f"conteúdo {i}")
    other = register(client, "bruno")
    assert api(client, "POST", "/api/users/ana/follow", token=other).status_code == 200
    r = api(client, "GET", "/api/feed/home", token=other)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 3
    assert api(client, "GET", "/api/feed/discover").status_code == 200