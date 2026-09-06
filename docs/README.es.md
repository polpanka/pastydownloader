<p align="center">
  <img src="../resources/paste512.png" width="120" alt="PastyDownloader logo">
</p>

<h1 align="center">PastyDownloader</h1>
<p align="center"><i>El asistente de Pastylink para descargar lo imposible de la web</i></p>

<p align="center">Creado por <b>Paolo Pancaldi</b></p>

<p align="center">
  <a href="../README.md">🇬🇧 English</a> ·
  <a href="README.it.md">🇮🇹 Italiano</a> ·
  <a href="README.fr.md">🇫🇷 Français</a> ·
  <b>🇪🇸 Español</b> ·
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
  <b>Pega un enlace. Consigue tu vídeo. Eso es todo.</b>
</p>

PastyDownloader es una aplicación rápida y sin complicaciones para descargar vídeo y audio de la web — la misma filosofía de «pega un enlace» que hay detrás de [pasty.link](https://pasty.link), el Multimedia Discovery Engine. Copia un enlace — o un lote entero — pulsa pegar y la app se encarga del resto: elige el motor adecuado, muestra el progreso y guarda el archivo justo donde tú quieras. Funciona en Windows, macOS, Linux y Android desde un único código fuente.

## ✨ Funciones

- 📋 **Pega cualquier cosa** — un solo enlace, decenas a la vez o una lista de reproducción HLS completa (`#EXTM3U`) pegada como texto sin formato
- 🌐 **Cientos de sitios** — YouTube, Instagram, Facebook y cientos más, cada uno dirigido a lo que mejor lo extrae
- 📡 **Streams directos** — HLS/m3u8, DASH y emisiones en directo, descargados directamente desde la fuente
- 💬 **Subtítulos automáticos** — descargados en el idioma de la aplicación cuando están disponibles
- 🎵 **Extracción de audio en 5 formatos** — MP3, AAC/M4A, FLAC, WAV u Opus
- 🔒 **Contenido que requiere inicio de sesión** — puede usar las cookies de tu navegador para descargar lo que necesita una cuenta
- 🌍 **Habla tu idioma** — Deutsch, English, Español, Français, Italiano, Nederlands, Português, Русский, العربية, 日本語, 简体中文, 한국어
- 💻 **Multiplataforma** — Windows, macOS, Linux (AppImage incluida) y Android, todo desde un único código fuente
- 🔗 **Complemento de [pasty.link](https://pasty.link)** — el mismo flujo de «pega un enlace» que la web, en tu ordenador y tu teléfono
- 🛡️ **Cero molestias** — sin cuentas, sin anuncios, sin rastreo, sin instalaciones manuales; una única app gratuita que hace un solo trabajo

## 📥 Descarga

Consigue la última versión para tu sistema operativo en la página de [Releases](https://github.com/polpanka/pastydownloader/releases/latest).

## Requisitos

- **Windows** — Windows 10 (64 bits, 1809 o posterior) o superior
- **macOS** — 11 (Big Sur) o posterior (Apple Silicon e Intel)
- **Linux** — una distribución con glibc 2.28+ (p. ej. Ubuntu 20.04+, Debian 11+, Fedora 29+, RHEL 8+)
- **Android** — 5.0 (Lollipop, API 21) o posterior, arm64 (consulta [ANDROID.md](../ANDROID.md) para los detalles de compilación)

## Por qué PastyDownloader

Completamente seguro: sin virus, sin anuncios, sin seguimiento de usuarios. Sin cuentas, sin extensiones del navegador compitiendo por tu atención. Solo una aplicación ligera y gratuita que hace un único trabajo — descargar — y lo hace bien.

## 📱 La versión de Android

PastyDownloader empezó en el escritorio, y la versión de Android no es una app aparte: es el mismo código [PySide6](https://www.qt.io/qt-for-python), compilado para otra plataforma. Se ejecutan descargas reales de yt-dlp en el dispositivo, incluida la fusión real de audio y vídeo mediante un FFmpeg compilado de forma nativa, no un sustituto recortado.

Esa combinación es poco habitual: la mayoría de las apps de yt-dlp para Android son reescrituras nativas que no comparten código con ninguna versión de escritorio, y los ports de Python que reutilizan una interfaz existente normalmente no están construidos sobre Qt. Llevar una app PySide6 completa a Android — acceso al almacenamiento, puentes JNI, un servicio de descarga en primer plano, FFmpeg nativo — requirió un esfuerzo sostenido, documentado en [ANDROID.md](../ANDROID.md).

## 🙏 Agradecimientos

PastyDownloader se apoya en los hombros de algunos proyectos de código abierto fantásticos. Un enorme agradecimiento a sus mantenedores y colaboradores:

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — el motor de extracción que da sentido a los sitios de vídeo de la web, trabajando en silencio tras casi cada descarga.
- **[FFmpeg](https://ffmpeg.org)** — la central multimedia que se encarga del remux, la conversión de formato y la codificación MP3.
- **[Qt for Python (PySide6)](https://www.qt.io/qt-for-python)** — el conjunto de herramientas tras la interfaz de escritorio.

Sin estos proyectos, PastyDownloader sencillamente no existiría.

## 🤝 Contribuir

Los informes de errores, las solicitudes de funciones y las pull requests son bienvenidos — consulta
[CONTRIBUTING.md](../CONTRIBUTING.md) para saber cómo abrir una incidencia, cuál es el alcance
del proyecto y cómo compilarlo desde el código fuente.

## Versiones

- **2026-09** - versión 1.7: corrección de errores menores
- **2026-08** - versión 1.5: añadida la versión de Android
- **2026-07** - versión 1.4: refactorización completa en PySide6, publicación como código abierto en GitHub
- **2024-04** - versión 0.7: corregido el error de enlace demasiado largo y otras correcciones menores
- **2023-06** - versión 0.6: conversión a mp3, compatibilidad con Dailymotion, Instagram y TikTok
- **2023-05** - versión 0.5: corrección de errores menores
- **2023-04** - versión 0.4: añadida la posibilidad de descargar archivos que no son vídeo
- **2023-03** - versión 0.3: primera versión, integración con Pastylink

---

Distribuido bajo licencia [GPLv3](../LICENSE). Consulta [TRADEMARK.md](../TRADEMARK.md) para la política sobre el nombre y el logotipo.

---

<p align="center">
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml"><img alt="Build Windows" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-windows.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml"><img alt="Build macOS" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-macos.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml"><img alt="Build Linux AppImage" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-linux.yml/badge.svg"></a>
  <a href="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml"><img alt="Build Android APK" src="https://github.com/polpanka/pastydownloader/actions/workflows/build-android.yml/badge.svg"></a>
</p>

<p align="center">Hecho para <a href="https://pasty.link">pasty.link</a></p>
