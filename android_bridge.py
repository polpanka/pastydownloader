#!/usr/bin/python

"""
Ponte Android per la notifica di sistema a fine download (vedi
PythonActivity.java, patchato - android/patches/pythonactivity_notify.patch):
niente pyjnius disponibile su questo bootstrap (vedi
android/patches/pythonactivity_permissions.patch), quindi Python non puo'
chiamare direttamente l'API Java per mostrare la notifica. Soluzione: un file
"a cassetta della posta" nella cartella privata dell'app (stessa di
ANDROID_PRIVATE) - Pasty.progressFinished (main.py) ci scrive quando un
batch finisce mentre l'app e' in background, un Handler Java in polling
periodico lo legge, mostra la notifica di sistema e cancella il file.

NB: qui vivevano anche il menu "Condividi" di sistema e l'importazione di
link condivisi da altre app - funzionalita' rimossa di proposito: il flusso
di download deve partire sempre e solo da un incolla manuale/da pasty.link,
mai da un link intercettato navigando su un'altra app (rischio di download
non voluti, es. da siti come Rai). Vedi ANDROID_HISTORY.md.
"""

import os
import logging
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from constants import Constants


class AndroidBridge:

    NOTIFY_OUTBOX_FILENAME = 'notify_outbox.txt'

    @staticmethod
    def _privateDir():
        # stessa cartella di ANDROID_PRIVATE (vedi PythonActivity.java,
        # mFilesDirectory = getFilesDir()) - unico posto scrivibile da
        # entrambi i lati senza permessi extra
        return os.environ.get('ANDROID_PRIVATE')

    @classmethod
    def _pathFor(cls, filename):
        privateDir = cls._privateDir()
        return os.path.join(privateDir, filename) if privateDir else None

    @classmethod
    def notifyDownloadFinished(cls, message):
        """Chiamato da Pasty.progressFinished (main.py) a ogni fine batch:
        scrive la notifica solo se l'app non e' in primo piano (se e'
        visibile l'utente vede gia' tutto nella griglia/status bar, una
        notifica di sistema sarebbe ridondante)."""
        if not Constants.IS_ANDROID:
            return
        if QGuiApplication.applicationState() == Qt.ApplicationActive:
            return
        path = cls._pathFor(cls.NOTIFY_OUTBOX_FILENAME)
        if not path:
            return
        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(message + '\n')
        except OSError as err:
            logging.error('AndroidBridge: error writing notify outbox: ' + str(err))
