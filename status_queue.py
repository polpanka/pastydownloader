#!/usr/bin/python

from PySide6.QtCore import QObject, QTimer


class StatusQueue(QObject):
    """Coda FIFO per i messaggi della barra di stato, per non farli
    sovrascrivere a vicenda da fonti concorrenti.

    - secondi > 0: evento a tempo, entra in coda FIFO, non interrompe mai
      cio' che e' in mostra
    - secondi <= 0: stato persistente, sostituisce subito la barra e ci resta
      fino alla prossima add()/clear()
    - clear(): rimuove lo stato persistente e fa ripartire la coda
    - showNow(): mostra subito saltando la coda, senza toccarne gli eventi in
      attesa (usare per un messaggio conclusivo - clear()+add() NON equivale)
    """

    def __init__(self, statusBar):
        super().__init__()
        self.statusBar = statusBar
        self.queue = []  # eventi in attesa: (testo, secondi>0)
        self.current = None  # (testo, secondi) mostrato, None se barra vuota
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._advance)

    def add(self, text, seconds=0):
        if seconds <= 0:
            self.showNow(text, seconds)
            return
        self.queue.append((text, seconds))
        if self.current is None:
            self._advance()

    def clear(self):
        self.timer.stop()
        self.current = None
        self._advance()

    def showNow(self, text, seconds=0):
        self.timer.stop()
        self.current = (text, seconds)
        self.statusBar.showMessage(text)
        if seconds > 0:
            self.timer.start(seconds * 1000)  # allo scadere la coda riprende da _advance()

    def _advance(self):
        if not self.queue:
            self.current = None
            self.statusBar.clearMessage()
            return
        text, seconds = self.queue.pop(0)
        self.current = (text, seconds)
        self.statusBar.showMessage(text)
        self.timer.start(seconds * 1000)
