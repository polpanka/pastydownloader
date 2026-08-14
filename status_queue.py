#!/usr/bin/python

from PySide6.QtCore import QObject, QTimer


class StatusQueue(QObject):
    """Coda FIFO per i messaggi della barra di stato: chi vuole mostrarne uno
    chiama add(testo, secondi) senza doversi piu' preoccupare di cancellare,
    perdere o sovrascrivere un messaggio che un'altra parte dell'app ha appena
    mostrato (prima ogni chiamante faceva self.statusBar.showMessage(...)
    diretto, e messaggi da fonti concorrenti - connettivita', ffmpeg/yt-dlp in
    background, azioni utente - si sovrascrivevano a vicenda in modo imprevedibile).

    Regole:
     - secondi > 0: messaggio "evento" (es. "Contenuto copiato"), entra in coda
       FIFO - rispetta rigorosamente l'ordine di arrivo, resta in attesa se
       c'e' gia' qualcosa in mostra (un altro evento non ancora scaduto, o un
       messaggio di stato persistente), non lo interrompe mai
     - secondi <= 0: messaggio "di stato" persistente (es. offline, riga N in
       download), sostituisce SUBITO quello che c'e' in barra in quel momento
       (chi mostra uno stato non deve aspettare la coda) e ci resta finche' non
       arriva un'altra add() o una clear() - la coda degli eventi eventualmente
       in attesa riprende solo a quel punto
     - clear(): toglie il messaggio persistente corrente e fa ripartire la coda
       degli eventi in attesa (se ce n'e'), altrimenti svuota la barra
     - showNow(testo, secondi): mostra subito, saltando la coda (non consuma
       ne' tocca gli eventi eventualmente in attesa) - per chi conclude un
       proprio stato persistente con un messaggio definitivo che deve essere
       visto subito (es. YtDlpUpdater: "in corso..." poi "aggiornato",
       Pasty.resetUi: "Riga N in corso..." poi "Download completato")

    Nota: un messaggio persistente non viene mai interrotto da un evento a
    tempo che arriva nel frattempo (altrimenti un "Contenuto copiato" di 2
    secondi potrebbe interrompere uno stato importante come "offline" che deve
    restare visibile) - solo un'altra add()/clear()/showNow() esplicita lo
    sostituisce. Attenzione: clear() poi add() NON equivale a showNow() - se
    nel frattempo si era accodato un evento in attesa, clear() lo promuove
    subito (fa ripartire la coda), e la add() successiva si accoderebbe di
    nuovo dietro a quello, non venendo mostrata immediatamente come ci si
    aspetterebbe da un messaggio "conclusivo": usare showNow() proprio per
    questo, quando il messaggio finale deve avere la precedenza.
    """

    def __init__(self, statusBar):
        super().__init__()
        self.statusBar = statusBar
        self.queue = []  # eventi in attesa: lista di (testo, secondi), secondi sempre > 0
        self.current = None  # (testo, secondi) attualmente mostrato, None se barra vuota
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
            # scaduto il tempo, la coda riprende normalmente da _advance()
            # (gli eventi eventualmente in attesa restano intoccati)
            self.timer.start(seconds * 1000)

    def _advance(self):
        if not self.queue:
            self.current = None
            self.statusBar.clearMessage()
            return
        text, seconds = self.queue.pop(0)
        self.current = (text, seconds)
        self.statusBar.showMessage(text)
        self.timer.start(seconds * 1000)
