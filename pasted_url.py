#!/usr/bin/python

import requests
from libs import Tools


class PastedUrl():
    """Rappresenta una riga della griglia, legge il content-type,
    decide il motore di download giusto (ffmpeg diretto,
    yt-dlp, o il generico) e il nome del file di destinazione."""

    URL_TYPE_VIDEO = 'video'
    URL_TYPE_YT_DLP = 'yt-dlp'
    URL_TYPE_GENERIC = 'generic'  # html, audio, pdf ...
    EXT_MP4 = '.mp4'

    # content-type da passare direttamente a ffmpeg (video e audio: entrambi
    # gestiti dallo stesso motore, l'audio finisce comunque in un .mp4 - la
    # conversione in mp3 e' un passo separato gia' esistente). NON basta
    # 'application/' da solo: coprirebbe anche pdf/json/zip/xml/js (tutti
    # 'application/*' ma non media), mandandoli a ffmpeg per errore invece
    # che al downloader generico che li salverebbe correttamente
    FFMPEG_DIRECT_CONTENT_TYPES = (
        'video/',
        'audio/',
        'application/octet-stream',
        'application/vnd.apple.mpegurl',
        'application/x-mpegurl',
        'application/dash+xml',
        'application/mp4',
        'application/ogg',           # ogg/opus/vorbis
        'application/x-matroska',    # mkv
        'application/vnd.ms-asf',    # wmv/asf
    )

    # content-type chiaramente non video/audio: saltano sia il probe ffmpeg
    # (isRealVideoOnline) sia il fallback yt-dlp e vanno dritti al downloader
    # generico, che li salva correttamente. image/* e' incluso perche' ffmpeg
    # aprirebbe comunque una foto come "video" di 1 frame (demuxer image2)
    GENERIC_ONLY_CONTENT_TYPES = (
        'image/',
        'application/pdf',
        'application/json',
        'application/zip',
        'application/xml',
        'text/xml',
        'text/plain',
        'text/css',
        'text/javascript',
        'application/javascript',
        'text/csv',
        'text/markdown',
        'text/calendar',
        'application/vnd.rar',
        'application/x-rar-compressed',
        'application/x-7z-compressed',
        'application/x-tar',
        'application/gzip',
        'application/x-gzip',
        'application/msword',
        'application/vnd.ms-excel',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.',  # docx/xlsx/pptx condividono questo prefisso
        'application/rtf',
        'application/epub+zip',
    )

    # tempo massimo per il probe ffmpeg (_isRealVideoOnline): senza un limite
    # un host lento/muto puo' bloccare l'analisi a tempo indeterminato
    PROBE_TIMEOUT_SECONDS = 15

    # tempo massimo per il tentativo yt-dlp "penultima spiaggia" su una pagina
    # generica (non una piattaforma nota): piu' breve dei 120s usati per un
    # download vero, perche' qui si tenta su tante pagine che quasi sempre
    # non hanno nulla da estrarre, e non deve rallentare troppo l'incolla
    GENERIC_YTDLP_FALLBACK_TIMEOUT_SECONDS = 20

    def __init__(self, appParent, rawUrl, ffmpeg=None):
        self.appParent = appParent
        self.ffmpeg = ffmpeg
        self.originalUrl = rawUrl
        decodedPastylinkUrl = Tools.decodePastylinkUrl(rawUrl) if Tools.isPastylinkUrl(rawUrl) else None
        self.isPastylink = bool(decodedPastylinkUrl)
        if self.isPastylink:
            self.url = decodedPastylinkUrl
        elif Tools.isM3u8ManifestText(rawUrl):
            self.url = Tools.writeM3u8InFile(Tools.stripBom(rawUrl))
        else:
            self.url = rawUrl
        self.contentType = None
        self.engine = self.URL_TYPE_GENERIC
        self.saveAs = None
        self._analyze()

    def getUrl(self):
        return self.url

    def getOriginalUrl(self):
        return self.originalUrl

    def getContentType(self):
        return self.contentType

    def getEngine(self):
        return self.engine

    def getSaveAs(self):
        return self.saveAs

    def _analyze(self):
        if not self.url:
            return
        tools = Tools()
        ext = ''
        self.contentType = self._getContentTypeFromUrl(self.url)
        ct = self.contentType
        if self.url.startswith(tools.getTempDirectory()):
            self.engine = self.URL_TYPE_VIDEO
            ext = self.EXT_MP4
        elif self.isPastylink:
            self.engine = self.URL_TYPE_YT_DLP
            ext = self.EXT_MP4
        elif ct and ct.startswith(self.GENERIC_ONLY_CONTENT_TYPES):
            pass  # resta generico: niente probe ne' fallback yt-dlp, sappiamo gia' che non e' un media
        elif (ct and ct.startswith(self.FFMPEG_DIRECT_CONTENT_TYPES)) or self._isRealVideoOnline():
            self.engine = self.URL_TYPE_VIDEO
            ext = self.EXT_MP4
        elif (not ct or ct.startswith('text/html')) and Tools.isYtDlpDownloadable(self.url, timeout=self.GENERIC_YTDLP_FALLBACK_TIMEOUT_SECONDS):
            # penultima spiaggia prima del generico: magari e' una pagina che
            # nasconde un video imbarcato, su un sito diverso dalle piattaforme
            # note. yt-dlp fa gia' da solo tutto il lavoro di scoperta (e di
            # eventuale fusione audio/video) al momento del download vero, qui
            # verifichiamo solo che trovi qualcosa
            self.engine = self.URL_TYPE_YT_DLP
            ext = self.EXT_MP4
        if ct and not ext:
            ext = '.' + ct.split('/')[-1]  # text/html
        self.saveAs = tools.getBestFilenameToSaveAs(self.url, ext)

    def _getContentTypeFromUrl(self, url):
        r = None
        try:
            referers = self.appParent.getReferers()
            host = Tools.getHostFromUrl(url)
            headers = None if host not in referers else {'referer': referers[host]}
            r = requests.get(url, headers=headers, stream=True, timeout=10)  # non deve scaricare tutto il video
            r.connection.close()
            return r.headers['Content-Type'].split(';')[0].strip().lower() if r.headers and 'Content-Type' in r.headers else None
        except Exception:
            if r:
                r.connection.close()
            return None

    def _isRealVideoOnline(self):
        if not self.ffmpeg:
            return False
        referers = self.appParent.getReferers()
        host = Tools.getHostFromUrl(self.url)
        referer = referers.get(host)
        command = [self.ffmpeg, '-hide_banner', '-loglevel', 'warning']
        if referer:
            command += ['-headers', 'Referer: %s\r\n' % referer]
        command += ['-i', self.url, '-f', 'image2pipe', '-frames', '1', '-r', '1', '-c:v:1', 'jpeg', '-']
        result = Tools.runCommand(command, timeout=self.PROBE_TIMEOUT_SECONDS)
        if not result or result.interrupted:
            return False
        # returncode 0 solo se il frame e' stato scritto davvero
        return result.returncode == 0
