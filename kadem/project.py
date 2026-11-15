"""Proje: dosya listesi, EMG eşleştirmesi, sorgular, referans anlar, özel aralıklar, hasta bilgisi, MVIC, ayarlar.
JSON olarak kaydedilir (.c3dproj). Dosya taraması (hasta adı, tarih, döngü sayıları, kanal durumu) burada yapılır."""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

import numpy as np

from . import __version__
from . import variables as V
from .cycles import donguleri_kur
from .emg import kanal_durumu, kanal_onerisi, emg_kanal_mi
from .engine import Sorgu, RefAn, Ayarlar, DosyaKaydi, DalgaFormu, hasta_anahtari, mvic_anahtari
from .intervals import Aralik
from .model import Trial, ascii_ad, olcum_tarihi

PROJE_SURUM = 1


def kullanici_klasoru() -> str:
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
    p = os.path.join(base, 'KADEM')
    if not os.path.isdir(p):
        os.makedirs(p, exist_ok=True)
        # v0.2 ve öncesinin (C3D Veri Çekici) kanal hafızası ve tercihlerini taşı
        eski = os.path.join(base, 'C3DVeriCekici')
        for ad in ('kanal_hafizasi.json', 'tercihler.json'):
            try:
                if os.path.isfile(os.path.join(eski, ad)):
                    import shutil
                    shutil.copy2(os.path.join(eski, ad), os.path.join(p, ad))
            except Exception:
                pass
    return p


# ---------------------------------------------------------------------------------
# Kanal hafızası (programın tüm projelerde hatırladığı eşleştirmeler)
# ---------------------------------------------------------------------------------
def _hafiza_yolu():
    return os.path.join(kullanici_klasoru(), 'kanal_hafizasi.json')


def tercihler_oku() -> dict:
    try:
        with open(os.path.join(kullanici_klasoru(), 'tercihler.json'), encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def tercihler_yaz(d: dict):
    try:
        with open(os.path.join(kullanici_klasoru(), 'tercihler.json'), 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def kanal_hafizasi_oku() -> dict:
    try:
        with open(_hafiza_yolu(), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def kanal_hafizasi_yaz(h: dict):
    try:
        with open(_hafiza_yolu(), 'w', encoding='utf-8') as f:
            json.dump(h, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


# ---------------------------------------------------------------------------------
# Dosya tarama
# ---------------------------------------------------------------------------------
def otomatik_tarihleri_yenile(dosyalar: list) -> int:
    """Elle girilmemiş ölçüm tarihlerini klasör adına göre yeniden belirler (eski sürümler Nexus dosyalarından
    okuyordu; o tarihler process tarihi olabilir). Değişen dosya sayısını döndürür."""
    n = 0
    for d in dosyalar:
        k = d.get('tarih_kaynagi') or ''
        if k == 'elle girildi' or k.startswith('C3D içi'):
            continue
        t, kaynak = olcum_tarihi(d['yol'])
        if t != (d.get('tarih') or '') or kaynak != k:
            if t != (d.get('tarih') or ''):
                n += 1
            d['tarih'], d['tarih_kaynagi'] = t, kaynak
    return n


def dosya_tara(yol: str) -> dict:
    """C3D dosyasının özet bilgisi (arayüz tabloları için)."""
    bilgi = {'yol': os.path.abspath(yol), 'dosya': os.path.splitext(os.path.basename(yol))[0], 'hata': None}
    try:
        st = os.stat(yol)
        bilgi['boyut'] = st.st_size
        bilgi['mtime'] = st.st_mtime
    except OSError as e:
        bilgi['hata'] = f'Dosya bulunamadı: {e}'
        return bilgi
    try:
        tr = Trial(yol)
    except Exception as e:  # noqa
        bilgi['hata'] = f'Okunamadı: {e}'
        return bilgi
    c = tr.c3d
    donguler = donguleri_kur(tr)
    bilgi.update({
        'subject': tr.subject, 'hasta_tahmini': tr.hasta_tahmini, 'tarih': tr.tarih, 'tarih_kaynagi': tr.tarih_kaynagi,
        'kare_hizi': tr.rate, 'analog_hizi': tr.analog_rate, 'sure_s': round(tr.n / tr.rate, 3) if tr.rate else 0,
        'kutle': tr.kutle, 'boy_mm': tr.boy_mm, 'bacak_L_mm': tr.bacak_mm.get('L'), 'bacak_R_mm': tr.bacak_mm.get('R'),
        'ic_L': len(tr.events['L']['IC']), 'ic_R': len(tr.events['R']['IC']),
        'dongu_L': sum(1 for d in donguler if d.taraf == 'L' and d.gecerli),
        'dongu_R': sum(1 for d in donguler if d.taraf == 'R' and d.gecerli),
        'kinetik_L': sum(1 for d in donguler if d.taraf == 'L' and d.kinetik),
        'kinetik_R': sum(1 for d in donguler if d.taraf == 'R' and d.kinetik),
        'model': (c.get('SUBJECTS', 'MARKER_SETS') or [''])[0] if isinstance(c.get('SUBJECTS', 'MARKER_SETS'), list) else '',
        'yazilim': f'{c.get("MANUFACTURER", "SOFTWARE") or ""} {c.get("MANUFACTURER", "VERSION_LABEL") or ""}'.strip(),
    })
    # mevcut değişkenler
    var = {}
    for d in V.KINEMATIK + V.KINETIK + V.GRF:
        var[d.id] = any(tr.var_mi(d.etiket.format(S=s)) for s in 'LR')
    var['ToeClearance'] = tr.var_mi('LTOE') or tr.var_mi('RTOE')
    bilgi['degiskenler'] = var
    # analog kanallar
    kanallar = []
    for i, ad in enumerate(c.analog_labels):
        birim = c.analog_units[i] if i < len(c.analog_units) else ''
        emg = emg_kanal_mi(ad, birim)
        k = {'ad': ad, 'birim': birim, 'emg': emg, 'fs': c.analog_rate}
        if emg and c.analog.shape[0]:
            k.update(kanal_durumu(c.analog[:, i], birim, c.analog_rate))
        kanallar.append(k)
    bilgi['kanallar'] = kanallar
    uy = list(tr.uyarilar)
    for d in donguler:
        uy += [(o, f'{"Sol" if d.taraf == "L" else "Sağ"} {d.no}. döngü: {m}', k) for o, m, k in d.uyarilar]
    bilgi['uyarilar'] = [{'onem': o, 'mesaj': m, 'kategori': k} for o, m, k in uy]
    return bilgi


# ---------------------------------------------------------------------------------
# Proje
# ---------------------------------------------------------------------------------
@dataclass
class Proje:
    dosyalar: list = field(default_factory=list)        # dict: yol, hasta, tarih, tarih_kaynagi, dahil, boyut, mtime
    sorgular: list = field(default_factory=list)        # Sorgu
    refler: list = field(default_factory=list)          # RefAn
    ozel_araliklar: list = field(default_factory=list)  # Aralik
    ayarlar: Ayarlar = field(default_factory=Ayarlar)
    hastalar: dict = field(default_factory=dict)        # 'hasta|tarih' -> {'etkilenen': 'L'|'R'|None}
    dislamalar: list = field(default_factory=list)      # {'dosya','taraf','dongu','neden'}
    cikti: dict = field(default_factory=lambda: {'klasor': '', 'dosya_adi': 'KADEM_Sonuclar.xlsx', 'anonim': False})
    kas_listesi: list = field(default_factory=list)     # kullanıcının eklediği kaslar [{'kod','ad'}]
    dalgalar: list = field(default_factory=list)        # DalgaFormu

    def dict(self) -> dict:
        return {
            'surum': PROJE_SURUM, 'program': f'KADEM {__version__}',
            'kayit_zamani': time.strftime('%Y-%m-%d %H:%M'),
            'dosyalar': self.dosyalar,
            'sorgular': [q.dict() for q in self.sorgular],
            'refler': [r.dict() for r in self.refler],
            'ozel_araliklar': [a.dict() for a in self.ozel_araliklar],
            'ayarlar': self.ayarlar.dict(),
            'hastalar': self.hastalar,
            'dislamalar': self.dislamalar,
            'cikti': self.cikti,
            'kas_listesi': self.kas_listesi,
            'dalgalar': [w.dict() for w in self.dalgalar],
        }

    @staticmethod
    def from_dict(d: dict) -> 'Proje':
        p = Proje()
        p.dosyalar = list(d.get('dosyalar') or [])
        p.sorgular = [Sorgu.from_dict(x) for x in d.get('sorgular') or []]
        p.refler = [RefAn.from_dict(x) for x in d.get('refler') or []]
        p.ozel_araliklar = [Aralik.from_dict(x) for x in d.get('ozel_araliklar') or []]
        p.ayarlar = Ayarlar.from_dict(d.get('ayarlar') or {})
        p.hastalar = dict(d.get('hastalar') or {})
        p.dislamalar = list(d.get('dislamalar') or [])
        p.cikti.update(d.get('cikti') or {})
        p.kas_listesi = list(d.get('kas_listesi') or [])
        p.dalgalar = [DalgaFormu.from_dict(x) for x in d.get('dalgalar') or []]
        p.ayarlar.kas_adlari = p.kas_adlari()
        return p

    def kaydet(self, yol: str):
        tmp = yol + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.dict(), f, ensure_ascii=False, indent=1, default=_json_default)
        os.replace(tmp, yol)

    @staticmethod
    def ac(yol: str) -> 'Proje':
        with open(yol, encoding='utf-8') as f:
            return Proje.from_dict(json.load(f))

    # --- yardımcılar -------------------------------------------------------------
    def dosya_kayitlari(self) -> list:
        return [DosyaKaydi(d['yol'], d.get('hasta') or '', d.get('tarih') or '', bool(d.get('dahil', True)))
                for d in self.dosyalar]

    def dislama_sozlugu(self) -> dict:
        return {(x['dosya'], x['taraf'], int(x['dongu'])): x.get('neden', '') for x in self.dislamalar}

    def kas_adlari(self) -> dict:
        return {k['kod']: k['ad'] for k in self.kas_listesi}

    def sablon(self) -> dict:
        return {'tur': 'kadem-sablon', 'surum': PROJE_SURUM,
                'sorgular': [q.dict() for q in self.sorgular], 'refler': [r.dict() for r in self.refler],
                'ozel_araliklar': [a.dict() for a in self.ozel_araliklar], 'kas_listesi': self.kas_listesi,
                'dalgalar': [w.dict() for w in self.dalgalar]}


def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, tuple):
        return list(o)
    raise TypeError(type(o))


# ---------------------------------------------------------------------------------
# MVIC tablosu içe aktarma
# ---------------------------------------------------------------------------------
_TR = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')


def _norm(s):
    return re.sub(r'\s+', ' ', str(s).translate(_TR)).strip().casefold()


def mvic_excel_oku(yol: str, kas_kodlari: list) -> tuple:
    """Desteklenen biçimler:
      - Hasta | Taraf | <KAS>_MVIC_uV  (ör. eski TA_MVIC.xlsx; birden fazla kas sütunu olabilir)
      - Hasta | Kas | Taraf | MVIC_uV
    İsteğe bağlı "Tarih" sütunu varsa değer yalnızca o ölçüm tarihi için geçerli olur.
    Dönüş: (eşleşmeler {'hasta|kas|taraf': µV}, uyarılar)."""
    import pandas as pd
    df = pd.read_excel(yol)
    cols = {_norm(c): c for c in df.columns}
    c_h = next((cols[k] for k in cols if 'hasta' in k or 'patient' in k or 'isim' in k or k == 'ad'), df.columns[0])
    c_t = next((cols[k] for k in cols if 'taraf' in k or 'side' in k), None)
    c_k = next((cols[k] for k in cols if k in ('kas', 'muscle')), None)
    c_d = next((cols[k] for k in cols if k in ('tarih', 'date', 'olcum tarihi', 'olcum_tarihi')), None)

    def tarih(r):
        if c_d is None:
            return '*'
        v = r[c_d]
        try:
            import pandas as pd
            if pd.isna(v):
                return '*'
            return pd.Timestamp(v).date().isoformat()
        except Exception:
            return '*'
    uy = []
    out = {}

    def taraf(x):
        t = _norm(x)
        if t in ('l', 'left', 'sol'):
            return 'L'
        if t in ('r', 'right', 'sag'):
            return 'R'
        return None
    if c_t is None:
        return {}, ['Tabloda "Taraf" sütunu bulunamadı.']
    if c_k is not None:
        c_v = next((cols[k] for k in cols if 'mvic' in k or 'uv' in k or 'deger' in k), None)
        if c_v is None:
            return {}, ['Tabloda MVIC değer sütunu bulunamadı.']
        for _, r in df.iterrows():
            t = taraf(r[c_t])
            try:
                v = float(r[c_v])
            except (TypeError, ValueError):
                continue
            if t and np.isfinite(v) and v > 0:
                out[mvic_anahtari(str(r[c_h]), str(r[c_k]).strip().upper(), t, tarih(r))] = v
    else:
        kas_sut = []
        for k, c in cols.items():
            m = re.match(r'^([a-z0-9]+)[_\s]*mvic', k)
            if m:
                kas_sut.append((m.group(1).upper(), c))
        if not kas_sut:
            c_v = next((cols[k] for k in cols if 'mvic' in k), None)
            if c_v is None:
                return {}, ['MVIC sütunu bulunamadı (ör. "TA_MVIC_uV").']
            kas_sut = [('TA', c_v)]
            uy.append('Kas sütunu yok; değerler TA için okundu.')
        for kas, c_v in kas_sut:
            for _, r in df.iterrows():
                t = taraf(r[c_t])
                try:
                    v = float(r[c_v])
                except (TypeError, ValueError):
                    continue
                if t and np.isfinite(v) and v > 0:
                    out[mvic_anahtari(str(r[c_h]), kas, t, tarih(r))] = v
    bos = int(len(df)) - len(out)
    if bos > 0:
        uy.append(f'{bos} satır boş ya da okunamadı.')
    return out, uy
