<p align="center">
  <img src="../src/resources/paste512.png" width="120" alt="PastyDownloader logo">
</p>

<h1 align="center">PastyDownloader</h1>
<p align="center"><i>Pastylink 出品的助手，从网络下载看似不可能的内容</i></p>

<p align="center">作者：<b>Paolo Pancaldi</b></p>

<p align="center">
  <a href="../README.md">🇬🇧 English</a> ·
  <a href="README.it.md">🇮🇹 Italiano</a> ·
  <a href="README.fr.md">🇫🇷 Français</a> ·
  <a href="README.es.md">🇪🇸 Español</a> ·
  <a href="README.de.md">🇩🇪 Deutsch</a> ·
  <b>🇨🇳 简体中文</b> ·
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
  <b>粘贴链接。拿到视频。就这么简单。</b>
</p>

PastyDownloader 是一款快速、直接的应用，用于从网络抓取视频和音频——延续 [pasty.link](https://pasty.link)（Multimedia Discovery Engine）背后同样的"粘贴链接"理念。复制一个链接——或者一整批——按下粘贴，剩下的它来搞定：选择合适的引擎、跟踪进度，并把文件保存到你想要的位置。基于同一套代码，运行于 Windows、macOS、Linux 和 Android。

## ✨ 功能

- 📋 **粘贴任何内容** — 单个链接、一次几十个，或作为纯文本粘贴的整个 HLS 播放列表（`#EXTM3U`）
- 🌐 **数百个站点** — YouTube、Instagram、Facebook 以及数百个其他站点，每个都会被分配到最擅长提取它的方式
- 📡 **直接流** — HLS/m3u8、DASH 和直播流，直接从源下载
- 💬 **自动字幕** — 可用时以应用的语言下载
- 🎵 **5 种格式的音频提取** — MP3、AAC/M4A、FLAC、WAV 或 Opus
- 🔒 **需要登录的内容** — 可以使用你浏览器的 Cookie 来下载需要账号的内容
- 🌍 **说你的语言** — Deutsch、English、Español、Français、Italiano、Nederlands、Português、Русский、العربية、日本語、简体中文、한국어
- 💻 **跨平台** — Windows、macOS、Linux（含 AppImage）和 Android，全部来自同一套代码
- 🔗 **[pasty.link](https://pasty.link) 的伴侣** — 与网站相同的"粘贴链接"流程，在你的电脑和手机上
- 🛡️ **零烦恼** — 无账号、无广告、无追踪、无需手动安装；一个只做一件事的免费应用

## 📥 下载

在 [Releases](https://github.com/polpanka/pastydownloader/releases/latest) 页面获取适用于你操作系统的最新版本。

## 系统要求

- **Windows** — Windows 10（64 位，1809 或更高）或更新版本
- **macOS** — 11（Big Sur）或更新版本（Apple Silicon 和 Intel）
- **Linux** — 带 glibc 2.28+ 的发行版（例如 Ubuntu 20.04+、Debian 11+、Fedora 29+、RHEL 8+）
- **Android** — 5.0（Lollipop，API 21）或更新版本，arm64

## 为什么选择 PastyDownloader

完全安全：没有病毒、没有广告、没有用户追踪。没有账号，没有争抢你注意力的浏览器扩展。只有一个轻量、免费的应用，专注做一件事——下载——并且做得很好。

## 📱 Android 版本

PastyDownloader 起步于桌面端，而 Android 版本并不是一个独立的应用——它是同一套 [PySide6](https://www.qt.io/qt-for-python) 代码，交叉编译而来。真正的 yt-dlp 下载在设备上运行，包括通过原生编译的 FFmpeg 进行真正的音视频合并，而不是一个精简的替代品。

这种组合并不常见：大多数 Android 上的 yt-dlp 应用是不与任何桌面版本共享代码的原生重写，而那些复用现有界面的 Python 移植通常不是基于 Qt 构建的。把一个完整的 PySide6 应用带到 Android——存储访问、JNI 桥接、前台下载服务、原生 FFmpeg——需要持续的努力。

## 🙏 致谢

PastyDownloader 站在一些出色的开源项目的肩膀上。衷心感谢它们的维护者和贡献者：

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — 让网络视频站点变得可解析的提取引擎，在几乎每一次下载的幕后默默运行。
- **[FFmpeg](https://ffmpeg.org)** — 处理重新封装、格式转换和 MP3 编码的媒体主力。
- **[Qt for Python (PySide6)](https://www.qt.io/qt-for-python)** — 桌面界面背后的工具包。

没有这些项目，PastyDownloader 根本不会存在。

## 🤝 参与贡献

欢迎提交错误报告、功能请求和拉取请求——请参阅
[CONTRIBUTING.md](../CONTRIBUTING.md)，了解如何提交 issue、项目范围以及如何从源码构建。

## 版本历史

- **2026-09** - 版本 1.7：小错误修复
- **2026-08** - 版本 1.5：新增 Android 版本
- **2026-07** - 版本 1.4：使用 PySide6 完全重构，在 GitHub 上开源
- **2024-04** - 版本 0.7：修复链接过长的错误及其他小问题
- **2023-06** - 版本 0.6：mp3 转换，支持 Dailymotion、Instagram 和 TikTok
- **2023-05** - 版本 0.5：小错误修复
- **2023-04** - 版本 0.4：新增下载非视频文件的支持
- **2023-03** - 版本 0.3：首次发布，集成 Pastylink

---

基于 [GPLv3](../LICENSE) 授权。名称/徽标政策见 [TRADEMARK.md](../TRADEMARK.md)。

---

<p align="center">
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml"><img alt="Build Windows" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml"><img alt="Build macOS" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml"><img alt="Build Linux AppImage" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml"><img alt="Build Android APK" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml/badge.svg"></a>
</p>

<p align="center">为 <a href="https://pasty.link">pasty.link</a> 打造</p>
