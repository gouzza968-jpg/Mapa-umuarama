"""Funções comuns para os dados do OpenStreetMap (Geofabrik -> osmium export geojsonseq)."""
import gzip, json, math, re, unicodedata

LAT0, LON0 = -23.766, -53.325
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110540


def proj(lat, lon):
    return ((lon - LON0) * KX, (lat - LAT0) * KY)


def unproj(x, y):
    return (LAT0 + y / KY, LON0 + x / KX)


def load_features(path):
    out = []
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            line = line.strip().lstrip('\x1e')
            if line:
                out.append(json.loads(line))
    return out


def lines_of(geom):
    t, c = geom['type'], geom['coordinates']
    if t == 'LineString': return [c]
    if t == 'MultiLineString': return c
    if t == 'Polygon': return c
    if t == 'MultiPolygon': return [r for p in c for r in p]
    return []


def centroid(geom):
    t, c = geom['type'], geom['coordinates']
    if t == 'Point': return c[1], c[0]
    pts = [p for l in lines_of(geom) for p in l]
    if not pts: return None
    return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)


STOP = {'RUA', 'R', 'AV', 'AVENIDA', 'DE', 'DA', 'DO', 'DOS', 'DAS', 'E', 'TRAVESSA', 'TRAV', 'ALAMEDA', 'AL', 'RODOVIA', 'ESTRADA', 'PRACA',
        'PROJETADA', 'PROJ', 'DR', 'DOUTOR', 'PROF', 'PROFESSOR', 'PE', 'PADRE', 'SAO', 'SANTA', 'SANTO', 'GOV', 'GOVERNADOR', 'VER', 'VEREADOR',
        'CEL', 'CORONEL', 'ENG', 'ENGENHEIRO', 'DEP', 'DEPUTADO', 'PRES', 'PRESIDENTE', 'MAL', 'MARECHAL', 'GAL', 'GENERAL', 'DONA', 'D', 'SEN',
        'SENADOR', 'CAP', 'CAPITAO', 'TEN', 'TENENTE'}


def key(s):
    s = unicodedata.normalize('NFD', s.upper()); s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'\(.*?\)', ' ', s); s = re.split(r'\bDECRETO\b', s)[0]
    return ' '.join(x for x in re.sub(r'[^A-Z0-9 ]', ' ', s).split() if x not in STOP)


CATS = [
    ('saude', 'Saúde'), ('farmacia', 'Farmácia'), ('mercado', 'Mercado'), ('posto', 'Posto de combustível'),
    ('borracharia', 'Borracharia'), ('oficina', 'Oficina de moto/carro'), ('seguranca', 'Polícia / Bombeiros'),
    ('escola', 'Escola'), ('servico', 'Serviço público / banco'), ('comida', 'Restaurante / lanchonete'), ('igreja', 'Igreja'),
]
CI = {c: i for i, (c, _) in enumerate(CATS)}
DEF = {'saude': 'Unidade de saúde', 'farmacia': 'Farmácia', 'mercado': 'Mercado', 'posto': 'Posto de combustível',
       'borracharia': 'Borracharia', 'oficina': 'Oficina'}


def cat_of(t):
    a, sh, nm = t.get('amenity', ''), t.get('shop', ''), (t.get('name') or '').lower()
    if 'highway' in t and not a and not sh: return None
    if 'borracharia' in nm or sh == 'tyres': return 'borracharia'
    if a in ('hospital', 'clinic', 'doctors') or (t.get('healthcare') and t.get('healthcare') != 'pharmacy'): return 'saude'
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


def pois_from(features, to_map, inside):
    """Lista de referências [x, y, cat, nome, endereço, lat, lon] em coordenadas do mapa."""
    pois, seen = [], set()
    for f in features:
        t = f.get('properties') or {}
        c = cat_of(t)
        if not c: continue
        ll = centroid(f['geometry'])
        if not ll: continue
        name = t.get('name') or DEF.get(c)
        if not name: continue
        x, y = to_map(*ll)
        if not inside(x, y): continue
        k = (c, name.lower(), round(x / 200), round(y / 200))
        if k in seen: continue
        seen.add(k)
        addr = ' '.join(v for v in (t.get('addr:street', ''), t.get('addr:housenumber', '')) if v).strip()
        pois.append([round(x), round(y), CI[c], name, addr, round(ll[0], 6), round(ll[1], 6)])
    return pois
