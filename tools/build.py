# Gera www/index.html a partir de tools/src.html, com a versão de version.json
#   python3 tools/build.py                 -> app (www/)
#   python3 tools/build.py --single ARQ    -> arquivo único com o mapa embutido (demonstração)
import json, os, shutil, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = json.load(open(os.path.join(root, 'version.json'), encoding='utf-8'))
ver = V['latest']
src = open(os.path.join(root, 'tools', 'src.html'), encoding='utf-8').read()
www = os.path.join(root, 'www')
open(os.path.join(www, 'index.html'), 'w', encoding='utf-8').write(
    src.replace('/*VERSION*/', ver).replace('/*EMBED*/null', 'null').replace('/*CHANGELOG*/null', 'null'))
shutil.copy(os.path.join(root, 'version.json'), os.path.join(www, 'version.json'))
if '--single' in sys.argv:
    D = open(os.path.join(www, 'data', 'mapa.json'), encoding='utf-8').read()
    out = src.replace('/*VERSION*/', ver).replace('/*EMBED*/null', D).replace('/*CHANGELOG*/null', json.dumps(V, ensure_ascii=False))
    open(sys.argv[sys.argv.index('--single') + 1], 'w', encoding='utf-8').write(out)
print('versão', ver)
