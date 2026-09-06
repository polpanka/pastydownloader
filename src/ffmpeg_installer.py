#!/usr/bin/python

import os, shutil, tempfile, subprocess, zipfile, tarfile
from PySide6.QtCore import QObject, Signal
from libs import Tools
from testi import MyText


class FfmpegInstaller(QObject):
    """Scarica ffmpeg al primo avvio se manca. Blocca la UI durante il download
    (non e' un aggiornamento in background come yt-dlp). Nessuna fonte pubblica
    un checksum: l'unica verifica e' lanciare il binario con -version."""

    statusMessage = Signal(str, int)
    ready = Signal(bool)

    # Windows/Linux: BtbN in zip/tar.xz (la 7z di gyan.dev non e' estraibile in
    # puro Python)
    URLS = {
        'win':   'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
        'mac':   'https://evermeet.cx/ffmpeg/ffmpeg-9.0.1.zip',
        'linux': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz',
    }

    # Thread separato, tutto nel try/except: senza ready.emit la UI si blocca
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

    # Scarica in tmp, estrae il solo binario ffmpeg, lo verifica e lo installa
    # in modo atomico (move in '.part' + os.replace)
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
            # timeout esplicito: un server muto bloccherebbe la UI per sempre
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

    # Estrae il solo binario ffmpeg (le build "full" hanno anche ffprobe/ffplay/doc)
    @staticmethod
    def _extract(osName, archivePath, outDir):
        if osName == 'mac':
            # evermeet.cx: "ffmpeg" in radice
            with zipfile.ZipFile(archivePath) as z:
                return z.extract('ffmpeg', outDir)
        if osName == 'win':
            # BtbN: <versione>/bin/ffmpeg.exe
            with zipfile.ZipFile(archivePath) as z:
                member = next((n for n in z.namelist() if n.endswith('/bin/ffmpeg.exe')), None)
                if not member:
                    raise ValueError('ffmpeg.exe not found inside the downloaded archive')
                return z.extract(member, outDir)
        # linux - BtbN: <versione>/bin/ffmpeg
        with tarfile.open(archivePath, mode='r:xz') as t:
            member = next((m for m in t.getmembers() if m.name.endswith('/bin/ffmpeg')), None)
            if not member:
                raise ValueError('ffmpeg not found inside the downloaded archive')
            t.extract(member, outDir, filter='data')
        return os.path.join(outDir, member.name)

    # Lancia il binario con -version: unica verifica possibile (niente checksum)
    @staticmethod
    def _verifyRuns(path):
        try:
            result = subprocess.run([path, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            return result.returncode == 0
        except Exception:
            return False
