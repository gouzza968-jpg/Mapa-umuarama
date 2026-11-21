"""Limpeza automática do chat (roda todo dia pelo GitHub Actions).

- Apaga fotos com mais de DIAS_FOTOS dias.
- Se o total de fotos passar de LIMITE_MB, apaga as mais antigas até ficar em ALVO_MB.
- Nas mensagens cujas fotos foram apagadas, troca a foto por "📷 Foto expirada".
- Apaga mensagens com mais de DIAS_MSG dias.

Variáveis de ambiente: SUPABASE_URL, SUPABASE_SERVICE_KEY (segredo do GitHub, nunca no código).
"""
import os, json, urllib.request, urllib.parse, datetime

URL = os.environ['SUPABASE_URL'].rstrip('/')
KEY = os.environ['SUPABASE_SERVICE_KEY']
BUCKET = 'chat-fotos'
DIAS_FOTOS = int(os.environ.get('DIAS_FOTOS', 15))
DIAS_MSG = int(os.environ.get('DIAS_MSG', 30))
LIMITE = int(os.environ.get('LIMITE_MB', 800)) * 1024 * 1024
ALVO = int(os.environ.get('ALVO_MB', 700)) * 1024 * 1024
SECO = os.environ.get('SIMULAR') == '1'   # só mostra o que faria


def req(method, path, body=None, headers=None):
    h = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'}
    h.update(headers or {})
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(URL + path, data=data, method=method, headers=h)
    with urllib.request.urlopen(r, timeout=60) as resp:
        txt = resp.read().decode() or 'null'
        return json.loads(txt)


def listar(prefix=''):
    out, off = [], 0
    while True:
        lote = req('POST', f'/storage/v1/object/list/{BUCKET}', {'prefix': prefix, 'limit': 1000, 'offset': off, 'sortBy': {'column': 'created_at', 'order': 'asc'}})
        out += lote
        if len(lote) < 1000: return out
        off += 1000


agora = datetime.datetime.now(datetime.timezone.utc)
def quando(s):
    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00')) if s else agora

# ---- fotos ----
fotos = []
for pasta in listar(''):
    if pasta.get('id'):     # arquivo solto na raiz
        fotos.append((pasta['name'], pasta)); continue
    for f in listar(pasta['name'] + '/'):
        if f.get('id'): fotos.append((pasta['name'] + '/' + f['name'], f))
fotos.sort(key=lambda x: quando(x[1].get('created_at')))
tam = lambda f: int((f.get('metadata') or {}).get('size') or 0)
total = sum(tam(f) for _, f in fotos)
print(f'fotos: {len(fotos)}, total {total / 1048576:.1f} MB')

apagar = [p for p, f in fotos if (agora - quando(f.get('created_at'))).days >= DIAS_FOTOS]
restante = total - sum(tam(f) for p, f in fotos if p in set(apagar))
if restante > LIMITE:
    for p, f in fotos:
        if restante <= ALVO: break
        if p in apagar: continue
        apagar.append(p); restante -= tam(f)
print(f'apagar {len(apagar)} fotos; ficará com {restante / 1048576:.1f} MB')

if apagar and not SECO:
    for i in range(0, len(apagar), 500):
        req('DELETE', f'/storage/v1/object/{BUCKET}', {'prefixes': apagar[i:i + 500]})
    # mensagens que apontavam para essas fotos
    urls = {f'{URL}/storage/v1/object/public/{BUCKET}/{p}' for p in apagar}
    msgs = req('GET', '/rest/v1/mensagens?select=id,foto,texto&foto=not.is.null&limit=10000')
    vazias = [m['id'] for m in msgs if m['foto'] in urls and not (m.get('texto') or '').strip()]
    comtexto = [m['id'] for m in msgs if m['foto'] in urls and (m.get('texto') or '').strip()]
    for ids, body in ((vazias, {'foto': None, 'texto': '📷 Foto expirada'}), (comtexto, {'foto': None})):
        for i in range(0, len(ids), 200):
            q = 'id=in.(' + ','.join(map(str, ids[i:i + 200])) + ')'
            req('PATCH', '/rest/v1/mensagens?' + q, body, {'Prefer': 'return=minimal'})
    print(f'mensagens atualizadas: {len(vazias) + len(comtexto)}')
    # áudios apagados
    try:
        aud = req('GET', '/rest/v1/mensagens?select=id,audio,texto&audio=not.is.null&limit=10000')
        ids = [m['id'] for m in aud if m['audio'] in urls]
        for i in range(0, len(ids), 200):
            q = 'id=in.(' + ','.join(map(str, ids[i:i + 200])) + ')'
            req('PATCH', '/rest/v1/mensagens?' + q, {'audio': None, 'audio_onda': None, 'texto': '🎤 Áudio expirado'}, {'Prefer': 'return=minimal'})
        print(f'áudios expirados: {len(ids)}')
    except Exception as e:
        print('áudios: coluna ainda não existe', e)

# ---- mensagens antigas ----
corte = (agora - datetime.timedelta(days=DIAS_MSG)).isoformat()
if not SECO:
    req('DELETE', '/rest/v1/mensagens?criado_em=lt.' + urllib.parse.quote(corte), headers={'Prefer': 'return=minimal'})
print(f'mensagens com mais de {DIAS_MSG} dias apagadas' + (' (simulação)' if SECO else ''))
