#!/usr/bin/python

"""
Istanza singola + consegna di un url httpasty:// dalla seconda istanza alla
prima (click su un link nel browser mentre l'app e' gia' aperta).

QLockFile (Tools.acquireSingleInstanceLock) fa da guardia anti-race sul
doppio avvio rapido; QLocalServer/QLocalSocket portano l'url dalla seconda
istanza alla prima. Su macOS il canale non serve (l'url arriva come
QFileOpenEvent al processo gia' vivo). Su Android non serve affatto: non c'e'
un secondo processo da coordinare, e QtNetwork non e' nemmeno bundlato
(pysidedeploy.spec: modules = Core,Gui,Widgets) - da qui gli import ritardati.
"""

from PySide6.QtCore import QObject, Signal

from libs import Tools
from testi import MyText
from constants import Constants


class SingleInstance(QObject):

    urlReceived = Signal(str)

    _TIMEOUT_MS = 1000

    def __init__(self, parent=None, serverName=None):
        super().__init__(parent)
        self.serverName = serverName or (MyText().appName + '-ipc')
        self._server = None

    # True  = siamo la prima istanza, proseguire l'avvio normale.
    # False = un'altra istanza risponde gia': pendingUrl le e' stato inoltrato,
    #         il chiamante deve uscire.
    def tryBecomePrimary(self, pendingUrl=None):
        if not Tools.acquireSingleInstanceLock():
            self.sendToPrimary(pendingUrl or '')
            return False
        if not Constants.IS_ANDROID:
            self.startServer()
        return True

    def startServer(self):
        from PySide6.QtNetwork import QLocalServer
        QLocalServer.removeServer(self.serverName)  # socket orfano di un crash precedente
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._onNewConnection)
        self._server.listen(self.serverName)

    def sendToPrimary(self, payload):
        if Constants.IS_ANDROID:
            return False
        from PySide6.QtNetwork import QLocalSocket
        socket = QLocalSocket()
        socket.connectToServer(self.serverName)
        if not socket.waitForConnected(self._TIMEOUT_MS):
            return False
        socket.write((payload or '').encode('utf-8'))
        socket.waitForBytesWritten(self._TIMEOUT_MS)
        socket.disconnectFromServer()
        return True

    def _onNewConnection(self):
        from PySide6.QtNetwork import QLocalSocket
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        chunks = bytearray()
        while socket.state() == QLocalSocket.ConnectedState or socket.bytesAvailable():
            if not socket.bytesAvailable() and not socket.waitForReadyRead(self._TIMEOUT_MS):
                break
            chunks += bytes(socket.readAll())
        payload = chunks.decode('utf-8', 'replace').strip()
        if payload.startswith(Tools.PASTYLINK_URL_PREFIX):
            self.urlReceived.emit(payload)
