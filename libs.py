#!/usr/bin/python

import os, sys, socket, subprocess, platform, unicodedata, re, shlex, json, asyncio, base64, tempfile, hashlib, time, threading, shutil, multiprocessing, queue, zipfile, traceback
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QFile, QTextStream, QIODevice, QSettings, QStandardPaths, QLockFile
from PySide6.QtGui import QClipboard
from testi import MyText
from constants import Constants
from android_bridge import AndroidBridge

import hashlib
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('urllib3').setLevel(logging.WARNING)


# Timeout per singola richiesta HTTP di yt-dlp (non per il download intero).
# Rete di sicurezza: lo Stop vero termina l'intero processo figlio.
YTDLP_SOCKET_TIMEOUT_SECONDS = 30


# Entry point del processo figlio di download (vedi Tools._runYtDlpInProcess).
# Funzione di modulo, non metodo: multiprocessing 'spawn' la reimporta in un
# interprete nuovo, cosi' il download e' interrompibile con process.kill().
def _ytDlpDownloadWorker(packageDir, ffmpegPath, url, saveAs, referer, ejsDir, subtitleLangs, useBrowserCookies, resultQueue):
    if packageDir not in sys.path:
        sys.path.insert(0, packageDir)
    # ejsDir risolto dal padre: QStandardPaths in un processo spawnato senza
    # QCoreApplication punterebbe a una cartella sbagliata.
    if ejsDir and ejsDir not in sys.path:
        sys.path.insert(0, ejsDir)
    import yt_dlp
    Tools._registerEmbeddedQuickJsProvider(yt_dlp)

    phaseState = {'total': 0}

    def onHook(d):
        # su file gia' scaricato yt-dlp manda 'finished' senza downloaded_bytes:
        # senza questo fallback la fase conterebbe 0 invece del totale reale
        bytesForThisEvent = d.get('downloaded_bytes')
        if bytesForThisEvent is None and d.get('status') == 'finished':
            bytesForThisEvent = d.get('total_bytes')
        reported = Tools._accumulateYtDlpProgress(d.get('status'), bytesForThisEvent, phaseState)
        if reported is not None:
            resultQueue.put(('progress', reported))

    # raccoglie warning/errori e messaggi info di yt-dlp (utili per diagnosticare
    # un fallimento senza rilanciare con -v)
    messages = []

    class _QueueLogger:
        def debug(self, msg):
            messages.append(msg)

        def warning(self, msg):
            messages.append(msg)

        def error(self, msg):
            messages.append(msg)

    ydlOpts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'noprogress': True,
        'logger': _QueueLogger(),
        'ffmpeg_location': ffmpegPath,
        # Su Android, priorita' alla velocita'
        'format': ('best[ext=mp4]/best/bestvideo+bestaudio/best' if Constants.IS_ANDROID else 'bestvideo+bestaudio/best'),
        'merge_output_format': 'mp4',
        'outtmpl': saveAs,
        'progress_hooks': [onHook],
        'socket_timeout': YTDLP_SOCKET_TIMEOUT_SECONDS,
    }
    postprocessors = []
    if subtitleLangs:
        # sottotitoli incorporati (una lingua + inglese di ripiego); se assenti
        # yt-dlp salta senza errori. writeautomaticsub copre anche gli auto-generati
        ydlOpts['writesubtitles'] = True
        ydlOpts['writeautomaticsub'] = True
        ydlOpts['subtitleslangs'] = subtitleLangs
        postprocessors.append({'key': 'FFmpegEmbedSubtitle'})
    # niente SponsorBlock/ModifyChapters: richiedono ffprobe (non distribuito con
    # l'app, e con ffmpeg_location impostato yt-dlp non lo cerca nel PATH) e il
    # loro errore faceva fallire l'intero download.
    # EmbedThumbnail invece usa mutagen (imbarcato), non ffprobe: ok tenerlo.
    ydlOpts['writethumbnail'] = True
    postprocessors.append({'key': 'EmbedThumbnail'})
    ydlOpts['postprocessors'] = postprocessors
    if referer:
        ydlOpts['http_headers'] = {'Referer': referer}
    # cookie da browser solo se abilitati (checkbox Preferenze): leggere un altro
    # browser puo' far scattare un prompt di sistema. Mai True su Android.
    cookiesFromBrowser = Tools._pickCookiesBrowser(url) if useBrowserCookies else None
    if cookiesFromBrowser:
        # (browser, profile, keyring, container): gli ultimi 3 a None = default
        ydlOpts['cookiesfrombrowser'] = (cookiesFromBrowser, None, None, None)
    try:
        try:
            with yt_dlp.YoutubeDL(ydlOpts) as ydl:
                ydl.download([url])
        except Exception as err:
            # un cookiesfrombrowser illeggibile fa fallire YoutubeDL() subito:
            # un solo nuovo tentativo senza cookie
            if 'cookiesfrombrowser' not in ydlOpts:
                raise
            messages.append('cookiesfrombrowser (%s) failed, retrying without: %s' % (cookiesFromBrowser, err))
            ydlOpts.pop('cookiesfrombrowser', None)
            with yt_dlp.YoutubeDL(ydlOpts) as ydl:
                ydl.download([url])
        resultQueue.put(('done', True, ''))
    except Exception as err:
        messages.append(str(err))
        resultQueue.put(('done', False, '\n'.join(messages[-5:])))
    finally:
        # senza close()+join_thread() il processo puo' uscire prima che 'done'
        # sia stato scritto sulla pipe, e il padre lo scambia per un crash
        resultQueue.close()
        resultQueue.join_thread()


def _ytDlpVerifyWorker(packageDir, resultQueue):
    """Processo figlio di verifica post-install (vedi Tools.verifyYtDlpImportable).
    Interprete nuovo: un wheel rotto non sporca il processo principale, e non
    viene mascherato da un yt_dlp gia' cacheato in sys.modules."""
    try:
        if packageDir not in sys.path:
            sys.path.insert(0, packageDir)
        import yt_dlp
        resultQueue.put(('ok', yt_dlp.version.__version__))
    except Exception as err:
        resultQueue.put(('error', str(err)))
    finally:
        # vedi lo stesso finally in _ytDlpDownloadWorker: senza, il risultato
        # appena messo in coda rischia di non essere consegnato prima che il
        # processo esca, facendo scambiare un'installazione valida per rotta
        resultQueue.close()
        resultQueue.join_thread()


def _ytDlpEjsVerifyWorker(packageDir, resultQueue):
    """Stesso principio di _ytDlpVerifyWorker, ma per yt_dlp_ejs (vedi
    Tools.verifyYtDlpEjsImportable, usato da Tools._downloadAndInstallYtDlpEjs
    dopo ogni download): processo a parte per non far dipendere l'esito dalla
    versione eventualmente gia' cacheata in sys.modules nel processo
    principale, e perche' un wheel corrotto non deve lasciare stato a meta'
    strada in giro. Verifica che core()/lib() siano davvero leggibili, non
    solo che il modulo importi: sono letture di file via importlib.resources,
    un wheel con lo zip troncato puo' importare lo stesso ma fallire li'"""
    try:
        if packageDir not in sys.path:
            sys.path.insert(0, packageDir)
        import yt_dlp_ejs.yt.solver
        core = yt_dlp_ejs.yt.solver.core()
        lib = yt_dlp_ejs.yt.solver.lib()
        if not core or not lib:
            raise ValueError('core()/lib() returned empty content')
        resultQueue.put(('ok', yt_dlp_ejs.version))
    except Exception as err:
        resultQueue.put(('error', str(err)))
    finally:
        resultQueue.close()
        resultQueue.join_thread()


# queue.Queue con close()/join_thread() no-op: riusa le funzioni worker (scritte
# per multiprocessing.Queue) quando su Android girano in un thread - Android/Bionic
# non ha sem_open, quindi multiprocessing.Queue non funziona li' (CPython bug 3770)
class _ThreadResultQueue(queue.Queue):
    def close(self):
        pass

    def join_thread(self):
        pass


class Tools():
    # Nomi file attesi per ffmpeg (scaricato al primo avvio da FfmpegInstaller in
    # ffmpegStorageDir; url di download in ffmpeg_installer.py). Su Windows la
    # fonte 7z di gyan.dev non e' estraibile in puro Python, si usa BtbN come Linux.
    FFMPEG_BIN_WIN = 'ffmpeg.exe'
    FFMPEG_BIN_MAC = 'ffmpeg_mac'
    # BtbN richiede glibc >= 2.28, solo x86_64. La build statica johnvansickle
    # va in segfault. Testare SEMPRE con un download reale prima di cambiare fonte.
    FFMPEG_BIN_LINUX = 'ffmpeg_linux'

    # Ritorna le impostazioni salvate dell'app (QSettings)
    @staticmethod
    def getSettings():
        return QSettings(MyText().orgName, MyText().appName)

    # Path del binario ffmpeg scaricato, o None. Non deve mai sollevare
    # (ffmpegStorageDir puo' fallire e i chiamanti non se lo aspettano).
    @classmethod
    def checkFFmpeg(cls):
        if Constants.IS_ANDROID:
            # ffmpeg e' una recipe p4a locale bundlata come libffmpegbin.so,
            # esposta via env ANDROID_NATIVE_LIBS dalla patch su PythonActivity.java
            try:
                nativeLibsDir = os.environ.get('ANDROID_NATIVE_LIBS')
                if not nativeLibsDir:
                    return None
                installed = os.path.join(nativeLibsDir, 'libffmpegbin.so')
                if not os.path.exists(installed):
                    return None
                # eseguito come processo a se', il linker non trova le .so
                # sorelle (libavcodec/...) da solo: LD_LIBRARY_PATH si propaga
                # ai sottoprocessi, incluse le chiamate ffmpeg di yt-dlp
                os.environ['LD_LIBRARY_PATH'] = nativeLibsDir
                return installed
            except Exception as err:
                Tools.consoleLogs("Impossibile risolvere ffmpeg da ANDROID_NATIVE_LIBS: " + str(err))
                return None
        try:
            installed = os.path.join(cls.ffmpegStorageDir(), cls.ffmpegBinaryName())
            return installed if os.path.exists(installed) else None
        except Exception as err:
            Tools.consoleLogs("Impossibile risolvere ffmpegStorageDir: " + str(err))
            return None

    # Cartella per-utente dove FfmpegInstaller installa ffmpeg (mai la cartella
    # di installazione, sola lettura)
    @staticmethod
    def ffmpegStorageDir():
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        path = os.path.join(base, 'ffmpeg')
        os.makedirs(path, exist_ok=True)
        return path

    # Soglia prima di scaricare ffmpeg/yt-dlp: evita solo un disco palesemente pieno
    MIN_FREE_DISK_BYTES = 200 * 1024 * 1024

    @staticmethod
    def hasEnoughDiskSpace(path):
        return shutil.disk_usage(path).free >= Tools.MIN_FREE_DISK_BYTES

    @staticmethod
    def ffmpegBinaryName():
        os_name = Tools.getOs()
        if os_name == 'win':
            return Tools.FFMPEG_BIN_WIN
        elif os_name == 'mac':
            return Tools.FFMPEG_BIN_MAC
        return Tools.FFMPEG_BIN_LINUX

    # "2026.07.04" -> (2026, 7, 4), per confrontare due versioni
    @staticmethod
    def versionTuple(version):
        parts = []
        for chunk in str(version).split('.'):
            digits = re.match(r'\d+', chunk)
            parts.append(int(digits.group()) if digits else 0)
        return tuple(parts)

    # Cartella per-utente dove vengono installate le versioni di yt-dlp scaricate
    @staticmethod
    def ytDlpStorageDir():
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        path = os.path.join(base, 'yt-dlp')
        os.makedirs(path, exist_ok=True)
        return path

    # tenuto vivo per tutta la sessione: se garbage-collected, rilascia il lock
    _singleInstanceLock = None

    # Impedisce piu' istanze in parallelo (doppio click ripetuto sull'exe mentre
    # le dipendenze si scaricano al primo avvio)
    @classmethod
    def acquireSingleInstanceLock(cls):
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        os.makedirs(base, exist_ok=True)
        lock = QLockFile(os.path.join(base, 'instance.lock'))
        if not lock.tryLock(100):
            return False
        cls._singleInstanceLock = lock
        return True

    # Marca una cartella <versione> come installazione completa (wheel estratto)
    YTDLP_PACKAGE_MARKER = os.path.join('yt_dlp', '__init__.py')

    # Allowlist dei nomi di cartella-versione validi: solo numeri e punti. Esclude
    # '<versione>.part' (staging), nomi binari vecchi, '.DS_Store'. Senza filtro,
    # versionTuple('X.Y.Z.part') sorterebbe piu' recente della vera X.Y.Z.
    # Limite noto: una versione con pezzo non numerico verrebbe riscaricata sempre.
    _VERSION_DIR_RE = re.compile(r'^\d+(?:\.\d+)*$')

    # Elenca le versioni di yt-dlp scaricate e installate per intero su disco,
    # ordinate dalla piu' vecchia alla piu' recente
    @classmethod
    def installedYtDlpVersions(cls):
        root = cls.ytDlpStorageDir()
        versions = []
        for name in os.listdir(root):
            if not cls._VERSION_DIR_RE.match(name):
                continue
            if os.path.isfile(os.path.join(root, name, cls.YTDLP_PACKAGE_MARKER)):
                versions.append(name)
        return sorted(versions, key=cls.versionTuple)

    # Cartella-pacchetto yt-dlp piu' recente installata (da aggiungere a sys.path
    # prima di 'import yt_dlp'), o None. Non deve mai sollevare.
    @classmethod
    def checkYtDlp(cls):
        try:
            versions = cls.installedYtDlpVersions()
            if versions:
                return os.path.join(cls.ytDlpStorageDir(), versions[-1])
        except Exception as err:
            Tools.consoleLogs("Impossibile risolvere ytDlpStorageDir: " + str(err))
        return None

    # yt_dlp importato in-process nel processo principale, solo per probe e log
    # versione (il download vero gira in un processo figlio killabile)
    _ytDlpModule = None

    @classmethod
    def _importYtDlp(cls, packageDir):
        if cls._ytDlpModule is not None:
            return cls._ytDlpModule
        if packageDir not in sys.path:
            sys.path.insert(0, packageDir)
        cls._prepareYtDlpEjsPath()
        try:
            import yt_dlp
        except Exception as err:
            logging.error("Impossibile importare yt_dlp da %s: %s" % (packageDir, err))
            return None
        cls._registerEmbeddedQuickJsProvider(yt_dlp)
        cls._ytDlpModule = yt_dlp
        return yt_dlp

    # Ultima versione di yt-dlp contro cui _registerEmbeddedQuickJsProvider e'
    # stato verificato per davvero. Solo un promemoria nei log (yt-dlp usa qui
    # sue API interne, che possono cambiare). Aggiornare a mano dopo riverifica.
    QUICKJS_PROVIDER_VERIFIED_AGAINST = '2026.08.19'

    # Feature ES2022+ che lo script di risoluzione sfide di yt-dlp richiede:
    # campione noto, non elenco completo. Controlla la capacita' reale del motore
    # bundlato (usato dal probe a runtime e da tests/test_quickjs_provider.py).
    QUICKJS_REQUIRED_FEATURES = {
        'Array.prototype.at': '[1].at(-1) !== undefined',
        'Object.hasOwn': 'typeof Object.hasOwn === "function"',
        'Array.prototype.flat': 'typeof [].flat === "function"',
        'String.prototype.replaceAll': 'typeof "".replaceAll === "function"',
        'Object.fromEntries': 'typeof Object.fromEntries === "function"',
    }

    # Nomi delle QUICKJS_REQUIRED_FEATURES non supportate dal motore bundlato
    # (lista vuota se ok)
    @classmethod
    def _missingQuickJsFeatures(cls, quickjsModule):
        missing = []
        for name, expression in cls.QUICKJS_REQUIRED_FEATURES.items():
            try:
                ctx = quickjsModule.Context()
                if not ctx.eval(expression):
                    missing.append(name)
            except Exception:
                missing.append(name)
        return missing

    # Logga (senza bloccare la registrazione) se il motore quickjs bundlato e'
    # rimasto indietro, prima che si manifesti come download YouTube degradati
    @classmethod
    def _warnIfQuickJsIsOutdated(cls, quickjsModule):
        missing = cls._missingQuickJsFeatures(quickjsModule)
        if missing:
            Tools.consoleLogs(
                "ATTENZIONE: il motore quickjs-ng bundlato in questa build non supporta: %s - "
                "i download YouTube potrebbero perdere qualita' o fallire senza errori evidenti. "
                "Aggiornare 'quickjs-ng' nei comandi pip install (.github/workflows/build-windows.yml, "
                "build-macos.yml, build-appimage.sh) e ricompilare l'app" % ", ".join(missing))

    # Idempotenza per-processo: register_provider() di yt-dlp solleva su chiave
    # duplicata, e _ytDlpDownloadWorker gira in un processo figlio nuovo ogni volta
    _quickJsProviderRegistered = False

    # Registra un provider JS Challenge per yt-dlp basato sul pacchetto Python
    # 'quickjs-ng' (modulo importabile: 'quickjs'), bundlato staticamente. Senza,
    # YouTube richiederebbe un runtime JS esterno (deno/node/...) che l'utente non
    # ha, e il download fallirebbe del tutto.
    # Deve essere 'quickjs-ng', NON il vecchio 'quickjs' (fermo al 2023, gli
    # mancano feature ES2022 - i due sono mutuamente esclusivi).
    # macOS x86_64: 'quickjs-ng' non ha wheel, il provider non si registra e
    # l'app torna al comportamento senza runtime JS (try/except sotto).
    # La classe del provider e' dentro il metodo apposta: contiene un eventuale
    # fallimento di import delle API interne di yt-dlp in un solo try/except.
    @classmethod
    def _registerEmbeddedQuickJsProvider(cls, ytdlp):
        if cls._quickJsProviderRegistered:
            return
        cls._quickJsProviderRegistered = True
        try:
            installedVersion = ytdlp.version.__version__
            # confronto per tupla: '2026.08.19' e '2026.8.19' sono la stessa versione
            if cls.versionTuple(installedVersion) != cls.versionTuple(cls.QUICKJS_PROVIDER_VERIFIED_AGAINST):
                Tools.consoleLogs(
                    "ATTENZIONE: yt-dlp %s e' diverso dall'ultima versione (%s) contro cui il "
                    "provider QuickJS embedded e' stato verificato per davvero - se i download "
                    "YouTube iniziano a fallire (nessun formato disponibile), verificare a mano "
                    "che Tools._registerEmbeddedQuickJsProvider sia ancora compatibile e "
                    "aggiornare QUICKJS_PROVIDER_VERIFIED_AGAINST" % (installedVersion, cls.QUICKJS_PROVIDER_VERIFIED_AGAINST))

            import quickjs
            cls._warnIfQuickJsIsOutdated(quickjs)
            # moduli interni di yt-dlp: API non stabile, puo' cambiare fra versioni
            from yt_dlp.extractor.youtube.jsc._builtin.ejs import EJSBaseJCP
            from yt_dlp.extractor.youtube.jsc.provider import (
                JsChallengeProviderError, register_preference, register_provider,
            )

            # suffisso 'JCP' obbligatorio: PROVIDER_KEY lo deriva togliendolo dal
            # nome classe, con un assert
            class PastyEmbeddedQuickJsJCP(EJSBaseJCP):
                JS_RUNTIME_NAME = 'pasty-embedded-quickjs'

                # motore in memoria, sempre disponibile (niente eseguibile da rilevare)
                def is_available(self, /):
                    return self._available

                # riceve lo script JS completo, ritorna l'output di console.log,
                # valutato in-process
                def _run_js_runtime(self, stdin, /):
                    captured = []
                    ctx = quickjs.Context()
                    ctx.add_callable('__pastyConsoleLog', lambda s: captured.append(s))
                    try:
                        ctx.eval('var console = {log: function(x) { __pastyConsoleLog(x); }};\n' + stdin)
                    except Exception as err:
                        raise JsChallengeProviderError(str(err))
                    if not captured:
                        raise JsChallengeProviderError('QuickJS (embedded) produced no output')
                    return captured[-1]

            register_provider(PastyEmbeddedQuickJsJCP)
            # priorita' 900 > 850 del provider 'quickjs' esterno: preferito
            # perche' non avvia un processo per ogni sfida
            register_preference(PastyEmbeddedQuickJsJCP)(lambda provider, requests: 900)
            Tools.consoleLogs("Provider QuickJS embedded registrato per yt-dlp")
        except Exception as err:
            # mai far fallire l'import di yt_dlp: senza provider si torna al
            # comportamento senza runtime JS
            Tools.consoleLogs("Provider QuickJS embedded non registrato (yt-dlp potrebbe aver cambiato API interna): " + str(err))

    # Solo Android: la verifica post-download gira in un thread e importa da una
    # cartella temporanea che sta per essere cancellata. 'import' resta in
    # sys.modules per tutto il processo, col __path__ su file spariti: il primo
    # lazy-load di un sottomodulo poi fallisce. Fix: si butta via il sottoalbero
    # di moduli appena la verifica finisce, cosi' il prossimo import riparte pulito.
    @staticmethod
    def _purgeModuleTree(prefix, syspathEntry=None):
        for name in list(sys.modules):
            if name == prefix or name.startswith(prefix + '.'):
                del sys.modules[name]
        if syspathEntry and syspathEntry in sys.path:
            sys.path.remove(syspathEntry)

    # Verifica in un processo/thread a parte che il pacchetto yt-dlp appena
    # scaricato sia importabile. Ritorna la versione (str) o None.
    @staticmethod
    def verifyYtDlpImportable(packageDir, timeout=15):
        if Constants.IS_ANDROID:
            resultQueue = _ThreadResultQueue()
            thread = threading.Thread(target=_ytDlpVerifyWorker, args=(packageDir, resultQueue), daemon=True)
            thread.start()
            try:
                kind, payload = resultQueue.get(timeout=timeout)
            except queue.Empty:
                kind, payload = 'error', 'timeout'
            thread.join(timeout=2)
            Tools._purgeModuleTree('yt_dlp', packageDir)  # vedi _purgeModuleTree
            return payload if kind == 'ok' else None
        ctx = multiprocessing.get_context('spawn')
        resultQueue = ctx.Queue()
        process = ctx.Process(target=_ytDlpVerifyWorker, args=(packageDir, resultQueue), daemon=True)
        process.start()
        try:
            kind, payload = resultQueue.get(timeout=timeout)
        except queue.Empty:
            kind, payload = 'error', 'timeout'
        process.join(timeout=2)
        if process.is_alive():
            process.terminate()
            process.join(timeout=1)
        resultQueue.close()
        return payload if kind == 'ok' else None

    # --- yt_dlp_ejs: aggiornamento best-effort dello script di risoluzione sfide
    # JS di YouTube. Non blocca l'avvio ne' mostra UI; la versione bundlata resta
    # sempre come fallback. Non riusa YtDlpUpdater: troppo piu' semplice.

    YTDLP_EJS_PACKAGE_MARKER = os.path.join('yt_dlp_ejs', '__init__.py')
    YTDLP_EJS_PYPI_URL = 'https://pypi.org/pypi/yt-dlp-ejs/json'
    YTDLP_EJS_KEEP_VERSIONS = 2

    # Cartella per-utente dove vengono installate le versioni di yt_dlp_ejs
    @staticmethod
    def ytDlpEjsStorageDir():
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        path = os.path.join(base, 'yt-dlp-ejs')
        os.makedirs(path, exist_ok=True)
        return path

    # Stesso filtro _VERSION_DIR_RE di installedYtDlpVersions
    @classmethod
    def installedYtDlpEjsVersions(cls):
        root = cls.ytDlpEjsStorageDir()
        versions = []
        for name in os.listdir(root):
            if not cls._VERSION_DIR_RE.match(name):
                continue
            if os.path.isfile(os.path.join(root, name, cls.YTDLP_EJS_PACKAGE_MARKER)):
                versions.append(name)
        return sorted(versions, key=cls.versionTuple)

    # Non deve mai sollevare, stesso motivo di checkYtDlp()
    @classmethod
    def checkYtDlpEjs(cls):
        try:
            versions = cls.installedYtDlpEjsVersions()
            if versions:
                return os.path.join(cls.ytDlpEjsStorageDir(), versions[-1])
        except Exception as err:
            Tools.consoleLogs("Impossibile risolvere ytDlpEjsStorageDir: " + str(err))
        return None

    # Da chiamare prima di 'import yt_dlp': se una versione di yt_dlp_ejs piu'
    # recente e' stata scaricata, la mette in testa a sys.path (ha precedenza
    # sulla copia bundlata, verificato con un frozen PyInstaller reale)
    @classmethod
    def _prepareYtDlpEjsPath(cls):
        ejsDir = cls.checkYtDlpEjs()
        if ejsDir and ejsDir not in sys.path:
            sys.path.insert(0, ejsDir)

    @staticmethod
    def verifyYtDlpEjsImportable(packageDir, timeout=15):
        if Constants.IS_ANDROID:
            # vedi Tools._purgeModuleTree/verifyYtDlpImportable per il perche'
            resultQueue = _ThreadResultQueue()
            thread = threading.Thread(target=_ytDlpEjsVerifyWorker, args=(packageDir, resultQueue), daemon=True)
            thread.start()
            try:
                kind, payload = resultQueue.get(timeout=timeout)
            except queue.Empty:
                kind, payload = 'error', 'timeout'
            thread.join(timeout=2)
            Tools._purgeModuleTree('yt_dlp_ejs', packageDir)
            return payload if kind == 'ok' else None
        ctx = multiprocessing.get_context('spawn')
        resultQueue = ctx.Queue()
        process = ctx.Process(target=_ytDlpEjsVerifyWorker, args=(packageDir, resultQueue), daemon=True)
        process.start()
        try:
            kind, payload = resultQueue.get(timeout=timeout)
        except queue.Empty:
            kind, payload = 'error', 'timeout'
        process.join(timeout=2)
        if process.is_alive():
            process.terminate()
            process.join(timeout=1)
        resultQueue.close()
        return payload if kind == 'ok' else None

    # Chiamato dallo stesso ciclo periodico di YtDlpUpdater.checkAndUpdate.
    # Nessun segnale Qt: un fallimento qui resta solo nei log.
    @classmethod
    def checkAndUpdateYtDlpEjs(cls):
        try:
            release = Tools.readFileJson(cls.YTDLP_EJS_PYPI_URL, timeout=10)
            info = (release.get('info') or {}) if isinstance(release, dict) else {}
            remoteVersion = info.get('version')
            urls = (release.get('urls') or []) if isinstance(release, dict) else []
            wheel = next((u for u in urls if u.get('packagetype') == 'bdist_wheel'
                          and str(u.get('filename', '')).endswith('-py3-none-any.whl')), None)
            if not remoteVersion or not wheel:
                return
            currentVersions = cls.installedYtDlpEjsVersions()
            currentVersion = currentVersions[-1] if currentVersions else None
            if currentVersion and cls.versionTuple(remoteVersion) <= cls.versionTuple(currentVersion):
                return
            Tools.consoleLogs("yt-dlp-ejs update found: " + remoteVersion)
            cls._downloadAndInstallYtDlpEjs(remoteVersion, wheel['url'], (wheel.get('digests') or {}).get('sha256'))
            Tools.consoleLogs("yt-dlp-ejs aggiornato a " + remoteVersion)
        except Exception as err:
            Tools.consoleLogs("yt-dlp-ejs update failed: " + str(err))

    # Stesso schema di YtDlpUpdater._downloadAndInstall (scarica, checksum,
    # estrae, verifica, install atomico, prune) - vedi li' i dettagli
    @classmethod
    def _downloadAndInstallYtDlpEjs(cls, version, wheelUrl, sha256Expected):
        storageDir = cls.ytDlpEjsStorageDir()
        if not Tools.hasEnoughDiskSpace(storageDir):
            raise IOError('Not enough disk space to install yt-dlp-ejs')
        destDir = os.path.join(storageDir, version)
        with tempfile.TemporaryDirectory() as tmp:
            wheelPath = os.path.join(tmp, 'yt_dlp_ejs.whl')
            ok, msg = Tools.downloadNotAsyncGeneric(wheelUrl, wheelPath, timeout=(10, 30))
            if not ok:
                raise IOError('Download failed: ' + str(msg))
            if sha256Expected and Tools.sha256OfFile(wheelPath).lower() != str(sha256Expected).lower():
                raise ValueError('Checksum mismatch for yt-dlp-ejs %s, discarding' % version)
            extractDir = os.path.join(tmp, 'extracted')
            with zipfile.ZipFile(wheelPath) as z:
                z.extractall(extractDir)
            if not os.path.isfile(os.path.join(extractDir, cls.YTDLP_EJS_PACKAGE_MARKER)):
                raise ValueError('yt_dlp_ejs package not found inside the downloaded wheel')
            if not cls.verifyYtDlpEjsImportable(extractDir):
                raise RuntimeError('Downloaded yt-dlp-ejs %s failed to import, discarded' % version)
            os.makedirs(storageDir, exist_ok=True)
            partialDir = destDir + '.part'
            shutil.rmtree(partialDir, ignore_errors=True)
            shutil.move(extractDir, partialDir)
            os.replace(partialDir, destDir)
        cls._pruneOldYtDlpEjsVersions()

    @classmethod
    def _pruneOldYtDlpEjsVersions(cls):
        root = cls.ytDlpEjsStorageDir()
        keep = set(cls.installedYtDlpEjsVersions()[-cls.YTDLP_EJS_KEEP_VERSIONS:])
        for name in os.listdir(root):
            if name in keep:
                continue
            try:
                shutil.rmtree(os.path.join(root, name))
            except OSError as err:
                Tools.consoleLogs("Could not prune old yt-dlp-ejs %s yet: %s" % (name, err))

    @staticmethod
    def sha256OfFile(path):
        digest = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                digest.update(chunk)
        return digest.hexdigest()

    # Nasconde la finestra console che Windows aprirebbe per ogni processo figlio
    @staticmethod
    def _noConsoleWindowKwargs():
        if platform.system() == 'Windows':
            return {'creationflags': subprocess.CREATE_NO_WINDOW}
        return {}

    # args e' una lista (mai una stringa shell) per non eseguire comandi arbitrari
    # da un url incollato. timeout/isStoppedFn opzionali: un thread di controllo
    # termina l'albero di processi al primo che scatta.
    @staticmethod
    def runCommand(args, timeout=None, isStoppedFn=None):
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding='utf-8', errors='replace', **Tools._noConsoleWindowKwargs())
        interruptedHolder = {'interrupted': False}
        watcher = None
        if timeout or isStoppedFn:
            startedAt = time.time()
            def watchForStopOrTimeout():
                while process.poll() is None:
                    if isStoppedFn and isStoppedFn():
                        interruptedHolder['interrupted'] = True
                        Tools._terminateProcessTree(process)
                        return
                    if timeout and (time.time() - startedAt) > timeout:
                        interruptedHolder['interrupted'] = True
                        Tools._terminateProcessTree(process)
                        return
                    time.sleep(Tools.STOP_CHECK_INTERVAL_SECONDS)
            watcher = threading.Thread(target=watchForStopOrTimeout, daemon=True)
            watcher.start()
        stdout, _ = process.communicate()
        if watcher:
            watcher.join(timeout=1)
        # .interrupted = ucciso da timeout o Stop: l'output parziale non e' un esito valido
        result = subprocess.CompletedProcess(args, process.returncode, stdout, None)
        result.interrupted = interruptedHolder['interrupted']
        return result

    def runFFmpegOld(self, url, save_as):
        command = 'ffmpeg -i "%s" -c copy -bsf:a aac_adtstoasc %s' % (url, save_as)
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return [True, 'Completed'] if result.returncode == 0 else [False, 'Error: %s' % result.stderr.decode("utf-8")]

    @staticmethod
    def runFFmpeg(url, save_as):
        command = 'ffmpeg -y -progress pipe:1 -i "%s" -c copy -bsf:a aac_adtstoasc %s' % (url, save_as)
        return subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr = subprocess.PIPE, encoding='utf-8', universal_newlines=True)

    # prefisso degli url speciali di pasty.link: "questo va aperto con yt-dlp"
    PASTYLINK_URL_PREFIX = 'httpasty://'

    @classmethod
    def isPastylinkUrl(cls, url):
        # httpasty://BASE64{"v1" : {"ytdlp" : "https://www.youtube.com/watch?v=jNQXAC9IVRw", "referer" : "https://example.com/" }}
        return url.startswith(cls.PASTYLINK_URL_PREFIX)

    # inizio di un manifest HLS incollato come testo (il BOM va tolto prima)
    M3U8_MANIFEST_MARKER = '#EXTM3U'

    @classmethod
    def isM3u8ManifestText(cls, text):
        return text.lstrip('﻿').strip().startswith(cls.M3U8_MANIFEST_MARKER)

    @classmethod
    def stripBom(cls, text):
        return text.lstrip('﻿').strip()

    @classmethod
    def _decodePastylinkV1(cls, url):
        payload = url[len(cls.PASTYLINK_URL_PREFIX):]
        padded = payload + '=' * (-len(payload) % 4)
        try:
            data = json.loads(base64.b64decode(padded))
            return data.get('v1') or {}
        except Exception:
            return None

    @classmethod
    def decodePastylinkUrl(cls, url):
        v1 = cls._decodePastylinkV1(url)
        return (v1 or {}).get('ytdlp') or None

    @classmethod
    def decodePastylinkReferer(cls, url):
        v1 = cls._decodePastylinkV1(url)
        return (v1 or {}).get('referer') or None

    @staticmethod
    def uriValidator(x):
        try:
            result = urlparse(x)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    @staticmethod
    def getHostFromUrl(url):
        parsed_uri = urlparse(url)
        return parsed_uri.netloc

    @classmethod
    def readFileJson(cls, link, timeout=10):
        if link.startswith('http'):
            req = cls.sendRequestGet(link, timeout=timeout)
            if req is None:
                raise ConnectionError("Unable to reach " + link)
            data = req.text.strip()
        elif link.startswith(':/'):
            data = cls.readFileFromResource(link)
        else:
            f = open (link, "r")
            data = f.read()
            f.close()
        return json.loads(data)

    @staticmethod
    def readFileFromResource(path):
        fd = QFile(path)
        if not fd.open(QIODevice.ReadOnly | QFile.Text):
            raise IOError("Unable to open resource: " + path)
        content = QTextStream(fd).readAll()
        fd.close()
        return content

    @staticmethod
    def parseSemVer(version):
        if isinstance(version, (int, float)):
            raise ValueError("Version must be a string, got %s: %r" % (type(version).__name__, version))
        match = re.match(r'^v?(\d+)\.(\d+)(?:\.(\d+))?', str(version).strip())
        if not match:
            raise ValueError("Invalid version string: %s" % version)
        major, minor, patch = match.groups()
        return (int(major), int(minor), int(patch or 0))

    @classmethod
    def isNewerVersion(cls, onlineVersion, thisVersion):
        return cls.parseSemVer(onlineVersion) > cls.parseSemVer(thisVersion)

    @classmethod
    def urlToFilename(cls, url):
        if url.startswith(cls.getTempDirectory()):
            url = 'file:/' + url
        host = cls.slugify(cls.getHostFromUrl(url))
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return host + '_' + hashlib.md5(url.encode('utf-8')).hexdigest() + '_'  + stamp

    @staticmethod
    def slugify(value):
        """
        Taken from https://github.com/django/django/blob/master/django/utils/text.py
        Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
        dashes to single dashes. Remove characters that aren't alphanumerics,
        underscores, or hyphens. Convert to lowercase. Also strip leading and
        trailing whitespace, dashes, and underscores.
        """
        value = str(value)
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
        value = re.sub(r'[^\w\s-]', '', value.lower())
        return re.sub(r'[-\s]+', '-', value).strip('-_')

    @staticmethod
    def removeFile(f):
        if os.path.exists(f):
            os.remove(f)
            return True
        else:
            return False

    @staticmethod
    def createFile(f):
        if os.path.exists(f):
            logging.info('File %s already created' % f)
            return None
        try:
            open(f, 'a').close()
            return True
        except OSError:
            logging.error('Failed creating the file')
            return False

    @staticmethod
    def renameFile(old, new):
        try:
            os.rename(old, new)
            return True
        except OSError:
            logging.error('Failed renaming the file')
            return False

    @staticmethod
    def getFilenameFromFullPath(path):
        return Path(path).name

    @classmethod
    def downloadPath(cls):
        settings = cls.getSettings()
        if settings.value('downloadPath'):
            return settings.value('downloadPath')
        if Constants.IS_ANDROID:
            # targetSdk 28 -> storage legacy: il path pubblico e' scrivibile con
            # os/open senza MediaStore (vedi ANDROID.md). Se WRITE_EXTERNAL_STORAGE
            # manca, checkDownloadFolder() all'avvio lo intercetta.
            public_download = '/storage/emulated/0/Download'
            try:
                os.makedirs(public_download, exist_ok=True)
            except OSError:
                pass
            return public_download
        path_desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        path_pasty = os.path.join(path_desktop, 'Pastylink')
        try:
            os.mkdir(path_pasty)
        except OSError as error:
            pass
        return path_pasty

    PROGRESS_THROTTLE_SECONDS = 0.5

    STOP_CHECK_INTERVAL_SECONDS = 0.3

    # sotto questa soglia l'output e' quasi certamente un container vuoto/troncato
    MIN_VALID_OUTPUT_SIZE_BYTES = 1024

    # il 403 di YouTube su alcuni client di fallback e' intermittente: un retry
    # e' piu' efficace di qualunque cambio di formato/client
    YTDLP_MAX_ATTEMPTS = 3
    YTDLP_RETRY_DELAY_SECONDS = 2

    # grace period fra SIGTERM e SIGKILL: un processo bloccato in I/O puo'
    # ignorare il SIGTERM
    TERMINATE_GRACE_SECONDS = 3

    @staticmethod
    def _terminateProcessTree(process):
        if Constants.IS_ANDROID:
            # niente psutil su Android; basta subprocess.Popen (command sempre
            # senza shell, quindi ffmpeg/yt-dlp e' l'unico processo diretto)
            try:
                process.terminate()
                process.wait(timeout=Tools.TERMINATE_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
            except ProcessLookupError:
                pass
            return
        import psutil  # import locale: niente recipe Android
        try:
            parent = psutil.Process(process.pid)
        except psutil.NoSuchProcess:
            return
        procs = parent.children(recursive=True) + [parent]
        for p in procs:
            try:
                p.terminate()
            except psutil.NoSuchProcess:
                pass
        _, stillAlive = psutil.wait_procs(procs, timeout=Tools.TERMINATE_GRACE_SECONDS)
        for p in stillAlive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass

    @staticmethod
    def _spawnWithStopWatcher(command, isStoppedFn=None):
        """Avvia un processo e, se isStoppedFn e' passato, un thread che lo
        termina (con tutto l'albero di figli) appena isStoppedFn() diventa vero."""
        # stderr=STDOUT: due pipe separate non drenate insieme -> deadlock
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding='utf-8', errors='replace', bufsize=1, **Tools._noConsoleWindowKwargs())
        stoppedHolder = {'stopped': False}
        watcher = None
        if isStoppedFn:
            def watchForStop():
                while process.poll() is None:
                    if isStoppedFn():
                        stoppedHolder['stopped'] = True
                        Tools._terminateProcessTree(process)
                        return
                    time.sleep(Tools.STOP_CHECK_INTERVAL_SECONDS)
            watcher = threading.Thread(target=watchForStop, daemon=True)
            watcher.start()
        return process, stoppedHolder, watcher

    @staticmethod
    def _runFFmpegWithProgress(command, saveAs, onProgress=None, isStoppedFn=None):
        """ffmpeg (-progress pipe:1) in un loop bloccante, da guidare via
        run_in_executor. Ogni heartbeat di progresso ricontrolla la dimensione
        reale di saveAs su disco (total_size di ffmpeg non e' affidabile con
        -c copy). Lo Stop e' sorvegliato da un thread, non solo tra le righe di
        stdout (ffmpeg puo' restare muto a lungo su uno stream stallato)."""
        process, stoppedHolder, watcher = Tools._spawnWithStopWatcher(command, isStoppedFn)
        lastUpdate = 0
        outputLines = []  # righe non di progresso: warning/errori di ffmpeg
        for line in process.stdout:
            line = line.strip()
            if line in ('progress=continue', 'progress=end'):
                if onProgress:
                    now = time.time()
                    if now - lastUpdate >= Tools.PROGRESS_THROTTLE_SECONDS:
                        lastUpdate = now
                        size = Tools.getSizeInByte(saveAs)
                        if size:
                            onProgress(size)
            elif line:
                outputLines.append(line)
        process.stdout.close()
        process.wait()
        if watcher:
            watcher.join(timeout=1)
        return stoppedHolder['stopped'], process.returncode, '\n'.join(outputLines)

    @staticmethod
    def _accumulateYtDlpProgress(status, downloadedBytes, phaseState):
        """yt-dlp scarica video e audio in fasi separate, i byte ripartono da
        zero ad ogni fase. Ritorna il totale cumulativo (fasi concluse + fase
        corrente), o None se l'hook non e' rilevante. phaseState['total'] mutato
        in place, persiste tra le chiamate dello stesso download."""
        downloadedBytes = downloadedBytes or 0
        if status == 'downloading':
            return phaseState['total'] + downloadedBytes
        if status == 'finished':
            phaseState['total'] += downloadedBytes
            return phaseState['total']
        return None

    @staticmethod
    def _ffmpegSucceeded(returncode, saveAs, stderr):
        """returncode 0 non basta: ffmpeg puo' uscire pulito lasciando un file
        vuoto/troncato. Controlla anche stderr e la dimensione minima."""
        if returncode != 0:
            return False
        if 'Output file is empty' in stderr:
            return False
        size = os.path.getsize(saveAs) if os.path.exists(saveAs) else 0
        return size > Tools.MIN_VALID_OUTPUT_SIZE_BYTES

    # righe di stream di 'ffmpeg -i': "Stream #0:6[0x6]: Video: h264 ..., 1920x1080 ..."
    _FFMPEG_STREAM_LINE_RE = re.compile(r'Stream #0:(\d+).*?:\s*(Video|Audio|Subtitle):.*')
    _FFMPEG_RESOLUTION_RE = re.compile(r'(\d{2,5})x(\d{2,5})')

    @staticmethod
    def _probeHlsStreams(ffmpeg, url, referer, isStoppedFn=None, timeout=15):
        """Elenca gli stream di un manifest HLS senza scaricare segmenti. Serve
        perche' con un -map esplicito ffmpeg disattiva la selezione automatica,
        quindi va scelto anche il video migliore (l'ordine delle varianti non e'
        garantito dallo standard)."""
        command = [ffmpeg, '-hide_banner']
        if referer:
            command += ['-referer', referer]
        command += ['-i', url]
        result = Tools.runCommand(command, timeout=timeout, isStoppedFn=isStoppedFn)
        bestVideoIndex, bestArea = None, -1
        hasAudio, hasSubtitle = False, False
        if not result or result.interrupted or not result.stdout:
            return None, False, False
        for match in Tools._FFMPEG_STREAM_LINE_RE.finditer(result.stdout):
            index, kind = int(match.group(1)), match.group(2)
            if kind == 'Audio':
                hasAudio = True
            elif kind == 'Subtitle':
                hasSubtitle = True
            elif kind == 'Video':
                sizeMatch = Tools._FFMPEG_RESOLUTION_RE.search(match.group(0))
                area = int(sizeMatch.group(1)) * int(sizeMatch.group(2)) if sizeMatch else 0
                if area > bestArea:
                    bestArea, bestVideoIndex = area, index
        return bestVideoIndex, hasAudio, hasSubtitle

    @staticmethod
    async def downloadVideoByFFmpeg(ffmpeg, url, referer, saveAs, onProgress=None, isStoppedFn=None):
        try:
            command = [ffmpeg]
            if referer:
                command += ['-referer', referer]
            command += ['-hide_banner', '-protocol_whitelist', 'file,http,https,tcp,tls,crypto',
                        '-loglevel', 'warning', '-y', '-progress', 'pipe:1', '-i', url]
            loop = asyncio.get_running_loop()
            # solo per m3u8: mappa il video migliore + sottotitoli soft. Per gli
            # altri url non serve e costerebbe solo tempo.
            if '.m3u8' in url.lower():
                bestVideoIndex, hasAudio, hasSubtitle = await loop.run_in_executor(
                    None, Tools._probeHlsStreams, ffmpeg, url, referer, isStoppedFn)
                if bestVideoIndex is not None:
                    command += ['-map', '0:%d' % bestVideoIndex]
                    if hasAudio:
                        command += ['-map', '0:a:0?']
                    if hasSubtitle:
                        command += ['-map', '0:s:0?']
                    command += ['-c:v', 'copy', '-c:a', 'copy']
                    if hasSubtitle:
                        command += ['-c:s', 'mov_text']  # unico codec sottotitoli per mp4
                else:
                    command += ['-c', 'copy']
            else:
                command += ['-c', 'copy']
            command += ['-bsf:a', 'aac_adtstoasc', saveAs]
            stopped, returncode, stderr = await loop.run_in_executor(None, Tools._runFFmpegWithProgress, command, saveAs, onProgress, isStoppedFn)
            if stopped:
                return [None, 'Stop forced by the user']
            if Tools._ffmpegSucceeded(returncode, saveAs, stderr):
                return [True, Tools.getSizeDynamic(saveAs)]
            # aac_adtstoasc vale solo per audio AAC/ADTS: su altri codec ffmpeg
            # si rifiuta, ritentiamo senza il filtro
            if 'not supported by the bitstream filter' in stderr:
                retryCommand = list(command)
                if '-bsf:a' in retryCommand:
                    i = retryCommand.index('-bsf:a')
                    del retryCommand[i:i + 2]
                stopped, returncode, stderr = await loop.run_in_executor(None, Tools._runFFmpegWithProgress, retryCommand, saveAs, onProgress, isStoppedFn)
                if stopped:
                    return [None, 'Stop forced by the user']
                if Tools._ffmpegSucceeded(returncode, saveAs, stderr):
                    return [True, Tools.getSizeDynamic(saveAs)]
            logging.error('FFmpeg error: ' + stderr)
            logging.error(command)
            return [False, stderr or 'FFmpeg produced no usable output']
        except Exception as err:
            logging.error(str(err))
            return [False, 'Download error #1']

    # Estensione di output per formato audio ('aac' -> .m4a, piu' compatibile di .aac)
    AUDIO_FORMAT_EXTENSIONS = {
        'mp3': 'mp3',
        'aac': 'm4a',
        'flac': 'flac',
        'wav': 'wav',
        'opus': 'opus',
    }

    # Encoder ffmpeg per formato. Su Android la recipe ffmpeg ha libshine (non
    # libmp3lame) e solo l'encoder opus nativo.
    AUDIO_FORMAT_CODECS = {
        'mp3': 'libshine' if Constants.IS_ANDROID else 'libmp3lame',
        'aac': 'aac',
        'flac': 'flac',
        'wav': 'pcm_s16le',
        'opus': 'opus' if Constants.IS_ANDROID else 'libopus',
    }

    @staticmethod
    async def ConvertAudioByFFmpeg(ffmpeg, newFile, oldVideo, audioFormat, onProgress=None, isStoppedFn=None):
        try:
            codec = Tools.AUDIO_FORMAT_CODECS.get(audioFormat, Tools.AUDIO_FORMAT_CODECS['mp3'])
            # -vn: senza, una copertina imbarcata puo' far scegliere a ffmpeg un muxer diverso
            command = [ffmpeg, '-hide_banner', '-loglevel', 'warning', '-y', '-progress', 'pipe:1', '-i', oldVideo, '-vn', '-c:a', codec, newFile]
            loop = asyncio.get_running_loop()
            stopped, returncode, stderr = await loop.run_in_executor(None, Tools._runFFmpegWithProgress, command, newFile, onProgress, isStoppedFn)
            # out
            if stopped:
                return [None, 'Stop forced by the user']
            if Tools._ffmpegSucceeded(returncode, newFile, stderr):
                return [True, Tools.getSizeDynamic(newFile)]
            logging.error('FFmpeg error: ' + stderr)
            logging.error(command)
            return [False, stderr or 'FFmpeg produced no usable output']
        except Exception as err:
            logging.error(str(err))
            return [False, 'Conversion error #1']

    @classmethod
    async def downloadAsyncGeneric(cls, src_url, saveAs, parentApp = None, onProgress=None, chunk_size=65536):
        import aiohttp, aiofiles  # import locali, vedi ANDROID.md
        connector = None
        if Constants.IS_ANDROID:
            # aiohttp non trova il bundle CA in automatico su Android
            import ssl, certifi
            connector = aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()))
        try:
            written = 0
            lastUpdate = 0
            async with aiohttp.ClientSession(connector=connector) as session:
                # niente 'br' in Accept-Encoding: un pacchetto brotli incompatibile
                # farebbe fallire il download con un errore criptico
                async with session.get(src_url, headers={'Accept-Encoding': 'gzip, deflate'}) as resp:
                    resp.raise_for_status()  # senza, una pagina d'errore verrebbe salvata come download riuscito
                    responseContentType = resp.headers.get('Content-Type', '')
                    if responseContentType.split(';')[0].strip().lower().startswith('text/html'):
                        return [False, 'The content is a webpage, not a downloadable file']
                    async with aiofiles.open(saveAs, 'wb') as fd:
                        async for chunk in resp.content.iter_chunked(chunk_size):
                            await fd.write(chunk)
                            written += len(chunk)
                            if onProgress:
                                now = time.time()
                                if now - lastUpdate >= cls.PROGRESS_THROTTLE_SECONDS:
                                    lastUpdate = now
                                    onProgress(written)
                            if parentApp and parentApp.isStopped():
                                raise asyncio.CancelledError
            return [True, Tools.getSizeDynamic(saveAs)]
        except asyncio.CancelledError as err:
            logging.info("Forced stop #2")
            return [None, 'Stop forced by the user']
        except Exception as err:
            logging.error(str(err))
            return [False, str(err)]

    @staticmethod
    def downloadNotAsyncGeneric(url, saveAs, isStopped=None, timeout=None):
        import requests  # import locale, vedi ANDROID.md
        try:
            with requests.get(url, stream=True, allow_redirects=True, timeout=timeout) as r:
                r.raise_for_status()
                with open(saveAs, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                        if isStopped and isStopped():
                            raise asyncio.CancelledError
            return [True, Tools.getSizeDynamic(saveAs)]
        except asyncio.CancelledError as err:
            logging.info("Forced stop #2")
            return [None, 'Stop forced by the user']
        except Exception as err:
            logging.error(str(err))
            return [False, str(err)]

    @classmethod
    def logYtDlpVersion(cls, packageDir):
        ytdlp = cls._importYtDlp(packageDir)
        version = ytdlp.version.__version__ if ytdlp else 'unknown'
        Tools.consoleLogs("Used: yt-dlp version " + version)

    # True se usare i cookie del browser per i contenuti con login. Preferenza
    # esplicita (checkbox); se mai toccata, default off su macOS (prompt
    # Portachiavi/TCC inatteso), on altrove. Sempre False su Android.
    @staticmethod
    def browserLoginConsentEnabled():
        if Constants.IS_ANDROID:
            return False
        stored = Tools.getSettings().value('browserLoginConsent')
        if stored in ('yes', 'no'):
            return stored == 'yes'
        return sys.platform != 'darwin'

    # Primo browser che ha un cookie per il dominio dell'url, o None. "Primo che
    # esiste" ~= "il piu' recente" (yt-dlp non espone l'ultimo uso). Su Android
    # non trova mai nulla (sandboxing).
    @staticmethod
    def _pickCookiesBrowser(url):
        try:
            import yt_dlp.cookies as ytdlpCookies
        except ImportError:
            return None
        domain = (urlparse(url).hostname or '').lower()
        if not domain:
            return None
        candidates = ['chrome', 'firefox', 'edge', 'brave']
        if sys.platform == 'darwin':
            candidates.append('safari')
        for browser in candidates:
            try:
                jar = ytdlpCookies.extract_cookies_from_browser(browser)
                for cookie in jar:
                    cookieDomain = cookie.domain.lstrip('.').lower()
                    if domain == cookieDomain or domain.endswith('.' + cookieDomain):
                        return browser
            except Exception:
                continue  # un browser illeggibile non deve far fallire la funzione
        return None

    # Probe di classificazione (PastedUrl._analyze): yt-dlp trova qualcosa su
    # questa pagina generica? extract_info(download=False), in-process con
    # timeout breve (un processo figlio non varrebbe il costo, gira spesso).
    @classmethod
    def isYtDlpDownloadable(cls, url, timeout=20):
        try:
            packageDir = cls.checkYtDlp()
            if not packageDir:
                return False
            ytdlp = cls._importYtDlp(packageDir)
            if not ytdlp:
                return False

            # socket_timeout limita solo le singole richieste, non la durata di
            # extract_info(): il limite rigido serve un thread daemon con
            # join(timeout) - non un kill vero, ma basta per una probe di sola lettura
            resultBox = []

            def _probe():
                try:
                    with ytdlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'noplaylist': True,
                                           'simulate': True, 'socket_timeout': timeout}) as ydl:
                        resultBox.append(ydl.extract_info(url, download=False))
                except Exception as err:
                    # logging.error (non consoleLogs): deve comparire anche nei build
                    # compilati, dove isDevMode() e' sempre False
                    logging.error("yt-dlp simulate failed for %s: %s" % (url, err))
                    resultBox.append(None)

            probeThread = threading.Thread(target=_probe, daemon=True)
            probeThread.start()
            probeThread.join(timeout * 2)  # margine per richieste sequenziali lente
            if probeThread.is_alive():
                logging.error("yt-dlp simulate: timeout scaduto per " + url)
                return False
            info = resultBox[0] if resultBox else None
            return info is not None
        except Exception as err:
            cls.consoleLogs("Error: yt-dlp simulate - " + str(err))
            return False

    YTDLP_TERMINATE_GRACE_SECONDS = 3  # grace fra terminate() e kill()

    # Download yt-dlp in un processo figlio (bloccante, da chiamare via
    # run_in_executor). Processo separato per poterlo killare in qualunque
    # momento allo Stop (una libreria in-process non lo permetterebbe).
    @staticmethod
    def _runYtDlpInProcess(packageDir, ffmpegPath, url, saveAs, referer, onProgress=None, isStoppedFn=None, subtitleLangs=None, useBrowserCookies=False):
        ctx = multiprocessing.get_context('spawn')
        resultQueue = ctx.Queue()
        ejsDir = Tools.checkYtDlpEjs()  # risolto qui, il figlio non puo' (vedi _ytDlpDownloadWorker)
        process = ctx.Process(target=_ytDlpDownloadWorker,
                               args=(packageDir, ffmpegPath, url, saveAs, referer, ejsDir, subtitleLangs, useBrowserCookies, resultQueue),
                               daemon=True)
        process.start()
        lastUpdate = 0
        stopped, success, errorDetail = False, False, ''
        while True:
            if isStoppedFn and isStoppedFn():
                # il figlio potrebbe aver gia' messo 'done' un istante prima:
                # un ultimo check non bloccante evita di riportare "interrotto"
                try:
                    kind, *payload = resultQueue.get_nowait()
                    if kind == 'done':
                        success, errorDetail = payload[0], payload[1]
                        break
                except queue.Empty:
                    pass
                stopped = True
                break
            try:
                kind, *payload = resultQueue.get(timeout=Tools.STOP_CHECK_INTERVAL_SECONDS)
            except queue.Empty:
                if not process.is_alive():
                    break  # il figlio e' morto senza mandare 'done'
                continue
            if kind == 'progress':
                if onProgress:
                    now = time.time()
                    if now - lastUpdate >= Tools.PROGRESS_THROTTLE_SECONDS:
                        lastUpdate = now
                        onProgress(payload[0])
            elif kind == 'done':
                success, errorDetail = payload[0], payload[1]
                break
        if stopped:
            process.terminate()
            process.join(timeout=Tools.YTDLP_TERMINATE_GRACE_SECONDS)
        else:
            process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)
        resultQueue.close()
        return stopped, success, errorDetail

    # Come _runYtDlpInProcess ma in un thread (Android): stesso protocollo
    # 'progress'/'done'. Un thread non si puo' uccidere a forza: se lo Stop
    # arriva prima del primo progress_hook, il download prosegue in background
    # (la riga in UI risulta comunque "Stopped" subito).
    @staticmethod
    def _runYtDlpInThread(packageDir, ffmpegPath, url, saveAs, referer, onProgress=None, isStoppedFn=None, subtitleLangs=None, useBrowserCookies=False):
        resultQueue = _ThreadResultQueue()
        ejsDir = Tools.checkYtDlpEjs()
        thread = threading.Thread(target=_ytDlpDownloadWorker,
                                   args=(packageDir, ffmpegPath, url, saveAs, referer, ejsDir, subtitleLangs, useBrowserCookies, resultQueue),
                                   daemon=True)
        thread.start()
        lastUpdate = 0
        stopped, success, errorDetail = False, False, ''
        while True:
            if isStoppedFn and isStoppedFn():
                # il thread potrebbe aver gia' messo 'done' un istante prima:
                # un ultimo check non bloccante evita di riportare "interrotto"
                try:
                    kind, *payload = resultQueue.get_nowait()
                    if kind == 'done':
                        success, errorDetail = payload[0], payload[1]
                        break
                except queue.Empty:
                    pass
                stopped = True
                break
            try:
                kind, *payload = resultQueue.get(timeout=Tools.STOP_CHECK_INTERVAL_SECONDS)
            except queue.Empty:
                if not thread.is_alive():
                    break  # il thread e' morto senza mandare 'done'
                continue
            if kind == 'progress':
                if onProgress:
                    now = time.time()
                    if now - lastUpdate >= Tools.PROGRESS_THROTTLE_SECONDS:
                        lastUpdate = now
                        onProgress(payload[0])
            elif kind == 'done':
                success, errorDetail = payload[0], payload[1]
                break
        if not stopped:
            thread.join(timeout=1)
        return stopped, success, errorDetail

    # Scarica (e fonde video+audio) direttamente con yt-dlp, con retry.
    @classmethod
    async def downloadVideoByYtDlp(cls, packageDir, ffmpegPath, url, saveAs, onProgress=None, isStoppedFn=None, referer=None, subtitleLangs=None, useBrowserCookies=False):
        try:
            cls.logYtDlpVersion(packageDir)
            loop = asyncio.get_running_loop()
            errorDetail = ''
            runner = Tools._runYtDlpInThread if Constants.IS_ANDROID else Tools._runYtDlpInProcess
            for attempt in range(cls.YTDLP_MAX_ATTEMPTS):
                stopped, success, errorDetail = await loop.run_in_executor(
                    None, runner, packageDir, ffmpegPath, url, saveAs, referer, onProgress, isStoppedFn, subtitleLangs, useBrowserCookies)
                if stopped:
                    return [None, 'Stop forced by the user']
                if success and os.path.exists(saveAs) and os.path.getsize(saveAs) > cls.MIN_VALID_OUTPUT_SIZE_BYTES:
                    return [True, Tools.getSizeDynamic(saveAs)]
                if attempt < cls.YTDLP_MAX_ATTEMPTS - 1:
                    Tools.consoleLogs('yt-dlp attempt %d/%d failed, retrying: %s' % (attempt + 1, cls.YTDLP_MAX_ATTEMPTS, errorDetail))
                    await asyncio.sleep(cls.YTDLP_RETRY_DELAY_SECONDS)
                    if isStoppedFn and isStoppedFn():
                        return [None, 'Stop forced by the user']
            logging.error('yt-dlp error: ' + errorDetail)
            return [False, errorDetail or 'yt-dlp produced no usable output']
        except Exception as err:
            logging.error(str(err))
            return [False, 'Download error #3']

    @staticmethod
    def getSizeInByte(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return None

    @staticmethod
    def formatSize(size):
        if not size:
            return "0.0 bytes"
        for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return "%3.1f %s" % (size, x)
            size /= 1024.0

    @classmethod
    def getSizeDynamic(cls, path):
        return cls.formatSize(cls.getSizeInByte(path))

    # se il file esiste gia', appende _(HH-MM-SS)
    @classmethod
    def getBestFilenameToSaveAs(cls, url, ext):
        saveAs = os.path.join(cls.downloadPath(), cls.urlToFilename(url)) + ext
        if not os.path.exists(saveAs):
            return saveAs
        now = datetime.now()
        return saveAs.rsplit('.',1)[0] + '_(' + now.strftime("%H-%M-%S") + ')' + ext
    @staticmethod
    def getOs():
        platf = platform.system()
        if platf == "Linux":
            return 'linux'
        elif platf == "Darwin":
            return 'mac'
        elif platf == "Windows":
            return 'win'
        else:
            return None

    @classmethod
    def getVersion(cls):
        return Constants.APP_VERSION

    @classmethod
    def openFolder(cls, foldername):
        if cls.getOs() == 'linux':
            try:
                subprocess.run(['dbus-send', '--print-reply', '--dest=org.freedesktop.FileManager1',
                                 '/org/freedesktop/FileManager1', 'org.freedesktop.FileManager1.ShowItems',
                                 'array:string:file://%s/*' % foldername, 'string:'])
            except Exception:
                pass
        elif cls.getOs() == 'mac':
            try:
                subprocess.run(['open', foldername])
            except Exception:
                pass
        else:
            os.startfile(foldername)

    # Apre il file con l'app predefinita (doppio click su una riga completata).
    # Linux: xdg-open, non il dbus/ShowItems di openFolder (che solo evidenzia).
    @classmethod
    def openFile(cls, filepath):
        if Constants.IS_ANDROID:
            AndroidBridge.openFile(filepath)
            return
        try:
            osName = cls.getOs()
            if osName == 'linux':
                subprocess.run(['xdg-open', filepath])
            elif osName == 'mac':
                subprocess.run(['open', filepath])
            else:
                os.startfile(filepath)
        except Exception as err:
            cls.consoleLogs("Impossibile aprire il file: " + str(err))

    @staticmethod
    def writeThisInFile(content, pathfile):
        try:
            f = open(pathfile, "w")
            f.write(content)
            f.close()
            return True
        except Exception:
            return False

    # 'EXE' se avviato da eseguibile/APK, 'DEV' se da sorgente
    @staticmethod
    def runType():
        if Constants.IS_ANDROID:
            return 'EXE'
        elif getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return 'EXE'
        else:
            return 'DEV'

    @classmethod
    def isDevMode(cls):
        return cls.runType() == 'DEV'

    # non piu' usato (recuperava i binari ffmpeg/yt-dlp imbarcati)
    @staticmethod
    def resourcePath(relative_path):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, 'bin', relative_path)

    @classmethod
    def showFileInNautilus(cls, path):
        if cls.getOs() == 'win':
            subprocess.Popen(r'explorer /select,"%s"' % path)
            subprocess.Popen(r'explorer /open,"%s"' % path)

    @staticmethod
    def copyToClipboard(text):
        cb = QApplication.clipboard()
        cb.clear(mode=QClipboard.Mode.Clipboard)
        cb.setText(text, mode=QClipboard.Mode.Clipboard)

    @staticmethod
    def pasteFromClipboard():
        return QApplication.clipboard().text()

    @classmethod
    def openDownloadFolder(cls):
        cls.openFolder(cls.downloadPath())

    @staticmethod
    def replaceExtension(filename, newExt):
        return filename.rsplit('.', 1)[0] + '.' + newExt

    # Connessione TCP a 8.8.8.8:53: dice solo "c'e' rete o no"
    @staticmethod
    def hasInternetConnection(timeout=3):
        try:
            with socket.create_connection(("8.8.8.8", 53), timeout=timeout):
                return True
        except OSError:
            return False

    @classmethod
    def sendRequestGet(cls, url, timeout = 10):
        import requests  # import locale
        try:
            cls.consoleLogs("Sent 'get' request to " + url)
            req = requests.get(url, timeout = timeout)
            return req
        except Exception as err:
            cls.consoleLogs("Not sent 'get' request to " + url + "because of: " + str(err))
            return None

    @classmethod
    def sendRequestPost(cls, url, params = None, timeout = 3):
        import requests  # import locale
        try:
            cls.consoleLogs("Sent 'post' request to " + url)
            req = requests.post(url, data = params, timeout = timeout)
            return req
        except Exception as err:
            cls.consoleLogs("Not sent 'post' request to " + url + "because of: " + str(err))
            return None

    @staticmethod
    def confirmDialog(txt):
        messageBox = QMessageBox()
        messageBox.setText(txt)
        messageBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        messageBox.exec()
        return messageBox.standardButton(messageBox.clickedButton()) == QMessageBox.Yes

    @classmethod
    def consoleLogs(cls, str):
        if cls.isDevMode():
            logging.debug(str)

    @staticmethod
    def getTempDirectory():
        return tempfile.gettempdir()

    @classmethod
    def writeM3u8InFile(cls, pasted):
        now = datetime.now()
        tmpfile = os.path.join(cls.getTempDirectory(), now.strftime("EXTM3U_%H-%M-%S")+'.m3u8')
        cls.writeThisInFile(pasted, tmpfile)
        return tmpfile
