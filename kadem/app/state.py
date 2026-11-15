"""Arayüz oturumu: projenin bellekteki hali, dosya taraması önbelleği, arka plan işleri ve API işlemleri."""
from __future__ import annotations

import copy
import glob
import json
import os
import re
import threading
import time
import traceback

import numpy as np

from .. import __version__, APP_NAME, APP_ALT_BASLIK
from .. import variables as V
from ..engine import Sorgu, RefAn, Ayarlar, DalgaFormu, calistir, otomatik_kod, aralik_sozlugu, hasta_anahtari, mvic_anahtari, mvic_coz, _deve
from ..intervals import Aralik, HAZIR_ARALIKLAR, HAZIR_ANLAR, capa_metni
from ..stats import ISTATISTIKLER, FAZ_ISTATISTIKLERI, ZAMAN_BIRIMLERI, SURE_BIRIMLERI, IST, FAZ_IST, GENLIK_ISTATISTIKLERI
from ..presets import PAKETLER, paket, dalga_paketi, DALGA_PAKETI
from ..project import Proje, dosya_tara, otomatik_tarihleri_yenile, tercihler_oku, tercihler_yaz, kanal_hafizasi_oku, kanal_hafizasi_yaz, mvic_excel_oku, kullanici_klasoru
from ..emg import kanal_onerisi
from ..aggregate import birim as sorgu_birimi
from ..model import ascii_ad
from .. import dil as dil_mod

GRUP_SIRASI = [('kinematik', 'Kinematik'), ('kinetik', 'Kinetik'), ('grf', 'Yer tepki kuvveti'), ('emg', 'EMG'),
               ('faz', 'Güç fazları (Winter)'), ('zu', 'Zamansal-uzamsal'), ('turetilmis', 'Türetilmiş')]


class Hata(Exception):
    pass


class Oturum:
    def __init__(self):
        self.kilit = threading.RLock()
        self.proje = Proje()
        self.proje_yolu = None
        self.degisti = False
        self.tarama = {}          # yol -> dosya_tara() çıktısı
        self.is_ = {'tur': None, 'calisiyor': False, 'ilerleme': 0, 'toplam': 0, 'mesaj': '', 'hata': None, 'bitti': True}
        self._iptal = False
        self.son_sonuc = None
        self.hafiza = kanal_hafizasi_oku()
        self.son_ping = time.time()
        self.tercihler = tercihler_oku()
        dil_mod.ayarla(self.tercihler.get('dil', 'tr'))

    # ------------------------------------------------------------------------------
    # Arka plan işleri
    # ------------------------------------------------------------------------------
    def _is_baslat(self, tur, hedef, *args):
        with self.kilit:
            if self.is_['calisiyor']:
                raise Hata('Başka bir işlem sürüyor, bitmesini bekleyin.')
            self._iptal = False
            self.is_ = {'tur': tur, 'calisiyor': True, 'ilerleme': 0, 'toplam': 0, 'mesaj': '', 'hata': None,
                        'bitti': False, 'baslangic': time.time()}

        def calis():
            try:
                hedef(*args)
            except Exception as e:  # noqa
                with self.kilit:
                    self.is_['hata'] = f'{type(e).__name__}: {e}'
                    self.is_['iz'] = traceback.format_exc()[-3000:]
            finally:
                with self.kilit:
                    self.is_['calisiyor'] = False
                    self.is_['bitti'] = True
                    self.is_['sure'] = round(time.time() - self.is_.get('baslangic', time.time()), 1)
        threading.Thread(target=calis, daemon=True).start()

    def _ilerle(self, i, n, mesaj=''):
        with self.kilit:
            self.is_['ilerleme'] = i
            self.is_['toplam'] = n
            self.is_['mesaj'] = os.path.basename(mesaj) if mesaj else ''

    def iptal(self, _=None):
        self._iptal = True
        return {'ok': True}

    # ------------------------------------------------------------------------------
    # Proje
    # ------------------------------------------------------------------------------
    def yeni(self, _=None):
        with self.kilit:
            if self.is_['calisiyor']:
                raise Hata('İşlem sürerken yeni proje açılamaz.')
            self.proje = Proje()
            self.proje_yolu = None
            self.degisti = False
            self.son_sonuc = None
        return self.durum()

    def ac(self, b):
        yol = b.get('yol')
        if not yol or not os.path.isfile(yol):
            raise Hata('Proje dosyası bulunamadı.')
        p = Proje.ac(yol)
        guncellenen = otomatik_tarihleri_yenile(p.dosyalar)
        with self.kilit:
            self.proje = p
            self.proje_yolu = yol
            self.degisti = False
            self.son_sonuc = None
        eksik = [d['yol'] for d in p.dosyalar if d['yol'] not in self.tarama]
        if eksik:
            self._is_baslat('tarama', self._tara, eksik, False)
        dd = self.durum()
        if guncellenen:
            dd['bilgi'] = (f'{guncellenen} dosyanın ölçüm tarihi klasör adına göre yeniden belirlendi '
                           f'(elle girilen tarihler değiştirilmedi).')
        return dd

    def kaydet(self, b):
        yol = b.get('yol') or self.proje_yolu
        if not yol:
            raise Hata('Kayıt yolu yok.')
        if not yol.lower().endswith('.c3dproj'):
            yol += '.c3dproj'
        with self.kilit:
            self.proje.kaydet(yol)
            self.proje_yolu = yol
            self.degisti = False
        return self.durum()

    def _degisti(self):
        self.degisti = True

    # ------------------------------------------------------------------------------
    # Dosyalar
    # ------------------------------------------------------------------------------
    def dosya_ekle(self, b):
        yollar = []
        for y in b.get('yollar') or []:
            if os.path.isdir(y):
                yollar += glob.glob(os.path.join(y, '**', '*.c3d'), recursive=True)
                yollar += glob.glob(os.path.join(y, '**', '*.C3D'), recursive=True)
            elif os.path.isfile(y) and y.lower().endswith('.c3d'):
                yollar.append(y)
        yollar = sorted({os.path.abspath(y) for y in yollar})
        with self.kilit:
            mevcut = {d['yol'] for d in self.proje.dosyalar}
        yeni = [y for y in yollar if y not in mevcut]
        if not yeni:
            d = self.durum()
            d['bilgi'] = 'Eklenecek yeni C3D dosyası bulunamadı.' if not yollar else 'Seçilen dosyalar zaten listede.'
            return d
        self._is_baslat('tarama', self._tara, yeni, True)
        return self.durum()

    def _tara(self, yollar, ekle):
        n = len(yollar)
        for i, y in enumerate(yollar):
            if self._iptal:
                break
            self._ilerle(i, n, y)
            bilgi = dosya_tara(y)
            with self.kilit:
                self.tarama[y] = bilgi
                if ekle and not any(d['yol'] == y for d in self.proje.dosyalar):
                    self.proje.dosyalar.append({
                        'yol': y, 'hasta': bilgi.get('hasta_tahmini') or bilgi['dosya'], 'tarih': bilgi.get('tarih') or '',
                        'tarih_kaynagi': bilgi.get('tarih_kaynagi') or '', 'dahil': not bilgi.get('hata'),
                        'boyut': bilgi.get('boyut'), 'mtime': bilgi.get('mtime')})
                    self._degisti()
                    self._kanal_onerileri_uygula(bilgi)
        with self.kilit:
            self.proje.dosyalar.sort(key=lambda d: (ascii_ad(d.get('hasta', '')).casefold(), os.path.basename(d['yol'])))
        self._ilerle(n, n, '')

    def _kanal_onerileri_uygula(self, bilgi):
        """Yeni kanal adları için hafızadan ya da addan öneri; yalnızca eşleştirilmemiş kanallara."""
        es = self.proje.ayarlar.emg_eslesme
        for k in bilgi.get('kanallar') or []:
            if not k.get('emg') or k['ad'] in es:
                continue
            h = self.hafiza.get(k['ad'])
            if h:
                es[k['ad']] = dict(h)
                continue
            if k.get('durum') == 'sinyal':
                kas, taraf = kanal_onerisi(k['ad'])
                if kas and taraf:
                    es[k['ad']] = {'kas': kas, 'taraf': taraf, 'oneri': True}

    def dosya_guncelle(self, b):
        yollar = b.get('yollar') or ([b['yol']] if b.get('yol') else [])
        alanlar = {k: b[k] for k in ('hasta', 'tarih', 'dahil') if k in b}
        if 'hasta' in alanlar:
            alanlar['hasta'] = str(alanlar['hasta']).strip()
            if not alanlar['hasta']:
                raise Hata('Hasta adı boş olamaz.')
        if 'tarih' in alanlar:
            t = str(alanlar['tarih']).strip()
            if t and not re.match(r'^\d{4}-\d{2}-\d{2}$', t):
                raise Hata('Tarih YYYY-AA-GG biçiminde olmalı.')
            alanlar['tarih'] = t
            alanlar['tarih_kaynagi'] = 'elle girildi'
        with self.kilit:
            yollar = set(yollar)
            for d in self.proje.dosyalar:
                if d['yol'] in yollar:
                    d.update(alanlar)
            self._degisti()
        return self.durum()

    def dosya_cikar(self, b):
        yollar = set(b.get('yollar') or [])
        with self.kilit:
            self.proje.dosyalar = [d for d in self.proje.dosyalar if d['yol'] not in yollar]
            self._degisti()
        return self.durum()

    def yeniden_tara(self, _=None):
        yollar = [d['yol'] for d in self.proje.dosyalar]
        self._is_baslat('tarama', self._tara, yollar, False)
        return self.durum()

    # ------------------------------------------------------------------------------
    # EMG kanalları
    # ------------------------------------------------------------------------------
    def kanal_esle(self, b):
        ad = b['ad']
        kas = (b.get('kas') or '').strip().upper()
        taraf = b.get('taraf') or None
        with self.kilit:
            es = self.proje.ayarlar.emg_eslesme
            if not kas:
                es[ad] = {'kas': '', 'taraf': None, 'yok_say': True}
                self.hafiza[ad] = {'kas': '', 'taraf': None, 'yok_say': True}
            else:
                if taraf not in ('L', 'R'):
                    taraf = (es.get(ad) or {}).get('taraf') or kanal_onerisi(ad)[1]
                es[ad] = {'kas': kas, 'taraf': taraf}
                self.hafiza[ad] = {'kas': kas, 'taraf': taraf}
            kanal_hafizasi_yaz(self.hafiza)
            self._degisti()
        return self.durum()

    def kanal_onerilerini_onayla(self, _=None):
        with self.kilit:
            for ad, e in self.proje.ayarlar.emg_eslesme.items():
                if e.get('oneri'):
                    e.pop('oneri', None)
                    self.hafiza[ad] = dict(e)
            kanal_hafizasi_yaz(self.hafiza)
            self._degisti()
        return self.durum()

    def kas_ekle(self, b):
        kod = re.sub(r'[^A-Za-z0-9]', '', str(b.get('kod', ''))).upper()
        ad = str(b.get('ad', '')).strip() or kod
        if not kod:
            raise Hata('Kas kodu gerekli (ör. ADDM).')
        with self.kilit:
            if kod in V.KAS_ADI or any(k['kod'] == kod for k in self.proje.kas_listesi):
                raise Hata('Bu kas kodu zaten var.')
            self.proje.kas_listesi.append({'kod': kod, 'ad': ad})
            self.proje.ayarlar.kas_adlari = self.proje.kas_adlari()
            self._degisti()
        return self.durum()

    # ------------------------------------------------------------------------------
    # Sorgular
    # ------------------------------------------------------------------------------
    def _araliklar(self):
        return aralik_sozlugu(self.proje.ozel_araliklar, {r.id: r for r in self.proje.refler})

    def _kod_benzersiz(self, kod, haric=None):
        mevcut = {q.kod for i, q in enumerate(self.proje.sorgular) if i != haric}
        if kod not in mevcut:
            return kod
        k = 2
        while f'{kod}_{k}' in mevcut:
            k += 1
        return f'{kod}_{k}'

    def _sorgu_dogrula(self, q: Sorgu):
        d = V.bul(q.degisken, self.proje.kas_adlari())
        if d is None:
            raise Hata('Değişken seçilmedi.')
        if d.tur in ('zu',):
            q.aralik, q.ist, q.bilesen = None, 'deger', None
            return
        if d.tur == 'faz':
            q.aralik, q.bilesen = None, None
            if q.ist not in FAZ_IST:
                raise Hata('Bu güç fazı için istatistik seçin.')
            return
        if not q.aralik or q.aralik not in self._araliklar():
            raise Hata('Aralık ya da an seçin.')
        if q.ist not in IST:
            raise Hata('İstatistik seçin.')
        ist = IST[q.ist]
        a = self._araliklar()[q.aralik]
        if a.an_mi and q.ist not in ('deger',):
            raise Hata('Bir an seçildiğinde istatistik "Değer" olmalı.')
        if not a.an_mi and q.ist == 'deger':
            raise Hata('"Değer" yalnızca anlar için kullanılır; aralık için başka bir istatistik seçin.')
        if ist.tur in ('emg', 'emg_zaman', 'emg_trial', 'cci') and d.tur != 'emg':
            raise Hata(f'"{ist.ad}" yalnızca EMG için kullanılabilir.')
        if q.ist == 'cci' and not (q.par or {}).get('kas2'):
            raise Hata('Ko-kontraksiyon için ikinci kası seçin.')
        if d.tur in ('kinetik', 'grf') and q.taraf == 'karsi':
            raise Hata('Kinetik ve GRF değişkenleri yalnızca aynı taraf için hesaplanır.')

    def sorgu_ekle(self, b):
        q = Sorgu.from_dict(b['sorgu'])
        q.par = {k: v for k, v in (q.par or {}).items() if v not in (None, '', 0) or k == 'kas2'}
        with self.kilit:
            self._sorgu_dogrula(q)
            refs = {r.id: r for r in self.proje.refler}
            if not q.kod:
                q.kod = otomatik_kod(q, self._araliklar(), refs)
            q.kod = re.sub(r'[^A-Za-z0-9_]', '_', ascii_ad(q.kod)).strip('_')[:64] or 'Degisken'
            if q.kod[0].isdigit():
                q.kod = 'V_' + q.kod
            idx = b.get('indeks')
            if idx is not None and 0 <= int(idx) < len(self.proje.sorgular):
                q.kod = self._kod_benzersiz(q.kod, haric=int(idx))
                self.proje.sorgular[int(idx)] = q
            else:
                q.kod = self._kod_benzersiz(q.kod)
                self.proje.sorgular.append(q)
            self._degisti()
        return self.durum()

    def kod_oner(self, b):
        q = Sorgu.from_dict(b['sorgu'])
        with self.kilit:
            return {'kod': otomatik_kod(q, self._araliklar(), {r.id: r for r in self.proje.refler})}

    def sorgu_sil(self, b):
        idx = sorted({int(i) for i in b.get('indeksler', [])}, reverse=True)
        with self.kilit:
            for i in idx:
                if 0 <= i < len(self.proje.sorgular):
                    del self.proje.sorgular[i]
            self._degisti()
        return self.durum()

    def sorgu_tasi(self, b):
        i, yon = int(b['indeks']), int(b['yon'])
        with self.kilit:
            s = self.proje.sorgular
            j = i + yon
            if 0 <= i < len(s) and 0 <= j < len(s):
                s[i], s[j] = s[j], s[i]
                self._degisti()
        return self.durum()

    def sorgu_kod(self, b):
        i = int(b['indeks'])
        kod = re.sub(r'[^A-Za-z0-9_]', '_', ascii_ad(str(b.get('kod', '')))).strip('_')[:64]
        if not kod:
            raise Hata('Sütun adı boş olamaz.')
        if kod[0].isdigit():
            kod = 'V_' + kod
        with self.kilit:
            self.proje.sorgular[i].kod = self._kod_benzersiz(kod, haric=i)
            if 'aciklama' in b:
                self.proje.sorgular[i].aciklama = str(b['aciklama'])
            self._degisti()
        return self.durum()

    def paket_ekle(self, b):
        ad = b['paket']
        if ad not in PAKETLER:
            raise Hata('Bilinmeyen paket.')
        s, a, r = paket(ad)
        with self.kilit:
            mevcut_a = {x.id for x in self.proje.ozel_araliklar}
            for x in a:
                if x.id not in mevcut_a:
                    self.proje.ozel_araliklar.append(x)
            mevcut_r = {x.id for x in self.proje.refler}
            for x in r:
                if x.id not in mevcut_r:
                    self.proje.refler.append(x)
            kodlar = {q.kod for q in self.proje.sorgular}
            eklenen = 0
            for q in s:
                if q.kod in kodlar:
                    continue
                self.proje.sorgular.append(q)
                eklenen += 1
            self._degisti()
        d = self.durum()
        d['bilgi'] = f'{PAKETLER[ad]["ad"]}: {eklenen} sorgu eklendi.' + ('' if eklenen == len(s) else
                                                                          f' ({len(s) - eklenen} tanesi zaten listede).')
        return d

    def sorgulari_temizle(self, _=None):
        with self.kilit:
            self.proje.sorgular = []
            self._degisti()
        return self.durum()

    # --- özel aralık / referans an ---
    def aralik_ekle(self, b):
        """Yeni özel aralık; b['id'] verilirse o aralığı günceller (ad ve tanım)."""
        ad = str(b.get('ad', '')).strip()
        bas, son = b.get('bas'), b.get('son')
        if not ad:
            raise Hata('Aralığa bir ad verin.')
        if not isinstance(bas, dict) or not isinstance(son, dict):
            raise Hata('Başlangıç ve bitiş seçin.')
        for c in (bas, son):
            if 'yuzde' in c:
                c['yuzde'] = float(c['yuzde'])
            for k in ('kayma_ms', 'kayma_gc'):
                if k in c:
                    c[k] = float(c[k] or 0)
                    if not c[k]:
                        del c[k]
            if 'ref' in c and not c['ref']:
                raise Hata('Referans an seçin.')
        aid = b.get('id')
        with self.kilit:
            if aid:
                a = next((x for x in self.proje.ozel_araliklar if x.id == aid), None)
                if a is None:
                    raise Hata('Aralık bulunamadı.')
                yeni_an = bas == son
                if yeni_an != a.an_mi:
                    kullanan = [q.kod for q in self.proje.sorgular if q.aralik == aid] + \
                               [r.ad for r in self.proje.refler if r.aralik == aid] + \
                               [w.kod for w in self.proje.dalgalar if w.aralik == aid]
                    if kullanan:
                        raise Hata(('Bu aralık kullanılıyor; başlangıç ve bitişi aynı yapılamaz (an olur): '
                                    if yeni_an else 'Bu an kullanılıyor; aralığa çevrilemez: ') + ', '.join(kullanan[:6]))
                a.ad, a.bas, a.son = ad, bas, son
                a.kisa = re.sub(r'[^A-Za-z0-9]', '', ascii_ad(b.get('kisa') or ad))[:20] or a.kisa
                self._degisti()
                d = self.durum()
                d['yeni_id'] = aid
                d['bilgi'] = 'Aralık güncellendi. Bu aralığı kullanan sorgular yeni tanımla hesaplanır.'
                return d
            n = 1
            ids = {a.id for a in self.proje.ozel_araliklar}
            while f'OZ{n}' in ids:
                n += 1
            kisa = re.sub(r'[^A-Za-z0-9]', '', ascii_ad(b.get('kisa') or ad))[:20] or f'Int{n}'
            self.proje.ozel_araliklar.append(Aralik(f'OZ{n}', ad, bas, son, kisa, b.get('aciklama', ''), True))
            self._degisti()
        d = self.durum()
        d['yeni_id'] = f'OZ{n}'
        return d

    def _silme_etkisi(self, tur, kimlik):
        """Bir özel aralık ya da referans an silinirse onunla birlikte silinmesi gerekenler (zincirleme)."""
        p = self.proje
        e = {'araliklar': [], 'refler': [], 'sorgular': [], 'dalgalar': []}
        kuyruk = [(tur, kimlik)]
        gorulen = set()
        while kuyruk:
            t, k = kuyruk.pop()
            if (t, k) in gorulen:
                continue
            gorulen.add((t, k))
            if t == 'aralik':
                e['araliklar'].append(k)
                e['sorgular'] += [i for i, q in enumerate(p.sorgular) if q.aralik == k]
                e['dalgalar'] += [w.kod for w in p.dalgalar if w.aralik == k]
                kuyruk += [('ref', r.id) for r in p.refler if r.aralik == k]
            else:
                e['refler'].append(k)
                e['sorgular'] += [i for i, q in enumerate(p.sorgular) if q.aralik == '@' + k]
                kuyruk += [('aralik', a.id) for a in p.ozel_araliklar if a.bas.get('ref') == k or a.son.get('ref') == k]
        e['sorgular'] = sorted(set(e['sorgular']))
        e['dalgalar'] = sorted(set(e['dalgalar']))
        return e

    def silme_etkisi(self, b):
        """Arayüzün onay penceresi için: silinecek kayıtların adları."""
        with self.kilit:
            p = self.proje
            tur = 'ref' if b.get('tur') == 'ref' else 'aralik'
            e = self._silme_etkisi(tur, b['id'])
            ilk = (tur, b['id'])
            return {'ok': True,
                    'sorgular': [p.sorgular[i].kod for i in e['sorgular']],
                    'dalgalar': e['dalgalar'],
                    'araliklar': [a.ad for a in p.ozel_araliklar if a.id in e['araliklar'] and ('aralik', a.id) != ilk],
                    'refler': [r.ad for r in p.refler if r.id in e['refler'] and ('ref', r.id) != ilk]}

    def _zincirleme_sil(self, tur, kimlik, zorla):
        p = self.proje
        e = self._silme_etkisi(tur, kimlik)
        baska = len(e['sorgular']) + len(e['dalgalar']) + len(e['araliklar']) + len(e['refler']) - 1
        if baska and not zorla:
            adlar = [p.sorgular[i].kod for i in e['sorgular']] + e['dalgalar'] + \
                    [a.ad for a in p.ozel_araliklar if a.id in e['araliklar'] and not (tur == 'aralik' and a.id == kimlik)] + \
                    [r.ad for r in p.refler if r.id in e['refler'] and not (tur == 'ref' and r.id == kimlik)]
            raise Hata(('Bu aralığı kullananlar var: ' if tur == 'aralik' else 'Bu referans anı kullananlar var: ')
                       + ', '.join(adlar[:6]))
        p.sorgular = [q for i, q in enumerate(p.sorgular) if i not in set(e['sorgular'])]
        p.dalgalar = [w for w in p.dalgalar if w.kod not in set(e['dalgalar'])]
        p.ozel_araliklar = [a for a in p.ozel_araliklar if a.id not in set(e['araliklar'])]
        p.refler = [r for r in p.refler if r.id not in set(e['refler'])]
        self._degisti()
        return baska

    def aralik_sil(self, b):
        with self.kilit:
            n = self._zincirleme_sil('aralik', b['id'], bool(b.get('zorla')))
        d = self.durum()
        if n:
            d['bilgi'] = f'Aralık ve onu kullanan {n} kayıt silindi.'
        return d

    def ref_ekle(self, b):
        """Yeni referans an; b['ref']['id'] verilirse o referans anı günceller."""
        r = b['ref']
        ad = str(r.get('ad', '')).strip()
        if not ad:
            raise Hata('Referans ana bir ad verin.')
        d = V.bul(r.get('degisken', ''), self.proje.kas_adlari())
        if d is None or d.tur in ('zu', 'faz'):
            raise Hata('Referans an için sürekli bir değişken seçin.')
        if r.get('aralik') not in self._araliklar() or self._araliklar()[r['aralik']].an_mi:
            raise Hata('Arama aralığı seçin.')
        with self.kilit:
            rid = r.get('id')
            if rid:
                ref = next((x for x in self.proje.refler if x.id == rid), None)
                if ref is None:
                    raise Hata('Referans an bulunamadı.')
                a = next((x for x in self.proje.ozel_araliklar if x.id == r['aralik']), None)
                if a is not None and (a.bas.get('ref') == rid or a.son.get('ref') == rid):
                    raise Hata('Arama aralığı bu referans anın kendisine bağlı olamaz.')
                ref.ad, ref.degisken, ref.bilesen, ref.aralik = ad, r['degisken'], r.get('bilesen'), r['aralik']
                ref.ekstremum, ref.taraf = r.get('ekstremum', 'max'), r.get('taraf', 'ipsi')
                ref.yumusatma_ms = float(r.get('yumusatma_ms') or 0)
                self._degisti()
                dd = self.durum()
                dd['yeni_id'] = f'@{rid}'
                dd['bilgi'] = 'Referans an güncellendi. Onu kullanan sorgular ve aralıklar yeni tanımla hesaplanır.'
                return dd
            n = 1
            ids = {x.id for x in self.proje.refler}
            while f'R{n}' in ids:
                n += 1
            ref = RefAn(f'R{n}', ad, r['degisken'], r.get('bilesen'), r['aralik'], r.get('ekstremum', 'max'),
                        r.get('taraf', 'ipsi'), float(r.get('yumusatma_ms') or 0))
            self.proje.refler.append(ref)
            self._degisti()
        dd = self.durum()
        dd['yeni_id'] = f'@R{n}'
        return dd

    def ref_sil(self, b):
        with self.kilit:
            n = self._zincirleme_sil('ref', b['id'], bool(b.get('zorla')))
        d = self.durum()
        if n:
            d['bilgi'] = f'Referans an ve onu kullanan {n} kayıt silindi.'
        return d

    def sablon_kaydet(self, b):
        yol = b['yol']
        if not yol.lower().endswith('.json'):
            yol += '.json'
        with open(yol, 'w', encoding='utf-8') as f:
            json.dump(self.proje.sablon(), f, ensure_ascii=False, indent=1)
        d = self.durum()
        d['bilgi'] = f'Şablon kaydedildi: {yol}'
        return d

    def sablon_yukle(self, b):
        with open(b['yol'], encoding='utf-8') as f:
            s = json.load(f)
        if s.get('tur') not in ('kadem-sablon', 'c3dveri-sablon'):
            raise Hata('Bu dosya bir sorgu şablonu değil.')
        with self.kilit:
            # aralık ve referans id çakışmalarını yeniden adlandır
            harita = {}
            mevcut_a = {a.id for a in self.proje.ozel_araliklar} | {a.id for a in HAZIR_ARALIKLAR + HAZIR_ANLAR}
            for ad in s.get('ozel_araliklar') or []:
                a = Aralik.from_dict(ad)
                if a.id in mevcut_a:
                    var = next((x for x in self.proje.ozel_araliklar if x.id == a.id), None)
                    if var is not None and var.bas == a.bas and var.son == a.son:
                        continue
                    n = 1
                    while f'OZ{n}' in mevcut_a:
                        n += 1
                    harita[a.id] = f'OZ{n}'
                    a.id = f'OZ{n}'
                self.proje.ozel_araliklar.append(a)
                mevcut_a.add(a.id)
            rh = {}
            mevcut_r = {r.id for r in self.proje.refler}
            for rd in s.get('refler') or []:
                r = RefAn.from_dict(rd)
                r.aralik = harita.get(r.aralik, r.aralik)
                if r.id in mevcut_r:
                    var = next((x for x in self.proje.refler if x.id == r.id), None)
                    if var is not None and var.dict() == r.dict():
                        continue
                    n = 1
                    while f'R{n}' in mevcut_r:
                        n += 1
                    rh[r.id] = f'R{n}'
                    r.id = f'R{n}'
                self.proje.refler.append(r)
                mevcut_r.add(r.id)
            for a in self.proje.ozel_araliklar:
                for c in (a.bas, a.son):
                    if c.get('ref') in rh:
                        c['ref'] = rh[c['ref']]
            for k in s.get('kas_listesi') or []:
                if not any(x['kod'] == k['kod'] for x in self.proje.kas_listesi):
                    self.proje.kas_listesi.append(k)
            self.proje.ayarlar.kas_adlari = self.proje.kas_adlari()
            for wd in s.get('dalgalar') or []:
                w = DalgaFormu.from_dict(wd)
                w.aralik = harita.get(w.aralik, w.aralik)
                if not any(x.kod == w.kod for x in self.proje.dalgalar):
                    self.proje.dalgalar.append(w)
            eklenen = 0
            for qd in s.get('sorgular') or []:
                q = Sorgu.from_dict(qd)
                q.aralik = harita.get(q.aralik, q.aralik)
                if q.aralik and q.aralik.startswith('@') and q.aralik[1:] in rh:
                    q.aralik = '@' + rh[q.aralik[1:]]
                if any(x.kod == q.kod for x in self.proje.sorgular):
                    continue
                self.proje.sorgular.append(q)
                eklenen += 1
            self._degisti()
        d = self.durum()
        d['bilgi'] = f'Şablondan {eklenen} sorgu eklendi.'
        return d

    # --- dalga formları ---
    def dalga_ekle(self, b):
        w = b['dalga']
        d = V.bul(w.get('degisken', ''), self.proje.kas_adlari())
        if d is None or d.tur in ('zu', 'faz'):
            raise Hata('Dalga formu için sürekli bir değişken seçin.')
        a = self._araliklar().get(w.get('aralik'))
        if a is None or a.an_mi:
            raise Hata('Dalga formu için bir aralık seçin (an olamaz).')
        n = int(w.get('nokta') or 101)
        if not 2 <= n <= 1001:
            raise Hata('Nokta sayısı 2–1001 arasında olmalı.')
        if d.tur in ('kinetik', 'grf') and w.get('taraf') == 'karsi':
            raise Hata('Kinetik ve GRF dalga formları yalnızca aynı taraf için çıkarılır.')
        kod = re.sub(r'[^A-Za-z0-9_\-]', '_', ascii_ad(str(w.get('kod') or ''))).strip('_')
        if not kod:
            bl = V.bilesen(d, w.get('bilesen'))
            kisa_b = {'X': 'Sag', 'Y': 'Fro', 'Z': 'Tra', 'AP': 'AP', 'ML': 'ML', 'V': 'Vert'}
            kod = d.kisa
            if bl and len(d.bilesenler) > 1:
                kod += '_' + kisa_b.get(bl.kod, bl.kod)
            kod += '_' + (a.kisa or a.id)
        with self.kilit:
            mevcut = {x.kod for x in self.proje.dalgalar}
            k, i = kod, 2
            while k in mevcut:
                k, i = f'{kod}_{i}', i + 1
            self.proje.dalgalar.append(DalgaFormu(k, d.id, w.get('bilesen') or (d.bilesenler[0].kod if d.bilesenler else None),
                                                  a.id, n, w.get('taraf') or 'ipsi', str(w.get('aciklama') or '')))
            self._degisti()
        return self.durum()

    def dalga_sil(self, b):
        kod = b['kod']
        with self.kilit:
            self.proje.dalgalar = [w for w in self.proje.dalgalar if w.kod != kod]
            self._degisti()
        return self.durum()

    def dalga_paket_ekle(self, _=None):
        ws, aa = dalga_paketi()
        with self.kilit:
            mevcut_a = {x.id for x in self.proje.ozel_araliklar}
            for x in aa:
                if x.id not in mevcut_a:
                    self.proje.ozel_araliklar.append(x)
            mevcut = {x.kod for x in self.proje.dalgalar}
            n = 0
            for w in ws:
                if w.kod not in mevcut:
                    self.proje.dalgalar.append(w)
                    n += 1
            self._degisti()
        d = self.durum()
        d['bilgi'] = f'{DALGA_PAKETI["ad"]}: {n} dalga formu eklendi.'
        return d

    # ------------------------------------------------------------------------------
    # Hastalar, MVIC, ayarlar, dışlamalar
    # ------------------------------------------------------------------------------
    def hasta_guncelle(self, b):
        if b.get('coklu'):
            with self.kilit:
                for x in b['coklu']:
                    self.proje.hastalar.setdefault(x['anahtar'], {})['etkilenen'] = \
                        x.get('etkilenen') if x.get('etkilenen') in ('L', 'R') else None
                self._degisti()
            return self.durum()
        k = b['anahtar']
        with self.kilit:
            h = self.proje.hastalar.setdefault(k, {})
            if 'etkilenen' in b:
                h['etkilenen'] = b['etkilenen'] if b['etkilenen'] in ('L', 'R') else None
            if 'not' in b:
                h['not'] = str(b['not'])
            self._degisti()
        return self.durum()

    def hasta_toplu(self, b):
        """Excel'den yapıştırılan Hasta | Taraf [| Tarih] satırlarını hastalarla eşleştirir.
        b['uygula'] yoksa yalnızca önizleme döner."""
        from ..model import metinden_tarih

        def norm(x):
            return re.sub(r'[^a-z0-9]', '', ascii_ad(str(x)).casefold())

        def taraf_coz(x):
            t = re.sub(r'[^a-z]', '', ascii_ad(str(x)).casefold())
            if t in ('l', 'left', 'sol', 's', 'sl'):
                return 'L'
            if t in ('r', 'right', 'sag', 'sg'):
                return 'R'
            if t in ('yok', 'none', 'bilateral', 'ikitarafli', 'x') or str(x).strip() in ('-', '—'):
                return ''
            return None
        with self.kilit:
            hastalar = {}
            for d in self.proje.dosyalar:
                hastalar.setdefault(norm(d.get('hasta', '')), {}).setdefault((d.get('hasta', ''), d.get('tarih', '')), 0)
            satirlar, degisecek = [], {}
            eslesen_anahtar = set()
            for ham in b.get('satirlar') or []:
                hucre = [str(x).strip() for x in (ham if isinstance(ham, list) else str(ham).split('\t'))]
                hucre = [x for x in hucre]
                if not any(hucre):
                    continue
                ad = hucre[0] if hucre else ''
                diger = [x for x in hucre[1:] if x]
                taraf, tarih = None, ''
                taraf_ham = ''
                for x in diger:
                    tc = taraf_coz(x)
                    if tc is not None and taraf is None:
                        taraf, taraf_ham = tc, x
                        continue
                    tt = metinden_tarih(x)
                    if tt and not tarih:
                        tarih = tt
                        continue
                    if taraf is None and not taraf_ham:
                        taraf_ham = x
                if norm(ad) in ('hasta', 'patient', 'ad', 'isim', 'name', 'hastaadi'):
                    continue   # başlık satırı
                kayit = {'hasta': ad, 'taraf_ham': taraf_ham, 'tarih': tarih, 'taraf': taraf, 'durum': '', 'eslesen': []}
                aday = hastalar.get(norm(ad))
                if not ad:
                    kayit['durum'] = 'hasta adı boş'
                elif taraf is None:
                    kayit['durum'] = 'taraf anlaşılmadı' if taraf_ham else 'taraf boş'
                elif not aday:
                    kayit['durum'] = 'hasta bulunamadı'
                else:
                    hedef = [k for k in aday if not tarih or k[1] == tarih]
                    if not hedef:
                        kayit['durum'] = 'bu tarihte ölçüm yok'
                    else:
                        degisen = 0
                        for h, t in hedef:
                            k = hasta_anahtari(h, t)
                            eslesen_anahtar.add(k)
                            eski = (self.proje.hastalar.get(k) or {}).get('etkilenen') or ''
                            if k in degisecek and degisecek[k] != taraf:
                                kayit['durum'] = 'listede aynı hasta için farklı taraf var'
                            degisecek[k] = taraf
                            if eski != taraf:
                                degisen += 1
                            kayit['eslesen'].append({'hasta': h, 'tarih': t, 'eski': eski})
                        if not kayit['durum']:
                            kayit['durum'] = 'tamam' if degisen else 'zaten aynı'
                satirlar.append(kayit)
            tum = {hasta_anahtari(h, t): (h, t) for grup in hastalar.values() for (h, t) in grup}
            eslesmeyen = sorted({h for k, (h, t) in tum.items() if k not in eslesen_anahtar},
                                key=lambda x: ascii_ad(x).casefold())
            ozet = {'satir': len(satirlar), 'tamam': sum(1 for x in satirlar if x['durum'] in ('tamam', 'zaten aynı')),
                    'sorunlu': sum(1 for x in satirlar if x['durum'] not in ('tamam', 'zaten aynı')),
                    'degisecek': sum(1 for k, v in degisecek.items()
                                     if ((self.proje.hastalar.get(k) or {}).get('etkilenen') or '') != v),
                    'listede_olmayan': eslesmeyen}
            if not b.get('uygula'):
                return {'ok': True, 'satirlar': satirlar, 'ozet': ozet}
            for k, v in degisecek.items():
                self.proje.hastalar.setdefault(k, {})['etkilenen'] = v or None
            self._degisti()
        d = self.durum()
        d['bilgi'] = f'{ozet["degisecek"]} hasta kaydının etkilenen tarafı güncellendi.' + (
            f' {ozet["sorunlu"]} satır eşleşmedi.' if ozet['sorunlu'] else '')
        return d

    def mvic_guncelle(self, b):
        with self.kilit:
            k = mvic_anahtari(b['hasta'], b['kas'], b['taraf'], b.get('tarih') or '*')
            v = b.get('deger')
            if v in (None, ''):
                self.proje.ayarlar.mvic.pop(k, None)
            else:
                v = float(str(v).replace(',', '.'))
                if v <= 0:
                    raise Hata('MVIC değeri pozitif olmalı.')
                self.proje.ayarlar.mvic[k] = v
            self._degisti()
        return self.durum()

    def mvic_ice_aktar(self, b):
        out, uy = mvic_excel_oku(b['yol'], [])
        with self.kilit:
            self.proje.ayarlar.mvic.update(out)
            self._degisti()
        d = self.durum()
        d['bilgi'] = f'{len(out)} MVIC değeri okundu.' + (' ' + ' '.join(uy) if uy else '')
        d['mvic_sor'] = bool(out) and self.proje.ayarlar.emg.normalizasyon != 'mvic'
        return d

    def ayarlar_guncelle(self, b):
        with self.kilit:
            a = self.proje.ayarlar
            for k, v in (b.get('dongu') or {}).items():
                if hasattr(a.dongu, k):
                    setattr(a.dongu, k, tuple(float(x) for x in v) if isinstance(v, list) else
                            (bool(v) if isinstance(getattr(a.dongu, k), bool) else float(v)))
            for k, v in (b.get('emg') or {}).items():
                if hasattr(a.emg, k):
                    cur = getattr(a.emg, k)
                    setattr(a.emg, k, bool(v) if isinstance(cur, bool) else (v if isinstance(cur, str) else
                                                                             (int(v) if isinstance(cur, int) else float(v))))
            for k in ('eksik_veri', 'topuk_marker', 'ortalama_yontemi'):
                if k in b:
                    setattr(a, k, str(b[k]))
            if 'sinir_uyarisi' in b:
                a.sinir_uyarisi = bool(b['sinir_uyarisi'])
            if 'uc_esik' in b:
                a.uc_esik = float(b['uc_esik'])
            if 'lob_min_gc' in b:
                a.lob_min_gc = max(float(b['lob_min_gc']), 0.0)
            if 'min_kinetik' in b:
                a.min_kinetik = max(int(round(float(b['min_kinetik']))), 1)
            for k in ('klasor', 'dosya_adi', 'anonim'):
                if k in (b.get('cikti') or {}):
                    self.proje.cikti[k] = b['cikti'][k]
            self._degisti()
        return self.durum()

    def ayarlari_sifirla(self, _=None):
        with self.kilit:
            eski = self.proje.ayarlar
            yeni = Ayarlar()
            yeni.emg_eslesme, yeni.mvic, yeni.kas_adlari = eski.emg_eslesme, eski.mvic, eski.kas_adlari
            self.proje.ayarlar = yeni
            self._degisti()
        return self.durum()

    def dislama(self, b):
        with self.kilit:
            key = (b['dosya'], b['taraf'], int(b['dongu']))
            self.proje.dislamalar = [x for x in self.proje.dislamalar
                                     if (x['dosya'], x['taraf'], int(x['dongu'])) != key]
            if b.get('dislandi', True):
                self.proje.dislamalar.append({'dosya': key[0], 'taraf': key[1], 'dongu': key[2],
                                              'neden': str(b.get('neden', '')).strip() or 'kullanıcı dışladı'})
            self._degisti()
        return self.durum()

    # ------------------------------------------------------------------------------
    # Çalıştırma
    # ------------------------------------------------------------------------------
    def calistir(self, b):
        with self.kilit:
            p = self.proje
            if not p.sorgular and not p.dalgalar:
                raise Hata('Önce en az bir sorgu ya da dalga formu ekleyin.')
            dahil = [d for d in p.dosyalar if d.get('dahil', True)]
            if not dahil:
                raise Hata('Çalıştırılacak dosya yok.')
            eksik = [os.path.basename(d['yol']) for d in dahil if not os.path.isfile(d['yol'])]
            if eksik:
                raise Hata('Bulunamayan dosyalar var: ' + ', '.join(eksik[:5]))
            emg_q = [q.degisken for q in p.sorgular if q.degisken.startswith('EMG:')] + \
                    [w.degisken for w in p.dalgalar if w.degisken.startswith('EMG:')]
            eslesen = {e.get('kas') for e in p.ayarlar.emg_eslesme.values() if e.get('kas')}
            eksik_kas = sorted({q[4:] for q in emg_q} - eslesen)
            if eksik_kas:
                raise Hata('Şu kaslar hiçbir kanala eşleştirilmemiş: ' + ', '.join(eksik_kas) +
                           '. "EMG kanalları" sayfasından eşleştirin.')
            klasor = (b.get('klasor') or p.cikti.get('klasor') or '').strip()
            if not klasor:
                klasor = os.path.dirname(self.proje_yolu) if self.proje_yolu else os.path.dirname(dahil[0]['yol'])
            ad = (b.get('dosya_adi') or p.cikti.get('dosya_adi') or 'KADEM_Sonuclar.xlsx').strip()
            if not ad.lower().endswith('.xlsx'):
                ad += '.xlsx'
            p.cikti['klasor'], p.cikti['dosya_adi'] = klasor, ad
            if 'anonim' in b:
                p.cikti['anonim'] = bool(b['anonim'])
            proje = Proje.from_dict(copy.deepcopy(p.dict()))
            proje.ayarlar.emg_eslesme = {k: v for k, v in proje.ayarlar.emg_eslesme.items() if v.get('kas')}
        yol = os.path.join(klasor, ad)
        self._is_baslat('calistir', self._calistir, proje, yol)
        return self.durum()

    def cikti_kontrol(self, b):
        """Çıktı dosyaları zaten varsa üzerine yazmadan önce sormak için: mevcut dosyalar ve boş bir ad önerisi."""
        with self.kilit:
            p = self.proje
            klasor = (b.get('klasor') or p.cikti.get('klasor') or '').strip()
            if not klasor:
                dahil = [d for d in p.dosyalar if d.get('dahil', True)]
                klasor = os.path.dirname(self.proje_yolu) if self.proje_yolu else (
                    os.path.dirname(dahil[0]['yol']) if dahil else '')
            ad = (b.get('dosya_adi') or p.cikti.get('dosya_adi') or 'KADEM_Sonuclar.xlsx').strip()
        if not ad.lower().endswith('.xlsx'):
            ad += '.xlsx'
        kok = os.path.splitext(ad)[0]

        def dosyalar(k):
            return [k + '.xlsx', k + '_Dalga_Formlari.xlsx', k + '_ANAHTAR.xlsx']
        mevcut = [x for x in dosyalar(kok) if os.path.isfile(os.path.join(klasor, x))]
        oneri = ad
        if mevcut:
            m = re.match(r'^(.*)_(\d{1,3})$', kok)
            taban, n = (m.group(1), int(m.group(2)) + 1) if m else (kok, 2)
            while any(os.path.isfile(os.path.join(klasor, x)) for x in dosyalar(f'{taban}_{n}')):
                n += 1
            oneri = f'{taban}_{n}.xlsx'
        return {'ok': True, 'mevcut': mevcut, 'oneri': oneri, 'klasor': klasor, 'dosya_adi': ad}

    def _calistir(self, proje: Proje, yol: str):
        from ..export import yaz
        dk = proje.dosya_kayitlari()
        snc = calistir(dk, proje.sorgular, proje.refler, proje.ozel_araliklar, proje.ayarlar,
                       ilerleme=self._ilerle, iptal=lambda: self._iptal, dalgalar=proje.dalgalar)
        if self._iptal:
            raise Hata('İşlem iptal edildi.')
        with self.kilit:
            self.is_['mesaj'] = 'Excel yazılıyor…'
        anonim = None
        if proje.cikti.get('anonim'):
            hastalar = sorted({d.hasta for d in dk if d.dahil}, key=lambda s: ascii_ad(s).casefold())
            anonim = {h: f'P{i + 1:03d}' for i, h in enumerate(hastalar)}
        tk = {os.path.splitext(os.path.basename(d['yol']))[0]: d.get('tarih_kaynagi', '') for d in proje.dosyalar}
        try:
            oz = yaz(snc, proje.ayarlar, yol, hasta_bilgi=proje.hastalar, dislamalar=proje.dislama_sozlugu(),
                     dosya_tarih_kaynagi=tk, anonim=anonim, dil=dil_mod.DIL)
        except PermissionError:
            raise Hata(f'Excel dosyası yazılamadı: {yol} açık olabilir. Kapatıp tekrar deneyin.')
        if proje.dalgalar:
            from ..export import dalga_yaz
            with self.kilit:
                self.is_['mesaj'] = 'Dalga formları yazılıyor…'
            dyol = os.path.splitext(yol)[0] + '_Dalga_Formlari.xlsx'
            try:
                oz['dalga_yol'] = dalga_yaz(snc, proje.ayarlar, dyol, proje.dislama_sozlugu(), anonim, proje.hastalar,
                                            dil=dil_mod.DIL)
            except PermissionError:
                raise Hata(f'Dalga formu dosyası yazılamadı: {dyol} açık olabilir.')
        if anonim:
            import pandas as pd
            anahtar = os.path.splitext(yol)[0] + '_ANAHTAR.xlsx'
            say, trial_kod = {}, []
            for bb in snc.dosya_bilgisi:
                kod = anonim.get(bb['hasta'], bb['hasta'])
                say[kod] = say.get(kod, 0) + 1
                trial_kod.append((bb['dosya'], f'{kod}_T{say[kod]:02d}'))
            M = dil_mod.M
            with pd.ExcelWriter(anahtar) as w:
                pd.DataFrame(sorted(anonim.items(), key=lambda x: x[1]),
                             columns=[M('Hasta', 'Patient'), M('Kod', 'Code')]).to_excel(w, sheet_name=M('Hastalar', 'Patients'),
                                                                                         index=False)
                pd.DataFrame(trial_kod, columns=[M('Dosya', 'File'), M('Kod', 'Code')]).to_excel(
                    w, sheet_name=M('Dosyalar', 'Files'), index=False)
            oz['anahtar'] = anahtar
        T = oz.pop('tablolar')
        uy = [u.satir() for u in snc.uyarilar]
        sayim = {}
        for u in uy:
            sayim[u['onem']] = sayim.get(u['onem'], 0) + 1
        dongu = T['dongu']
        dongu_liste = []
        if not dongu.empty:
            for _, r in dongu.iterrows():
                dongu_liste.append({'dosya': r['Dosya'], 'taraf': r['Taraf'], 'dongu': int(r['Dongu']),
                                    'hasta': r['Hasta'], 'kinetik': int(r['Kinetik']), 'dislandi': int(r['Dislandi']),
                                    'neden': r['Dislama_Nedeni']})
        with self.kilit:
            self.son_sonuc = {
                'yol': yol, 'klasor': os.path.dirname(yol), 'zaman': time.strftime('%H:%M'), 'ozet': oz, 'sayim': sayim,
                'uyarilar': sorted(uy, key=lambda u: {'Hata': 0, 'Uyarı': 1, 'Bilgi': 2}[u['onem']])[:1500],
                'uyari_toplam': len(uy),
                'uc': T['uc'].head(300).replace({np.nan: None}).to_dict('records') if not T['uc'].empty else [],
                'donguler': dongu_liste,
                'onizleme': _onizleme(T['genis']),
            }

    # ------------------------------------------------------------------------------
    # Durum
    # ------------------------------------------------------------------------------
    def dil(self, b):
        self.tercihler['dil'] = dil_mod.ayarla(b.get('dil'))
        tercihler_yaz(self.tercihler)
        return self.durum()

    def ceviri(self, _=None):
        return dil_mod.js_tablosu()

    def durum(self, _=None):
        with self.kilit:
            p = self.proje
            es = p.ayarlar.emg_eslesme
            dosyalar = []
            for d in p.dosyalar:
                t = self.tarama.get(d['yol']) or {}
                durum = 'bekliyor' if not t else ('hata' if t.get('hata') else 'tamam')
                if t and not t.get('hata') and d.get('mtime') and t.get('mtime') and abs(t['mtime'] - d['mtime']) > 1:
                    durum = 'degisti'
                kanallar = [k for k in t.get('kanallar') or [] if k.get('emg')]
                eslesen = sum(1 for k in kanallar if (es.get(k['ad']) or {}).get('kas'))
                dosyalar.append({
                    'yol': d['yol'], 'dosya': os.path.splitext(os.path.basename(d['yol']))[0],
                    'klasor': os.path.dirname(d['yol']), 'hasta': d.get('hasta', ''), 'tarih': d.get('tarih', ''),
                    'tarih_kaynagi': d.get('tarih_kaynagi', ''), 'dahil': d.get('dahil', True), 'durum': durum,
                    'hata': t.get('hata'), 'subject': t.get('subject', ''),
                    'dongu_L': t.get('dongu_L'), 'dongu_R': t.get('dongu_R'),
                    'kinetik_L': t.get('kinetik_L'), 'kinetik_R': t.get('kinetik_R'),
                    'kare_hizi': t.get('kare_hizi'), 'sure_s': t.get('sure_s'),
                    'emg_kanal': len(kanallar), 'emg_eslesen': eslesen,
                    'uyari_sayisi': len([u for u in t.get('uyarilar') or [] if u['onem'] != 'Bilgi']),
                    'uyarilar': (t.get('uyarilar') or [])[:30],
                })
            # kanallar
            kanal = {}
            for d in p.dosyalar:
                t = self.tarama.get(d['yol']) or {}
                for k in t.get('kanallar') or []:
                    if not k.get('emg'):
                        continue
                    x = kanal.setdefault(k['ad'], {'ad': k['ad'], 'birim': k.get('birim', ''), 'dosya_sayisi': 0,
                                                   'sinyal': 0, 'parazit': 0, 'bos': 0, 'rms': [], 'fs': k.get('fs')})
                    x['dosya_sayisi'] += 1
                    x[k.get('durum', 'bos')] = x.get(k.get('durum', 'bos'), 0) + 1
                    if k.get('rms_uv'):
                        x['rms'].append(k['rms_uv'])
            kanal_liste = []
            for ad, x in sorted(kanal.items(), key=lambda kv: _kanal_sira(kv[0])):
                e = es.get(ad) or {}
                kas_o, taraf_o = kanal_onerisi(ad)
                if x['sinyal'] and not x['parazit']:
                    dur, acik = 'sinyal', 'Kas sinyali'
                elif x['sinyal']:
                    dur, acik = 'karisik', f'{x["sinyal"]} dosyada sinyal, {x["parazit"]} dosyada yalnızca parazit'
                elif x['parazit']:
                    dur, acik = 'parazit', 'Yalnızca 50 Hz parazit (sensör bağlı değil?)'
                else:
                    dur, acik = 'bos', 'Boş / sabit'
                kanal_liste.append({'ad': ad, 'birim': x['birim'], 'dosya_sayisi': x['dosya_sayisi'], 'durum': dur,
                                    'aciklama': acik, 'rms': round(float(np.median(x['rms'])), 1) if x['rms'] else None,
                                    'kas': e.get('kas') or '', 'taraf': e.get('taraf') or '', 'oneri': bool(e.get('oneri')),
                                    'yok_say': bool(e.get('yok_say')), 'oneri_kas': kas_o, 'oneri_taraf': taraf_o,
                                    'fs': x['fs']})
            # hastalar
            hasta = {}
            for d, dd in zip(p.dosyalar, dosyalar):
                k = hasta_anahtari(d.get('hasta', ''), d.get('tarih', ''))
                h = hasta.setdefault(k, {'anahtar': k, 'hasta': d.get('hasta', ''), 'tarih': d.get('tarih', ''), 'dosya': 0,
                                         'dongu_L': 0, 'dongu_R': 0, 'kinetik_L': 0, 'kinetik_R': 0, 'kutle': set(),
                                         'bacak_L': set(), 'bacak_R': set(), 'dahil': 0})
                h['dosya'] += 1
                if d.get('dahil', True):
                    h['dahil'] += 1
                    for kk in ('dongu_L', 'dongu_R', 'kinetik_L', 'kinetik_R'):
                        h[kk] += dd.get(kk) or 0
                t = self.tarama.get(d['yol']) or {}
                if t.get('kutle'):
                    h['kutle'].add(round(t['kutle'], 1))
                for s in 'LR':
                    if t.get(f'bacak_{s}_mm'):
                        h[f'bacak_{s}'].add(round(t[f'bacak_{s}_mm']))
            hasta_liste = []
            for k, h in hasta.items():
                hb = p.hastalar.get(k) or {}
                h['mvic_anahtar'] = ascii_ad(h['hasta']).casefold()
                h['etkilenen'] = hb.get('etkilenen') or ''
                h['not'] = hb.get('not', '')
                h['tutarsiz'] = len(h['kutle']) > 1 or len(h['bacak_L']) > 1 or len(h['bacak_R']) > 1
                for kk in ('kutle', 'bacak_L', 'bacak_R'):
                    h[kk] = ', '.join(str(x) for x in sorted(h[kk]))
                hasta_liste.append(h)
            hasta_liste.sort(key=lambda h: (ascii_ad(h['hasta']).casefold(), h['tarih']))
            benzer = _benzer_adlar([h['hasta'] for h in hasta_liste])
            # sorgular
            aral = self._araliklar()
            refs = {r.id: r for r in p.refler}
            sorgular = []
            for q in p.sorgular:
                sorgular.append({**q.dict(), 'ozet': _sorgu_ozet(q, aral, refs, p.kas_adlari())})
            mvic = []
            for k, v in sorted(p.ayarlar.mvic.items()):
                h, tarih, kas, taraf = mvic_coz(k)
                mvic.append({'anahtar': k, 'hasta': h, 'tarih': tarih, 'kas': kas, 'taraf': taraf, 'deger': v})
            return {
                'program': {'ad': APP_NAME, 'surum': __version__, 'alt': APP_ALT_BASLIK}, 'dil': dil_mod.DIL,
                'proje': {'yol': self.proje_yolu, 'ad': os.path.splitext(os.path.basename(self.proje_yolu))[0]
                          if self.proje_yolu else 'Adsız proje', 'degisti': self.degisti},
                'dosyalar': dosyalar, 'kanallar': kanal_liste, 'hastalar': hasta_liste, 'benzer_adlar': benzer,
                'sorgular': sorgular,
                'refler': [{**r.dict(), 'ozet': _ref_ozet(r, aral, p.kas_adlari())} for r in p.refler],
                'ozel_araliklar': [{**a.dict(), 'ozet': f'{capa_metni(a.bas, {r.id: r.ad for r in p.refler})} → '
                                                         f'{capa_metni(a.son, {r.id: r.ad for r in p.refler})}'}
                                   for a in p.ozel_araliklar],
                'ayarlar': p.ayarlar.dict(), 'emg_zincir': p.ayarlar.emg.zincir_metni(),
                'dalgalar': [{**w.dict(), 'ozet': _dalga_ozet(w, aral, p.kas_adlari())} for w in p.dalgalar],
                'mvic': mvic, 'kas_listesi': p.kas_listesi, 'cikti': p.cikti, 'dislamalar': p.dislamalar,
                'is': dict(self.is_), 'son_sonuc': self.son_sonuc,
                'katalog': self._katalog(aral),
                'varsayilan_klasor': os.path.dirname(self.proje_yolu) if self.proje_yolu else
                (os.path.dirname(p.dosyalar[0]['yol']) if p.dosyalar else os.path.expanduser('~')),
            }

    def _katalog(self, aral):
        p = self.proje
        var_mi = {}
        for t in self.tarama.values():
            for k, v in (t.get('degiskenler') or {}).items():
                var_mi[k] = var_mi.get(k, False) or v
        es = p.ayarlar.emg_eslesme
        eslesmis = {e.get('kas') for e in es.values() if e.get('kas')}
        kaslar = [{'kod': k, 'ad': a, 'eslesmis': k in eslesmis} for k, a in V.KASLAR] + \
                 [{'kod': k['kod'], 'ad': k['ad'], 'eslesmis': k['kod'] in eslesmis} for k in p.kas_listesi]
        gruplar = []
        for gid, gad in GRUP_SIRASI:
            if gid == 'emg':
                dl = [{'id': f'EMG:{k["kod"]}', 'ad': f'{k["ad"]} ({k["kod"]})', 'birim': 'µV', 'tur': 'emg',
                       'bilesenler': [], 'var': k['eslesmis'], 'aciklama': ''} for k in kaslar if k['eslesmis']]
            else:
                dl = []
                for d in V.STATIK:
                    if d.tur != gid:
                        continue
                    if gid in ('kinematik', 'kinetik', 'grf'):
                        v = var_mi.get(d.id, not self.tarama)
                        if not v and d.id in ('ThoraxAngles', 'SpineAngles', 'HeadAngles', 'NeckAngles', 'ShoulderAngles',
                                              'ElbowAngles', 'WristAngles', 'AbsAnkleAngle'):
                            continue
                    elif gid == 'turetilmis':
                        v = var_mi.get(d.id, not self.tarama)
                    else:
                        v = True
                    dl.append({'id': d.id, 'ad': d.ad, 'birim': d.birim, 'tur': d.tur, 'var': v,
                               'bilesenler': [b.dict() for b in d.bilesenler] if len(d.bilesenler) > 1 or d.tur != 'emg'
                               else [], 'aciklama': d.aciklama, 'duzey': d.duzey})
            gruplar.append({'id': gid, 'ad': gad, 'degiskenler': dl})
        ref_adlari = {r.id: r.ad for r in p.refler}
        araliklar = []
        for a in aral.values():
            if a.id.startswith('@FAZ:'):
                grup = 'Güç fazı tepe anları'
            elif a.id.startswith('@'):
                grup = 'Anlar' if a.id in {x.id for x in HAZIR_ANLAR} else 'Referans anlar'
            elif a.ozel:
                grup = 'Özel aralıklar'
            else:
                grup = 'Aralıklar'
            araliklar.append({'id': a.id, 'ad': a.ad, 'an': a.an_mi, 'grup': grup, 'ozel': a.ozel,
                              'ozet': f'{capa_metni(a.bas, ref_adlari)} → {capa_metni(a.son, ref_adlari)}'})
        return {
            'gruplar': gruplar, 'araliklar': araliklar,
            'istatistikler': [{'id': i.id, 'ad': i.ad, 'tur': i.tur, 'aciklama': i.aciklama} for i in ISTATISTIKLER],
            'faz_istatistikleri': [{'id': i.id, 'ad': i.ad, 'tur': i.tur} for i in FAZ_ISTATISTIKLERI],
            'zaman_birimleri': ZAMAN_BIRIMLERI, 'sure_birimleri': SURE_BIRIMLERI,
            'genlik_ist': sorted(GENLIK_ISTATISTIKLERI),
            'kaslar': kaslar,
            'paketler': [{'id': k, 'ad': v['ad'], 'n': len(v['sorgular'])} for k, v in PAKETLER.items()],
            'fazlar': [{'id': f'FAZ:{k}', 'ad': f'{k} – {v[0]}', 'aciklama': v[5]} for k, v in V.FAZLAR.items()],
            'olaylar': [{'id': k, 'ad': v} for k, v in
                        {'IC': 'IC (topuk teması)', 'CFO': 'Karşı Foot Off', 'CIC': 'Karşı IC', 'FO': 'Foot Off',
                         'NIC': 'Sonraki IC', 'PCIC': 'Önceki karşı IC'}.items()],
        }


def _kanal_sira(ad):
    m = re.match(r'^([A-Za-z_]*?)(\d+)', ad)
    return (0 if not re.match(r'^emg\d', ad, re.I) else 1, re.sub(r'\d+', lambda x: x.group(0).zfill(4), ad.lower()))


def _benzer_adlar(adlar):
    """Yazım farkı olabilecek hasta adları (Yılmaz/Yilmaz, fazladan boşluk)."""
    def n(s):
        return re.sub(r'[^a-z]', '', ascii_ad(s).casefold())
    grup = {}
    for a in adlar:
        grup.setdefault(n(a), set()).add(a)
    return [sorted(v) for v in grup.values() if len(v) > 1]


def _sorgu_ozet(q: Sorgu, aral, refs, kas_adlari):
    d = V.bul(q.degisken, kas_adlari)
    b = V.bilesen(d, q.bilesen) if d else None
    a = aral.get(q.aralik) if q.aralik else None
    ist = IST.get(q.ist) or FAZ_IST.get(q.ist)
    istad = ist.ad if ist else q.ist
    if ist and ist.tur in ('zaman', 'emg_zaman'):
        istad += f' ({ZAMAN_BIRIMLERI.get(q.zaman_birimi, q.zaman_birimi)})'
    if q.ist == 'cci':
        istad += f' – {(q.par or {}).get("kas2", "?")}'
    if (q.par or {}).get('yumusatma_ms'):
        istad += f', {q.par["yumusatma_ms"]:g} ms yumuşatma'
    return {'degisken': d.ad if d else q.degisken, 'bilesen': (f'{b.ad}' + (f' ({b.isaret})' if b.isaret else '')) if b and
            d and len(d.bilesenler) > 1 else '', 'aralik': a.ad if a else ('—' if not q.aralik else q.aralik),
            'ist': istad, 'birim': sorgu_birimi(q, kas_adlari), 'taraf': 'karşı taraf' if q.taraf == 'karsi' else '',
            'grup': d.grup if d else ''}


def _dalga_ozet(w, aral, kas_adlari):
    d = V.bul(w.degisken, kas_adlari)
    b = V.bilesen(d, w.bilesen) if d else None
    a = aral.get(w.aralik)
    return {'degisken': d.ad if d else w.degisken, 'bilesen': (b.ad + (f' ({b.isaret})' if b.isaret else '')) if b and d and
            len(d.bilesenler) > 1 else '', 'aralik': a.ad if a else w.aralik, 'birim': d.birim if d else '',
            'taraf': 'karşı taraf' if w.taraf == 'karsi' else ''}


def _ref_ozet(r: RefAn, aral, kas_adlari):
    d = V.bul(r.degisken, kas_adlari)
    b = V.bilesen(d, r.bilesen) if d else None
    a = aral.get(r.aralik)
    return f'{d.ad if d else r.degisken}{" " + b.ad if b and d and len(d.bilesenler) > 1 else ""} – ' \
           f'{"en yüksek" if r.ekstremum == "max" else "en düşük"} – {a.ad if a else r.aralik}' + \
           (' (karşı taraf)' if r.taraf == 'karsi' else '')


def _onizleme(genis):
    if genis is None or genis.empty:
        return {'sutunlar': [], 'satirlar': []}
    df = genis.iloc[:50, :40].copy()
    satirlar = []
    for _, r in df.iterrows():
        satirlar.append([None if (isinstance(v, float) and not np.isfinite(v)) else
                         (round(float(v), 4) if isinstance(v, (float, np.floating)) else
                          (int(v) if isinstance(v, (np.integer,)) else v)) for v in r.tolist()])
    return {'sutunlar': list(df.columns), 'satirlar': satirlar, 'toplam_sutun': int(genis.shape[1])}
