#!/usr/bin/python
"""
Test per YtDlpUpdater.ensureInstalled() (ytdlp_updater.py): il meccanismo che
scarica yt-dlp al primo avvio quando non e' gia' presente in
Tools.ytDlpStorageDir() (vedi Pasty.initDependencies in main.py, stesso
schema di FfmpegInstaller per ffmpeg - a differenza di quello pero' yt-dlp
pubblica un manifest ufficiale con checksum SHA2-256SUMS, verificato qui).

Il flusso completo (rete reale, GitHub) e' stato verificato manualmente
durante lo sviluppo prima di scrivere questi test mockati: ensureInstalled()
contro una cartella vuota scarica davvero l'ultima release, verifica il
checksum e installa un binario funzionante.

Esecuzione: python3 -m unittest discover -s tests (stesse dipendenze del programma).
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from testi import MyText

_app = QApplication.instance() or QApplication(sys.argv[:1])
_app.setApplicationName(MyText().appName)
_app.setOrganizationName(MyText().orgName)

from libs import Tools
from ytdlp_updater import YtDlpUpdater


RELEASE_JSON = {
    'tag_name': '2099.01.01',
    'assets': [
        {'name': 'yt-dlp_linux', 'browser_download_url': 'https://example.test/yt-dlp_linux'},
        {'name': 'yt-dlp.exe', 'browser_download_url': 'https://example.test/yt-dlp.exe'},
        {'name': 'yt-dlp_macos', 'browser_download_url': 'https://example.test/yt-dlp_macos'},
        {'name': 'SHA2-256SUMS', 'browser_download_url': 'https://example.test/SHA2-256SUMS'},
    ],
}


class EnsureInstalledTest(unittest.TestCase):
    """Copre i segnali emessi (statusMessage/ready) in ciascun esito, che sono
    cio' da cui dipende il lock della UI in Pasty.initDependencies/onYtDlpReady."""

    def setUp(self):
        self.installer = YtDlpUpdater()
        self.readyEvents = []
        self.statusEvents = []
        self.installer.ready.connect(self.readyEvents.append)
        self.installer.statusMessage.connect(lambda txt, sec: self.statusEvents.append((txt, sec)))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_already_installed_short_circuits_without_downloading(self):
        with mock.patch.object(Tools, 'checkYtDlp', return_value='/already/there/yt-dlp'), \
             mock.patch.object(Tools, 'readFileJson') as fetchRelease:
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [True])
        fetchRelease.assert_not_called()
        self.assertEqual(self.statusEvents, [])  # nessun messaggio: non c'e' stato nessun download

    def test_regression_unexpected_error_in_the_initial_check_still_emits_ready_false(self):
        # ensureInstalled() gira in un threading.Thread grezzo (vedi
        # Pasty.initDependencies): un'eccezione non gestita anche solo nel
        # controllo iniziale lo farebbe morire in silenzio senza mai emettere
        # ready, lasciando l'interfaccia bloccata per sempre
        with mock.patch.object(Tools, 'checkYtDlp', side_effect=OSError('disco pieno')):
            self.installer.ensureInstalled()  # non deve sollevare
        self.assertEqual(self.readyEvents, [False])

    def test_no_release_asset_for_this_os_emits_ready_false(self):
        with mock.patch.object(Tools, 'checkYtDlp', return_value=None), \
             mock.patch.object(Tools, 'getOs', return_value='linux'), \
             mock.patch.object(Tools, 'readFileJson', return_value={'tag_name': '2099.01.01', 'assets': []}):
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [False])

    def test_not_enough_disk_space_emits_ready_false_without_downloading(self):
        with mock.patch.object(Tools, 'checkYtDlp', return_value=None), \
             mock.patch.object(Tools, 'getOs', return_value='linux'), \
             mock.patch.object(Tools, 'ytDlpStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'readFileJson', return_value=RELEASE_JSON), \
             mock.patch.object(Tools, 'sendRequestGet', return_value=None), \
             mock.patch.object(Tools, 'hasEnoughDiskSpace', return_value=False), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric') as download:
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [False])
        download.assert_not_called()

    def test_download_failure_emits_ready_false_and_leaves_no_partial_file(self):
        with mock.patch.object(Tools, 'checkYtDlp', return_value=None), \
             mock.patch.object(Tools, 'getOs', return_value='linux'), \
             mock.patch.object(Tools, 'ytDlpBinaryName', return_value='yt-dlp_linux'), \
             mock.patch.object(Tools, 'ytDlpStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'readFileJson', return_value=RELEASE_JSON), \
             mock.patch.object(Tools, 'sendRequestGet', return_value=None), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric', return_value=(False, 'connection refused')):
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [False])
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_checksum_mismatch_is_discarded_not_installed(self):
        def fakeDownload(url, saveAs, isStopped=None, timeout=None):
            with open(saveAs, 'wb') as f:
                f.write(b'#!/bin/sh\nexit 0\n')
            return [True, '1 KB']

        def fakeSumsRequest(url, timeout=10):
            resp = mock.Mock()
            resp.text = 'deadbeef00  yt-dlp_linux\n'  # sha256 sbagliato apposta
            return resp

        with mock.patch.object(Tools, 'checkYtDlp', return_value=None), \
             mock.patch.object(Tools, 'getOs', return_value='linux'), \
             mock.patch.object(Tools, 'ytDlpBinaryName', return_value='yt-dlp_linux'), \
             mock.patch.object(Tools, 'ytDlpStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'readFileJson', return_value=RELEASE_JSON), \
             mock.patch.object(Tools, 'sendRequestGet', side_effect=fakeSumsRequest), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric', side_effect=fakeDownload):
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [False])
        self.assertEqual(os.listdir(self.tmp.name), [])  # niente file scartati lasciati in giro

    def test_successful_end_to_end_install_on_linux(self):
        # binario "vero" (uno script che esce con successo): copre anche
        # _verifyRuns per davvero, non mockato, chmod incluso - checksum
        # calcolato per davvero sul contenuto scritto da fakeDownload
        scriptContent = b'#!/bin/sh\nexit 0\n'
        import hashlib
        realSha256 = hashlib.sha256(scriptContent).hexdigest()

        def fakeDownload(url, saveAs, isStopped=None, timeout=None):
            with open(saveAs, 'wb') as f:
                f.write(scriptContent)
            return [True, '1 KB']

        def fakeSumsRequest(url, timeout=10):
            resp = mock.Mock()
            resp.text = '%s  yt-dlp_linux\n' % realSha256
            return resp

        with mock.patch.object(Tools, 'checkYtDlp', return_value=None), \
             mock.patch.object(Tools, 'getOs', return_value='linux'), \
             mock.patch.object(Tools, 'ytDlpBinaryName', return_value='yt-dlp_linux'), \
             mock.patch.object(Tools, 'ytDlpStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'readFileJson', return_value=RELEASE_JSON), \
             mock.patch.object(Tools, 'sendRequestGet', side_effect=fakeSumsRequest), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric', side_effect=fakeDownload):
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [True])
        finalBin = os.path.join(self.tmp.name, '2099.01.01', 'yt-dlp_linux')
        self.assertTrue(os.path.exists(finalBin))
        self.assertTrue(os.access(finalBin, os.X_OK))
        self.assertEqual(len(self.statusEvents), 1)  # un solo messaggio "in corso" mostrato all'avvio del download


class FetchLatestReleaseTest(unittest.TestCase):
    """_fetchLatestRelease(): condiviso da _doCheck() (periodico) ed
    ensureInstalled() (primo avvio) - deve trovare il giusto asset per il SO
    corrente e non esplodere se una release non ne pubblica uno."""

    def test_finds_asset_and_sums_for_current_os(self):
        with mock.patch.object(Tools, 'getOs', return_value='linux'), \
             mock.patch.object(Tools, 'readFileJson', return_value=RELEASE_JSON):
            version, asset, sums = YtDlpUpdater()._fetchLatestRelease()
        self.assertEqual(version, '2099.01.01')
        self.assertEqual(asset['name'], 'yt-dlp_linux')
        self.assertEqual(sums['name'], 'SHA2-256SUMS')

    def test_asset_is_none_when_release_has_none_for_this_os(self):
        releaseWithoutLinux = {'tag_name': '2099.01.01', 'assets': [
            {'name': 'yt-dlp.exe', 'browser_download_url': 'https://example.test/yt-dlp.exe'},
        ]}
        with mock.patch.object(Tools, 'getOs', return_value='linux'), \
             mock.patch.object(Tools, 'readFileJson', return_value=releaseWithoutLinux):
            version, asset, sums = YtDlpUpdater()._fetchLatestRelease()
        self.assertEqual(version, '2099.01.01')
        self.assertIsNone(asset)


class CheckYtDlpResilientToStorageDirFailureTest(unittest.TestCase):
    """Tools.checkYtDlp() non deve mai sollevare: ytDlpStorageDir() puo'
    fallire (permessi, disco pieno...), e checkYtDlp() viene chiamato senza
    protezione sia sul thread principale (Pasty.initDependencies, all'avvio)
    sia dentro YtDlpUpdater.ensureInstalled - deve restituire None invece di
    far esplodere il chiamante."""

    def test_returns_none_instead_of_raising(self):
        with mock.patch.object(Tools, 'ytDlpStorageDir', side_effect=OSError('permessi negati')):
            result = Tools.checkYtDlp()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
