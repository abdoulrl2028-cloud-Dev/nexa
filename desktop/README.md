# NEXA — Aplicação Desktop (Tauri v2)

Cliente desktop do NEXA construído com [Tauri v2](https://tauri.app). Ele abre a
aplicação web NEXA (PWA) dentro de uma janela nativa, reaproveitando 100%
do backend e do frontend — não há código de UI duplicado.

> **Estado: scaffold.** Este diretório contém a estrutura mínima do projeto Tauri
> **não é compilada/verificada nesta máquina** (requer toolchain Rust). Compile
> numa máquina de desenvolvimento com Rust instalado.

## Pré-requisitos

- Rust toolchain (`rustup`, stable)
- Dependências de sistema do Tauri v2 (Linux: `webkit2gtk-4.1`, `libappindicator`,
  `librsvg`; ver [prereqs do Tauri](https://v2.tauri.app/start/prerequisites/))
- Backend NEXA no ar em `http://localhost:8000` (veja `../run.sh`)

## Estrutura

```
desktop/
├── src/index.html            # tela de carregamento (entrada da webview)
└── src-tauri/
    ├── Cargo.toml            # manifesto Rust (tauri v2)
    ├── tauri.conf.json       # janela, segurança (CSP), bundle
    ├── capabilities/         # permissões
    ├── icons/icon.png        # ícone
    └── src/main.rs, lib.rs   # entry point
```

A janela aponta para `http://localhost:8000` (a própria PWA) — configurável em
`tauri.conf.json` → `app.windows[].url`.

## Como rodar

```bash
# na raiz do NEXA, com o backend no ar:
../run.sh          # arranca a API em :8000

# em outra aba, no diretório desktop:
npm install -g @tauri-apps/cli   # opcional (ou use cargo diretamente)
cargo tauri dev                  # janela de desenvolvimento com hot-reload
cargo tauri build                # gera instaladores (.deb, .msi, .dmg…)
```

## Notas de segurança

- O CSP da janela permite somente o próprio NEXA e o `ws://localhost:8000` para o
  WebSocket realtime de mensagens.
- Nenhum token é armazenado fora do backend: as sessões ficam em cookie httpOnly
  gerenciado pelo próprio servidor.

## Roadmap (fora do scaffold)

- [ ] Empacotar com URL de produção configurável (`SITE_URL`) em vez de localhost
- [ ] Notificações nativas do sistema via plugin
- [ ] Auto-update (tauri-plugin-updater)
- [ ] Icones para todas as plataformas (`tauri icon`)
