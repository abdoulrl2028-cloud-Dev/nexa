# NEXA como PWA (Progressive Web App)

O NEXA é instalável como Progressive Web App em desktop e mobile (Android/iOS via
"Adicionar à tela inicial"). É também a base do TWA para a Play Store
(`GOOGLE-PLAY.md`).

## O que entrega

- **Instalável**: manifesto + service worker + ícones → prompt de instalação.
- **Offline-first**: o service worker cacheia o shell; conteúdo dinâmico é
  network-only.
- **Rápido**: estáticos imutáveis cacheados (long-lived); SSR serve HTML completo.
- **Realtime de mensagens** via WebSocket na área logada.

## Arquivos

```
static/
├── manifest.json           # identidade da PWA (nome, ícones, tema)
├── sw.js                   # service worker
├── icons/
│   ├── icon.svg
│   ├── icon-192.png
│   └── icon-512.png        # gradiente #6366f1→#a855f7 + "N"
├── css/app.css
└── js/app.js
```

## Manifesto

- `name`/`short_name` = NEXA.
- `start_url` = área logada.
- `display: standalone` (app em janela própria).
- `background_color`/`theme_color` para transição suave.
- Ícones 192 e 512 (obrigatórios para instalação).

## Service worker (`sw.js`)

- Cache `nexa-v1` para o shell (estáticos).
- **Network-only** para `/api/`, `/media/` e `/app*` — nunca cachear dado de
  sessão/conteúdo dinâmico (evita vazar dados privados offline).
- Estratégia "precache + runtime" para os assets.

## Área instalação / login

- O `beforeinstallprompt` é exposto (e capturado via `js/app.js`) para o botão
  "Instalar".
- Sessão via cookie httpOnly:`nexa_session` — a PWA usa as mesmas rotas SSR e API.

## Habilitar em produção

1. Servir HTTPS (obrigatório para service worker).
2. Registrar o `sw.js` na página (já ocorre em `templates/`).
3. Confirmar que `manifest.json` retorna 200.
4. (Opcional, recomendado) ícones com mascarável para telas de iOS.

## Verificação

- Google Lighthouse (PWA) deve apontar instalável/armazenável.
- `curl -s /manifest.json | jq .` confirma ícones.
- Devtools → Application → Service workers: `activated`.
- Teste de instalação no Chrome (ícone na barra).

## Relação com TWA/Desktop

- **TWA** (Android, Play): abra a PWA numa Trusted Web Activity (`GOOGLE-PLAY.md`).
- **Desktop** (Tauri): a janela Tauri abre a própria PWA/SSR (`DESKTOP.md`).
- **Tablet**: mesma PWA responsiva (`TABLET.md`).
