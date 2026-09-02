# SEO do NEXA

Como o NEXA garante indexação de conteúdo público por buscadores, mesmo sendo um
app com área logada e PWA.

## Abordagem: SSR (Server-Side Rendering)

Toda a parte pública é renderizada como HTML no servidor com Jinja2. Não há CSR
para conteúdo indexável — o Google vê o HTML completo, não uma cascata de JS.

## O que é indexável vs. não

| Área | Indexável? | Mecanismo |
|------|-----------|-----------|
| `/` (home com posts públicos) | Sim | SSR + `post-card` + stats |
| `/post/{slug}` público | Sim | SSR + JSON-LD `BlogPosting` + canonical |
| `/login`, `/register` | Não | meta `noindex` |
| `/app/*` (área logada) | Não | `Authorization` obrigatória + robots `Disallow` |
| Posts `private`/`friends` | Não | retornam 404 para anônimos |

## Tags implementadas

- **Canonical** `<link rel="canonical">` em páginas indexáveis.
- **JSON-LD** (`schema.org/BlogPosting`) nos posts públicos: título, autor, data,
  URL, imagem.
- **Meta noindex** nas páginas de auth e área logada.
- **Open Graph / social** básicos (título, descrição, imagem).
- **`hreflang`** autogenerado para `pt-BR`/`pt-PT` quando relevante (home).

## robots.txt

Gerado dinamicamente por ambiente (`app/pages/...`):
- `development`: `Disallow: /` (evita indexar seu ambiente de dev).
- `staging`/`production`: permite público, `Disallow: /app/`, `/login`,
  `/register`, `/api/`, `/media/` + **Sitemap**.

## Sitemaps

Sitemaps dinâmicos (`app/pages/sitemap.py`) com contagens por `func.count`
(fix para Result → scalar). Incluem URLs públicas canonizadas pelo `SITE_URL`.

## Práticas recomendadas

1. Definir `SITE_URL` correto por ambiente (usado em canonical, canonical e sitemap).
2. Enviar o sitemap no Google Search Console.
3. Verificação: `curl -s https://site.com/post/<slug> | grep canonical`.
4. A área `/app/*` depende de sessão; anônimos recebem 302 → `/login` (não indexada).

## Testes de regressão

Suíte `tests/test_seo.py` cobre (29 testes no total, 6 de SEO):
- página pública indexável (canonical + JSON-LD presente),
- `/login` é `noindex`,
- post privado → 404 para anônimo (nunca exposto),
- home tem stats + `hreflang` + canonical,
- sitemap/robots corretos,
- manifest aponta para ícones reais.

Teste importante: para simular anônimo de verdade, o cookie da sessão deve ser
limpo (`client.cookies.clear()`) — o TestClient, do contrário, mantém a sessão do
registro e "vira" o dono do recurso.
