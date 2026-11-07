#!/usr/bin/python
"""Test offline di Tools.downloadAsyncGeneric (requests in thread, niente aiohttp)."""

import asyncio
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


class FakeResponse:
    def __init__(self, chunks, contentType='video/mp4', status=200):
        self.chunks = chunks
        self.headers = {'Content-Type': contentType}
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError('HTTP %d' % self.status)

    def iter_content(self, chunk_size=8192):
        yield from self.chunks


class FakeParent:
    def __init__(self, stopped=False):
        self.stopped = stopped

    def isStopped(self):
        return self.stopped


class GenericDownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.saveAs = os.path.join(self.tmp.name, 'f.bin')

    def run_(self, response, parent=None, onProgress=None):
        with mock.patch('requests.get', return_value=response) as get:
            result = asyncio.run(Tools.downloadAsyncGeneric('https://example.test/f', self.saveAs, parent, onProgress))
        return result, get

    def test_saves_file_reports_progress_and_avoids_brotli(self):
        seen = []
        result, get = self.run_(FakeResponse([b'abc', b'defg']), onProgress=seen.append)
        self.assertTrue(result[0], result)
        with open(self.saveAs, 'rb') as f:
            self.assertEqual(f.read(), b'abcdefg')
        self.assertEqual(seen[0], 3)  # primo chunk sempre notificato, poi throttle
        self.assertEqual(get.call_args.kwargs['headers'], {'Accept-Encoding': 'gzip, deflate'})
        self.assertEqual(get.call_args.kwargs['timeout'], (10, 30))  # niente attesa infinita se il server tace

    def test_html_is_rejected_without_writing_file(self):
        result, _ = self.run_(FakeResponse([b'<html>'], contentType='text/html; charset=utf-8'))
        self.assertFalse(result[0])
        self.assertFalse(os.path.exists(self.saveAs))

    def test_http_error_is_a_failure(self):
        result, _ = self.run_(FakeResponse([b'x'], status=404))
        self.assertFalse(result[0])

    def test_user_stop_returns_none(self):
        result, _ = self.run_(FakeResponse([b'abc', b'def']), parent=FakeParent(stopped=True))
        self.assertIsNone(result[0])


if __name__ == '__main__':
    unittest.main()
