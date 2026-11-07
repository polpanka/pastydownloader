#!/usr/bin/python
"""Test offline di Tools.hasYtDlpExtractor e del suo uso in PastedUrl._analyze."""

import os
import re
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from testi import MyText

_app = QApplication.instance() or QApplication(sys.argv[:1])
_app.setApplicationName(MyText().appName)
_app.setOrganizationName(MyText().orgName)

from libs import Tools
from pasted_url import PastedUrl


def fakeExtractor(key, pattern, working=True):
    return type(key + 'IE', (), {
        'ie_key': classmethod(lambda cls: key),
        'working': classmethod(lambda cls: working),
        'suitable': classmethod(lambda cls, url: re.match(pattern, url) is not None)})


FAKE_YTDLP = SimpleNamespace(extractor=SimpleNamespace(gen_extractor_classes=lambda: [
    fakeExtractor('Youtube', r'https?://(?:www\.)?youtube\.com/watch'),
    fakeExtractor('Generic', r'.*'),
    fakeExtractor('KnownDRM', r'https?://(?:www\.)?hulu\.com/'),
    fakeExtractor('Broken', r'https?://broken\.example/', working=False),
]))


class HasYtDlpExtractorTest(unittest.TestCase):
    def match(self, url, ytdlp=FAKE_YTDLP, packageDir='/fake'):
        with mock.patch.object(Tools, 'checkYtDlp', return_value=packageDir), \
             mock.patch.object(Tools, '_importYtDlp', return_value=ytdlp):
            return Tools.hasYtDlpExtractor(url)

    def test_known_site_matches(self):
        self.assertTrue(self.match('https://www.youtube.com/watch?v=abc'))

    def test_generic_is_ignored(self):
        self.assertFalse(self.match('https://example.com/page'))

    def test_known_drm_is_ignored(self):
        self.assertFalse(self.match('https://www.hulu.com/watch/abc'))

    def test_non_working_extractor_is_ignored(self):
        self.assertFalse(self.match('https://broken.example/x'))

    def test_false_when_ytdlp_not_installed(self):
        self.assertFalse(self.match('https://www.youtube.com/watch?v=abc', packageDir=None))

    def test_false_when_import_fails(self):
        self.assertFalse(self.match('https://www.youtube.com/watch?v=abc', ytdlp=None))

    def test_exception_does_not_propagate(self):
        broken = SimpleNamespace(extractor=SimpleNamespace(gen_extractor_classes=mock.Mock(side_effect=RuntimeError('x'))))
        self.assertFalse(self.match('https://www.youtube.com/watch?v=abc', ytdlp=broken))


class AnalyzeUsesExtractorMatchTest(unittest.TestCase):
    URL = 'https://site.example/watch/1'

    def analyze(self, contentType, extractorMatch, realVideo=False, probe=False):
        with mock.patch.object(PastedUrl, '_getContentTypeFromUrl', return_value=contentType), \
             mock.patch.object(Tools, 'hasYtDlpExtractor', return_value=extractorMatch) as has, \
             mock.patch.object(PastedUrl, '_isRealVideoOnline', return_value=realVideo) as ffmpeg, \
             mock.patch.object(Tools, 'isYtDlpDownloadable', return_value=probe) as probeMock:
            pasted = PastedUrl(mock.Mock(), 0, self.URL, 'ffmpeg')
        return pasted, has, ffmpeg, probeMock

    def test_known_site_goes_to_ytdlp_without_network_probes(self):
        pasted, has, ffmpeg, probe = self.analyze('text/html', True)
        self.assertEqual(pasted.getEngine(), PastedUrl.URL_TYPE_YT_DLP)
        ffmpeg.assert_not_called()
        probe.assert_not_called()

    def test_missing_content_type_is_treated_like_html(self):
        pasted, has, ffmpeg, probe = self.analyze(None, True)
        self.assertEqual(pasted.getEngine(), PastedUrl.URL_TYPE_YT_DLP)
        probe.assert_not_called()

    def test_unknown_site_still_uses_ffmpeg_then_probe(self):
        pasted, has, ffmpeg, probe = self.analyze('text/html', False, probe=True)
        self.assertEqual(pasted.getEngine(), PastedUrl.URL_TYPE_YT_DLP)
        ffmpeg.assert_called_once()
        probe.assert_called_once()

    def test_unknown_site_with_real_video_goes_to_ffmpeg(self):
        pasted, has, ffmpeg, probe = self.analyze('text/html', False, realVideo=True)
        self.assertEqual(pasted.getEngine(), PastedUrl.URL_TYPE_VIDEO)
        probe.assert_not_called()

    def test_direct_media_never_asks_the_extractors(self):
        pasted, has, ffmpeg, probe = self.analyze('video/mp4', True)
        self.assertEqual(pasted.getEngine(), PastedUrl.URL_TYPE_VIDEO)
        has.assert_not_called()

    def test_non_media_content_type_stays_generic(self):
        pasted, has, ffmpeg, probe = self.analyze('application/pdf', True)
        self.assertEqual(pasted.getEngine(), PastedUrl.URL_TYPE_GENERIC)
        has.assert_not_called()


if __name__ == '__main__':
    unittest.main()
