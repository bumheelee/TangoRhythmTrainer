# -*- mode: python ; coding: utf-8 -*-
# macOS build spec: produces dist/TangoMusicScoreGenerator.app
from PyInstaller.utils.hooks import collect_all, collect_submodules

packages = [
    'librosa', 'soundfile', 'numpy', 'scipy', 'numba',
    'llvmlite', 'audioread', 'pooch', 'soxr',
]

# Logo shown in the GUI header (icon is applied to the .app bundle below).
datas = [('maximo_logo.png', '.'), ('maximo_icon.ico', '.')]
binaries = []
hiddenimports = []
for pkg in packages:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass
hiddenimports += collect_submodules('librosa')

analysis = Analysis(
    ['tango_music_score_gui.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

# onedir layout inside the .app (faster start-up and more reliable than onefile on macOS)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name='TangoMusicScoreGenerator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name='TangoMusicScoreGenerator',
)

app = BUNDLE(
    coll,
    name='TangoMusicScoreGenerator.app',
    icon='maximo_icon.icns',
    bundle_identifier='com.maximotango.musicscoregenerator',
    info_plist={
        'CFBundleName': 'Tango Music Score Generator',
        'CFBundleDisplayName': 'Tango Music Score Generator',
        'CFBundleShortVersionString': '2.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
    },
)
