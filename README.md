# Mapa Umuarama — app Android

App Android com o **Mapa Oficial de Numeração Predial de Umuarama-PR**, feito para motoboys.

- Busca por **rua + número** (ex.: `ney braga 1520`), bairro ou local; se o número não estiver no mapa, a rua inteira fica destacada
- Ruas, quadras, lotes, numeração predial, bairros, rios e rodovias
- Tema escuro (e claro)
- Funciona **sem internet**
- Guia **Configurações**: atualizações do app (baixa e instala por dentro do app)
- Opção experimental: **abrir rota no Google Maps**

## Baixar o APK

Sempre a versão mais recente:
**https://github.com/gouzza968-jpg/Mapa-umuarama/releases/latest/download/mapa-umuarama.apk**

## Como o APK é gerado

A cada push na `main`, o GitHub Actions (`.github/workflows/build-apk.yml`):
1. gera `www/index.html` com `tools/build.py`
2. cria o projeto Android com Capacitor e copia ícones, tela de abertura e o plugin de atualização (`native/`)
3. compila e assina sempre com a mesma chave (`native/mapaumuarama.keystore`), para o app poder ser atualizado por cima
4. publica um **Release** com `mapa-umuarama.apk` e `update.json`

O app consulta `releases/latest/download/update.json`; quando o `versionCode` é maior que o instalado, aparece **“Nova versão disponível”** em Configurações.

## Lançar uma atualização

1. Altere o app em `tools/src.html`
2. Em `version.json`, mude `"latest"` e adicione as novidades no começo de `"versions"`
3. Commit e push — o APK novo sai sozinho em alguns minutos

## Atualizar o mapa (novo DWG)

`tools/extrair_dwg.py` converte o JSON do [LibreDWG](https://www.gnu.org/software/libredwg/) (`dwgread -O JSON`) em `www/data/mapa.json`.
