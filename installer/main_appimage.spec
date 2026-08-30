# -*- mode: python ; coding: utf-8 -*-
# Variante "onedir" di main_unix.spec, usata solo per costruire l'AppImage:
# linuxdeploy ha bisogno di una cartella con l'exe e le sue .so accanto per
# poter ispezionare e bundlare le dipendenze reali (Qt, plugin di piattaforma,
# librerie di sistema) - un onefile (che si autoestrae in un tmpdir a runtime)
# non gli permette di farlo in modo statico.

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None


a = Analysis(
    ['../main.py'],
    pathex=[],
    binaries=[],
    # yt_dlp_ejs non e' solo un modulo Python: porta con se' anche gli script
    # .js veri e propri (yt_dlp_ejs/yt/solver/*.min.js) usati per risolvere le
    # sfide JS di YouTube - PyInstaller li tratta come "data files", non come
    # import, quindi vanno raccolti a parte (esattamente come fa la build
    # ufficiale di yt-dlp stessa: yt_dlp/__pyinstaller/hook-yt_dlp.py, dentro
    # al pacchetto scaricato da YtDlpUpdater, usa questa stessa chiamata)
    datas=collect_data_files('yt_dlp_ejs', includes=['**/*.js']),
    # dipendenze opzionali di yt-dlp (extra 'default' su PyPI - vedi
    # ytdlp_updater.py): yt-dlp non e' piu' un binario standalone che se le
    # porta dietro da solo (i vecchi eseguibili yt-dlp_linux/.exe/_macos
    # scaricati dalle release GitHub le includevano gia', costruiti con lo
    # stesso hook-yt_dlp.py ufficiale citato sopra), e' un pacchetto Python
    # scaricato a runtime dentro la cartella dati dell'utente e importato
    # in-process da li' (vedi Tools._importYtDlp/_runYtDlpInProcess in
    # libs.py) - PyInstaller non vede mai questi import analizzando main.py
    # (yt_dlp stesso non compare da nessuna parte nel codice dell'app, viene
    # solo scaricato ed eseguito a runtime), quindi vanno elencati qui a mano.
    # Senza, yt-dlp le troverebbe comunque assenti a runtime e
    # disabiliterebbe in silenzio le funzionalita' che dipendono da loro (HLS
    # cifrato in AES, metadata negli mp3 scaricati, alcuni siti che usano
    # websocket, script di risoluzione delle sfide JS di YouTube piu'
    # aggiornati di quello vendorizzato dentro yt_dlp stesso) invece di
    # fallire in modo rumoroso. curl_cffi in particolare serve per
    # l'"impersonation" TLS/HTTP di un browser reale, richiesta da alcuni
    # extractor per bypassare la protezione anti-bot (verificato con un caso
    # reale: senza curl_cffi, Dailymotion falliva con "attempting
    # impersonation, but none of these impersonate targets are available" -
    # non un fallback degradato, un fallimento totale per quell'extractor).
    # yt_dlp_ejs da solo fornisce solo lo script:
    # per eseguirlo davvero serve un motore JS, fornito qui da 'quickjs-ng'
    # (bundlato staticamente, vedi Tools._registerEmbeddedQuickJsProvider in
    # libs.py - non richiede un binario/runtime esterno come deno/node/bun/qjs
    # installato a parte sul sistema dell'utente, a differenza di come
    # funzionavano i vecchi eseguibili standalone di yt-dlp). 'quickjs' non
    # compare qui in hiddenimports: e' un import letterale dentro libs.py
    # (non dinamico come yt_dlp_ejs), quindi PyInstaller lo rileva da solo
    # analizzando main.py - verificato con una build reale (nessun "missing
    # module" nel report di PyInstaller). Eccezione nota: su macOS x86_64
    # 'quickjs-ng' non ha un wheel precompilato (vedi il pip install "best
    # effort" in build-macos.yml) - su quella build il provider non si
    # registra e serve comunque un runtime esterno come prima.
    # yt_dlp_ejs va con collect_submodules, non come stringa semplice: il suo
    # yt_dlp_ejs/yt/solver/__init__.py fa un import auto-referenziale di se'
    # stesso (import yt_dlp_ejs.yt.solver dentro yt_dlp_ejs.yt.solver) per
    # poter usare importlib.resources.files() sul proprio stesso pacchetto -
    # verificato che con un semplice hiddenimports=['yt_dlp_ejs'] PyInstaller
    # bundla il modulo ma le funzioni core()/lib() al suo interno risultano
    # mancanti a runtime (AttributeError), mentre collect_submodules lo bundla
    # per intero e funziona
    # secretstorage: come brotli/mutagen/ecc. sopra, importato dentro un
    # try/except di yt_dlp (cookies.py, solo per leggere i cookie salvati da
    # browser Chromium via portachiavi di sistema - vedi build-appimage.sh),
    # quindi va dichiarato a mano o PyInstaller non lo
    # vede da solo con l'analisi statica
    hiddenimports=['brotli', 'certifi', 'mutagen', 'Cryptodome', 'websockets', 'urllib3', 'curl_cffi', 'secretstorage', *collect_submodules('yt_dlp_ejs')],
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
