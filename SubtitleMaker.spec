# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app\\app.py'],
    pathex=['.'],
    binaries=[('ffmpeg\\ffmpeg.exe', 'ffmpeg'), ('ffmpeg\\ffprobe.exe', 'ffmpeg')],
    datas=[('C:\\Users\\johnc\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\whisper\\assets', 'whisper\\assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SubtitleMaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
