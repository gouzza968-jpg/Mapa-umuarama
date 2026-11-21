"""Atualiza o Mapa 1 com dados do OpenStreetMap.

Uso: python3 tools/osm/atualizar_mapa1.py www/data/mapa.json dados-osm/umuarama.geojsonseq.gz

1. Avenidas e rodovias em destaque: desenha o traçado delas (categorias 'avenida' e 'rodovia').
2. Nomes mais atuais: onde o Mapa 1 só tem nome provisório (Rua Projetada A, Rua B...) e o
   OpenStreetMap tem o nome definitivo, troca o rótulo. Onde os nomes diferem, mantém o da
   prefeitura e acrescenta o outro nome como apelido para a busca.
"""
import json, gzip, base64, struct, sys, os, re, math, collections, unicodedata
sys.path.insert(0, os.path.dirname(__file__))
from comum import load_features, lines_of, key

mapa_path, osm_path = sys.argv[1], sys.argv[2]
D = json.load(open(mapa_path, encoding='utf-8'))
meta, S = D['meta'], D['meta']['S']
G = D['georef']
a0, a1, a2 = G['lat']; b0, b1, b2 = G['lon']; det = a1 * b2 - a2 * b1
def to_map(lat, lon):
    dl, dn = lat - a0, lon - b0
    return ((dl * b2 - a2 * dn) / det, (a1 * dn - b1 * dl) / det)
W, H = meta['w'], meta['h']
feats = load_features(osm_path)

# ---------------- 1) traçado de avenidas e rodovias ----------------
ROD = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link'}
def is_av(t):
    n = (t.get('name') or '').strip().lower()
    return n.startswith(('avenida', 'av.', 'av ')) or t.get('highway') in ('secondary', 'secondary_link')
novas = {'rodovia': [], 'avenida': []}
for f in feats:
    t = f.get('properties') or {}
    hw = t.get('highway')
    if not hw or f['geometry']['type'] not in ('LineString', 'MultiLineString'): continue
    ref = (t.get('ref') or '').upper()
    cat = 'rodovia' if (hw in ROD or ref.startswith(('PR-', 'BR-', 'PR ', 'BR '))) else 'avenida' if is_av(t) else None
    if not cat: continue
    for l in lines_of(f['geometry']):
        pts = [to_map(p[1], p[0]) for p in l]
        if any(0 <= x <= W and 0 <= y <= H for x, y in pts): novas[cat].append(pts)

buf = base64.b64decode(D['geo']); raw = gzip.decompress(buf)
allints = struct.unpack('<%di' % (len(raw) // 4), raw)
partes = []
for c, off, n in meta['lines']:
    if c in ('avenida', 'rodovia'): continue
    partes.append((c, list(allints[off // 4: off // 4 + n])))
for c in ('rodovia', 'avenida'):
    ints = []
    for pl in novas[c]:
        q = [(round(x), round(y)) for x, y in pl]
        d = [q[0]] + [p for i, p in enumerate(q[1:]) if p != q[i]]
        if len(d) < 2: continue
        ints.append(len(d))
        for x, y in d: ints += [x, y]
    partes.append((c, ints))
nb = bytearray(); lines = []
for c, ints in partes:
    lines.append([c, len(nb), len(ints)]); nb += struct.pack('<%di' % len(ints), *ints)
meta['lines'] = lines
D['geo'] = base64.b64encode(gzip.compress(bytes(nb), 9)).decode()
print('traçados: rodovias', len(novas['rodovia']), '| avenidas', len(novas['avenida']))

# ---------------- 2) nomes mais atuais ----------------
texts = json.loads(gzip.decompress(base64.b64decode(D['txt'])))
streets = json.loads(gzip.decompress(base64.b64decode(D['streets'])))
TI = {c: i for i, c in enumerate(meta['tcats'])}

segs = []   # (x1,y1,x2,y2,nome) em unidades do mapa
for f in feats:
    t = f.get('properties') or {}
    if not t.get('highway') or not t.get('name'): continue
    for l in lines_of(f['geometry']):
        pts = [to_map(p[1], p[0]) for p in l]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]): segs.append((x1, y1, x2, y2, t['name'].strip()))
CELL = 1000
grid = collections.defaultdict(list)
for i, (x1, y1, x2, y2, _) in enumerate(segs):
    for gx in range(int(min(x1, x2) // CELL), int(max(x1, x2) // CELL) + 1):
        for gy in range(int(min(y1, y2) // CELL), int(max(y1, y2) // CELL) + 1): grid[(gx, gy)].append(i)

def perto(x, y, rot, raio=200):
    best, bd = None, raio
    for gx in range(int((x - raio) // CELL), int((x + raio) // CELL) + 1):
        for gy in range(int((y - raio) // CELL), int((y + raio) // CELL) + 1):
            for i in grid.get((gx, gy), ()):
                x1, y1, x2, y2, nm = segs[i]
                dx, dy = x2 - x1, y2 - y1; L = dx * dx + dy * dy
                if L == 0: continue
                u = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / L))
                d = math.hypot(x - x1 - u * dx, y - y1 - u * dy)
                ang = abs(((math.atan2(dy, dx) - rot) + math.pi / 2) % math.pi - math.pi / 2)
                if d < bd and ang < 0.5: bd, best = d, nm
    return best

def limpo(s):
    s = re.split(r'\s(DEC\.?|DECRETO|LEI)\b', s, flags=re.I)[0]
    s = re.sub(r'\(.*?\)', ' ', s)
    s = unicodedata.normalize('NFD', s.upper()); s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Z0-9 ]', ' ', s).split()
GEN = {'RUA', 'R', 'AV', 'AVENIDA', 'TRAVESSA', 'TRAV', 'ALAMEDA', 'AL', 'PROJETADA', 'PROJ', 'PRACA', 'ESTRADA', 'MARGINAL'}
def provisorio(s):
    """Rua B, Rua 1, Rua Projetada L, Av. Proj. 3 ... (nome genérico + uma letra/número)"""
    w = limpo(s)
    if not w or w[0] not in GEN: return False
    resto = [x for x in w if x not in GEN]
    if len(resto) != 1: return False
    r = resto[0]
    return (len(r) == 1) or (r.isdigit() and len(r) <= 3) or bool(re.fullmatch(r'[A-Z]\d{0,2}|\d{1,3}[A-Z]?', r))

lab_street = {}
for si, (nm, labs, nums) in enumerate(streets):
    for i in labs: lab_street[i] = si
trocados, votos = 0, collections.defaultdict(collections.Counter)
for i, t in enumerate(texts):
    if t[6] != TI['rua'] or len(t[7]) < 5: continue          # ignora letras soltas e pedaços de rótulo
    osm = perto(t[0], t[1], t[3])
    if not osm or provisorio(osm) or key(osm) == key(t[7]): continue
    if provisorio(t[7]):
        t[7] = osm; trocados += 1
        si = lab_street.get(i)
        if si is not None and provisorio(streets[si][0]): streets[si][0] = osm
    elif i in lab_street:
        votos[lab_street[i]][osm] += 1
# apelido só quando pelo menos 2 rótulos da mesma rua apontam para o mesmo nome do OpenStreetMap
apelidos = collections.defaultdict(set)
for si, c in votos.items():
    nome, n = c.most_common(1)[0]
    if n >= 2 and n >= 0.6 * sum(c.values()): apelidos[nome].add(si)
# apelidos de busca: outro nome apontando para os mesmos rótulos e números
for nome, sis in apelidos.items():
    labs = sorted({i for si in sis for i in streets[si][1]}); nums = sorted({i for si in sis for i in streets[si][2]})
    streets.append([nome, labs, nums, 1])   # 4º campo = apelido
print('rótulos trocados (provisório -> nome atual):', trocados, '| nomes alternativos na busca:', len(apelidos))

D['txt'] = base64.b64encode(gzip.compress(json.dumps(texts, ensure_ascii=False, separators=(',', ':')).encode(), 9)).decode()
D['streets'] = base64.b64encode(gzip.compress(json.dumps(streets, ensure_ascii=False, separators=(',', ':')).encode(), 9)).decode()
json.dump(D, open(mapa_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('ok')
