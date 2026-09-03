#!/usr/bin/python

import os, asyncio, traceback
from PySide6.QtCore import QObject, Signal, QSettings
from libs import Tools
from testi import MyText
from pasted_url import PastedUrl
from android_bridge import AndroidBridge


class AsyncWorker(QObject):

    # generic
    finished = Signal()
    progress = Signal(str, int)
    sizeUpdate = Signal(int, str)
    gridStateUpdate = Signal(int, str, str)   # rowId, stateText, tooltip
    gridSaveAsUpdate = Signal(int, str)       # rowId, saveAs
    settings = QSettings(MyText().orgName, MyText().appName)
    appParent = None
    gridParent = None
    rowsToDownload = []
    ffmpeg = None

    # current download
    rowId = None
    pastedUrl = None
    saveAs = None  # solo per la conversione mp3 post-download
    downloadStarted = False

    def __init__(self, appParent, rows, ffmpeg, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.appParent = appParent
        self.gridParent = appParent.pastyGrid
        self.rowsToDownload = rows
        self.ffmpeg = ffmpeg
        # connesso qui: Qt sceglie Direct/Queued in base al thread emittente
        self.gridStateUpdate.connect(self._applyGridState)
        self.gridSaveAsUpdate.connect(self._applyGridSaveAs)

    def _applyGridState(self, rowId, stateText, tooltip):
        if stateText == self.gridParent.STATUS_CODE_ERROR and not self.appParent.DEVEL_MODE:
            tooltip = ''
        self.gridParent.setCellState(rowId, stateText, tooltip)
        self.gridParent.setCellStatusCode(rowId, stateText)

    def _applyGridSaveAs(self, rowId, saveAs):
        self.gridParent.setCellSaveAs(rowId, saveAs)

    def setBothStates(self, stateText, tooltip=''):
        self.gridStateUpdate.emit(self.rowId, stateText, tooltip)

    def isStopped(self):
        return self.appParent.stop

    def setInDownload(self):
        self.progress.emit('type_download', self.rowId)
        self.setBothStates(self.gridParent.STATUS_CODE_DOWNLOADING)

    def setInConvertion(self):
        self.progress.emit('type_convert', self.rowId)
        self.setBothStates(self.gridParent.STATUS_CODE_CONVERTING)

    def allProcessesFinished(self):
        # notifiche Android chiamate qui (thread di background), non in
        # Pasty.progressFinished: su Android il ciclo eventi Qt del thread GUI
        # si ferma in background, quindi 'finished' (connessione in coda) non
        # verrebbe consegnato finche' l'utente non riapre l'app
        msg = MyText().msgDownloadFinished % Tools.getFilenameFromFullPath(Tools.downloadPath())
        AndroidBridge.notifyDownloadFinished(msg)
        AndroidBridge.stopForegroundDownload()
        self.finished.emit()

    def isToDownloadOnlyInMp4(self):
        return self.gridParent.getCellConvert(self.rowId) == self.appParent.ACTION_TO_MP4

    def isToConvertInMp3(self):
        return self.gridParent.getCellConvert(self.rowId) in [self.appParent.ACTION_TO_MP3, self.appParent.ACTION_TO_BOTH]

    def isToKeepOnlyInMp3(self):
        return self.gridParent.getCellConvert(self.rowId) == self.appParent.ACTION_TO_MP3

    """Long-running task."""
    def runAllUrls(self):
        rows = self.rowsToDownload if self.rowsToDownload else range(self.gridParent.grid.rowCount())
        for self.rowId in rows:
            if self.isStopped():
                break
            if self.gridParent.getCellState(self.rowId) != self.gridParent.STATUS_CODE_WAITING:
                continue
            # thread di background: un'eccezione non gestita salterebbe
            # allProcessesFinished() lasciando la UI bloccata
            try:
                rawUrl = self.gridParent.getCellUrl(self.rowId)
                self.pastedUrl = PastedUrl(self.appParent, self.rowId, rawUrl, self.ffmpeg)
                asyncio.run(self.manageSingleUrl())
            except Exception as err:
                Tools.consoleLogs("Error: generic #0 - " + str(err))
                if Tools.isDevMode():
                    traceback.print_exc()
                self.setBothStates(self.gridParent.STATUS_CODE_ERROR, 'Unexpected crush #0')
        self.allProcessesFinished()

    async def manageSingleUrl(self):
        try:
            results = await self.runSingleUrl()
        except Exception as err:
            Tools.consoleLogs("Error: generic #1 - " + str(err))
            if Tools.isDevMode():
                traceback.print_exc()
            results = [self.gridParent.STATUS_CODE_ERROR, 'Unexpected crush #1']
        self.setBothStates(results[0], results[1])

    async def runSingleUrl(self):
        Tools.consoleLogs("\nRunning url: " + self.pastedUrl.getUrl())
        result = [self.gridParent.STATUS_CODE_ERROR, 'Unknown error']
        # download
        isAlreadyDownloaded = self.gridParent.getCellSaveAs(self.rowId) != '' and os.path.exists(self.gridParent.getCellSaveAs(self.rowId))
        videoPath = self.gridParent.getCellSaveAs(self.rowId) if isAlreadyDownloaded else self.pastedUrl.getSaveAs()
        if self.isToDownloadOnlyInMp4() or (self.isToConvertInMp3() and not isAlreadyDownloaded):
            Tools.consoleLogs("Action: Downloading")
            result = await self.runDownload()
        # converting
        if self.isToConvertInMp3() and (result[0] == self.gridParent.STATUS_CODE_COMPLETED or isAlreadyDownloaded):
            Tools.consoleLogs("Action: Converting")
            result = await self.runConversion(videoPath)
        # deleting
        if result[0] == self.gridParent.STATUS_CODE_COMPLETED and self.isToKeepOnlyInMp3():
            Tools.consoleLogs("Action: Deleting")
            Tools.removeFile(videoPath)
            self.gridSaveAsUpdate.emit(self.rowId, '')
        # result
        return result

    def onSizeProgress(self, bytesWritten):
        if not self.downloadStarted:
            self.downloadStarted = True
            self.setInDownload()
        self.sizeUpdate.emit(self.rowId, Tools.formatSize(bytesWritten))

    def onConversionSizeProgress(self, bytesWritten):
        self.sizeUpdate.emit(self.rowId, Tools.formatSize(bytesWritten))

    async def runDownload(self):
        self.downloadStarted = False
        try:
            url = self.pastedUrl.getUrl()
            saveAs = self.pastedUrl.getSaveAs()
            engine = self.pastedUrl.getEngine()
            # caso generico
            if engine == PastedUrl.URL_TYPE_GENERIC:
                Tools.consoleLogs("Used: Async generic dl")
                results = await Tools.downloadAsyncGeneric(url, saveAs, self, self.onSizeProgress)
                return self.smartReturn(results)
            if engine == PastedUrl.URL_TYPE_YT_DLP:
                Tools.consoleLogs("Used: yt-dlp direct download")
                ytDlpPackageDir = Tools.checkYtDlp()
                if not ytDlpPackageDir:
                    return self.smartReturn([False, 'yt-dlp not available'])
                # sottotitoli nella lingua dell'app + inglese di ripiego
                appLang = MyText.getLanguage()
                subtitleLangs = [appLang] if appLang == 'en' else [appLang, 'en']
                useBrowserCookies = Tools.browserLoginConsentEnabled()
                results = await Tools.downloadVideoByYtDlp(ytDlpPackageDir, self.ffmpeg, url, saveAs, self.onSizeProgress, self.isStopped, referer=self.pastedUrl.getPastylinkReferer(), subtitleLangs=subtitleLangs, useBrowserCookies=useBrowserCookies)
            # caso di video normale
            else:
                Tools.consoleLogs("Used: ffmpeg with default url")
                referers = self.appParent.getReferers()
                host = Tools.getHostFromUrl(url)
                referer = referers.get(host, '')
                results = await Tools.downloadVideoByFFmpeg(self.ffmpeg, url, referer, saveAs, self.onSizeProgress, self.isStopped)
            # stop dell'utente ma un file utilizzabile e' gia' su disco (tipico
            # dei download lunghi / dirette): lo si aggancia alla riga - apribile,
            # eliminabile, convertibile come un download finito - pur restando
            # "Stopped" (non e' completo). Il tooltip mostra la dimensione tenuta.
            if results and results[0] is None:
                kept = self._keepUsablePartial(saveAs)
                if kept:
                    self.gridSaveAsUpdate.emit(self.rowId, kept)
                    return self.smartReturn([None, Tools.getSizeDynamic(kept)])
            # results
            if results and results[0] == True:
                self.gridSaveAsUpdate.emit(self.rowId, saveAs)
            return self.smartReturn(results)
        except Exception as err:
            Tools.consoleLogs("Error: generic #2 - " + str(err))
            if Tools.isDevMode():
                traceback.print_exc()
            return [self.gridParent.STATUS_CODE_ERROR, 'Unexpected error #2']

    def _keepUsablePartial(self, saveAs):
        """Dopo uno Stop: se il file (o il .part di yt-dlp) e' riproducibile lo
        tiene, rinominando il .part al nome definitivo. Ritorna il path tenuto o None."""
        if Tools.isPlayableMediaFile(saveAs):
            return saveAs
        partial = saveAs + '.part'
        if Tools.isPlayableMediaFile(partial):
            try:
                os.replace(partial, saveAs)
                return saveAs
            except OSError:
                return partial
        return None

    async def runConversion(self, myVideo):
        self.setInConvertion()
        audioFormat = self.settings.value('audioFormat', 'mp3')
        extension = Tools.AUDIO_FORMAT_EXTENSIONS.get(audioFormat, 'mp3')
        self.saveAs = Tools.replaceExtension(myVideo, extension)
        results = await Tools.ConvertAudioByFFmpeg(self.ffmpeg, self.saveAs, myVideo, audioFormat, self.onConversionSizeProgress, self.isStopped)
        return self.smartReturn(results)


    # altro

    def smartReturn(self, returnedData):
        success, msg = returnedData
        if success == None:
            return [self.gridParent.STATUS_CODE_STOPPED, msg]
        return [self.gridParent.STATUS_CODE_COMPLETED, msg] if success == True else [self.gridParent.STATUS_CODE_ERROR, msg]
