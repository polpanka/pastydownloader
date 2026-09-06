<p align="center">
  <img src="../resources/paste512.png" width="120" alt="PastyDownloader logo">
</p>

<h1 align="center">PastyDownloader</h1>
<p align="center"><i>L'assistente di Pastylink per scaricare dal web anche l'impossibile</i></p>

<p align="center">Creato da <b>Paolo Pancaldi</b></p>

<p align="center">
  <a href="../README.md">🇬🇧 English</a> ·
  <b>🇮🇹 Italiano</b> ·
  <a href="README.fr.md">🇫🇷 Français</a> ·
  <a href="README.es.md">🇪🇸 Español</a> ·
  <a href="README.de.md">🇩🇪 Deutsch</a> ·
  <a href="README.zh.md">🇨🇳 简体中文</a> ·
  <a href="README.ja.md">🇯🇵 日本語</a> ·
  <a href="README.pt.md">🇵🇹 Português</a> ·
  <a href="README.ru.md">🇷🇺 Русский</a> ·
  <a href="README.ko.md">🇰🇷 한국어</a> ·
  <a href="README.nl.md">🇳🇱 Nederlands</a> ·
  <a href="README.ar.md">🇸🇦 العربية</a>
</p>

<p align="center">
  <a href="https://github.com/polpanka/pastydownloader/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/polpanka/pastydownloader?include_prereleases&label=release"></a>
  <a href="https://github.com/polpanka/pastydownloader/releases"><img alt="Total downloads" src="https://img.shields.io/github/downloads/polpanka/pastydownloader/total?label=downloads"></a>
  <a href="../LICENSE"><img alt="License: GPLv3" src="https://img.shields.io/badge/license-GPLv3-blue.svg"></a>
  <img alt="Platforms" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Android-lightgrey">
  <a href="https://pasty.link"><img alt="Website" src="https://img.shields.io/badge/website-pasty.link-blue"></a>
</p>

<p align="center">
  <b>Incolla un link. Ottieni il tuo video. Tutto qui.</b>
</p>

PastyDownloader è un'app veloce e senza fronzoli per scaricare video e audio dal web — la stessa filosofia dell'"incolla un link" che c'è dietro [pasty.link](https://pasty.link), il Multimedia Discovery Engine. Copia un link — o un intero elenco — premi incolla e al resto pensa lui: sceglie il motore giusto, mostra l'avanzamento e salva il file esattamente dove vuoi tu. Funziona su Windows, macOS, Linux e Android con un unico codice sorgente.

## ✨ Funzionalità

- 📋 **Incolla qualsiasi cosa** — un singolo link, decine in una volta o un'intera playlist HLS (`#EXTM3U`) incollata come testo grezzo
- 🌐 **Centinaia di siti** — YouTube, Instagram, Facebook e centinaia di altri, ciascuno indirizzato al metodo di estrazione migliore
- 📡 **Stream diretti** — HLS/m3u8, DASH e dirette, scaricati direttamente dalla sorgente
- 💬 **Sottotitoli automatici** — scaricati nella lingua dell'app, quando disponibili
- 🎵 **Estrazione audio in 5 formati** — MP3, AAC/M4A, FLAC, WAV oppure Opus
- 🔒 **Contenuti che richiedono l'accesso** — può usare i cookie del tuo browser per scaricare ciò che richiede un account
- 🌍 **Parla la tua lingua** — Deutsch, English, Español, Français, Italiano, Nederlands, Português, Русский, العربية, 日本語, 简体中文, 한국어
- 💻 **Multipiattaforma** — Windows, macOS, Linux (AppImage inclusa) e Android, tutto da un unico codice sorgente
- 🔗 **Complemento di [pasty.link](https://pasty.link)** — lo stesso flusso "incolla un link" del sito, sul tuo computer e sul telefono
- 🛡️ **Zero complicazioni** — niente account, niente pubblicità, niente tracciamento, niente installazioni manuali; un'unica app gratuita che fa una cosa sola

## 📥 Download

Scarica l'ultima build per il tuo sistema operativo dalla pagina [Releases](https://github.com/polpanka/pastydownloader/releases/latest).

## Requisiti

- **Windows** — Windows 10 (64 bit, 1809 o successivo) o versioni successive
- **macOS** — 11 (Big Sur) o successivo (Apple Silicon e Intel)
- **Linux** — una distribuzione con glibc 2.28+ (es. Ubuntu 20.04+, Debian 11+, Fedora 29+, RHEL 8+)
- **Android** — 5.0 (Lollipop, API 21) o successivo, arm64 (vedi [ANDROID.md](../ANDROID.md) per i dettagli di compilazione)

## Perché PastyDownloader

Completamente sicuro: nessun virus, nessuna pubblicità, nessun tracciamento degli utenti. Niente account, nessuna estensione del browser che si contende la tua attenzione. Solo un'app leggera e gratuita che fa una cosa sola — scaricare — e la fa bene.

## 📱 La build Android

PastyDownloader è nato sul desktop e la build Android non è un'app separata: è lo stesso codice [PySide6](https://www.qt.io/qt-for-python), compilato per un'altra piattaforma. I download avvengono davvero sul dispositivo, inclusa l'unione reale di audio e video tramite un FFmpeg compilato nativamente, non un surrogato ridotto all'osso.

Questa combinazione è insolita: la maggior parte delle app basate su yt-dlp per Android sono riscritture native che non condividono codice con alcuna versione desktop, e i port in Python che riutilizzano un'interfaccia esistente di solito non sono costruiti su Qt. Portare un'app PySide6 completa su Android — accesso allo storage, ponti JNI, un servizio di download in primo piano, FFmpeg nativo — ha richiesto un lavoro prolungato, documentato in [ANDROID.md](../ANDROID.md).

## 🙏 Ringraziamenti

PastyDownloader poggia sulle spalle di alcuni fantastici progetti open source. Un grande grazie ai loro maintainer e contributori:

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — il motore di estrazione che dà un senso ai siti video del web, al lavoro silenziosamente dietro quasi ogni download.
- **[FFmpeg](https://ffmpeg.org)** — la centrale multimediale che gestisce remux, conversione di formato e codifica MP3.
- **[Qt for Python (PySide6)](https://www.qt.io/qt-for-python)** — il toolkit dietro l'interfaccia desktop.

Senza questi progetti, PastyDownloader semplicemente non esisterebbe.

## 🤝 Contribuire

Segnalazioni di bug, richieste di funzionalità e pull request sono benvenute — vedi
[CONTRIBUTING.md](../CONTRIBUTING.md) per sapere come aprire una issue, qual è l'ambito del
progetto e come compilarlo dai sorgenti.

## Release

- **2026-09** - versione 1.7: correzione di bug minori
- **2026-08** - versione 1.5: aggiunta la build Android
- **2026-07** - versione 1.4: refactor completo in PySide6, rilascio open source su GitHub
- **2024-04** - versione 0.7: corretto l'errore dei link troppo lunghi e altre piccole correzioni
- **2023-06** - versione 0.6: conversione mp3, supporto a Dailymotion, Instagram e TikTok
- **2023-05** - versione 0.5: correzione di bug minori
- **2023-04** - versione 0.4: aggiunto il supporto al download di file non video
- **2023-03** - versione 0.3: primo rilascio, integrazione con Pastylink

---

<p align="center">
Distribuito con licenza [GPLv3](../LICENSE). Vedi [TRADEMARK.md](../TRADEMARK.md) per la
politica su nome e logo.
</p>

<p align="center">
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml"><img alt="Build Windows" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml"><img alt="Build macOS" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml"><img alt="Build Linux AppImage" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml"><img alt="Build Android APK" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml/badge.svg"></a>
</p>

<p align="center">Realizzato per <a href="https://pasty.link">pasty.link</a></p>
