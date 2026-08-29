import os


class Constants:
    # versione dell'app: da tenere allineata a mano con pastylink all'url .../api/checkUpdates/
    # sul server (vedi MyText.checkUpdates), che e' il file confrontato per
    # sapere se c'e' un aggiornamento disponibile (vedi Pasty.checkUpdates)
    APP_VERSION = '1.4'
    APP_VERSION_DATE = '2026.08.20'

    # True dentro un pacchetto Android (ANDROID_ARGUMENT e' la env var che
    # python-for-android/buildozer impostano sempre per ogni app, non solo
    # per Kivy). Vedi ANDROID.md.
    IS_ANDROID = 'ANDROID_ARGUMENT' in os.environ

    # Guscio sperimentale Android (vedi pysidedeploy.spec, ANDROID.md): salta
    # l'installazione/aggiornamento di ffmpeg e yt-dlp all'avvio - l'app parte
    # e mostra la UI ma non puo' scaricare nulla. Si attiva da solo su
    # Android, oppure a mano con PASTY_SHELL_ONLY=1 per provarlo anche su
    # desktop Linux. Da NON attivare mai nelle build desktop reali.
    SHELL_ONLY_MODE = os.environ.get('PASTY_SHELL_ONLY') == '1' or IS_ANDROID

    # colors
    COLOR_BLUE              = '#004e63'
    COLOR_RED               = '#da4633'
    COLOR_RED_ACCESSIB      = '#d73C28'
    COLOR_WHITE             = '#ffffff'
    COLOR_BLACK             = '#000000'
    COLOR_BG_GRID_LIGHT     = '#e8eff4'
    COLOR_BG_GRID_DARK      = '#d8e1e7'
    COLOR_BG_GRID_LIGHT_DT  = '#2c363b' # alternate row, dark theme
    COLOR_BG_GRID_DARK_DT   = '#20282c' # base row, dark theme

    # status codes
    STATUS_CODE_COMPLETED   = 'Completed'
    STATUS_CODE_ERROR       = 'Error'
    STATUS_CODE_WAITING     = 'Waiting'
    STATUS_CODE_DOWNLOADING = 'Downloading'
    STATUS_CODE_STOPPED     = 'Stopped'
    STATUS_CODE_CONVERTING  = 'Converting'

    # tema scelto in Preferenze (chiave 'theme' in QSettings) - THEME_SYSTEM
    # e' il default, segue il tema del sistema operativo com'era il comportamento
    # implicito dell'app prima di questa scelta
    THEME_SYSTEM = 'system'
    THEME_LIGHT  = 'light'
    THEME_DARK   = 'dark'

    # Forza (o ripristina, con THEME_SYSTEM) lo schema colori dell'intera app -
    # va chiamato dopo aver creato la QApplication, prima di costruire le
    # finestre, cosi' isDarkTheme()/getGridStyle() sotto vedono gia' la scelta
    # dell'utente invece di quella del sistema operativo
    @staticmethod
    def applyTheme(theme):
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtCore import Qt
        styleHints = QGuiApplication.styleHints()
        # setColorScheme esiste solo da Qt/PySide6 6.8 in poi: la build
        # ufficiale (mac/windows/linux) e' pinnata a PySide6 6.7.3 (vedi i
        # workflow .github/workflows/build-*.yml e build-appimage.sh), quindi
        # su quella l'attributo non c'e' - senza questo guard l'app crasha
        # all'avvio. Se manca, si resta sul tema di sistema (comportamento
        # implicito precedente all'introduzione della scelta in Preferenze)
        if not hasattr(styleHints, 'setColorScheme'):
            return
        scheme = {
            Constants.THEME_LIGHT: Qt.ColorScheme.Light,
            Constants.THEME_DARK: Qt.ColorScheme.Dark,
        }.get(theme, Qt.ColorScheme.Unknown)
        styleHints.setColorScheme(scheme)

    @staticmethod
    def isDarkTheme():
        from PySide6.QtGui import QGuiApplication, QPalette
        from PySide6.QtCore import Qt
        # preferito: legge lo schema colore riportato direttamente dalla
        # piattaforma (Qt/PySide6 6.8+, vedi guard in applyTheme sopra) -
        # su Android QApplication.palette() (fallback sotto) resta spesso
        # quella di default anche a tema scuro attivo (i widget nativi -
        # bottoni, menu - vengono comunque disegnati scuri dallo stile,
        # ma leggendo lo schema invece della palette, non da questo valore
        # stantio), causando la griglia bianca con tutto il resto scuro
        styleHints = QGuiApplication.styleHints()
        if hasattr(styleHints, 'colorScheme'):
            scheme = styleHints.colorScheme()
            if scheme != Qt.ColorScheme.Unknown:
                return scheme == Qt.ColorScheme.Dark
        from PySide6.QtWidgets import QApplication
        return QApplication.palette().color(QPalette.Window).lightness() < 128

    # richiamare quando lo schema colore cambia (vedi PastyGrid.initUi) per
    # tenere la griglia sincronizzata - no-op su PySide6 < 6.8 (stessa
    # limitazione di applyTheme sopra)
    @staticmethod
    def onThemeChange(callback):
        from PySide6.QtGui import QGuiApplication
        styleHints = QGuiApplication.styleHints()
        if hasattr(styleHints, 'colorSchemeChanged'):
            styleHints.colorSchemeChanged.connect(lambda _: callback())

    # su Android il font di default e' troppo piccolo per un uso touch
    # confortevole (testato su device reale) - non c'e' un vero "zoom" in
    # Qt Widgets, ma ingrandire il font di default dell'app si propaga da
    # solo a (quasi) tutti i widget standard (bottoni, label, header/celle
    # della griglia, menu) perche' lo ereditano da QApplication.font()
    # invece di uno fisso per-widget.
    # Dimensione ASSOLUTA, non un moltiplicatore relativo a app.font():
    # lo stile nativo Android sembra riportare un QApplication.font() di
    # base diverso a seconda dello schema colore attivo (Light/Dark) - un
    # moltiplicatore sopra un baseline che cambia da solo dava caratteri
    # corretti col tema dark ma enormi col tema light. 16pt e' anche la
    # dimensione body-text di default di Material Design su Android
    # (16sp), e coincide con quanto dava gia' il ×1.6 che sul tema dark
    # risultava corretto
    ANDROID_FONT_POINT_SIZE = 16

    # QApplication.palette() su Android spesso resta quella di default anche
    # a tema scuro attivo (vedi isDarkTheme sopra) - i widget nativi si
    # disegnano scuri comunque tramite lo stile, ma qualunque colore che
    # peschiamo dalla palette (es. il testo dei nostri popup QMenu) risulta
    # sbagliato/illeggibile. Fix: sovrascrivere esplicitamente la palette
    # dell'app con colori scuri coerenti, riusando le costanti gia' in uso
    # per la griglia. Cache della palette originale cosi' si puo' tornare
    # indietro se l'utente cambia tema a light mentre l'app e' aperta
    _defaultPalette = None

    @staticmethod
    def applyAndroidDarkPalette():
        if not Constants.IS_ANDROID:
            return
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette, QColor
        app = QApplication.instance()
        if Constants._defaultPalette is None:
            Constants._defaultPalette = QPalette(app.palette())
        if not Constants.isDarkTheme():
            app.setPalette(Constants._defaultPalette)
            return
        palette = QPalette(Constants._defaultPalette)
        windowBg = QColor(Constants.COLOR_BG_GRID_DARK_DT)
        fieldBg = QColor(Constants.COLOR_BG_GRID_LIGHT_DT)
        text = QColor(Constants.COLOR_WHITE)
        highlight = QColor(Constants.COLOR_BLUE)
        for role in (QPalette.Window, QPalette.AlternateBase):
            palette.setColor(role, windowBg)
        for role in (QPalette.Base, QPalette.Button, QPalette.ToolTipBase):
            palette.setColor(role, fieldBg)
        for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText, QPalette.ToolTipText, QPalette.HighlightedText):
            palette.setColor(role, text)
        palette.setColor(QPalette.BrightText, QColor(Constants.COLOR_RED))
        palette.setColor(QPalette.Link, highlight)
        palette.setColor(QPalette.Highlight, highlight)
        app.setPalette(palette)

    @staticmethod
    def applyAndroidFontScale():
        if not Constants.IS_ANDROID:
            return
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        font = app.font()
        font.setPointSizeF(Constants.ANDROID_FONT_POINT_SIZE)
        app.setFont(font)

    @staticmethod
    def getGridStyle():
        isDark = Constants.isDarkTheme()
        bgAlt = Constants.COLOR_BG_GRID_LIGHT_DT if isDark else Constants.COLOR_BG_GRID_LIGHT
        bgBase = Constants.COLOR_BG_GRID_DARK_DT if isDark else Constants.COLOR_BG_GRID_DARK
        textColor = Constants.COLOR_WHITE if isDark else Constants.COLOR_BLACK
        return """
            QTableWidget { alternate-background-color: %s; background-color: %s; color: %s; }
            QTableWidget::item:selected { background: %s; color: %s; }
        """ % (bgAlt, bgBase, textColor, Constants.COLOR_BLUE, Constants.COLOR_WHITE)
