#!/usr/bin/python
"""
Test per YtDlpUpdater.ensureInstalled() (ytdlp_updater.py): il meccanismo che
scarica yt-dlp al primo avvio quando non e' gia' presente in
Tools.ytDlpStorageDir() (vedi Pasty.initDependencies in main.py, stesso
schema di FfmpegInstaller per ffmpeg). A differenza di quello pero' yt-dlp e'
un pacchetto Python (wheel py3-none-any) installato da PyPI, non un binario
per SO: PyPI pubblica gia' lo sha256 di ogni file nella sua API JSON, quindi
niente file di checksum separato da scaricare a parte.

Il flusso completo (rete reale, PyPI) e' stato verificato manualmente durante
lo sviluppo prima di scrivere questi test mockati: ensureInstalled() contro
una cartella vuota scarica davvero l'ultima versione, verifica il checksum e
installa un pacchetto importabile.

Esecuzione: python3 -m unittest discover -s tests (stesse dipendenze del programma).
"""

import hashlib
import io
import os
import sys
import tempfile
import unittest
import zipfile
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
    'info': {'version': '2099.01.01'},
    'urls': [
        {'packagetype': 'sdist', 'filename': 'yt_dlp-2099.01.01.tar.gz',
         'url': 'https://example.test/yt_dlp-2099.01.01.tar.gz', 'digests': {'sha256': 'deadbeef'}},
        {'packagetype': 'bdist_wheel', 'filename': 'yt_dlp-2099.01.01-py3-none-any.whl',
         'url': 'https://example.test/yt_dlp-2099.01.01-py3-none-any.whl', 'digests': {'sha256': 'aaaa'}},
    ],
}


def _buildFakeWheelBytes(version):
    """Un wheel minimo ma davvero importabile (yt_dlp/__init__.py +
    yt_dlp/version.py con __version__), per esercitare per davvero
    Tools.verifyYtDlpImportable (un vero processo figlio che fa 'import
    yt_dlp'), non solo l'estrazione dello zip."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('yt_dlp/__init__.py', 'from . import version\n')
        z.writestr('yt_dlp/version.py', '__version__ = %r\n' % version)
    return buf.getvalue()


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
        # ytDlpStorageDir mockato sulla cartella temporanea di test: il ramo
        # "gia' installato" chiama anche _pruneOldVersions() (vedi
        # ensureInstalled), che senza questo mock toccherebbe la vera
        # cartella AppData dell'app durante l'esecuzione dei test
        with mock.patch.object(Tools, 'checkYtDlp', return_value='/already/there/yt-dlp/2099.01.01'), \
             mock.patch.object(Tools, 'ytDlpStorageDir', return_value=self.tmp.name), \
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

    def test_no_wheel_published_emits_ready_false(self):
        releaseWithoutWheel = {'info': {'version': '2099.01.01'}, 'urls': [
            {'packagetype': 'sdist', 'filename': 'yt_dlp-2099.01.01.tar.gz',
             'url': 'https://example.test/x', 'digests': {'sha256': 'a'}},
        ]}
        with mock.patch.object(Tools, 'checkYtDlp', return_value=None), \
             mock.patch.object(Tools, 'readFileJson', return_value=releaseWithoutWheel):
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [False])

    def test_not_enough_disk_space_emits_ready_false_without_downloading(self):
        with mock.patch.object(Tools, 'checkYtDlp', return_value=None), \
             mock.patch.object(Tools, 'ytDlpStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'readFileJson', return_value=RELEASE_JSON), \
             mock.patch.object(Tools, 'hasEnoughDiskSpace', return_value=False), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric') as download:
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [False])
        download.assert_not_called()

    def test_download_failure_emits_ready_false_and_leaves_no_partial_file(self):
        with mock.patch.object(Tools, 'checkYtDlp', return_value=None), \
             mock.patch.object(Tools, 'ytDlpStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'readFileJson', return_value=RELEASE_JSON), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric', return_value=(False, 'connection refused')):
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [False])
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_checksum_mismatch_is_discarded_not_installed(self):
        def fakeDownload(url, saveAs, isStopped=None, timeout=None):
            with open(saveAs, 'wb') as f:
                f.write(b'not a real wheel')
            return [True, '1 KB']

        releaseWithWrongHash = {'info': {'version': '2099.01.01'}, 'urls': [
            {'packagetype': 'bdist_wheel', 'filename': 'yt_dlp-2099.01.01-py3-none-any.whl',
             'url': 'https://example.test/yt_dlp.whl', 'digests': {'sha256': 'deadbeef00'}},  # sha256 sbagliato apposta
        ]}
        with mock.patch.object(Tools, 'checkYtDlp', return_value=None), \
             mock.patch.object(Tools, 'ytDlpStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'readFileJson', return_value=releaseWithWrongHash), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric', side_effect=fakeDownload):
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [False])
        self.assertEqual(os.listdir(self.tmp.name), [])  # niente cartelle scartate lasciate in giro

    def test_package_that_fails_to_import_is_discarded_not_installed(self):
        # zip valido ma senza __init__.py: l'estrazione riesce ma non e' un
        # pacchetto yt_dlp vero, deve essere scartato prima di essere installato
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('yt_dlp/not_the_real_thing.txt', 'oops')
        wheelBytes = buf.getvalue()
        realSha256 = hashlib.sha256(wheelBytes).hexdigest()

        def fakeDownload(url, saveAs, isStopped=None, timeout=None):
            with open(saveAs, 'wb') as f:
                f.write(wheelBytes)
            return [True, '1 KB']

        release = {'info': {'version': '2099.01.01'}, 'urls': [
            {'packagetype': 'bdist_wheel', 'filename': 'yt_dlp-2099.01.01-py3-none-any.whl',
             'url': 'https://example.test/yt_dlp.whl', 'digests': {'sha256': realSha256}},
        ]}
        with mock.patch.object(Tools, 'checkYtDlp', return_value=None), \
             mock.patch.object(Tools, 'ytDlpStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'readFileJson', return_value=release), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric', side_effect=fakeDownload):
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [False])
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_successful_end_to_end_install(self):
        # wheel "vero" (davvero importabile): copre anche
        # Tools.verifyYtDlpImportable per davvero, non mockato - checksum
        # calcolato per davvero sul contenuto scritto da fakeDownload
        wheelBytes = _buildFakeWheelBytes('2099.01.01')
        realSha256 = hashlib.sha256(wheelBytes).hexdigest()

        def fakeDownload(url, saveAs, isStopped=None, timeout=None):
            with open(saveAs, 'wb') as f:
                f.write(wheelBytes)
            return [True, '1 KB']

        release = {'info': {'version': '2099.01.01'}, 'urls': [
            {'packagetype': 'bdist_wheel', 'filename': 'yt_dlp-2099.01.01-py3-none-any.whl',
             'url': 'https://example.test/yt_dlp.whl', 'digests': {'sha256': realSha256}},
        ]}
        with mock.patch.object(Tools, 'checkYtDlp', return_value=None), \
             mock.patch.object(Tools, 'ytDlpStorageDir', return_value=self.tmp.name), \
             mock.patch.object(Tools, 'readFileJson', return_value=release), \
             mock.patch.object(Tools, 'downloadNotAsyncGeneric', side_effect=fakeDownload):
            self.installer.ensureInstalled()
        self.assertEqual(self.readyEvents, [True])
        installedInitPy = os.path.join(self.tmp.name, '2099.01.01', 'yt_dlp', '__init__.py')
        self.assertTrue(os.path.exists(installedInitPy))
        self.assertEqual(len(self.statusEvents), 1)  # un solo messaggio "in corso" mostrato all'avvio del download


class FetchLatestReleaseTest(unittest.TestCase):
    """_fetchLatestRelease(): condiviso da _doCheck() (periodico) ed
    ensureInstalled() (primo avvio) - deve trovare il wheel py3-none-any e non
    esplodere se una release non ne pubblica uno (solo sdist)."""

    def test_finds_wheel_and_version(self):
        with mock.patch.object(Tools, 'readFileJson', return_value=RELEASE_JSON):
            version, wheel = YtDlpUpdater()._fetchLatestRelease()
        self.assertEqual(version, '2099.01.01')
        self.assertTrue(wheel['filename'].endswith('-py3-none-any.whl'))

    def test_wheel_is_none_when_release_has_only_sdist(self):
        releaseSdistOnly = {'info': {'version': '2099.01.01'}, 'urls': [
            {'packagetype': 'sdist', 'filename': 'yt_dlp-2099.01.01.tar.gz',
             'url': 'https://example.test/x', 'digests': {'sha256': 'a'}},
        ]}
        with mock.patch.object(Tools, 'readFileJson', return_value=releaseSdistOnly):
            version, wheel = YtDlpUpdater()._fetchLatestRelease()
        self.assertEqual(version, '2099.01.01')
        self.assertIsNone(wheel)


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
