from pythonforandroid.recipe import Recipe
from pythonforandroid.util import current_directory
from pythonforandroid.logger import shprint
from multiprocessing import cpu_count
from os.path import realpath
import sh


# Copia della recipe p4a ufficiale (pythonforandroid/recipes/libshine), con
# due differenze:
#  - libshine come libreria STATICA (.a), non dinamica: la recipe ffmpeg
#    locale la linka dentro l'unico libffmpegbin.so statico (vedi il blocco
#    "MP3 su Android" in android/recipes/ffmpeg/__init__.py).
#  - fixbuild.patch fatto via sed in prebuild_arch invece che come .patch:
#    l'archivio shine ha alcuni file .h con CRLF e GNU patch moderno rifiuta
#    ("different line endings"). Il patch ufficiale fa solo questa modifica.
class LibShineRecipe(Recipe):
    version = 'c72aba9031bde18a0995e7c01c9b53f2e08a0e46'
    url = 'https://github.com/toots/shine/archive/{version}.zip'
    built_libraries = {'libshine.a': 'lib'}

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            shprint(sh.sed, '-i',
                    's/void shine_mdct_initialise();/void shine_mdct_initialise(shine_global_config *config);/',
                    'src/lib/l3mdct.h')

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
