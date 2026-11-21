"""Encaixa o Mapa 1 (coordenadas locais do DWG) no OpenStreetMap e grava as referências nele.

Uso: python3 tools/osm/referencias.py www/data/mapa.json dados-osm/umuarama.geojsonseq.gz

1. Casa os nomes das ruas do mapa com os do OpenStreetMap.
2. Calcula escala, rotação e deslocamento (RANSAC nos centros das ruas + refino ponto a ponto).
3. Converte hospitais, farmácias, mercados, postos, borracharias etc. para o mapa.
"""
import json, gzip, base64, math, sys, random, collections, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from comum import proj, unproj, load_features, lines_of, key, pois_from, CATS

mapa_path, osm_path = sys.argv[1], sys.argv[2]
D = json.load(open(mapa_path, encoding='utf-8'))
S = D['meta']['S']
texts = json.loads(gzip.decompress(base64.b64decode(D['txt'])))
streets = json.loads(gzip.decompress(base64.b64decode(D['streets'])))
feats = load_features(osm_path)

ways = collections.defaultdict(list)
for f in feats:
    t = f.get('properties') or {}
    if 'highway' in t and t.get('name'):
        k = key(t['name'])
        if len(k) >= 3:
            for l in lines_of(f['geometry']):
                if len(l) > 1: ways[k].append(np.array([proj(p[1], p[0]) for p in l]))
print('ruas OSM', len(ways))

mstreets = collections.defaultdict(list)
for name, labs, nums in streets:
    k = key(name)
    if len(k) >= 3: mstreets[k] += [(texts[i][0] / S, texts[i][1] / S) for i in labs]
common = [k for k in mstreets if k in ways]
print('ruas do mapa', len(mstreets), 'em comum', len(common))


def similarity(A, B):
    ma, mb = A.mean(0), B.mean(0); a, b = A - ma, B - mb
    U, Sg, Vt = np.linalg.svd(b.T @ a / len(A)); d = np.sign(np.linalg.det(U @ Vt))
    R = U @ np.diag([1, d]) @ Vt; s = (Sg * [1, d]).sum() / (a ** 2).sum() * len(A)
    return s, R, mb - s * R @ ma


def apply(T, P): s, R, t = T; return (s * (R @ np.asarray(P, float).T)).T + t


A = np.array([np.mean(mstreets[k], 0) for k in common])
B = np.array([np.concatenate(ways[k]).mean(0) for k in common])
best, bestn = None, -1
random.seed(1)
for _ in range(5000):
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
    ds = np.array(ds); lim = max(15, 3 * np.median(ds)); m = ds < lim
    T = similarity(np.array(src)[m], np.array(dst)[m])
print('pares', int(m.sum()), 'erro mediano %.1f m, 90%% %.1f m' % (np.median(ds[m]), np.percentile(ds[m], 90)))

s, R, t = T
def to_map(lat, lon):
    p = R.T @ ((np.array(proj(lat, lon)) - t) / s); return p[0] * S, p[1] * S
W, H = D['meta']['w'], D['meta']['h']
pois = pois_from(feats, to_map, lambda x, y: 0 <= x <= W and 0 <= y <= H)
print('referências', len(pois), collections.Counter(CATS[p[2]][0] for p in pois))


def map_to_ll(mx, my):
    x, y = apply(T, [[mx / S, my / S]])[0]; return unproj(x, y)
o, ex, ey = map_to_ll(0, 0), map_to_ll(1000, 0), map_to_ll(0, 1000)
D['georef'] = {'lat': [o[0], (ex[0] - o[0]) / 1000, (ey[0] - o[0]) / 1000], 'lon': [o[1], (ex[1] - o[1]) / 1000, (ey[1] - o[1]) / 1000],
            'erro_m': round(float(np.median(ds[m])), 1)}
D['pois'] = pois
D['poicats'] = CATS
json.dump(D, open(mapa_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('ok', D['georef'])
