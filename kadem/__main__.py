"""Programı başlatır: yerel sunucuyu açar ve arayüzü kendi penceresinde (Edge/Chrome uygulama modu) gösterir.

Kullanım:  python -m kadem            (pencere açar)
           python -m kadem --tarayici (varsayılan tarayıcıda açar)
           python -m kadem --port 8765 --pencere-yok (yalnızca sunucu; test için)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser

from . import APP_NAME, __version__
from .project import kullanici_klasoru


def _tarayici_bul():
    adaylar = []
    if os.name == 'nt':
        for kok in (os.environ.get('PROGRAMFILES(X86)'), os.environ.get('PROGRAMFILES'), os.environ.get('LOCALAPPDATA')):
            if not kok:
                continue
            adaylar += [os.path.join(kok, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
                        os.path.join(kok, 'Google', 'Chrome', 'Application', 'chrome.exe')]
    else:
        for ad in ('microsoft-edge', 'google-chrome', 'chromium', 'chromium-browser'):
            p = shutil.which(ad)
            if p:
                adaylar.append(p)
    for p in adaylar:
        if p and os.path.isfile(p):
            return p
    return None


def _calisan_ornek():
    """Zaten açık bir program varsa adresini döndürür."""
    try:
        with open(os.path.join(kullanici_klasoru(), 'calisan.json'), encoding='utf-8') as f:
            d = json.load(f)
        req = urllib.request.Request(f'http://127.0.0.1:{d["port"]}/api/ping', data=b'{}', method='POST',
                                     headers={'X-Token': d['token'], 'Content-Type': 'application/json'})
        acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # sistem proxy'sini atla
        with acici.open(req, timeout=1.5) as r:
            if r.status == 200:
                return d
    except Exception:
        return None
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog='kadem', description=f'{APP_NAME} {__version__}')
    ap.add_argument('--port', type=int, default=0)
    ap.add_argument('--tarayici', action='store_true', help='varsayılan tarayıcıda aç')
    ap.add_argument('--pencere-yok', action='store_true', help='yalnızca sunucuyu başlat')
    ap.add_argument('--token', default=None)
    a = ap.parse_args(argv)

    if not a.pencere_yok:
        d = _calisan_ornek()
        if d:
            url = f'http://127.0.0.1:{d["port"]}/#t={d["token"]}'
            tb = _tarayici_bul()
            if tb and not a.tarayici:
                subprocess.Popen([tb, f'--app={url}', f'--user-data-dir={os.path.join(kullanici_klasoru(), "pencere")}'])
            else:
                webbrowser.open(url)
            return 0

    from .app.server import Sunucu
    s = Sunucu(a.port, a.token)
    s.baslat()
    bilgi = os.path.join(kullanici_klasoru(), 'calisan.json')
    try:
        with open(bilgi, 'w', encoding='utf-8') as f:
            json.dump({'port': s.port, 'token': s.token, 'pid': os.getpid()}, f)
    except Exception:
        pass
    print(f'{APP_NAME} {__version__} çalışıyor: {s.url}', flush=True)

    tarayici_sureci = None
    if not a.pencere_yok:
        tb = None if a.tarayici else _tarayici_bul()
        if tb:
            profil = os.path.join(kullanici_klasoru(), 'pencere')
            tarayici_sureci = subprocess.Popen([tb, f'--app={s.url}', f'--user-data-dir={profil}', '--no-first-run',
                                                '--no-default-browser-check', '--window-size=1440,920',
                                                '--disable-features=Translate'])
        else:
            webbrowser.open(s.url)
    try:
        while not s.kapanis.is_set():
            time.sleep(1.0)
            if tarayici_sureci is not None:
                if tarayici_sureci.poll() is not None:
                    # pencere kapandı; kısa bir süre yeni istek gelmezse kapat
                    if time.time() - s.son_istek > 3:
                        break
            elif not a.pencere_yok and time.time() - max(s.son_istek, s.oturum.son_ping) > 15 * 60:
                break   # tarayıcı modunda 15 dk hiç istek yoksa kapan
    except KeyboardInterrupt:
        pass
    finally:
        s.durdur()
        try:
            os.remove(bilgi)
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
