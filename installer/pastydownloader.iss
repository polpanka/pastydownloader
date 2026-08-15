; Script per Inno Setup (https://jrsoftware.org/isinfo.php) - genera l'installer
; Windows di PastyDownloader a partire dall'output "onedir" di PyInstaller.
;
; USO
; ---
; 1. Compila prima l'app in modalita' onedir (non onefile) con PyInstaller:
;      pyinstaller main_win_installer.spec
;    (NON main_win.spec, che e' onefile e produce un singolo .exe - questo
;    script si aspetta invece dist\PastyDownloader\PastyDownloader.exe con
;    la cartella _internal accanto, vedi main_win_installer.spec)
; 2. Apri questo file con Inno Setup Compiler (o lancia da riga di comando
;    "ISCC.exe installer\pastydownloader.iss" dalla cartella del progetto).
; 3. Il risultato e' bin\PastyDownloader-Setup.exe
;
; Automatizzato in .github/workflows/build-windows.yml, che fa esattamente
; questi passaggi ad ogni build in CI.
;
; NON verificato su Windows (scritto in ambiente Linux, senza Inno Setup a
; disposizione per compilarlo) - alla prima compilazione controlla con calma
; eventuali errori di percorso/sintassi prima di distribuirlo.

; Versione dell'app: tenuta allineata a mano via pastylink dalla pagina api/checkUpdates/,
; come gia' fai per gli altri passi manuali della release (vedi info/info.txt) -
; niente di automatico qui per evitare di introdurre un parsing JSON non
; testato che potrebbe rompere silenziosamente la compilazione dello script
#define MyAppVersion "0.8"
#define MyAppName "PastyDownloader"
#define MyAppPublisher "Pastylink"
#define MyAppURL "https://pasty.link"
#define MyAppExeName "PastyDownloader.exe"

[Setup]
; AppId identifica l'app tra le versioni installate (serve per gli
; aggiornamenti in-place) - generato una volta con Python (uuid.uuid4()),
; NON cambiarlo nelle release successive, altrimenti Windows lo vede come
; un programma diverso invece che un aggiornamento
AppId={{53670135-47A4-4DFC-94C1-7C2B334089DE}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
VersionInfoVersion={#MyAppVersion}

; {autopf}: Program Files se l'installazione e' per tutti gli utenti,
; l'equivalente per-utente se no - vedi PrivilegesRequired sotto
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; niente admin richiesto di default: installa per l'utente corrente, ma
; lascia comunque la possibilita' di scegliere "installa per tutti gli
; utenti" (che a quel punto chiedera' i privilegi admin solo se richiesto)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog

; l'app e i suoi binari (ffmpeg/yt-dlp) sono tutti a 64 bit, vedi la
; conversazione sulla compatibilita' - niente da installare su Windows a 32 bit.
; "x64compatible" richiede Inno Setup 6.3+: se la tua versione e' piu' vecchia
; e ISCC si lamenta di non riconoscerlo, sostituiscilo con il vecchio "x64"
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; l'output di PyInstaller (soprattutto ffmpeg/yt-dlp bundlati) e' gia'
; compresso di suo - ricomprimerlo con lzma/max rallenta la build per un
; guadagno minimo, "fast" e' un buon compromesso
Compression=lzma2/fast
SolidCompression=yes

OutputDir=..\bin
OutputBaseFilename={#MyAppName}-Setup
SetupIconFile=..\resources\favicon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern

; lingue incluse di default nell'installazione di Inno Setup - copre buona
; parte delle 7 lingue gia' supportate dall'app stessa (testi.py); cinese e
; giapponese richiedono i file .isl aggiuntivi (non bundlati di default con
; Inno Setup), aggiungili se ti servono davvero nell'installer.
; Se ISCC da' errore "file not found" su uno di questi .isl, vuol dire che
; la tua installazione di Inno Setup non li include: cancella semplicemente
; la riga incriminata, non e' un problema bloccante
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; tutta la cartella onedir di PyInstaller (exe + _internal con librerie,
; plugin Qt, ffmpeg.exe/yt-dlp.exe bundlati) - ignoreversion perche' sono
; file interni dell'app, non librerie condivise di sistema da preservare
Source: "..\dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

; Note per versioni future di questo script (non incluse qui per restare
; verificabili al primo tentativo):
;  - Pulizia disinstallazione: {localappdata}\Pastylink\ffmpeg e
;    \Pastylink\yt-dlp (le versioni scaricate in autonomia da YtDlpUpdater)
;    non vengono toccate di proposito - sono innocue da lasciare, e la
;    cartella download dell'utente (Desktop\Pastylink) va lasciata sempre
;    stare, non e' roba dell'installer.
;  - Rilevare un'istanza di PastyDownloader gia' in esecuzione prima di
;    installare/disinstallare richiederebbe una sezione [Code] in Pascal
;    Script - omessa qui apposta, non avendo modo di testarla su Windows.
