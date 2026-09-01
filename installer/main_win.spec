# -*- mode: python ; coding: utf-8 -*-


from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None


a = Analysis(
    ['../main.py'],
    pathex=[],
    binaries=[],
    # script .js di yt_dlp_ejs (dato, non import - vedi il commento esteso in
    # installer/main_appimage.spec)
    datas=collect_data_files('yt_dlp_ejs', includes=['**/*.js']),
    # dipendenze opzionali di yt-dlp (extra 'default' su PyPI): yt-dlp e' un
    # pacchetto scaricato a runtime e importato in-process da una cartella
    # esterna (vedi Tools._importYtDlp in libs.py), mai importato da main.py -
    # PyInstaller non le vede mai da solo, vanno elencate qui a mano (stesso
    # commento esteso in installer/main_appimage.spec)
    # yt_dlp_ejs va con collect_submodules, non come stringa semplice - vedi
    # il commento esteso in installer/main_appimage.spec (il suo
    # yt_dlp_ejs/yt/solver/__init__.py fa un import auto-referenziale che
    # un hiddenimports=['yt_dlp_ejs'] semplice non bundla per intero)
    hiddenimports=['brotli', 'certifi', 'optparse', 'collections', 'fileinput', 'functools', 'io', 'locale', 'operator', 'sqlite3', 'heapq', 'collections.abc', 'html.parser', 'xml.etree.ElementTree', 'mutagen', 'Cryptodome', 'websockets', 'urllib3', 'curl_cffi', *collect_submodules('yt_dlp_ejs')],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PastyDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # False: UPX comprime l'exe ma su Windows puo' corrompere VCRUNTIME140.dll
    # e aumenta il tasso di falsi positivi antivirus (assomiglia di piu' a un
    # packer) - vedi conversazione sulla compatibilita' Windows
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="../resources/favicon.ico",
)
