#!/usr/bin/python
"""Scarica l'ultima versione di yt-dlp da PyPI e stampa tutti i moduli che
importa dall'esterno di se stesso (stdlib + terze parti), lazy/nidificati
inclusi - la stessa cosa che gli spec PyInstaller in installer/*.spec devono
elencare a mano in hiddenimports (yt-dlp non e' mai 'pip install'ato nel
venv di build, quindi PyInstaller non vede mai i suoi import analizzando
main.py - vedi i commenti in installer/main_appimage.spec).

USO
---
    python3 check_ytdlp_hidden_imports.py > oggi.txt
    diff ieri.txt oggi.txt

Ogni riga nuova in "oggi.txt" e' un modulo che yt-dlp non importava ieri:
va verificato se e' gia' coperto da un'altra dipendenza dell'app (PySide6/
aiohttp/requests/ecc, o dagli hiddenimports gia' presenti) o se va aggiunto
a mano negli spec (stesso identico bug che ha causato il problema Dailymotion
del 2026-09-01: optparse/collections/fileinput/functools/io/locale/operator/
sqlite3/heapq/collections.abc/html.parser/xml.etree.ElementTree mancanti).

La riga di versione (prima riga, con '#') cambia ad ogni esecuzione dato che
scarica sempre l'ultima release: e' normale che compaia nel diff, ignorala.

Nessuna dipendenza esterna: solo stdlib, cosi' gira ovunque senza pip install.
"""

import ast
import json
import os
import sys
import tempfile
import urllib.request
import zipfile

PYPI_URL = 'https://pypi.org/pypi/yt-dlp/json'


def fetchLatestWheelUrl():
    with urllib.request.urlopen(PYPI_URL, timeout=15) as resp:
        release = json.load(resp)
    version = release.get('info', {}).get('version')
    urls = release.get('urls', [])
    wheel = next((u for u in urls if u.get('packagetype') == 'bdist_wheel'
                  and str(u.get('filename', '')).endswith('-py3-none-any.whl')), None)
    if not version or not wheel:
        raise RuntimeError('Nessun wheel py3-none-any trovato su PyPI per yt-dlp')
    return version, wheel['url']


def downloadAndExtract(wheelUrl, destDir):
    wheelPath = os.path.join(destDir, 'yt_dlp.whl')
    urllib.request.urlretrieve(wheelUrl, wheelPath)
    with zipfile.ZipFile(wheelPath) as z:
        z.extractall(destDir)
    return os.path.join(destDir, 'yt_dlp')


# Cammina l'intero albero yt_dlp/ e ritorna (stdlibModules, thirdPartyModules,
# dynamicImportLiterals). ast.walk (non solo il livello del modulo) prende
# anche gli import annidati dentro funzioni/try-except (import lazy) - lo
# stesso schema che ha nascosto optparse & co. finche' non sono esplosi solo
# nel build compilato.
def scanImports(packageDir):
    stdlibNames = sys.stdlib_module_names
    absoluteImports = set()  # nomi dotted completi, es. 'xml.etree.ElementTree'
    dynamicLiterals = set()  # argomenti stringa di importlib.import_module()/__import__()

    for dirpath, dirs, files in os.walk(packageDir):
        # __pyinstaller/: e' l'hook ufficiale di yt-dlp per chi lo pip-installa
        # sul serio (vedi hook-yt_dlp.py) - mai eseguito in questo progetto,
        # solo rumore (importa PyInstaller stesso)
        dirs[:] = [d for d in dirs if d != '__pyinstaller']
        for filename in files:
            if not filename.endswith('.py'):
                continue
            path = os.path.join(dirpath, filename)
            try:
                source = open(path, encoding='utf-8').read()
                tree = ast.parse(source, filename=path)
            except (SyntaxError, UnicodeDecodeError) as err:
                print('# ATTENZIONE: parse fallito per %s: %s' % (path, err), file=sys.stderr)
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        absoluteImports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.level and node.level > 0:
                        continue  # relativo (dentro yt_dlp stesso): non ci serve
                    if node.module:
                        absoluteImports.add(node.module)
                elif isinstance(node, ast.Call):
                    funcName = None
                    if isinstance(node.func, ast.Name):
                        funcName = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        funcName = node.func.attr
                    if funcName in ('import_module', '__import__') and node.args:
                        firstArg = node.args[0]
                        if isinstance(firstArg, ast.Constant) and isinstance(firstArg.value, str):
                            dynamicLiterals.add(firstArg.value)

    # top-level per capire stdlib vs terze parti, ma la lista finale resta
    # quella dotted completa (serve il sottomodulo esatto, vedi xml.etree)
    absoluteImports = {m for m in absoluteImports if m.split('.')[0] != 'yt_dlp'}
    stdlib = sorted(m for m in absoluteImports if m.split('.')[0] in stdlibNames)
    thirdParty = sorted(m for m in absoluteImports if m.split('.')[0] not in stdlibNames)
    dynamicLiterals = {m for m in dynamicLiterals if not m.startswith('yt_dlp')}
    return stdlib, thirdParty, sorted(dynamicLiterals)


def main():
    # exit code pulito (1) invece di un traceback grezzo: chi lancia lo script
    # (es. un cron PHP) controlla di norma solo l'exit code, non l'output
    try:
        version, wheelUrl = fetchLatestWheelUrl()
        with tempfile.TemporaryDirectory(prefix='ytdlp_hidden_imports_') as tmp:
            packageDir = downloadAndExtract(wheelUrl, tmp)
            stdlib, thirdParty, dynamic = scanImports(packageDir)
    except Exception as err:
        print('ERRORE: %s' % err, file=sys.stderr)
        sys.exit(1)

    print('# yt-dlp %s (questa riga cambia sempre, ignorala nel diff)' % version)
    print('## stdlib')
    for m in stdlib:
        print(m)
    print('## third-party')
    for m in thirdParty:
        print(m)
    if dynamic:
        # import dinamici via stringa (import_module/__import__): non sempre
        # risolvibili staticamente, controllare a mano se compaiono
        print('## dynamic (import_module/__import__ con stringa letterale)')
        for m in dynamic:
            print(m)


if __name__ == '__main__':
    main()
