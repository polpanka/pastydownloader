# -*- mode: python ; coding: utf-8 -*-
# Variante "onedir" di main_unix.spec, usata solo per costruire l'AppImage:
# linuxdeploy ha bisogno di una cartella con l'exe e le sue .so accanto per
# poter ispezionare e bundlare le dipendenze reali (Qt, plugin di piattaforma,
# librerie di sistema) - un onefile (che si autoestrae in un tmpdir a runtime)
# non gli permette di farlo in modo statico.

block_cipher = None


a = Analysis(
    ['../main.py'],
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
    # False: comprime solo un po' l'eseguibile, in cambio di rischi non
    # sempre segnalati (bug di runtime, exe che assomiglia di piu' a un
    # packer) - stessa scelta fatta per Windows, per prudenza estesa qui
    upx=False,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="../resources/favicon.ico",
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
