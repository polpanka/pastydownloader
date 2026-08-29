#!/usr/bin/python

"""
Ponte Android per due funzionalita' lato Java (PythonActivity.java,
patchato - vedi android/patches/pythonactivity_notify.patch e
pythonactivity_foreground_service.patch): niente pyjnius disponibile su
questo bootstrap (vedi android/patches/pythonactivity_permissions.patch),
quindi Python non puo' chiamare direttamente l'API Java. Soluzione, in
entrambi i casi: un file "a cassetta della posta" nella cartella privata
dell'app (stessa di ANDROID_PRIVATE), scritto da Python e letto/consumato
da un Handler Java in polling periodico:

- notify_outbox.txt: Pasty.progressFinished (main.py) ci scrive quando un
  batch finisce mentre l'app e' in background - Java legge, mostra la
  notifica di sistema e cancella il file.
- download_active.txt: Pasty.fetchRows/progressFinished (main.py) lo
  scrivono/cancellano quando un batch inizia/finisce - la sua sola
  esistenza dice a Java se avviare o fermare il Foreground Service (vedi
  DownloadForegroundService.java e ANDROID_HISTORY.md), che tiene il
  processo esente dal freeze che Android applica alle app in background.
  Il contenuto del file (un messaggio gia' tradotto) e' quello che
  Java mostra nella notifica persistente, letto direttamente dal servizio

NB: qui viveva anche il menu "Condividi" di sistema (link condivisi da
altre app) - funzionalita' rimossa di proposito: il flusso di download
deve partire sempre e solo da un incolla manuale/da pasty.link, mai da un
link intercettato navigando su un'altra app (rischio di download non
voluti, es. da siti come Rai). Vedi ANDROID_HISTORY.md.
"""

import os
import logging
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from constants import Constants


class AndroidBridge:

    NOTIFY_OUTBOX_FILENAME = 'notify_outbox.txt'
    DOWNLOAD_ACTIVE_FILENAME = 'download_active.txt'

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

    @classmethod
    def startForegroundDownload(cls, message):
        """Chiamato da Pasty.fetchRows (main.py) appena parte un batch:
        a differenza di notifyDownloadFinished, va scritto sempre (non solo
        se l'app e' in background) - il Foreground Service deve gia' essere
        attivo nel momento in cui l'utente esce dall'app, non solo dopo
        essere gia' uscito (altrimenti il processo rischia comunque il
        freeze nella finestra fra l'uscita e il prossimo poll Java)"""
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
        """Chiamato da Pasty.progressFinished (main.py) a ogni fine batch
        (successo, errore o Stop - gira comunque): cancellare il file e'
        il segnale che dice a Java di fermare il Foreground Service"""
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
