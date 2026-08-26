#!/usr/bin/python

"""
PastyDownloader - Pastylink App

Author: Paolo Pancaldi
Website: pasty.link

Funzionalita':
- Incolla dagli appunti:
   . URL (anche multipli)
   . playlist #EXTM3U
- Rileva il tipo di sorgente e sceglie il motore giusto per il download:
   . generico (aiohttp)
   . yt-dlp (YouTube / Dailymotion / Instagram / TikTok / ...)
   . video diretto via ffmpeg
- Avanzamento download
- Conversione in mp3 dopo il download (mai / converti + elimina video / converti + mantieni)
- Stop di un singolo download o di tutti quelli in attesa
- Menù contestuale (copia link, ri-scarica, converti, stop...)
- Controllo connessione a internet e verifica aggiornamenti all'avvio
"""

import os, sys, time, threading, multiprocessing

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QStatusBar, QMessageBox, QPushButton, QToolButton, QVBoxLayout, QHBoxLayout, QWidget, QDialog, QLabel, QDialogButtonBox
    from PySide6.QtCore import QSettings, QTimer, Signal, Qt
    from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor
except ImportError:
    # Nessun toolkit grafico disponibile (tipicamente OS troppo vecchio per i
    # binari bundlati) - niente QMessageBox possibile qui, serve un dialogo
    # nativo del SO; se anche quello non e' disponibile va bene il solo
    # stderr, l'app comunque non puo' partire
    _startup_error_msg = (
        "PastyDownloader failed to start because a required system component "
        "could not be loaded.\n\nThis usually happens when your operating "
        "system is too old. Please update it and try again, or get in touch "
        "at pasty.link if the problem persists."
    )
    if sys.platform == "darwin":
        import subprocess
        # PySide6 e' pinnato alla 6.7.3 in build-macos.yml (wheel universal2,
        # stesso floor macOS 11 "Big Sur" per arm64 e x86_64 - non serve piu'
        # distinguere per architettura come prima di quel pin) - se il pin
        # cambia, aggiornare anche questo messaggio. Va scritta qui a mano
        # (non letta da un file condiviso) perche' a questo punto PySide6
        # potrebbe non essere importabile, quindi neanche moduli del progetto
        # che lo importano a loro volta
        _startup_error_msg = _startup_error_msg.replace(
            "system is too old.",
            "system is too old (this version of PastyDownloader requires macOS 11 Big Sur or later).",
        )
        # niente "\n" nel testo: un ritorno a capo letterale dentro la
        # stringa passata a -e rischia di rompere il parsing dell'AppleScript
        _mac_msg = _startup_error_msg.replace("\n\n", " ")
        subprocess.run(
            ["osascript", "-e",
             f'display dialog "{_mac_msg}" with title "PastyDownloader" '
             f'buttons {{"OK"}} default button "OK" with icon caution'],
            check=False,
        )
    elif sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, _startup_error_msg, "PastyDownloader", 0x10)
    else:
        import shutil, subprocess
        if shutil.which("zenity"):
            subprocess.run(["zenity", "--error", "--title=PastyDownloader", f"--text={_startup_error_msg}"], check=False)
        elif shutil.which("kdialog"):
            subprocess.run(["kdialog", "--error", _startup_error_msg, "--title", "PastyDownloader"], check=False)
    print(_startup_error_msg, file=sys.stderr)
    sys.exit(1)

from libs import Tools
from testi import MyText
from constants import Constants

if Constants.IS_ANDROID:
    # il Python cross-compilato per Android non ha un bundle di certificati
    # CA configurato: ogni richiesta HTTPS (aiohttp/requests) fallisce con
    # SSLCertVerificationError finche' SSL_CERT_FILE non punta a uno valido -
    # certifi lo fornisce pronto (vedi ANDROID.md). Deve girare prima di
    # qualunque uso di ssl/aiohttp/requests, quindi qui, al primo import
    import certifi
    os.environ.setdefault('SSL_CERT_FILE', certifi.where())

from grid import PastyGrid
from worker import AsyncWorker
from ytdlp_updater import YtDlpUpdater
from ffmpeg_installer import FfmpegInstaller
from status_queue import StatusQueue
from toolbar import Menu
import resources # x le images

# x evitare che Win mostri la app pyhton nella systray
# https://www.pythonguis.com/tutorials/packaging-pyqt5-pyside2-applications-windows-pyinstaller/
try:
    from ctypes import windll  # Only exists on Windows.
    myappid = 'link.pasty'
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass



class Pasty(QMainWindow):

    connectivityChecked = Signal(bool)

    VERSION = Tools.getVersion()
    DEVEL_MODE = Tools.isDevMode()

    appName = MyText().appName
    menu = None
    button = None
    pastyGrid = PastyGrid()
    asyncExec = None
    statusBar = None
    referers = None
    is_running = False
    isOnline = True
    dependenciesReady = False
    time_start_download = None
    stop = False
    settings = QSettings(MyText().orgName, MyText().appName)

    ACTION_TO_MP3  = 'mp3'
    ACTION_TO_MP4  = 'mp4'
    ACTION_TO_BOTH = 'both'

    def __init__(self):
        super().__init__()
        Tools.consoleLogs("App starting - version " + str(self.VERSION))
        self.initUI()
        self.show()

    def initUI(self):
        # info
        tools = Tools()
        texts = MyText()
        self.setWindowTitle(self.appName)
        self.setWindowIcon(QIcon(texts.pasty_favicon)) # x Win
        width = 800 if not self.settings.value('width') else int(self.settings.value('width'))
        height = 400 if not self.settings.value('height') else int(self.settings.value('height'))
        self.resize(width, height)
        self.centerScreen()
        
        # menu
        self.menu = Menu()
        self.menu.initUi(self)

        # button
        self.button = QPushButton(MyText().btnDefault)
        self.button.setShortcut('Ctrl+V')
        self.button.clicked.connect(self.startAll)
        self.button.setMinimumHeight(60)

        # grid
        self.pastyGrid.initUi()
        self.pastyGrid.initColumns(self.DEVEL_MODE)
        self.pastyGrid.initContextMenu(self.onContextMenu)
        self.pastyGrid.actionCopy.triggered.connect(self.copyCurrentRowLink)
        self.pastyGrid.grid.cellDoubleClicked.connect(self.onRowDoubleClicked)

        # statusbar
        self.statusBar = QStatusBar()
        self.statusQueue = StatusQueue(self.statusBar)

        # setting layout
        topRow = QHBoxLayout()
        topRow.addWidget(self.button)
        if Constants.IS_ANDROID:
            # QMenuBar non ha modo di essere raggiunto su Android (era
            # pensato per il vecchio tasto hardware "Menu", rimosso da anni -
            # vedi Menu.buildPopupMenu in toolbar.py): pulsante extra che
            # apre le stesse azioni gia' esistenti come popup
            self.menuButton = QToolButton()
            # niente carattere Unicode '☰': il font disponibile su Android
            # non lo copre sempre (glifo "rotto"/invisibile) - disegnata a
            # mano cosi' non dipende da nessun font
            self.menuButton.setIcon(self._buildHamburgerIcon())
            self.menuButton.setMinimumHeight(60)
            self.menuButton.setStyleSheet("QToolButton { padding: 0 16px; }")
            self.menuButton.clicked.connect(self.openMenuPopup)
            topRow.addWidget(self.menuButton)
        layout = QVBoxLayout()
        layout.addLayout(topRow)
        layout.addWidget(self.pastyGrid.grid)
        layout.addWidget(self.statusBar)
        centralWidget = QWidget()
        centralWidget.setLayout(layout)
        self.setCentralWidget(centralWidget)

        self.initDependencies()
        self.resetUi()
        self.pastyGrid.resizeEvent(self.width())
        # Niente check qui all'avvio (ne' su Android ne' su desktop): su
        # Android il popup di sistema per WRITE_EXTERNAL_STORAGE e'
        # asincrono (PythonActivity.onCreate lo richiede e non aspetta la
        # risposta), quindi appena l'app parte il permesso e' spesso ancora
        # "non deciso" - indistinguibile da "negato" lato Python (os.access)
        # prima che l'utente risponda, causerebbe un popup d'errore spurio a
        # ogni avvio pulito. Comportamento uniformato su tutte le
        # piattaforme: l'unico check resta quello in fetchRows() prima di
        # ogni download (popup + non parte nulla, nessuna chiusura forzata -
        # l'utente puo' sistemare il problema, es. concedere il permesso o
        # cambiare il path nelle settings, e ritentare senza riavviare).
        self.initConnectivityCheck()
        # deferred so the window shows up immediately, without waiting on the network
        QTimer.singleShot(0, lambda: self.checkUpdates(False))

    def initConnectivityCheck(self):
        # controllo eseguito una sola volta all'avvio
        self.connectivityChecked.connect(self.onConnectivityChecked)
        self.checkInternetConnection()

    def checkInternetConnection(self):
        threading.Thread(target=self._checkInternetConnectionInBackground, daemon=True).start()

    def _checkInternetConnectionInBackground(self):
        self.connectivityChecked.emit(Tools.hasInternetConnection())

    def onConnectivityChecked(self, isConnected):
        wasUnlocked = self.isUiUnlocked()
        self.isOnline = isConnected
        if self.is_running:
            return # non toccare la UI mentre un batch e' gia' in corso
        self._updateLockState(wasUnlocked)
        if not isConnected:
            self.setStatusBar(MyText().internetError, 0)

    def isUiUnlocked(self):
        return self.isOnline and self.dependenciesReady

    def _refreshLockState(self):
        self.button.setEnabled(self.isUiUnlocked())
        self.menu.setMenuType(Menu.TYPE_STANDARD if self.isUiUnlocked() else Menu.TYPE_NO_INTERNET)
        self.pastyGrid.setContextMenuType(PastyGrid.TYPE_FULL if self.isUiUnlocked() else PastyGrid.TYPE_NO_INTERNET)

    def _updateLockState(self, wasUnlocked):
        # da chiamare dopo aver aggiornato isOnline/dependenciesReady
        self._refreshLockState()
        if not wasUnlocked and self.isUiUnlocked():
            self.statusQueue.showNow(MyText().setupCompleteMsg, 5)

    # ffmpeg e yt-dlp si scaricano in cascata, mai in parallelo: prima ffmpeg,
    # poi (solo se riuscito) yt-dlp - vedi onFfmpegReady/onYtDlpReady
    def initDependencies(self):
        self.ffmpegInstaller = FfmpegInstaller()
        self.ffmpegInstaller.statusMessage.connect(self.setStatusBar)
        self.ffmpegInstaller.ready.connect(self.onFfmpegReady)
        self.ytDlpUpdater = YtDlpUpdater()
        self.ytDlpUpdater.statusMessage.connect(self.setStatusBar)
        self.ytDlpUpdater.statusMessageNow.connect(self.statusQueue.showNow)
        self.ytDlpUpdater.ready.connect(self.onYtDlpReady)
        if Constants.IS_ANDROID:
            self.dependenciesReady = bool(Tools.checkYtDlp())
            if self.dependenciesReady:
                self.startYtDlpPeriodicUpdates()
            else:
                threading.Thread(target=self.ytDlpUpdater.ensureInstalled, daemon=True).start()
            return
        self.dependenciesReady = bool(Tools.checkFFmpeg()) and bool(Tools.checkYtDlp())
        if self.dependenciesReady:
            self.startYtDlpPeriodicUpdates()
        else:
            threading.Thread(target=self.ffmpegInstaller.ensureInstalled, daemon=True).start()

    def enableDevelMode(self):
        if self.DEVEL_MODE:
            return
        self.DEVEL_MODE = True
        self.pastyGrid.initColumns(True)
        self.pastyGrid.resizeEvent(self.width())
        self.setStatusBar('DEVEL_MODE enabled', 5)

    def onFfmpegReady(self, success):
        if not success:
            self.showInstallFailedPopup()
            return
        threading.Thread(target=self.ytDlpUpdater.ensureInstalled, daemon=True).start()

    def onYtDlpReady(self, success):
        if not success:
            self.showInstallFailedPopup()
            return
        wasUnlocked = self.isUiUnlocked()
        self.dependenciesReady = True
        self._updateLockState(wasUnlocked)
        self.startYtDlpPeriodicUpdates()

    def showInstallFailedPopup(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(MyText.titleError)
        box.setText(MyText().installFailedMsg)
        box.addButton(MyText().btnClose, QMessageBox.AcceptRole)
        box.exec()
        self.close()  # is_running e' sempre False qui: chiude senza chiedere conferma (vedi closeEvent)

    def startYtDlpPeriodicUpdates(self):
        # Su Android non c'e' un aggiornamento periodico in background: non e'
        # essenziale (yt-dlp resta comunque installato/verificato una volta
        # sola al primo avvio, vedi YtDlpUpdater.ensureInstalled - una
        # versione un po' vecchia degrada, non rompe l'app) e toglie di mezzo
        # un thread di verifica in piu' che potrebbe girare in concomitanza
        # con classificazione/download gia' in corso, condividendo
        # sys.modules con loro (vedi ANDROID_HISTORY.md punto 12 - il fix li'
        # regge comunque anche con questo attivo, ma senza e' piu' semplice)
        if Constants.IS_ANDROID:
            return
        # staggered after the app-version check, so it doesn't compete for
        # the same startup network burst
        QTimer.singleShot(5000, self.checkYtDlpUpdate)
        self.ytDlpUpdaterTimer = QTimer(self)
        self.ytDlpUpdaterTimer.timeout.connect(self.checkYtDlpUpdate)
        self.ytDlpUpdaterTimer.start(YtDlpUpdater.CHECK_INTERVAL_HOURS * 3600 * 1000)

    def checkYtDlpUpdate(self):
        threading.Thread(target=self.ytDlpUpdater.checkAndUpdate, daemon=True).start()

    def waitingUi(self):
        self.is_running = True
        self.button.setEnabled(False)
        self.button.setText(MyText().btnReverse)
        self.button.setIcon(QIcon(MyText().pasty_icon_rev))
        self.menu.setMenuType(Menu.TYPE_DOWNLOADING)
        self.pastyGrid.setContextMenuType(PastyGrid.TYPE_MINIMAL)

    def resetUi(self, msg=None):
        # msg=None: non tocca la barra di stato (lascia il messaggio gia'
        # eventualmente impostato da chi ha chiamato resetUi, es. pasteUrls())
        self.is_running = False
        self._refreshLockState()
        self.button.setText(MyText().btnDefault)
        self.button.setIcon(QIcon(MyText().pasty_icon))
        if msg is not None:
            # showNow(), non setStatusBar()/add(): un batch appena finito
            # lascia quasi sempre un messaggio persistente "Riga N in
            # corso..." (vedi progressInCorso). Con clear()+add() questo
            # messaggio finale rischierebbe di accodarsi dietro un evento
            # eventualmente promosso dal clear() (es. un "Contenuto copiato"
            # rimasto in attesa durante il batch) invece di essere mostrato
            # subito (vedi StatusQueue.showNow)
            self.statusQueue.showNow(msg, 5)
        self.stop = False
    
    def _buildHamburgerIcon(self):
        # sia Constants.isDarkTheme() (bianco/nero indovinato) sia
        # QPalette.ButtonText letto dal bottone si sono rivelati inaffidabili
        # su Android (icona rimasta bianca anche col tema light, illeggibile
        # - lo stile nativo non sembra seguire la palette per questo widget).
        # Fix indipendente da qualunque rilevazione di tema: ogni riga
        # disegnata due volte, un contorno nero spesso sotto e uno bianco
        # piu' sottile sopra - resta visibile su qualunque sfondo
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        outline = QPen(QColor(Constants.COLOR_BLACK))
        outline.setWidth(5)
        fill = QPen(QColor(Constants.COLOR_WHITE))
        fill.setWidth(3)
        for pen in (outline, fill):
            painter.setPen(pen)
            for y in (8, 16, 24):
                painter.drawLine(4, y, 28, y)
        painter.end()
        return QIcon(pixmap)

    def openMenuPopup(self):
        popup = self.menu.buildPopupMenu()
        popup.exec(self.menuButton.mapToGlobal(self.menuButton.rect().bottomRight()))

    def centerScreen(self):
        qr = self.frameGeometry()
        cp = QApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
    
    def resizeEvent(self, event):
        self.settings.setValue('width', event.size().width())
        self.settings.setValue('height', event.size().height())
        self.pastyGrid.resizeEvent(self.width())
    
    def openPopup(self, title, msg):
        QMessageBox.about(self, title, msg)

    # popup About dedicato
    def openAboutPopup(self):
        dialog = QDialog(self)
        # senza, lo sfondo del dialogo resta trasparente su Android e si
        # mimetizza con quello che c'e' sotto (es. la griglia) - i widget
        # normali non riempiono da soli lo sfondo con la palette a meno di
        # chiederglielo esplicitamente
        dialog.setAutoFillBackground(True)
        dialog.setWindowTitle(MyText().actionAbout)

        iconLabel = QLabel()
        iconLabel.setPixmap(QIcon(MyText().pasty_favicon).pixmap(64, 64))
        iconLabel.mousePressEvent = lambda event: self.menu._trackDevelModeUnlock()

        textLabel = QLabel('<b>Pastylink</b><br><br>' + (MyText().aboutVersion % self.VERSION) + '<br>' + MyText().aboutWebsite + '<br>')
        textLabel.setTextFormat(Qt.RichText)
        textLabel.setOpenExternalLinks(True)

        contentRow = QHBoxLayout()
        contentRow.addWidget(iconLabel, 0, Qt.AlignTop)
        contentRow.addWidget(textLabel, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)

        layout = QVBoxLayout()
        layout.addLayout(contentRow)
        layout.addWidget(buttons)

        dialog.setLayout(layout)
        dialog.exec()

    def checkDownloadFolder(self):
        path = Tools.downloadPath()
        if not os.path.isdir(path) or not os.access(path, os.W_OK):
            QMessageBox.critical(self, MyText.titleError, MyText.downloadPathError)
            return False
        return True

    def checkUpdates(self, forced=True):
        try:
            thisVersion = Constants.APP_VERSION
            onlineVersion = Tools.readFileJson(MyText().checkUpdates, timeout=5)['vers']
            isDifferentVers = Tools.isNewerVersion(onlineVersion, thisVersion)
            if forced:
                msg = MyText().txtUpdatesHtml % onlineVersion if isDifferentVers else MyText().txtUpdatesNo
                self.openPopup(MyText().titleUpdates, msg)
            elif isDifferentVers:
                self.setStatusBar(MyText().txtUpdatesTxt % onlineVersion, 10)
        except Exception:
            if forced:
                self.setStatusBar(MyText().txtUpdatesError, 5)
    
    def onContextMenu(self, event):
        if self.pastyGrid.grid.rowCount() == 0:
            return
        # recupero info
        action = self.pastyGrid.contextMenu.exec(self.pastyGrid.grid.mapToGlobal(event))
        item = self.pastyGrid.grid.itemAt(event) # self.pastyGrid.grid.currentRow() | self.pastyGrid.grid.currentIndex()
        if item is None:
            return
        rowId = item.row()
        Tools.consoleLogs("Context menu action '%s' on row %s" % (action.text() if action else 'none', rowId))
        # ACTIONS
        # copy
        if action == self.pastyGrid.actionCopy:
            url = self.pastyGrid.getCellUrl(rowId)
            Tools.copyToClipboard(url)
            self.setStatusBar(MyText().msgContentCopied, 2)
        # open
        elif action == self.pastyGrid.actionOpen:
            Tools.openDownloadFolder()
        # re-download
        elif action == self.pastyGrid.actionRedownload:
            self.pastyGrid.setCellConvert(rowId, self.ACTION_TO_MP4)
            self.fetchRow(rowId)
        # actionConvert
        elif action == self.pastyGrid.actionConvert:
            self.pastyGrid.setCellConvert(rowId, self.ACTION_TO_BOTH)
            self.fetchRow(rowId)
        # stop
        elif action == self.pastyGrid.actionStopRow:
            self.stop = True
        # clear row
        elif action == self.pastyGrid.actionClearRow:
            self.pastyGrid.removeRow(rowId)
        # destroy both
        elif action == self.pastyGrid.actionDestroyBoth:
            myfile = self.pastyGrid.getCellSaveAs(rowId)
            if myfile:
                Tools.removeFile(myfile)
            self.pastyGrid.removeRow(rowId)
        else:
            Tools.consoleLogs("Action non gestita")

    def copyCurrentRowLink(self):
        rowId = self.pastyGrid.grid.currentRow()
        if rowId < 0:
            return
        url = self.pastyGrid.getCellUrl(rowId)
        Tools.copyToClipboard(url)
        self.setStatusBar(MyText().msgContentCopied, 2)

    def startAll(self):
        Tools.consoleLogs("User action: paste and download")
        self.pasteUrls()
        # pasteUrls() ha gia' spiegato l'esito nella barra di stato (link
        # trovati, nessun link valido, pastylink invalido): fetchRows() non
        # deve sovrascriverlo con "nessun link in attesa" se non trova nulla
        self.fetchRows(showNoLinksMessage=False)
    
    def getReferers(self):
        if self.referers is None:
            try:
                self.referers = Tools.readFileJson(MyText().referers)
            except Exception as err:
                Tools.consoleLogs("Impossibile scaricare referer.json: " + str(err))
                self.referers = {}
        return self.referers

    def stopAll(self):
        self.pastyGrid.setStoppedAllWaitingUrls()
        self.stop = True

    def pasteUrls(self):
        # EXTM3U: il testo intero e' un solo "link" da aggiungere cosi' com'e'
        pasted = Tools.stripBom(Tools.pasteFromClipboard())
        tokens = [pasted] if Tools.isM3u8ManifestText(pasted) else pasted.split()
        count, hasInvalidPastylink = self.pastyGrid.importUrls(tokens)
        Tools.consoleLogs("Pasted %s urls, %s valid" % (len(tokens), count))
        if hasInvalidPastylink:
            statusMsg = MyText().msgInvalidPastylink
        elif count:
            statusMsg = MyText().msgFoundLinks % count
        else:
            statusMsg = MyText().msgNoValidLinks
        self.setStatusBar(statusMsg, 5)

    def fetchRow(self, rowId):
        if not self.is_running:
            self.pastyGrid.setCellState(rowId, self.pastyGrid.STATUS_CODE_WAITING)
            self.pastyGrid.setCellStatusCode(rowId, self.pastyGrid.STATUS_CODE_WAITING)
            self.fetchRows([rowId])

    def onRowDoubleClicked(self, rowId, column):
        self.fetchRow(rowId)

    def fetchRows(self, rows=None, showNoLinksMessage=True):
        self.waitingUi()
        if not self.pastyGrid.getAllWaitingUrlsInTable():
            self.resetUi(MyText().noLinks if showNoLinksMessage else None)
            return False
        if not self.isOnline:
            self.resetUi()
            self.setStatusBar(MyText().internetError, 0) # persistente, non a scomparsa: resta offline finche' non torna la connessione
            return False
        ffmpeg = Tools.checkFFmpeg()
        if not ffmpeg:
            self.resetUi()
            self.showInstallFailedPopup()
            return False
        if not self.checkDownloadFolder():
            self.resetUi()
            return False
        try:
            # move process in separated thread
            Tools.consoleLogs("Starting download thread for rows: " + str(rows))
            self.setStatusBar(MyText().msgDownloadStarted)
            self.time_start_download = time.time()
            self.moveProcessInSeparatedThread([rows, ffmpeg])
        except Exception as err:
            Tools.consoleLogs("Error #1 unexpected: " + str(err))
            self.resetUi()
    
    def moveProcessInSeparatedThread(self, asyncParams):
        self.asyncExec = AsyncWorker(self, *asyncParams)
        self.asyncExec.progress.connect(self.progressInCorso)
        self.asyncExec.sizeUpdate.connect(self.updateRowSize)
        self.asyncExec.finished.connect(self.progressFinished)
        self.thread = threading.Thread(target=self.asyncExec.runAllUrls, daemon=True)
        self.thread.start()

    def setStatusBar(self, txt, sec=0):
        self.statusQueue.add(txt, sec)

    def progressInCorso(self, type, rowId):
        action = MyText().typeDownload if type == 'type_download' else MyText().typeConversion
        self.setStatusBar(action + MyText().msgInProgress % str(rowId+1))

    def updateRowSize(self, rowId, sizeText):
        self.pastyGrid.setCellState(rowId, sizeText)

    def progressFinished(self):
        msg = MyText().msgDownloadFinished % round(time.time() - self.time_start_download)
        Tools.consoleLogs(msg)
        # solo le righe di QUESTO batch, non l'intera griglia: altrimenti un ri-download singolo fallito potrebbe aprire comunque la cartella
        thisBatchRows = self.asyncExec.rowsToDownload if self.asyncExec.rowsToDownload else range(self.pastyGrid.grid.rowCount())
        # su Android l'opzione e' disabilitata in Preferenze (vedi
        # SettingsDialog.addForm3) perche' Tools.openFolder non fa nulla li',
        # ma un valore 'open' salvato prima di questa modifica potrebbe
        # essere ancora in QSettings - ignorato esplicitamente anche qui
        if not Constants.IS_ANDROID and not self.stop and self.settings.value('doOpen') != 'nothing' and self.pastyGrid.hasAnyCompletedRow(thisBatchRows):
            Tools.openDownloadFolder()
        self.resetUi(msg)
        if Constants.IS_ANDROID:
            # sulla barra di stato il messaggio finale sparisce dopo pochi secondi
            QMessageBox.information(self, self.appName, msg)

    def closeEvent(self, event):
        if not self.is_running:
            event.accept()
            return
        reply = QMessageBox.question(self, MyText.confirmExitTitle, MyText.confirmExitMsg,
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            event.ignore()
            return
        Tools.consoleLogs("Exit confirmed with download in progress - stopping it")
        self.stopAll()
        thread = getattr(self, 'thread', None)
        if thread and thread.is_alive():
            thread.join(timeout=5)
        event.accept()


if __name__ == '__main__':
    # deve essere la primissima cosa eseguita sotto __main__: ogni download
    # yt-dlp gira in un processo figlio 'spawn' (vedi Tools._runYtDlpInProcess),
    # che sotto un eseguibile PyInstaller frozen rilancerebbe da capo l'intera
    # app (QApplication compresa, in un ciclo) invece di eseguire solo il
    # worker richiesto, se freeze_support() non intercetta prima la richiesta
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    app.setApplicationName(MyText().appName)
    app.setOrganizationName(MyText().orgName)
    app.setOrganizationDomain(MyText().orgDomain)
    if not Tools.acquireSingleInstanceLock():
        sys.exit(0)  # un'altra istanza e' gia' in esecuzione
    Constants.applyTheme(QSettings(MyText().orgName, MyText().appName).value('theme') or Constants.THEME_SYSTEM)
    Constants.applyAndroidFontScale()
    Constants.applyAndroidDarkPalette()
    Constants.onThemeChange(Constants.applyAndroidDarkPalette)
    window = Pasty()
    sys.exit(app.exec())
