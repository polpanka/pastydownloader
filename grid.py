#!/usr/bin/python

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QTableView, QAbstractItemView, QMenu
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QIcon
from libs import Tools
from testi import MyText
from constants import Constants

class PastyGrid():

    TYPE_FULL = 'full'
    TYPE_MINIMAL = 'minimal'
    TYPE_NO_INTERNET = 'no-internet'

    grid = None
    settings = QSettings(MyText().orgName, MyText().appName)

    # const
    STATUS_CODE_COMPLETED   = Constants.STATUS_CODE_COMPLETED
    STATUS_CODE_ERROR       = Constants.STATUS_CODE_ERROR
    STATUS_CODE_WAITING     = Constants.STATUS_CODE_WAITING
    STATUS_CODE_DOWNLOADING = Constants.STATUS_CODE_DOWNLOADING
    STATUS_CODE_STOPPED     = Constants.STATUS_CODE_STOPPED
    STATUS_CODE_CONVERTING  = Constants.STATUS_CODE_CONVERTING
    COLUMNS_TABLE           = None

    # context menu
    contextMenu = None
    actionCopy = None
    actionOpen = None
    actionRedownload = None
    actionStopRow = None
    actionClearRow = None
    actionDestroyBoth = None

    def initColumns(self, devel_mode):
        self.COLUMNS_TABLE = [
            {'name': MyText().colUrl,        'width':80 if not devel_mode else 40, 'visible':True  },
            {'name': MyText().colState,      'width':20 if not devel_mode else 10, 'visible':True  },
            {'name': MyText().colStatusCode, 'width': 0 if not devel_mode else 10, 'visible':False if not devel_mode else True },
            {'name': MyText().colSaveAs,     'width': 0 if not devel_mode else 30, 'visible':False if not devel_mode else True },
            {'name': MyText().colActions,    'width': 0 if not devel_mode else 10, 'visible':False if not devel_mode else True },
        ]
        self.grid.setColumnCount(len(self.COLUMNS_TABLE)) # servono tutte anche le nascoste
        self.grid.setHorizontalHeaderLabels([item['name'] for item in self.COLUMNS_TABLE])
        self.setHiddenColumns()

    def initUi(self):
        self.grid = QTableWidget()
        self.grid.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.grid.verticalHeader().setVisible(True)
        self.grid.setEditTriggers(QTableView.NoEditTriggers)
        self.grid.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.grid.setContextMenuPolicy(Qt.CustomContextMenu)
        self.grid.setShowGrid(False)
        self.grid.setWordWrap(False) # x win
        self.grid.setAlternatingRowColors(True)
        self.grid.setStyleSheet(Constants.getGridStyle())
        self.reset()
    
    def initContextMenu(self, callback):
        self.contextMenu = QMenu(self.grid)
        self.actionCopy = self.contextMenu.addAction(MyText().ctxCopyLink)
        self.actionCopy.setIcon(QIcon(":/images/edit-copy"))
        self.actionCopy.setShortcut('Ctrl+C')
        self.actionOpen = self.contextMenu.addAction(MyText().ctxOpenFolder)
        self.actionOpen.setIcon(QIcon(":/images/system-file-manager"))
        self.actionRedownload = self.contextMenu.addAction(MyText().ctxDownloadNow)
        self.actionRedownload.setIcon(QIcon(":/images/emblem-downloads"))
        self.actionConvert = self.contextMenu.addAction(MyText().ctxConvertMp3)
        self.actionConvert.setIcon(QIcon(":/images/mediaplayer-app"))
        self.contextMenu.addSeparator()
        self.actionStopRow = self.contextMenu.addAction(MyText().ctxStop)
        self.actionStopRow.setIcon(QIcon(":/images/list-remove"))
        self.actionClearRow = self.contextMenu.addAction(MyText().ctxRemove)
        self.actionClearRow.setIcon(QIcon(":/images/process-stop"))
        self.actionDestroyBoth = self.contextMenu.addAction(MyText().ctxDeleteAndRemove)
        self.actionDestroyBoth.setIcon(QIcon(":/images/edit-delete"))
        self.grid.customContextMenuRequested.connect(callback)

    def setContextMenuType(self, type):
        if type == self.TYPE_MINIMAL:
            self.actionRedownload.setEnabled(False)
            self.actionConvert.setEnabled(False)
            self.actionStopRow.setEnabled(True)
            self.actionClearRow.setEnabled(False)
            self.actionDestroyBoth.setEnabled(False)
        elif type == self.TYPE_NO_INTERNET:
            self.actionRedownload.setEnabled(False)
            self.actionConvert.setEnabled(False)
            self.actionStopRow.setEnabled(False)
            self.actionClearRow.setEnabled(True)
            self.actionDestroyBoth.setEnabled(True)
        else: # TYPE_FULL
            self.actionRedownload.setEnabled(True)
            self.actionConvert.setEnabled(True)
            self.actionStopRow.setEnabled(False)
            self.actionClearRow.setEnabled(True)
            self.actionDestroyBoth.setEnabled(True)

    def reset(self):
        while self.grid.rowCount() > 0:
            self.removeRow(0)
        self.grid.setRowCount(0)
    
    def removeRow(self, rowId):
        self.grid.removeRow(rowId)
    
    def setHiddenColumns(self):
        for i, visible in enumerate([item['visible'] for item in self.COLUMNS_TABLE]):
            if not visible:
                self.grid.setColumnHidden(i, True)

    def getCell(self, rowId, colId):
        return self.grid.item(rowId, colId).text()
    
    def setCell(self, rowId, colId, value, tooltip=''):
        try:
            item = QTableWidgetItem(value)
            item.setToolTip(tooltip)
            self.grid.setItem(rowId, colId, item)
            self.grid.viewport().update() # fix x Win
        except Exception:
            print('Error in setting cell')
    
    def getCellUrl(self, rowId):
        return self.getCell(rowId, 0)

    def getCellState(self, rowId):
        return self.getCell(rowId, 1)
    
    def getCellStatusCode(self, rowId):
        return self.getCell(rowId, 2)
    
    def getCellSaveAs(self, rowId):
        return self.getCell(rowId, 3)
    
    def getCellConvert(self, rowId):
        return self.getCell(rowId, 4)

    def setCellUrl(self, rowId, value):
        self.setCell(rowId, 0, value)

    def setCellState(self, rowId, value, tooltip=''):
        self.setCell(rowId, 1, value, tooltip)
    
    def setCellStatusCode(self, rowId, value):
        self.setCell(rowId, 2, value)

    def setCellSaveAs(self, rowId, value):
        self.setCell(rowId, 3, value)
    
    def setCellConvert(self, rowId, value):
        self.setCell(rowId, 4, value)

    def setStoppedAllWaitingUrls(self):
        if self.grid.rowCount() > 0:
            for rowId in range(self.grid.rowCount()):
                if self.getCellStatusCode(rowId) == self.STATUS_CODE_WAITING:
                    self.setCellState(rowId, self.STATUS_CODE_STOPPED)
                    self.setCellStatusCode(rowId, self.STATUS_CODE_STOPPED)
        
    def resizeEvent(self, totalWidth):
        for i, percentage in enumerate([item['width'] for item in self.COLUMNS_TABLE]):
            self.grid.setColumnWidth(i, int(totalWidth * percentage / 100))

    def importUrls(self, urls):
        count = 0
        hasInvalidPastylink = False
        for url in urls:
            url = url.strip()
            isManifestText = Tools.isM3u8ManifestText(url)
            isPastylink = Tools.isPastylinkUrl(url)
            if isPastylink and not Tools.decodePastylinkUrl(url):
                hasInvalidPastylink = True
                continue
            if url \
                and (url.startswith('http') or url.startswith('rtmp') or url.startswith('rtsp') or isManifestText or isPastylink) \
                and url not in self.getAllUrlsInTable() \
                and (isManifestText or isPastylink or Tools.uriValidator(url)):
                count += 1
                self.addRow(url)
        return count, hasInvalidPastylink

    def addRow(self, url):
        newRow = self.grid.rowCount()
        self.grid.insertRow(newRow)
        self.setCellUrl(newRow, url)
        self.setCellState(newRow, self.STATUS_CODE_WAITING)
        self.setCellStatusCode(newRow, self.STATUS_CODE_WAITING)
        self.setCellSaveAs(newRow, '')
        self.setCellConvert(newRow, self.settings.value('ytConversion'))

    def getAllUrlsInTable(self):
        return [self.getCellUrl(rowId) for rowId in range(self.grid.rowCount())]
    
    def getAllWaitingUrlsInTable(self):
        return [self.getCellUrl(rowId) for rowId in range(self.grid.rowCount()) if self.getCellStatusCode(rowId) == self.STATUS_CODE_WAITING ]

    def hasAnyCompletedRow(self, rows=None):
        rowIds = rows if rows is not None else range(self.grid.rowCount())
        return any(self.getCellStatusCode(rowId) == self.STATUS_CODE_COMPLETED for rowId in rowIds)

    def updateIsToConvert(self):
        if self.grid.rowCount() > 0:
            for rowId in range(self.grid.rowCount()):
                self.setCellConvert(rowId, self.settings.value('ytConversion'))
