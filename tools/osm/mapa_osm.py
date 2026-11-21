"""Gera um mapa do app (mesmo formato de www/data/mapa.json) a partir do OpenStreetMap.

Uso: python3 tools/osm/mapa_osm.py dados-osm/umuarama.geojsonseq.gz mapas/mapa2.json
"""
import json, gzip, base64, math, struct, sys, os, re, collections
sys.path.insert(0, os.path.dirname(__file__))
from comum import proj, unproj, load_features, lines_of, centroid, key, pois_from, CATS

src, out = sys.argv[1], sys.argv[2]
feats = load_features(src)
S = 10  # decímetros

VIA = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link'}
RUA = {'tertiary', 'tertiary_link', 'residential', 'unclassified', 'living_street', 'pedestrian', 'road'}
OUTRO = {'service', 'track'}
LCATS = ['rio', 'verde', 'lote', 'quadra', 'via', 'bairro', 'num', 'circ', 'outro', 'rodovia', 'avenida']
TCATS = ['rua', 'num', 'quadra', 'lote', 'bairro', 'rio', 'local', 'outro']
TI = {c: i for i, c in enumerate(TCATS)}

lines = collections.defaultdict(list)   # cat -> [[(x,y),...]] em metros locais
named = collections.defaultdict(list)   # nome -> [[(x,y),...]]
texts = []                              # (x, y, h, rot, ha, va, cat, texto) em metros
for f in feats:
    t = f.get('properties') or {}; g = f['geometry']
    hw = t.get('highway')
    if hw in VIA or hw in RUA or hw in OUTRO:
        ref = (t.get('ref') or '').upper(); nm = (t.get('name') or '').lower()
        c = ('rodovia' if hw in ('motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link') or ref.startswith(('PR', 'BR'))
             else 'avenida' if hw in ('secondary', 'secondary_link') or nm.startswith(('avenida', 'av.', 'av '))
             else 'via' if hw in VIA else 'quadra' if hw in RUA else 'outro')
        for l in lines_of(g):
            pts = [proj(p[1], p[0]) for p in l]
            if len(pts) > 1:
                lines[c].append(pts)
                if t.get('name') and hw not in OUTRO: named[t['name']].append(pts)
    elif t.get('waterway') in ('river', 'stream', 'canal', 'drain') and g['type'] in ('LineString', 'MultiLineString'):
        for l in lines_of(g): lines['rio'].append([proj(p[1], p[0]) for p in l])
        if t.get('name'):
            l = lines_of(g)[0]; m = l[len(l) // 2]; x, y = proj(m[1], m[0]); texts.append((x, y, 4, 0, 1, 2, TI['rio'], t['name']))
    elif t.get('leisure') == 'park':
        for l in lines_of(g): lines['verde'].append([proj(p[1], p[0]) for p in l])
    if t.get('place') in ('suburb', 'neighbourhood', 'quarter') and t.get('name') and g['type'] == 'Point':
        x, y = proj(g['coordinates'][1], g['coordinates'][0]); texts.append((x, y, 18, 0, 1, 2, TI['bairro'], t['name']))

# nomes das ruas: no meio de trechos longos, alinhados à rua
lab_of = collections.defaultdict(list)
for name, segs in named.items():
    total = 0
    for pts in segs:
        L = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
        acc, nxt = 0, 60
        for i, l in enumerate(L):
            while acc + l >= nxt and l > 0:
                u = (nxt - acc) / l
                x = pts[i][0] + u * (pts[i + 1][0] - pts[i][0]); y = pts[i][1] + u * (pts[i + 1][1] - pts[i][1])
                rot = math.atan2(pts[i + 1][1] - pts[i][1], pts[i + 1][0] - pts[i][0])
                if l > 20:
                    lab_of[name].append(len(texts)); texts.append((x, y, 2.4, rot, 1, 2, TI['rua'], name))
                nxt += 350
            acc += l
        total += sum(L)
    if not lab_of[name] and segs:   # rua curta: um rótulo no meio
        pts = max(segs, key=len); i = max(0, len(pts) // 2 - 1)
        rot = math.atan2(pts[i + 1][1] - pts[i][1], pts[i + 1][0] - pts[i][0])
        lab_of[name].append(len(texts)); texts.append(((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2, 2.4, rot, 1, 2, TI['rua'], name))

# numeração (addr:housenumber)
nums_of = collections.defaultdict(list)
nkey = {key(n): n for n in named}
for f in feats:
    t = f.get('properties') or {}
    if not t.get('addr:housenumber'): continue
    ll = centroid(f['geometry'])
    if not ll: continue
    x, y = proj(*ll)
    st = nkey.get(key(t.get('addr:street', '')))
    if st: nums_of[st].append(len(texts))
    texts.append((x, y, 2.5, 0, 1, 2, TI['num'], t['addr:housenumber']))

# limites: área com ruas
xs = sorted(p[0] for c in ('quadra', 'via') for l in lines[c] for p in l)
ys = sorted(p[1] for c in ('quadra', 'via') for l in lines[c] for p in l)
q = lambda a, f: a[int((len(a) - 1) * f)]
minx, maxx, miny, maxy = q(xs, .002) - 300, q(xs, .998) + 300, q(ys, .002) - 300, q(ys, .998) + 300
inb = lambda x, y: minx <= x <= maxx and miny <= y <= maxy
W, H = round((maxx - minx) * S), round((maxy - miny) * S)

buf = bytearray(); header = []
for c in LCATS:
    ints = []
    for pl in lines.get(c, []):
        if not any(inb(x, y) for x, y in pl): continue
        qd = [(round((x - minx) * S), round((y - miny) * S)) for x, y in pl]
        d = [qd[0]] + [p for i, p in enumerate(qd[1:]) if p != qd[i]]
        if len(d) < 2: continue
        ints.append(len(d))
        for x, y in d: ints += [x, y]
    header.append([c, len(buf), len(ints)])
    buf += struct.pack('<%di' % len(ints), *ints)

keep = [i for i, t in enumerate(texts) if inb(t[0], t[1])]
newidx = {o: n for n, o in enumerate(keep)}
tj = [[round((texts[i][0] - minx) * S), round((texts[i][1] - miny) * S), round(texts[i][2] * S), round(texts[i][3], 3), texts[i][4], texts[i][5], texts[i][6], texts[i][7]] for i in keep]
streets = []
for name in named:
    labs = [newidx[i] for i in lab_of[name] if i in newidx]
    if not labs: continue
    streets.append([name, labs, [newidx[i] for i in nums_of.get(name, []) if i in newidx]])

def to_map(lat, lon):
    x, y = proj(lat, lon); return (x - minx) * S, (y - miny) * S
pois = pois_from(feats, to_map, lambda x, y: 0 <= x <= W and 0 <= y <= H)

o = unproj(minx, miny)
D = {
    'meta': {'w': W, 'h': H, 'S': S, 'lines': header, 'tcats': TCATS},
    'georef': {'lat': [o[0], 0, 1 / (S * 110540)], 'lon': [o[1], 1 / (S * 111320 * math.cos(math.radians(-23.766))), 0], 'erro_m': 0},
    'geo': base64.b64encode(gzip.compress(bytes(buf), 9)).decode(),
    'txt': base64.b64encode(gzip.compress(json.dumps(tj, ensure_ascii=False, separators=(',', ':')).encode(), 9)).decode(),
    'streets': base64.b64encode(gzip.compress(json.dumps(streets, ensure_ascii=False, separators=(',', ':')).encode(), 9)).decode(),
    'pois': pois, 'poicats': CATS,
}
json.dump(D, open(out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('mapa OSM:', W, 'x', H, '| ruas', len(streets), '| textos', len(tj), '| referências', len(pois), collections.Counter(CATS[p[2]][0] for p in pois))
