from pythonforandroid.toolchain import Recipe, current_directory, shprint
from os.path import exists, join, realpath
import sh
from multiprocessing import cpu_count


# PATCH locale (PastyDownloader): copia della recipe ufficiale p4a
# (pythonforandroid/recipes/ffmpeg), con diverse differenze accumulate nel
# tempo (ognuna commentata per esteso dove compare, marcatore "PATCH
# locale") - per il diff completo rispetto all'ufficiale, vedi
# UPSTREAM_DIFF_REFERENCE.patch in questa stessa cartella. La prima e più
# semplice: rimosso `depends = [('sdl2', 'sdl3')]`. Nel sorgente originale
# quel campo serve solo a forzare l'ordine di build ("Need this to build
# correct recipe order", mai referenziato in get_recipe_env/build_arch), ma
# essendo un depends "duro" il risolutore di dipendenze di p4a lo richiede in
# QUALUNQUE grafo valido - col nostro bootstrap qt (niente sdl2/sdl3 nei
# requirements) questo faceva fallire l'intera build con "Didn't find any
# valid dependency graphs", anche se la compilazione vera non tocca mai SDL.
#
# Vive in android/recipes/ (non deployment/recipes/): pysidedeploy.spec
# punta qui col --force, `deployment/` viene ripulita con shutil.rmtree()
# ad ogni run (vedi deploy_lib/deploy_util.py:cleanup) - una recipe li'
# dentro sparirebbe prima ancora che la build parta.
class FFMpegRecipe(Recipe):
    version = '8.0.1'
    # Moved to github.com instead of ffmpeg.org to improve download speed
    url = 'https://www.ffmpeg.org/releases/ffmpeg-{version}.tar.xz'
    # PATCH locale: openssl spostato da opts_depends a depends. Nel
    # sorgente originale era solo opzionale (soft dependency, nessun ordine
    # di build garantito), ma build_arch qui sotto linka -lssl/-lcrypto se
    # 'openssl' compare comunque nel build (sempre vero per noi: serve a
    # Python per requests/aiohttp/certifi via SSL). Verificato con una build
    # reale: senza questo, p4a ha messo ffmpeg PRIMA di openssl nell'ordine
    # finale (['...', 'ffmpeg', 'hostpython3', 'libffi', 'openssl', ...] -
    # opts_depends non garantiva l'edge nel grafo per questa combinazione),
    # facendo fallire ./configure con "ld.lld: error: unable to find
    # library -lssl/-lcrypto" perche' openssl non era ancora compilato
    # PATCH locale: libshine aggiunto per l'encoder MP3 (vedi build_arch
    # sotto e android/recipes/libshine/) - ANDROID_HISTORY.md punto 18/19
    depends = ['openssl', 'libshine']
    opts_depends = ['ffpyplayer_codecs', 'av_codecs']
    patches = ['patches/configure.patch', 'patches/backport-Android15-MediaCodec-fix.patch']
    # PATCH locale: libffmpegbin.so statico, non piu' un eseguibile linkato
    # dinamicamente contro libavcodec.so/libavutil.so/ecc (sorelle nella
    # stessa cartella nativa). Verificato su device reale con readelf: il
    # binario risultava linkato contro LIBAVUTIL_60 ma il libavutil.so
    # bundlato esportava solo fino a LIBAVUTIL_59 (mismatch di symbol
    # versioning interno alla build di ffmpeg, causa non isolata - forse un
    # quirk di --disable-symver con questa combinazione NDK/versione ffmpeg)
    # -> "cannot locate symbol av_default_item_name" a runtime, anche con
    # LD_LIBRARY_PATH impostato correttamente (che infatti trovava il file,
    # falliva solo sulla versione del simbolo). Con tutto statico questa
    # intera classe di problemi (percorsi Y versioni Y namespace del linker)
    # sparisce - stesso approccio gia' usato dalla versione desktop
    # dell'app (ffmpeg_installer.py scarica un binario statico)
    _libs = [
        "libffmpegbin.so",
    ]
    built_libraries = dict.fromkeys(_libs, "./lib")

    def should_build(self, arch):
        build_dir = self.get_build_dir(arch.arch)
        return not exists(join(build_dir, 'lib', 'libffmpegbin.so'))

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        env['NDK'] = self.ctx.ndk_dir
        return env

    def build_arch(self, arch):
        with current_directory(self.get_build_dir(arch.arch)):
            env = arch.get_env()

            # PATCH locale: nella recipe ufficiale p4a questo '--disable-everything'
            # viene scritto qui e poi immediatamente scartato dalla riassegnazione
            # 'flags = [...]' due righe sotto (non 'flags += [...]') - dead code,
            # gia' cosi' anche a monte (verificato contro la recipe ufficiale
            # p4a), non un errore introdotto qui. La build quindi NON riparte
            # da un ffmpeg minimale: usa il set di codec/formati di default di
            # ffmpeg, a cui sotto vengono solo AGGIUNTI extra (openssl,
            # libshine) o abilitate opzioni - le liste
            # --enable-parser/decoder/muxer/demuxer piu' sotto (ramo 'else')
            # NON sono percio' una restrizione effettiva, sono ridondanti col
            # default gia' attivo. Rimosso qui per non suggerire un'intenzione
            # di minimizzazione che non esiste: "fixarlo" per davvero
            # (farlo funzionare sul serio) rischierebbe di disabilitare
            # decoder/demuxer non elencati esplicitamente ma di cui l'app si
            # affida implicitamente oggi (es. webm/vp9/opus, comuni su
            # YouTube) - andrebbe fatto solo con un ripasso dedicato e test
            # per formato, non di sfuggita qui
            cflags = []
            ldflags = []

            # enable hardware acceleration codecs
            flags = [
                '--enable-jni',
                '--enable-mediacodec'
            ]

            if 'openssl' in self.ctx.recipe_build_order:
                flags += [
                    '--enable-version3',
                    '--enable-openssl',
                    '--enable-nonfree',
                    '--enable-protocol=https,tls_openssl',
                ]
                build_dir = Recipe.get_recipe(
                    'openssl', self.ctx).get_build_dir(arch.arch)
                cflags += ['-I' + build_dir + '/include/']
                ldflags += ['-L' + build_dir, '-lssl', '-lcrypto']

            # PATCH locale: encoder MP3 (libshine, vedi android/recipes/
            # libshine/) - a differenza di libx264/libvpx/libshine nel ramo
            # "if" sotto (attivo solo con ffpyplayer_codecs/av_codecs nei
            # requirements, che noi non usiamo), qui va sempre, perche' e'
            # l'unico codec extra che vogliamo (non "abilita tutto" come fa
            # quel ramo). --enable-gpl e' richiesto da libshine stesso
            # (licenza GPL, come --enable-libx264/--enable-libvpx sotto).
            #
            # Linkato a mano via -I/-L/-lshine (come openssl qui sopra),
            # NON via pkg-config: due tentativi falliti prima di trovare
            # questo (vedi ANDROID_HISTORY.md punto 19) hanno scoperto che
            # patches/configure.patch - gia' esistente, scritta per bypassare
            # pkg-config su openssl/x264 perche' inaffidabile in questo
            # ambiente cross-compile - aveva gia' riscritto anche la riga di
            # libshine nel configure di ffmpeg, da
            # "require_pkg_config libshine shine shine/layer3.h
            # shine_encode_buffer" a
            # "require \"shine\" shine/layer3.h shine_encode_buffer -lshine
            # -lm": un controllo manuale (via check_lib/-lshine), non
            # pkg-config. Serve quindi che -lshine si risolva con i normali
            # meccanismi -I/-L del compilatore, non con PKG_CONFIG_PATH
            flags += ['--enable-gpl', '--enable-libshine']
            libshine_build_dir = Recipe.get_recipe(
                'libshine', self.ctx).get_build_dir(arch.arch)
            cflags += ['-I' + libshine_build_dir + '/include/']
            ldflags += ['-L' + libshine_build_dir + '/lib/', '-lshine']

            codecs_opts = {"ffpyplayer_codecs", "av_codecs"}
            if codecs_opts.intersection(self.ctx.recipe_build_order):

                # Enable GPL
                flags += ['--enable-gpl']

                # libx264
                flags += ['--enable-libx264']
                build_dir = Recipe.get_recipe(
                    'libx264', self.ctx).get_build_dir(arch.arch)
                cflags += ['-I' + build_dir + '/include/']
                # Newer versions of FFmpeg prioritize the dynamic library and ignore
                # the static one, unless the static library path is explicitly set.
                ldflags += [build_dir + '/lib/' + 'libx264.a']

                # libshine
                flags += ['--enable-libshine']
                build_dir = Recipe.get_recipe('libshine', self.ctx).get_build_dir(arch.arch)
                cflags += ['-I' + build_dir + '/include/']
                ldflags += ['-lshine', '-L' + build_dir + '/lib/']
                ldflags += ['-lm']

                # libvpx
                flags += ['--enable-libvpx']
                build_dir = Recipe.get_recipe(
                    'libvpx', self.ctx).get_build_dir(arch.arch)
                cflags += ['-I' + build_dir + '/include/']
                ldflags += ['-lvpx', '-L' + build_dir + '/lib/']

                # Enable all codecs:
                flags += [
                    '--enable-parsers',
                    '--enable-decoders',
                    '--enable-encoders',
                    '--enable-muxers',
                    '--enable-demuxers',
                ]
            else:
                # Enable codecs only for .mp4 (+ mp3 muxer, per l'encoder
                # libshine abilitato sopra - senza mp3 in questa lista un
                # '.mp3' in output fallirebbe con "Unknown encoder/muxer"
                # anche con l'encoder disponibile):
                flags += [
                    '--enable-parser=aac,ac3,h261,h264,mpegaudio,mpeg4video,mpegvideo,vc1',
                    '--enable-decoder=aac,h264,mpeg4,mpegvideo',
                    '--enable-muxer=h264,mov,mp4,mpeg2video,mp3',
                    '--enable-demuxer=aac,h264,m4v,mov,mpegvideo,vc1,rtsp',
                ]

            # needed to prevent _ffmpeg.so: version node not found for symbol av_init_packet@LIBAVFORMAT_52
            # /usr/bin/ld: failed to set dynamic section sizes: Bad value
            flags += [
                '--disable-symver',
            ]

            # disable doc
            flags += [
                '--disable-doc',
            ]

            # other flags:
            flags += [
                '--enable-filter=aresample,resample,crop,adelay,volume,scale',
                '--enable-protocol=file,http,hls,udp,tcp',
                '--enable-small',
                '--enable-hwaccels',
                '--enable-pic',
                '--enable-static',
                '--disable-debug',
                '--disable-shared',
            ]

            if 'arm64' in arch.arch:
                arch_flag = 'aarch64'
            elif 'x86' in arch.arch:
                arch_flag = 'x86'
                flags += ['--disable-asm']
            else:
                arch_flag = 'arm'

            # android:
            flags += [
                '--target-os=android',
                '--enable-cross-compile',
                '--cross-prefix={}-'.format(arch.target),
                '--arch={}'.format(arch_flag),
                '--strip={}'.format(self.ctx.ndk.llvm_strip),
                '--nm={}'.format(self.ctx.ndk.llvm_nm),
                # PATCH locale: NDK moderni (r23+) non hanno piu' un ar con
                # prefisso target (aarch64-linux-android21-ar), solo
                # llvm-ar - senza questo configure lo deduce da solo dal
                # cross-prefix e fallisce con "not found" (mai emerso prima
                # con --enable-shared: l'archiviazione statica AR entra in
                # gioco solo con --enable-static, vedi sopra)
                '--ar={}'.format(self.ctx.ndk.llvm_ar),
                '--ranlib={}'.format(self.ctx.ndk.llvm_ranlib),
                # PATCH locale: stesso identico problema di --ar sopra, ma
                # per pkg-config - il default di ffmpeg diventa
                # "<cross-prefix>pkg-config" (vedi pkg_config_default nel
                # configure di ffmpeg), un binario che non esiste da nessuna
                # parte (l'NDK non ne fornisce uno cross-prefissato). Senza
                # questo, "ERROR: shine not found" anche con PKG_CONFIG_PATH
                # giusto (vedi sopra): il comando pkg-config cercato non
                # viene proprio trovato, non e' un problema di percorso .pc
                '--pkg-config=pkg-config',
                '--sysroot={}'.format(self.ctx.ndk.sysroot),
                '--enable-neon',
                '--prefix={}'.format(realpath('.')),
            ]

            if arch_flag == 'arm':
                cflags += [
                    '-Wno-error=incompatible-pointer-types',
                    '-mfpu=vfpv3-d16',
                    '-mfloat-abi=softfp',
                    '-fPIC',
                ]

            env['CFLAGS'] += ' ' + ' '.join(cflags)
            env['LDFLAGS'] += ' ' + ' '.join(ldflags)

            # PATCH locale: se ./configure fallisce, salva il suo vero log
            # diagnostico (ffbuild/config.log - mostra ogni singolo test di
            # libreria/funzione tentato, molto piu' utile del semplice
            # "ERROR: X not found" a schermo) in un posto che sopravvive -
            # pyside6-android-deploy ripulisce .buildozer/ appena la build
            # fallisce, senza questo il log diagnostico andrebbe perso prima
            # di poterlo leggere (successo scoperto a caro prezzo mentre si
            # capiva perche' l'encoder MP3 non si linkava, vedi
            # ANDROID_HISTORY.md punto 19)
            configure = sh.Command('./configure')
            try:
                shprint(configure, *flags, _env=env)
            finally:
                import shutil as _shutil
                config_log_src = 'ffbuild/config.log'
                if exists(config_log_src):
                    _shutil.copy(config_log_src, '/tmp/ffmpeg_config_debug.log')

            shprint(sh.make, '-j', f"{cpu_count()}", _env=env)
            shprint(sh.make, 'install', _env=env)
            shprint(sh.cp, "ffmpeg", "./lib/libffmpegbin.so")


recipe = FFMpegRecipe()
