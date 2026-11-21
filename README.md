# Mapa Umuarama

Web app (PWA) com o **Mapa Oficial de Numeração Predial de Umuarama-PR**, feito para entregadores.

- Busca por **rua + número** (ex.: `ney braga 1520`), bairro ou local
- Ruas, quadras, lotes, numeração predial, bairros, rios e rodovias
- Tema escuro (e claro)
- Guia **Configurações** com as atualizações do app
- Opção experimental: **abrir rota no Google Maps**
- Instalável na tela inicial e funciona **sem internet**

## Publicar no GitHub Pages

1. No repositório: **Settings → Pages**
2. Em *Source*, escolha **Deploy from a branch**
3. Branch **main**, pasta **/ (root)** → **Save**
4. Em 1–2 minutos o app fica em `https://SEU-USUARIO.github.io/NOME-DO-REPO/`

Mande esse link para os motoboys. No celular, eles podem tocar em **Configurações → Instalar** (Android) ou em **Compartilhar → Adicionar à Tela de Início** (iPhone).

## Lançar uma atualização

1. Altere o app em `tools/src.html`
2. Em `version.json`, mude `"latest"` para a nova versão (ex.: `1.2.0`) e adicione um item no começo de `"versions"` com a data e as novidades
3. Rode `python3 tools/build.py` (gera `index.html` e `sw.js` com a nova versão)
4. Faça commit e push

Quem já usa o app vê o aviso **“Nova versão disponível”** e atualiza em **Configurações → Atualizar agora**.

## Atualizar o mapa (novo DWG)

`tools/extrair_dwg.py` converte o JSON gerado pelo [LibreDWG](https://www.gnu.org/software/libredwg/) (`dwgread -O JSON`) em `data/mapa.json`.

## Estrutura

| Arquivo | O que é |
|---|---|
| `index.html` | O app (gerado) |
| `sw.js` | Service worker: cache offline e atualizações (gerado) |
| `version.json` | Versão atual e lista de novidades |
| `data/mapa.json` | Dados do mapa compactados |
| `manifest.webmanifest`, `icons/` | Instalação como app |
| `tools/` | Código-fonte e scripts de build |
