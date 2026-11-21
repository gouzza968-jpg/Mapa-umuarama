# Gera os arquivos do site a partir de src.html / sw-src.js usando a versão de version.json
import json, os, shutil, sys
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here) if os.path.basename(here) == 'tools' else here
tools = os.path.join(root, 'tools') if os.path.isdir(os.path.join(root, 'tools')) else here
V = json.load(open(os.path.join(root, 'version.json'), encoding='utf-8'))
ver = V['latest']
src = open(os.path.join(tools, 'src.html'), encoding='utf-8').read()
open(os.path.join(root, 'index.html'), 'w', encoding='utf-8').write(src.replace('/*VERSION*/', ver).replace('/*EMBED*/null', 'null').replace('/*CHANGELOG*/null', 'null'))
sw = open(os.path.join(tools, 'sw-src.js'), encoding='utf-8').read()
open(os.path.join(root, 'sw.js'), 'w', encoding='utf-8').write(sw.replace('/*VERSION*/', ver))
if '--single' in sys.argv:  # arquivo único com dados embutidos
    D = open(os.path.join(root, 'data', 'mapa.json'), encoding='utf-8').read()
    out = src.replace('/*VERSION*/', ver).replace('/*EMBED*/null', D).replace('/*CHANGELOG*/null', json.dumps(V, ensure_ascii=False))
    open(sys.argv[sys.argv.index('--single') + 1], 'w', encoding='utf-8').write(out)
print('versão', ver)
