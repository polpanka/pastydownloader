#!/usr/bin/python
"""
Test per MyText.getLanguage()/setLanguage() (testi.py): al primo avvio (nessuna
lingua mai scelta in QSettings) la lingua deve essere rilevata dal sistema
operativo se supportata, e quella scelta va salvata subito - cosi' non viene
ridetectata a ogni avvio, e un'eventuale scelta manuale successiva (Preferenze)
la sovrascrive normalmente.

Usa un org/app name dedicato per QSettings, per non toccare le impostazioni
vere dell'utente che lancia i test.

Esecuzione: python3 -m unittest discover -s tests (stesse dipendenze del programma).
"""

import os
import sys
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv[:1])

import testi
from testi import MyText


class LanguageDetectionTest(unittest.TestCase):

    def setUp(self):
        # MyText.orgName/appName sono attributi di classe condivisi da tutto il
        # processo di test: usarne una coppia dedicata (e ripristinare quella
        # vera alla fine) evita di toccare le QSettings reali dell'utente E di
        # far bleedare questo cambiamento sugli altri file di test
        originalOrgName, originalAppName = MyText.orgName, MyText.appName
        self.addCleanup(setattr, MyText, 'orgName', originalOrgName)
        self.addCleanup(setattr, MyText, 'appName', originalAppName)
        MyText.orgName = 'PastylinkTests'
        MyText.appName = 'PastyDownloaderTests'
        self.settings = QSettings(MyText.orgName, MyText.appName)
        self.settings.clear()
        self.addCleanup(self.settings.clear)

    def _fakeSystemLocale(self, localeName):
        fakeLocale = mock.Mock()
        fakeLocale.name.return_value = localeName
        return mock.patch.object(testi.QLocale, 'system', return_value=fakeLocale)

    def test_first_run_uses_the_system_locale_when_supported(self):
        with self._fakeSystemLocale('it_IT'):
            self.assertEqual(MyText.getLanguage(), 'it')

    def test_first_run_falls_back_to_default_when_system_locale_is_not_supported(self):
        with self._fakeSystemLocale('pl_PL'):
            self.assertEqual(MyText.getLanguage(), MyText.DEFAULT_LANGUAGE)

    def test_first_run_detection_is_persisted_so_it_is_not_redetected_next_time(self):
        with self._fakeSystemLocale('de_DE'):
            self.assertEqual(MyText.getLanguage(), 'de')
        # una seconda chiamata, anche con un'altra lingua di sistema "finta",
        # deve ignorarla: ormai la lingua e' quella salvata al primo avvio
        with self._fakeSystemLocale('fr_FR'):
            self.assertEqual(MyText.getLanguage(), 'de')

    def test_explicit_choice_overrides_and_persists_over_the_detected_one(self):
        with self._fakeSystemLocale('it_IT'):
            MyText.getLanguage()  # simula il primo avvio: rileva e salva 'it'
        MyText.setLanguage('fr')
        self.assertEqual(MyText.getLanguage(), 'fr')


if __name__ == '__main__':
    unittest.main()
