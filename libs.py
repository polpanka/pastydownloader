#!/usr/bin/python

import os, sys, socket, subprocess, platform, unicodedata, re, shlex, json, requests, asyncio, aiofiles, aiohttp, base64, tempfile, hashlib, time, threading, psutil, shutil, multiprocessing, queue, zipfile
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QFile, QTextStream, QIODevice, QSettings, QStandardPaths, QLockFile
from PySide6.QtGui import QClipboard
from testi import MyText
from constants import Constants

import hashlib
import logging

# Configurazione base del logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('urllib3').setLevel(logging.WARNING)


# Timeout di rete passato a yt-dlp per ogni singola richiesta HTTP (non per il
# download intero, che puo' durare molto piu' a lungo): senza, una richiesta
# che si blocca prima del primo progress_hook (es. durante l'estrazione delle
# info) non avrebbe nessun punto in cui yt-dlp stesso possa accorgersi dello
# Stop - qui e' comunque solo una rete di sicurezza secondaria, dato che lo
# Stop vero e proprio termina l'intero processo figlio (vedi
# Tools._runYtDlpInProcess), non dipende da questo timeout
YTDLP_SOCKET_TIMEOUT_SECONDS = 30


# Entry point del processo figlio avviato da Tools._runYtDlpInProcess per ogni
# download yt-dlp. Deve restare una funzione di modulo (mai un metodo/closure
# legato a QObject o ad altro stato non serializzabile): multiprocessing con
# lo start method 'spawn' (vedi _runYtDlpInProcess) la richiama per riferimento
# in un interprete Python nuovo, che deve poterla importare da capo - e'
# proprio questo a permettere di uccidere il download in qualunque momento con
# un semplice process.terminate()/kill(), esattamente come si faceva col
# subprocess esterno di prima, pur restando yt-dlp una libreria Python
# importata (niente piu' binario per SO scaricato a parte, vedi ytdlp_updater.py)
def _ytDlpDownloadWorker(packageDir, ffmpegPath, url, saveAs, referer, ejsDir, resultQueue):
    if packageDir not in sys.path:
        sys.path.insert(0, packageDir)
    # ejsDir e' gia' risolto dal processo padre (vedi _runYtDlpInProcess), non
    # va ricalcolato qui con Tools.checkYtDlpEjs()/QStandardPaths: verificato
    # che in un processo figlio spawnato, senza QCoreApplication con
    # applicationName/organizationName impostati (mai fatto qui, questo
    # processo non esegue il vero main.py), QStandardPaths.AppDataLocation
    # risolve una cartella generica diversa da quella vera dell'app - avrebbe
    # cercato yt_dlp_ejs nel posto sbagliato, non trovando mai nulla
    if ejsDir and ejsDir not in sys.path:
        sys.path.insert(0, ejsDir)
    import yt_dlp
    Tools._registerEmbeddedQuickJsProvider(yt_dlp)

    phaseState = {'total': 0}

    def onHook(d):
        # sul path "file gia' scaricato" (continuedl, es. un retry che ritrova
        # l'output di un tentativo precedente) yt-dlp manda 'finished' con solo
        # total_bytes valorizzato, downloaded_bytes resta assente - senza
        # questo fallback quella fase verrebbe sommata come 0 invece che col
        # suo totale reale (vedi DownloadHandler.download in downloader/common.py)
        bytesForThisEvent = d.get('downloaded_bytes')
        if bytesForThisEvent is None and d.get('status') == 'finished':
            bytesForThisEvent = d.get('total_bytes')
        reported = Tools._accumulateYtDlpProgress(d.get('status'), bytesForThisEvent, phaseState)
        if reported is not None:
            resultQueue.put(('progress', reported))

    # cattura sia i veri warning/errori sia i messaggi informativi
    # ("[youtube] Extracting URL...") che yt-dlp instrada tutti verso
    # logger.debug quando gli si passa un logger custom (vedi to_screen() in
    # YoutubeDL.py) - stesso principio delle infoLines di prima: spesso sono
    # l'indizio decisivo per capire un fallimento (quale client/formato ha
    # tentato) senza dover rilanciare yt-dlp a mano con -v
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
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': saveAs,
        'progress_hooks': [onHook],
        'socket_timeout': YTDLP_SOCKET_TIMEOUT_SECONDS,
    }
    if referer:
        ydlOpts['http_headers'] = {'Referer': referer}
    try:
        with yt_dlp.YoutubeDL(ydlOpts) as ydl:
            ydl.download([url])
        resultQueue.put(('done', True, ''))
    except Exception as err:
        messages.append(str(err))
        resultQueue.put(('done', False, '\n'.join(messages[-5:])))
    finally:
        # multiprocessing.Queue scrive davvero sulla pipe tramite un thread
        # interno separato: senza chiudere e aspettare che questo thread abbia
        # finito, il processo puo' uscire prima che il 'done' appena messo sia
        # stato consegnato per davvero, e il genitore lo scambierebbe per un
        # crash silenzioso (vedi Tools._runYtDlpInProcess) - un download
        # riuscito verrebbe segnalato come fallito
        resultQueue.close()
        resultQueue.join_thread()


def _ytDlpVerifyWorker(packageDir, resultQueue):
    """Entry point del processo figlio di verifica post-install (vedi
    Tools.verifyYtDlpImportable, usato da YtDlpUpdater dopo ogni download) -
    stessa ragione di _ytDlpDownloadWorker per restare una funzione di modulo.
    Gira in un interprete Python nuovo per due motivi: un wheel corrotto/
    incompleto non lascia nessuno stato nel processo principale se il suo
    import fallisce, e il processo principale potrebbe gia' avere un'altra
    versione di yt_dlp cacheata in sys.modules (vedi Tools._importYtDlp), che
    lo farebbe apparire "importabile" anche se la versione appena scaricata e'
    in realta' rotta. Funziona identico da sorgente e da eseguibile PyInstaller
    frozen (dove non esiste un python -c generico da poter lanciare a parte)"""
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


class Tools():
    # ffmpeg non e' piu' imbarcato nell'eseguibile: viene scaricato al primo
    # avvio da FfmpegInstaller e installato in ffmpegStorageDir() (vedi
    # checkFFmpeg). Questi restano solo i nomi dei file attesi per SO, url di
    # download in ffmpeg_installer.py

    # Windows - build "essentials" (rolling, aggiornata ad ogni commit):
    # https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-essentials.7z
    # Nota: e' un .7z con filtro BCJ2, non estraibile in puro Python (py7zr non
    # lo supporta) - per questo il download effettivo usa la build BtbN in .zip
    # (stessa fonte gia' verificata per Linux), vedi FfmpegInstaller.URLS
    FFMPEG_BIN_WIN = 'ffmpeg.exe'

    # macOS - build ufficiale evermeet.cx (versionata, non rolling):
    # https://evermeet.cx/ffmpeg/ffmpeg-9.0.1.zip
    FFMPEG_BIN_MAC = 'ffmpeg_mac'

    # Linux - build BtbN (dipende dalla glibc di sistema: richiede glibc >= 2.28,
    # quindi incompatibile con distro molto datate come Ubuntu 18.04/RHEL 7, e disponibile solo per x86_64):
    # https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz
    # Provata in alternativa la build statica di johnvansickle.com
    # (ldd: "not a dynamic executable", compatibile con qualunque distro/kernel Linux 3.2.0+) - SCARTATA: va in segfault
    # Verificato che la build BtbN qui sotto invece scarica e converte correttamente sia con
    # un url di test Apple sia con un vero stream m3u8 RAI. Se in futuro si
    # vuole ritentare la strada "piu' compatibile", testare SEMPRE con un
    # download reale (non solo -version/probe) prima di sostituire il binario
    FFMPEG_BIN_LINUX = 'ffmpeg_linux'

    # yt-dlp non e' piu' un binario scaricato per SO: e' un pacchetto Python
    # puro (wheel py3-none-any, uguale su Windows/macOS/Linux) installato da
    # YtDlpUpdater in ytDlpStorageDir()/<versione>/ e importato in-process
    # (vedi checkYtDlp/_importYtDlp) - niente piu' subprocess verso un
    # eseguibile esterno

    # Ritorna le impostazioni salvate dell'app (QSettings)
    @staticmethod
    def getSettings():
        return QSettings(MyText().orgName, MyText().appName)

    # Risolve il binario ffmpeg scaricato al primo avvio (vedi FfmpegInstaller/
    # ffmpegStorageDir), se presente - mai un binario imbarcato (rimosso da
    # binaries=[...] nei file .spec) ne' un'installazione di sistema.
    # Non deve mai sollevare: ffmpegStorageDir() puo' fallire (permessi, disco
    # pieno...) - i chiamanti (Pasty.initDependencies sul thread principale,
    # FfmpegInstaller.ensureInstalled in un thread separato) non se lo aspettano
    @classmethod
    def checkFFmpeg(cls):
        try:
            installed = os.path.join(cls.ffmpegStorageDir(), cls.ffmpegBinaryName())
            return installed if os.path.exists(installed) else None
        except Exception as err:
            Tools.consoleLogs("Impossibile risolvere ffmpegStorageDir: " + str(err))
            return None

    # Cartella scrivibile per-utente dove FfmpegInstaller installa ffmpeg
    # scaricato al primo avvio (mai la cartella di installazione, sola lettura)
    @staticmethod
    def ffmpegStorageDir():
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        path = os.path.join(base, 'ffmpeg')
        os.makedirs(path, exist_ok=True)
        return path

    # Controllo di cortesia usato da FfmpegInstaller/YtDlpUpdater prima di
    # scaricare (ffmpeg da solo, tra archivio e binario estratto, supera i
    # 200MB) - volutamente non generosissimo: deve solo evitare un download
    # su un disco palesemente troppo pieno, non bloccare un'installazione che
    # invece andrebbe a buon fine
    MIN_FREE_DISK_BYTES = 200 * 1024 * 1024

    # True se la cartella ha almeno MIN_FREE_DISK_BYTES liberi
    @staticmethod
    def hasEnoughDiskSpace(path):
        return shutil.disk_usage(path).free >= Tools.MIN_FREE_DISK_BYTES

    # Nome del file eseguibile ffmpeg corretto in base al sistema operativo
    @staticmethod
    def ffmpegBinaryName():
        os_name = Tools.getOs()
        if os_name == 'win':
            return Tools.FFMPEG_BIN_WIN
        elif os_name == 'mac':
            return Tools.FFMPEG_BIN_MAC
        return Tools.FFMPEG_BIN_LINUX

    # Converte una stringa di versione (es. "2026.07.04") in una tupla di interi
    # confrontabile, per capire quale tra due versioni e' la piu' recente
    @staticmethod
    def versionTuple(version):
        parts = []
        for chunk in str(version).split('.'):
            digits = re.match(r'\d+', chunk)
            parts.append(int(digits.group()) if digits else 0)
        return tuple(parts)

    # Cartella scrivibile per-utente dove vengono installate le versioni di
    # yt-dlp scaricate in autonomia (mai la cartella di installazione, sola lettura)
    @staticmethod
    def ytDlpStorageDir():
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        path = os.path.join(base, 'yt-dlp')
        os.makedirs(path, exist_ok=True)
        return path

    # tenuto vivo per tutta la sessione: se questo oggetto venisse
    # garbage-collected il lock si rilascerebbe subito
    _singleInstanceLock = None

    # Impedisce che un utente impaziente (es. doppio click ripetuto sull'exe
    # mentre le dipendenze si scaricano al primo avvio, specialmente lento su
    # Windows tra autoestrazione onefile e download di ffmpeg/yt-dlp) avvii
    # piu' istanze in parallelo
    @classmethod
    def acquireSingleInstanceLock(cls):
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        os.makedirs(base, exist_ok=True)
        lock = QLockFile(os.path.join(base, 'instance.lock'))
        if not lock.tryLock(100):
            return False
        cls._singleInstanceLock = lock
        return True

    # Marcatore che identifica una cartella <ytDlpStorageDir>/<versione> come
    # un'installazione completa (wheel estratto): il pacchetto yt_dlp vero e
    # proprio, con il suo __init__.py, non un'estrazione a meta'
    YTDLP_PACKAGE_MARKER = os.path.join('yt_dlp', '__init__.py')

    # Elenca le versioni di yt-dlp scaricate e installate per intero su disco,
    # ordinate dalla piu' vecchia alla piu' recente
    @classmethod
    def installedYtDlpVersions(cls):
        root = cls.ytDlpStorageDir()
        versions = []
        for name in os.listdir(root):
            if os.path.isfile(os.path.join(root, name, cls.YTDLP_PACKAGE_MARKER)):
                versions.append(name)
        return sorted(versions, key=cls.versionTuple)

    # Risolve la cartella-pacchetto di yt-dlp scaricata al primo avvio (vedi
    # YtDlpUpdater.ensureInstalled/ytDlpStorageDir), se presente - mai un
    # pacchetto imbarcato ne' un'installazione di sistema. E' una cartella da
    # aggiungere a sys.path prima di 'import yt_dlp' (vedi _importYtDlp), non
    # un binario da eseguire: yt-dlp gira in-process, sia nel processo
    # principale (probe/versione, vedi _importYtDlp) sia nel processo figlio
    # che scarica davvero (vedi _runYtDlpInProcess) - mai shellato come
    # eseguibile esterno.
    # Le versioni scaricate non vengono mai sovrascritte sul posto, quindi un
    # download gia' avviato continua a usare il path che aveva risolto
    # all'inizio; una versione piu' nuova scaricata in background mentre l'app
    # e' aperta viene vista solo dal prossimo riavvio (vedi _importYtDlp: una
    # volta importato, il modulo resta quello per tutta la sessione).
    # Non deve mai sollevare: ytDlpStorageDir() puo' fallire (permessi, disco
    # pieno...) - i chiamanti (Pasty.initDependencies sul thread principale,
    # YtDlpUpdater.ensureInstalled in un thread separato) non se lo aspettano
    @classmethod
    def checkYtDlp(cls):
        try:
            versions = cls.installedYtDlpVersions()
            if versions:
                return os.path.join(cls.ytDlpStorageDir(), versions[-1])
        except Exception as err:
            Tools.consoleLogs("Impossibile risolvere ytDlpStorageDir: " + str(err))
        return None

    # Modulo yt_dlp importato in-process nel processo principale (per il probe
    # di classificazione e il log versione, vedi isYtDlpDownloadable/
    # logYtDlpVersion) - mai per il download vero, che gira in un processo
    # figlio a parte (vedi _runYtDlpInProcess) cosi' da poter essere
    # interrotto in qualunque momento con un kill, come si faceva col
    # subprocess esterno di prima. Cache di processo: 'import' e' gia' cache-
    # ato da Python via sys.modules, questo evita solo di rifare
    # sys.path.insert ogni volta
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
            Tools.consoleLogs("Impossibile importare yt_dlp da %s: %s" % (packageDir, err))
            return None
        cls._registerEmbeddedQuickJsProvider(yt_dlp)
        cls._ytDlpModule = yt_dlp
        return yt_dlp

    # Ultima versione di yt-dlp contro cui si e' verificato per davvero (build
    # reale, download YouTube reale, zero runtime JS esterno sul sistema) che
    # _registerEmbeddedQuickJsProvider funzioni. E' solo un promemoria
    # automatico (vedi il confronto qui sotto), non un controllo bloccante:
    # yt-dlp si aggiorna da solo in background (vedi YtDlpUpdater) senza che
    # nessuno lo guardi, quindi non c'e' altro modo per accorgersi che una
    # versione futura ha ristrutturato le sue API interne (usate qui, vedi
    # sotto) se non a valle di un bug report - questo almeno lo mette nei log
    # dal primo avvio con la versione nuova, invece di scoprirlo mesi dopo.
    # Da aggiornare a mano dopo aver riverificato l'integrazione con una
    # nuova versione di yt-dlp
    QUICKJS_PROVIDER_VERIFIED_AGAINST = '2026.08.19'

    # Feature JS di cui lo script di risoluzione sfide di yt-dlp/yt_dlp_ejs si
    # e' verificato aver bisogno per davvero (vedi il commento esteso su
    # 'quickjs' vs 'quickjs-ng' piu' sotto: con il motore troppo vecchio
    # falliva silenziosamente proprio su queste). A differenza di
    # QUICKJS_PROVIDER_VERIFIED_AGAINST, che confronta solo un numero di
    # versione, questo e' un controllo diretto sulla capacita' reale del
    # motore bundlato - rileva un motore rimasto indietro anche se nessuno si
    # e' accorto di dover aggiornare il pin. Non e' un elenco completo di
    # tutto cio' che potrebbe mai servire, solo un campione di feature ES2022+
    # note per essere state richieste in passato: usato sia dal probe a
    # runtime (vedi _probeQuickJsFeatures, chiamato una volta per processo
    # dentro _registerEmbeddedQuickJsProvider) sia da un test vero e proprio
    # (tests/test_quickjs_provider.py) che fa fallire la suite - non solo un
    # log - se il motore bundlato smette di supportarle
    QUICKJS_REQUIRED_FEATURES = {
        'Array.prototype.at': '[1].at(-1) !== undefined',
        'Object.hasOwn': 'typeof Object.hasOwn === "function"',
        'Array.prototype.flat': 'typeof [].flat === "function"',
        'String.prototype.replaceAll': 'typeof "".replaceAll === "function"',
        'Object.fromEntries': 'typeof Object.fromEntries === "function"',
    }

    # Prova ognuna delle QUICKJS_REQUIRED_FEATURES sul motore quickjs-ng
    # effettivamente bundlato in questa build, senza toccare la rete ne'
    # risolvere nessuna sfida vera - deterministico e istantaneo (poche
    # eval() su espressioni minuscole). Ritorna la lista dei nomi mancanti
    # (vuota se tutto ok)
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

    # Chiamato una volta per processo dentro _registerEmbeddedQuickJsProvider,
    # subito dopo 'import quickjs': logga in modo esplicito (non un warning
    # generico, elenca esattamente cosa manca e cosa fare) se il motore
    # bundlato e' rimasto indietro, PRIMA che si manifesti come download
    # YouTube silenziosamente degradati (alcuni formati mancanti ma il
    # download riesce comunque, vedi runSingleUrl - non solleva nessun
    # errore visibile altrimenti). Non impedisce comunque la registrazione:
    # un motore parzialmente funzionante e' comunque meglio di nessun motore
    @classmethod
    def _warnIfQuickJsIsOutdated(cls, quickjsModule):
        missing = cls._missingQuickJsFeatures(quickjsModule)
        if missing:
            Tools.consoleLogs(
                "ATTENZIONE: il motore quickjs-ng bundlato in questa build non supporta: %s - "
                "i download YouTube potrebbero perdere qualita' o fallire senza errori evidenti. "
                "Aggiornare 'quickjs-ng' nei comandi pip install (.github/workflows/build-windows.yml, "
                "build-macos.yml, build-appimage.sh) e ricompilare l'app" % ", ".join(missing))

    # Una sola registrazione per processo: register_provider() di yt-dlp
    # solleva un errore su una chiave duplicata (vedi register_provider_generic
    # in yt_dlp/extractor/youtube/pot/_provider.py) - _importYtDlp gia' non
    # rientra qui una seconda volta da solo (vedi cache _ytDlpModule sopra),
    # ma _ytDlpDownloadWorker gira in un processo figlio nuovo ad ogni
    # download quindi non puo' condividere quella cache: questo flag e'
    # comunque per-processo (side reset automatico ad ogni processo figlio),
    # serve solo a rendere l'idempotenza esplicita invece di implicita
    _quickJsProviderRegistered = False

    # Registra un provider JS Challenge per yt-dlp basato sul pacchetto Python
    # 'quickjs-ng' (estensione C compilata, bundlata staticamente nell'app -
    # vedi i comandi pip install in .github/workflows/*.yml e build-appimage.sh;
    # PyInstaller.utils.hooks non serve perche' e' un import letterale in
    # questo file, non dinamico) - senza, YouTube richiederebbe un runtime JS
    # esterno (deno/node/bun/qjs) installato a parte sul sistema dell'utente,
    # che l'app non controlla e che la maggior parte degli utenti non ha (vedi
    # conversazione: verificato con debug reale di yt-dlp che senza nessun
    # runtime disponibile un download YouTube normale fallisce del tutto, non
    # solo con qualita' ridotta).
    #
    # Deve essere per forza 'quickjs-ng' (modulo importabile: 'quickjs',
    # stesso nome del vecchio pacchetto 'quickjs' - i due sono mutuamente
    # esclusivi, mai installarli entrambi): il pacchetto 'quickjs' (senza
    # -ng), piu' vecchio e fermo al 2023, imbarca una versione di QuickJS
    # troppo datata - verificato con un test reale (video YouTube corrente,
    # zero runtime JS sul sistema): con 'quickjs' lo script di risoluzione
    # vero di yt-dlp falliva con "TypeError: not a function" (mancano
    # Array.prototype.at/Object.hasOwn, ES2022), mentre con 'quickjs-ng' lo
    # stesso identico download riesce per intero. yt-dlp stesso lo conferma
    # nel proprio codice (_QJS_MIN_RECOMMENDED in
    # jsc/_builtin/quickjs.py: quickjs-ng >= 0.12.0, control esplicito che
    # 'quickjs-ng' 0.16.x supera).
    #
    # Nota per il packaging: 'quickjs-ng' non pubblica un wheel precompilato
    # per macOS x86_64 (solo arm64) - vedi il pip install "best effort" in
    # build-macos.yml. Su quella singola combinazione di build il provider
    # semplicemente non si registra (il try/except qui sotto lo rende
    # innocuo), l'app torna al comportamento pre-esistente per quella build
    # (nessun runtime JS -> alcuni download YouTube potrebbero fallire).
    #
    # L'intera classe del provider e' tenuta dentro questo metodo (non a
    # livello di modulo) apposta: l'unico punto che ne ha bisogno e' qui, e
    # cosi' un fallimento di import (yt-dlp che ha spostato/rinominato i suoi
    # moduli interni) resta contenuto in un solo try/except senza lasciare
    # classi a meta' definite in giro
    @classmethod
    def _registerEmbeddedQuickJsProvider(cls, ytdlp):
        if cls._quickJsProviderRegistered:
            return
        cls._quickJsProviderRegistered = True
        try:
            installedVersion = ytdlp.version.__version__
            # confronto per tupla, non per stringa: yt_dlp.version.__version__
            # e la versione riportata da PyPI possono differire nello zero-
            # padding (es. '2026.08.19' vs '2026.8.19') pur essendo la stessa
            # versione - versionTuple() e' la stessa normalizzazione gia'
            # usata altrove nel progetto per confrontare versioni yt-dlp
            if cls.versionTuple(installedVersion) != cls.versionTuple(cls.QUICKJS_PROVIDER_VERIFIED_AGAINST):
                Tools.consoleLogs(
                    "ATTENZIONE: yt-dlp %s e' diverso dall'ultima versione (%s) contro cui il "
                    "provider QuickJS embedded e' stato verificato per davvero - se i download "
                    "YouTube iniziano a fallire (nessun formato disponibile), verificare a mano "
                    "che Tools._registerEmbeddedQuickJsProvider sia ancora compatibile e "
                    "aggiornare QUICKJS_PROVIDER_VERIFIED_AGAINST" % (installedVersion, cls.QUICKJS_PROVIDER_VERIFIED_AGAINST))

            import quickjs
            cls._warnIfQuickJsIsOutdated(quickjs)
            # moduli interni di yt-dlp (nomi con underscore): non e' API
            # pubblica documentata/stabile come YoutubeDL(options), puo'
            # cambiare senza preavviso tra una versione e l'altra - da qui in
            # poi tutto resta dentro il try
            from yt_dlp.extractor.youtube.jsc._builtin.ejs import EJSBaseJCP
            from yt_dlp.extractor.youtube.jsc.provider import (
                JsChallengeProviderError, register_preference, register_provider,
            )

            # nome che finisce per 'JCP' obbligatorio: PROVIDER_KEY di
            # IEContentProvider lo deriva togliendo questo suffisso dal nome
            # della classe (vedi extractor/youtube/pot/_provider.py), e lo
            # pretende con un assert
            class PastyEmbeddedQuickJsJCP(EJSBaseJCP):
                JS_RUNTIME_NAME = 'pasty-embedded-quickjs'

                # a differenza della classe base (pensata per deno/node/bun/
                # qjs esterni, rilevati sul PATH), qui non c'e' nessun
                # eseguibile da rilevare: il motore e' gia' in memoria,
                # bundlato staticamente nell'app - quindi sempre disponibile
                def is_available(self, /):
                    return self._available

                # unico metodo che EJSBaseJCP chiede alle sottoclassi:
                # riceve lo script JS gia' completo come stringa, deve
                # ritornarne l'output testuale (quello che scriverebbe
                # console.log) - qui viene valutato in-process invece che
                # spedito a un processo esterno via stdin/stdout
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
            # priorita' alta (850 e' quella del provider ufficiale 'quickjs'
            # a binario esterno): preferito rispetto a un eventuale runtime
            # esterno comunque rilevato sul sistema dell'utente, visto che
            # non ha il costo di avviare un processo ad ogni sfida
            register_preference(PastyEmbeddedQuickJsJCP)(lambda provider, requests: 900)
            Tools.consoleLogs("Provider QuickJS embedded registrato per yt-dlp")
        except Exception as err:
            # non deve mai far fallire l'import di yt_dlp: senza questo
            # provider l'app torna semplicemente al comportamento precedente
            # (nessun runtime JS disponibile, alcuni download YouTube
            # potrebbero fallire), non deve andare in crash
            Tools.consoleLogs("Provider QuickJS embedded non registrato (yt-dlp potrebbe aver cambiato API interna): " + str(err))

    # Verifica che una cartella-pacchetto yt-dlp appena scaricata (vedi
    # YtDlpUpdater._downloadAndInstall) sia davvero importabile e funzionante,
    # in un processo a parte (vedi _ytDlpVerifyWorker) invece che con
    # _importYtDlp nel processo corrente - stesso principio del vecchio
    # _verifyRuns che lanciava il binario scaricato con --version prima di
    # fidarsene. Ritorna la versione riportata (stringa) se l'import riesce,
    # None altrimenti
    @staticmethod
    def verifyYtDlpImportable(packageDir, timeout=15):
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

    # --- yt_dlp_ejs: aggiornamento automatico dello script di risoluzione
    # sfide JS di YouTube (vedi _registerEmbeddedQuickJsProvider), stesso
    # principio di YtDlpUpdater ma senza mai bloccare l'avvio dell'app ne'
    # mostrare messaggi in UI: e' un miglioramento best-effort, non un
    # requisito - la versione bundlata staticamente nell'app (vedi
    # 'collect_data_files' in installer/*.spec) resta sempre un fallback
    # funzionante anche se questo controllo/download fallisce (rete assente,
    # PyPI irraggiungibile...). Stessa idea di YtDlpUpdater ma non ne
    # riusa il codice: e' molto piu' piccolo (niente binari per SO, niente
    # gate sulla UI) e non vale la complessita' di parametrizzare la classe
    # gia' testata invece di duplicare poche righe

    YTDLP_EJS_PACKAGE_MARKER = os.path.join('yt_dlp_ejs', '__init__.py')
    YTDLP_EJS_PYPI_URL = 'https://pypi.org/pypi/yt-dlp-ejs/json'
    YTDLP_EJS_KEEP_VERSIONS = 2

    # Cartella scrivibile per-utente dove vengono installate le versioni di
    # yt_dlp_ejs scaricate in autonomia (mai la cartella di installazione,
    # sola lettura)
    @staticmethod
    def ytDlpEjsStorageDir():
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        path = os.path.join(base, 'yt-dlp-ejs')
        os.makedirs(path, exist_ok=True)
        return path

    @classmethod
    def installedYtDlpEjsVersions(cls):
        root = cls.ytDlpEjsStorageDir()
        versions = []
        for name in os.listdir(root):
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

    # Da chiamare prima di 'import yt_dlp' (sia nel processo principale, vedi
    # _importYtDlp, sia nel processo figlio di download, vedi
    # _ytDlpDownloadWorker): se abbiamo scaricato una versione piu' recente
    # di yt_dlp_ejs rispetto a quella bundlata staticamente nell'app, la
    # mette in testa a sys.path cosi' yt-dlp la trova per prima quando importa
    # 'yt_dlp_ejs.yt.solver' al suo interno - verificato con un eseguibile
    # PyInstaller reale che un modulo su sys.path ha davvero la precedenza su
    # uno bundlato staticamente nello stesso frozen bundle, non il contrario
    @classmethod
    def _prepareYtDlpEjsPath(cls):
        ejsDir = cls.checkYtDlpEjs()
        if ejsDir and ejsDir not in sys.path:
            sys.path.insert(0, ejsDir)

    @staticmethod
    def verifyYtDlpEjsImportable(packageDir, timeout=15):
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

    # Punto di ingresso chiamato dallo stesso ciclo periodico di
    # YtDlpUpdater.checkAndUpdate (vedi main.py) - non ha un suo timer
    # separato. A differenza di YtDlpUpdater non emette nessun segnale Qt: un
    # fallimento qui (rete assente, PyPI giu'...) non deve mai impedire
    # all'app di funzionare, quindi resta silenzioso a parte i log
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

    # Stesso schema (scarica wheel, verifica checksum, estrae, verifica che
    # sia davvero importabile in un processo a parte, installa in modo
    # atomico, elimina le versioni vecchie) di
    # YtDlpUpdater._downloadAndInstall, vedi i commenti li' per il
    # ragionamento completo su ognuno di questi passi
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
            shutil.rmtree(partialDir, ignore_errors=True)  # vedi lo stesso comportamento di shutil.move su una directory in YtDlpUpdater._downloadAndInstall
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

    # Calcola lo sha256 di un file, per verificare l'integrita' di un download
    @staticmethod
    def sha256OfFile(path):
        digest = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                digest.update(chunk)
        return digest.hexdigest()

    # kwargs extra per nascondere la finestra console che Windows aprirebbe
    # altrimenti per ogni processo figlio (ffmpeg/yt-dlp), dato che l'app
    # stessa e' windowed (nessuna console propria) - CREATE_NO_WINDOW esiste
    # solo nel modulo subprocess su Windows, per questo il controllo di
    # piattaforma va fatto PRIMA di leggere l'attributo
    @staticmethod
    def _noConsoleWindowKwargs():
        if platform.system() == 'Windows':
            return {'creationflags': subprocess.CREATE_NO_WINDOW}
        return {}

    # args e' una lista di argomenti (mai una stringa shell): evita che un
    # url incollato dall'utente con caratteri speciali (", `, $(...), ;) possa
    # spezzare fuori dalle virgolette ed eseguire comandi di shell arbitrari.
    # timeout e isStoppedFn sono opzionali: se passati, un thread di controllo
    # termina l'intero albero di processi al primo che scatta, cosi' un host
    # lento/muto non puo' bloccare la coda dei download a tempo indeterminato
    # ne' restare sordo al pulsante Stop
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
                        Tools._terminateProcessTree(process.pid)
                        return
                    if timeout and (time.time() - startedAt) > timeout:
                        interruptedHolder['interrupted'] = True
                        Tools._terminateProcessTree(process.pid)
                        return
                    time.sleep(Tools.STOP_CHECK_INTERVAL_SECONDS)
            watcher = threading.Thread(target=watchForStopOrTimeout, daemon=True)
            watcher.start()
        stdout, _ = process.communicate()
        if watcher:
            watcher.join(timeout=1)
        # .interrupted: forzato a scadenza timeout o Stop utente - in quel caso
        # l'output parziale gia' scritto da ffmpeg prima di essere ucciso non va
        # interpretato come un esito valido (ne' successo ne' fallimento certo)
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

    # prefisso degli url speciali generati dal sito pasty.link stesso, per
    # segnalare esplicitamente all'app "questo va aperto con yt-dlp" senza
    # che l'app debba indovinarlo (vedi isPastylinkUrl/decodePastylinkUrl)
    PASTYLINK_URL_PREFIX = 'httpasty://'

    @classmethod
    def isPastylinkUrl(cls, url):
        # httpasty://BASE64{"v1" : {"ytdlp" : "https://www.youtube.com/watch?v=jNQXAC9IVRw", "referer" : "https://example.com/" }}
        return url.startswith(cls.PASTYLINK_URL_PREFIX)

    # marcatore che apre un manifest HLS testuale incollato per intero
    # (invece che come url): alcuni editor/browser anteppongono un BOM UTF-8
    # al testo copiato, va sempre tolto prima di controllare il prefisso
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
        path_desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        path_pasty = os.path.join(path_desktop, 'Pastylink')
        try:
            os.mkdir(path_pasty)
        except OSError as error:
            pass
        return path_pasty

    PROGRESS_THROTTLE_SECONDS = 0.5

    STOP_CHECK_INTERVAL_SECONDS = 0.3

    # un vero output audio/video con dati incapsulati non e' mai solo poche
    # centinaia di byte: sotto questa soglia e' quasi certamente un
    # container vuoto/troncato, indipendentemente da cosa dice stderr
    MIN_VALID_OUTPUT_SIZE_BYTES = 1024

    # quante volte ritentare un download yt-dlp fallito prima di arrendersi
    # (vedi downloadVideoByYtDlp): il 403 di YouTube su alcuni client di
    # fallback (es. android_vr, usato quando manca un runtime JS) e'
    # intermittente - verificato ripetendo a mano lo stesso identico comando
    # sullo stesso video: 1o tentativo bloccato, 2o e 3o riusciti subito dopo,
    # senza alcuna modifica nel frattempo - quindi un semplice retry e' piu'
    # efficace di qualunque cambio di formato/client
    YTDLP_MAX_ATTEMPTS = 3
    YTDLP_RETRY_DELAY_SECONDS = 2

    # Grace period concesso dopo il SIGTERM prima di passare al SIGKILL: un
    # processo bloccato in I/O (es. su una connessione di rete che non risponde
    # piu') puo' ignorare il SIGTERM, lasciando altrimenti process.wait() in
    # attesa indefinita dopo uno Stop utente o un timeout
    TERMINATE_GRACE_SECONDS = 3

    @staticmethod
    def _terminateProcessTree(pid):
        try:
            parent = psutil.Process(pid)
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
        """Avvia un processo e, se richiesto, un thread che lo termina (con
        tutto il suo albero di figli) appena isStoppedFn() diventa vero.
        Condiviso dal download ffmpeg e da quello yt-dlp, che hanno lo stesso
        bisogno di potersi fermare a comando invece di restare bloccati fino
        alla fine naturale del processo. 'command' e' sempre una lista di
        argomenti (mai una stringa shell), cosi' un url con caratteri speciali
        non puo' spezzare fuori dalle virgolette ed eseguire comandi arbitrari."""
        # stderr=STDOUT (non PIPE separata): se lette solo a fine processo,
        # tante righe su stderr (es. warning ripetuti di
        # ffmpeg su uno stream instabile/corrotto) possono riempire il buffer
        # del pipe del SO e bloccare il processo figlio in scrittura, che a
        # sua volta blocca per sempre il ciclo di lettura di stdout qui sotto
        # (deadlock classico dei subprocess con piu' pipe non drenate insieme)
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding='utf-8', errors='replace', bufsize=1, **Tools._noConsoleWindowKwargs())
        stoppedHolder = {'stopped': False}
        watcher = None
        if isStoppedFn:
            def watchForStop():
                while process.poll() is None:
                    if isStoppedFn():
                        stoppedHolder['stopped'] = True
                        Tools._terminateProcessTree(process.pid)
                        return
                    time.sleep(Tools.STOP_CHECK_INTERVAL_SECONDS)
            watcher = threading.Thread(target=watchForStop, daemon=True)
            watcher.start()
        return process, stoppedHolder, watcher

    @staticmethod
    def _runFFmpegWithProgress(command, saveAs, onProgress=None, isStoppedFn=None):
        """Runs ffmpeg (with -progress pipe:1) in a blocking loop, meant to be
        driven via loop.run_in_executor so the asyncio loop is never blocked.
        ffmpeg's own 'total_size=' field isn't reliable for -c copy (stream copy)
        operations, so each progress heartbeat from ffmpeg is used only as an
        event-driven trigger to re-check the real, current size of saveAs on disk
        - no more fixed-interval external polling. Stop is watched by a separate
        thread instead of only between stdout lines: if ffmpeg goes quiet (e.g.
        a stalled/buffering network stream), the read loop can block for a long
        time with no progress lines, and checking isStoppedFn only there would
        leave stop undetected and the process hanging. The watcher kills the
        whole process tree (ffmpeg can itself spawn children), which then
        unblocks the stdout read via EOF."""
        process, stoppedHolder, watcher = Tools._spawnWithStopWatcher(command, isStoppedFn)
        lastUpdate = 0
        # righe non di progresso: con stderr ora unita a stdout (vedi
        # _spawnWithStopWatcher) sono l'unico posto dove finiscono i
        # warning/errori veri di ffmpeg - servono a _ffmpegSucceeded e al
        # messaggio d'errore in caso di fallimento
        outputLines = []
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
        """yt-dlp riporta i byte scaricati via progress_hooks con 'status' in
        downloading/finished. Quando le tracce non sono gia' combinate, le
        scarica una per volta (prima il video, poi l'audio): i byte riportati
        sono sempre quelli della sola fase in corso, ripartono da zero al
        cambio fase. Il progresso ritornato e' quindi sempre "quanto gia'
        concluso nelle fasi precedenti" + "quanto scaricato in quella
        attuale" - a differenza del vecchio parsing testuale (dove bisognava
        dedurre il cambio fase da un numero che torna a scendere), qui lo
        stato 'finished' dice esplicitamente quando una fase e' conclusa, cosi'
        il totale va aggiornato subito invece di aspettare che la fase
        successiva inizi a riportare byte.
        phaseState: dict con chiave 'total', mutato in place (persiste tra le
        chiamate per lo stesso download). Ritorna il totale cumulativo da
        riportare a onProgress, o None se questo hook non e' rilevante."""
        downloadedBytes = downloadedBytes or 0
        if status == 'downloading':
            return phaseState['total'] + downloadedBytes
        if status == 'finished':
            phaseState['total'] += downloadedBytes
            return phaseState['total']
        return None

    @staticmethod
    def _ffmpegSucceeded(returncode, saveAs, stderr):
        """returncode == 0 is not enough: ffmpeg can exit cleanly after a demuxing
        error on a broken/stalled input, leaving an empty or truncated output
        file (e.g. 'Output file is empty, nothing was encoded' on stderr - un
        messaggio che ffmpeg non traduce mai, quindi indipendente dalla lingua
        del sistema, ma che potrebbe comunque cambiare tra una versione e
        l'altra di ffmpeg). Come rete di sicurezza aggiuntiva, indipendente
        dal testo di stderr, scartiamo anche un output cosi' piccolo da non
        poter essere un vero file audio/video con dati incapsulati."""
        if returncode != 0:
            return False
        if 'Output file is empty' in stderr:
            return False
        size = os.path.getsize(saveAs) if os.path.exists(saveAs) else 0
        return size > Tools.MIN_VALID_OUTPUT_SIZE_BYTES

    # regex sulle righe di stream stampate da 'ffmpeg -i' (non da ffprobe, che
    # qui non e' imbarcato): es. "Stream #0:6[0x6]: Video: h264 ..., 1920x1080 [..."
    _FFMPEG_STREAM_LINE_RE = re.compile(r'Stream #0:(\d+).*?:\s*(Video|Audio|Subtitle):.*')
    _FFMPEG_RESOLUTION_RE = re.compile(r'(\d{2,5})x(\d{2,5})')

    @staticmethod
    def _probeHlsStreams(ffmpeg, url, referer, isStoppedFn=None, timeout=15):
        """Ispeziona (senza scaricare video) gli stream che un manifest HLS
        espone: '-i' da solo apre il manifest e le sue sotto-playlist (testo,
        pochi KB) ma non scarica segmenti. Serve perche' appena si usa anche
        un solo altro -map esplicito, la selezione automatica di ffmpeg per
        gli stream non mappati si disattiva (verificato) - quindi per poter
        aggiungere i sottotitoli come traccia separata dobbiamo anche scegliere
        esplicitamente il video migliore, e l'ordine delle varianti in un
        master playlist non e' garantito dallo standard HLS (di solito e'
        crescente ma non c'e' alcun obbligo)."""
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
            # solo per i manifest m3u8: un master HLS puo' avere piu' varianti di
            # risoluzione e una traccia sottotitoli separata (EXT-X-MEDIA). Senza
            # scaricare nulla, controlliamo cosa offre per poter mappare il video
            # migliore + i sottotitoli come traccia soft (non "bruciata" nel video)
            # - non lo facciamo per gli altri url (mp4 diretti ecc) perche' quasi
            # mai hanno questa struttura e costerebbe solo tempo in piu' per niente
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
                        command += ['-c:s', 'mov_text']  # unico codec sottotitoli che il contenitore mp4 sa incapsulare
                else:
                    command += ['-c', 'copy']
            else:
                command += ['-c', 'copy']
            command += ['-bsf:a', 'aac_adtstoasc', saveAs]
            stopped, returncode, stderr = await loop.run_in_executor(None, Tools._runFFmpegWithProgress, command, saveAs, onProgress, isStoppedFn)
            # out
            if stopped:
                return [None, 'Stop forced by the user']
            if Tools._ffmpegSucceeded(returncode, saveAs, stderr):
                return [True, Tools.getSizeDynamic(saveAs)]
            # aac_adtstoasc serve solo per audio AAC in formato ADTS (tipico negli stream HLS): su un audio codificato diversamente (mp3, opus, vorbis...)
            # ffmpeg si rifiuta proprio di aprire il file di output. Ritentiamo senza, invece di far fallire l'intero download per un filtro inapplicabile
            if 'not supported by the bitstream filter' in stderr:
                retryCommand = list(command)
                if '-bsf:a' in retryCommand:
                    i = retryCommand.index('-bsf:a')
                    del retryCommand[i:i + 2]  # il flag e il suo valore, ovunque si trovino nel comando
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

    @staticmethod
    async def ConvertToMp3ByFFmpeg(ffmpeg, newMp3, oldVideo, onProgress=None, isStoppedFn=None):
        try:
            # conversion
            command = [ffmpeg, '-hide_banner', '-loglevel', 'warning', '-y', '-progress', 'pipe:1', '-i', oldVideo, newMp3]
            loop = asyncio.get_running_loop()
            stopped, returncode, stderr = await loop.run_in_executor(None, Tools._runFFmpegWithProgress, command, newMp3, onProgress, isStoppedFn)
            # out
            if stopped:
                return [None, 'Stop forced by the user']
            if Tools._ffmpegSucceeded(returncode, newMp3, stderr):
                return [True, Tools.getSizeDynamic(newMp3)]
            logging.error('FFmpeg error: ' + stderr)
            logging.error(command)
            return [False, stderr or 'FFmpeg produced no usable output']
        except Exception as err:
            logging.error(str(err))
            return [False, 'Conversion error #1']

    @classmethod
    async def downloadAsyncGeneric(cls, src_url, saveAs, parentApp = None, onProgress=None, chunk_size=65536):
        try:
            written = 0
            lastUpdate = 0
            async with aiohttp.ClientSession() as session:
                # niente 'br' (Brotli) in Accept-Encoding: e' opzionale in aiohttp,
                # non e' tra le dipendenze dichiarate dell'app, e se il pacchetto
                # brotli installato sul sistema ha una versione/API incompatibile
                # con quella attesa da aiohttp il download fallisce con un errore
                # criptico anche se il server e la pagina sono perfettamente validi
                async with session.get(src_url, headers={'Accept-Encoding': 'gzip, deflate'}) as resp:
                    resp.raise_for_status()  # es. 403/404: senza questo, la pagina d'errore verrebbe salvata e riportata come download riuscito
                    responseContentType = resp.headers.get('Content-Type', '')
                    if responseContentType.split(';')[0].strip().lower().startswith('text/html'):
                        # una pagina html non e' mai il contenuto che l'utente vuole scaricare qui
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
        try:
            with requests.get(url, stream=True, allow_redirects=True, timeout=timeout) as r:
                r.raise_for_status()
                # in caso di Content-Encoding: gzip
                # r.raw.decode_content = True  ---oppure---  r.raw.read = functools.partial(r.raw.read, decode_content=True)
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

    # Logga la versione di yt-dlp effettivamente in uso (importata in-process,
    # vedi _importYtDlp) - utile per verificare a runtime quale versione e'
    # stata risolta
    @classmethod
    def logYtDlpVersion(cls, packageDir):
        ytdlp = cls._importYtDlp(packageDir)
        version = ytdlp.version.__version__ if ytdlp else 'unknown'
        Tools.consoleLogs("Used: yt-dlp version " + version)

    # Probe leggero usato solo in fase di classificazione (PastedUrl._analyze), per
    # decidere se tentare yt-dlp su una pagina generica prima di arrendersi al
    # downloader generico. download=False non scarica ne' analizza i singoli
    # formati: si affida per intero all'extractor di yt-dlp, che sa gia' da
    # solo riconoscere/fondere anche tracce audio/video separate (a differenza
    # del vecchio approccio "estrai un url e scaricalo con ffmpeg", qui basta
    # sapere che yt-dlp trova qualcosa - sara' lui stesso a scaricarlo per intero).
    # Gira nel processo principale (in-process, non nel processo figlio usato
    # per il download vero): e' solo un probe di classificazione con un
    # timeout breve, non deve poter bloccare l'interfaccia a lungo, ma non
    # vale la pena del costo di avviare un intero processo figlio per questo
    @classmethod
    def isYtDlpDownloadable(cls, url, timeout=20):
        try:
            packageDir = cls.checkYtDlp()
            if not packageDir:
                return False
            ytdlp = cls._importYtDlp(packageDir)
            if not ytdlp:
                return False
            with ytdlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'noplaylist': True,
                                   'simulate': True, 'socket_timeout': timeout}) as ydl:
                info = ydl.extract_info(url, download=False)
            return info is not None
        except Exception as err:
            cls.consoleLogs("Error: yt-dlp simulate - " + str(err))
            return False

    # Grace period concesso al processo figlio yt-dlp dopo il terminate() prima
    # di passare al kill() - stesso principio di TERMINATE_GRACE_SECONDS per
    # ffmpeg, valore separato perche' un merge audio+video in corso (gestito da
    # yt-dlp stesso via ffmpeg) puo' impiegare un istante in piu' a chiudersi
    # in modo pulito
    YTDLP_TERMINATE_GRACE_SECONDS = 3

    # Esegue un download yt-dlp in un processo figlio separato (vedi
    # _ytDlpDownloadWorker), bloccante - va chiamato via loop.run_in_executor
    # cosi' l'event loop asyncio non resta bloccato. A differenza di ffmpeg
    # (ancora un eseguibile esterno via subprocess), yt-dlp e' importato come
    # libreria Python (vedi ytdlp_updater.py): un vero processo figlio, invece
    # di una chiamata diretta nel thread, resta comunque necessario per poter
    # interrompere lo Stop in qualunque momento con un kill del processo -
    # cosa che una libreria importata in-process non permetterebbe (l'unico
    # aggancio che yt-dlp offre per interrompersi da solo, sollevare
    # DownloadCancelled dentro un progress_hook, scatta solo nei punti in cui
    # yt-dlp stesso richiama l'hook, non se resta bloccato prima, es. durante
    # l'estrazione delle info)
    @staticmethod
    def _runYtDlpInProcess(packageDir, ffmpegPath, url, saveAs, referer, onProgress=None, isStoppedFn=None):
        ctx = multiprocessing.get_context('spawn')
        resultQueue = ctx.Queue()
        # risolto qui (processo padre, QStandardPaths gia' funzionante) e
        # passato come argomento: vedi il commento in _ytDlpDownloadWorker sul
        # perche' non puo' risolverselo da solo
        ejsDir = Tools.checkYtDlpEjs()
        process = ctx.Process(target=_ytDlpDownloadWorker,
                               args=(packageDir, ffmpegPath, url, saveAs, referer, ejsDir, resultQueue),
                               daemon=True)
        process.start()
        lastUpdate = 0
        stopped, success, errorDetail = False, False, ''
        while True:
            if isStoppedFn and isStoppedFn():
                stopped = True
                break
            try:
                kind, *payload = resultQueue.get(timeout=Tools.STOP_CHECK_INTERVAL_SECONDS)
            except queue.Empty:
                if not process.is_alive():
                    break  # il figlio e' morto senza mandare 'done' (es. crash python non catturato)
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
            process.join(timeout=1)  # 'done' gia' ricevuto: il figlio sta solo finendo di uscire da solo
        if process.is_alive():
            # non dovrebbe succedere (interprete gia' a fine lavoro, o appena
            # terminato) ma non deve restare un processo orfano appeso
            process.kill()
            process.join(timeout=1)
        resultQueue.close()
        return stopped, success, errorDetail

    # Scarica (ed eventualmente fonde video+audio) direttamente con yt-dlp,
    # invece di estrarre un url e passarlo a ffmpeg come faceva la versione
    # precedente: yt-dlp e' lo strumento pensato apposta per questo, sa gia'
    # scegliere e fondere le tracce giuste (risolve anche il caso di pagine
    # con audio e video su url HLS separati, dove un singolo url passato a
    # ffmpeg produrrebbe un video muto), e non rischia di scaricare un url
    # temporaneo/firmato gia' scaduto nel frattempo
    @classmethod
    async def downloadVideoByYtDlp(cls, packageDir, ffmpegPath, url, saveAs, onProgress=None, isStoppedFn=None, referer=None):
        try:
            cls.logYtDlpVersion(packageDir)
            loop = asyncio.get_running_loop()
            errorDetail = ''
            for attempt in range(cls.YTDLP_MAX_ATTEMPTS):
                stopped, success, errorDetail = await loop.run_in_executor(
                    None, Tools._runYtDlpInProcess, packageDir, ffmpegPath, url, saveAs, referer, onProgress, isStoppedFn)
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

    # calculate file size in KB, MB, GB
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

    # frm ciao.mondo
    # to  ciao.mondo_(12-34-56)
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

    @staticmethod
    def writeThisInFile(content, pathfile):
        try:
            f = open(pathfile, "w")
            f.write(content)
            f.close()
            return True
        except Exception:
            return False

    # Specifica se il programma è avviato
    # a runtime da exe oppure da source durante lo sviluppo
    @staticmethod
    def runType():
        if Constants.IS_ANDROID:
            return 'EXE'
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return 'EXE'
        else:
            return 'DEV'

    @classmethod
    def isDevMode(cls):
        return cls.runType() == 'DEV'

    # https://cuteprogramming.wordpress.com/2021/10/18/packaging-pyqt5-app-with-pyinstaller-on-windows/
    # relative_path e' sempre il nome di un binario dentro bin/ (ffmpeg/yt-dlp imbarcati)
    # non piu usato, prima per recuperare i binari di ffmpeg e ytdlp
    @staticmethod
    def resourcePath(relative_path):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, 'bin', relative_path)

    # Under construction
    # @todo
    @classmethod
    def showFileInNautilus(cls, path):
        if cls.getOs() == 'win':
            subprocess.Popen(r'explorer /select,"%s"' % path)
            subprocess.Popen(r'explorer /open,"%s"' % path)
        else:
            # ???
            pass

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

    # Controllo di connessione vero e veloce: un tentativo di connessione TCP verso
    # un DNS pubblico noto (Google, 8.8.8.8:53), non un server nostro o di terzi -
    # cosi' il risultato dice solo "c'e' rete o no", senza dipendere dalla
    # disponibilita' di un servizio HTTP specifico
    @staticmethod
    def hasInternetConnection(timeout=3):
        try:
            with socket.create_connection(("8.8.8.8", 53), timeout=timeout):
                return True
        except OSError:
            return False

    @classmethod
    def sendRequestGet(cls, url, timeout = 10):
        try:
            cls.consoleLogs("Sent 'get' request to " + url)
            req = requests.get(url, timeout = timeout)
            return req
        except Exception as err:
            cls.consoleLogs("Not sent 'get' request to " + url + "because of: " + str(err))
            return None

    @classmethod
    def sendRequestPost(cls, url, params = None, timeout = 3):
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
