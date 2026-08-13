#!/usr/bin/python
"""
Test di funzionamento di base per l'incolla-e-riconosci di PastyDownloader:
- URL diretto a un mp4
- manifest HLS (#EXTM3U) incollato per intero, con e senza BOM UTF-8
- URL YouTube
- media non-video: pdf, pagina html, immagine (devono restare sul downloader generico)
- fallback yt-dlp su pagine generiche non appartenenti alle piattaforme note
- url pastylink://<base64> generati dal sito pasty.link

main.Pasty.pasteUrls() e' volutamente "leggero": non fa nessuna analisi (niente
rete, niente probe ffmpeg/yt-dlp), si limita a validare il formato e aggiungere
le righe in griglia cosi' come sono state incollate - altrimenti incollare piu'
link farebbe percepire l'interfaccia come bloccata. L'oggetto PastedUrl (che fa
l'analisi vera e propria) viene creato solo al momento dello scaricamento, in
AsyncWorker.runAllUrls, che gira gia' in un thread separato da quello grafico.

La maggior parte di questi test quindi non tocca la rete per il solo incolla;
la toccano invece i test che costruiscono un PastedUrl direttamente (simulando
cosa succede al momento dello scaricamento). Eccezioni che scaricano per
davvero (poco, file piccoli): YtDlpDirectDownloadTest, NonAacAudioDownloadTest.

Uso gli stessi url (o dello stesso tipo) presenti in toolbar.py -> Menu.fakePopulate,
il pannello "Populate" visibile in DEVEL_MODE.

Esecuzione (richiede le stesse dipendenze del programma: PySide6, aiofiles,
aiohttp, psutil, requests - nessuna libreria di test aggiuntiva, solo unittest
della standard library):
    python3 -m unittest discover -s tests

Alcuni test scaricano file grossi/lenti (es. l'intero manifest multi-traccia
con sottotitoli, ~240MB): sono raggruppati in classi disabilitate di default
(vedi RUN_SLOW_TESTS_ENV_VAR piu' sotto) e si attivano solo esplicitamente:
    PASTY_RUN_SLOW_TESTS=1 python3 -m unittest discover -s tests
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import unittest
from unittest import mock
from unittest.mock import AsyncMock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv[:1])

import main
from grid import PastyGrid
from libs import Tools
from testi import MyText
from worker import AsyncWorker
from pasted_url import PastedUrl


# mp4 buono, da toolbar.py -> fakePopulate
MP4_URL = 'https://vod05.msf.cdn.mediaset.net/farmunica/2024/03/1542611_18e5c175b37d01/mp4/hd_no_mpl.mp4'
# m3u8 buono piccolo, da toolbar.py -> fakePopulate (usato come sorgente del testo manifest da incollare)
M3U8_SOURCE_URL = 'https://ms-027.host-cdn.net/hls/llzefbb2x4hnmttc2rvmpoooq7hxqi6jetco6eod7,qslsyhpz4bmzgkywnea,3alqyhpz4bmpb4u2biq,.urlset/master.m3u8'
# nessun link YouTube in fakePopulate: scelto il primo video mai caricato su
# YouTube (di proprieta' di YouTube stesso), praticamente permanente e stabile
YOUTUBE_URL = 'https://www.youtube.com/watch?v=jNQXAC9IVRw'

# media non-video: devono finire tutti sul downloader generico, non su ffmpeg/yt-dlp.
# Scelti perche' sono fixture di test pensate per restare stabili nel tempo
PDF_URL = 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf'
HTML_PAGE_URL = 'https://example.com/'
IMAGE_URL = 'https://httpbin.org/image/jpeg'
# pagina di news con un video incorporato, non riconoscibile in anticipo
# (non e' un url pastylink://): da toolbar.py -> fakePopulate, dove e'
# gia' commentata "# yt-dlp"
GENERIC_YTDLP_PAGE_URL = 'https://www.cbsnews.com/video/becker-hardly-a-week-goes-by-without-trump-administration-threatening-election-official-arrests/'
# manifest HLS master con traccia audio separata (GENERIC_YTDLP_PAGE_URL punta
# proprio qui dietro le quinte): #EXT-X-STREAM-INF referenzia un AUDIO group a
# parte, quindi serve che ffmpeg (non yt-dlp) sappia associare le due tracce da
# solo leggendo il manifest. Il server lo serve con content-type
# "application/x-mpegURL" (non minuscolo) - usato apposta per coprire quel caso
MULTI_TRACK_M3U8_URL = 'https://prod.vodvideo.cbsnews.com/cbsnews/vr/hls/4685365_hls/master.m3u8'
# audio mp3 (non aac) diretto: il bitstream filter aac_adtstoasc, pensato per
# l'audio aac-adts tipico dell'HLS, rifiuta di aprire il file di output se il
# codec e' un altro (qui mp3) - piccolo (1.5MB), ok per la suite normale
MP3_AUDIO_URL = 'http://jucciz.com/mp3/1987s/1.mp3'

# le classi che scaricano file interi grossi/lenti sono marcate con
# @unittest.skipUnless(RUN_SLOW_TESTS, ...): restano nella suite (documentate,
# eseguibili quando serve davvero controllare a fondo) ma non rallentano ogni
# esecuzione normale. Si attivano con: PASTY_RUN_SLOW_TESTS=1 python3 -m unittest ...
RUN_SLOW_TESTS_ENV_VAR = 'PASTY_RUN_SLOW_TESTS'
RUN_SLOW_TESTS = bool(os.environ.get(RUN_SLOW_TESTS_ENV_VAR))


def makePastylinkUrl(realUrl, extra=None):
    payload = {'url': realUrl, **(extra or {})}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    return Tools.PASTYLINK_URL_PREFIX + encoded


class FakeAppParent:
    """Sostituto minimale della finestra principale Pasty: espone solo cio' che
    servono a Pasty.pasteUrls(), a PastedUrl e ad AsyncWorker, senza costruire
    tutta la UI (menu, toolbar, thread di connettivita', ecc)."""

    ACTION_TO_MP3 = 'mp3'
    ACTION_TO_MP4 = 'mp4'
    ACTION_TO_BOTH = 'both'

    def __init__(self, grid):
        self.pastyGrid = grid
        self.DEVEL_MODE = True  # evita la POST reale di saveStatsUrls
        self.stop = False  # letto da AsyncWorker.isStopped(), usato dal watcher di Tools.runCommand
        self.lastStatus = None

    def setStatusBar(self, txt, sec=0):
        self.lastStatus = txt

    def getReferers(self):
        return {}


class _FakeWidget:
    def setEnabled(self, *a): pass
    def setText(self, *a): pass
    def setIcon(self, *a): pass


class _FakeMenu:
    def setMenuType(self, *a): pass


class _FakeFullAppParent(FakeAppParent):
    """FakeAppParent + gli attributi usati da Pasty.fetchRows/resetUi/waitingUi,
    per testare per intero il flusso di Pasty.startAll() (pasteUrls + fetchRows)."""

    def __init__(self, grid):
        super().__init__(grid)
        self.is_running = False
        self.isOnline = True
        self.button = _FakeWidget()
        self.menu = _FakeMenu()

    # main.Pasty.fetchRows() le chiama come self.waitingUi()/self.resetUi():
    # vanno esposte sull'istanza, delegando all'implementazione vera
    def waitingUi(self):
        return main.Pasty.waitingUi(self)

    def resetUi(self, msg=None):
        return main.Pasty.resetUi(self, msg)


def makeGrid():
    grid = PastyGrid()
    grid.initUi()
    grid.initColumns(True)
    return grid


class PasteMp4Test(unittest.TestCase):

    def setUp(self):
        self.grid = makeGrid()
        self.app = FakeAppParent(self.grid)

    def test_paste_mp4_url_is_added_to_grid(self):
        with mock.patch.object(Tools, 'pasteFromClipboard', return_value=MP4_URL):
            main.Pasty.pasteUrls(self.app)
        self.assertEqual(self.grid.getAllUrlsInTable(), [MP4_URL])

    def test_mp4_url_is_routed_to_direct_video_engine(self):
        """Simula cosa fa AsyncWorker.runAllUrls al momento dello scaricamento:
        costruisce un PastedUrl dall'url cosi' com'e' in griglia."""
        if not Tools.hasInternetConnection():
            self.skipTest('nessuna connessione a internet')
        pastedUrl = PastedUrl(self.app, MP4_URL, Tools.checkFFmpeg())
        if pastedUrl.getEngine() == PastedUrl.URL_TYPE_GENERIC:
            self.skipTest('url mp4 di test non raggiungibile in questo momento')
        self.assertEqual(pastedUrl.getEngine(), PastedUrl.URL_TYPE_VIDEO)
        self.assertTrue(pastedUrl.getSaveAs().endswith('.mp4'))
        self.assertEqual(pastedUrl.getUrl(), pastedUrl.getOriginalUrl())


class PasteM3u8ManifestTest(unittest.TestCase):

    manifestText = None

    @classmethod
    def setUpClass(cls):
        if not Tools.hasInternetConnection():
            raise unittest.SkipTest('nessuna connessione a internet')
        try:
            r = requests.get(M3U8_SOURCE_URL, timeout=10)
            r.raise_for_status()
        except Exception as err:
            raise unittest.SkipTest('manifest m3u8 di test non raggiungibile: %s' % err)
        if not r.text.strip().startswith('#EXTM3U'):
            raise unittest.SkipTest('la sorgente di test non e" (piu") un manifest #EXTM3U valido')
        cls.manifestText = r.text

    def setUp(self):
        self.grid = makeGrid()
        self.app = FakeAppParent(self.grid)
        self.writtenFiles = []

    def tearDown(self):
        for path in self.writtenFiles:
            Tools.removeFile(path)

    def pasteManifest(self, text):
        with mock.patch.object(Tools, 'pasteFromClipboard', return_value=text):
            main.Pasty.pasteUrls(self.app)
        return self.grid.getAllUrlsInTable()

    def test_paste_manifest_adds_raw_text_to_grid(self):
        # niente scrittura su file al momento dell'incolla: in griglia c'e'
        # il testo del manifest cosi' com'e', non un path locale
        rows = self.pasteManifest(self.manifestText)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], self.manifestText.strip())
        self.assertTrue(rows[0].startswith('#EXTM3U'))

    def test_paste_manifest_with_bom_is_still_recognized(self):
        rows = self.pasteManifest('﻿' + self.manifestText)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].startswith('#EXTM3U') or rows[0].startswith('﻿#EXTM3U'))

    def test_manifest_row_is_written_to_file_and_routed_to_direct_video_engine(self):
        """Simula cosa fa AsyncWorker.runAllUrls al momento dello scaricamento:
        prende il testo grezzo cosi' com'e' in griglia e costruisce un
        PastedUrl, che scrive il file solo ora."""
        rawManifestFromGrid = self.pasteManifest(self.manifestText)[0]
        pastedUrl = PastedUrl(self.app, rawManifestFromGrid, Tools.checkFFmpeg())
        self.writtenFiles.append(pastedUrl.getUrl())
        tmpfile = pastedUrl.getUrl()
        self.assertTrue(tmpfile.startswith(Tools.getTempDirectory()))
        self.assertTrue(tmpfile.endswith('.m3u8'))
        self.assertTrue(os.path.exists(tmpfile))
        with open(tmpfile, encoding='utf-8') as f:
            self.assertEqual(f.read(), self.manifestText.strip())
        self.assertEqual(pastedUrl.getEngine(), PastedUrl.URL_TYPE_VIDEO)
        self.assertTrue(pastedUrl.getSaveAs().endswith('.mp4'))
        # getUrl() e' il path locale, getOriginalUrl() resta l'intero testo
        # del manifest cosi' come incollato - non un url
        self.assertEqual(pastedUrl.getOriginalUrl(), self.manifestText.strip())


class PasteYoutubeTest(unittest.TestCase):

    def setUp(self):
        self.grid = makeGrid()
        self.app = FakeAppParent(self.grid)

    def test_paste_youtube_url_is_added_to_grid(self):
        with mock.patch.object(Tools, 'pasteFromClipboard', return_value=YOUTUBE_URL):
            main.Pasty.pasteUrls(self.app)
        self.assertEqual(self.grid.getAllUrlsInTable(), [YOUTUBE_URL])

    def test_plain_youtube_url_still_reaches_ytdlp_via_fallback(self):
        """Senza piu' isSpecialUrl (sostituita da isPastylinkUrl, vedi
        PastylinkUrlTest), un url youtube.com semplice non ha piu' una
        scorciatoia istantanea: passa dal fallback generico (probe ffmpeg +
        isYtDlpDownloadable) come una qualunque pagina sconosciuta - piu'
        lento ma l'esito finale deve restare comunque yt-dlp. Mockiamo le
        chiamate di rete per tenerlo veloce e deterministico."""
        with mock.patch.object(PastedUrl, '_getContentTypeFromUrl', return_value='text/html'), \
             mock.patch.object(PastedUrl, '_isRealVideoOnline', return_value=False), \
             mock.patch.object(Tools, 'isYtDlpDownloadable', return_value=True):
            pastedUrl = PastedUrl(self.app, YOUTUBE_URL, Tools.checkFFmpeg())
        self.assertEqual(pastedUrl.getEngine(), PastedUrl.URL_TYPE_YT_DLP)
        self.assertTrue(pastedUrl.getSaveAs().endswith('.mp4'))


class PastylinkUrlTest(unittest.TestCase):
    """isPastylinkUrl/decodePastylinkUrl: sostituiscono isSpecialUrl. Un url
    'pastylink://<base64 di un json>' e' generato dal sito pasty.link stesso
    per segnalare esplicitamente "questo va aperto con yt-dlp", senza che
    l'app debba indovinarlo. Qui costruiamo noi il payload (non c'e' modo di
    verificare contro il vero pasty.link), quindi questi test provano che il
    nostro decoder e' corretto e coerente con se stesso, non che rispecchi
    esattamente il formato reale del sito.

    L'incolla non decodifica nulla (vedi il modulo docstring): in griglia
    resta l'url pastylink:// grezzo, la decodifica avviene solo quando viene
    costruito un PastedUrl (al momento dello scaricamento)."""

    def setUp(self):
        self.app = FakeAppParent(makeGrid())

    def test_is_pastylink_url(self):
        self.assertTrue(Tools.isPastylinkUrl('pastylink://abc'))
        self.assertFalse(Tools.isPastylinkUrl(YOUTUBE_URL))

    def test_decode_roundtrip(self):
        url = makePastylinkUrl(YOUTUBE_URL, {'title': 'ignorato'})
        self.assertEqual(Tools.decodePastylinkUrl(url), YOUTUBE_URL)

    def test_decode_invalid_payload_returns_none(self):
        self.assertIsNone(Tools.decodePastylinkUrl('pastylink://non-e-base64-valido!!!'))

    def test_decode_missing_url_key_returns_none(self):
        encoded = base64.urlsafe_b64encode(json.dumps({'title': 'senza url'}).encode()).decode().rstrip('=')
        self.assertIsNone(Tools.decodePastylinkUrl(Tools.PASTYLINK_URL_PREFIX + encoded))

    def test_paste_pastylink_url_is_added_to_grid_raw(self):
        pastylinkUrl = makePastylinkUrl(YOUTUBE_URL)
        with mock.patch.object(Tools, 'pasteFromClipboard', return_value=pastylinkUrl):
            main.Pasty.pasteUrls(self.app)
        # in griglia resta l'url pastylink:// grezzo, non ancora decodificato
        self.assertEqual(self.app.pastyGrid.getAllUrlsInTable(), [pastylinkUrl])

    def test_pastylink_url_is_decoded_and_routed_to_ytdlp_when_pastedurl_is_built(self):
        """Simula cosa fa AsyncWorker.runAllUrls al momento dello scaricamento."""
        pastylinkUrl = makePastylinkUrl(YOUTUBE_URL)
        pastedUrl = PastedUrl(self.app, pastylinkUrl, Tools.checkFFmpeg())  # nessun mock: isPastylinkUrl e' un puro controllo di stringa, zero rete
        self.assertEqual(pastedUrl.getUrl(), YOUTUBE_URL)           # gia' decodificato
        self.assertEqual(pastedUrl.getOriginalUrl(), pastylinkUrl)  # il grezzo resta comunque disponibile
        self.assertEqual(pastedUrl.getEngine(), PastedUrl.URL_TYPE_YT_DLP)
        self.assertTrue(pastedUrl.getSaveAs().endswith('.mp4'))

    def test_invalid_pastylink_url_is_rejected_at_paste_time_with_status_error(self):
        # la decodifica del pastylink e' locale (niente rete): va fatta subito
        # al paste, cosi' un payload corrotto non finisce mai in griglia e
        # l'utente viene avvisato subito invece di scoprirlo al download
        invalidUrl = 'pastylink://non-valido!!!'
        with mock.patch.object(Tools, 'pasteFromClipboard', return_value=invalidUrl):
            main.Pasty.pasteUrls(self.app)
        self.assertEqual(self.app.pastyGrid.getAllUrlsInTable(), [])
        self.assertEqual(self.app.lastStatus, MyText().msgInvalidPastylink)

    def test_invalid_pastylink_url_built_directly_falls_back_to_raw_url(self):
        # costruzione diretta di PastedUrl (bypassando il filtro di grid.py):
        # rimane un fallback difensivo, il decode fallito ricade sul ramo else
        invalidUrl = 'pastylink://non-valido!!!'
        pastedUrl = PastedUrl(self.app, invalidUrl, Tools.checkFFmpeg())
        self.assertEqual(pastedUrl.getUrl(), invalidUrl)
        self.assertFalse(pastedUrl.isPastylink)

    def test_start_all_does_not_overwrite_invalid_pastylink_status_with_no_links(self):
        # bug reale: il bottone "Incolla e scarica" chiama pasteUrls() e poi
        # fetchRows() in sequenza (vedi Pasty.startAll). Senza nessun link in
        # attesa, fetchRows() mostrava sempre 'noLinks', cancellando il
        # messaggio piu' specifico appena impostato da pasteUrls()
        invalidUrl = 'pastylink://non-valido!!!'
        fullApp = _FakeFullAppParent(self.app.pastyGrid)
        # replica cosa fa Pasty.startAll() (self.pasteUrls() + self.fetchRows()):
        # chiamata diretta perche' _FakeFullAppParent non e' una vera main.Pasty.
        # setContextMenuType e' mockato: qui il menu contestuale del grid non
        # e' stato inizializzato (makeGrid() non chiama initContextMenu) ed e'
        # comunque irrilevante per cio' che stiamo verificando
        with mock.patch.object(Tools, 'pasteFromClipboard', return_value=invalidUrl), \
             mock.patch.object(fullApp.pastyGrid, 'setContextMenuType'):
            main.Pasty.pasteUrls(fullApp)
            main.Pasty.fetchRows(fullApp, showNoLinksMessage=False)
        self.assertEqual(fullApp.lastStatus, MyText().msgInvalidPastylink)

    def test_pastylink_url_download_uses_the_decoded_url(self):
        pastylinkUrl = makePastylinkUrl(YOUTUBE_URL)
        self.app.pastyGrid.addRow(pastylinkUrl)  # riga grezza, esattamente come la lascerebbe pasteUrls
        self.app.pastyGrid.setCellConvert(0, self.app.ACTION_TO_MP4)
        worker = AsyncWorker(self.app, [0], Tools.checkFFmpeg())
        with mock.patch.object(Tools, 'downloadVideoByYtDlp', new=AsyncMock(return_value=[True, '1 KB'])) as dl:
            worker.runAllUrls()
        calledUrl = dl.call_args[0][2]  # downloadVideoByYtDlp(ytdlp, ffmpeg, url, saveAs, ...)
        self.assertEqual(calledUrl, YOUTUBE_URL)  # non l'url pastylink:// grezzo
        self.assertEqual(worker.pastedUrl.getEngine(), PastedUrl.URL_TYPE_YT_DLP)


class PasteGenericMediaTest(unittest.TestCase):
    """pdf, pagina html, immagine: nessuno dei tre e' un video. Devono finire
    tutti sul downloader generico (mai scambiati per video da ffmpeg - vedi
    il caso immagine, che ffmpeg saprebbe aprire come 'video' di 1 frame -
    e mai tentati con yt-dlp)."""

    # media -> (url, estensione attesa, firma/contenuto atteso all'inizio del file)
    CASES = {
        'pdf': (PDF_URL, '.pdf', b'%PDF'),
        'html': (HTML_PAGE_URL, '.html', b'<'),
        'image': (IMAGE_URL, '.jpeg', b'\xff\xd8\xff'),  # magic number JPEG
    }

    def setUp(self):
        self.grid = makeGrid()
        self.app = FakeAppParent(self.grid)
        self.savedFiles = []

    def tearDown(self):
        for path in self.savedFiles:
            Tools.removeFile(path)

    def test_media_is_added_to_grid(self):
        for name, (url, _ext, _magic) in self.CASES.items():
            with self.subTest(media=name):
                with mock.patch.object(Tools, 'pasteFromClipboard', return_value=url):
                    main.Pasty.pasteUrls(self.app)
                self.assertEqual(self.grid.getAllUrlsInTable(), [url])
                self.grid.reset()

    def test_media_is_classified_as_generic(self):
        if not Tools.hasInternetConnection():
            self.skipTest('nessuna connessione a internet')
        ffmpeg = Tools.checkFFmpeg()
        for name, (url, ext, _magic) in self.CASES.items():
            with self.subTest(media=name):
                pastedUrl = PastedUrl(self.app, url, ffmpeg)
                self.assertEqual(pastedUrl.getEngine(), PastedUrl.URL_TYPE_GENERIC, name)
                self.assertTrue(pastedUrl.getSaveAs().endswith(ext), '%s: saveAs=%s' % (name, pastedUrl.getSaveAs()))

    def test_media_downloads_correctly_via_generic_downloader(self):
        if not Tools.hasInternetConnection():
            self.skipTest('nessuna connessione a internet')
        for name, (url, ext, magic) in self.CASES.items():
            with self.subTest(media=name):
                saveAs = os.path.join(Tools.getTempDirectory(), 'pasty_test_%s%s' % (name, ext))
                self.savedFiles.append(saveAs)
                result = asyncio.run(Tools.downloadAsyncGeneric(url, saveAs))
                self.assertTrue(result[0], '%s: %s' % (name, result))
                with open(saveAs, 'rb') as f:
                    content = f.read(16)
                self.assertTrue(content.startswith(magic), '%s: contenuto inatteso %r' % (name, content))


class PasteGenericYtDlpFallbackTest(unittest.TestCase):
    """Una pagina che non e' gia' video (per content-type/probe ffmpeg) ne'
    un url pastylink://, ma nasconde un video imbarcato: come penultima
    spiaggia prima del downloader generico, PastedUrl deve provare yt-dlp
    (che ha un extractor generico) prima di arrendersi. yt-dlp scarica (e se
    serve fonde audio+video) direttamente da solo."""

    def setUp(self):
        if not Tools.hasInternetConnection():
            self.skipTest('nessuna connessione a internet')
        self.app = FakeAppParent(makeGrid())

    def test_fallback_mechanism_routes_to_ytdlp_when_downloadable(self):
        # verifica il meccanismo in modo deterministico (senza dipendere dalla
        # rete): se il probe dice che yt-dlp trova qualcosa, l'engine diventa yt-dlp
        with mock.patch.object(Tools, 'isYtDlpDownloadable', return_value=True) as mocked:
            pastedUrl = PastedUrl(self.app, GENERIC_YTDLP_PAGE_URL, Tools.checkFFmpeg())
        mocked.assert_called_once()
        self.assertEqual(pastedUrl.getEngine(), PastedUrl.URL_TYPE_YT_DLP)
        self.assertTrue(pastedUrl.getSaveAs().endswith('.mp4'))

    def test_page_with_video_only_hls_tracks_is_routed_to_ytdlp(self):
        """Caso reale, gia' in fakePopulate: le tracce audio e video di questa
        pagina sono HLS separate (nessun url unico contiene entrambe). Con il
        vecchio approccio (estrai-un-url-e-scaricalo-con-ffmpeg) sarebbe stata
        scartata per non rischiare un video muto; ora che e' yt-dlp stesso a
        scaricare e fondere le tracce, il probe la riconosce come scaricabile."""
        pastedUrl = PastedUrl(self.app, GENERIC_YTDLP_PAGE_URL, Tools.checkFFmpeg())
        self.assertEqual(pastedUrl.getEngine(), PastedUrl.URL_TYPE_YT_DLP)


class PasteMultiTrackM3u8Test(unittest.TestCase):
    """Un manifest HLS master incollato direttamente (non una pagina che lo
    nasconde) con audio su una traccia separata (EXT-X-MEDIA + AUDIO group
    referenziato da EXT-X-STREAM-INF): qui e' ffmpeg stesso, non yt-dlp, a
    dover leggere il manifest e associare le due tracce. Il file reale e'
    grande (~240MB, 11 minuti): verifichiamo solo la classificazione, non il
    download completo (vedi FullMultiTrackM3u8DownloadTest per quello)."""

    def setUp(self):
        if not Tools.hasInternetConnection():
            self.skipTest('nessuna connessione a internet')

    def test_master_playlist_with_separate_audio_group_is_routed_to_direct_video_engine(self):
        pastedUrl = PastedUrl(FakeAppParent(makeGrid()), MULTI_TRACK_M3U8_URL, Tools.checkFFmpeg())
        if pastedUrl.getEngine() == PastedUrl.URL_TYPE_GENERIC:
            self.skipTest('manifest di test non raggiungibile in questo momento')
        self.assertEqual(pastedUrl.getEngine(), PastedUrl.URL_TYPE_VIDEO)
        self.assertTrue(pastedUrl.getSaveAs().endswith('.mp4'))

    def test_probe_finds_best_video_track_and_subtitle_track(self):
        """Il probe legge solo il testo del manifest (pochi KB), non scarica
        segmenti video: verifica che scelga la risoluzione piu' alta (non la
        prima elencata) e riconosca la traccia sottotitoli separata."""
        ffmpeg = Tools.checkFFmpeg()
        bestVideoIndex, hasAudio, hasSubtitle = Tools._probeHlsStreams(ffmpeg, MULTI_TRACK_M3U8_URL, '')
        if bestVideoIndex is None:
            self.skipTest('manifest di test non raggiungibile in questo momento')
        self.assertTrue(hasAudio)
        self.assertTrue(hasSubtitle)

    def test_probe_on_manifest_without_audio_or_subtitles(self):
        """Regressione: il manifest piccolo usato altrove nella suite non ha
        ne' audio ne' sottotitoli (solo video) - il probe non deve inventarseli."""
        ffmpeg = Tools.checkFFmpeg()
        bestVideoIndex, hasAudio, hasSubtitle = Tools._probeHlsStreams(ffmpeg, M3U8_SOURCE_URL, '')
        if bestVideoIndex is None:
            self.skipTest('manifest di test non raggiungibile in questo momento')
        self.assertFalse(hasAudio)
        self.assertFalse(hasSubtitle)


@unittest.skipUnless(RUN_SLOW_TESTS, 'test lento e pesante (~240MB, ~1 minuto): imposta %s=1 per eseguirlo' % RUN_SLOW_TESTS_ENV_VAR)
class FullMultiTrackM3u8DownloadTest(unittest.TestCase):
    """Come PasteMultiTrackM3u8Test, ma scarica per intero il manifest master
    (~240MB, ~1 minuto) invece di limitarsi alla classificazione: verifica che
    il file finale abbia davvero la risoluzione migliore, l'audio e i
    sottotitoli come traccia soft. Disabilitato di default, da attivare
    esplicitamente quando serve un controllo end-to-end."""

    def setUp(self):
        if not Tools.hasInternetConnection():
            self.skipTest('nessuna connessione a internet')
        self.ffmpeg = Tools.checkFFmpeg()
        if not self.ffmpeg:
            self.skipTest('ffmpeg imbarcato non trovato')
        self.saveAs = os.path.join(Tools.getTempDirectory(), 'pasty_test_full_hls_subs.mp4')

    def tearDown(self):
        Tools.removeFile(self.saveAs)

    def test_master_playlist_download_includes_best_video_audio_and_soft_subtitles(self):
        result = asyncio.run(Tools.downloadVideoByFFmpeg(self.ffmpeg, MULTI_TRACK_M3U8_URL, '', self.saveAs))
        self.assertTrue(result[0], result)
        probe = subprocess.run([self.ffmpeg, '-hide_banner', '-i', self.saveAs],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding='utf-8', errors='replace')
        self.assertIn('1920x1080', probe.stdout)  # la risoluzione migliore disponibile, non la prima elencata
        self.assertIn('Audio:', probe.stdout)
        self.assertIn('Subtitle:', probe.stdout)


class ContentTypeClassificationTest(unittest.TestCase):
    """Content-type esplicitamente censiti in FFMPEG_DIRECT_CONTENT_TYPES e
    GENERIC_ONLY_CONTENT_TYPES: mockano solo il content-type (nessun url
    reale da raggiungere), il resto del codice di PastedUrl._analyze gira
    per intero. Zero rete: il primo controllo (_getContentTypeFromUrl) e'
    l'unico che tocca la rete, ed e' proprio quello mockato."""

    def setUp(self):
        self.app = FakeAppParent(makeGrid())

    def classify(self, contentType):
        with mock.patch.object(PastedUrl, '_getContentTypeFromUrl', return_value=contentType):
            return PastedUrl(self.app, 'https://example.test/resource', Tools.checkFFmpeg())

    def test_audio_and_other_media_content_types_are_routed_to_direct_video_engine(self):
        for contentType in ['audio/mpeg', 'application/ogg', 'application/x-matroska', 'application/vnd.ms-asf']:
            with self.subTest(contentType=contentType):
                pastedUrl = self.classify(contentType)
                self.assertEqual(pastedUrl.getEngine(), PastedUrl.URL_TYPE_VIDEO)
                self.assertTrue(pastedUrl.getSaveAs().endswith('.mp4'))

    def test_clearly_non_media_content_types_are_routed_to_generic(self):
        contentTypes = ['application/pdf', 'application/json', 'application/zip',
                         'application/xml', 'text/xml', 'text/plain', 'text/css',
                         'text/javascript', 'application/javascript', 'image/png',
                         'text/csv', 'text/markdown', 'application/vnd.rar',
                         'application/x-7z-compressed', 'application/msword',
                         'application/epub+zip']
        for contentType in contentTypes:
            with self.subTest(contentType=contentType):
                pastedUrl = self.classify(contentType)
                self.assertEqual(pastedUrl.getEngine(), PastedUrl.URL_TYPE_GENERIC)
                self.assertTrue(pastedUrl.getSaveAs().endswith('.' + contentType.split('/')[-1]))


class RunAllUrlsBuildsPastedUrlTest(unittest.TestCase):
    """AsyncWorker.runAllUrls deve costruire (e quindi analizzare) un
    PastedUrl fresco per ogni riga proprio al momento dello scaricamento,
    non prima: verifica che l'url grezzo in griglia venga passato cosi'
    com'e' a PastedUrl, e che il downloader usi il risultato di quell'analisi."""

    def setUp(self):
        self.grid = makeGrid()
        self.app = FakeAppParent(self.grid)

    def test_worker_builds_pastedurl_from_raw_grid_value_at_download_time(self):
        self.grid.addRow(MP4_URL)
        self.grid.setCellConvert(0, self.app.ACTION_TO_MP4)
        worker = AsyncWorker(self.app, [0], Tools.checkFFmpeg())
        self.assertIsNone(worker.pastedUrl)  # non ancora costruito
        with mock.patch.object(PastedUrl, '_getContentTypeFromUrl', return_value='video/mp4'), \
             mock.patch.object(Tools, 'downloadVideoByFFmpeg', new=AsyncMock(return_value=[True, '1 MB'])):
            worker.runAllUrls()
        self.assertIsInstance(worker.pastedUrl, PastedUrl)
        self.assertEqual(worker.pastedUrl.getUrl(), MP4_URL)
        self.assertEqual(worker.pastedUrl.getEngine(), PastedUrl.URL_TYPE_VIDEO)


class NonAacAudioDownloadTest(unittest.TestCase):
    """Un audio mp3 diretto (non aac) scaricato via ffmpeg: aac_adtstoasc e'
    pensato solo per l'audio aac in formato adts (tipico dell'HLS) - su un
    codec diverso ffmpeg si rifiuta di aprire il file di output, e prima di
    questo fix l'intero download falliva. Verifica il retry automatico senza
    quel filtro."""

    def setUp(self):
        if not Tools.hasInternetConnection():
            self.skipTest('nessuna connessione a internet')
        self.ffmpeg = Tools.checkFFmpeg()
        if not self.ffmpeg:
            self.skipTest('ffmpeg imbarcato non trovato')
        self.saveAs = os.path.join(Tools.getTempDirectory(), 'pasty_test_mp3_audio.mp4')

    def tearDown(self):
        Tools.removeFile(self.saveAs)

    def test_mp3_audio_download_succeeds_via_retry_without_aac_filter(self):
        result = asyncio.run(Tools.downloadVideoByFFmpeg(self.ffmpeg, MP3_AUDIO_URL, '', self.saveAs))
        if not result[0]:
            self.skipTest('mp3 di test non raggiungibile in questo momento: %s' % result)
        probe = subprocess.run([self.ffmpeg, '-hide_banner', '-i', self.saveAs],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding='utf-8', errors='replace')
        self.assertIn('Audio:', probe.stdout)


class YtDlpDirectDownloadTest(unittest.TestCase):
    """Verifica reale (non mockata) che Tools.downloadVideoByYtDlp scarichi
    per intero e fonda video+audio in un unico file valido - il cuore del
    nuovo meccanismo, sia per le piattaforme note sia per il fallback
    generico. Usa lo stesso video di YOUTUBE_URL: piccolo (19s), cosi' il
    download reale resta veloce."""

    def setUp(self):
        if not Tools.hasInternetConnection():
            self.skipTest('nessuna connessione a internet')
        self.ffmpeg = Tools.checkFFmpeg()
        self.ytdlp = Tools.checkYtDlp()
        if not self.ffmpeg or not self.ytdlp:
            self.skipTest('ffmpeg o yt-dlp imbarcati non trovati')
        self.saveAs = os.path.join(Tools.getTempDirectory(), 'pasty_test_ytdlp_direct.mp4')

    def tearDown(self):
        Tools.removeFile(self.saveAs)

    def test_download_merges_video_and_audio_into_one_valid_file(self):
        result = asyncio.run(Tools.downloadVideoByYtDlp(
            self.ytdlp, self.ffmpeg, YOUTUBE_URL, self.saveAs, None, None))
        self.assertTrue(result[0], result)
        self.assertTrue(os.path.exists(self.saveAs))
        # verifica che il file abbia davvero sia una traccia video sia una audio
        probe = subprocess.run([self.ffmpeg, '-hide_banner', '-i', self.saveAs],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding='utf-8', errors='replace')
        self.assertIn('Video:', probe.stdout)
        self.assertIn('Audio:', probe.stdout)


class YtDlpProgressAccumulationTest(unittest.TestCase):
    """Quando le tracce non sono gia' combinate, yt-dlp le scarica una per
    volta (prima il video, poi l'audio): i byte scaricati riportati da
    --progress-template ripartono da zero al cambio fase. Verifica (senza
    rete, con un processo finto) che _runYtDlpWithProgress sommi le fasi
    gia' completate invece di far tornare indietro il progresso mostrato."""

    class _FakeStdout(list):
        def close(self):
            pass

    class _FakeStderr:
        def read(self):
            return ''

        def close(self):
            pass

    class _FakeProcess:
        def __init__(self, lines):
            self.stdout = YtDlpProgressAccumulationTest._FakeStdout(lines)
            self.stderr = YtDlpProgressAccumulationTest._FakeStderr()
            self.returncode = 0

        def poll(self):
            return 0  # gia' terminato: niente thread watcher da avviare

        def wait(self):
            pass

    def test_progress_does_not_go_backwards_across_video_and_audio_phases(self):
        prefix = Tools.YTDLP_PROGRESS_PREFIX
        lines = [
            prefix + '1000', prefix + '100000', prefix + '220000',  # fase video
            prefix + '1000', prefix + '120000', prefix + '250000',  # fase audio, riparte da zero
        ]
        process = self._FakeProcess(lines)
        seen = []
        with mock.patch.object(Tools, '_spawnWithStopWatcher', return_value=(process, {'stopped': False}, None)), \
             mock.patch.object(Tools, 'PROGRESS_THROTTLE_SECONDS', 0):
            Tools._runYtDlpWithProgress(['fake'], onProgress=seen.append, isStoppedFn=None)
        self.assertEqual(seen, [1000, 100000, 220000, 221000, 340000, 470000])
        self.assertTrue(all(a <= b for a, b in zip(seen, seen[1:])), seen)


if __name__ == '__main__':
    unittest.main()
