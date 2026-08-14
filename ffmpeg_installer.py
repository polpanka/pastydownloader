#!/usr/bin/python

import os, shutil, tempfile, subprocess, zipfile, tarfile
from PySide6.QtCore import QObject, Signal
from libs import Tools
from testi import MyText


class FfmpegInstaller(QObject):
    """Scarica ffmpeg al primo avvio se non e' gia' presente in Tools.ffmpegStorageDir().

    A differenza di yt-dlp (vedi YtDlpUpdater), ffmpeg non ha piu' nessun binario
    "seed" imbarcato nell'eseguibile: l'app parte senza ffmpeg e, se non l'ha gia'
    scaricato in una sessione precedente, lo scarica da zero qui, bloccando
    l'interfaccia (vedi Pasty.initDependencies/onFfmpegReady) finche' il
    download e la verifica non sono completi - non e' un aggiornamento
    periodico in background come per yt-dlp, solo un controllo all'avvio.

    Nessuna delle 3 fonti pubblica un manifest/checksum ufficiale scaricabile
    a parte come per yt-dlp (SHA2-256SUMS): l'unica verifica possibile e'
    funzionale, lanciando il binario scaricato con -version prima di fidarsene
    (vedi _verifyRuns), esattamente come gia' fatto per yt-dlp.
    """

    statusMessage = Signal(str, int)
    ready = Signal(bool)

    # Windows: la build "essentials" di gyan.dev (quella storicamente usata,
    # vedi Tools.FFMPEG_BIN_WIN) e' un .7z con filtro BCJ2 non estraibile in
    # puro Python (py7zr non lo supporta - verificato: UnsupportedCompressionMethodError).
    # Si usa quindi la build BtbN in .zip, la stessa fonte gia' verificata per Linux
    URLS = {
        'win':   'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
        'mac':   'https://evermeet.cx/ffmpeg/ffmpeg-9.0.1.zip',
        'linux': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz',
    }

    # Punto di ingresso: verifica se ffmpeg e' gia' installato, altrimenti lo scarica.
    # Va chiamato in un thread separato (vedi Pasty.installDependencies): fa una
    # richiesta di rete e puo' metterci diversi secondi.
    # Tutto il corpo e' dentro il try/except (anche il controllo iniziale, non
    # solo il download): questo metodo gira in un threading.Thread grezzo, e
    # un'eccezione non gestita qui lo farebbe morire in silenzio senza mai
    # emettere ready, lasciando l'interfaccia bloccata per sempre (stesso
    # principio gia' applicato a AsyncWorker.runAllUrls/Pasty.getReferers)
    def ensureInstalled(self):
        try:
            if Tools.checkFFmpeg():
                self.ready.emit(True)
                return
            Tools.consoleLogs("ffmpeg non presente, scaricamento in corso...")
            self.statusMessage.emit(MyText().ytDlpUpdating, 0)
            self._downloadAndInstall()
            Tools.consoleLogs("ffmpeg installato correttamente")
            self.ready.emit(True)
        except Exception as err:
            Tools.consoleLogs("Installazione ffmpeg fallita: " + str(err))
            self.ready.emit(False)

    # Scarica l'archivio in una cartella temporanea, estrae solo il binario ffmpeg,
    # verifica che funzioni davvero e solo a quel punto lo installa in modo atomico
    # in Tools.ffmpegStorageDir() - un crash/kill in un punto qualsiasi qui sopra
    # non lascia mai un binario parziale/rotto dove checkFFmpeg() lo troverebbe
    def _downloadAndInstall(self):
        osName = Tools.getOs()
        url = self.URLS.get(osName)
        if not url:
            raise ValueError('No ffmpeg download source for this OS: %s' % osName)
        if not Tools.hasEnoughDiskSpace(Tools.ffmpegStorageDir()):
            raise IOError('Not enough disk space to install ffmpeg')
        binName = Tools.ffmpegBinaryName()
        finalBin = os.path.join(Tools.ffmpegStorageDir(), binName)
        with tempfile.TemporaryDirectory() as tmp:
            archivePath = os.path.join(tmp, os.path.basename(url))
            # timeout esplicito (connessione, tra un chunk e il successivo):
            # senza, un server che accetta la connessione e poi non risponde
            # piu' bloccherebbe questo thread per sempre - e a differenza di
            # yt-dlp (aggiornamento in background, non vitale) qui terrebbe
            # l'intera interfaccia bloccata a tempo indeterminato (vedi
            # Pasty.initDependencies). Il read-timeout si applica tra un
            # chunk e il successivo, non alla durata totale: un download
            # lento ma che progredisce non viene interrotto
            ok, msg = Tools.downloadNotAsyncGeneric(url, archivePath, timeout=(10, 30))
            if not ok:
                raise IOError('Download failed: ' + str(msg))
            extractedBin = self._extract(osName, archivePath, os.path.join(tmp, 'extracted'))
            if osName != 'win':
                os.chmod(extractedBin, 0o755)
            if not self._verifyRuns(extractedBin):
                raise RuntimeError('Downloaded ffmpeg failed to run, discarded')
            os.makedirs(Tools.ffmpegStorageDir(), exist_ok=True)
            partialBin = finalBin + '.part'
            shutil.move(extractedBin, partialBin)
            os.replace(partialBin, finalBin)

    # Estrae solo il file ffmpeg dall'archivio (mai l'archivio intero: sono build
    # "full" da centinaia di MB con ffprobe/ffplay/doc che non servono all'app).
    # Il nome cercato dentro l'archivio e' quello con cui la fonte lo pubblica
    # (sempre "ffmpeg"/"ffmpeg.exe", verificato scaricando i 3 archivi reali
    # durante lo sviluppo) - non e' detto coincida con Tools.ffmpegBinaryName()
    # (il nome locale con cui viene poi installato, vedi _downloadAndInstall),
    # che su Linux/Mac e' rinominato per disambiguare i 3 SO
    @staticmethod
    def _extract(osName, archivePath, outDir):
        if osName == 'mac':
            # evermeet.cx: zip con il binario "ffmpeg" gia' in radice
            with zipfile.ZipFile(archivePath) as z:
                return z.extract('ffmpeg', outDir)  # extract() ritorna gia' il path risolto
        if osName == 'win':
            # BtbN: zip con <cartella-versione>/bin/ffmpeg.exe
            with zipfile.ZipFile(archivePath) as z:
                member = next((n for n in z.namelist() if n.endswith('/bin/ffmpeg.exe')), None)
                if not member:
                    raise ValueError('ffmpeg.exe not found inside the downloaded archive')
                return z.extract(member, outDir)  # extract() ritorna gia' il path risolto
        # linux - BtbN: tar.xz con <cartella-versione>/bin/ffmpeg
        with tarfile.open(archivePath, mode='r:xz') as t:
            member = next((m for m in t.getmembers() if m.name.endswith('/bin/ffmpeg')), None)
            if not member:
                raise ValueError('ffmpeg not found inside the downloaded archive')
            t.extract(member, outDir, filter='data')
        return os.path.join(outDir, member.name)

    # Controlla che il binario scaricato sia davvero eseguibile e funzionante,
    # lanciandolo con -version prima di fidarsene (stesso principio di
    # YtDlpUpdater._verifyRuns, unica verifica disponibile qui: nessuna delle
    # fonti pubblica un checksum ufficiale da confrontare)
    @staticmethod
    def _verifyRuns(path):
        try:
            result = subprocess.run([path, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            return result.returncode == 0
        except Exception:
            return False
