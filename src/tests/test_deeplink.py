#!/usr/bin/python
"""
Deep link httpasty:// (scheme handler del SO): quando un url httpasty:// arriva
dal browser, l'app lo aggiunge in griglia, porta la finestra in primo piano e
scarica subito se nulla e' in corso - altrimenti accoda.

- Tools.pastylinkArgFromArgv: estrae l'url dagli argomenti del processo
- Pasty.importExternalUrl: aggiunta riga + stato + download subito o in coda
- Pasty._downloadWaitingRows: scarica le righe in attesa (fine batch / UI sbloccata)
- AndroidBridge.pollIncomingUrl: canale Java->Python del deep link su Android
- SingleInstance: la seconda istanza inoltra l'url alla prima via QLocalSocket

Esecuzione:
    python3 -m unittest discover -s tests
"""

import base64
import json
import os
import sys
import unittest
from unittest import mock
from urllib.parse import quote

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
from testi import MyText

_app = QApplication.instance() or QApplication(sys.argv[:1])
_app.setApplicationName(MyText().appName)
_app.setOrganizationName(MyText().orgName)

import main
from grid import PastyGrid
from libs import Tools
from single_instance import SingleInstance


YOUTUBE_URL = 'https://www.youtube.com/watch?v=jNQXAC9IVRw'


def makePastylinkUrl(realUrl):
    payload = {'v1': {'ytdlp': realUrl}}
    encoded = base64.b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    return Tools.PASTYLINK_URL_PREFIX + encoded


def makeGrid():
    grid = PastyGrid()
    grid.initUi()
    grid.initColumns(True)
    return grid


def pumpEvents(times=5):
    for _ in range(times):
        QCoreApplication.processEvents()


class ArgvExtractionTest(unittest.TestCase):

    def test_no_url_returns_none(self):
        self.assertIsNone(Tools.pastylinkArgFromArgv(['main.py']))
        self.assertIsNone(Tools.pastylinkArgFromArgv(['main.py', '--debug', 'foo']))

    def test_url_in_any_position_is_found(self):
        url = makePastylinkUrl(YOUTUBE_URL)
        self.assertEqual(Tools.pastylinkArgFromArgv(['main.py', url]), url)
        self.assertEqual(Tools.pastylinkArgFromArgv(['main.py', '--flag', url]), url)

    def test_argv0_is_never_taken(self):
        self.assertIsNone(Tools.pastylinkArgFromArgv(['httpasty://argv0-non-conta']))


class PercentEncodedPayloadTest(unittest.TestCase):
    """Da <a href="httpasty://..."> il browser percent-encoda il blob prima di
    passarlo allo scheme handler ('+' -> '%2B', '/' -> '%2F'): il decoder deve
    fare unquote e decodificare comunque."""

    def test_blob_with_slash_or_plus_gets_quoted_and_still_decodes(self):
        # base64 con separatori compatti: contiene '/' e/o '+' che il browser
        # trasforma in %2F / %2B
        raw = json.dumps({'v1': {'ytdlp': 'https://example.com/video/10?t=abc'}}, separators=(',', ':'))
        payload = base64.b64encode(raw.encode()).decode().rstrip('=')
        self.assertTrue('/' in payload or '+' in payload)
        quoted = Tools.PASTYLINK_URL_PREFIX + quote(payload, safe='')
        self.assertIn('%2', quoted)
        self.assertEqual(Tools.decodePastylinkUrl(quoted), 'https://example.com/video/10?t=abc')

    def test_aggressively_quoted_blob_still_decodes(self):
        # alcuni browser percent-encodano anche caratteri "safe": simuliamolo
        blob = makePastylinkUrl(YOUTUBE_URL)
        payload = blob[len(Tools.PASTYLINK_URL_PREFIX):]
        quoted = Tools.PASTYLINK_URL_PREFIX + ''.join('%%%02X' % ord(c) for c in payload)
        self.assertEqual(Tools.decodePastylinkUrl(quoted), YOUTUBE_URL)

    def test_plain_blob_is_unaffected(self):
        blob = makePastylinkUrl(YOUTUBE_URL)
        self.assertEqual(Tools.decodePastylinkUrl(blob), YOUTUBE_URL)


class _FakeApp:
    """Minimo indispensabile per Pasty.importExternalUrl / _downloadWaitingRows."""

    def __init__(self, grid, uiUnlocked=True, isRunning=False):
        self.pastyGrid = grid
        self._uiUnlocked = uiUnlocked
        self.is_running = isRunning
        self.lastStatus = None
        self.raised = 0
        self.fetchCalls = 0

    def _raiseWindow(self):
        self.raised += 1

    def setStatusBar(self, txt, sec=0):
        self.lastStatus = txt

    def isUiUnlocked(self):
        return self._uiUnlocked

    def fetchRows(self, rows=None, showNoLinksMessage=True):
        self.fetchCalls += 1

    def importExternalUrl(self, url):
        return main.Pasty.importExternalUrl(self, url)

    def _downloadWaitingRows(self):
        return main.Pasty._downloadWaitingRows(self)


class ImportExternalUrlTest(unittest.TestCase):

    def test_valid_url_idle_and_unlocked_adds_row_raises_and_downloads(self):
        app = _FakeApp(makeGrid(), uiUnlocked=True, isRunning=False)
        app.importExternalUrl(makePastylinkUrl(YOUTUBE_URL))
        pumpEvents()  # fetchRows differito via QTimer.singleShot(0)
        self.assertEqual(len(app.pastyGrid.getAllUrlsInTable()), 1)
        self.assertEqual(app.raised, 1)
        self.assertEqual(app.fetchCalls, 1)
        self.assertEqual(app.lastStatus, MyText().msgFoundLinks % 1)

    def test_valid_url_while_batch_running_is_queued_not_downloaded(self):
        app = _FakeApp(makeGrid(), uiUnlocked=True, isRunning=True)
        app.importExternalUrl(makePastylinkUrl(YOUTUBE_URL))
        pumpEvents()
        self.assertEqual(len(app.pastyGrid.getAllUrlsInTable()), 1)  # riga in attesa
        self.assertEqual(app.fetchCalls, 0)

    def test_valid_url_while_ui_locked_is_queued_not_downloaded(self):
        app = _FakeApp(makeGrid(), uiUnlocked=False, isRunning=False)
        app.importExternalUrl(makePastylinkUrl(YOUTUBE_URL))
        pumpEvents()
        self.assertEqual(len(app.pastyGrid.getAllUrlsInTable()), 1)
        self.assertEqual(app.fetchCalls, 0)

    def test_invalid_pastylink_is_rejected_with_status_and_no_row(self):
        app = _FakeApp(makeGrid())
        app.importExternalUrl('httpasty://payload-corrotto!!!')
        pumpEvents()
        self.assertEqual(app.pastyGrid.getAllUrlsInTable(), [])
        self.assertEqual(app.lastStatus, MyText().msgInvalidPastylink)
        self.assertEqual(app.fetchCalls, 0)

    def test_empty_url_only_raises_the_window(self):
        app = _FakeApp(makeGrid())
        app.importExternalUrl('')
        pumpEvents()
        self.assertEqual(app.raised, 1)
        self.assertEqual(app.fetchCalls, 0)


class DownloadWaitingRowsTest(unittest.TestCase):

    def _appWithWaitingRow(self, **kw):
        grid = makeGrid()
        grid.addRow(makePastylinkUrl(YOUTUBE_URL))  # entra come STATUS_CODE_WAITING
        return _FakeApp(grid, **kw)

    def test_fetch_when_idle_and_unlocked_with_waiting_rows(self):
        app = self._appWithWaitingRow(uiUnlocked=True, isRunning=False)
        app._downloadWaitingRows()
        pumpEvents()  # QTimer.singleShot(0, ...)
        self.assertEqual(app.fetchCalls, 1)

    def test_no_fetch_while_still_running(self):
        app = self._appWithWaitingRow(uiUnlocked=True, isRunning=True)
        app._downloadWaitingRows()
        pumpEvents()
        self.assertEqual(app.fetchCalls, 0)

    def test_no_fetch_while_ui_locked(self):
        app = self._appWithWaitingRow(uiUnlocked=False, isRunning=False)
        app._downloadWaitingRows()
        pumpEvents()
        self.assertEqual(app.fetchCalls, 0)

    def test_no_fetch_without_waiting_rows(self):
        app = _FakeApp(makeGrid(), uiUnlocked=True, isRunning=False)  # griglia vuota
        app._downloadWaitingRows()
        pumpEvents()
        self.assertEqual(app.fetchCalls, 0)


class SingleInstanceIpcTest(unittest.TestCase):
    """La seconda istanza inoltra l'url alla prima via QLocalSocket; la prima
    lo emette come signal. Nome server dedicato per non collidere col vero."""

    SERVER = 'PastyDownloader-test-ipc'

    def setUp(self):
        self.primary = SingleInstance(serverName=self.SERVER)
        self.primary.startServer()
        self.received = []
        self.primary.urlReceived.connect(self.received.append)

    def tearDown(self):
        if self.primary._server:
            self.primary._server.close()

    def test_pastylink_payload_is_forwarded_and_emitted(self):
        url = makePastylinkUrl(YOUTUBE_URL)
        sender = SingleInstance(serverName=self.SERVER)
        self.assertTrue(sender.sendToPrimary(url))
        pumpEvents(10)
        self.assertEqual(self.received, [url])

    def test_non_pastylink_payload_is_ignored(self):
        sender = SingleInstance(serverName=self.SERVER)
        sender.sendToPrimary('https://example.com/not-a-deeplink')
        pumpEvents(10)
        self.assertEqual(self.received, [])

    def test_empty_payload_is_ignored(self):
        sender = SingleInstance(serverName=self.SERVER)
        sender.sendToPrimary('')
        pumpEvents(10)
        self.assertEqual(self.received, [])


class SingleInstanceAndroidTest(unittest.TestCase):
    """Su Android QtNetwork non e' bundlato (pysidedeploy.spec) e non c'e' una
    seconda istanza: SingleInstance non deve toccare QLocalServer/QLocalSocket."""

    def test_send_to_primary_is_a_noop_without_qtnetwork(self):
        from constants import Constants
        with mock.patch.object(Constants, 'IS_ANDROID', True):
            si = SingleInstance(serverName='PastyDownloader-android-test')
            self.assertFalse(si.sendToPrimary(makePastylinkUrl(YOUTUBE_URL)))


class AndroidIncomingUrlTest(unittest.TestCase):
    """Android: Java (PythonActivity.handleDeepLinkIntent) scrive incoming_url.txt,
    AndroidBridge.pollIncomingUrl lo consuma una volta sola."""

    def setUp(self):
        import tempfile, shutil
        from constants import Constants
        self.Constants = Constants
        self.dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.dir, ignore_errors=True))
        for patcher in (mock.patch.dict(os.environ, {'ANDROID_PRIVATE': self.dir}),
                        mock.patch.object(Constants, 'IS_ANDROID', True)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _write(self, text):
        with open(os.path.join(self.dir, 'incoming_url.txt'), 'w', encoding='utf-8') as f:
            f.write(text)

    def test_no_file_returns_none(self):
        from android_bridge import AndroidBridge
        self.assertIsNone(AndroidBridge.pollIncomingUrl())

    def test_file_is_read_then_consumed(self):
        from android_bridge import AndroidBridge
        url = makePastylinkUrl(YOUTUBE_URL)
        self._write(url + '\n')
        self.assertEqual(AndroidBridge.pollIncomingUrl(), url)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'incoming_url.txt')))  # consumato
        self.assertIsNone(AndroidBridge.pollIncomingUrl())  # niente da leggere due volte

    def test_not_android_returns_none_even_with_file(self):
        from android_bridge import AndroidBridge
        self._write('httpasty://x')
        with mock.patch.object(self.Constants, 'IS_ANDROID', False):
            self.assertIsNone(AndroidBridge.pollIncomingUrl())


if __name__ == '__main__':
    unittest.main()
