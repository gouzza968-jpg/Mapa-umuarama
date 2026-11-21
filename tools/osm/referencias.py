"""Encaixa o mapa (coordenadas locais do DWG) no OpenStreetMap e gera os pontos de referência.

Uso: python3 tools/osm/referencias.py www/data/mapa.json dados-osm/umuarama.json.gz

1. Casa os nomes das ruas do mapa com os nomes das ruas do OpenStreetMap.
2. Calcula a transformação (escala, rotação, deslocamento) mapa -> lat/lon,
   começando por RANSAC nos centros das ruas e refinando ponto a ponto (ICP).
3. Converte hospitais, farmácias, mercados, postos, borracharias etc. para o mapa
   e grava em mapa.json: "geo" (transformação) e "pois" (referências).
"""
import json, gzip, base64, math, re, sys, random, unicodedata, collections
import numpy as np

mapa_path, osm_path = sys.argv[1], sys.argv[2]
D = json.load(open(mapa_path, encoding='utf-8'))
S = D['meta']['S']
texts = json.loads(gzip.decompress(base64.b64decode(D['txt'])))
streets = json.loads(gzip.decompress(base64.b64decode(D['streets'])))
osm = json.loads(gzip.open(osm_path).read())['elements']

STOP = {'RUA','R','AV','AVENIDA','DE','DA','DO','DOS','DAS','E','TRAVESSA','TRAV','ALAMEDA','AL','RODOVIA','ESTRADA','PRACA','PROJETADA','PROJ','DR','DOUTOR','PROF','PROFESSOR','PE','PADRE','SAO','SANTA','SANTO','GOV','GOVERNADOR','VER','VEREADOR','CEL','CORONEL','ENG','ENGENHEIRO','DEP','DEPUTADO','PRES','PRESIDENTE','MAL','MARECHAL','GAL','GENERAL','DONA','D','SEN','SENADOR','CAP','CAPITAO','TEN','TENENTE'}
def key(s):
    s = unicodedata.normalize('NFD', s.upper()); s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'\(.*?\)', ' ', s); s = re.split(r'\bDECRETO\b', s)[0]
    w = [x for x in re.sub(r'[^A-Z0-9 ]', ' ', s).split() if x not in STOP]
    return ' '.join(w)

# ---- OSM: projeção local em metros ----
lat0, lon0 = -23.766, -53.325
KX, KY = 111320 * math.cos(math.radians(lat0)), 110540
def proj(lat, lon): return ((lon - lon0) * KX, (lat - lat0) * KY)
def unproj(x, y): return (lat0 + y / KY, lon0 + x / KX)

ways = collections.defaultdict(list)
for e in osm:
    if e['type'] == 'way' and 'highway' in e.get('tags', {}) and e['tags'].get('name') and e.get('geometry'):
        k = key(e['tags']['name'])
        if len(k) >= 3: ways[k].append(np.array([proj(p['lat'], p['lon']) for p in e['geometry']]))
print('ruas OSM', len(ways))

# ---- ruas do mapa ----
mstreets = collections.defaultdict(list)
for name, labs, nums in streets:
    k = key(name)
    if len(k) >= 3: mstreets[k] += [(texts[i][0] / S, texts[i][1] / S) for i in labs]  # metros locais do mapa
common = [k for k in mstreets if k in ways]
print('ruas do mapa', len(mstreets), 'em comum', len(common))

def similarity(A, B):
    """B ~ s*R*A + t (Umeyama)"""
    ma, mb = A.mean(0), B.mean(0); a, b = A - ma, B - mb
    U, Sg, Vt = np.linalg.svd(b.T @ a / len(A)); d = np.sign(np.linalg.det(U @ Vt))
    Dm = np.diag([1, d]); R = U @ Dm @ Vt; s = (Sg * [1, d]).sum() / (a ** 2).sum() * len(A)
    return s, R, mb - s * R @ ma
def apply(T, P): s, R, t = T; return (s * (R @ np.asarray(P).T)).T + t

# centros para RANSAC
A = np.array([np.mean(mstreets[k], 0) for k in common])
B = np.array([np.concatenate(ways[k]).mean(0) for k in common])
best, bestn = None, -1
random.seed(1)
for _ in range(4000):
    i, j = random.sample(range(len(common)), 2)
    if np.linalg.norm(A[i] - A[j]) < 300: continue
    T = similarity(A[[i, j]], B[[i, j]])
    if not (0.8 < T[0] < 1.25): continue
    n = (np.linalg.norm(apply(T, A) - B, axis=1) < 250).sum()
    if n > bestn: best, bestn = T, n
print('RANSAC inliers', bestn, 'escala', round(best[0], 4))

def nearest_on(polys, p):
    bd, bq = 1e18, None
    for P in polys:
        a, b = P[:-1], P[1:]; ab = b - a; L = (ab ** 2).sum(1); L[L == 0] = 1e-9
        t = np.clip(((p - a) * ab).sum(1) / L, 0, 1); q = a + ab * t[:, None]
        d = ((q - p) ** 2).sum(1); i = d.argmin()
        if d[i] < bd: bd, bq = d[i], q[i]
    return bq, math.sqrt(bd)

T = best
for it in range(12):
    src, dst, ds = [], [], []
    for k in common:
        for p in mstreets[k]:
            q, d = nearest_on(ways[k], apply(T, [p])[0])
            src.append(p); dst.append(q); ds.append(d)
    ds = np.array(ds); lim = max(15, 3 * np.median(ds))
    m = ds < lim
    T = similarity(np.array(src)[m], np.array(dst)[m])
    print(f'iteração {it}: pares {m.sum()}/{len(ds)} mediana {np.median(ds):.1f} m  escala {T[0]:.5f}')
res = ds[ds < lim]
print('erro final: mediana %.1f m, 90%% %.1f m' % (np.median(res), np.percentile(res, 90)))

# ---- referências ----
CATS = [
    ('saude', 'Saúde'), ('farmacia', 'Farmácia'), ('mercado', 'Mercado'), ('posto', 'Posto de combustível'),
    ('borracharia', 'Borracharia'), ('oficina', 'Oficina de moto/carro'), ('seguranca', 'Polícia / Bombeiros'),
    ('escola', 'Escola'), ('servico', 'Serviço público / banco'), ('comida', 'Restaurante / lanchonete'), ('igreja', 'Igreja'),
]
CI = {c: i for i, (c, _) in enumerate(CATS)}
def cat_of(t):
    a, sh, nm = t.get('amenity', ''), t.get('shop', ''), t.get('name', '').lower()
    if 'borracharia' in nm or sh == 'tyres': return 'borracharia'
    if a in ('hospital', 'clinic', 'doctors') or t.get('healthcare') and t.get('healthcare') != 'pharmacy': return 'saude'
    if a == 'pharmacy' or t.get('healthcare') == 'pharmacy': return 'farmacia'
    if sh in ('supermarket', 'convenience', 'mall', 'bakery', 'butcher', 'greengrocer', 'department_store') or a == 'marketplace': return 'mercado'
    if a == 'fuel': return 'posto'
    if sh in ('car_repair', 'motorcycle', 'motorcycle_repair'): return 'oficina'
    if a in ('police', 'fire_station'): return 'seguranca'
    if a in ('school', 'university', 'college'): return 'escola'
    if a in ('bank', 'post_office', 'townhall', 'bus_station'): return 'servico'
    if a in ('restaurant', 'fast_food'): return 'comida'
    if a == 'place_of_worship': return 'igreja'
    return None
DEF = {'saude': 'Unidade de saúde', 'farmacia': 'Farmácia', 'mercado': 'Mercado', 'posto': 'Posto de combustível', 'borracharia': 'Borracharia', 'oficina': 'Oficina'}
# inversa: metros OSM -> mapa
s, R, t = T
def to_map(x, y):
    p = R.T @ ((np.array([x, y]) - t) / s)
    return p[0] * S, p[1] * S
W, H = D['meta']['w'], D['meta']['h']
pois, seen = [], set()
for e in osm:
    tg = e.get('tags', {})
    if e['type'] == 'way' and 'highway' in tg: continue
    c = cat_of(tg)
    if not c: continue
    if e['type'] == 'node': lat, lon = e['lat'], e['lon']
    elif e.get('geometry'): lat = np.mean([g['lat'] for g in e['geometry']]); lon = np.mean([g['lon'] for g in e['geometry']])
    elif e.get('bounds'): b = e['bounds']; lat, lon = (b['minlat'] + b['maxlat']) / 2, (b['minlon'] + b['maxlon']) / 2
    else: continue
    name = tg.get('name') or DEF.get(c)
    if not name: continue
    x, y = to_map(*proj(lat, lon))
    if not (0 <= x <= W and 0 <= y <= H): continue
    k = (c, name.lower(), round(x / 200), round(y / 200))
    if k in seen: continue
    seen.add(k)
    addr = ' '.join(v for v in (tg.get('addr:street', ''), tg.get('addr:housenumber', '')) if v).strip()
    pois.append([round(x), round(y), CI[c], name, addr, round(lat, 6), round(lon, 6)])
print('referências', len(pois), collections.Counter(CATS[p[2]][0] for p in pois))

# transformação mapa(unidades) -> metros OSM -> lat/lon, guardada como afim em lat/lon
def map_to_ll(mx, my):
    x, y = apply(T, [[mx / S, my / S]])[0]; return unproj(x, y)
o = map_to_ll(0, 0); ex = map_to_ll(1000, 0); ey = map_to_ll(0, 1000)
D['geo'] = {'lat': [o[0], (ex[0] - o[0]) / 1000, (ey[0] - o[0]) / 1000], 'lon': [o[1], (ex[1] - o[1]) / 1000, (ey[1] - o[1]) / 1000],
            'erro_m': round(float(np.median(res)), 1)}
D['pois'] = pois
D['poicats'] = CATS
json.dump(D, open(mapa_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('ok', D['geo'])
