#!/bin/bash
#
# USO
# ---
#   ./build-appimage.sh
#
# Nessun parametro, nessuna variabile d'ambiente da impostare, nessun comando
# da lanciare prima: e' uno script "one-shot", si lancia e basta, da dentro
# la cartella del progetto (o anche da fuori: fa da solo cd nella cartella
# in cui si trova questo file). Alla fine produce:
#
#   bin/PastyDownloader-x86_64.AppImage
#
# che si esegue direttamente, senza installazione:
#
#   chmod +x bin/PastyDownloader-x86_64.AppImage   # di solito gia' eseguibile
#   ./bin/PastyDownloader-x86_64.AppImage
#
# COSA SERVE GIA' PRESENTE (nessuna delle due richiede sudo/apt)
# ---------------------------------------------------------------
#   - python3 con il modulo "venv" (quasi sempre gia' incluso: NON serve il
#     pacchetto apt python3-venv ne' che ensurepip funzioni, vedi sotto)
#   - curl e una connessione a internet (scarica PySide6/PyInstaller da
#     PyPI e linuxdeploy/appimagetool da GitHub - qualche centinaio di MB)
#
# NON serve FUSE: linuxdeploy/appimagetool sono a loro volta AppImage, ma
# girano tramite APPIMAGE_EXTRACT_AND_RUN (vedi sotto) - utile soprattutto
# in CI (es. GitHub Actions), dove i runner di solito non hanno FUSE
# disponibile di default
#
# COSA FA IN AUTONOMIA (non serve preparare nulla prima)
# -------------------------------------------------------
#   - crea un virtualenv Python usa-e-getta in una cartella temporanea e ci
#     installa dentro tutte le dipendenze (PySide6, aiofiles, aiohttp,
#     psutil, requests, PyInstaller) - non tocca ne' l'installazione Python
#     di sistema ne' un eventuale altro venv gia' presente
#   - rigenera resources.py, compila con PyInstaller, scarica ed esegue
#     linuxdeploy + appimagetool (che bundlano anche le dipendenze di sistema
#     - X11/xcb, glib, dbus, fontconfig... - che PyInstaller da solo non
#     porta con se', e senza le quali l'app rischia di non partire su una
#     distro diversa da quella di build), e pulisce la cartella temporanea
#     alla fine (anche in caso di errore, vedi il trap piu' sotto)
#
# Nota su main_appimage.spec: e' una variante "onedir" (una cartella con
# l'exe e le sue .so accanto) di main_unix.spec (che invece produce un
# onefile che si autoestrae a runtime). Per l'AppImage serve onedir: e'
# l'unico modo per far ispezionare a linuxdeploy le librerie reali.
set -euo pipefail
cd "$(dirname "$0")"

# controllo rapido dei prerequisiti, con un messaggio chiaro invece di un
# errore a meta' script se manca qualcosa
for cmd in python3 curl; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Manca '$cmd', necessario per questo script." >&2; exit 1; }
done

# fa eseguire linuxdeploy/appimagetool via autoestrazione in un tmpdir invece
# che montarsi tramite FUSE - identico risultato, ma funziona anche dove FUSE
# non c'e' (container Docker, runner CI) senza doverlo verificare/installare
export APPIMAGE_EXTRACT_AND_RUN=1

BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

# venv usa-e-getta (--without-pip: ensurepip spesso non e' disponibile senza
# il pacchetto apt python3-venv, quindi salto il suo tentativo automatico e
# bootstrappo pip io stesso subito dopo con get-pip.py ufficiale)
echo "== 1/6: venv + dipendenze =="
python3 -m venv --without-pip "$BUILD_DIR/venv"
curl -sL https://bootstrap.pypa.io/get-pip.py -o "$BUILD_DIR/get-pip.py"
"$BUILD_DIR/venv/bin/python" "$BUILD_DIR/get-pip.py"
"$BUILD_DIR/venv/bin/python" -m pip install --upgrade \
    PySide6 aiofiles aiohttp psutil requests pyinstaller

# rigenero resources.py con lo stesso PySide6 appena installato nel venv,
# cosi' il formato binario e' sempre coerente con la versione usata per la build
echo "== 2/6: rigenero resources.py con la stessa versione di PySide6 =="
"$BUILD_DIR/venv/bin/pyside6-rcc" resources.qrc -o resources.py

# --distpath/--workpath fuori dal progetto: cosi' git status resta pulito,
# nessun output di build finisce sotto controllo di versione per errore
echo "== 3/6: PyInstaller (onedir) =="
"$BUILD_DIR/venv/bin/pyinstaller" \
    --distpath "$BUILD_DIR/dist" --workpath "$BUILD_DIR/pywork" --noconfirm \
    main_appimage.spec

# tool ufficiali AppImage, presi dal canale "continuous" (sempre l'ultima build)
echo "== 4/6: scarico linuxdeploy + appimagetool =="
mkdir -p "$BUILD_DIR/tools"
curl -sL -o "$BUILD_DIR/tools/linuxdeploy" \
    https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
curl -sL -o "$BUILD_DIR/tools/appimagetool" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x "$BUILD_DIR/tools/linuxdeploy" "$BUILD_DIR/tools/appimagetool"

# copio l'intera cartella onedir di PyInstaller (exe + _internal/) dentro
# l'AppDir - linuxdeploy ha bisogno di vederli entrambi assieme
echo "== 5/6: costruisco l'AppDir =="
APPDIR="$BUILD_DIR/AppDir"
mkdir -p "$APPDIR/usr/bin"
cp -r "$BUILD_DIR/dist/PastyDownloader"/* "$APPDIR/usr/bin/"

# icona: resources/paste512.png e' gia' quadrata e nella risoluzione giusta
# (AppImage vuole una delle risoluzioni standard, es. 256x256/512x512
cp resources/paste512.png "$BUILD_DIR/pastydownloader.png"

# desktop file richiesto da linuxdeploy per generare AppRun/icona nell'AppDir
cat > "$BUILD_DIR/pastydownloader.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=PastyDownloader
Comment=Multimedia Discovery Engine
Exec=PastyDownloader
Icon=pastydownloader
Categories=Network;FileTransfer;
Terminal=false
EOF

# rimuovo il plugin immagini TIFF: alla dipendenza libtiff.so.5 manca sempre
# (non e' mai stata bundlata da PyInstaller), e l'app non lo usa comunque -
# se resta, fa fallire tutto il passo successivo di linuxdeploy
rm -f "$APPDIR/usr/bin/_internal/PySide6/Qt/plugins/imageformats/libqtiff.so"

# rimuovo i plugin "platform" per sistemi embedded/headless-GPU (eglfs,
# framebuffer Linux, EGL minimale, Vulkan KHR display, VNC): l'app desktop
# reale usa solo xcb (X11) o wayland, questi non vengono mai caricati a runtime
# ma le loro dipendenze di sistema (libEGL.so.1, libvulkan.so.1...) non sono
# installate sul runner nudo - se restano, fanno fallire linuxdeploy allo
# stesso modo di libqtiff.so sopra. Tengo invece libqxcb/libqwayland (uso
# reale), libqminimal (fallback minuscolo e innocuo) e libqoffscreen (usato
# dal controllo "parte senza crash" qui sotto e dai test, via QT_QPA_PLATFORM=offscreen)
for plugin in libqeglfs libqlinuxfb libqminimalegl libqvkkhrdisplay libqvnc; do
    rm -f "$APPDIR/usr/bin/_internal/PySide6/Qt/plugins/platforms/$plugin.so"
done

# linuxdeploy: PySide6 non fornisce un qmake reale, quindi il suo plugin
# "qt" (che lo richiede per trovare Qt) non e' utilizzabile - non serve
# comunque, perche' PyInstaller ha gia' bundlato Qt e tutti i suoi plugin.
# Quello che manca davvero e' fare analizzare a linuxdeploy le dipendenze
# di SISTEMA di quei plugin (X11/xcb/glib/dbus/fontconfig...), passandoli
# esplicitamente con --library
LIBS=()
for f in \
    "$APPDIR"/usr/bin/_internal/PySide6/Qt/plugins/platforms/*.so \
    "$APPDIR"/usr/bin/_internal/PySide6/Qt/plugins/imageformats/*.so \
    "$APPDIR"/usr/bin/_internal/PySide6/Qt/plugins/xcbglintegrations/*.so \
    "$APPDIR"/usr/bin/_internal/PySide6/Qt/plugins/platformthemes/*.so \
    "$APPDIR"/usr/bin/_internal/PySide6/Qt/plugins/platforminputcontexts/*.so ; do
    [ -f "$f" ] && LIBS+=(--library "$f")
done

# primo giro: bundla solo le dipendenze di sistema dei plugin elencati sopra
"$BUILD_DIR/tools/linuxdeploy" --appdir "$APPDIR" "${LIBS[@]}"

# secondo giro: solo desktop-file/icona/AppRun (va fatto separatamente perche'
# il primo giro, senza --desktop-file/--icon-file, non li tocca affatto)
"$BUILD_DIR/tools/linuxdeploy" --appdir "$APPDIR" \
    --desktop-file "$BUILD_DIR/pastydownloader.desktop" \
    --icon-file "$BUILD_DIR/pastydownloader.png"

# impacchetto l'AppDir completo nel singolo file .AppImage finale
echo "== 6/6: genero l'AppImage =="
ARCH=x86_64 "$BUILD_DIR/tools/appimagetool" "$APPDIR" bin/PastyDownloader-x86_64.AppImage

echo
echo "Fatto: bin/PastyDownloader-x86_64.AppImage"
