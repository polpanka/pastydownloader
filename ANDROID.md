# Esperimento: guscio Android

Proof of concept per capire quanto è lontana la UI PySide6 di PastyDownloader
da un APK che almeno si apre su Android. **Nessun download funziona**: ffmpeg,
yt-dlp e gli aggiornamenti automatici sono disattivati di proposito (vedi
`Constants.SHELL_ONLY_MODE` in `constants.py`) — l'obiettivo è solo vedere la
finestra principale su un device/emulatore.

Richiede un host Linux o macOS (`pyside6-android-deploy` non gira su Windows).

## 1. Ambiente Python (serve 3.11, non 3.12)

`buildozer` (usato sotto il cofano da `pyside6-android-deploy`) richiede
Python 3.11 o inferiore sull'host che esegue il tool di deploy — non è il
Python che gira dentro l'APK (quello è cross-compilato a parte), è proprio
l'interprete che lancia lo script. Se hai solo 3.12 di sistema:

```bash
sudo apt install python3.11 python3.11-venv
```

Poi il venv dedicato:

```bash
python3.11 -m venv .venv-android
source .venv-android/bin/activate
pip install pyside6==6.11.2
pip install -r .venv-android/lib/python3.11/site-packages/PySide6/scripts/requirements-android.txt
```

(Se anche `python3.11-venv` manca e non hai subito accesso a `sudo`, un
`virtualenv` bundlato con PyCharm funziona allo stesso modo senza bisogno del
pacchetto di sistema: `python3.11 /opt/pycharm-*/plugins/python-ce/helpers/virtualenv-py3.pyz .venv-android`.)

## 2. NDK/SDK Android (una tantum)

```bash
git clone --depth 1 https://code.qt.io/pyside/pyside-setup /tmp/pyside-setup
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64   # o dove sta la tua JDK
pip install -r /tmp/pyside-setup/tools/cross_compile_android/requirements.txt
python /tmp/pyside-setup/tools/cross_compile_android/main.py \
  --download-only --skip-update --auto-accept-license
```

Scarica NDK e SDK in `~/.pyside6_android_deploy` (**underscore**, non
trattino — la doc ufficiale in un punto lo scrive diverso, occhio).
`JAVA_HOME` deve essere valorizzato esplicitamente: lo script cerca una JDK
ma non trova quella di sistema solo con `java` in PATH, serve la env var.

Nel nostro run: NDK scaricato è r27c (non r26b come suggerisce
`pyside6-android-deploy --help` per "required version" — sembra solo testo
informativo non aggiornato, il download automatico ha preso r27c senza
lamentarsi).

## 3. Wheel PySide6/Shiboken6 per Android

`qtpip download PySide6 --android --arch aarch64` **non funziona senza un
account Qt commerciale** (si blocca con "Commercial License NOT found").
Le wheel open source si scaricano dirette, senza alcun account, da:

```bash
curl -O https://download.qt.io/official_releases/QtForPython/pyside6/pyside6-6.11.2-6.11.2-cp311-cp311-android_aarch64.whl
curl -O https://download.qt.io/official_releases/QtForPython/shiboken6/shiboken6-6.11.2-6.11.2-cp311-cp311-android_aarch64.whl
```

Nota: le wheel Android partono dalla **6.8** — la 6.7.3 (quella su cui è
pinnato il desktop, vedi i workflow `.github/workflows/build-*.yml`) non ha
build Android. Per l'esperimento va bene una versione più recente (qui 6.11.2,
la stessa installata nel venv di deploy) visto che è un venv/toolchain
separato dal build desktop.

## 4. Generare pysidedeploy.spec

**Non scrivere lo spec a mano copiando dalla documentazione** — meglio farlo
generare dal tool stesso ed editarlo, perché la sintassi ha due bug non
documentati (vedi sotto):

```bash
pyside6-android-deploy --init \
  --wheel-pyside "$HOME/.pyside6_android_deploy/wheels/pyside6-6.11.2-6.11.2-cp311-cp311-android_aarch64.whl" \
  --wheel-shiboken "$HOME/.pyside6_android_deploy/wheels/shiboken6-6.11.2-6.11.2-cp311-cp311-android_aarch64.whl" \
  -f
```

Poi a mano: `title = PastyDownloader`, `icon` puntato a
`resources/paste512.png`.

### Bug 1 — il commento nello spec va con `/`, non `#` né `;`

Il generatore (`--init`) scrive commenti con `#`, ma il parser che rilegge
`pysidedeploy.spec` (diverso da quello usato per `buildozer.spec`, che invece
accetta `#`) di default riconosce solo `/` come prefisso commento
(`config.py`, classe `Config.__init__`, parametro `comment_prefixes: str =
"/"`, mai sovrascritto per `AndroidConfig`). Il file che il tool stesso genera
**non si rilegge** con le sue impostazioni di default — fallisce con
`configparser.MissingSectionHeaderError`. Soluzione: niente commenti dentro
`pysidedeploy.spec`, le spiegazioni stanno solo qui.

### Bug 2 — `ndk_path`/`sdk_path` nello spec vengono ignorati se il file già esiste

In `android_config.py`, la lettura di `ndk_path`/`sdk_path` dal file di
config è dentro un `elif not existing_config_file:` — cioè gira **solo** la
prima volta che lo spec viene creato, mai nelle esecuzioni successive con
`--config-file` su un file già esistente. Risultato: anche con i valori giusti
scritti nello spec, il tool prova a scaricare di nuovo NDK/SDK o crasha
(`TypeError: unsupported operand type(s) for /: 'NoneType' and 'str'`).
Soluzione: passare **sempre** `--wheel-pyside`/`--wheel-shiboken`/
`--ndk-path`/`--sdk-path` anche da riga di comando, pure quando si usa
`--config-file`:

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
pyside6-android-deploy --config-file pysidedeploy.spec \
  --wheel-pyside "$HOME/.pyside6_android_deploy/wheels/pyside6-6.11.2-6.11.2-cp311-cp311-android_aarch64.whl" \
  --wheel-shiboken "$HOME/.pyside6_android_deploy/wheels/shiboken6-6.11.2-6.11.2-cp311-cp311-android_aarch64.whl" \
  --ndk-path "$HOME/.pyside6_android_deploy/android-ndk/android-ndk-r27c" \
  --sdk-path "$HOME/.pyside6_android_deploy/android-sdk"
```

## 5. Dry-run (verificato) e build vera

`--dry-run --force` con i comandi sopra è stato verificato e passa pulito:
analizza le librerie Qt con `llvm-readobj`, poi pianifica `pip install
cython==0.29.33`, `buildozer init`, `buildozer android debug`.

Per la build vera, togliere `--dry-run`. È il passo lungo/pesante (prima
build di `buildozer` scarica ulteriori toolchain, compila ricette native,
Gradle scarica le sue dipendenze) — non ancora eseguito in questo esperimento.

```bash
pyside6-android-deploy --config-file pysidedeploy.spec \
  --wheel-pyside "$HOME/.pyside6_android_deploy/wheels/pyside6-6.11.2-6.11.2-cp311-cp311-android_aarch64.whl" \
  --wheel-shiboken "$HOME/.pyside6_android_deploy/wheels/shiboken6-6.11.2-6.11.2-cp311-cp311-android_aarch64.whl" \
  --ndk-path "$HOME/.pyside6_android_deploy/android-ndk/android-ndk-r27c" \
  --sdk-path "$HOME/.pyside6_android_deploy/android-sdk" \
  --force
```

Produce un `.apk` nella directory del progetto. Installalo con
`adb install -r nome.apk` su un device con debug USB attivo, o trascinalo
nell'emulatore Android Studio.

## 6. Build vera: log dei tentativi

Primo tentativo (`buildozer android debug`) fallito subito, prima di
scaricare/compilare qualunque cosa di pesante (disco invariato):

```
zlib headers must be installed, run: sudo apt-get install zlib1g-dev
```

`buildozer`/python-for-android tipicamente richiede diverse librerie di
sviluppo di sistema oltre a questa (`libffi-dev`, `libssl-dev`, `autoconf`,
`libtool`, `pkg-config`, ...) - da installarle una alla volta man mano che
si presentano invece che in blocco, per non rischiare nomi pacchetto non
piu' validi su Ubuntu 24.04.

Secondo tentativo, dopo `zlib1g-dev`: passato oltre zlib, fermato su un altro
requisito di sistema - `javac` non trovato. Sul sistema c'era solo
`openjdk-21-jre` (runtime), non il JDK completo:

```
sudo apt-get install openjdk-21-jdk
```

Anche questo fallito prima di consumare disco/tempo significativi.

Terzo tentativo, dopo il JDK: superato molto di piu' (clone di
python-for-android, download di Apache ANT, SDK/NDK trovati - NDK r27c
scaricato contro un r28c "raccomandato" da p4a, solo informativo, non ha
bloccato nulla), poi fermato su:

```
sdkmanager path ".../android-sdk/tools/bin/sdkmanager" does not exist, sdkmanager is not installed
```

Causa: lo script di download NDK/SDK (punto 2) mette `cmdline-tools`
direttamente sotto `android-sdk/`, ma sia `sdkmanager` stesso sia
`buildozer` (legacy) si aspettano il layout
`android-sdk/cmdline-tools/latest/bin/...`. Fix in due parti:

```bash
SDK=~/.pyside6_android_deploy/android-sdk
mv "$SDK/cmdline-tools" "$SDK/cmdline-tools-tmp"
mkdir -p "$SDK/cmdline-tools"
mv "$SDK/cmdline-tools-tmp" "$SDK/cmdline-tools/latest"

mkdir -p "$SDK/tools/bin"
for f in "$SDK/cmdline-tools/latest/bin/"*; do
  ln -s "../../cmdline-tools/latest/bin/$(basename "$f")" "$SDK/tools/bin/$(basename "$f")"
done
```

Attenzione: il symlink va fatto sui **singoli file** dentro `tools/bin/`,
non sulla cartella `bin` intera - lo script `sdkmanager` risolve da solo i
symlink per calcolare la propria posizione (`APP_HOME`), ma lo fa testando
`-h` sul file invocato, non su una directory intermedia symlinkata. Un
symlink di directory produce un `ClassNotFoundException` (APP_HOME sbagliato,
classpath non trovato) invece dell'errore "sdk root" corretto.

Quarto tentativo, dopo il fix sdkmanager: superato tutto l'SDK/NDK setup,
arrivato a compilare l'host Python di bootstrap per la cross-compilazione
(python-for-android). Fermato su:

```
configure: error: no acceptable C compiler found in $PATH
```

```
sudo apt install build-essential
```

Disco ancora invariato (60GB liberi) anche a questo punto - il fallimento e'
prima della compilazione vera e propria pesante.

Quinto tentativo, dopo `build-essential`: e' entrato davvero nella
compilazione (host Python di bootstrap completato, 7600+ righe di log),
fermato sulla recipe `libffi` per arm64-v8a:

```
autogen.sh: 2: exec: autoreconf: not found
```

```
sudo apt install autoconf automake libtool
```

Disco ancora invariato (60GB) anche qui.

Sesto tentativo, dopo `autoconf`/`automake` (il pacchetto `libtool` non
serve un binario `libtool` di sistema, solo `libtoolize` - lo script
`autogen.sh` genera lui lo script `libtool` locale): **build completata**.

```
BUILD SUCCESSFUL in 48s
# Android packaging done!
# APK PastyDownloader-0.1-arm64-v8a-debug.apk available in the bin directory
```

APK valido, 150MB, nella root del progetto
(`PastyDownloader-0.1-arm64-v8a-debug.apk`). Disco sceso di soli 2GB (58GB
liberi rimasti) - mai stato un problema reale in tutto l'esperimento.

**Verificato su device reale (installata via `adb install`)**: si apre e si
chiude subito. `adb logcat` mostra la causa:

```
UnsatisfiedLinkError: dlopen failed: library "libpython3.11.so" not found:
needed by .../libshiboken6.abi3.so
```

L'APK conteneva `libpython3.14.so`: la recipe `python3` di
python-for-android ha `version = '3.14.2'` hardcoded di default (l'ultima
CPython disponibile), ma le wheel PySide6/Shiboken6 scaricate sono `cp311`
(Python 3.11). `pyside6-android-deploy` non espone questo pin tramite
`pysidedeploy.spec` - e' hardcoded in
`deploy_lib/android/buildozer.py:27` (`requirements =
"python3,shiboken6,PySide6"`, senza versione). Patchato a mano nel venv:

```python
self.set_value("app", "requirements",
               "python3==3.11.16,hostpython3==3.11.16,shiboken6,PySide6")
```

(serve pinnare **anche** `hostpython3`, non solo `python3` - sono due
recipe separate che p4a pretende combacino esattamente, altrimenti fallisce
con `python3 should have same version as hostpython3, 3.11.16 != 3.14.2`
prima ancora di ricompilare).

Questo e' un fix nel venv di deploy (`.venv-android`, fuori dal repo), da
rifare se il venv viene ricreato da zero - vedi il punto 1 di questo file.

**Aggiornamento - la UI Qt funziona davvero su Android.** Dopo aver risolto
il mismatch di versione Python (sopra), l'app crashava ancora, ma non piu'
per problemi nativi: `ModuleNotFoundError: No module named 'requests'`,
prima da `libs.py` poi da `pasted_url.py` - entrambi fanno `import requests`
a livello di modulo (mai dentro una funzione), e nessuno dei due file ha
una recipe/wheel per requests nel build Android (l'approccio "aggiungilo ai
requirements" e' stato scartato per colpa di `psutil`, vedi sopra - stessa
causa, path diverso). Fix: spostati tutti gli import di `requests`,
`aiohttp`, `aiofiles`, `psutil` da import globali a **import locali dentro
le singole funzioni che li usano**, in `libs.py` e `pasted_url.py`. Nessuna
di quelle funzioni viene mai chiamata quando `SHELL_ONLY_MODE` e' attivo
(sono tutte nei percorsi ffmpeg/yt-dlp/download gia' saltati), quindi
l'import non scatta mai a runtime sul guscio Android - e sul desktop il
comportamento resta identico (stesso identico import, solo spostato da
module-level a function-level, pattern Python normale).

Con questo fix (build precedente, prima del percorso di salvataggio Android):
**l'app si apre, resta viva, e mostra un vero dialogo Qt**
(`QMessageBox`, testo leggibile, bottone OK funzionante) - non un crash.
Il dialogo e' "The download folder is not accessible"
(`MyText.downloadPathError`, controllato in `main.py:checkDownloadFolder`),
perche' `Tools.downloadPath()` (`libs.py:407`) costruisce il percorso come
`~/Desktop/Pastylink` - una convenzione da desktop che su Android non ha
senso (niente "Desktop", e `os.path.expanduser('~')` punta comunque alla
sandbox privata dell'app). Esattamente il problema di storage/scoped-storage
previsto fin dall'inizio di questo esperimento - la UI Qt e i dialoghi
funzionano, il prossimo vero lavoro (fuori scope per questo POC) sarebbe
un percorso di salvataggio Android-aware (SAF/MediaStore), non altri fix
di build.

**Percorso di salvataggio Android** (`Tools.downloadPath()`, `libs.py`): su
Android non ha senso `~/Desktop/Pastylink` (niente "Desktop", e
`os.path.expanduser('~')` punta comunque alla sandbox privata dell'app).
Scelta consapevole: cartella privata dell'app
(`context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)`, via
`Constants.IS_ANDROID`) invece della vera cartella Download condivisa - zero
permessi richiesti e funziona subito, ma i file non sono visibili
nell'app Files/Galleria dell'utente senza sapere dove cercarli
(`Android/data/org.../files/Download`). L'alternativa vera (MediaStore, file
visibili normalmente) richiederebbe gestire ffmpeg separatamente perché non
puo' scrivere su uno stream MediaStore, solo su un path filesystem - scartata
per questo esperimento, restava "malissimo ma funzionante" comunque.

Per chiamare le API Android da Python serve `pyjnius` (modulo `jnius`) - **non
incluso di default nel bootstrap "qt"** di python-for-android (lo e' invece in
quello Kivy). Va aggiunto ai requirements:

```python
self.set_value("app", "requirements",
               "python3==3.11.16,hostpython3==3.11.16,shiboken6,PySide6,pyjnius")
```

Con `pyjnius` nei requirements, la build ha triggerato per la prima volta un
passaggio non ancora esercitato prima (pip install di `patchelf`/`setuptools`
per l'hostpython3 ricompilato da zero) che ha rivelato un'altra dipendenza di
sistema mancante:

```
SSLError("Can't connect to HTTPS URL because the SSL module is not available.")
```

Causa: manca `libssl-dev` di sistema - l'hostpython3 che il tool ricompila da
sorgente ha bisogno delle librerie di sviluppo OpenSSL dell'host per abilitare
`_ssl`, a differenza del Python di sistema (gia' pronto/precompilato da
Ubuntu, non ha questo problema). Fix:

```
sudo apt install libssl-dev
```

**Aggiornamento - `pyjnius` non funziona col bootstrap "qt".** Con
`pyjnius` nei requirements e `context.getExternalFilesDir(...)` via
`jnius.autoclass`, l'app crashava con:

```
ImportError: dlopen failed: cannot locate symbol "WebView_AndroidGetJNIEnv"
referenced by ".../jnius/jnius.so"
```

Causa: `WebView_AndroidGetJNIEnv` (la funzione C che pyjnius usa per
agganciarsi al `JNIEnv` del thread corrente) e' definita solo nei bootstrap
Kivy `webview`/`service_only` di python-for-android
(`bootstraps/webview/build/jni/application/src/pyjniusjni.c`) - il
bootstrap `qt` (quello che usiamo, obbligato da `pyside6-android-deploy`)
non la fornisce. Portarla nel bootstrap qt sarebbe fattibile in teoria (e'
un file C autonomo, non dipende da nulla di specifico del bootstrap
webview) ma richiederebbe patchare il sorgente di python-for-android che
viene clonato/purgato ad ogni build - fuori scope per questo esperimento.

**Fix reale usato**: il bootstrap qt imposta gia' da solo, come env var di
processo, `ANDROID_PRIVATE` = `getFilesDir().getAbsolutePath()` (storage
interno privato dell'app) - vedi
`bootstraps/qt/build/src/main/java/org/kivy/android/PythonActivity.java`.
Nessun JNI, nessun permesso, puro `os.environ['ANDROID_PRIVATE']` da
Python. `pyjnius` tolto di nuovo dai requirements (non serve piu', ed era
comunque la fonte del problema). E' storage interno (`getFilesDir()`), non
external (`getExternalFilesDir()`): ancora meno visibile all'utente della
prima scelta, ma funziona senza intoppi.

**Risultato finale: successo.** Con questo fix l'app si apre e mostra la
**finestra principale completa** - bottone "Paste and Download", griglia
con colonne Url/Status/SaveAs/Action, tutta l'interfaccia desktop
renderizzata nativamente da Qt su un device Android reale (Xiaomi/HyperOS,
`rodin`/`2412DPC0AG`). Nessun crash, nessun dialogo d'errore.

Riepilogo di tutto cio' che ha richiesto arrivarci, in ordine:
Python 3.11 (non 3.12) sull'host, `zlib1g-dev`, `openjdk-21-jdk`,
`build-essential`, `autoconf`/`automake`, `libssl-dev`; due bug del tool
`pyside6-android-deploy` aggirati (sintassi commenti nello spec,
`ndk_path`/`sdk_path` ignorati su config esistente); layout SDK
`cmdline-tools/latest` sistemato con symlink mirati; versione Python target
pinnata a 3.11.16 (`python3==3.11.16,hostpython3==3.11.16`) per matchare le
wheel PySide6/Shiboken6 cp311; import di `requests`/`aiohttp`/`aiofiles`/
`psutil` resi locali in `libs.py` e `pasted_url.py` (mai a livello di
modulo); percorso di salvataggio riscritto per Android usando
`ANDROID_PRIVATE` (storage interno privato, no JNI, no permessi) al posto
di `~/Desktop/Pastylink`.

Per provare l'APK su un device Android reale:

```bash
adb install -r PastyDownloader-0.1-arm64-v8a-debug.apk
```

su un device con debug USB attivo, o trascinando l'APK in un emulatore
Android Studio.

## Cosa aspettarsi che si rompa ancora

- **La build vera stessa**: fermata al primo giro su una dipendenza di
  sistema mancante (vedi sopra), non ancora arrivata alla parte di
  compilazione nativa/Gradle vera e propria - quello resta il punto dove ci
  si aspetta il prossimo intoppo serio (versioni Gradle/AGP, spazio disco per
  le sue cache).
- **`QFileDialog.getExistingDirectory`** in `settings.py` — su Android non
  c'è un vero filesystem selezionabile liberamente (scoped storage); qui non
  è stato toccato, quindi probabilmente non funziona o non è raggiungibile.
- **Percorsi di `resources/*.png`** — caricati via path relativo, da
  verificare che vengano estratti correttamente dal pacchetto.
- **Menu contestuale (tasto destro) nella griglia** (`grid.py`) — su touch
  non c'è un equivalente diretto, resterà semplicemente irraggiungibile.

Se anche solo la finestra vuota si apre, l'esperimento ha già risposto alla
domanda "quanto siamo lontani".
