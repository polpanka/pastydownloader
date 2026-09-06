#!/usr/bin/python
"""
Test per FfmpegInstaller (ffmpeg_installer.py): il meccanismo che scarica ffmpeg
al primo avvio quando non e' gia' presente in Tools.ffmpegStorageDir() (vedi
Pasty.initDependencies in main.py). Copre:
 - estrazione del solo binario ffmpeg dai 3 formati di archivio reali (zip per
   win/mac, tar.xz per linux), costruiti qui in memoria - niente rete
 - verifica funzionale del binario scaricato (-version)
 - il flusso completo ensureInstalled(): gia' installato / successo / fallimento
   download / fallimento verifica, e i segnali Qt emessi in ciascun caso

Esecuzione: python3 -m unittest discover -s tests (stesse dipendenze del programma).
"""

import io
import os
import sys
import tarfile
import tempfile
import unittest
import zipfile
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from testi import MyText

_app = QApplication.instance() or QApplication(sys.argv[:1])
# senza questi due, QStandardPaths.AppDataLocation (usato da Tools.ffmpegStorageDir)
# risolve a una cartella basata sull'argv0 del test runner invece che su quella
# vera dell'app - stesso setup del vero main.py
_app.setApplicationName(MyText().appName)
_app.setOrganizationName(MyText().orgName)

from libs import Tools
from ffmpeg_installer import FfmpegInstaller


def makeZip(path, members):
    with zipfile.ZipFile(path, 'w') as z:
        for name, content in members.items():
            z.writestr(name, content)


def makeTarXz(path, members):
    with tarfile.open(path, 'w:xz') as t:
        for name, content in members.items():
            data = content.encode()
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = 0o755
            t.addfile(info, io.BytesIO(data))


class ExtractTest(unittest.TestCase):
    """FfmpegInstaller._extract deve prendere solo il binario ffmpeg dall'archivio
    (mai l'archivio intero: sono build "full" da centinaia di MB con
    ffprobe/ffplay/doc che non servono), rispettando la struttura reale delle
    3 fonti (verificata scaricando davvero i 3 archivi durante lo sviluppo)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_mac_zip_has_ffmpeg_at_root(self):
        # evermeet.cx: zip con il binario "ffmpeg" gia' in radice
        archive = os.path.join(self.tmp.name, 'mac.zip')
        makeZip(archive, {'ffmpeg': 'FAKE_MAC_BIN'})
        outDir = os.path.join(self.tmp.name, 'out')
        result = FfmpegInstaller._extract('mac', archive, outDir)
        self.assertEqual(result, os.path.join(outDir, 'ffmpeg'))
        with open(result) as f:
            self.assertEqual(f.read(), 'FAKE_MAC_BIN')

    def test_win_zip_picks_bin_ffmpeg_exe_ignoring_siblings(self):
        # BtbN: zip con <cartella-versione>/bin/ffmpeg.exe, accanto a
        # ffprobe.exe/ffplay.exe che vanno ignorati
        archive = os.path.join(self.tmp.name, 'win.zip')
        makeZip(archive, {
            'ffmpeg-master-latest-win64-gpl/bin/ffprobe.exe': 'ignore me',
            'ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe': 'FAKE_WIN_BIN',
            'ffmpeg-master-latest-win64-gpl/bin/ffplay.exe': 'ignore me too',
        })
        outDir = os.path.join(self.tmp.name, 'out')
        result = FfmpegInstaller._extract('win', archive, outDir)
        self.assertEqual(result, os.path.join(outDir, 'ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe'))
        with open(result) as f:
            self.assertEqual(f.read(), 'FAKE_WIN_BIN')

    def test_linux_tarxz_picks_bin_ffmpeg(self):
        # BtbN: tar.xz con <cartella-versione>/bin/ffmpeg
        archive = os.path.join(self.tmp.name, 'linux.tar.xz')
        makeTarXz(archive, {
            'ffmpeg-master-latest-linux64-gpl/bin/ffprobe': 'ignore me',
            'ffmpeg-master-latest-linux64-gpl/bin/ffmpeg': 'FAKE_LINUX_BIN',
        })
        outDir = os.path.join(self.tmp.name, 'out')
        result = FfmpegInstaller._extract('linux', archive, outDir)
        self.assertEqual(result, os.path.join(outDir, 'ffmpeg-master-latest-linux64-gpl/bin/ffmpeg'))
        with open(result) as f:
            self.assertEqual(f.read(), 'FAKE_LINUX_BIN')

    def test_win_zip_without_the_expected_member_raises(self):
        archive = os.path.join(self.tmp.name, 'win.zip')
        makeZip(archive, {'unexpected/layout/readme.txt': 'nope'})
        with self.assertRaises(ValueError):
            FfmpegInstaller._extract('win', archive, os.path.join(self.tmp.name, 'out'))


class VerifyRunsTest(unittest.TestCase):
    """_verifyRuns: unica verifica disponibile (nessuna delle 3 fonti pubblica
    un checksum ufficiale) - deve fidarsi solo di un returncode 0 reale, mai
    di assunzioni sul testo di output (stessa lezione gia' imparata con
    PastedUrl._isRealVideoOnline, vedi pasted_url.py)."""

    def test_true_when_process_exits_zero(self):
        with mock.patch('ffmpeg_installer.subprocess.run') as run:
            run.return_value = mock.Mock(returncode=0)
            self.assertTrue(FfmpegInstaller._verifyRuns('/fake/ffmpeg'))

    def test_false_when_process_exits_non_zero(self):
        with mock.patch('ffmpeg_installer.subprocess.run') as run:
            run.return_value = mock.Mock(returncode=1)
            self.assertFalse(FfmpegInstaller._verifyRuns('/fake/ffmpeg'))

    def test_false_when_process_cannot_even_start(self):
        with mock.patch('ffmpeg_installer.subprocess.run', side_effect=OSError('not found')):
            self.assertFalse(FfmpegInstaller._verifyRuns('/fake/ffmpeg'))


class EnsureInstalledTest(unittest.TestCase):
    """Flusso completo di ensureInstalled(): copre i segnali emessi (statusMessage/
    ready) in ciascun esito, che sono cio' da cui dipende il lock della UI in
    Pasty.initDependencies/onFfmpegReady."""

    def setUp(self):
        self.installer = FfmpegInstaller()
        self.readyEvents = []
        self.statusEvents = []
        self.installer.ready.connect(self.readyEvents.append)
        self.installer.statusMessage.connect(lambda txt, sec: self.statusEvents.append((txt, sec)))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_already_installed_short_circuits_without_downloading(self):
        with mock.patch.object(Tools, 'checkFFmpeg', return_value='/already/there/ffmpeg'), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric') as download:
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [True])
        download.assert_not_called()
        self.assertEqual(self.statusEvents, [])  # nessun messaggio: non c'e' stato nessun download

    def test_regression_unexpected_error_in_the_initial_check_still_emits_ready_false(self):
        # ensureInstalled() gira in un threading.Thread grezzo (vedi
        # Pasty.initDependencies): un'eccezione non gestita anche solo nel
        # controllo iniziale (non nel download vero e proprio) lo farebbe
        # morire in silenzio senza mai emettere ready, lasciando l'interfaccia
        # bloccata per sempre senza popup ne' messaggio
        with mock.patch.object(Tools, 'checkFFmpeg', side_effect=OSError('disco pieno')):
            self.installer.ensureInstalled()  # non deve sollevare
        self.assertEqual(self.readyEvents, [False])

    def test_not_enough_disk_space_emits_ready_false_without_downloading(self):
        with mock.patch.object(Tools, 'checkFFmpeg', return_value=None), \
             mock.patch.object(Tools, 'ffmpegStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'hasEnoughDiskSpace', return_value=False), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric') as download:
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [False])
        download.assert_not_called()

    def test_download_failure_emits_ready_false_and_leaves_no_partial_file(self):
        with mock.patch.object(Tools, 'checkFFmpeg', return_value=None), \
             mock.patch.object(Tools, 'ffmpegStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric', return_value=(False, 'connection refused')):
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [False])
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_binary_that_fails_to_run_is_discarded_not_installed(self):
        def fakeDownload(url, saveAs, isStopped=None, timeout=None):
            makeZip(saveAs, {'ffmpeg': 'not a real binary'})
            return [True, '1 KB']

        with mock.patch.object(Tools, 'checkFFmpeg', return_value=None), \
             mock.patch.object(Tools, 'getOs', return_value='mac'), \
             mock.patch.object(Tools, 'ffmpegBinaryName', return_value='ffmpeg_mac'), \
             mock.patch.object(Tools, 'ffmpegStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric', side_effect=fakeDownload):
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [False])
        self.assertEqual(os.listdir(self.tmp.name), [])  # niente file rotti lasciati in giro

    def test_successful_end_to_end_install_on_linux(self):
        # binario "vero" (uno script che esce con successo): copre anche
        # _verifyRuns per davvero, non mockato, chmod incluso
        def fakeDownload(url, saveAs, isStopped=None, timeout=None):
            # nell'archivio il binario si chiama sempre "ffmpeg" (non "ffmpeg_linux":
            # quello e' solo il nome locale con cui viene poi installato)
            makeTarXz(saveAs, {'ffmpeg-master-latest-linux64-gpl/bin/ffmpeg': '#!/bin/sh\nexit 0\n'})
            return [True, '1 KB']

        with mock.patch.object(Tools, 'checkFFmpeg', return_value=None), \
             mock.patch.object(Tools, 'getOs', return_value='linux'), \
             mock.patch.object(Tools, 'ffmpegBinaryName', return_value='ffmpeg_linux'), \
             mock.patch.object(Tools, 'ffmpegStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric', side_effect=fakeDownload):
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [True])
        finalBin = os.path.join(self.tmp.name, 'ffmpeg_linux')
        self.assertTrue(os.path.exists(finalBin))
        self.assertTrue(os.access(finalBin, os.X_OK))
        self.assertEqual(len(self.statusEvents), 1)  # un solo messaggio "in corso" mostrato all'avvio del download


class HasEnoughDiskSpaceTest(unittest.TestCase):
    """Tools.hasEnoughDiskSpace: usato da FfmpegInstaller/YtDlpUpdater prima di
    scaricare, per non lasciare a meta' un download su un disco quasi pieno."""

    def test_true_when_free_space_is_above_the_threshold(self):
        with mock.patch('libs.shutil.disk_usage', return_value=mock.Mock(free=Tools.MIN_FREE_DISK_BYTES + 1)):
            self.assertTrue(Tools.hasEnoughDiskSpace('/any/path'))

    def test_false_when_free_space_is_below_the_threshold(self):
        with mock.patch('libs.shutil.disk_usage', return_value=mock.Mock(free=Tools.MIN_FREE_DISK_BYTES - 1)):
            self.assertFalse(Tools.hasEnoughDiskSpace('/any/path'))


class CheckFFmpegResilientToStorageDirFailureTest(unittest.TestCase):
    """Tools.checkFFmpeg() non deve mai sollevare: ffmpegStorageDir() puo'
    fallire (permessi, disco pieno...), e checkFFmpeg() viene chiamato senza
    protezione sia sul thread principale (Pasty.initDependencies, all'avvio)
    sia dentro FfmpegInstaller.ensureInstalled - deve restituire None (ffmpeg
    non trovato, verra' scaricato) invece di far esplodere il chiamante."""

    def test_returns_none_instead_of_raising(self):
        with mock.patch.object(Tools, 'ffmpegStorageDir', side_effect=OSError('permessi negati')):
            result = Tools.checkFFmpeg()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
