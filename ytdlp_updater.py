#!/usr/bin/python

import os, shutil, tempfile, zipfile
from PySide6.QtCore import QObject, Signal
from libs import Tools
from testi import MyText


class YtDlpUpdater(QObject):
    """Keeps the app's own yt-dlp installation current in the background, e la
    scarica da zero al primo avvio se manca del tutto (vedi ensureInstalled).

    yt-dlp non e' piu' un binario per SO scaricato da una release GitHub e
    shellato via subprocess: e' un pacchetto Python puro (wheel py3-none-any,
    identico su Windows/macOS/Linux) pubblicato su PyPI, scaricato e installato
    qui in ytDlpStorageDir()/<versione>/ ed eseguito in-process (vedi
    Tools.checkYtDlp/_importYtDlp/downloadVideoByYtDlp). PyPI pubblica gia' lo
    sha256 di ogni file direttamente nella sua API JSON (chiave 'digests'),
    quindi qui non serve piu' un file di checksum separato da scaricare e
    parsare a parte (era il caso di SHA2-256SUMS per le release GitHub).

    Punto importante che cambia rispetto a prima: un binario scaricato veniva
    "raccolto" al prossimo download (ogni download era un subprocess nuovo,
    che carica qualunque binario si trovi in quel momento su disco). Un
    pacchetto Python importato invece resta in sys.modules per tutta la durata
    del processo (vedi Tools._importYtDlp) - quindi un aggiornamento scaricato
    qui in background, mentre l'app e' gia' aperta, viene davvero usato solo
    dal prossimo riavvio dell'app, non dal prossimo download di questa stessa
    sessione. E' una scelta deliberata (niente reimport a caldo, rischioso con
    lo stato interno di migliaia di moduli extractor), non un bug: il
    download vero e proprio gira comunque in un processo figlio a parte (vedi
    Tools._runYtDlpInProcess), che pero' importa yt_dlp da zero ogni volta -
    quindi in realta' un download avviato *dopo* che l'installazione e' stata
    sostituita su disco vede gia' la versione nuova, anche senza riavviare
    l'app; solo il probe di classificazione e il log versione nel processo
    principale (isYtDlpDownloadable/logYtDlpVersion) restano fissati alla
    versione importata la prima volta, fino al riavvio.

    Una versione piu' nuova viene scaricata in una nuova cartella versionata
    sotto Tools.ytDlpStorageDir() - non sovrascrive mai l'installazione
    attualmente in uso, quindi un download gia' avviato contro una versione
    piu' vecchia continua a usare la cartella che aveva risolto. Runs in a
    plain background thread (see main.py:checkYtDlpUpdate/installDependencies),
    so statusMessage/statusMessageNow/ready sono l'unica cosa che raggiunge il
    thread grafico.
    """

    statusMessage = Signal(str, int)
    # messaggio "conclusivo" (es. "aggiornato"): a differenza di statusMessage
    # non aspetta il proprio turno in coda, sostituisce subito il messaggio
    # persistente "in corso" appena mostrato (vedi StatusQueue.showNow - con
    # clear()+statusMessage normale rischierebbe di accodarsi dietro un
    # evento nel frattempo promosso dal clear(), non venendo mostrato subito)
    statusMessageNow = Signal(str, int)
    # emesso solo da ensureInstalled() (mai da checkAndUpdate/_doCheck, che
    # resta un aggiornamento opzionale in background): dice se al primo
    # avvio, quando yt-dlp mancava del tutto, l'installazione e' riuscita -
    # vedi Pasty.initDependencies/onYtDlpReady, che blocca la UI nel frattempo
    ready = Signal(bool)

    CHECK_INTERVAL_HOURS = 6
    KEEP_VERSIONS = 2

    PYPI_URL = 'https://pypi.org/pypi/yt-dlp/json'

    _checking = False

    # Punto di ingresso chiamato da main.py (all'avvio e periodicamente): evita
    # controlli sovrapposti se uno e' gia' in corso, poi esegue il controllo vero e proprio
    def checkAndUpdate(self):
        if self._checking:
            return
        self._checking = True
        try:
            self._doCheck()
            # stesso ciclo periodico, nessun timer separato: aggiorna anche lo
            # script yt_dlp_ejs (vedi Tools.checkAndUpdateYtDlpEjs in libs.py)
            # usato dal provider QuickJS embedded - a differenza di yt-dlp
            # stesso, un fallimento qui non emette nessun segnale (non blocca
            # mai l'app, resta solo nei log)
            Tools.checkAndUpdateYtDlpEjs()
        finally:
            self._checking = False

    # Interroga PyPI per l'ultima versione pubblicata, confronta con quella
    # attualmente installata e, se ce n'e' una piu' nuova, scarica e installa
    # il wheel (uguale per ogni SO: e' pura Python)
    def _doCheck(self):
        try:
            remoteVersion, wheel = self._fetchLatestRelease()
            if not remoteVersion or not wheel:
                return
            # installedYtDlpVersions() puo' sollevare (permessi, disco pieno
            # sulla cartella AppData): va dentro questo stesso try, non lasciata
            # tra i due blocchi, altrimenti un'eccezione qui ucciderebbe il
            # thread di questo controllo con un traceback grezzo invece di
            # essere loggata come ovunque altrove (si autoripara comunque al
            # giro successivo, 6 ore dopo, ma nel frattempo silenziosamente)
            currentVersions = Tools.installedYtDlpVersions()
            currentVersion = currentVersions[-1] if currentVersions else None
            if currentVersion and Tools.versionTuple(remoteVersion) <= Tools.versionTuple(currentVersion):
                return
        except Exception as err:
            Tools.consoleLogs("yt-dlp update check failed: " + str(err))
            return
        Tools.consoleLogs("yt-dlp update found: " + remoteVersion)
        self.statusMessage.emit(MyText().ytDlpUpdating, 0)
        try:
            self._downloadAndInstall(remoteVersion, wheel['url'], (wheel.get('digests') or {}).get('sha256'))
            self.statusMessageNow.emit(MyText().ytDlpUpdateDone, 5)
        except Exception as err:
            Tools.consoleLogs("yt-dlp update failed: " + str(err))

    # Punto di ingresso per il primo avvio (vedi Pasty.onFfmpegReady, che lo
    # avvia in cascata subito dopo l'installazione di ffmpeg): se yt-dlp non
    # e' gia' installato (Tools.checkYtDlp() vuoto), scarica l'ultima versione
    # disponibile - a differenza di _doCheck() non confronta con nessuna
    # versione attualmente installata (non ce n'e' nessuna), scarica sempre
    # l'ultima. Va chiamato in un thread separato: fa richieste di rete e puo'
    # metterci diversi secondi.
    # Tutto il corpo e' dentro il try/except (anche il controllo iniziale, non
    # solo il download): questo metodo gira in un threading.Thread grezzo, e
    # un'eccezione non gestita qui lo farebbe morire in silenzio senza mai
    # emettere ready, lasciando l'interfaccia bloccata per sempre (stesso
    # principio di FfmpegInstaller.ensureInstalled)
    def ensureInstalled(self):
        try:
            if Tools.checkYtDlp():
                self._pruneOldVersions()  # ripulisce anche qui, non solo dopo un download: vedi _pruneOldVersions
                self.ready.emit(True)
                return
            Tools.consoleLogs("yt-dlp non presente, scaricamento in corso...")
            self.statusMessage.emit(MyText().ytDlpUpdating, 0)
            remoteVersion, wheel = self._fetchLatestRelease()
            if not remoteVersion or not wheel:
                raise ValueError('No yt-dlp wheel found on PyPI')
            self._downloadAndInstall(remoteVersion, wheel['url'], (wheel.get('digests') or {}).get('sha256'))
            Tools.consoleLogs("yt-dlp installato correttamente")
            self.ready.emit(True)
        except Exception as err:
            Tools.consoleLogs("Installazione yt-dlp fallita: " + str(err))
            self.ready.emit(False)

    # Interroga PyPI per l'ultima versione pubblicata e ritorna
    # (remoteVersion, wheel), dove wheel e' la entry di 'urls' per il file
    # .whl "py3-none-any" (uguale per ogni SO - yt-dlp e' pura Python), o None
    # se questa release non ne pubblica uno. Condiviso da _doCheck()
    # (aggiornamento periodico) ed ensureInstalled() (primo avvio)
    def _fetchLatestRelease(self):
        release = Tools.readFileJson(self.PYPI_URL, timeout=10)
        info = (release.get('info') or {}) if isinstance(release, dict) else {}
        remoteVersion = info.get('version')
        urls = (release.get('urls') or []) if isinstance(release, dict) else []
        wheel = next((u for u in urls if u.get('packagetype') == 'bdist_wheel'
                      and str(u.get('filename', '')).endswith('-py3-none-any.whl')), None)
        return remoteVersion, wheel

    # Scarica il wheel in una cartella temporanea, verifica checksum e che sia
    # davvero importabile, e solo a quel punto lo installa in modo atomico
    # nella cartella versionata finale (mai sovrascrivendo l'installazione
    # eventualmente in uso), poi elimina le versioni vecchie.
    # La cartella finale e' Tools.ytDlpStorageDir()/<version>/, cioe' una
    # sottocartella "yt-dlp" dentro la cartella dati scrivibile dell'utente
    # (QStandardPaths.AppDataLocation), ad es.
    # ~/.local/share/Pastylink/yt-dlp/2026.08.19/yt_dlp/... su Linux,
    # ~/Library/Application Support/Pastylink/yt-dlp/2026.08.19/yt_dlp/... su
    # Mac, %APPDATA%/Pastylink/yt-dlp/2026.08.19/yt_dlp/... su Windows - mai la
    # cartella di installazione dell'app, che potrebbe essere di sola lettura
    def _downloadAndInstall(self, version, wheelUrl, sha256Expected):
        if not Tools.hasEnoughDiskSpace(Tools.ytDlpStorageDir()):
            raise IOError('Not enough disk space to install yt-dlp')
        destDir = os.path.join(Tools.ytDlpStorageDir(), version)
        with tempfile.TemporaryDirectory() as tmp:
            wheelPath = os.path.join(tmp, 'yt_dlp.whl')
            # timeout esplicito (connessione, tra un chunk e il successivo):
            # senza, un server che accetta la connessione e poi non risponde
            # piu' bloccherebbe questo thread per sempre - e per
            # ensureInstalled() (chiamato al primo avvio se yt-dlp manca del
            # tutto) terrebbe l'intera interfaccia bloccata a tempo
            # indeterminato. Il read-timeout si applica tra un chunk e il
            # successivo, non alla durata totale: un download lento ma che
            # progredisce non viene interrotto
            ok, msg = Tools.downloadNotAsyncGeneric(wheelUrl, wheelPath, timeout=(10, 30))
            if not ok:
                raise IOError('Download failed: ' + str(msg))
            if sha256Expected:
                if Tools.sha256OfFile(wheelPath).lower() != str(sha256Expected).lower():
                    raise ValueError('Checksum mismatch for yt-dlp %s, discarding' % version)
            else:
                # capita se la risposta JSON di PyPI per questo file non
                # include affatto 'digests.sha256' - raro ma non impossibile,
                # e non e' un motivo per bloccare l'installazione (resta
                # comunque protetta dalla verifica funzionale sotto,
                # verifyYtDlpImportable): va pero' loggato, non saltato in
                # silenzio, perche' e' l'unico controllo di integrita' del
                # download che stiamo perdendo in quel caso
                Tools.consoleLogs("yt-dlp %s: nessun sha256 pubblicato da PyPI per questo file, controllo integrita' saltato" % version)
            # un wheel e' solo uno zip: nessun passo di build, e' gia' pura
            # Python (py3-none-any) - basta estrarlo cosi' com'e'
            extractDir = os.path.join(tmp, 'extracted')
            with zipfile.ZipFile(wheelPath) as z:
                z.extractall(extractDir)
            if not os.path.isfile(os.path.join(extractDir, Tools.YTDLP_PACKAGE_MARKER)):
                raise ValueError('yt_dlp package not found inside the downloaded wheel')
            # verifica funzionale (in un processo a parte, vedi
            # Tools.verifyYtDlpImportable) prima di fidarsene, stesso principio
            # di quando si lanciava il binario scaricato con --version
            if not Tools.verifyYtDlpImportable(extractDir):
                raise RuntimeError('Downloaded yt-dlp %s failed to import, discarded' % version)
            # only move a verified-working install into the real storage dir,
            # and only ever expose it under its final name via an atomic
            # rename - so a crash/kill anywhere above never leaves a broken
            # or partial folder where installedYtDlpVersions() would find it
            os.makedirs(Tools.ytDlpStorageDir(), exist_ok=True)
            partialDir = destDir + '.part'
            # a differenza di un file singolo (shutil.move sovrascrive un file
            # di destinazione gia' esistente), su una directory shutil.move la
            # annida dentro invece di sostituirla se la destinazione esiste
            # gia' - un .part residuo di un tentativo precedente interrotto
            # per questa stessa versione andrebbe altrimenti a finire come
            # partialDir/extracted/yt_dlp/... invece che partialDir/yt_dlp/...,
            # facendo sparire silenziosamente il marker che
            # installedYtDlpVersions() si aspetta di trovare
            shutil.rmtree(partialDir, ignore_errors=True)
            shutil.move(extractDir, partialDir)
            os.replace(partialDir, destDir)
        self._pruneOldVersions()

    # Elimina tutto cio' che non serve piu' in ytDlpStorageDir(): le versioni
    # valide oltre le ultime KEEP_VERSIONS, ma anche qualunque cosa non sia
    # affatto un'installazione valida riconosciuta da installedYtDlpVersions()
    # - una cartella '<versione>.part' rimasta da un'installazione interrotta,
    # o (caso reale dopo l'aggiornamento di questa app: yt-dlp era prima un
    # binario per SO, es. 'yt-dlp_linux', scaricato da una release GitHub,
    # vedi il vecchio schema in git history) una cartella-versione nel vecchio
    # formato binario, che il nuovo installedYtDlpVersions() non riconosce piu'
    # (cerca yt_dlp/__init__.py, non un eseguibile) e quindi non userebbe mai -
    # invece di lasciarla in giro per sempre a occupare spazio, va ripulita
    # con lo stesso giro di pulizia.
    # E' sicuro farlo anche se in quel momento c'e' un download in corso in un
    # processo figlio (vedi Tools._runYtDlpInProcess): KEEP_VERSIONS=2 fa si'
    # che la versione appena sostituita (quella che un batch avviato un
    # attimo prima dell'aggiornamento potrebbe aver risolto) non venga mai
    # cancellata subito, ma solo al giro di pulizia successivo - servirebbero
    # due aggiornamenti veri consecutivi (quindi molte ore) prima che una
    # versione ancora in uso venga toccata.
    # Come ulteriore rete di sicurezza: su Windows, se la cartella fosse
    # comunque bloccata (in uso da un processo), shutil.rmtree solleva
    # OSError, che viene catturato qui sotto e si riprova al controllo
    # successivo; su Linux/Mac cancellare i file di un processo in esecuzione
    # e' comunque innocuo di per se' (il kernel mantiene l'inode finche' il
    # processo lo tiene aperto, anche dopo la cancellazione della voce su disco)
    # Tutto il corpo e' dentro un try/except generico (non solo la rimozione
    # delle singole cartelle, gia' coperta sotto): entrambi i chiamanti
    # (_downloadAndInstall, dopo un'installazione gia' riuscita, ed
    # ensureInstalled, quando yt-dlp era gia' installato) non hanno un
    # try/except proprio attorno a questa chiamata, quindi un problema qui
    # (es. Tools.installedYtDlpVersions()/os.listdir(root) che sollevano per
    # permessi o disco) si propagherebbe fino al loro try/except esterno - in
    # ensureInstalled() questo significherebbe ready.emit(False), che chiude
    # l'intera app (vedi Pasty.onYtDlpReady) per un problema di sola pulizia,
    # non di installazione ne' funzionamento
    @classmethod
    def _pruneOldVersions(cls):
        try:
            root = Tools.ytDlpStorageDir()
            keep = set(Tools.installedYtDlpVersions()[-cls.KEEP_VERSIONS:])
            for name in os.listdir(root):
                if name in keep:
                    continue
                try:
                    shutil.rmtree(os.path.join(root, name))
                except OSError as err:
                    Tools.consoleLogs("Could not prune old yt-dlp %s yet: %s" % (name, err))
        except Exception as err:
            Tools.consoleLogs("yt-dlp: pulizia versioni vecchie fallita (non bloccante): " + str(err))
