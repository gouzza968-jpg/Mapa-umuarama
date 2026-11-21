"""Monta o Mapa Principal: o Mapa 1 (prefeitura) completado com outras fontes abertas.

Uso: python3 tools/osm/mapa_principal.py www/data/mapa.json dados-osm/umuarama.geojsonseq.gz dados-extras www/data/principal.json

Fontes mescladas:
  - Mapa 1 (prefeitura): quadras, lotes, numeração e nomes (já com nomes atuais, avenidas e rodovias)
  - OpenStreetMap: ruas de loteamentos novos que o Mapa 1 ainda não tem
  - IBGE CNEFE 2022: números de casas e prédios com coordenadas (onde o Mapa 1 não tem o número)
  - Overture Maps e CNEFE: comércios e estabelecimentos com nome (para a busca e a camada "Comércios")
"""
import json, gzip, base64, struct, sys, os, re, math, csv, io, collections, unicodedata
sys.path.insert(0, os.path.dirname(__file__))
from comum import load_features, lines_of, key

mapa_path, osm_path, extras, out_path = sys.argv[1:5]
D = json.load(open(mapa_path, encoding='utf-8'))
meta, S = D['meta'], D['meta']['S']
G = D['georef']
a0, a1, a2 = G['lat']; b0, b1, b2 = G['lon']; det = a1 * b2 - a2 * b1
def to_map(lat, lon):
    dl, dn = lat - a0, lon - b0
    return ((dl * b2 - a2 * dn) / det, (a1 * dn - b1 * dl) / det)
W, H = meta['w'], meta['h']
M = S   # unidades do mapa por metro (decímetros)
inside = lambda x, y: -2000 <= x <= W + 2000 and -2000 <= y <= H + 2000

texts = json.loads(gzip.decompress(base64.b64decode(D['txt'])))
streets = json.loads(gzip.decompress(base64.b64decode(D['streets'])))
TI = {c: i for i, c in enumerate(meta['tcats'])}
raw = gzip.decompress(base64.b64decode(D['geo']))
allints = struct.unpack('<%di' % (len(raw) // 4), raw)
partes = [(c, list(allints[off // 4: off // 4 + n])) for c, off, n in meta['lines']]

def polylines(ints):
    i = 0
    while i < len(ints):
        n = ints[i]; yield [(ints[i + 1 + 2 * k], ints[i + 2 + 2 * k]) for k in range(n)]; i += 1 + 2 * n

# ---------- grade das quadras e lotes do Mapa 1 (área já mapeada) ----------
CELL = 1000
cob = collections.defaultdict(list)
for c, ints in partes:
    if c not in ('quadra', 'lote'): continue
    for pl in polylines(ints):
        for (x1, y1), (x2, y2) in zip(pl, pl[1:]):
            for gx in range(int(min(x1, x2) // CELL), int(max(x1, x2) // CELL) + 1):
                for gy in range(int(min(y1, y2) // CELL), int(max(y1, y2) // CELL) + 1): cob[(gx, gy)].append((x1, y1, x2, y2))
def dist_cob(x, y, raio):
    bd = raio
    for gx in range(int((x - raio) // CELL), int((x + raio) // CELL) + 1):
        for gy in range(int((y - raio) // CELL), int((y + raio) // CELL) + 1):
            for x1, y1, x2, y2 in cob.get((gx, gy), ()):
                dx, dy = x2 - x1, y2 - y1; L = dx * dx + dy * dy
                u = 0 if L == 0 else max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / L))
                bd = min(bd, math.hypot(x - x1 - u * dx, y - y1 - u * dy))
    return bd

# ---------- 1) ruas novas do OpenStreetMap ----------
HW = {'residential', 'living_street', 'tertiary', 'secondary', 'primary', 'unclassified', 'service', 'trunk', 'pedestrian', 'road'}
feats = load_features(osm_path)
por_nome = collections.defaultdict(list)
for f in feats:
    t = f.get('properties') or {}
    if t.get('highway') not in HW or not t.get('name'): continue
    if f['geometry']['type'] not in ('LineString', 'MultiLineString'): continue
    for l in lines_of(f['geometry']):
        pts = [to_map(p[1], p[0]) for p in l]
        if not any(inside(x, y) for x, y in pts): continue
        # amostra a cada ~10 m; trecho "novo" = pontos a mais de 35 m de qualquer quadra/lote do Mapa 1
        amostra = []
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(x2 - x1, y2 - y1) // 100))
            amostra += [(x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n) for k in range(n)]
        novos = sum(1 for x, y in amostra if dist_cob(x, y, 350) >= 350)
        if novos >= 0.7 * len(amostra) and len(amostra) >= 3: por_nome[t['name'].strip()].append(pts)

nome_si = collections.defaultdict(list)   # chave -> índices de ruas
for si, s in enumerate(streets): nome_si[key(s[0])].append(si)
via_nova = []; ruas_novas = 0
for nome, pls in por_nome.items():
    labs = []
    for pts in pls:
        via_nova.append(pts)
        L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
        if L < 300: continue
        # rótulo no meio do trecho, alinhado com a rua
        acc, alvo = 0, L / 2
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            d = math.hypot(x2 - x1, y2 - y1)
            if acc + d >= alvo and d > 0:
                u = (alvo - acc) / d; ang = math.atan2(y2 - y1, x2 - x1)
                if ang > math.pi / 2: ang -= math.pi
                if ang < -math.pi / 2: ang += math.pi
                labs.append(len(texts)); texts.append([round(x1 + u * (x2 - x1)), round(y1 + u * (y2 - y1)), 40, round(ang % (2 * math.pi), 3), 1, 2, TI['rua'], nome.upper()])
                break
            acc += d
    if not labs: continue
    k = key(nome)
    if nome_si.get(k):
        for si in nome_si[k]: streets[si][1] += labs
    else:
        nome_si[k].append(len(streets)); streets.append([nome.upper(), labs, []]); ruas_novas += 1
ints = []
for pl in via_nova:
    q = [(round(x), round(y)) for x, y in pl]
    d = [q[0]] + [p for i, p in enumerate(q[1:]) if p != q[i]]
    if len(d) < 2: continue
    ints.append(len(d))
    for x, y in d: ints += [x, y]
partes = [(c, (v + ints) if c == 'via' else v) for c, v in partes]
print('OpenStreetMap: ruas novas', ruas_novas, '| trechos', len(via_nova))

# ---------- 1b) nomes atuais em ruas sem nome no Mapa 1 (os mesmos nomes do Mapa 3 / OpenStreetMap) ----------
RG = 300
ruagrid = collections.defaultdict(list)
for i, t in enumerate(texts):
    if t[6] == TI['rua']: ruagrid[(int(t[0] // RG), int(t[1] // RG))].append(i)
def rotulos_perto(x, y, raio):
    out = []
    for gx in range(int((x - raio) // RG), int((x + raio) // RG) + 1):
        for gy in range(int((y - raio) // RG), int((y + raio) // RG) + 1):
            for i in ruagrid.get((gx, gy), ()):
                if math.hypot(texts[i][0] - x, texts[i][1] - y) < raio: out.append(i)
    return out
nomeados, rot_novos = set(), 0
for f in feats:
    t = f.get('properties') or {}
    if t.get('highway') not in HW or not t.get('name') or f['geometry']['type'] not in ('LineString', 'MultiLineString'): continue
    nome = t['name'].strip(); k = key(nome)
    for l in lines_of(f['geometry']):
        pts = [to_map(p[1], p[0]) for p in l]
        if not any(inside(x, y) for x, y in pts): continue
        acc, prox = 0, 900   # um ponto a cada ~180 m do trecho (o primeiro a 90 m do início)
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            d = math.hypot(x2 - x1, y2 - y1)
            while d > 0 and acc + d >= prox:
                u = (prox - acc) / d; x, y = x1 + u * (x2 - x1), y1 + u * (y2 - y1); prox += 1800
                if dist_cob(x, y, 350) >= 350: continue                 # fora da área do Mapa 1 (já tratado acima)
                if rotulos_perto(x, y, 1300): continue                   # já tem nome de rua por perto
                ang = math.atan2(y2 - y1, x2 - x1)
                if ang > math.pi / 2: ang -= math.pi
                if ang < -math.pi / 2: ang += math.pi
                i = len(texts); texts.append([round(x), round(y), 40, round(ang % (2 * math.pi), 3), 1, 2, TI['rua'], nome.upper()])
                ruagrid[(int(x // RG), int(y // RG))].append(i); rot_novos += 1
                if nome_si.get(k):
                    for si in nome_si[k]: streets[si][1].append(i)
                else:
                    nome_si[k].append(len(streets)); streets.append([nome.upper(), [i], []]); nomeados.add(k)
            acc += d
print('Ruas sem nome no Mapa 1 que ganharam nome:', rot_novos, 'rótulos |', len(nomeados), 'ruas novas na busca')

# ---------- 2) números do IBGE CNEFE 2022 ----------
rows = list(csv.DictReader(io.StringIO(gzip.open(os.path.join(extras, 'cnefe_umuarama.csv.gz'), 'rt', encoding='utf-8').read()), delimiter=';'))
def centro(si):
    ls = [texts[i] for i in streets[si][1] + streets[si][2]]
    return [(t[0], t[1]) for t in ls]
NUMG = 400
numgrid = collections.defaultdict(list)
for i, t in enumerate(texts):
    if t[6] == TI['num']: numgrid[(int(t[0] // NUMG), int(t[1] // NUMG))].append(i)
def num_perto(x, y, raio):
    for gx in range(int((x - raio) // NUMG), int((x + raio) // NUMG) + 1):
        for gy in range(int((y - raio) // NUMG), int((y + raio) // NUMG) + 1):
            for i in numgrid.get((gx, gy), ()):
                if math.hypot(texts[i][0] - x, texts[i][1] - y) < raio: return True
    return False
ja = set()
for si, s in enumerate(streets):
    for i in s[2]: ja.add((key(s[0]), texts[i][7].lstrip('0')))
cache_rua = {}
NUMS = {'UM': '1', 'UMA': '1', 'DOIS': '2', 'TRES': '3', 'QUATRO': '4', 'CINCO': '5', 'SEIS': '6', 'SETE': '7', 'OITO': '8', 'NOVE': '9', 'DEZ': '10',
        'ONZE': '11', 'DOZE': '12', 'TREZE': '13', 'QUATORZE': '14', 'CATORZE': '14', 'QUINZE': '15', 'DEZESSEIS': '16', 'DEZESSETE': '17',
        'DEZOITO': '18', 'DEZENOVE': '19', 'VINTE': '20', 'TRINTA': '30', 'PRIMEIRO': '1'}
IGN = {'ANTIGA', 'NORTE', 'SUL', 'PROL', 'PROLONG', 'PROLONGAMENTO', 'GEN', 'C', 'JR', 'JUNIOR', 'FILHO', 'NETO', 'A', 'O', 'OS', 'AS', 'PAPA'}
def nucleo(k):
    w = [NUMS.get(x, x) for x in k.split()]
    out = []
    for x in w:   # "20 1" -> "21"
        if out and out[-1] in ('20', '30') and x.isdigit() and len(x) == 1: out[-1] = str(int(out[-1]) + int(x))
        else: out.append(x)
    return frozenset(x for x in out if x not in IGN and len(x) > 1 or x.isdigit())
nuc_si = collections.defaultdict(list)
for si, st_ in enumerate(streets): nuc_si[nucleo(key(st_[0]))].append(si)
todos_nuc = list(nuc_si.items())
cache_cand = {}
def candidatas(k):
    if k in cache_cand: return cache_cand[k]
    n = nucleo(k); c = set(nome_si.get(k, ())) | set(nuc_si.get(n, ()))
    if not c and len(n) >= 2:   # mesmo nome com palavras a mais ou a menos (ex.: "Cássio Gastão Vidigal" x "Gastão Vidigal")
        for nn, sis in todos_nuc:
            if len(nn) >= 2 and (nn <= n or n <= nn): c |= set(sis)
    cache_cand[k] = [si for si in c if not (len(streets[si]) > 3 and streets[si][3])] or [si for si in c]
    return cache_cand[k]
def rua_de(nome_cnefe, x, y):
    """Escolhe a rua do mapa com o mesmo nome mais próxima do endereço (até 1,5 km de um rótulo ou número dela)."""
    k = key(nome_cnefe)
    cands = candidatas(k)
    best, bd = None, 15000
    for si in cands:
        if si not in cache_rua: cache_rua[si] = centro(si)
        for px, py in cache_rua[si]:
            d = math.hypot(px - x, py - y)
            if d < bd: bd, best = d, si
    return best, k
add_num, sem_rua, novas_cnefe = 0, 0, {}
for r in rows:
    n = (r['NUM_ENDERECO'] or '').strip().lstrip('0')
    if not n or r['NV_GEO_COORD'] not in ('1', '2'): continue    # só coordenadas do endereço ou da face da quadra
    try: lat, lon = float(r['LATITUDE']), float(r['LONGITUDE'])
    except ValueError: continue
    x, y = to_map(lat, lon)
    if not inside(x, y): continue
    nome = ' '.join(v for v in (r['NOM_TIPO_SEGLOGR'], r['NOM_TITULO_SEGLOGR'], r['NOM_SEGLOGR']) if v).strip()
    si, k = rua_de(nome, x, y)
    if (k, n) in ja: continue
    if num_perto(x, y, 60): ja.add((k, n)); continue        # o Mapa 1 já tem um número aqui
    ja.add((k, n))
    idx = len(texts); texts.append([round(x), round(y), 22, 0, 1, 2, TI['num'], n])
    numgrid[(int(x // NUMG), int(y // NUMG))].append(idx)
    if si is None:
        si = novas_cnefe.get(k)
        if si is None:
            si = len(streets); streets.append([nome.upper(), [], []]); novas_cnefe[k] = si; nome_si[k].append(si); sem_rua += 1
        streets[si][1].append(idx)
    streets[si][2].append(idx); add_num += 1
print('IBGE CNEFE: números acrescentados', add_num, '| ruas só do IBGE', sem_rua)

# ---------- 3) comércios e estabelecimentos ----------
cats = [c for c, _ in D['poicats']]
if 'comercio' not in cats: D['poicats'].append(['comercio', 'Comércios e empresas']); cats.append('comercio')
CI = {c: i for i, c in enumerate(cats)}
OV = {'pharmacy': 'farmacia', 'hospital': 'saude', 'clinic': 'saude', 'doctor': 'saude', 'dentist': 'saude', 'medical_center': 'saude',
      'supermarket': 'mercado', 'grocery_store': 'mercado', 'convenience_store': 'mercado', 'bakery': 'mercado', 'butcher_shop': 'mercado',
      'gas_station': 'posto', 'tire_shop': 'borracharia', 'tire_dealer_and_repair': 'borracharia', 'automotive_repair': 'oficina',
      'car_repair': 'oficina', 'motorcycle_repair': 'oficina', 'police_station': 'seguranca', 'fire_station': 'seguranca',
      'school': 'escola', 'college_university': 'escola', 'bank': 'servico', 'post_office': 'servico', 'restaurant': 'comida',
      'fast_food_restaurant': 'comida', 'pizza_restaurant': 'comida', 'burger_restaurant': 'comida', 'cafe': 'comida',
      'church': 'igreja', 'place_of_worship': 'igreja'}
pois = D['pois']
pg = collections.defaultdict(list)
def nk(s): s = unicodedata.normalize('NFD', s.upper()); return re.sub(r'[^A-Z0-9]', '', ''.join(c for c in s if unicodedata.category(c) != 'Mn'))
def repetido(x, y, nome):
    k = nk(nome)[:10]
    for gx in (int(x // 1000) - 1, int(x // 1000), int(x // 1000) + 1):
        for gy in (int(y // 1000) - 1, int(y // 1000), int(y // 1000) + 1):
            for px, py, pk in pg.get((gx, gy), ()):
                if math.hypot(px - x, py - y) < 800 and (pk[:6] == k[:6]): return True
    return False
def guarda(x, y, nome): pg[(int(x // 1000), int(y // 1000))].append((x, y, nk(nome)[:10]))
for p in pois: guarda(p[0], p[1], p[3])
n_ov = n_cn = 0
ov = json.load(gzip.open(os.path.join(extras, 'overture_lugares.geojson.gz'), 'rt', encoding='utf-8'))['features']
for f in ov:
    pr = f.get('properties') or {}
    if (pr.get('confidence') or 0) < 0.6 or f['geometry']['type'] != 'Point': continue
    nome = ((pr.get('names') or {}).get('primary') or '').strip()
    if len(nome) < 3: continue
    lon, lat = f['geometry']['coordinates'][:2]
    x, y = to_map(lat, lon)
    if not inside(x, y) or repetido(x, y, nome): continue
    bc = pr.get('basic_category') or ((pr.get('taxonomy') or {}).get('primary')) or ''
    c = OV.get(bc, 'comercio')
    ad = (pr.get('addresses') or [{}])[0].get('freeform') or ''
    pois.append([round(x), round(y), CI[c], nome, ad, round(lat, 6), round(lon, 6)]); guarda(x, y, nome); n_ov += 1
ESP = {'4': 'escola', '5': 'saude', '8': 'igreja'}
for r in rows:
    nome = (r['DSC_ESTABELECIMENTO'] or '').strip()
    if len(nome) < 3 or r['COD_ESPECIE'] not in ('4', '5', '6', '8'): continue
    try: lat, lon = float(r['LATITUDE']), float(r['LONGITUDE'])
    except ValueError: continue
    x, y = to_map(lat, lon)
    if not inside(x, y) or repetido(x, y, nome): continue
    nome = nome.title()
    rua = ' '.join(v for v in (r['NOM_TIPO_SEGLOGR'], r['NOM_TITULO_SEGLOGR'], r['NOM_SEGLOGR']) if v).title()
    num = (r['NUM_ENDERECO'] or '').lstrip('0')
    pois.append([round(x), round(y), CI[ESP.get(r['COD_ESPECIE'], 'comercio')], nome, (rua + (', ' + num if num else '')).strip(), round(lat, 6), round(lon, 6)])
    guarda(x, y, nome); n_cn += 1
print('Estabelecimentos: Overture', n_ov, '| IBGE', n_cn, '| total de referências', len(pois))

# ---------- grava ----------
nb = bytearray(); lines = []
for c, ints in partes:
    lines.append([c, len(nb), len(ints)]); nb += struct.pack('<%di' % len(ints), *ints)
meta['lines'] = lines
D['geo'] = base64.b64encode(gzip.compress(bytes(nb), 9)).decode()
D['txt'] = base64.b64encode(gzip.compress(json.dumps(texts, ensure_ascii=False, separators=(',', ':')).encode(), 9)).decode()
D['streets'] = base64.b64encode(gzip.compress(json.dumps(streets, ensure_ascii=False, separators=(',', ':')).encode(), 9)).decode()
D['fontes'] = ['Prefeitura de Umuarama (Mapa 1)', 'OpenStreetMap', 'IBGE CNEFE 2022', 'Overture Maps']
json.dump(D, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('ruas no total:', len({key(s[0]) for s in streets if not (len(s) > 3 and s[3])}), '| arquivo', os.path.getsize(out_path) // 1024, 'KB')
