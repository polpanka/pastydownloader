#!/usr/bin/python

"""
Ponte Python->Java su Android: niente pyjnius su questo bootstrap, quindi si
comunica scrivendo file "cassetta della posta" nella cartella privata
(ANDROID_PRIVATE), che un Handler Java legge in polling.

- notify_outbox.txt: notifica di sistema di fine batch (solo se in background)
- download_active.txt: la sua esistenza dice a Java se il Foreground Service
  (anti-freeze) va attivo; il contenuto e' il testo della notifica persistente
- open_file_request.txt: percorso del file da aprire con l'app di sistema
- incoming_url.txt: link httpasty:// aperto da un browser (deep link) - qui
  e' Java che scrive e Python che legge in polling (verso opposto agli altri)
"""

import os
import logging
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from constants import Constants


class AndroidBridge:

    NOTIFY_OUTBOX_FILENAME = 'notify_outbox.txt'
    DOWNLOAD_ACTIVE_FILENAME = 'download_active.txt'
    OPEN_FILE_REQUEST_FILENAME = 'open_file_request.txt'
    INCOMING_URL_FILENAME = 'incoming_url.txt'

    @staticmethod
    def _privateDir():
        # ANDROID_PRIVATE = getFilesDir(): unico posto scrivibile da entrambi i lati
        return os.environ.get('ANDROID_PRIVATE')

    @classmethod
    def _pathFor(cls, filename):
        privateDir = cls._privateDir()
        return os.path.join(privateDir, filename) if privateDir else None

    @classmethod
    def notifyDownloadFinished(cls, message):
        """Fine batch: scrive la notifica solo se l'app e' in background."""
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

    @classmethod
    def startForegroundDownload(cls, message):
        """Inizio batch: scritto sempre, il Foreground Service deve essere gia'
        attivo quando l'utente esce dall'app."""
        if not Constants.IS_ANDROID:
            return
        path = cls._pathFor(cls.DOWNLOAD_ACTIVE_FILENAME)
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(message)
        except OSError as err:
            logging.error('AndroidBridge: error writing download_active flag: ' + str(err))

    @classmethod
    def stopForegroundDownload(cls):
        """Fine batch (comunque vada): cancellare il file ferma il Foreground Service."""
        if not Constants.IS_ANDROID:
            return
        path = cls._pathFor(cls.DOWNLOAD_ACTIVE_FILENAME)
        if not path:
            return
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError as err:
            logging.error('AndroidBridge: error removing download_active flag: ' + str(err))

    @classmethod
    def pollIncomingUrl(cls):
        """Deep link httpasty://: Java scrive l'URI dell'intent VIEW qui
        (rename atomico), Python lo consuma. Ritorna l'url una volta sola."""
        if not Constants.IS_ANDROID:
            return None
        path = cls._pathFor(cls.INCOMING_URL_FILENAME)
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, encoding='utf-8') as f:
                url = f.read().strip()
        except OSError as err:
            logging.error('AndroidBridge: error reading incoming url: ' + str(err))
            url = None
        try:
            os.remove(path)
        except OSError:
            pass
        return url or None

    @classmethod
    def openFile(cls, filepath):
        """Scrive il percorso; Java lo apre con l'app di sistema. 'w': una
        richiesta alla volta, la precedente non consumata si sovrascrive."""
        if not Constants.IS_ANDROID:
            return
        path = cls._pathFor(cls.OPEN_FILE_REQUEST_FILENAME)
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(filepath)
        except OSError as err:
            logging.error('AndroidBridge: error writing open file request: ' + str(err))
