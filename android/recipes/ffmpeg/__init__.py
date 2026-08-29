from pythonforandroid.toolchain import Recipe, current_directory, shprint
from os.path import exists, join, realpath
import sh
from multiprocessing import cpu_count


# PATCH locale (PastyDownloader): copia della recipe ufficiale p4a
# (pythonforandroid/recipes/ffmpeg), unica
# differenza: rimosso `depends = [('sdl2', 'sdl3')]`. Nel sorgente originale
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
    depends = ['openssl']
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

            flags = ['--disable-everything']
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
                # Enable codecs only for .mp4:
                flags += [
                    '--enable-parser=aac,ac3,h261,h264,mpegaudio,mpeg4video,mpegvideo,vc1',
                    '--enable-decoder=aac,h264,mpeg4,mpegvideo',
                    '--enable-muxer=h264,mov,mp4,mpeg2video',
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

            configure = sh.Command('./configure')
            shprint(configure, *flags, _env=env)
            shprint(sh.make, '-j', f"{cpu_count()}", _env=env)
            shprint(sh.make, 'install', _env=env)
            shprint(sh.cp, "ffmpeg", "./lib/libffmpegbin.so")


recipe = FFMpegRecipe()
