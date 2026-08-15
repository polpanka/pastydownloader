#!/usr/bin/python

import os, sys, socket, subprocess, platform, unicodedata, re, shlex, json, requests, asyncio, aiofiles, aiohttp, base64, tempfile, hashlib, time, threading, psutil, shutil
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QFile, QTextStream, QIODevice, QSettings, QStandardPaths
from PySide6.QtGui import QClipboard
from testi import MyText
from constants import Constants

import hashlib
import logging

# Configurazione base del logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('urllib3').setLevel(logging.WARNING)

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

    # Windows:
    # https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe
    YTDLP_BIN_WIN = 'yt-dlp.exe'

    # macOS:
    # https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos
    YTDLP_BIN_MAC = 'yt-dlp_macos'

    # Linux:
    # https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux
    YTDLP_BIN_LINUX = 'yt-dlp_linux'

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

    # Nome del file eseguibile yt-dlp corretto in base al sistema operativo
    @staticmethod
    def ytDlpBinaryName():
        os_name = Tools.getOs()
        if os_name == 'win':
            return Tools.YTDLP_BIN_WIN
        elif os_name == 'mac':
            return Tools.YTDLP_BIN_MAC
        return Tools.YTDLP_BIN_LINUX

    # Cartella scrivibile per-utente dove vengono installate le versioni di
    # yt-dlp scaricate in autonomia (mai la cartella di installazione, sola lettura)
    @staticmethod
    def ytDlpStorageDir():
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        path = os.path.join(base, 'yt-dlp')
        os.makedirs(path, exist_ok=True)
        return path

    # Elenca le versioni di yt-dlp scaricate e con un binario utilizzabile su disco,
    # ordinate dalla piu' vecchia alla piu' recente
    @classmethod
    def installedYtDlpVersions(cls):
        root = cls.ytDlpStorageDir()
        binName = cls.ytDlpBinaryName()
        versions = []
        for name in os.listdir(root):
            binPath = os.path.join(root, name, binName)
            if os.path.isfile(binPath):
                versions.append(name)
        return sorted(versions, key=cls.versionTuple)

    # Risolve il binario yt-dlp scaricato al primo avvio (vedi YtDlpUpdater.
    # ensureInstalled/ytDlpStorageDir), se presente - mai un binario imbarcato
    # (rimosso da binaries=[...] nei file .spec) ne' un'installazione di sistema.
    # Le versioni scaricate non vengono mai sovrascritte sul posto, quindi un
    # download gia' avviato continua a usare il path che aveva risolto all'inizio.
    # Non deve mai sollevare: ytDlpStorageDir() puo' fallire (permessi, disco
    # pieno...) - i chiamanti (Pasty.initDependencies sul thread principale,
    # YtDlpUpdater.ensureInstalled in un thread separato) non se lo aspettano
    @classmethod
    def checkYtDlp(cls):
        try:
            versions = cls.installedYtDlpVersions()
            if versions:
                return os.path.join(cls.ytDlpStorageDir(), versions[-1], cls.ytDlpBinaryName())
        except Exception as err:
            Tools.consoleLogs("Impossibile risolvere ytDlpStorageDir: " + str(err))
        return None

    # Calcola lo sha256 di un file, per verificare l'integrita' di un download
    @staticmethod
    def sha256OfFile(path):
        digest = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                digest.update(chunk)
        return digest.hexdigest()

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
                                    encoding='utf-8', errors='replace')
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
        # httpasty://BASE64{"v1" : {"ytdlp" : "https://www.youtube.com/watch?v=jNQXAC9IVRw" }}
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
    def decodePastylinkUrl(cls, url):
        """Decodifica un url 'httpasty://<base64 di un json>' generato dal
        sito pasty.link con base64_encode() di PHP (base64 standard, mai
        url-safe). Il json decodificato deve avere la forma
        {"v1": {"ytdlp": "<url da aprire con yt-dlp>"}}. Tollerante sul
        padding mancante (comune quando il base64 finisce dentro un url).
        Ritorna None se il formato non e' valido o manca la chiave 'ytdlp'."""
        payload = url[len(cls.PASTYLINK_URL_PREFIX):]
        padded = payload + '=' * (-len(payload) % 4)
        try:
            data = json.loads(base64.b64decode(padded))
            return (data.get('v1') or {}).get('ytdlp') or None
        except Exception:
            return None

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

    @staticmethod
    def _terminateProcessTree(pid):
        try:
            parent = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return
        for child in parent.children(recursive=True):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        try:
            parent.terminate()
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
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    encoding='utf-8', errors='replace', bufsize=1)
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
        for line in process.stdout:
            line = line.strip()
            if onProgress and line in ('progress=continue', 'progress=end'):
                now = time.time()
                if now - lastUpdate >= Tools.PROGRESS_THROTTLE_SECONDS:
                    lastUpdate = now
                    size = Tools.getSizeInByte(saveAs)
                    if size:
                        onProgress(size)
        process.stdout.close()
        process.wait()
        if watcher:
            watcher.join(timeout=1)
        stderr = process.stderr.read()
        process.stderr.close()
        return stoppedHolder['stopped'], process.returncode, stderr

    # prefisso usato per riconoscere le righe di progresso generate apposta da
    # yt-dlp (vedi downloadVideoByYtDlp): evita di dover fare parsing fragile
    # sulla riga [download] formattata per l'uomo, che yt-dlp puo' cambiare
    # in qualunque momento tra una versione e l'altra
    YTDLP_PROGRESS_PREFIX = 'PASTY_PROGRESS '

    @staticmethod
    def _runYtDlpWithProgress(command, onProgress=None, isStoppedFn=None):
        """Come _runFFmpegWithProgress, ma per yt-dlp: qui il progresso arriva
        gia' come numero di byte scaricati (via --progress-template), senza
        bisogno di ricontrollare la dimensione del file su disco - utile
        perche' durante il download di tracce separate (video+audio, fuse da
        yt-dlp stesso alla fine) il file di destinazione finale non esiste
        ancora con le dimensioni giuste.
        Quando le tracce sono separate, yt-dlp le scarica una per volta (prima
        il video, poi l'audio): i byte riportati sono sempre quelli della sola
        fase in corso e ripartono da zero al cambio fase. Il progresso mostrato
        e' quindi sempre "quanto gia' concluso in totale" + "quanto scaricato
        nella fase attuale": il totale gia' concluso parte da zero e cresce di
        una fase alla volta, ogni volta che ne notiamo la fine - l'unico modo
        per accorgersene e' che il numero riportato torni a scendere, cosa che
        succede solo quando inizia la fase successiva."""
        process, stoppedHolder, watcher = Tools._spawnWithStopWatcher(command, isStoppedFn)
        lastUpdate = 0
        totalFromFinishedPhases = 0
        bytesSoFarInCurrentPhase = 0
        for line in process.stdout:
            line = line.strip()
            if onProgress and line.startswith(Tools.YTDLP_PROGRESS_PREFIX):
                try:
                    reportedBytes = int(line[len(Tools.YTDLP_PROGRESS_PREFIX):])
                except ValueError:
                    continue
                if reportedBytes < bytesSoFarInCurrentPhase:
                    # il numero e' sceso: la fase precedente e' finita, il suo ultimo valore va sommato al totale prima di ripartire
                    totalFromFinishedPhases += bytesSoFarInCurrentPhase
                bytesSoFarInCurrentPhase = reportedBytes
                now = time.time()
                if now - lastUpdate >= Tools.PROGRESS_THROTTLE_SECONDS:
                    lastUpdate = now
                    onProgress(totalFromFinishedPhases + bytesSoFarInCurrentPhase)
        process.stdout.close()
        process.wait()
        if watcher:
            watcher.join(timeout=1)
        stderr = process.stderr.read()
        process.stderr.close()
        return stoppedHolder['stopped'], process.returncode, stderr

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

    # Logga la versione del binario yt-dlp effettivamente in uso, interrogandolo
    # con --version - utile per verificare a runtime quale yt-dlp e' stato
    # risolto (imbarcato vs scaricato in autonomia da YtDlpUpdater)
    @staticmethod
    def logYtDlpVersion(ytdlp):
        try:
            result = subprocess.run([ytdlp, '--version'], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, timeout=10, encoding='utf-8', errors='replace')
            version = result.stdout.strip() if result.returncode == 0 else 'unknown'
        except Exception:
            version = 'unknown'
        Tools.consoleLogs("Used: yt-dlp version " + version)

    # Probe leggero usato solo in fase di classificazione (PastedUrl._analyze), per
    # decidere se tentare yt-dlp su una pagina generica prima di arrendersi al
    # downloader generico. --simulate non scarica ne' analizza i singoli
    # formati: si affida per intero all'extractor di yt-dlp, che sa gia' da
    # solo riconoscere/fondere anche tracce audio/video separate (a differenza
    # del vecchio approccio "estrai un url e scaricalo con ffmpeg", qui basta
    # sapere che yt-dlp trova qualcosa - sara' lui stesso a scaricarlo per intero)
    @classmethod
    def isYtDlpDownloadable(cls, url, timeout=20):
        try:
            ytdlp = cls.checkYtDlp()
            if not ytdlp:
                return False
            result = subprocess.run([ytdlp, '--simulate', '--no-warnings', '--no-playlist', url],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     timeout=timeout, encoding='utf-8', errors='replace')
            return result.returncode == 0
        except Exception as err:
            cls.consoleLogs("Error: yt-dlp simulate - " + str(err))
            return False

    # Scarica (ed eventualmente fonde video+audio) direttamente con yt-dlp,
    # invece di estrarre un url e passarlo a ffmpeg come faceva la versione
    # precedente: yt-dlp e' lo strumento pensato apposta per questo, sa gia'
    # scegliere e fondere le tracce giuste (risolve anche il caso di pagine
    # con audio e video su url HLS separati, dove un singolo url passato a
    # ffmpeg produrrebbe un video muto), e non rischia di scaricare un url
    # temporaneo/firmato gia' scaduto nel frattempo
    @classmethod
    async def downloadVideoByYtDlp(cls, ytdlp, ffmpegPath, url, saveAs, onProgress=None, isStoppedFn=None):
        try:
            cls.logYtDlpVersion(ytdlp)
            command = [ytdlp, '--no-warnings', '--no-playlist', '--newline',
                       '--ffmpeg-location', ffmpegPath,
                       '-f', 'bestvideo+bestaudio/best',
                       '--merge-output-format', 'mp4',
                       '--progress-template', 'download:%s%%(progress.downloaded_bytes)s' % cls.YTDLP_PROGRESS_PREFIX]
            command += ['-o', saveAs, url]
            loop = asyncio.get_running_loop()
            stopped, returncode, stderr = await loop.run_in_executor(None, Tools._runYtDlpWithProgress, command, onProgress, isStoppedFn)
            if stopped:
                return [None, 'Stop forced by the user']
            if returncode == 0 and os.path.exists(saveAs) and os.path.getsize(saveAs) > cls.MIN_VALID_OUTPUT_SIZE_BYTES:
                return [True, Tools.getSizeDynamic(saveAs)]
            logging.error('yt-dlp error: ' + stderr)
            logging.error(str(command))
            return [False, stderr or 'yt-dlp produced no usable output']
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
    def saveStatsUrls(cls):
        url = MyText().saveStats
        new_data = {
            "ver": cls.getVersion(),
            "os": cls.getOs(),
        }
        cls.sendRequestPost(url, new_data)

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
