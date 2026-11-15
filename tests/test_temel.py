"""Hızlı kontrol: tüm hazır paketleri bir C3D klasöründe çalıştırır ve Excel yazar.

Kullanım:  python tests/test_temel.py "D:\\Raw Files\\Calisma"  [çıktı.xlsx]
"""
import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kadem.engine import calistir, Ayarlar, DosyaKaydi  # noqa: E402
from kadem.export import yaz  # noqa: E402
from kadem.model import Trial  # noqa: E402
from kadem.presets import tum_paketler  # noqa: E402
from kadem.emg import kanal_onerisi  # noqa: E402


def main():
    klasor = sys.argv[1]
    cikti = sys.argv[2] if len(sys.argv) > 2 else os.path.join(klasor, 'KADEM_test.xlsx')
    dosyalar = sorted(glob.glob(os.path.join(klasor, '**', '*.c3d'), recursive=True))
    print(f'{len(dosyalar)} C3D dosyası')
    dk, es = [], {}
    for f in dosyalar:
        t = Trial(f)
        dk.append(DosyaKaydi(f, t.hasta_tahmini, t.tarih))
        for ad in t.c3d.analog_labels:
            kas, taraf = kanal_onerisi(ad)
            if kas and taraf:
                es[ad] = {'kas': kas, 'taraf': taraf}
    s, a, r = tum_paketler()
    ay = Ayarlar()
    ay.emg_eslesme = es
    t0 = time.time()
    snc = calistir(dk, s, r, a, ay)
    oz = yaz(snc, ay, cikti)
    oz.pop('tablolar')
    print(f'{time.time() - t0:.1f} s', oz)
    hata = [u for u in snc.uyarilar if u.onem == 'Hata']
    print(f'{len(hata)} hata kaydı')
    for u in hata[:20]:
        print('  ', u.dosya, u.taraf, u.dongu, u.kod, u.mesaj)


if __name__ == '__main__':
    main()
