<p align="center">
  <img src="../src/resources/paste512.png" width="120" alt="PastyDownloader logo">
</p>

<h1 align="center">PastyDownloader</h1>
<p align="center"><i>Der Pastylink-Helfer, um das Unmögliche aus dem Web herunterzuladen</i></p>

<p align="center">Erstellt von <b>Paolo Pancaldi</b></p>

<p align="center">
  <a href="../README.md">🇬🇧 English</a> ·
  <a href="README.it.md">🇮🇹 Italiano</a> ·
  <a href="README.fr.md">🇫🇷 Français</a> ·
  <a href="README.es.md">🇪🇸 Español</a> ·
  <b>🇩🇪 Deutsch</b> ·
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
  <b>Link einfügen. Video erhalten. Fertig.</b>
</p>

PastyDownloader ist eine schnelle, unkomplizierte App, um Video und Audio aus dem Web zu holen — dieselbe „Link einfügen"-Philosophie, die auch hinter [pasty.link](https://pasty.link), der Multimedia Discovery Engine, steht. Kopiere einen Link — oder gleich einen ganzen Schwung — drücke auf Einfügen, und die App erledigt den Rest: Sie wählt die richtige Engine, zeigt den Fortschritt an und speichert die Datei genau dort, wo du sie haben willst. Läuft auf Windows, macOS, Linux und Android aus einer einzigen Codebasis.

## ✨ Funktionen

- 📋 **Alles einfügen** — einen einzelnen Link, Dutzende auf einmal oder eine ganze HLS-Playlist (`#EXTM3U`) als reinen Text eingefügt
- 🌐 **Hunderte Seiten** — YouTube, Instagram, Facebook und hunderte weitere, jede an das weitergeleitet, was sie am besten extrahiert
- 📡 **Direkte Streams** — HLS/m3u8, DASH und Live-Streams, direkt von der Quelle heruntergeladen
- 💬 **Automatische Untertitel** — in der Sprache der App heruntergeladen, sofern verfügbar
- 🎵 **Audio-Extraktion in 5 Formaten** — MP3, AAC/M4A, FLAC, WAV oder Opus
- 🔒 **Inhalte mit Anmeldepflicht** — kann deine Browser-Cookies nutzen, um herunterzuladen, was ein Konto erfordert
- 🌍 **Spricht deine Sprache** — Deutsch, English, Español, Français, Italiano, Nederlands, Português, Русский, العربية, 日本語, 简体中文, 한국어
- 💻 **Plattformübergreifend** — Windows, macOS, Linux (AppImage inklusive) und Android, alles aus einer Codebasis
- 🔗 **Begleiter zu [pasty.link](https://pasty.link)** — derselbe „Link einfügen"-Ablauf wie auf der Website, auf deinem Rechner und Handy
- 🛡️ **Kein Ärger** — keine Konten, keine Werbung, kein Tracking, keine manuellen Installationen; eine kostenlose App, die genau eine Aufgabe erledigt

## 📥 Download

Hol dir den aktuellsten Build für dein Betriebssystem von der Seite [Releases](https://github.com/polpanka/pastydownloader/releases/latest).

## Voraussetzungen

- **Windows** — Windows 10 (64-Bit, 1809 oder neuer) oder neuer
- **macOS** — 11 (Big Sur) oder neuer (Apple Silicon und Intel)
- **Linux** — eine Distribution mit glibc 2.28+ (z. B. Ubuntu 20.04+, Debian 11+, Fedora 29+, RHEL 8+)
- **Android** — 5.0 (Lollipop, API 21) oder neuer, arm64

## Warum PastyDownloader

Vollkommen sicher: kein Virus, keine Werbung, kein Nutzer-Tracking. Keine Konten, keine Browser-Erweiterungen, die um deine Aufmerksamkeit buhlen. Nur eine schlanke, kostenlose App, die genau eine Aufgabe erledigt — herunterladen — und das gut.

## 📱 Der Android-Build

PastyDownloader begann auf dem Desktop, und der Android-Build ist keine separate App — es ist dieselbe [PySide6](https://www.qt.io/qt-for-python)-Codebasis, für eine andere Plattform kompiliert. Echte yt-dlp-Downloads laufen auf dem Gerät, einschließlich echtem Zusammenführen von Audio und Video über ein nativ kompiliertes FFmpeg, kein abgespeckter Ersatz.

Diese Kombination ist ungewöhnlich: Die meisten yt-dlp-Apps für Android sind native Neuentwicklungen, die keinen Code mit einer Desktop-Version teilen, und die Python-Ports, die eine vorhandene Oberfläche wiederverwenden, sind in der Regel nicht auf Qt aufgebaut. Eine vollständige PySide6-App auf Android zu bringen — Speicherzugriff, JNI-Brücken, ein Vordergrund-Download-Dienst, natives FFmpeg — erforderte anhaltende Arbeit.

## 🙏 Danksagungen

PastyDownloader steht auf den Schultern einiger fantastischer Open-Source-Projekte. Großer Dank an ihre Maintainer und Beitragenden:

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — die Extraktions-Engine, die den Videoseiten des Webs einen Sinn abringt und bei fast jedem Download leise im Hintergrund arbeitet.
- **[FFmpeg](https://ffmpeg.org)** — das Medien-Kraftwerk, das Remuxing, Formatkonvertierung und MP3-Kodierung übernimmt.
- **[Qt for Python (PySide6)](https://www.qt.io/qt-for-python)** — das Toolkit hinter der Desktop-Oberfläche.

Ohne diese Projekte würde PastyDownloader schlicht nicht existieren.

## 🤝 Mitwirken

Fehlerberichte, Funktionswünsche und Pull Requests sind willkommen — siehe
[CONTRIBUTING.md](../CONTRIBUTING.md) für Hinweise, wie man ein Issue meldet, was der
Projektumfang ist und wie man aus dem Quellcode baut.

## Releases

- **2026-09** - Version 1.7: kleinere Fehlerbehebung
- **2026-08** - Version 1.5: Android-Build hinzugefügt
- **2026-07** - Version 1.4: komplettes Refactoring in PySide6, Open-Source-Veröffentlichung auf GitHub
- **2024-04** - Version 0.7: Fehler bei zu langen Links behoben und weitere kleinere Fehlerbehebungen
- **2023-06** - Version 0.6: mp3-Konvertierung, Unterstützung für Dailymotion, Instagram und TikTok
- **2023-05** - Version 0.5: kleinere Fehlerbehebung
- **2023-04** - Version 0.4: Unterstützung zum Herunterladen von Nicht-Video-Dateien hinzugefügt
- **2023-03** - Version 0.3: erste Veröffentlichung, Pastylink-Integration

---

Lizenziert unter [GPLv3](../LICENSE). Siehe [TRADEMARK.md](../TRADEMARK.md) für die Namens- und Logo-Richtlinie.

---

<p align="center">
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml"><img alt="Build Windows" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml"><img alt="Build macOS" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml"><img alt="Build Linux AppImage" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml"><img alt="Build Android APK" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml/badge.svg"></a>
</p>

<p align="center">Gebaut für <a href="https://pasty.link">pasty.link</a></p>
