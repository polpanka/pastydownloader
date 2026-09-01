<p align="center">
  <img src="resources/paste512.png" width="120" alt="PastyDownloader logo">
</p>

<h1 align="center">PastyDownloader</h1>
<p align="center"><i>The Pastylink helper to download the impossible from the Web</i></p>

<p align="center">
  <a href="https://github.com/polpanka/pastydownloader/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/polpanka/pastydownloader?include_prereleases"></a>
  <a href="LICENSE"><img alt="License: GPLv3" src="https://img.shields.io/badge/license-GPLv3-blue.svg"></a>
  <img alt="Platforms" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Android-lightgrey">
</p>

<p align="center">
  <b>Paste a link. Get your video. That's it.</b>
</p>

PastyDownloader is a fast, no-nonsense app for grabbing video and audio from the web — the same paste-a-link philosophy behind [pasty.link](https://pasty.link), the Multimedia Discovery Engine. Copy a link — or a whole batch of them — hit paste, and it figures out the rest: picks the right engine, tracks progress, and saves the file exactly where you want it. Runs on Windows, macOS, Linux, and Android from a single codebase.

## ✨ Features

- 📋 **Paste anything** — single links, multiple links at once, or a whole HLS playlist (`#EXTM3U`) pasted as raw text
- 🎯 **Smart engine detection** — routes each link automatically to whatever handles it best: YouTube, TikTok, Instagram, Facebook, Vimeo, Dailymotion and more; direct streaming links (HLS/m3u8, raw video)
- 📦 **Batch downloads** — queue as many links as you want, watch live progress per item, stop one or stop them all
- 🎵 **Audio conversion** — convert to MP3 after download, keeping or discarding the source video
- 🖱️ **Right-click power** — copy link, re-download, convert, stop, or remove, straight from the grid
- ⚡ **Zero hassle** — everything it needs is fetched automatically on first run, no manual installs, no PATH wrangling; internal libraries keep themselves up to date in the background
- 🌍 **Speaks your language** — detects your OS language on first launch (Deutsch, English, Español, Français, Italiano, Nederlands, Português, Русский, العربية, 日本語, 简体中文, 한국어)
- 💻 **Cross-platform** — Windows, macOS, Linux (AppImage included), and Android, all from one PySide6 codebase (see below)
- 🔗 **[pasty.link](https://pasty.link) integration** — send links straight from the website into the app with one click

## 📥 Download

Grab the latest build for your OS from the [Releases](https://github.com/polpanka/pastydownloader/releases/latest) page.

## Requirements

- **Windows** — Windows 10 (64-bit, 1809 or later) or later
- **macOS** — 11 (Big Sur) or later (Apple Silicon and Intel)
- **Linux** — a distro with glibc 2.28+ (e.g. Ubuntu 20.04+, Debian 11+, Fedora 29+, RHEL 8+)
- **Android** — 5.0 (Lollipop, API 21) or later, arm64 (see [ANDROID.md](ANDROID.md) for build details)

## Why PastyDownloader

Completely safe: no virus, no ads, no user tracking. No accounts, no browser extensions fighting for your attention. Just one lightweight, free app that does a single job — downloading — and does it well.

## 📱 The Android build

PastyDownloader started on the desktop, and the Android build is not a separate app — it is the same [PySide6](https://www.qt.io/qt-for-python) codebase, cross-compiled. Real yt-dlp downloads run on-device, including genuine audio+video merging through a natively-compiled FFmpeg, not a stripped-down substitute.

That combination is unusual: most yt-dlp apps for Android are native rewrites that share no code with any desktop version, and the Python ports that do reuse an existing UI generally aren't built on Qt. Bringing a full PySide6 app to Android — storage access, JNI bridges, a foreground download service, native FFmpeg — took a sustained effort documented in [ANDROID.md](ANDROID.md).

## 🙏 Acknowledgements

PastyDownloader stands on the shoulders of some fantastic open source projects. Huge thanks to their maintainers and contributors:

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — the extraction engine that makes sense of the web's video sites, running quietly behind the scenes of almost every download.
- **[FFmpeg](https://ffmpeg.org)** — the media powerhouse handling remuxing, format conversion, and MP3 encoding.
- **[Qt for Python (PySide6)](https://www.qt.io/qt-for-python)** — the toolkit behind the desktop interface.

Without these projects, PastyDownloader simply wouldn't exist.

## Releases

- **2026-09** - version 1.6: minor bug fix
- **2026-08** - version 1.5: Android build added
- **2026-07** - version 1.4: complete refactor in PySide6, open-sourced on GitHub
- **2024-04** - version 0.7: fixed too long link error and other minor bug fixes
- **2023-06** - version 0.6: mp3 conversion, Dailymotion Instagram and TikTok support
- **2023-05** - version 0.5: minor bug fix
- **2023-04** - version 0.4: added support to download non-video files
- **2023-03** - version 0.3: first release, Pastylink integration

---

Licensed under [GPLv3](LICENSE). See [TRADEMARK.md](TRADEMARK.md) for the
name/logo policy.

<p align="center">Built for <a href="https://pasty.link">pasty.link</a></p>
