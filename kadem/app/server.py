"""Yerel HTTP sunucusu: arayüz dosyaları + JSON API. Yalnızca 127.0.0.1'e bağlanır, istekler oturum anahtarıyla korunur."""
from __future__ import annotations

import json
import mimetypes
import os
import secrets
import string
import subprocess
import sys
import threading
import time
import traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

from .state import Oturum, Hata

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
if getattr(sys, 'frozen', False):
    STATIC = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), 'kadem', 'app', 'static')

_dialog_kilit = threading.Lock()


# ---------------------------------------------------------------------------------
# Yerel dosya pencereleri (Windows'ta tkinter ile). Olmazsa arayüz kendi gezginini kullanır.
# ---------------------------------------------------------------------------------
def _tk_root():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes('-topmost', True)
    except Exception:
        pass
    root.update()
    return root


def yerel_pencere(tur: str, baslik: str = '', baslangic: str = '', uzanti: str = ''):
    with _dialog_kilit:
        from tkinter import filedialog
        root = _tk_root()
        try:
            ilk = baslangic if baslangic and os.path.isdir(baslangic) else os.path.expanduser('~')
            if tur == 'klasor':
                r = filedialog.askdirectory(parent=root, title=baslik or 'Klasör seçin', initialdir=ilk)
                return [r] if r else []
            if tur == 'dosyalar':
                ft = [('C3D dosyaları', '*.c3d'), ('Tüm dosyalar', '*.*')]
                r = filedialog.askopenfilenames(parent=root, title=baslik or 'Dosya seçin', initialdir=ilk, filetypes=ft)
                return list(r) if r else []
            if tur == 'ac':
                ft = {'c3dproj': [('Proje', '*.c3dproj')], 'json': [('Şablon', '*.json')],
                      'xlsx': [('Excel', '*.xlsx *.xls')]}.get(uzanti, [('Tüm dosyalar', '*.*')])
                r = filedialog.askopenfilename(parent=root, title=baslik or 'Dosya açın', initialdir=ilk, filetypes=ft)
                return [r] if r else []
            if tur == 'kaydet':
                ft = {'c3dproj': [('Proje', '*.c3dproj')], 'json': [('Şablon', '*.json')],
                      'xlsx': [('Excel', '*.xlsx')]}.get(uzanti, [('Tüm dosyalar', '*.*')])
                r = filedialog.asksaveasfilename(parent=root, title=baslik or 'Kaydet', initialdir=ilk, filetypes=ft,
                                                 defaultextension='.' + uzanti if uzanti else '')
                return [r] if r else []
        finally:
            root.destroy()
    return []


def suruculer():
    if os.name != 'nt':
        return ['/']
    out = []
    for h in string.ascii_uppercase:
        p = f'{h}:\\'
        if os.path.exists(p):
            out.append(p)
    return out


def gozat(yol: str, uzanti: str = 'c3d'):
    if not yol:
        yol = os.path.expanduser('~')
    yol = os.path.abspath(yol)
    if os.path.isfile(yol):
        yol = os.path.dirname(yol)
    if not os.path.isdir(yol):
        raise Hata('Klasör bulunamadı.')
    klasorler, dosyalar = [], []
    try:
        girdiler = sorted(os.scandir(yol), key=lambda e: e.name.lower())
    except PermissionError:
        raise Hata('Bu klasöre erişim izni yok.')
    for e in girdiler:
        if e.name.startswith(('.', '$')):
            continue
        try:
            if e.is_dir():
                klasorler.append(e.name)
            elif not uzanti or e.name.lower().endswith('.' + uzanti):
                dosyalar.append(e.name)
        except OSError:
            continue
    ust = os.path.dirname(yol)
    return {'yol': yol, 'ust': ust if ust != yol else None, 'klasorler': klasorler[:2000], 'dosyalar': dosyalar[:5000],
            'suruculer': suruculer(), 'ev': os.path.expanduser('~')}


def isletim_ac(yol: str):
    if not os.path.exists(yol):
        raise Hata('Dosya bulunamadı.')
    if os.name == 'nt':
        os.startfile(yol)  # noqa
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', yol])
    else:
        subprocess.Popen(['xdg-open', yol])


# ---------------------------------------------------------------------------------
class Sunucu:
    def __init__(self, port: int = 0, token: str | None = None):
        self.oturum = Oturum()
        self.token = token or secrets.token_urlsafe(18)
        self.son_istek = time.time()
        self.kapanis = threading.Event()
        sunucu = self

        class Isleyici(BaseHTTPRequestHandler):
            server_version = 'KADEM/1'

            def log_message(self, *a):
                pass

            def _host_ok(self):
                h = (self.headers.get('Host') or '').split(':')[0]
                return h in ('127.0.0.1', 'localhost')

            def _gonder(self, kod, govde: bytes, tur='application/json; charset=utf-8', ek=None):
                self.send_response(kod)
                self.send_header('Content-Type', tur)
                self.send_header('Content-Length', str(len(govde)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                for k, v in (ek or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(govde)

            def do_GET(self):
                if not self._host_ok():
                    return self._gonder(403, b'{}')
                yol = urlparse(self.path).path
                if yol in ('/', '/index.html'):
                    yol = '/index.html'
                dosya = os.path.normpath(os.path.join(STATIC, unquote(yol.lstrip('/'))))
                if not dosya.startswith(os.path.normpath(STATIC)) or not os.path.isfile(dosya):
                    return self._gonder(404, b'not found', 'text/plain')
                tur = mimetypes.guess_type(dosya)[0] or 'application/octet-stream'
                if tur.startswith('text/') or tur in ('application/javascript',):
                    tur += '; charset=utf-8'
                with open(dosya, 'rb') as f:
                    veri = f.read()
                ek = {'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'"} \
                    if dosya.endswith('.html') else None
                self._gonder(200, veri, tur, ek)

            def do_POST(self):
                if not self._host_ok():
                    return self._gonder(403, b'{"hata":"host"}')
                if self.headers.get('X-Token') != sunucu.token:
                    return self._gonder(403, json.dumps({'ok': False, 'hata': 'Oturum anahtarı geçersiz. '
                                                                             'Programı yeniden başlatın.'}).encode())
                sunucu.son_istek = time.time()
                ad = urlparse(self.path).path.rsplit('/', 1)[-1]
                try:
                    n = int(self.headers.get('Content-Length') or 0)
                    govde = json.loads(self.rfile.read(n) or b'{}') if n else {}
                    sonuc = sunucu.api(ad, govde)
                    if isinstance(sonuc, dict) and 'ok' not in sonuc:
                        sonuc['ok'] = True
                    veri = json.dumps(sonuc, ensure_ascii=False, default=_json).encode('utf-8')
                    self._gonder(200, veri)
                except Hata as e:
                    self._gonder(200, json.dumps({'ok': False, 'hata': str(e)}, ensure_ascii=False).encode('utf-8'))
                except Exception as e:  # noqa
                    iz = traceback.format_exc()
                    _log(iz)
                    self._gonder(200, json.dumps({'ok': False, 'hata': f'Beklenmeyen hata: {type(e).__name__}: {e}',
                                                  'iz': iz[-2500:]}, ensure_ascii=False).encode('utf-8'))

        self.httpd = ThreadingHTTPServer(('127.0.0.1', port), Isleyici)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    @property
    def url(self):
        return f'http://127.0.0.1:{self.port}/#t={self.token}'

    def api(self, ad: str, b: dict):
        o = self.oturum
        if ad == 'ping':
            o.son_ping = time.time()
            return {'is': o.is_}
        if ad == 'pencere':
            try:
                return {'yollar': yerel_pencere(b.get('tur', 'klasor'), b.get('baslik', ''), b.get('baslangic', ''),
                                                b.get('uzanti', ''))}
            except Exception as e:  # tkinter yok ya da açılamadı
                return {'ok': False, 'yerel_yok': True, 'hata': f'Yerel pencere açılamadı ({type(e).__name__}).'}
        if ad == 'gozat':
            return gozat(b.get('yol', ''), b.get('uzanti', 'c3d'))
        if ad == 'isletim_ac':
            isletim_ac(b['yol'])
            return {}
        if ad == 'kapat':
            threading.Timer(0.3, self.durdur).start()
            return {}
        f = getattr(o, ad, None)
        if f is None or ad.startswith('_') or not callable(f):
            raise Hata(f'Bilinmeyen işlem: {ad}')
        return f(b)

    def baslat(self):
        t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        t.start()
        return t

    def durdur(self):
        self.kapanis.set()
        try:
            self.httpd.shutdown()
        except Exception:
            pass


def _json(o):
    import numpy as np
    if isinstance(o, (np.floating,)):
        f = float(o)
        return f if f == f else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)


def _log(metin: str):
    try:
        from ..project import kullanici_klasoru
        with open(os.path.join(kullanici_klasoru(), 'hata_kaydi.txt'), 'a', encoding='utf-8') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S') + '\n' + metin + '\n')
    except Exception:
        pass
