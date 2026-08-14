#!/usr/bin/python

import os, sys, asyncio, traceback
from PySide6.QtCore import QObject, Signal, QSettings
from libs import Tools
from testi import MyText
from pasted_url import PastedUrl


class AsyncWorker(QObject):

    # generic
    finished = Signal()
    progress = Signal(str, int)
    sizeUpdate = Signal(int, str)
    settings = QSettings(MyText().orgName, MyText().appName)
    appParent = None
    gridParent = None
    rowsToDownload = []
    ffmpeg = None

    # current download
    rowId = None
    pastedUrl = None
    saveAs = None  # usato solo dalla conversione mp3 post-download (vedi runConversion)

    def __init__(self, appParent, rows, ffmpeg, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.appParent = appParent
        self.gridParent = appParent.pastyGrid
        self.rowsToDownload = rows
        self.ffmpeg = ffmpeg

    def setBothStates(self, stateText, statusCode, tooltip=''):
        self.gridParent.setCellState(self.rowId, stateText, tooltip)
        if statusCode != None:
            self.gridParent.setCellStatusCode(self.rowId, statusCode if statusCode != '' else stateText)

    def isStopped(self):
        return self.appParent.stop

    def setInDownload(self):
        self.progress.emit('type_download', self.rowId)
        self.setBothStates(self.gridParent.STATUS_CODE_DOWNLOADING, '')

    def setInConvertion(self):
        self.progress.emit('type_convert', self.rowId)
        self.setBothStates(self.gridParent.STATUS_CODE_CONVERTING, '')

    def allProcessesFinished(self):
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
            # creazione e analisi di PastedUrl
            # questo metodo gira in un threading.Thread grezzo (vedi Pasty.moveProcessInSeparatedThread),
            # un'eccezione non gestita lo farebbe morire in silenzio senza mai chiamare allProcessesFinished() sotto, lasciando l'interfaccia bloccata
            try:
                rawUrl = self.gridParent.getCellUrl(self.rowId)
                self.pastedUrl = PastedUrl(self.appParent, self.rowId, rawUrl, self.ffmpeg)
                asyncio.run(self.manageSingleUrl())
            except Exception as err:
                Tools.consoleLogs("Error: generic #0 - " + str(err))
                if Tools.isDevMode():
                    traceback.print_exc()
                self.setBothStates(self.gridParent.STATUS_CODE_ERROR, '', 'Unexpected crush #0')
        self.allProcessesFinished()

    async def manageSingleUrl(self):
        try:
            results = await self.runSingleUrl()
        except Exception as err:
            Tools.consoleLogs("Error: generic #1 - " + str(err))
            if Tools.isDevMode():
                traceback.print_exc()
            results = [self.gridParent.STATUS_CODE_ERROR, 'Unexpected crush #1']
        self.setBothStates(results[0], '', results[1])

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
            self.gridParent.setCellSaveAs(self.rowId, '')
        # result
        return result

    def onSizeProgress(self, bytesWritten):
        self.sizeUpdate.emit(self.rowId, Tools.formatSize(bytesWritten))

    async def runDownload(self):
        self.setInDownload()
        try:
            url = self.pastedUrl.getUrl()
            saveAs = self.pastedUrl.getSaveAs()
            engine = self.pastedUrl.getEngine()
            # caso generico
            if engine == PastedUrl.URL_TYPE_GENERIC:
                Tools.consoleLogs("Used: Async generic dl")
                results = await Tools.downloadAsyncGeneric(url, saveAs, self, self.onSizeProgress)
                return self.smartReturn(results)
            # caso special url / yt-dlp: yt-dlp scarica (e se serve fonde audio+video) da solo
            if engine == PastedUrl.URL_TYPE_YT_DLP:
                Tools.consoleLogs("Used: yt-dlp direct download")
                ytdlp = Tools.checkYtDlp()
                if not ytdlp:
                    return self.smartReturn([False, 'yt-dlp not available'])
                results = await Tools.downloadVideoByYtDlp(ytdlp, self.ffmpeg, url, saveAs, self.onSizeProgress, self.isStopped)
            # caso di video normale
            else:
                Tools.consoleLogs("Used: ffmpeg with default url")
                referers = self.appParent.getReferers()
                host = Tools.getHostFromUrl(url)
                referer = referers.get(host, '')
                results = await Tools.downloadVideoByFFmpeg(self.ffmpeg, url, referer, saveAs, self.onSizeProgress, self.isStopped)
            # results
            if results and results[0] == True:
                self.gridParent.setCellSaveAs(self.rowId, saveAs)
            return self.smartReturn(results)
        except Exception as err:
            Tools.consoleLogs("Error: generic #2 - " + str(err))
            if Tools.isDevMode():
                traceback.print_exc()
            return [self.gridParent.STATUS_CODE_ERROR, 'Unexpected error #2']

    async def runConversion(self, myVideo):
        self.setInConvertion()
        self.saveAs = Tools.replaceExtension(myVideo, 'mp3')
        results = await Tools.ConvertToMp3ByFFmpeg(self.ffmpeg, self.saveAs, myVideo, self.onSizeProgress, self.isStopped)
        return self.smartReturn(results)


    # altro

    def smartReturn(self, returnedData):
        success, msg = returnedData
        if success == None:
            return [self.gridParent.STATUS_CODE_STOPPED, msg]
        return [self.gridParent.STATUS_CODE_COMPLETED, msg] if success == True else [self.gridParent.STATUS_CODE_ERROR, msg]
