<p align="center">
  <img src="../src/resources/paste512.png" width="120" alt="PastyDownloader logo">
</p>

<h1 align="center">PastyDownloader</h1>
<p align="center"><i>ウェブから「不可能」をダウンロードする Pastylink のヘルパー</i></p>

<p align="center">作者: <b>Paolo Pancaldi</b></p>

<p align="center">
  <a href="../README.md">🇬🇧 English</a> ·
  <a href="README.it.md">🇮🇹 Italiano</a> ·
  <a href="README.fr.md">🇫🇷 Français</a> ·
  <a href="README.es.md">🇪🇸 Español</a> ·
  <a href="README.de.md">🇩🇪 Deutsch</a> ·
  <a href="README.zh.md">🇨🇳 简体中文</a> ·
  <b>🇯🇵 日本語</b> ·
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
  <b>リンクを貼る。動画が手に入る。それだけ。</b>
</p>

PastyDownloader は、ウェブから動画や音声を取得するための、速くて余計なもののないアプリです。Multimedia Discovery Engine である [pasty.link](https://pasty.link) の背後にある「リンクを貼るだけ」という考え方をそのまま受け継いでいます。リンクを 1 つ、あるいはまとめてコピーし、貼り付けを押すだけで、あとはアプリが処理します。適切なエンジンを選び、進捗を追跡し、ファイルをあなたが望む場所に正確に保存します。単一のコードベースから Windows、macOS、Linux、Android で動作します。

## ✨ 特徴

- 📋 **何でも貼り付け** — 1 つのリンク、一度に数十個、あるいはプレーンテキストとして貼り付けた HLS プレイリスト全体（`#EXTM3U`）
- 🌐 **数百のサイト** — YouTube、Instagram、Facebook をはじめとする数百のサイト。それぞれ最も適した方法へ振り分けられます
- 📡 **ダイレクトストリーム** — HLS/m3u8、DASH、ライブ配信を、ソースから直接ダウンロード
- 💬 **字幕の自動取得** — 利用可能な場合、アプリの言語でダウンロード
- 🎵 **5 つの形式での音声抽出** — MP3、AAC/M4A、FLAC、WAV、Opus
- 🔒 **ログインが必要なコンテンツ** — ブラウザの Cookie を使って、アカウントが必要なものをダウンロード可能
- 🌍 **あなたの言語で** — Deutsch、English、Español、Français、Italiano、Nederlands、Português、Русский、العربية、日本語、简体中文、한국어
- 💻 **クロスプラットフォーム** — Windows、macOS、Linux（AppImage 同梱）、Android を、すべて 1 つのコードベースから
- 🔗 **[pasty.link](https://pasty.link) のコンパニオン** — ウェブサイトと同じ「リンクを貼るだけ」の流れを、あなたのパソコンとスマートフォンで
- 🛡️ **手間ゼロ** — アカウント不要、広告なし、追跡なし、手動インストール不要。1 つの仕事だけをこなす無料アプリ

## 📥 ダウンロード

お使いの OS 向けの最新ビルドを [Releases](https://github.com/polpanka/pastydownloader/releases/latest) ページから入手してください。

## 動作要件

- **Windows** — Windows 10（64 ビット、1809 以降）以降
- **macOS** — 11（Big Sur）以降（Apple Silicon および Intel）
- **Linux** — glibc 2.28 以上のディストリビューション（例: Ubuntu 20.04+、Debian 11+、Fedora 29+、RHEL 8+）
- **Android** — 5.0（Lollipop、API 21）以降、arm64

## なぜ PastyDownloader か

完全に安全: ウイルスなし、広告なし、ユーザー追跡なし。アカウント不要、注意を奪い合うブラウザ拡張機能もありません。ただ 1 つの仕事 — ダウンロード — をこなし、それをうまくやる、軽量で無料のアプリです。

## 📱 Android ビルド

PastyDownloader はデスクトップから始まりました。Android ビルドは別のアプリではなく、同じ [PySide6](https://www.qt.io/qt-for-python) のコードベースをクロスコンパイルしたものです。本物の yt-dlp によるダウンロードが端末上で実行され、ネイティブにコンパイルされた FFmpeg による本物の音声・映像の結合も行われます。簡略化された代替物ではありません。

この組み合わせは珍しいものです。Android 向けのほとんどの yt-dlp アプリは、どのデスクトップ版ともコードを共有しないネイティブの書き直しであり、既存の UI を再利用する Python の移植版も、たいてい Qt の上には構築されていません。完全な PySide6 アプリを Android へ — ストレージアクセス、JNI ブリッジ、フォアグラウンドのダウンロードサービス、ネイティブ FFmpeg — 持ち込むには、継続的な取り組みが必要でした。

## 🙏 謝辞

PastyDownloader は、いくつかの素晴らしいオープンソースプロジェクトの肩の上に立っています。メンテナーとコントリビューターの皆さんに心から感謝します:

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — ウェブの動画サイトを解釈する抽出エンジン。ほぼすべてのダウンロードの裏側で静かに動いています。
- **[FFmpeg](https://ffmpeg.org)** — 再多重化、形式変換、MP3 エンコードを担うメディアの主力。
- **[Qt for Python (PySide6)](https://www.qt.io/qt-for-python)** — デスクトップインターフェースを支えるツールキット。

これらのプロジェクトがなければ、PastyDownloader はそもそも存在しませんでした。

## 🤝 コントリビュート

バグ報告、機能リクエスト、プルリクエストを歓迎します。issue の立て方、プロジェクトの範囲、
ソースからのビルド方法については [CONTRIBUTING.md](../CONTRIBUTING.md) を参照してください。

## リリース

- **2026-09** - バージョン 1.7: 軽微なバグ修正
- **2026-08** - バージョン 1.5: Android ビルドを追加
- **2026-07** - バージョン 1.4: PySide6 での全面的なリファクタリング、GitHub でオープンソース化
- **2024-04** - バージョン 0.7: リンクが長すぎるエラーを修正、その他の軽微な修正
- **2023-06** - バージョン 0.6: mp3 変換、Dailymotion・Instagram・TikTok のサポート
- **2023-05** - バージョン 0.5: 軽微なバグ修正
- **2023-04** - バージョン 0.4: 動画以外のファイルのダウンロードに対応
- **2023-03** - バージョン 0.3: 初回リリース、Pastylink 連携

---

[GPLv3](../LICENSE) のもとでライセンスされています。名称・ロゴのポリシーについては [TRADEMARK.md](../TRADEMARK.md) を参照してください。

---

<p align="center">
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml"><img alt="Build Windows" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml"><img alt="Build macOS" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml"><img alt="Build Linux AppImage" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml"><img alt="Build Android APK" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml/badge.svg"></a>
</p>

<p align="center"><a href="https://pasty.link">pasty.link</a> のために作られました</p>
