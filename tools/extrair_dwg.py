import pickle, re, math, json, struct, gzip, base64, collections, sys

objs = pickle.load(open('/home/claude/dwg/objs.pkl', 'rb'))

def fix(s):
    if not isinstance(s, str): return ''
    b = s.encode('latin-1')
    try: return b.decode('utf-8')
    except UnicodeDecodeError: return b.decode('cp1252', errors='replace')

L = {o['handle'][-1]: fix(o['name']) for o in objs if o.get('object') == 'LAYER'}

# ---- line categories ----
LINECAT = [
    ('rio',     ['Rios','RIO','RIO_NASCENTE_CORREGO','Nascentes Rios','Rios Nascentes','corrego']),
    ('verde',   ['MATA','.preservação','APP','Área Verde','Maciços Árvores','RESERVALEGAL','limite legal APA','REFLO_E_TOP']),
    ('lote',    ['Lotes - divisão','Lotes - divisão - desmembramento','00_divisa_lotes','Lim. LOTE','.Lote Caucionado','AREAS DOS LOTES','LOTES_FECHADOS','LOTE']),
    ('quadra',  ['Quadras - divisão','QUADRAS','00_quadras','Limit. Quadras','QUADRAS DIVISÃO','QUADRA','.Loteamento Limite','Loteamentos limites','.Expansão']),
    ('via',     ['Asfalto - delimitação','Asfalto - faixa de domínio','Asfalto - eixo da pista','Asfalto - borda','Asfalto - pavimento','Estrada','Via - Rodovias Municipais','.Trevo','MEIO FIO','Meio fio1','MFIO','PAVIM','Vielas','TREVO']),
    ('bairro',  ['Delimitação Bairros','DIV_BAIRROS_TOP']),
    ('num',     ['.Numeração predial Novo','.Numeração predial Caderno','.Eixo numeração','.Numeração de casa']),
    ('circ',    ['Quadras - circulo']),
]
lc = {}
for c, ls in LINECAT:
    for l in ls: lc[l] = c
LCATS = [c for c, _ in LINECAT] + ['outro']

RUA = re.compile(r'^\s*(RUA|R\.|AV\b|AV\.|AVENIDA|TRAV|TRAVESSA|ALAMEDA|ESTRADA|RODOVIA|PR[- ]?\d|BR[- ]?\d|PRAÇA|PÇ|MARGINAL|VIA\b|CONTORNO|PROLONG)', re.I)
TEXTCAT = {
    'rua': ['Ruas - nomes','.Ruas Decretos','04_tx_ruas','WAGNER','TOP_NIV_631'],
    'num': ['.Numeração predial Novo','.Numeração de casa','.Eixo numeração','Estrada'],
    'quadra': ['Quadras - número'],
    'lote': ['Lotes - número','NUMEROS DE LOTES','LOTES NUMEROS','04_tx_n_lotes'],
    'bairro': ['.Textos','Bairros - nomes'],
    'rio': ['Rios - nomes','Rios','RIO','RIO_NASCENTE_CORREGO','Nascentes Rios'],
    'local': ['Indicadores - empresas','Id - institucionais','Textos diversos','QUADRAS'],
}
tc = {}
for c, ls in TEXTCAT.items():
    for l in ls: tc[l] = c
TCATS = ['rua','num','quadra','lote','bairro','rio','local','outro']

def clean_mtext(s):
    s = s.replace('\\P', ' ').replace('\\~', ' ')
    s = re.sub(r'\\[ACcFfHhQTWpLlOoKkSs][^;\\{}]*;', '', s)
    s = re.sub(r'\\[LlOoKk]', '', s)
    s = s.replace('{', '').replace('}', '')
    s = re.sub(r'\\S([^;]*)[#^/]([^;]*);', r'\1/\2', s)
    s = re.sub(r'%%[cC]', 'Ø', s); s = re.sub(r'%%[dD]', '°', s); s = re.sub(r'%%[pP]', '±', s)
    return re.sub(r'\s+', ' ', s).strip()

polys = collections.defaultdict(list)   # cat -> list of [(x,y),...]
texts = []

def arcpts(cx, cy, r, a0, a1):
    while a1 <= a0: a1 += 2 * math.pi
    ang = a1 - a0
    n = max(16 if ang > 6 else 2, min(48, int(math.ceil(ang * r / (1.5 if r > 15 else 3)))))
    return [(cx + r * math.cos(a0 + ang * i / n), cy + r * math.sin(a0 + ang * i / n)) for i in range(n + 1)]

def lw_pts(o):
    pts = [tuple(p[:2]) for p in o.get('points') or []]
    if not pts: return []
    closed = bool(o.get('flag', 0) & 512)
    bul = o.get('bulges') or []
    out = [pts[0]]
    segs = len(pts) if closed else len(pts) - 1
    for i in range(segs):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        b = bul[i] if i < len(bul) else 0
        if b and abs(b) > 1e-6:
            th = 4 * math.atan(b)
            dx, dy = q[0] - p[0], q[1] - p[1]
            ch = math.hypot(dx, dy)
            if ch > 1e-9:
                r = ch / (2 * math.sin(abs(th) / 2))
                mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
                h = r * math.cos(abs(th) / 2)
                nx, ny = -dy / ch, dx / ch
                sgn = 1 if b > 0 else -1
                cx, cy = mx + sgn * nx * h, my + sgn * ny * h
                a0 = math.atan2(p[1] - cy, p[0] - cx)
                n = max(2, min(32, int(abs(th) * r / 1.5)))
                for k in range(1, n):
                    a = a0 + th * k / n
                    out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        out.append(q)
    return out

skipped = collections.Counter()
for o in objs:
    e = o.get('entity')
    if not e or o.get('entmode') != 2: continue
    lay = L.get((o.get('layer') or [0])[-1], '?')
    ext = o.get('extrusion') or [0, 0, 1]
    flip = ext[2] < 0
    if e in ('TEXT', 'MTEXT', 'ATTRIB'):
        if e == 'MTEXT':
            s = clean_mtext(fix(o.get('text') or ''))
            p = o['ins_pt']; h = o.get('text_height') or 2.5
            xd = o.get('x_axis_dir') or [1, 0, 0]
            rot = math.atan2(xd[1], xd[0])
            att = o.get('attachment', 1)  # 1..9 TL TC TR ML MC MR BL BC BR
            ha = (att - 1) % 3; va = (att - 1) // 3   # va 0=top 1=mid 2=bottom
            va_m = {0: 3, 1: 2, 2: 0}[va]
        else:
            s = fix(o.get('text_value') or '').strip()
            h = o.get('height') or 2.5
            rot = o.get('rotation') or 0
            ha = o.get('horiz_alignment') or 0
            va_m = o.get('vert_alignment') or 0
            p = o['alignment_pt'] if (ha or va_m) and o.get('alignment_pt') else o['ins_pt']
            if ha in (3, 5): ha = 0  # aligned/fit -> left on ins
            if ha == 4: ha = 1
            ha = min(ha, 2)
        s = re.sub(r'\s+', ' ', s).strip()
        if not s: continue
        x, y = p[0], p[1]
        if flip: x = -x; rot = math.pi - rot
        c = tc.get(lay, 'outro')
        if c not in ('num', 'quadra', 'lote') and RUA.match(s) and len(s) > 4: c = 'rua'
        texts.append((x, y, h, rot, ha, va_m, TCATS.index(c), s))
        continue
    c = lc.get(lay, 'outro')
    if e == 'LINE':
        polys[c].append([tuple(o['start'][:2]), tuple(o['end'][:2])])
    elif e == 'ARC':
        cx, cy = o['center'][:2]; a0, a1 = o['start_angle'], o['end_angle']
        if flip: cx = -cx; a0, a1 = math.pi - a1, math.pi - a0
        polys[c].append(arcpts(cx, cy, o['radius'], a0, a1))
    elif e == 'CIRCLE':
        cx, cy = o['center'][:2]
        if flip: cx = -cx
        polys[c].append(arcpts(cx, cy, o['radius'], 0, 2 * math.pi))
    elif e == 'LWPOLYLINE':
        pts = lw_pts(o)
        if flip: pts = [(-x, y) for x, y in pts]
        if len(pts) > 1: polys[c].append(pts)
    elif e == 'SPLINE':
        cp = o.get('fit_pts') or o.get('ctrl_pts') or []
        pts = [(q['x'], q['y']) if isinstance(q, dict) else tuple(q[:2]) for q in cp]
        if len(pts) > 1: polys[c].append(pts)
    elif e == 'ELLIPSE':
        cx, cy = o['center'][:2]; mx, my = o['sm_axis'][:2]; ratio = o['axis_ratio']
        a0, a1 = o['start_angle'], o['end_angle']
        while a1 <= a0: a1 += 2 * math.pi
        R = math.hypot(mx, my); ph = math.atan2(my, mx)
        n = 48; pts = []
        for i in range(n + 1):
            t = a0 + (a1 - a0) * i / n
            ex, ey = R * math.cos(t), R * ratio * math.sin(t)
            pts.append((cx + ex * math.cos(ph) - ey * math.sin(ph), cy + ex * math.sin(ph) + ey * math.cos(ph)))
        polys[c].append(pts)
    else:
        skipped[e] += 1

# merge consecutive LINE segments that share endpoints (chain) to reduce size
def chain(segs):
    out = []; cur = None
    for s in segs:
        if cur and len(s) >= 2 and abs(cur[-1][0] - s[0][0]) < 1e-3 and abs(cur[-1][1] - s[0][1]) < 1e-3:
            cur.extend(s[1:])
        else:
            if cur: out.append(cur)
            cur = list(s)
    if cur: out.append(cur)
    return out

# bounds from robust percentiles of points
allx = sorted(p[0] for c in ('quadra','lote','via','rio') for pl in polys[c] for p in pl)
ally = sorted(p[1] for c in ('quadra','lote','via','rio') for pl in polys[c] for p in pl)
q = lambda a, f: a[int(len(a) * f)]
minx, maxx, miny, maxy = q(allx, .001), q(allx, .999), q(ally, .001), q(ally, .999)
pad = 300
minx -= pad; miny -= pad; maxx += pad; maxy += pad
print('bounds', minx, miny, maxx, maxy, 'skipped', skipped)
inb = lambda x, y: minx <= x <= maxx and miny <= y <= maxy

S = 10  # decimeters
buf = bytearray()
header = []
for c in LCATS:
    pls = chain(polys.get(c, []))
    pls = [pl for pl in pls if any(inb(x, y) for x, y in pl)]
    ints = []
    nseg = 0
    for pl in pls:
        q_ = [(round((x - minx) * S), round((y - miny) * S)) for x, y in pl]
        # dedupe consecutive
        d = [q_[0]] + [p for i, p in enumerate(q_[1:]) if p != q_[i]]
        if len(d) < 2: continue
        ints.append(len(d))
        for x, y in d: ints += [x, y]
        nseg += len(d) - 1
    off = len(buf)
    buf += struct.pack('<%di' % len(ints), *ints)
    header.append([c, off, len(ints)])
    print(c, len(pls), nseg)

texts = [t for t in texts if inb(t[0], t[1])]
tj = [[round((t[0] - minx) * S), round((t[1] - miny) * S), round(t[2] * S), round(t[3], 3), t[4], t[5], t[6], t[7]] for t in texts]
print('texts', len(tj), collections.Counter(TCATS[t[6]] for t in tj))

meta = {'w': round((maxx - minx) * S), 'h': round((maxy - miny) * S), 'S': S, 'lines': header, 'tcats': TCATS}
geo = base64.b64encode(gzip.compress(bytes(buf), 9)).decode()
txt = base64.b64encode(gzip.compress(json.dumps(tj, ensure_ascii=False, separators=(',', ':')).encode(), 9)).decode()
json.dump({'meta': meta, 'geo': geo, 'txt': txt}, open('/home/claude/dwg/data.json', 'w'))
print('sizes', len(geo), len(txt))
pickle.dump((polys, texts, (minx, miny, maxx, maxy)), open('/home/claude/dwg/ext.pkl', 'wb'))

# ---------- streets & address index ----------
import unicodedata, numpy as np
def norm(s):
    s = unicodedata.normalize('NFD', s.upper()); s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
    return re.sub(r'[^A-Z0-9 ]', ' ', s)
def street_name(s):
    s = re.split(r'\s(DEC\.?|DECRETO|LEI)\b', s, flags=re.I)[0]
    s = re.sub(r'\s+', ' ', s).strip(' -,.')
    return s
def key(s):
    k = norm(s)
    k = re.sub(r'\bPROJ(ETADA)?\b.*', '', k) if not re.match(r'\s*(RUA|AV\w*)\s+PROJ', k) else k
    k = re.sub(r'\bAV(ENIDA)?\b', 'AV', k); k = re.sub(r'\bR\b', 'RUA', k)
    return re.sub(r'\s+', ' ', k).strip()
TI = {c: i for i, c in enumerate(TCATS)}
streets = {}
for i, t in enumerate(tj):
    if t[6] != TI['rua']: continue
    nm = street_name(t[7]);
    if len(nm) < 4 or re.match(r'\s*(DEC|DECRETO|LEI|LEGISLATIVO|PROJ)\b', nm, re.I) or not re.search(r'[A-Za-zÀ-ú]{3}', nm): continue
    k = key(nm)
    if len(k) < 4: continue
    st = streets.setdefault(k, {'names': collections.Counter(), 'lab': []})
    st['names'][nm] += 1; st['lab'].append(i)
skeys = list(streets)
# label arrays
lab = [(si, tj[i][0], tj[i][1], tj[i][3]) for si, k in enumerate(skeys) for i in streets[k]['lab']]
LA = np.array(lab, dtype=float)
nums = [(i, t) for i, t in enumerate(tj) if t[6] == TI['num'] and re.fullmatch(r'\d{1,5}[A-Z]?', t[7])]
assign = {}
for i, t in nums:
    dx = t[0] - LA[:, 1]; dy = t[1] - LA[:, 2]
    c, s_ = np.cos(LA[:, 3]), np.sin(LA[:, 3])
    along = np.abs(dx * c + dy * s_); perp = np.abs(-dx * s_ + dy * c)
    score = perp + np.maximum(0, along - 600) * 0.5
    ok = (perp < 400) & (along < 2500)   # decimeters: 40m perp, 250m along
    if not ok.any(): continue
    j = np.argmin(np.where(ok, score, 1e18))
    assign[i] = int(LA[j, 0])
print('numbers', len(nums), 'assigned', len(assign), 'streets', len(skeys))
# reverse index: for each street list of number text indices
sidx = []
for si, k in enumerate(skeys):
    st = streets[k]
    sidx.append([st['names'].most_common(1)[0][0], st['lab'], []])
for i, si in assign.items(): sidx[si][2].append(i)
D = json.load(open('/home/claude/dwg/data.json'))
D['streets'] = base64.b64encode(gzip.compress(json.dumps(sidx, ensure_ascii=False, separators=(',', ':')).encode(), 9)).decode()
json.dump(D, open('/home/claude/dwg/data.json', 'w'))
print('streets size', len(D['streets']))
for x in sorted(sidx, key=lambda x: -len(x[2]))[:8]: print(x[0], len(x[1]), len(x[2]))
for x in sidx:
    if 'SAKAI' in x[0].upper() or 'Barilli' in x[0]: print(x[0], sorted(tj[i][7] for i in x[2]))
