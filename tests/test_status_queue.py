#!/usr/bin/python
"""
Test per StatusQueue (status_queue.py): la coda FIFO che sostituisce le
chiamate dirette a QStatusBar.showMessage/clearMessage sparse per l'app, cosi'
messaggi da fonti concorrenti (connettivita', ffmpeg/yt-dlp in background,
azioni utente) non si cancellano/sovrascrivono piu' a vicenda in modo
imprevedibile.

I timer vengono simulati emettendo timer.timeout direttamente (nessuna attesa
reale): il test resta deterministico e veloce.

Esecuzione: python3 -m unittest discover -s tests (stesse dipendenze del programma).
"""

import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv[:1])

from status_queue import StatusQueue


class _FakeStatusBar:
    def __init__(self):
        self.calls = []

    def showMessage(self, text):
        self.calls.append(('show', text))

    def clearMessage(self):
        self.calls.append(('clear', None))

    @property
    def lastShown(self):
        shows = [c[1] for c in self.calls if c[0] == 'show']
        return shows[-1] if shows else None


def expire(queue):
    """Simula la scadenza del timer del messaggio effimero corrente."""
    queue.timer.timeout.emit()


class EphemeralQueueingTest(unittest.TestCase):
    """secondi > 0: entra in coda FIFO, mostrato solo quando arriva il suo turno."""

    def setUp(self):
        self.bar = _FakeStatusBar()
        self.queue = StatusQueue(self.bar)

    def test_shows_immediately_when_nothing_else_is_displayed(self):
        self.queue.add('primo', 5)
        self.assertEqual(self.bar.lastShown, 'primo')
        self.assertTrue(self.queue.timer.isActive())

    def test_second_event_waits_behind_the_first_still_running_one(self):
        self.queue.add('primo', 5)
        self.queue.add('secondo', 3)
        self.assertEqual(self.bar.lastShown, 'primo')  # non sovrascritto

    def test_second_event_shows_only_after_the_first_one_expires(self):
        self.queue.add('primo', 5)
        self.queue.add('secondo', 3)
        expire(self.queue)
        self.assertEqual(self.bar.lastShown, 'secondo')

    def test_strict_arrival_order_with_three_events(self):
        self.queue.add('uno', 1)
        self.queue.add('due', 1)
        self.queue.add('tre', 1)
        shown = [self.bar.lastShown]
        expire(self.queue)
        shown.append(self.bar.lastShown)
        expire(self.queue)
        shown.append(self.bar.lastShown)
        self.assertEqual(shown, ['uno', 'due', 'tre'])

    def test_bar_clears_when_queue_is_exhausted(self):
        self.queue.add('unico', 1)
        expire(self.queue)
        self.assertEqual(self.bar.calls[-1], ('clear', None))
        self.assertIsNone(self.queue.current)


class PersistentMessageTest(unittest.TestCase):
    """secondi <= 0: sostituisce subito quello che c'e', mai interrotto da un
    evento a tempo arrivato nel frattempo - solo un'altra add()/clear()."""

    def setUp(self):
        self.bar = _FakeStatusBar()
        self.queue = StatusQueue(self.bar)

    def test_shows_immediately_and_has_no_running_timer(self):
        self.queue.add('offline', 0)
        self.assertEqual(self.bar.lastShown, 'offline')
        self.assertFalse(self.queue.timer.isActive())

    def test_preempts_a_still_running_ephemeral_message_immediately(self):
        self.queue.add('contenuto copiato', 5)
        self.queue.add('offline', 0)
        self.assertEqual(self.bar.lastShown, 'offline')
        self.assertFalse(self.queue.timer.isActive())  # il timer del precedente e' stato fermato

    def test_ephemeral_event_arriving_while_persistent_is_shown_does_not_preempt_it(self):
        self.queue.add('offline', 0)
        self.queue.add('contenuto copiato', 2)
        self.assertEqual(self.bar.lastShown, 'offline')  # resta "offline", non interrotto

    def test_clear_promotes_the_ephemeral_event_that_was_waiting(self):
        self.queue.add('offline', 0)
        self.queue.add('contenuto copiato', 2)
        self.queue.clear()
        self.assertEqual(self.bar.lastShown, 'contenuto copiato')
        self.assertTrue(self.queue.timer.isActive())

    def test_clear_with_nothing_waiting_leaves_the_bar_empty(self):
        self.queue.add('offline', 0)
        self.queue.clear()
        self.assertEqual(self.bar.calls[-1], ('clear', None))
        self.assertIsNone(self.queue.current)

    def test_a_new_persistent_message_replaces_the_previous_one(self):
        self.queue.add('riga 1 in corso...', 0)
        self.queue.add('riga 2 in corso...', 0)
        self.assertEqual(self.bar.lastShown, 'riga 2 in corso...')


class ShowNowTest(unittest.TestCase):
    """showNow(): il modo corretto di concludere un messaggio persistente con
    un messaggio finale (es. YtDlpUpdater "in corso..." -> "aggiornato",
    Pasty.resetUi "Riga N in corso..." -> "Download completato"). Regressione:
    clear()+add() non basta, perche' clear() puo' promuovere un evento
    eventualmente in attesa (es. un 'Contenuto copiato' rimasto in coda), e la
    add() successiva si accoderebbe di nuovo dietro a quello invece di essere
    mostrata subito."""

    def setUp(self):
        self.bar = _FakeStatusBar()
        self.queue = StatusQueue(self.bar)

    def test_regression_showNow_is_not_pushed_behind_a_pending_event_that_clear_would_promote(self):
        self.queue.add('aggiornamento in corso...', 0)
        self.queue.add('contenuto copiato', 5)  # resta in attesa dietro al persistente
        self.queue.showNow('aggiornato', 5)
        self.assertEqual(self.bar.lastShown, 'aggiornato')  # non 'contenuto copiato'

    def test_clear_then_add_would_have_shown_the_wrong_message_here(self):
        # documenta esattamente il bug corretto: stesso scenario del test
        # sopra, ma con la sequenza clear()+add() che NON va piu' usata
        self.queue.add('aggiornamento in corso...', 0)
        self.queue.add('contenuto copiato', 5)
        self.queue.clear()
        self.queue.add('aggiornato', 5)
        self.assertEqual(self.bar.lastShown, 'contenuto copiato')  # il bug: non 'aggiornato'

    def test_showNow_does_not_consume_the_pending_queue(self):
        self.queue.add('in corso...', 0)
        self.queue.add('contenuto copiato', 5)
        self.queue.showNow('concluso', 3)
        expire(self.queue)  # scade 'concluso'
        self.assertEqual(self.bar.lastShown, 'contenuto copiato')  # l'evento in attesa e' ancora li'

    def test_showNow_with_zero_seconds_leaves_no_timer_running(self):
        self.queue.showNow('stato', 0)
        self.assertFalse(self.queue.timer.isActive())


if __name__ == '__main__':
    unittest.main()
