class Constants:
    # versione dell'app: da tenere allineata a mano con pastylink all'url .../api/checkUpdates/
    # sul server (vedi MyText.checkUpdates), che e' il file confrontato per
    # sapere se c'e' un aggiornamento disponibile (vedi Pasty.checkUpdates)
    APP_VERSION = '1.2'
    APP_VERSION_DATE = '2026.08.19'

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
        scheme = {
            Constants.THEME_LIGHT: Qt.ColorScheme.Light,
            Constants.THEME_DARK: Qt.ColorScheme.Dark,
        }.get(theme, Qt.ColorScheme.Unknown)
        QGuiApplication.styleHints().setColorScheme(scheme)

    @staticmethod
    def isDarkTheme():
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette
        return QApplication.palette().color(QPalette.Window).lightness() < 128

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
