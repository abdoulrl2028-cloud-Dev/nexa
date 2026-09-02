# Aplicação Desktop (Tauri)

Como o NEXA é entregue como aplicação desktop para Windows, macOS e Linux usando
Tauri v2.

## Conceito

O `desktop/` é um wrapper Tauri v2 que abre a aplicação web NEXA (PWA/SSR) numa
janela nativa. Reaproveita 100% do backend e frontend — uma única base de código
em todas as plataformas (web, mobile via TWA, desktop via Tauri).

> O NEXA é **SSR**: a "app web" e o "frontend" já são a própria API. O Tauri apenas
> hospeda essa URL real.

## Estado

- **Scaffold** completo (estrutura Tauri v2 pronta).
- **Não compilado/verificado nesta máquina** — requer toolchain Rust.
- Veja `desktop/README.md` para instruções de build.

## Estrutura

```
desktop/
├── src/index.html              # tela de carregamento da webview
└── src-tauri/
    ├── Cargo.toml              # manifesto Rust (tauri v2)
    ├── tauri.conf.json         # janela, segurança (CSP), bundle
    ├── capabilities/default.json
    ├── icons/icon.png
    └── src/{main.rs, lib.rs}
```

## Ponto de entrada

`tauri.conf.json` define `app.windows[0].url = http://localhost:8000` (em dev) ou
a `SITE_URL` de produção. O `frontendDist` aponta para `../src` como fallback.

## Segurança

- CSP restrita: só o próprio site e `ws://localhost:8000` (realtime).
- Sessão via cookie httpOnly gerenciada pelo backend (nenhum token embutido no desktop).

## Build / release

```bash
cd desktop
cargo tauri dev        # janela de desenvolvimento
cargo tauri build      # gera .deb/.AppImage (Linux), .msi/.exe (Win), .dmg (macOS)
```

Empacotar binários assinados para distribuição requer CI com toolchain Rust
(workflow de exemplo em `../.github/workflows/ci.yml`).

## Roadmap (fora do scaffold)

- [ ] `SITE_URL` de produção configurável no build (não só localhost).
- [ ] Notificações nativas (tauri-plugin-notification).
- [ ] Auto-update (tauri-plugin-updater).
- [ ] Ícones completos por plataforma (`tauri icon icons/source.png`).
- [ ] Assinatura de código para Windows/macOS.
