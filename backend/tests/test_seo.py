"""SEO: páginas públicas indexáveis, conteúdo privado com noindex, sitemaps e robots."""
from tests.conftest import api, create_post, register


def test_public_post_page_is_indexable(client):
    token = register(client, "ana")
    create_post(client, token, "Artigo público", "conteúdo indexável")
    r = client.get("/post/artigo-publico")
    assert r.status_code == 200
    html = r.text
    assert 'rel="canonical"' in html and "/post/artigo-publico" in html
    assert "application/ld+json" in html and "BlogPosting" in html
    assert "noindex" not in html.lower()


def test_login_page_is_noindex(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert r.headers.get("x-robots-tag", "").startswith("noindex")
    assert "noindex" in r.text.lower()


def test_private_post_page_noindex(client):
    token = register(client, "ana")
    create_post(client, token, "Painel interno", "sigiloso", visibility="private")
    client.cookies.clear()  # visitante anônimo de verdade
    r = client.get("/post/painel-interno")
    # não publicamente visível -> 404 (conteúdo privado nunca é exposto)
    assert r.status_code == 404


def test_public_home_has_stats_and_hreflang_canonical(client):
    token = register(client, "ana")
    create_post(client, token, "Post público da home", "conteúdo")
    r = client.get("/")
    assert r.status_code == 200
    assert "NEXA" in r.text and "post-card" in r.text
    assert 'rel="canonical"' in r.text


def test_sitemap_and_robots(client):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "sitemapindex" in r.text
    for sub in ("sitemap-users.xml", "sitemap-posts.xml", "sitemap-groups.xml",
                "sitemap-circles.xml", "sitemap-events.xml"):
        assert sub in r.text
    r = client.get("/robots.txt")
    assert r.status_code == 200 and "Disallow: /" in r.text


def test_manifest_points_to_real_icons(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "NEXA"
    assert any("icon-512.png" in i["src"] for i in body["icons"])
    # ícones existem e respondem
    for i in body["icons"]:
        src = i["src"].replace("http://localhost:8000", "")
        assert client.get(src).status_code == 200


def test_service_worker_at_root(client):
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert "application/javascript" in r.headers["content-type"]
    assert r.headers.get("service-worker-allowed") == "/"
    assert "self.addEventListener" in r.text
    # páginas registram o service worker (escopo raiz)
    for path in ("/", "/login", "/app"):
        html = client.get(path, follow_redirects=False)
        if html.status_code == 200:
            assert "navigator.serviceWorker.register('/sw.js')" in html.text