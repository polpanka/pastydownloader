#!/usr/bin/python

from libs import Tools


class PastedUrl():
    """Rappresenta una riga della griglia, legge il content-type,
    decide il motore di download giusto (ffmpeg diretto,
    yt-dlp, o il generico) e il nome del file di destinazione."""

    URL_TYPE_VIDEO = 'video'
    URL_TYPE_YT_DLP = 'yt-dlp'
    URL_TYPE_GENERIC = 'generic'  # html, audio, pdf ...
    EXT_MP4 = '.mp4'

    # content-type da passare direttamente a ffmpeg (elenco esplicito: non basta
    # 'application/' da solo, coprirebbe anche pdf/json/zip)
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

    # content-type non media: dritti al downloader generico, niente probe.
    # image/* incluso perche' ffmpeg aprirebbe una foto come video di 1 frame.
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

    PROBE_TIMEOUT_SECONDS = 15  # probe ffmpeg (_isRealVideoOnline)
    GENERIC_YTDLP_FALLBACK_TIMEOUT_SECONDS = 20  # probe yt-dlp su pagina generica

    def __init__(self, appParent, rowId, rawUrl, ffmpeg=None):
        self.appParent = appParent
        self.rowId = rowId
        self.ffmpeg = ffmpeg
        self.originalUrl = rawUrl
        decodedPastylinkUrl = Tools.decodePastylinkUrl(rawUrl) if Tools.isPastylinkUrl(rawUrl) else None
        self.isPastylink = bool(decodedPastylinkUrl)
        self.pastylinkReferer = Tools.decodePastylinkReferer(rawUrl) if self.isPastylink else None
        if self.isPastylink:
            self.url = decodedPastylinkUrl
            self.appParent.pastyGrid.setCellUrl(self.rowId, self.url)
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

    def getPastylinkReferer(self):
        return self.pastylinkReferer

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
            pass  # resta generico
        elif (ct and ct.startswith(self.FFMPEG_DIRECT_CONTENT_TYPES)) or self._isRealVideoOnline():
            self.engine = self.URL_TYPE_VIDEO
            ext = self.EXT_MP4
        elif (not ct or ct.startswith('text/html')) and Tools.isYtDlpDownloadable(self.url, timeout=self.GENERIC_YTDLP_FALLBACK_TIMEOUT_SECONDS):
            # pagina generica che magari nasconde un video: yt-dlp lo trova?
            self.engine = self.URL_TYPE_YT_DLP
            ext = self.EXT_MP4
        if ct and not ext:
            ext = '.' + ct.split('/')[-1]  # text/html
        self.saveAs = tools.getBestFilenameToSaveAs(self.url, ext)

    def _getContentTypeFromUrl(self, url):
        import requests  # import locale
        r = None
        try:
            referers = self.appParent.getReferers()
            host = Tools.getHostFromUrl(url)
            headers = None if host not in referers else {'referer': referers[host]}
            r = requests.get(url, headers=headers, stream=True, timeout=10)  # stream: non scarica tutto
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
        return result.returncode == 0  # 0 = frame scritto davvero
