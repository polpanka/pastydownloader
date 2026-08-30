import os


class Constants:
    # da allineare a mano col file .../api/checkUpdates/ sul server
    APP_VERSION = '1.5'
    APP_VERSION_DATE = '2026.08.30'

    # ANDROID_ARGUMENT e' impostata da python-for-android per ogni app
    IS_ANDROID = 'ANDROID_ARGUMENT' in os.environ

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

    # tema scelto in Preferenze (chiave 'theme'); SYSTEM = default, segue il SO
    THEME_SYSTEM = 'system'
    THEME_LIGHT  = 'light'
    THEME_DARK   = 'dark'

    # Forza lo schema colori dell'app. Chiamare dopo la QApplication, prima
    # delle finestre.
    @staticmethod
    def applyTheme(theme):
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtCore import Qt
        styleHints = QGuiApplication.styleHints()
        # setColorScheme solo da PySide6 6.8+ (la build ufficiale e' 6.7.3):
        # senza guard l'app crasha; se manca si resta sul tema di sistema
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
        # preferito: lo schema colore della piattaforma (6.8+). Su Android
        # QApplication.palette() resta spesso quella di default anche a tema scuro.
        styleHints = QGuiApplication.styleHints()
        if hasattr(styleHints, 'colorScheme'):
            scheme = styleHints.colorScheme()
            if scheme != Qt.ColorScheme.Unknown:
                return scheme == Qt.ColorScheme.Dark
        from PySide6.QtWidgets import QApplication
        return QApplication.palette().color(QPalette.Window).lightness() < 128

    # (bg, text) opachi e theme-aware per i popup che su Android non ereditano
    # uno sfondo (QMenu, QDialog): la palette da sola non basta, serve un
    # background-color esplicito nel foglio di stile
    @staticmethod
    def popupColors():
        isDark = Constants.isDarkTheme()
        bg = Constants.COLOR_BG_GRID_DARK_DT if isDark else Constants.COLOR_BG_GRID_LIGHT
        text = Constants.COLOR_WHITE if isDark else Constants.COLOR_BLACK
        return bg, text

    # da chiamare quando lo schema colore cambia; no-op su PySide6 < 6.8
    @staticmethod
    def onThemeChange(callback):
        from PySide6.QtGui import QGuiApplication
        styleHints = QGuiApplication.styleHints()
        if hasattr(styleHints, 'colorSchemeChanged'):
            styleHints.colorSchemeChanged.connect(lambda _: callback())

    # font di default troppo piccolo per touch su Android; dimensione assoluta,
    # non un moltiplicatore (il baseline cambia da solo con lo schema colore)
    ANDROID_FONT_POINT_SIZE = 16

    # su Android la palette resta spesso chiara anche a tema scuro: la
    # sovrascriviamo con colori scuri coerenti. Cache dell'originale per tornare indietro.
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
