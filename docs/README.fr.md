<p align="center">
  <img src="../src/resources/paste512.png" width="120" alt="PastyDownloader logo">
</p>

<h1 align="center">PastyDownloader</h1>
<p align="center"><i>L'assistant Pastylink pour télécharger l'impossible depuis le Web</i></p>

<p align="center">Créé par <b>Paolo Pancaldi</b></p>

<p align="center">
  <a href="../README.md">🇬🇧 English</a> ·
  <a href="README.it.md">🇮🇹 Italiano</a> ·
  <b>🇫🇷 Français</b> ·
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
  <b>Collez un lien. Récupérez votre vidéo. C'est tout.</b>
</p>

PastyDownloader est une application rapide et sans fioritures pour récupérer des vidéos et de l'audio sur le web — la même philosophie du « collez un lien » qui est derrière [pasty.link](https://pasty.link), le Multimedia Discovery Engine. Copiez un lien — ou toute une série — appuyez sur coller, et l'appli s'occupe du reste : elle choisit le bon moteur, suit la progression et enregistre le fichier exactement où vous le souhaitez. Fonctionne sur Windows, macOS, Linux et Android à partir d'une seule base de code.

## ✨ Fonctionnalités

- 📋 **Collez n'importe quoi** — un seul lien, des dizaines à la fois, ou une playlist HLS entière (`#EXTM3U`) collée en texte brut
- 🌐 **Des centaines de sites** — YouTube, Instagram, Facebook et des centaines d'autres, chacun dirigé vers ce qui l'extrait le mieux
- 📡 **Flux directs** — HLS/m3u8, DASH et diffusions en direct, téléchargés directement depuis la source
- 💬 **Sous-titres automatiques** — téléchargés dans la langue de l'application lorsqu'ils sont disponibles
- 🎵 **Extraction audio en 5 formats** — MP3, AAC/M4A, FLAC, WAV ou Opus
- 🔒 **Contenus nécessitant une connexion** — peut utiliser les cookies de votre navigateur pour télécharger ce qui exige un compte
- 🌍 **Parle votre langue** — Deutsch, English, Español, Français, Italiano, Nederlands, Português, Русский, العربية, 日本語, 简体中文, 한국어
- 💻 **Multiplateforme** — Windows, macOS, Linux (AppImage incluse) et Android, le tout à partir d'une seule base de code
- 🔗 **Complément de [pasty.link](https://pasty.link)** — le même flux « collez un lien » que le site, sur votre ordinateur et votre téléphone
- 🛡️ **Zéro tracas** — pas de comptes, pas de publicité, pas de pistage, pas d'installations manuelles ; une seule application gratuite qui fait un seul travail

## 📥 Téléchargement

Récupérez la dernière version pour votre système d'exploitation sur la page [Releases](https://github.com/polpanka/pastydownloader/releases/latest).

## Prérequis

- **Windows** — Windows 10 (64 bits, 1809 ou ultérieur) ou plus récent
- **macOS** — 11 (Big Sur) ou plus récent (Apple Silicon et Intel)
- **Linux** — une distribution avec glibc 2.28+ (par ex. Ubuntu 20.04+, Debian 11+, Fedora 29+, RHEL 8+)
- **Android** — 5.0 (Lollipop, API 21) ou plus récent, arm64

## Pourquoi PastyDownloader

Totalement sûr : pas de virus, pas de publicité, aucun pistage des utilisateurs. Pas de comptes, pas d'extensions de navigateur qui se disputent votre attention. Juste une application légère et gratuite qui fait un seul travail — télécharger — et le fait bien.

## 📱 La version Android

PastyDownloader a commencé sur le bureau, et la version Android n'est pas une application distincte : c'est la même base de code [PySide6](https://www.qt.io/qt-for-python), compilée pour une autre plateforme. De véritables téléchargements yt-dlp s'exécutent sur l'appareil, y compris la fusion réelle de l'audio et de la vidéo grâce à un FFmpeg compilé nativement, et non un substitut allégé.

Cette combinaison est inhabituelle : la plupart des applis yt-dlp pour Android sont des réécritures natives qui ne partagent aucun code avec une version de bureau, et les portages Python qui réutilisent une interface existante ne sont généralement pas construits sur Qt. Amener une application PySide6 complète sur Android — accès au stockage, ponts JNI, service de téléchargement au premier plan, FFmpeg natif — a demandé un effort soutenu.

## 🙏 Remerciements

PastyDownloader repose sur les épaules de quelques formidables projets open source. Un grand merci à leurs mainteneurs et contributeurs :

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — le moteur d'extraction qui donne du sens aux sites de vidéos du web, à l'œuvre discrètement en coulisses de presque chaque téléchargement.
- **[FFmpeg](https://ffmpeg.org)** — la centrale multimédia qui gère le remuxage, la conversion de format et l'encodage MP3.
- **[Qt for Python (PySide6)](https://www.qt.io/qt-for-python)** — la boîte à outils derrière l'interface de bureau.

Sans ces projets, PastyDownloader n'existerait tout simplement pas.

## 🤝 Contribuer

Les rapports de bugs, demandes de fonctionnalités et pull requests sont les bienvenus — voir
[CONTRIBUTING.md](../CONTRIBUTING.md) pour savoir comment signaler un problème, quel est le
périmètre du projet et comment compiler depuis les sources.

## Versions

- **2026-09** - version 1.7 : correction de bugs mineurs
- **2026-08** - version 1.5 : ajout de la version Android
- **2026-07** - version 1.4 : refonte complète en PySide6, publication open source sur GitHub
- **2024-04** - version 0.7 : correction de l'erreur de lien trop long et autres petits correctifs
- **2023-06** - version 0.6 : conversion mp3, prise en charge de Dailymotion, Instagram et TikTok
- **2023-05** - version 0.5 : correction de bugs mineurs
- **2023-04** - version 0.4 : prise en charge du téléchargement de fichiers non vidéo
- **2023-03** - version 0.3 : première version, intégration Pastylink

---

Sous licence [GPLv3](../LICENSE). Voir [TRADEMARK.md](../TRADEMARK.md) pour la politique concernant le nom et le logo.

---

<p align="center">
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml"><img alt="Build Windows" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml"><img alt="Build macOS" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml"><img alt="Build Linux AppImage" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml"><img alt="Build Android APK" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml/badge.svg"></a>
</p>

<p align="center">Conçu pour <a href="https://pasty.link">pasty.link</a></p>
