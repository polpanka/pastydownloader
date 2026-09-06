<p align="center">
  <img src="../resources/paste512.png" width="120" alt="PastyDownloader logo">
</p>

<h1 align="center">PastyDownloader</h1>
<p align="center"><i>De Pastylink-helper om het onmogelijke van het web te downloaden</i></p>

<p align="center">Gemaakt door <b>Paolo Pancaldi</b></p>

<p align="center">
  <a href="../README.md">🇬🇧 English</a> ·
  <a href="README.it.md">🇮🇹 Italiano</a> ·
  <a href="README.fr.md">🇫🇷 Français</a> ·
  <a href="README.es.md">🇪🇸 Español</a> ·
  <a href="README.de.md">🇩🇪 Deutsch</a> ·
  <a href="README.zh.md">🇨🇳 简体中文</a> ·
  <a href="README.ja.md">🇯🇵 日本語</a> ·
  <a href="README.pt.md">🇵🇹 Português</a> ·
  <a href="README.ru.md">🇷🇺 Русский</a> ·
  <a href="README.ko.md">🇰🇷 한국어</a> ·
  <b>🇳🇱 Nederlands</b> ·
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
  <b>Plak een link. Krijg je video. Meer niet.</b>
</p>

PastyDownloader is een snelle, no-nonsense app om video en audio van het web te halen — dezelfde "plak een link"-filosofie die achter [pasty.link](https://pasty.link), de Multimedia Discovery Engine, zit. Kopieer een link — of een hele reeks — druk op plakken, en de app regelt de rest: hij kiest de juiste engine, houdt de voortgang bij en slaat het bestand precies op waar jij het wilt. Draait op Windows, macOS, Linux en Android vanuit één codebasis.

## ✨ Functies

- 📋 **Plak van alles** — één link, tientallen tegelijk, of een volledige HLS-afspeellijst (`#EXTM3U`) als platte tekst geplakt
- 🌐 **Honderden sites** — YouTube, Instagram, Facebook en honderden andere, elk doorgestuurd naar wat het het beste ophaalt
- 📡 **Directe streams** — HLS/m3u8, DASH en livestreams, rechtstreeks van de bron gedownload
- 💬 **Automatische ondertitels** — gedownload in de taal van de app wanneer beschikbaar
- 🎵 **Audio-extractie in 5 formaten** — MP3, AAC/M4A, FLAC, WAV of Opus
- 🔒 **Inhoud achter een login** — kan je browsercookies gebruiken om te downloaden wat een account vereist
- 🌍 **Spreekt jouw taal** — Deutsch, English, Español, Français, Italiano, Nederlands, Português, Русский, العربية, 日本語, 简体中文, 한국어
- 💻 **Cross-platform** — Windows, macOS, Linux (AppImage inbegrepen) en Android, allemaal vanuit één codebasis
- 🔗 **Metgezel van [pasty.link](https://pasty.link)** — dezelfde "plak een link"-workflow als de website, op je computer en telefoon
- 🛡️ **Geen gedoe** — geen accounts, geen advertenties, geen tracking, geen handmatige installaties; één gratis app die één taak doet

## 📥 Download

Haal de nieuwste build voor jouw besturingssysteem op via de pagina [Releases](https://github.com/polpanka/pastydownloader/releases/latest).

## Vereisten

- **Windows** — Windows 10 (64-bits, 1809 of later) of nieuwer
- **macOS** — 11 (Big Sur) of nieuwer (Apple Silicon en Intel)
- **Linux** — een distributie met glibc 2.28+ (bijv. Ubuntu 20.04+, Debian 11+, Fedora 29+, RHEL 8+)
- **Android** — 5.0 (Lollipop, API 21) of nieuwer, arm64 (zie [ANDROID.md](../ANDROID.md) voor bouwdetails)

## Waarom PastyDownloader

Volkomen veilig: geen virus, geen advertenties, geen gebruikers-tracking. Geen accounts, geen browserextensies die om je aandacht vechten. Gewoon één lichte, gratis app die één taak doet — downloaden — en dat goed doet.

## 📱 De Android-build

PastyDownloader begon op de desktop, en de Android-build is geen aparte app — het is dezelfde [PySide6](https://www.qt.io/qt-for-python)-codebasis, gecompileerd voor een ander platform. Echte yt-dlp-downloads draaien op het toestel zelf, inclusief het echt samenvoegen van audio en video via een natief gecompileerde FFmpeg, geen uitgeklede vervanger.

Die combinatie is ongebruikelijk: de meeste yt-dlp-apps voor Android zijn natieve herschrijvingen die geen code delen met enige desktopversie, en de Python-ports die een bestaande UI hergebruiken zijn doorgaans niet op Qt gebouwd. Een volledige PySide6-app naar Android brengen — opslagtoegang, JNI-bruggen, een voorgronddownloadservice, natieve FFmpeg — vergde een volgehouden inspanning, gedocumenteerd in [ANDROID.md](../ANDROID.md).

## 🙏 Met dank aan

PastyDownloader staat op de schouders van een aantal fantastische opensourceprojecten. Enorm veel dank aan hun onderhouders en bijdragers:

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — de extractie-engine die de videosites van het web begrijpelijk maakt en stilletjes op de achtergrond van bijna elke download werkt.
- **[FFmpeg](https://ffmpeg.org)** — de mediakrachtcentrale die remuxen, formaatconversie en MP3-codering verzorgt.
- **[Qt for Python (PySide6)](https://www.qt.io/qt-for-python)** — de toolkit achter de desktopinterface.

Zonder deze projecten zou PastyDownloader simpelweg niet bestaan.

## 🤝 Bijdragen

Bugrapporten, functieverzoeken en pull requests zijn welkom — zie
[CONTRIBUTING.md](../CONTRIBUTING.md) voor hoe je een issue indient, wat de reikwijdte van
het project is en hoe je vanuit de broncode bouwt.

## Releases

- **2026-09** - versie 1.7: kleine bugfix
- **2026-08** - versie 1.5: Android-build toegevoegd
- **2026-07** - versie 1.4: volledige refactor in PySide6, opensource gemaakt op GitHub
- **2024-04** - versie 0.7: fout bij te lange links opgelost en andere kleine bugfixes
- **2023-06** - versie 0.6: mp3-conversie, ondersteuning voor Dailymotion, Instagram en TikTok
- **2023-05** - versie 0.5: kleine bugfix
- **2023-04** - versie 0.4: ondersteuning toegevoegd voor het downloaden van niet-videobestanden
- **2023-03** - versie 0.3: eerste release, Pastylink-integratie

---

<p align="center">
Gelicentieerd onder [GPLv3](../LICENSE). Zie [TRADEMARK.md](../TRADEMARK.md) voor het
naam-/logobeleid.
</p>

<p align="center">
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml"><img alt="Build Windows" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml"><img alt="Build macOS" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml"><img alt="Build Linux AppImage" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml"><img alt="Build Android APK" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml/badge.svg"></a>
</p>

<p align="center">Gebouwd voor <a href="https://pasty.link">pasty.link</a></p>
