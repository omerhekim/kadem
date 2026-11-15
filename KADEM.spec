# -*- mode: python ; coding: utf-8 -*-
# PyInstaller tanımı:  pyinstaller --noconfirm --clean KADEM.spec
from PyInstaller.utils.hooks import collect_submodules

gizli = collect_submodules('kadem') + [
    'scipy.signal', 'scipy.special', 'openpyxl', 'openpyxl.cell._writer', 'xlsxwriter',
    'tkinter', 'tkinter.filedialog',
]

a = Analysis(
    ['baslat.py'],
    pathex=['.'],
    binaries=[],
    datas=[('kadem/app/static', 'kadem/app/static'), ('kadem/app/ikon.ico', 'kadem/app')],
    hiddenimports=gizli,
    excludes=['matplotlib', 'IPython', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'pytest', 'notebook', 'sphinx'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KADEM',
    console=False,
    icon='kadem/app/ikon.ico',
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name='KADEM', upx=False)
