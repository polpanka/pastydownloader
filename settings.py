#!/usr/bin/python

import sys, os
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel, QGroupBox, QPushButton, QLineEdit, QFormLayout, QComboBox, QFileDialog, QMessageBox, QScrollArea, QWidget, QApplication
from PySide6.QtCore import QSettings
from libs import Tools
from testi import MyText
from constants import Constants

class SettingsDialog(QDialog):

    parentApp = None
    formGroupBox0 = None
    formGroupBox1 = None
    formGroupBox2 = None
    formGroupBox3 = None
    formGroupBox4 = None
    language = None
    dlFolder = None
    ytConversion = None
    theme = None
    buttonBox = None
    settings = QSettings(MyText().orgName, MyText().appName)

    # constructor
    def __init__(self, parentApp):
        super(SettingsDialog, self).__init__()
        self.parentApp = parentApp
        self.setWindowTitle(MyText().prefsTitle)
        self.setAutoFillBackground(True)
        self.addForm0()
        self.addForm1()
        self.addForm2()
        self.addForm3()
        self.addForm4()
        self.addExitButtons()

        formsLayout = QVBoxLayout()
        formsLayout.addWidget(self.formGroupBox0)
        formsLayout.addWidget(self.formGroupBox1)
        formsLayout.addWidget(self.formGroupBox2)
        formsLayout.addWidget(self.formGroupBox3)
        formsLayout.addWidget(self.formGroupBox4)

        mainLayout = QVBoxLayout()
        if Constants.IS_ANDROID:
            # dimensione fissa 500px pensata per desktop - su schermo
            # piccolo, coi caratteri ingranditi (Constants.applyAndroidFontScale),
            # il contenuto puo' superare l'altezza dello schermo e rendere
            # OK/Annulla irraggiungibili: contenuto scrollabile, pulsanti
            # sempre visibili fuori dallo scroll
            formsWidget = QWidget()
            formsWidget.setLayout(formsLayout)
            scrollArea = QScrollArea()
            scrollArea.setWidget(formsWidget)
            scrollArea.setWidgetResizable(True)
            mainLayout.addWidget(scrollArea)
            screen = QApplication.primaryScreen().availableGeometry()
            self.resize(int(screen.width() * 0.9), int(screen.height() * 0.85))
        else:
            self.resize(500, 0)
            mainLayout.addLayout(formsLayout)
        mainLayout.addWidget(self.buttonBox)
        self.setLayout(mainLayout)

    # riquadro "Language"
    def addForm0(self):
        self.formGroupBox0 = QGroupBox(MyText().languageLabel)
        self.language = QComboBox()
        for code, label in MyText.LANGUAGES:
            self.language.addItem(label, code)
        indexFound = self.language.findData(MyText.getLanguage())
        if indexFound != -1:
            self.language.setCurrentIndex(indexFound)
        layout = QFormLayout()
        layout.addRow(self.language)
        self.formGroupBox0.setLayout(layout)

    # riquadro "Download Folder"
    def addForm1(self):
        self.formGroupBox1 = QGroupBox(MyText().downloadFolderLabel)
        self.btn = QPushButton(MyText().selectButton)
        self.btn.clicked.connect(self.selectNewFolder)
        self.dlFolder = QLineEdit()
        self.dlFolder.setText(Tools().downloadPath())
        layout = QFormLayout()
        layout.addRow(self.btn, self.dlFolder)
        self.formGroupBox1.setLayout(layout)

    # riquadro "Video": select con le 3 modalita' di conversione mp3 (mai / converti+elimina / converti+mantieni)
    def addForm2(self):
        ytOpts = [(MyText().convNever,self.parentApp.ACTION_TO_MP4), (MyText().convDeleteVideo,self.parentApp.ACTION_TO_MP3), (MyText().convKeepVideo,self.parentApp.ACTION_TO_BOTH)]
        self.formGroupBox2 = QGroupBox(MyText().videoGroupLabel)
        self.ytConversion = QComboBox()
        for k, v in ytOpts:
            self.ytConversion.addItem(k, v)
        ext = self.settings.value('ytConversion')
        indexFound = self.ytConversion.findData(ext) if ext else -1
        if indexFound != -1:
            self.ytConversion.setCurrentIndex(indexFound)
        layout = QFormLayout()
        layout.addRow(self.ytConversion)
        self.formGroupBox2.setLayout(layout)

    # riquadro "After download": select se aprire la cartella di download a fine lavoro o non fare nulla
    def addForm3(self):
        self.formGroupBox3 = QGroupBox(MyText().afterDownloadLabel)
        self.doOpen = QComboBox()
        self.doOpen.addItem(MyText().doOpenFolder, 'open')
        self.doOpen.addItem(MyText().doNothing, 'nothing')
        current = self.settings.value('doOpen')
        indexFound = self.doOpen.findData(current) if current else -1
        if indexFound != -1:
            self.doOpen.setCurrentIndex(indexFound)
        if Constants.IS_ANDROID:
            # Tools.openFolder usa dbus-send/FileManager1 (desktop Linux),
            # su Android non fa nulla (vedi Menu.buildPopupMenu in
            # toolbar.py) - non ha senso lasciare la scelta selezionabile
            self.doOpen.setCurrentIndex(self.doOpen.findData('nothing'))
            self.doOpen.setEnabled(False)
        layout = QFormLayout()
        layout.addRow(self.doOpen)
        self.formGroupBox3.setLayout(layout)

    # riquadro "Theme": System (default, segue il sistema operativo) / Light / Dark
    def addForm4(self):
        self.formGroupBox4 = QGroupBox(MyText().themeLabel)
        self.theme = QComboBox()
        themeOpts = [(MyText().themeSystem, Constants.THEME_SYSTEM), (MyText().themeLight, Constants.THEME_LIGHT), (MyText().themeDark, Constants.THEME_DARK)]
        for k, v in themeOpts:
            self.theme.addItem(k, v)
        current = self.settings.value('theme') or Constants.THEME_SYSTEM
        indexFound = self.theme.findData(current)
        if indexFound != -1:
            self.theme.setCurrentIndex(indexFound)
        layout = QFormLayout()
        layout.addRow(self.theme)
        self.formGroupBox4.setLayout(layout)

    # pulsanti OK/Annulla in fondo
    def addExitButtons(self):
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.saveInfo)
        self.buttonBox.rejected.connect(self.reject)

    # click su OK: salva tutti i valori scelti nei riquadri sopra
    def saveInfo(self):
        # language
        settingLang = self.language.currentData()
        languageChanged = settingLang != MyText.getLanguage()
        MyText.setLanguage(settingLang)
        # dl path
        settingDL = self.dlFolder.text().rstrip('/\\')
        if settingDL and os.path.exists(settingDL):
            self.settings.setValue('downloadPath', settingDL)
        # yt conv
        settingYT = self.ytConversion.currentData()
        self.settings.setValue('ytConversion', settingYT)
        # open folder
        settingOpen = self.doOpen.currentData()
        self.settings.setValue('doOpen', settingOpen)
        # theme
        settingTheme = self.theme.currentData()
        themeChanged = settingTheme != (self.settings.value('theme') or Constants.THEME_SYSTEM)
        self.settings.setValue('theme', settingTheme)
        Tools.consoleLogs("Settings saved: language=%s downloadPath=%s ytConversion=%s doOpen=%s theme=%s" % (settingLang, settingDL, settingYT, settingOpen, settingTheme))
        if languageChanged or themeChanged:
            QMessageBox.information(self, MyText().titleRestart, MyText().restartRequired)
        return self.accept()
    
    # click sul bottone "Select": apre il file picker di sistema per la cartella
    def selectNewFolder(self):
        kwargs = {}
        if Constants.IS_ANDROID:
            kwargs['options'] = QFileDialog.Option.DontUseNativeDialog
        path = QFileDialog.getExistingDirectory(None, 'Select Folder', **kwargs)
        if path:
            self.dlFolder.setText(path)
 