#!/usr/bin/python

import os
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel, QGroupBox, QPushButton, QLineEdit, QFormLayout, QComboBox, QCheckBox, QFileDialog, QMessageBox, QScrollArea, QWidget, QApplication
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
    formGroupBox5 = None
    language = None
    dlFolder = None
    ytConversion = None
    audioFormat = None
    theme = None
    buttonBox = None
    settings = QSettings(MyText().orgName, MyText().appName)

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
        # su Android non e' possibile
        if not Constants.IS_ANDROID:
            self.addForm5()
        self.addExitButtons()

        formsLayout = QVBoxLayout()
        formsLayout.addWidget(self.formGroupBox0)
        formsLayout.addWidget(self.formGroupBox1)
        formsLayout.addWidget(self.formGroupBox2)
        formsLayout.addWidget(self.formGroupBox3)
        formsLayout.addWidget(self.formGroupBox4)
        if not Constants.IS_ANDROID:
            formsLayout.addWidget(self.formGroupBox5)

        mainLayout = QVBoxLayout()
        if Constants.IS_ANDROID:
            # contenuto scrollabile: coi font ingranditi puo' superare lo schermo
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

    # riquadro "Video": modalita' di conversione audio + formato audio
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
        audioFormats = [('MP3', 'mp3'), ('AAC (M4A)', 'aac'), ('FLAC', 'flac'), ('WAV', 'wav'), ('Opus', 'opus')]
        self.audioFormat = QComboBox()
        for k, v in audioFormats:
            self.audioFormat.addItem(k, v)
        currentFormat = self.settings.value('audioFormat')
        indexFound = self.audioFormat.findData(currentFormat) if currentFormat else -1
        if indexFound != -1:
            self.audioFormat.setCurrentIndex(indexFound)
        layout = QFormLayout()
        layout.addRow(self.ytConversion)
        layout.addRow(MyText().audioFormatLabel, self.audioFormat)
        self.formGroupBox2.setLayout(layout)

    # riquadro "After download": aprire la cartella a fine lavoro o no
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
            self.doOpen.setCurrentIndex(self.doOpen.findData('nothing'))  # openFolder non fa nulla su Android
            self.doOpen.setEnabled(False)
        layout = QFormLayout()
        layout.addRow(self.doOpen)
        self.formGroupBox3.setLayout(layout)

    # riquadro "Theme": System / Light / Dark
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

    # riquadro "Browser login": checkbox cookie del browser per i contenuti con
    # login (salvato 'yes'/'no'; default per-SO, vedi Tools.browserLoginConsentEnabled)
    def addForm5(self):
        self.formGroupBox5 = QGroupBox(MyText().browserLoginTitle)
        self.browserLogin = QCheckBox(MyText().browserLoginSettingLabel)
        self.browserLogin.setChecked(Tools.browserLoginConsentEnabled())
        layout = QVBoxLayout()
        layout.addWidget(self.browserLogin)
        self.formGroupBox5.setLayout(layout)

    def addExitButtons(self):
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.saveInfo)
        self.buttonBox.rejected.connect(self.reject)

    def saveInfo(self):
        settingLang = self.language.currentData()
        languageChanged = settingLang != MyText.getLanguage()
        MyText.setLanguage(settingLang)
        settingDL = self.dlFolder.text().rstrip('/\\')
        if settingDL and os.path.exists(settingDL):
            self.settings.setValue('downloadPath', settingDL)
        settingYT = self.ytConversion.currentData()
        self.settings.setValue('ytConversion', settingYT)
        settingAudioFormat = self.audioFormat.currentData()
        self.settings.setValue('audioFormat', settingAudioFormat)
        settingOpen = self.doOpen.currentData()
        self.settings.setValue('doOpen', settingOpen)
        settingTheme = self.theme.currentData()
        themeChanged = settingTheme != (self.settings.value('theme') or Constants.THEME_SYSTEM)
        self.settings.setValue('theme', settingTheme)
        if not Constants.IS_ANDROID:  # browser login: assente su Android
            self.settings.setValue('browserLoginConsent', 'yes' if self.browserLogin.isChecked() else 'no')
        Tools.consoleLogs("Settings saved: language=%s downloadPath=%s ytConversion=%s audioFormat=%s doOpen=%s theme=%s" % (settingLang, settingDL, settingYT, settingAudioFormat, settingOpen, settingTheme))
        if languageChanged or themeChanged:
            QMessageBox.information(self, MyText().titleRestart, MyText().restartRequired)
        return self.accept()
    
    def selectNewFolder(self):
        kwargs = {}
        if Constants.IS_ANDROID:
            # dialog non nativo forzato; ShowDirsOnly va rimesso a mano quando si passa 'options'
            kwargs['options'] = QFileDialog.Option.DontUseNativeDialog | QFileDialog.Option.ShowDirsOnly
        path = QFileDialog.getExistingDirectory(None, 'Select Folder', **kwargs)
        if path:
            self.dlFolder.setText(path)
 