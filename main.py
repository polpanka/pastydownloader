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

import os, sys, time, threading
from PySide6.QtWidgets import QApplication, QMainWindow, QStatusBar, QMessageBox, QPushButton, QVBoxLayout, QWidget
from PySide6.QtCore import QSettings, QTimer, Signal
from PySide6.QtGui import QIcon
from libs import Tools
from testi import MyText
from constants import Constants
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
        layout = QVBoxLayout()
        layout.addWidget(self.button)
        layout.addWidget(self.pastyGrid.grid)
        layout.addWidget(self.statusBar)
        centralWidget = QWidget()
        centralWidget.setLayout(layout)
        self.setCentralWidget(centralWidget)

        self.initDependencies()
        self.resetUi()
        self.pastyGrid.resizeEvent(self.width())
        self.checkDownloadFolder()
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

    def checkDownloadFolder(self):
        path = Tools.downloadPath()
        if not os.path.isdir(path) or not os.access(path, os.W_OK):
            QMessageBox.critical(self, MyText.titleError, MyText.downloadPathError)
            return False
        return True

    def checkUpdates(self, forced=True):
        try:
            thisVersion = float(Constants.APP_VERSION)
            onlineVersion = float(Tools.readFileJson(MyText().checkUpdates, timeout=5)['vers'])
            isDifferentVers = (onlineVersion > thisVersion)
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
        if not Tools.isDevMode() and count:
            Tools.saveStatsUrls()
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
        if not self.stop and self.settings.value('doOpen') != 'nothing' and self.pastyGrid.hasAnyCompletedRow(thisBatchRows):
            Tools.openDownloadFolder()
        self.resetUi(msg)

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
    app = QApplication(sys.argv)
    app.setApplicationName(MyText().appName)
    app.setOrganizationName(MyText().orgName)
    app.setOrganizationDomain(MyText().orgDomain)
    if not Tools.acquireSingleInstanceLock():
        sys.exit(0)  # un'altra istanza e' gia' in esecuzione
    Constants.applyTheme(QSettings(MyText().orgName, MyText().appName).value('theme') or Constants.THEME_SYSTEM)
    window = Pasty()
    sys.exit(app.exec())
