# Google Play (Android) — TWA

Publicar o NEXA na Google Play usando a técnica **TWA** (Trusted Web Activity). O
app no Play é um wrapper fino que abre a PWA/SSR do NEXA em tela cheia, sem duplicar
o frontend.

## Dica de arquitetura

O NEXA é um **app web com SSR/SEO + PWA**. Para a Play Store, a abordagem mais
barata de manter é:

- **PWA instalável** (web) — coberto em `PWA.md`.
- **TWA** (Android) — um projeto Android mínimo que carrega a `SITE_URL` numa
  Trusted Web Activity, exibindo a PWA como app nativo.

Isso dá "instalação" na Play sem escrever um app Android nativo do zero.

## Pré-requisitos

- Google Play Developer account (US$25 única).
- Produção com `SITE_URL` HTTPS e PWA servida corretamente (`manifest.json`,
  `sw.js`, ícones 192/512 — ver `PWA.md`).
- Asset Links do domínio para ligar o TWA ao site (prova de posse do domínio).

## Estrutura mínima (na raiz de um wrapper Android)

```
android-twa/
├── app/
│   └── src/main/
│       ├── AndroidManifest.xml        # declara a TWA + assetlinks
│       └── assets/.well-known/...     # não — asset links vão no domínio
└── build.gradle
```

É comum usar o projeto **[bubblewrap](https://github.com/GoogleChromeLabs/bubblewrap)`**
para gerar esse wrapper a partir do manifest da PWA.

## Passos

1. **PWA pronta** em produção (manifest + service worker + ícones).
2. **Asset Links**: servir `/.well-known/assetlinks.json` no domínio com a
   assinatura de debug e de release.
3. **Gerar o wrapper**: `npx @bubblewrap/cli init --manifest https://nexa.example.com/manifest.json`
   (aprova e ajusta nome, ícones, cores).
4. **Assinar** com uma chave de release (guardar com segurança — perda = não
   consegue atualizar).
5. Testar o app de debug num dispositivo.
6. **Upload** na Google Play (App bundle `.aab`), preencher ficha + política de
   privacidade, classificação de conteúdo, e enviar para revisão.

## Requisitos específicos

- Política de privacidade acessível públicamente.
- Classificação de conteúdo (pode haver conteúdo gerado por usuário).
- Declarar coleta de dados (NEXA coleta conta, conteúdo e, se S3, mídia).
- Ícones múltiplos (legado, adaptável, etc.) — o bubblewrap cuida.
- É preciso manter `targetSdkVersion` atualizada a cada ano (política do Play).

## Notas

- **WebView vs TWA**: use TWA (não WebView simples) para compatibilidade com a
  PWA/`BeforeInstallPrompt`.
- Verificação do domínio via Asset Links é o que liga a janela do TWA ao app da
  Play — sem isso a TWA abre como aba.

## Caso queira app nativo

Se um dia precisar de experiência 100% nativa, o `desktop/` mostra o modelo:
um wrapper que navega até a `SITE_URL`. Análogo é possível no Android com
`WebView`/`Custom Tabs` apontando para o mesmo NEXA.
