#!/usr/bin/python

"""
Ponte Android per tre funzionalita' lato Java (PythonActivity.java,
patchato - vedi android/patches/pythonactivity_notify.patch,
pythonactivity_foreground_service.patch e pythonactivity_openfile.patch):
niente pyjnius disponibile su questo bootstrap (vedi
android/patches/pythonactivity_permissions.patch), quindi Python non puo'
chiamare direttamente l'API Java. Soluzione, in tutti i casi: un file "a
cassetta della posta" nella cartella privata dell'app (stessa di
ANDROID_PRIVATE), scritto da Python e letto/consumato da un Handler Java in
polling periodico:

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
- open_file_request.txt: Tools.openFile (libs.py), chiamato dal doppio
  click su una riga gia' completata (Pasty.onRowDoubleClicked in main.py) -
  ci scrive il percorso assoluto del file da aprire, Java lo legge e lo apre
  con l'app predefinita del sistema (es. un player video) tramite un
  content:// URI (FileProvider, vedi
  android/patches/android_manifest_fileprovider.patch)

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
    OPEN_FILE_REQUEST_FILENAME = 'open_file_request.txt'

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

    @classmethod
    def openFile(cls, filepath):
        """Chiamato da Tools.openFile (libs.py) quando IS_ANDROID: scrive il
        percorso assoluto, PythonActivity.pollOpenFileRequest lo consuma e
        apre il file con l'app predefinita del sistema. 'w' (non 'a' come
        notify_outbox): una sola richiesta alla volta ha senso qui, una
        eventuale precedente non ancora consumata va sovrascritta, non
        accodata"""
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
