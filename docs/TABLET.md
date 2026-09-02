# Suporte Tablet

Como o NEXA se comporta em tablets (iPad, Android tablet, 2-em-1, desktop), e o
modelo do layout responsivo.

## Princípio

O NEXA é **SSR + PWA responsivo** e single-column por padrão. Ele usa CSS moderno
(`static/css/app.css`) com `min-width` breakpoints e um container de largura
máxima (para posts legíveis). Em telas largas (desktop/tablet em landscape), a
área logada usa um **layout colapsável** que dá mais amplitude para o feed.

> O NEXA **não tem** um layout "master-detail" obrigatório como Gmail/WhatsApp
> Web. Mensagens diretas usam uma **lista de conversas + painel de leitura** que,
> em tablets, vira uma coluna lateral quando há espaço.

## Breakpoints principais

| Tela | Faixa | Comportamento |
|------|-------|---------------|
| Phone | < 640px | single column, bottom/sheet de navegação |
| Tablet (retrato) | 640–1024px | single column otimizada, toque grande |
| Tablet/desktop (paisagem) | ≥ 1024px | conteúdo centralizado, painéis laterais |
| Desktop amplo | ≥ 1280px | colunas extras (mensagens com lista+leitura) |

## Responsividade de componentes

- **Feed**: largura máx. (~680px) para leitura confortável.
- **Mensagens**: em telas ≥ 900px, exibe `lista de conversas` + `painel de leitura`
  lado a lado; abaixo disso uma única visão.
- **Stories**: barra horizontal com rolagem por toque.
- **Nav**: muda de barra inferior (mobile) para lateral/superior (tablet/desktop).
- **Textos e alvos de toque**: `font-size` e espaçamento acomodados para dedo.

## Manutenção

A responsividade vive em `static/css/app.css` (media queries) e `templates/`
(`app_base.html`, `space.html`, etc.). Não há CSS separado por dispositivo — o
mesmo CSS serve web, PWA, TWA e desktop, garantindo consistência.

## Verificação

1. Abra em devtool com device toolbar em iPad/tablet retrato.
2. Teste feed, criação de post, mensagens e stories em cada breakpoint.
3. Em paisagem ≥ 900px, confirme o layout de duas colunas das mensagens.
4. Confirme que alvos de toque ≥ 44px e sem overflow horizontal.

## Desktop / TWA / Tablet: mesma base

Como o NEXA é responsivo, um tablet (portrait), um iPad e o wrapper desktop
(`desktop/`) usam exatamente o mesmo código — nenhuma versão separada é mantida.
