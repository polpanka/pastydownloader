<p align="center">
  <img src="../resources/paste512.png" width="120" alt="PastyDownloader logo">
</p>

<h1 align="center">PastyDownloader</h1>
<p align="center"><i>웹에서 불가능해 보이는 것까지 내려받는 Pastylink 도우미</i></p>

<p align="center">제작: <b>Paolo Pancaldi</b></p>

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
  <b>🇰🇷 한국어</b> ·
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
  <b>링크를 붙여넣으세요. 영상을 받으세요. 그게 전부입니다.</b>
</p>

PastyDownloader는 웹에서 영상과 오디오를 가져오는 빠르고 군더더기 없는 앱으로, Multimedia Discovery Engine인 [pasty.link](https://pasty.link) 뒤에 있는 것과 같은 "링크만 붙여넣기" 철학을 따릅니다. 링크 하나를, 또는 한 무더기를 복사하고 붙여넣기를 누르면 나머지는 앱이 알아서 합니다. 알맞은 엔진을 고르고, 진행 상황을 추적하며, 파일을 원하는 위치에 정확히 저장합니다. 하나의 코드베이스로 Windows, macOS, Linux, Android에서 실행됩니다.

## ✨ 기능

- 📋 **무엇이든 붙여넣기** — 링크 하나, 한 번에 수십 개, 또는 일반 텍스트로 붙여넣은 전체 HLS 재생목록(`#EXTM3U`)
- 🌐 **수백 개의 사이트** — YouTube, Instagram, Facebook을 비롯한 수백 개 사이트가 각각 가장 잘 추출하는 방식으로 라우팅됩니다
- 📡 **다이렉트 스트림** — HLS/m3u8, DASH, 라이브 스트림을 소스에서 바로 내려받습니다
- 💬 **자동 자막** — 가능한 경우 앱 언어로 내려받습니다
- 🎵 **5가지 형식의 오디오 추출** — MP3, AAC/M4A, FLAC, WAV 또는 Opus
- 🔒 **로그인이 필요한 콘텐츠** — 계정이 필요한 콘텐츠를 내려받기 위해 브라우저 쿠키를 사용할 수 있습니다
- 🌍 **당신의 언어로** — Deutsch, English, Español, Français, Italiano, Nederlands, Português, Русский, العربية, 日本語, 简体中文, 한국어
- 💻 **크로스 플랫폼** — Windows, macOS, Linux(AppImage 포함), Android까지 모두 하나의 코드베이스로
- 🔗 **[pasty.link](https://pasty.link)의 동반 앱** — 웹사이트와 동일한 "링크 붙여넣기" 흐름을 컴퓨터와 휴대폰에서
- 🛡️ **번거로움 제로** — 계정 없음, 광고 없음, 추적 없음, 수동 설치 없음. 한 가지 일만 하는 무료 앱 하나

## 📥 다운로드

[Releases](https://github.com/polpanka/pastydownloader/releases/latest) 페이지에서 사용 중인 운영체제용 최신 빌드를 받으세요.

## 요구 사항

- **Windows** — Windows 10(64비트, 1809 이상) 이상
- **macOS** — 11(Big Sur) 이상 (Apple Silicon 및 Intel)
- **Linux** — glibc 2.28+ 배포판 (예: Ubuntu 20.04+, Debian 11+, Fedora 29+, RHEL 8+)
- **Android** — 5.0(Lollipop, API 21) 이상, arm64 (빌드 세부 정보는 [ANDROID.md](../ANDROID.md) 참고)

## 왜 PastyDownloader인가

완전히 안전합니다. 바이러스 없음, 광고 없음, 사용자 추적 없음. 계정도, 주의를 빼앗는 브라우저 확장도 없습니다. 그저 한 가지 일 — 다운로드 — 을 잘 해내는 가볍고 무료인 앱 하나입니다.

## 📱 Android 빌드

PastyDownloader는 데스크톱에서 시작했으며, Android 빌드는 별도의 앱이 아니라 동일한 [PySide6](https://www.qt.io/qt-for-python) 코드베이스를 크로스 컴파일한 것입니다. 실제 yt-dlp 다운로드가 기기에서 실행되며, 네이티브로 컴파일된 FFmpeg를 통한 진짜 오디오·영상 병합도 포함됩니다. 축소된 대체물이 아닙니다.

이런 조합은 드뭅니다. Android용 yt-dlp 앱 대부분은 어떤 데스크톱 버전과도 코드를 공유하지 않는 네이티브 재작성이며, 기존 UI를 재사용하는 Python 포팅도 대개 Qt 위에 만들어지지 않습니다. 완전한 PySide6 앱을 Android로 가져오는 일 — 저장소 접근, JNI 브리지, 포그라운드 다운로드 서비스, 네이티브 FFmpeg — 에는 [ANDROID.md](../ANDROID.md)에 기록된 지속적인 노력이 필요했습니다.

## 🙏 감사의 말

PastyDownloader는 몇몇 훌륭한 오픈 소스 프로젝트의 어깨 위에 서 있습니다. 그 관리자와 기여자들에게 깊이 감사드립니다:

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — 웹의 영상 사이트를 이해하게 해 주는 추출 엔진으로, 거의 모든 다운로드의 뒤에서 조용히 동작합니다.
- **[FFmpeg](https://ffmpeg.org)** — 리먹싱, 형식 변환, MP3 인코딩을 담당하는 미디어 발전소입니다.
- **[Qt for Python (PySide6)](https://www.qt.io/qt-for-python)** — 데스크톱 인터페이스를 뒷받침하는 툴킷입니다.

이 프로젝트들이 없었다면 PastyDownloader는 애초에 존재하지 못했을 것입니다.

## 🤝 기여하기

버그 신고, 기능 요청, 풀 리퀘스트를 환영합니다 — 이슈를 등록하는 방법, 프로젝트 범위,
소스에서 빌드하는 방법은 [CONTRIBUTING.md](../CONTRIBUTING.md)를 참고하세요.

## 릴리스

- **2026-09** - 버전 1.7: 사소한 버그 수정
- **2026-08** - 버전 1.5: Android 빌드 추가
- **2026-07** - 버전 1.4: PySide6로 전면 리팩터링, GitHub에서 오픈 소스 공개
- **2024-04** - 버전 0.7: 너무 긴 링크 오류 및 기타 사소한 버그 수정
- **2023-06** - 버전 0.6: mp3 변환, Dailymotion·Instagram·TikTok 지원
- **2023-05** - 버전 0.5: 사소한 버그 수정
- **2023-04** - 버전 0.4: 영상이 아닌 파일 다운로드 지원 추가
- **2023-03** - 버전 0.3: 첫 릴리스, Pastylink 연동

---

[GPLv3](../LICENSE)에 따라 라이선스가 부여됩니다. 이름/로고 정책은 [TRADEMARK.md](../TRADEMARK.md)를 참고하세요.

---

<p align="center">
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml"><img alt="Build Windows" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml"><img alt="Build macOS" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml"><img alt="Build Linux AppImage" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml"><img alt="Build Android APK" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml/badge.svg"></a>
</p>

<p align="center"><a href="https://pasty.link">pasty.link</a>를 위해 제작됨</p>
