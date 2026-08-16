#!/usr/bin/python
#https://gist.github.com/peteristhegreat/c0ca6e1a57e5d4b9cd0bb1d7b3be1d6a

from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import QSettings
from libs import Tools
from testi import MyText
from settings import SettingsDialog


class Menu():

    TYPE_STANDARD = 'standard'
    TYPE_DOWNLOADING = 'dl'
    TYPE_NO_INTERNET = 'no-internet'

    UNLOCK_CLICKS_REQUIRED = 10
    _unlockClickCount = 0

    app = None
    openAction = None
    exitAction = None
    starAction = None
    stopAction = None
    clearAction = None
    settingsAction = None
    aboutAction = None
    populateAction = None
    resetLanguageAction = None

    def initUi(self, app):
        self.app = app
        menu = app.menuBar()
        menu.setStyleSheet("border: 0px;")
        
        # File
        self.openAction = QAction(MyText().ctxOpenFolder, app)
        self.openAction.setIcon(QIcon(":/images/system-file-manager"))
        self.openAction.setShortcut('Ctrl+O')
        self.openAction.triggered.connect(lambda x: Tools().openDownloadFolder())
        self.exitAction = QAction(MyText().actionExit, app)
        self.exitAction.setIcon(QIcon(":/images/exit"))
        self.exitAction.setShortcut('Ctrl+Q')
        self.exitAction.triggered.connect(self.closeAll)
        menuFile = menu.addMenu(MyText().menuFile)
        menuFile.addAction(self.openAction)
        menuFile.addAction(self.exitAction)

        # Edit
        self.starAction = QAction(MyText().actionStartWaiting, app)
        self.starAction.setIcon(QIcon(":/images/media-playback-start"))
        self.starAction.triggered.connect(app.fetchRows)
        self.stopAction = QAction(MyText().actionStopAll, app)
        self.stopAction.setIcon(QIcon(":/images/list-remove"))
        self.stopAction.triggered.connect(app.stopAll)
        self.clearAction = QAction(MyText().actionRemoveAll, app)
        self.clearAction.setIcon(QIcon(":/images/process-stop"))
        self.clearAction.triggered.connect(app.pastyGrid.reset)
        self.settingsAction = QAction(MyText().actionPreferences, app)
        self.settingsAction.setIcon(QIcon(":/images/system-run"))
        self.settingsAction.triggered.connect(self.openSettings)
        menuEdit = menu.addMenu(MyText().menuEdit)
        menuEdit.addAction(self.starAction)
        menuEdit.addAction(self.stopAction)
        menuEdit.addAction(self.clearAction)
        menuEdit.addAction(self.settingsAction)

        # Help
        self.updatesAction = QAction(MyText().actionCheckUpdates, app)
        self.updatesAction.setIcon(QIcon(":/images/software-update-available"))
        self.updatesAction.triggered.connect(lambda x: app.checkUpdates(True))
        self.aboutAction = QAction(MyText().actionAbout, app)
        self.aboutAction.setIcon(QIcon(":/images/help-about"))
        self.aboutAction.triggered.connect(lambda x: app.openAboutPopup())
        menuHelp = menu.addMenu(MyText().menuHelp)
        menuHelp.addAction(self.updatesAction)
        menuHelp.addAction(self.aboutAction)

        # DEVEL
        if app.DEVEL_MODE:
            self.enableDevelMenu()

        # other
        self.setMenuType(self.TYPE_STANDARD)

    def _trackDevelModeUnlock(self):
        if self.app.DEVEL_MODE:
            return  # gia' sbloccato (o gia' una build di sviluppo): niente da contare
        self._unlockClickCount += 1
        if self._unlockClickCount >= self.UNLOCK_CLICKS_REQUIRED:
            self.app.enableDevelMode()
            self.enableDevelMenu()

    def enableDevelMenu(self):
        if self.populateAction is not None:
            return  # gia' presente
        self.populateAction = QAction('Populate', self.app)
        self.populateAction.triggered.connect(self.fakePopulate)
        self.resetLanguageAction = QAction('Reset language', self.app)
        self.resetLanguageAction.triggered.connect(self.resetLanguage)
        menuDEVEL = self.app.menuBar().addMenu('DEVEL')
        menuDEVEL.addAction(self.populateAction)
        menuDEVEL.addAction(self.resetLanguageAction)

    def closeAll(self):
        Tools.consoleLogs("Closing application")
        self.app.close()

    def setMenuType(self, type):
        if type == self.TYPE_STANDARD:
            self.starAction.setEnabled(True)
            self.stopAction.setEnabled(False)
            self.clearAction.setEnabled(True)
            self.settingsAction.setEnabled(True)
        elif type == self.TYPE_DOWNLOADING:
            self.starAction.setEnabled(False)
            self.stopAction.setEnabled(True)
            self.clearAction.setEnabled(False)
            self.settingsAction.setEnabled(False)
        else: # TYPE_NO_INTERNET
            self.starAction.setEnabled(False)
            self.stopAction.setEnabled(False)
            self.clearAction.setEnabled(False)
            self.settingsAction.setEnabled(False)

    def fakePopulate(self):
        add = self.app.pastyGrid.addRow
        # @todo mp4 pretende / non vuole il referer
        add('http://jucciz.com/mp3/1987s/1.mp3')                                                                                                                  # mp3
        add('https://prod.vodvideo.cbsnews.com/cbsnews/vr/hls/4685365_hls/master.m3u8')                                                                           # m3u8 audio / video diviso
        add('https://streamcdnr4-cdnraivoddom6.msvdn.net/dom6/podcastcdn/teche_root/PLAYRAI_TECHE_CINEMA_HD/11745903_,1200,1800,2400,.mp4.csmil/playlist.m3u8')   # m3u8 lungo
        add('https://ms-027.host-cdn.net/hls/llzefbb2x4hnmttc2rvmpoooq7hxqi6jetco6eod7,qslsyhpz4bmzgkywnea,3alqyhpz4bmpb4u2biq,.urlset/master.m3u8')              # m3u8 buono piccolo
        add('https://vod05.msf.cdn.mediaset.net/farmunica/2024/03/1542611_18e5c175b37d01/mp4/hd_no_mpl.mp4')                                                      # mp4 buono
        add('https://s-delivery36.mxdcontent.net/v/276b9b717172699c270cadfc1d783c8a.mp4?s=mwDENkEANjGrNswZVgT0Lw&e=1678551980&_t=1678533246')                     # mp4 scaduto
        add('https://www.cbsnews.com/video/becker-hardly-a-week-goes-by-without-trump-administration-threatening-election-official-arrests/')                     # yt-dlp
        add('https://www.youtube.com/watch?v=jNQXAC9IVRw')                                                                                                        # youtube
        add('https://www.dailymotion.com/video/x8ksj36')                                                                                                          # dailymotion
        add('https://www.instagram.com/p/CrlECZoto2O/')                                                                                                           # instagram
        add('https://www.tiktok.com/@polpanka/video/7164483565328092422')                                                                                         # tiktok
        add('https://fb.watch/kAgUGqJP-E/')                                                                                                                       # fb
        add('https://www.facebook.com/mirabilandia/videos/267787532351376/')                                                                                      # facebook
        add('https://vimeo.com/822264148')                                                                                                                        # vimeo
        add('https://ubuntu.com/engage/secure-kubernetes-at-the-edge')                                                                                            # html page
        add('https://www.bilibili.com/video/BV13x41117TL')                                                                                                        # solo con PastyDownloader (con yt-dlp) check dell'ip che scarica
        add('https://ok.ru/video/3205586750138')                                                                                                                  # solo con PastyDownloader (con yt-dlp) check dell'ip che scarica

    def resetLanguage(self):
        # QSettings vuoto: al prossimo avvio MyText.getLanguage() la ridetecta
        # dal sistema operativo invece di leggere una lingua scelta in precedenza
        QSettings(MyText.orgName, MyText.appName).remove('language')
        Tools.consoleLogs("Language reset - restart the app to redetect it from the OS")

    def openSettings(self):
        Tools.consoleLogs("Opening settings dialog")
        dlg = SettingsDialog(self.app)
        isSaved = dlg.exec()
        if isSaved:
            self.app.pastyGrid.updateIsToConvert()
        return isSaved
    