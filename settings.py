#!/usr/bin/python

import sys, os
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel, QGroupBox, QPushButton, QLineEdit, QFormLayout, QComboBox, QFileDialog, QMessageBox
from PySide6.QtCore import QSettings
from libs import Tools
from testi import MyText

class SettingsDialog(QDialog):

    parentApp = None
    formGroupBox0 = None
    formGroupBox1 = None
    formGroupBox2 = None
    formGroupBox3 = None
    language = None
    dlFolder = None
    ytConversion = None
    buttonBox = None
    settings = QSettings(MyText().orgName, MyText().appName)

    # constructor
    def __init__(self, parentApp):
        super(SettingsDialog, self).__init__()
        self.parentApp = parentApp
        self.setWindowTitle(MyText().prefsTitle)
        self.resize(500, 0)
        self.addForm0()
        self.addForm1()
        self.addForm2()
        self.addForm3()
        self.addExitButtons()

        # creating a vertical layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.formGroupBox0)
        mainLayout.addWidget(self.formGroupBox1)
        mainLayout.addWidget(self.formGroupBox2)
        mainLayout.addWidget(self.formGroupBox3)
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
        layout = QFormLayout()
        layout.addRow(self.doOpen)
        self.formGroupBox3.setLayout(layout)

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
        Tools.consoleLogs("Settings saved: language=%s downloadPath=%s ytConversion=%s doOpen=%s" % (settingLang, settingDL, settingYT, settingOpen))
        if languageChanged:
            QMessageBox.information(self, MyText().titleRestart, MyText().restartRequired)
        return self.accept()
    
    # click sul bottone "Select": apre il file picker di sistema per la cartella
    def selectNewFolder(self):
        path = QFileDialog.getExistingDirectory(None, 'Select Folder')
        if path:
            self.dlFolder.setText(path)
 