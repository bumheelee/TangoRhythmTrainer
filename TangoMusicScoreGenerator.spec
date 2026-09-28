# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

# librosa has a number of dynamically imported modules/data files.
# Collect its package tree and the numerical/audio dependencies explicitly.
packages = [
    'librosa',
    'soundfile',
    'numpy',
    'scipy',
    'numba',
    'llvmlite',
    'audioread',
    'pooch',
    'soxr',
]

# Bundle the Maximo Tango logo (shown in the GUI header / window icon).
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

# Safely collect remaining librosa submodules.
hiddenimports += collect_submodules('librosa')

# Application modules are imported normally.

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
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name='TangoMusicScoreGenerator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='maximo_icon.ico',
)
