#!/usr/bin/python

import os, shutil, tempfile, subprocess
from PySide6.QtCore import QObject, Signal
from libs import Tools
from testi import MyText


class YtDlpUpdater(QObject):
    """Keeps the app's own yt-dlp build current in the background.

    Unlike ffmpeg, yt-dlp is published directly by its own project on
    GitHub with a real "latest release" API and per-file sha256 checksums
    (SHA2-256SUMS asset) - so this talks straight to that official upstream,
    no self-hosted manifest needed. A newer build is downloaded into a new
    versioned folder under Tools.ytDlpStorageDir() - it never overwrites the
    binary currently in place, so a download already running against an
    older version keeps working undisturbed, while any batch started after
    the swap picks up the new one via Tools.checkYtDlp(). Runs in a plain
    background thread (see main.py:checkYtDlpUpdate), so statusMessage is
    the only thing that reaches the GUI thread.
    """

    statusMessage = Signal(str, int)

    CHECK_INTERVAL_HOURS = 6
    KEEP_VERSIONS = 2

    API_URL = 'https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest'

    _checking = False

    # Punto di ingresso chiamato da main.py (all'avvio e periodicamente): evita
    # controlli sovrapposti se uno e' gia' in corso, poi esegue il controllo vero e proprio
    def checkAndUpdate(self):
        if self._checking:
            return
        self._checking = True
        try:
            self._doCheck()
        finally:
            self._checking = False

    # Interroga la release ufficiale piu' recente su GitHub, confronta la versione con
    # quella attualmente installata e, se ce n'e' una piu' nuova, scarica e installa
    # il binario giusto per il sistema operativo corrente
    def _doCheck(self):
        try:
            release = Tools.readFileJson(self.API_URL, timeout=10)
        except Exception as err:
            Tools.consoleLogs("yt-dlp update check failed: " + str(err))
            return
        remoteVersion = release.get('tag_name') if isinstance(release, dict) else None
        assets = (release.get('assets') or []) if isinstance(release, dict) else []
        if not remoteVersion or not assets:
            return
        currentVersions = Tools.installedYtDlpVersions()
        currentVersion = currentVersions[-1] if currentVersions else None
        if currentVersion and Tools.versionTuple(remoteVersion) <= Tools.versionTuple(currentVersion):
            return
        binName = Tools.ytDlpBinaryName()
        asset = next((a for a in assets if a.get('name') == binName), None)
        if not asset:
            return
        sumsAsset = next((a for a in assets if a.get('name') == 'SHA2-256SUMS'), None)
        Tools.consoleLogs("yt-dlp update found: " + remoteVersion)
        self.statusMessage.emit(MyText().ytDlpUpdating, 0)
        try:
            expectedSha256 = self._expectedSha256(sumsAsset['browser_download_url'], binName) if sumsAsset else None
            self._downloadAndInstall(remoteVersion, asset['browser_download_url'], expectedSha256)
            self.statusMessage.emit(MyText().ytDlpUpdateDone, 5)
        except Exception as err:
            Tools.consoleLogs("yt-dlp update failed: " + str(err))

    # Legge il file SHA2-256SUMS pubblicato con la release e ne estrae lo sha256
    # atteso per il binario di questo sistema operativo
    @staticmethod
    def _expectedSha256(sumsUrl, binName):
        req = Tools.sendRequestGet(sumsUrl, timeout=10)
        if not req:
            return None
        for line in req.text.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == binName:
                return parts[0]
        return None

    # Scarica il binario in una cartella temporanea, verifica checksum e funzionamento,
    # e solo a quel punto lo installa in modo atomico nella cartella versionata finale
    # (mai sovrascrivendo il binario eventualmente in uso), poi elimina le versioni vecchie.
    # La cartella finale e' Tools.ytDlpStorageDir()/<version>/<nome binario>, cioe' una
    # sottocartella "yt-dlp" dentro la cartella dati scrivibile dell'utente (QStandardPaths.
    # AppDataLocation), ad es. ~/.local/share/Pastylink/yt-dlp/2026.07.04/yt-dlp_linux su
    # Linux, ~/Library/Application Support/Pastylink/yt-dlp/2026.07.04/yt-dlp_macos su Mac,
    # %APPDATA%/Pastylink/yt-dlp/2026.07.04/yt-dlp.exe su Windows - mai la cartella di
    # installazione dell'app, che potrebbe essere di sola lettura
    def _downloadAndInstall(self, version, url, sha256Expected):
        binName = Tools.ytDlpBinaryName()
        destDir = os.path.join(Tools.ytDlpStorageDir(), version)
        finalBin = os.path.join(destDir, binName)
        with tempfile.TemporaryDirectory() as tmp:
            stagedBin = os.path.join(tmp, binName)
            ok, msg = Tools.downloadNotAsyncGeneric(url, stagedBin)
            if not ok:
                raise IOError('Download failed: ' + str(msg))
            if sha256Expected and Tools.sha256OfFile(stagedBin).lower() != str(sha256Expected).lower():
                raise ValueError('Checksum mismatch for yt-dlp %s, discarding' % version)
            if Tools.getOs() != 'win':
                # da eseguibile per l'utente corrente - mai servono permessi di
                # root: viene installato ed eseguito nella cartella dati
                # dell'utente, con gli stessi privilegi dell'app stessa
                os.chmod(stagedBin, 0o755)
            # scrivendo i byte noi stessi (niente browser/API di download di
            # sistema) il file non viene mai marcato "scaricato da internet"
            # (Mark of the Web su Windows, com.apple.quarantine su macOS), e
            # lo lanciamo con subprocess.run (mai shell=True/os.startfile):
            # quindi non compaiono i popup "sviluppatore sconosciuto"/
            # SmartScreen - quelli scattano solo quando un file taggato cosi'
            # viene aperto dalla shell, non quando lo eseguiamo noi via API.
            # Resta un rischio reale e fuori dal nostro controllo: yt-dlp.exe,
            # non firmato digitalmente, e' un bersaglio noto di falsi positivi
            # antivirus (Windows Defender in primis - segnalato dallo stesso
            # progetto yt-dlp). Se un AV lo mette in quarantena, questo
            # controllo (_verifyRuns) fallisce comunque in modo pulito: si
            # scarta il download e si continua a usare la versione precedente
            # funzionante, ritentando al prossimo controllo programmato
            if not self._verifyRuns(stagedBin):
                raise RuntimeError('Downloaded yt-dlp %s failed to run, discarded' % version)
            # only move a verified-working binary into the real storage dir,
            # and only ever expose it under its final name via an atomic
            # rename - so a crash/kill anywhere above never leaves a broken
            # or partial file where installedYtDlpVersions() would find it
            os.makedirs(destDir, exist_ok=True)
            partialBin = finalBin + '.part'
            shutil.move(stagedBin, partialBin)
            os.replace(partialBin, finalBin)
        self._pruneOldVersions()

    # Controlla che il binario scaricato sia davvero eseguibile e funzionante,
    # lanciandolo con --version prima di fidarsene
    @staticmethod
    def _verifyRuns(path):
        try:
            result = subprocess.run([path, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            return result.returncode == 0
        except Exception:
            return False

    # Elimina le versioni scaricate piu' vecchie, mantenendo solo le ultime KEEP_VERSIONS.
    # E' sicuro farlo anche se in quel momento c'e' un download/estrazione in corso:
    # KEEP_VERSIONS=2 fa si' che la versione appena sostituita (quella che un batch
    # avviato un attimo prima dell'aggiornamento potrebbe aver risolto) non venga mai
    # cancellata subito, ma solo al giro di pulizia successivo - servirebbero due
    # aggiornamenti veri consecutivi (quindi molte ore) prima che una versione ancora
    # in uso venga toccata. Il probe di classificazione (Tools.isYtDlpDownloadable) ha
    # un timeout breve, ma il download vero (Tools.downloadVideoByYtDlp) no - non e'
    # quindi garantito che un processo non possa sopravvivere cosi' a lungo, ma anche
    # in quel caso raro non e' un problema:
    # Come ulteriore rete di sicurezza: su Windows, se il file fosse comunque bloccato
    # (in uso da un processo), shutil.rmtree solleva OSError, che viene catturato qui
    # sotto e si riprova al controllo successivo; su Linux/Mac cancellare il file di un
    # processo in esecuzione e' comunque innocuo di per se' (il kernel mantiene l'inode
    # finche' il processo lo tiene aperto, anche dopo la cancellazione della voce su disco)
    @classmethod
    def _pruneOldVersions(cls):
        for old in Tools.installedYtDlpVersions()[:-cls.KEEP_VERSIONS]:
            try:
                shutil.rmtree(os.path.join(Tools.ytDlpStorageDir(), old))
            except OSError as err:
                Tools.consoleLogs("Could not prune old yt-dlp %s yet: %s" % (old, err))
