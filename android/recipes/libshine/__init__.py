from pythonforandroid.recipe import Recipe
from pythonforandroid.util import current_directory
from pythonforandroid.logger import shprint
from multiprocessing import cpu_count
from os.path import realpath
import sh


# PATCH locale (PastyDownloader): copia della recipe ufficiale p4a
# (pythonforandroid/recipes/libshine, patch fixbuild.patch inclusa
# invariata), unica differenza: costruisce libshine come libreria STATICA
# (.a) invece che dinamica (.so, `--enable-shared`/`--disable-static`
# nell'originale). Serve alla recipe ffmpeg locale (android/recipes/ffmpeg/)
# per l'encoder MP3 (`--enable-libshine`, vedi build_arch li') - ffmpeg qui
# e' compilato interamente statico in un unico libffmpegbin.so apposta per
# evitare mismatch di versioning dei simboli fra .so separate (vedi
# ANDROID_HISTORY.md punto "ffmpeg-kit"): una libshine.so a parte
# reintrodurrebbe esattamente quella classe di problema. install_libraries()
# di p4a (recipe.py) copia nell'APK solo i file che finiscono in ".so" - un
# .a dichiarato in built_libraries viene quindi trovato/verificato ma MAI
# imbarcato separatamente, resta solo una dipendenza di link per ffmpeg
class LibShineRecipe(Recipe):
    version = 'c72aba9031bde18a0995e7c01c9b53f2e08a0e46'
    url = 'https://github.com/toots/shine/archive/{version}.zip'
    patches = ["fixbuild.patch"]
    built_libraries = {'libshine.a': 'lib'}

    def get_recipe_env(self, arch=None, with_flags_in_cc=True):
        env = super().get_recipe_env(arch, with_flags_in_cc)
        # technically, libraries should go to `LDLIBS`, but it seems
        # that libshine doesn't like so, and it will fail on linking stage
        env['LDLIBS'] = env['LDLIBS'].replace(' -lm', '')
        env['LDFLAGS'] += ' -lm'
        return env

    def build_arch(self, arch):
        with current_directory(self.get_build_dir(arch.arch)):
            env = self.get_recipe_env(arch)
            shprint(sh.Command('./bootstrap'))
            configure = sh.Command('./configure')
            shprint(configure,
                    f'--host={arch.command_prefix}',
                    '--enable-pic',
                    # PATCH locale: statico invece di dinamico, vedi commento
                    # sopra la classe
                    '--enable-static',
                    '--disable-shared',
                    f'--prefix={realpath(".")}',
                    _env=env)
            shprint(sh.make, '-j', str(cpu_count()), _env=env)
            shprint(sh.make, 'install', _env=env)


recipe = LibShineRecipe()
