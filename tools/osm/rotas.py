"""Gera a malha de ruas para calcular rotas no app (a partir do OpenStreetMap).

Uso: python3 tools/osm/rotas.py dados-osm/umuarama.geojsonseq.gz www/data/rotas.json

Saída (tudo em base64 de inteiros little-endian):
  (cada vetor vai compactado com gzip)
  xy   Int32[2N]  coordenadas em decímetros na projeção local (comum.proj)
  off  Int32[N+1] início das arestas de cada nó (CSR)
  to   Int32[E]   nó de destino
  t    Int32[E]   tempo em décimos de segundo
  d    Int32[E]   distância em decímetros
"""
import sys, os, json, math, base64, struct, collections
sys.path.insert(0, os.path.dirname(__file__))
from comum import proj, load_features

SPEED = {  # km/h para moto em área urbana
    'motorway': 80, 'trunk': 70, 'primary': 55, 'secondary': 50, 'tertiary': 40, 'unclassified': 35,
    'residential': 30, 'living_street': 15, 'service': 15, 'track': 15, 'road': 30,
}
src, out = sys.argv[1], sys.argv[2]
feats = load_features(src)
nid, xy = {}, []
def node(lon, lat):
    k = (round(lon * 1e7), round(lat * 1e7))
    if k not in nid:
        nid[k] = len(xy); x, y = proj(lat, lon); xy.append((x, y))
    return nid[k]

edges = []  # (a, b, tempo_s, dist_m)
for f in feats:
    t = f.get('properties') or {}
    hw = t.get('highway', '')
    base = hw.replace('_link', '')
    if base not in SPEED or f['geometry']['type'] != 'LineString': continue
    if t.get('access') in ('no', 'private') or t.get('motor_vehicle') == 'no' or t.get('motorcycle') == 'no': continue
    v = SPEED[base] * (0.8 if hw.endswith('_link') else 1)
    try:
        ms = float(str(t.get('maxspeed', '')).split()[0])
        if 5 <= ms <= 110: v = min(v * 1.2, ms) if base in ('residential', 'service') else ms * 0.85
    except (ValueError, IndexError): pass
    ow = t.get('oneway', '')
    fwd, back = True, True
    if ow in ('yes', 'true', '1') or t.get('junction') in ('roundabout', 'circular'): back = False
    elif ow == '-1': fwd = False
    if t.get('oneway:motorcycle') == 'no': fwd = back = True
    pts = f['geometry']['coordinates']
    ids = [node(p[0], p[1]) for p in pts]
    for a, b in zip(ids, ids[1:]):
        if a == b: continue
        d = math.hypot(xy[a][0] - xy[b][0], xy[a][1] - xy[b][1])
        tm = d / (v / 3.6)
        if fwd: edges.append((a, b, tm, d))
        if back: edges.append((b, a, tm, d))
N = len(xy)
print('nós', N, 'arestas', len(edges))

# maior componente (ignorando sentido) — evita encaixar o destino num trecho solto
adj = collections.defaultdict(list)
for a, b, *_ in edges: adj[a].append(b); adj[b].append(a)
comp = [-1] * N; best, bestc = 0, -1; c = 0
for s in range(N):
    if comp[s] != -1 or s not in adj: continue
    st = [s]; comp[s] = c; n = 0
    while st:
        u = st.pop(); n += 1
        for w in adj[u]:
            if comp[w] == -1: comp[w] = c; st.append(w)
    if n > best: best, bestc = n, c
    c += 1
keep = [i for i in range(N) if comp[i] == bestc]
remap = {o: n for n, o in enumerate(keep)}
E = sorted((remap[a], remap[b], tm, d) for a, b, tm, d in edges if a in remap and b in remap)
print('maior componente: nós', len(keep), 'arestas', len(E))
off = [0] * (len(keep) + 1)
for a, *_ in E: off[a + 1] += 1
for i in range(len(keep)): off[i + 1] += off[i]
import gzip
pack = lambda arr: base64.b64encode(gzip.compress(struct.pack('<%di' % len(arr), *arr), 9)).decode()
xyi = [v for i in keep for v in (round(xy[i][0] * 10), round(xy[i][1] * 10))]
D = {'versao': 1, 'n': len(keep), 'xy': pack(xyi), 'off': pack(off), 'to': pack([b for _, b, _, _ in E]),
     't': pack([max(1, round(tm * 10)) for *_, tm, _ in E]), 'd': pack([max(1, round(d * 10)) for *_, d in E])}
json.dump(D, open(out, 'w'), separators=(',', ':'))
print('ok', os.path.getsize(out) // 1024, 'KB')
