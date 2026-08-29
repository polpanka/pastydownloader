[app]
title = PastyDownloader
project_dir = .
input_file = main.py
exec_directory = .
project_file = 
icon = resources/paste512.png

[python]
python_path = ~/Documents/www/pastydownloader/.venv-android/bin/python3.11
packages = Nuitka==4.1.1
android_packages = buildozer==1.5.0,cython==0.29.33

[qt]
qml_files = 
excluded_qml_plugins = 
modules = Core,Gui,Widgets
plugins = 

[android]
wheel_pyside = ~/.pyside6_android_deploy/wheels/pyside6-6.11.2-6.11.2-cp311-cp311-android_aarch64.whl
wheel_shiboken = ~/.pyside6_android_deploy/wheels/shiboken6-6.11.2-6.11.2-cp311-cp311-android_aarch64.whl
plugins = platforms_qtforandroid

[nuitka]
macos.permissions = 
mode = onefile
extra_args = --quiet --noinclude-qt-translations

[buildozer]
mode = debug
recipe_dir = ~/Documents/www/pastydownloader/deployment/recipes
jars_dir = ~/Documents/www/pastydownloader/deployment/jar/PySide6/jar
ndk_path = ~/.pyside6_android_deploy/android-ndk/android-ndk-r27c
sdk_path = ~/.pyside6_android_deploy/android-sdk
local_libs = plugins_platforms_qtforandroid
arch = aarch64

