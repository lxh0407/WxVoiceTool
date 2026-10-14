# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("yara")

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=[("runtime", "runtime"), ("ui/theme.qss", "ui")],
    hiddenimports=hidden + ["lameenc"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WxVoiceTool",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="WxVoiceTool",
)
