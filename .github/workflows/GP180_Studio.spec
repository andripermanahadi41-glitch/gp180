# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gp180_studio.py'],
    pathex=['.'],
    binaries=[],
    datas=[('data', 'data'), ('template.prst', '.'), ('icon.ico', '.')],
    hiddenimports=['gp180lib', 'gp180_agent', 'gp180_i18n', 'gp180_secrets', 'gp180_setlist', 'gp180_theme', 'gp180_ui', 'gp180_oauth', 'gp180_lufs', 'gp180_calibration', 'gp180_batch', 'gp180_batch_live', 'gp180_midi', 'gp180_usb', 'sounddevice', 'pyloudnorm', 'mido'],
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
    name='GP180_Studio',
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
    icon=['icon.ico'],
)
