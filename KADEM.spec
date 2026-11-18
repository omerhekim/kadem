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
# Güvenlik: kadem paketindeki her modül exe'ye girmiş olmalı. Derleme aracı okuyamadığı bir dosyayı sessizce
# dışarıda bırakır (ör. kullanılan Python sürümünde geçersiz bir yazım); o zaman derleme burada durur.
import glob as _glob, os as _os
_beklenen = {'kadem.' + _os.path.relpath(p, 'kadem')[:-3].replace(_os.sep, '.') for p in _glob.glob('kadem/**/*.py', recursive=True)}
_beklenen = {m[:-len('.__init__')] if m.endswith('.__init__') else m for m in _beklenen}
_eksik = sorted(_beklenen - {ad for ad, _, _ in a.pure})
if _eksik:
    raise SystemExit('Exe\'ye girmeyen modüller: ' + ', '.join(_eksik))

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
