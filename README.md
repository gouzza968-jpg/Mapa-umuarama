# Mapa Umuarama — app Android

App Android com o **Mapa Oficial de Numeração Predial de Umuarama-PR**, feito para motoboys.

- Escolha do mapa na guia **Explorar** (o atual é o **Mapa 1**); novos mapas publicados em `mapas/catalogo.json` podem ser baixados por dentro do app
- Ao abrir uma rua, campo opcional para procurar o número
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

## Adicionar um novo mapa (Mapa 2, Mapa 3…)

1. Converta o DWG em `mapas/mapa2.json` (mesmo formato de `www/data/mapa.json`)
2. Adicione em `mapas/catalogo.json`:
   ```json
   {"id": "mapa2", "nome": "Mapa 2", "descricao": "…", "cidade": "Umuarama - PR", "url": "mapas/mapa2.json", "tamanho": 2945649}
   ```
3. Commit e push — o app mostra “Novo mapa disponível” e o usuário baixa no botão do mapa, na guia Explorar, sem precisar de APK novo.

## Referências e Mapa 2 (OpenStreetMap)

- `.github/workflows/osm.yml` baixa o extrato do OpenStreetMap do Paraná e recorta Umuarama em `dados-osm/`
- `tools/osm/referencias.py` encaixa o Mapa 1 nas coordenadas reais (erro mediano ~3 m) e grava as referências nele
- `tools/osm/mapa_osm.py` gera o Mapa 2 (`www/data/mapa2.json`) direto do OpenStreetMap
- `tools/osm/rotas.py` gera a malha de ruas para as rotas no app (`www/data/rotas.json`), com mãos únicas e velocidade por tipo de via

## Chat e limpeza automática

- `supabase/chat.sql`: rode uma vez no SQL Editor do Supabase (tabela de mensagens, fotos e regras de segurança)
- `.github/workflows/limpeza.yml`: todo dia apaga fotos com mais de 15 dias (e as mais antigas se passar de 800 MB) e mensagens com mais de 30 dias
- Precisa do segredo `SUPABASE_SERVICE_KEY` em Settings → Secrets and variables → Actions
