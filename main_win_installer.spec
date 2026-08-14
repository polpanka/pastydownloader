# -*- mode: python ; coding: utf-8 -*-
# Variante "onedir" di main_win.spec, usata solo per generare l'installer con
# installer\pastydownloader.iss: quello script si aspetta una cartella con
# l'exe e le sue dipendenze accanto (dist\PastyDownloader\*), non un onefile
# che si autoestrae a runtime - stesso motivo per cui esiste main_appimage.spec
# per Linux. main_win.spec (onefile) resta il modo per generare il singolo
# exe portatile zippato, com'e' sempre stato.

block_cipher = None


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='PastyDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # False: UPX comprime i file ma su Windows puo' corrompere VCRUNTIME140.dll
    # e aumenta il tasso di falsi positivi antivirus (assomiglia di piu' a un
    # packer) - vedi conversazione sulla compatibilita' Windows, stessa scelta
    # fatta in main_win.spec
    upx=False,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="resources/favicon.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PastyDownloader',
)
