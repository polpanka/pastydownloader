<p align="center">
  <img src="../resources/paste512.png" width="120" alt="PastyDownloader logo">
</p>

<h1 align="center">PastyDownloader</h1>
<p align="center"><i>O ajudante do Pastylink para baixar o impossível da web</i></p>

<p align="center">Criado por <b>Paolo Pancaldi</b></p>

<p align="center">
  <a href="../README.md">🇬🇧 English</a> ·
  <a href="README.it.md">🇮🇹 Italiano</a> ·
  <a href="README.fr.md">🇫🇷 Français</a> ·
  <a href="README.es.md">🇪🇸 Español</a> ·
  <a href="README.de.md">🇩🇪 Deutsch</a> ·
  <a href="README.zh.md">🇨🇳 简体中文</a> ·
  <a href="README.ja.md">🇯🇵 日本語</a> ·
  <b>🇵🇹 Português</b> ·
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
  <b>Cole um link. Receba o seu vídeo. É só isso.</b>
</p>

O PastyDownloader é um aplicativo rápido e sem complicações para baixar vídeo e áudio da web — a mesma filosofia do "cole um link" que existe por trás do [pasty.link](https://pasty.link), o Multimedia Discovery Engine. Copie um link — ou um lote inteiro — toque em colar, e ele cuida do resto: escolhe o mecanismo certo, acompanha o progresso e salva o arquivo exatamente onde você quiser. Roda no Windows, macOS, Linux e Android a partir de um único código-fonte.

## ✨ Recursos

- 📋 **Cole qualquer coisa** — um único link, dezenas de uma vez ou uma playlist HLS inteira (`#EXTM3U`) colada como texto puro
- 🌐 **Centenas de sites** — YouTube, Instagram, Facebook e centenas de outros, cada um encaminhado para o que melhor o extrai
- 📡 **Streams diretos** — HLS/m3u8, DASH e transmissões ao vivo, baixados diretamente da fonte
- 💬 **Legendas automáticas** — baixadas no idioma do aplicativo quando disponíveis
- 🎵 **Extração de áudio em 5 formatos** — MP3, AAC/M4A, FLAC, WAV ou Opus
- 🔒 **Conteúdo que exige login** — pode usar os cookies do seu navegador para baixar o que precisa de uma conta
- 🌍 **Fala o seu idioma** — Deutsch, English, Español, Français, Italiano, Nederlands, Português, Русский, العربية, 日本語, 简体中文, 한국어
- 💻 **Multiplataforma** — Windows, macOS, Linux (AppImage incluído) e Android, tudo a partir de um único código-fonte
- 🔗 **Companheiro do [pasty.link](https://pasty.link)** — o mesmo fluxo de "cole um link" do site, no seu computador e no seu celular
- 🛡️ **Zero incômodo** — sem contas, sem anúncios, sem rastreamento, sem instalações manuais; um único aplicativo gratuito que faz um só trabalho

## 📥 Download

Baixe a versão mais recente para o seu sistema operacional na página de [Releases](https://github.com/polpanka/pastydownloader/releases/latest).

## Requisitos

- **Windows** — Windows 10 (64 bits, 1809 ou posterior) ou mais recente
- **macOS** — 11 (Big Sur) ou mais recente (Apple Silicon e Intel)
- **Linux** — uma distribuição com glibc 2.28+ (ex.: Ubuntu 20.04+, Debian 11+, Fedora 29+, RHEL 8+)
- **Android** — 5.0 (Lollipop, API 21) ou mais recente, arm64 (consulte [ANDROID.md](../ANDROID.md) para detalhes de compilação)

## Por que o PastyDownloader

Totalmente seguro: sem vírus, sem anúncios, sem rastreamento de usuários. Sem contas, sem extensões de navegador disputando a sua atenção. Apenas um aplicativo leve e gratuito que faz um só trabalho — baixar — e o faz bem.

## 📱 A versão Android

O PastyDownloader começou no desktop, e a versão Android não é um aplicativo separado — é o mesmo código-fonte [PySide6](https://www.qt.io/qt-for-python), compilado para outra plataforma. Downloads reais do yt-dlp são executados no dispositivo, incluindo a junção real de áudio e vídeo por meio de um FFmpeg compilado nativamente, e não um substituto reduzido.

Essa combinação é incomum: a maioria dos aplicativos de yt-dlp para Android são reescritas nativas que não compartilham código com nenhuma versão de desktop, e os ports em Python que reaproveitam uma interface existente geralmente não são construídos sobre Qt. Levar um aplicativo PySide6 completo para o Android — acesso ao armazenamento, pontes JNI, um serviço de download em primeiro plano, FFmpeg nativo — exigiu um esforço prolongado, documentado em [ANDROID.md](../ANDROID.md).

## 🙏 Agradecimentos

O PastyDownloader se apoia nos ombros de alguns projetos de código aberto fantásticos. Muito obrigado aos seus mantenedores e colaboradores:

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — o mecanismo de extração que dá sentido aos sites de vídeo da web, trabalhando silenciosamente nos bastidores de quase todo download.
- **[FFmpeg](https://ffmpeg.org)** — a potência de mídia que cuida do remux, da conversão de formato e da codificação de MP3.
- **[Qt for Python (PySide6)](https://www.qt.io/qt-for-python)** — o kit de ferramentas por trás da interface de desktop.

Sem esses projetos, o PastyDownloader simplesmente não existiria.

## 🤝 Contribuindo

Relatórios de bugs, pedidos de recursos e pull requests são bem-vindos — consulte
[CONTRIBUTING.md](../CONTRIBUTING.md) para saber como abrir uma issue, qual é o escopo do
projeto e como compilar a partir do código-fonte.

## Versões

- **2026-09** - versão 1.7: correção de bugs menores
- **2026-08** - versão 1.5: adicionada a versão Android
- **2026-07** - versão 1.4: refatoração completa em PySide6, código aberto no GitHub
- **2024-04** - versão 0.7: corrigido o erro de link longo demais e outras correções menores
- **2023-06** - versão 0.6: conversão para mp3, suporte a Dailymotion, Instagram e TikTok
- **2023-05** - versão 0.5: correção de bugs menores
- **2023-04** - versão 0.4: adicionado suporte para baixar arquivos que não são vídeo
- **2023-03** - versão 0.3: primeiro lançamento, integração com o Pastylink

---

<p align="center">
Licenciado sob a [GPLv3](../LICENSE). Consulte [TRADEMARK.md](../TRADEMARK.md) para a
política de nome/logotipo.
</p>

<p align="center">
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml"><img alt="Build Windows" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml"><img alt="Build macOS" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml"><img alt="Build Linux AppImage" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml"><img alt="Build Android APK" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml/badge.svg"></a>
</p>

<p align="center">Feito para o <a href="https://pasty.link">pasty.link</a></p>
