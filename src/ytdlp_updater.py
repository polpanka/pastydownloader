#!/usr/bin/python

import os, shutil, tempfile, zipfile
from PySide6.QtCore import QObject, Signal
from libs import Tools
from testi import MyText


class YtDlpUpdater(QObject):
    """Tiene aggiornato yt-dlp in background e lo scarica da zero al primo avvio
    (ensureInstalled). yt-dlp e' un wheel py3-none-any da PyPI, installato in
    ytDlpStorageDir()/<versione>/ e importato in-process.

    Ogni versione va in una cartella nuova, mai sovrascritta: un aggiornamento in
    background e' visto dal processo principale solo al riavvio (il modulo resta
    in sys.modules), ma il processo figlio di download reimporta ogni volta.
    Gira in un thread di background: solo statusMessage/statusMessageNow/ready
    raggiungono il thread grafico.
    """

    statusMessage = Signal(str, int)
    # messaggio conclusivo: non aspetta il turno in coda, sostituisce subito
    # quello "in corso" (vedi StatusQueue.showNow)
    statusMessageNow = Signal(str, int)
    # emesso solo da ensureInstalled(): se al primo avvio l'installazione e'
    # riuscita (Pasty.onYtDlpReady blocca la UI nel frattempo)
    ready = Signal(bool)

    CHECK_INTERVAL_HOURS = 6
    KEEP_VERSIONS = 2

    PYPI_URL = 'https://pypi.org/pypi/yt-dlp/json'

    _checking = False

    # Chiamato da main.py all'avvio e periodicamente; evita controlli sovrapposti
    def checkAndUpdate(self):
        if self._checking:
            return
        self._checking = True
        try:
            self._doCheck()
            Tools.checkAndUpdateYtDlpEjs()  # stesso ciclo, nessun segnale
        finally:
            self._checking = False

    # Se PyPI ha una versione piu' nuova di quella installata, la scarica
    def _doCheck(self):
        try:
            remoteVersion, wheel = self._fetchLatestRelease()
            if not remoteVersion or not wheel:
                return
            # dentro il try: installedYtDlpVersions() puo' sollevare e ucciderebbe il thread
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

    # Primo avvio (cascata dopo ffmpeg): se yt-dlp manca lo scarica. Thread
    # separato, tutto nel try/except: un'eccezione senza ready.emit bloccherebbe
    # la UI per sempre.
    def ensureInstalled(self):
        try:
            if Tools.checkYtDlp():
                self._pruneOldVersions()
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

    # (remoteVersion, wheel) da PyPI - wheel e' la entry .whl py3-none-any, o None
    def _fetchLatestRelease(self):
        release = Tools.readFileJson(self.PYPI_URL, timeout=10)
        info = (release.get('info') or {}) if isinstance(release, dict) else {}
        remoteVersion = info.get('version')
        urls = (release.get('urls') or []) if isinstance(release, dict) else []
        wheel = next((u for u in urls if u.get('packagetype') == 'bdist_wheel'
                      and str(u.get('filename', '')).endswith('-py3-none-any.whl')), None)
        return remoteVersion, wheel

    # Scarica il wheel in tmp, verifica checksum + importabilita', poi lo
    # installa in modo atomico in ytDlpStorageDir()/<version>/ (mai
    # sovrascrivendo l'installazione in uso), infine prune.
    def _downloadAndInstall(self, version, wheelUrl, sha256Expected):
        if not Tools.hasEnoughDiskSpace(Tools.ytDlpStorageDir()):
            raise IOError('Not enough disk space to install yt-dlp')
        destDir = os.path.join(Tools.ytDlpStorageDir(), version)
        with tempfile.TemporaryDirectory() as tmp:
            wheelPath = os.path.join(tmp, 'yt_dlp.whl')
            # timeout esplicito: un server muto bloccherebbe il thread per sempre
            ok, msg = Tools.downloadNotAsyncGeneric(wheelUrl, wheelPath, timeout=(10, 30))
            if not ok:
                raise IOError('Download failed: ' + str(msg))
            if sha256Expected:
                if Tools.sha256OfFile(wheelPath).lower() != str(sha256Expected).lower():
                    raise ValueError('Checksum mismatch for yt-dlp %s, discarding' % version)
            else:
                # raro: PyPI non pubblica lo sha256. Resta la verifica funzionale sotto.
                Tools.consoleLogs("yt-dlp %s: nessun sha256 da PyPI, controllo integrita' saltato" % version)
            extractDir = os.path.join(tmp, 'extracted')
            with zipfile.ZipFile(wheelPath) as z:
                z.extractall(extractDir)
            if not os.path.isfile(os.path.join(extractDir, Tools.YTDLP_PACKAGE_MARKER)):
                raise ValueError('yt_dlp package not found inside the downloaded wheel')
            if not Tools.verifyYtDlpImportable(extractDir):
                raise RuntimeError('Downloaded yt-dlp %s failed to import, discarded' % version)
            # move in '.part' poi os.replace atomico: un crash non lascia mai una
            # cartella parziale dove installedYtDlpVersions() la troverebbe
            os.makedirs(Tools.ytDlpStorageDir(), exist_ok=True)
            partialDir = destDir + '.part'
            shutil.rmtree(partialDir, ignore_errors=True)  # shutil.move annida se la dest esiste
            shutil.move(extractDir, partialDir)
            os.replace(partialDir, destDir)
        self._pruneOldVersions()

    # Elimina da ytDlpStorageDir() tutto tranne le ultime KEEP_VERSIONS valide:
    # anche cartelle '.part' o vecchi formati binari non piu' riconosciuti.
    # KEEP_VERSIONS=2 protegge la versione appena sostituita da un batch in corso.
    # Tutto nel try/except: i chiamanti non lo hanno, e un errore qui in
    # ensureInstalled() farebbe ready.emit(False), che chiude l'app.
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
