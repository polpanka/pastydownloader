#!/usr/bin/python
"""
Test per Tools._missingQuickJsFeatures / QUICKJS_REQUIRED_FEATURES (libs.py).

Il motore quickjs-ng e' bundlato staticamente nell'eseguibile (vedi
installer/*.spec e i comandi pip install in .github/workflows/*.yml e
build-appimage.sh) - a differenza di yt-dlp/yt_dlp_ejs (vedi YtDlpUpdater/
Tools.checkAndUpdateYtDlpEjs in ytdlp_updater.py/libs.py) non si aggiorna mai
da solo. Se una feature JS che lo script di risoluzione delle sfide YouTube
richiede smette di essere supportata dal motore bundlato, oggi il download
fallisce in modo silenziosamente degradato (alcuni formati mancanti, ma il
download riesce comunque - vedi Tools._registerEmbeddedQuickJsProvider), non
con un errore visibile che qualcuno per forza legge.

Questo test fa fallire la suite - non solo loggare qualcosa che nessuno
guarda - se il pacchetto 'quickjs-ng' installato nell'ambiente di sviluppo/CI
non supporta piu' le feature note per essere state richieste in passato: e'
il modo per accorgersi che va aggiornata la versione pinnata nei comandi pip
install PRIMA di pubblicare una build con un motore troppo vecchio (successe
per davvero passando dal pacchetto 'quickjs', troppo vecchio, a
'quickjs-ng' - vedi il commento esteso in Tools._registerEmbeddedQuickJsProvider).

Esecuzione: python3 -m unittest discover -s tests (richiede anche il
pacchetto 'quickjs-ng' installato, non solo le dipendenze base del programma
- se assente il test viene saltato, non e' una dipendenza obbligatoria per
eseguire il resto della suite).
"""

import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from testi import MyText

_app = QApplication.instance() or QApplication(sys.argv[:1])
_app.setApplicationName(MyText().appName)
_app.setOrganizationName(MyText().orgName)

from libs import Tools


class QuickJsRequiredFeaturesTest(unittest.TestCase):

    def setUp(self):
        try:
            import quickjs
        except ImportError:
            self.skipTest("pacchetto 'quickjs-ng' non installato in questo ambiente")
        self.quickjs = quickjs

    def test_bundled_engine_supports_all_required_features(self):
        missing = Tools._missingQuickJsFeatures(self.quickjs)
        self.assertEqual(
            missing, [],
            "Il motore quickjs-ng installato non supporta: %s - aggiornare la versione "
            "pinnata nei comandi pip install (.github/workflows/build-windows.yml, "
            "build-macos.yml, build-appimage.sh) prima di pubblicare una nuova build" % missing)


if __name__ == '__main__':
    unittest.main()
