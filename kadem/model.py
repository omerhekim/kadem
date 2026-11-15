"""Trial (C3D dosyası) ve yürüme döngüsü modeli.

- Event zamanları saniye olarak tutulur (kareye yuvarlanmaz; isteğe bağlı uyum modu hariç).
- Döngü: aynı tarafın IC'sinden bir sonraki IC'sine. Karşı taraf FO/IC ve aynı taraf FO döngünün içinden alınır.
- Program event düzeltmez; eksik/şüpheli durumları uyarı olarak yazar.
"""
from __future__ import annotations

import os
import re
import datetime as _dt
from dataclasses import dataclass, field

import numpy as np

from .c3d_reader import read_c3d
from .warnings_ import HATA, UYARI, BILGI

IC_ADLARI = {'foot strike', 'heel strike', 'foot contact', 'initial contact', 'ic', 'fs', 'hs', 'footstrike',
             'heelstrike', 'contact'}
FO_ADLARI = {'foot off', 'toe off', 'fo', 'to', 'toeoff', 'footoff', 'foot-off', 'toe-off'}
SOL_ADLARI = {'left', 'l', 'sol'}
SAG_ADLARI = {'right', 'r', 'sag', 'sağ'}

PELVIS_MARKERLARI = ('LASI', 'RASI', 'LPSI', 'RPSI')


def taraf_kodu(context: str):
    c = (context or '').strip().lower()
    if c in SOL_ADLARI:
        return 'L'
    if c in SAG_ADLARI:
        return 'R'
    return None


def karsi(taraf: str) -> str:
    return 'R' if taraf == 'L' else 'L'


# ---------------------------------------------------------------------------------
# Hasta adı ve ölçüm tarihi
# ---------------------------------------------------------------------------------
_TR = str.maketrans('çğıöşüÇĞİÖŞÜâîû', 'cgiosuCGIOSUaiu')


def ascii_ad(s: str) -> str:
    return re.sub(r'\s+', ' ', str(s).translate(_TR)).strip()


def hasta_adi_tahmin(dosya_adi: str, subject: str = '', klasor: str = '') -> str:
    """Dosya adından hasta adını tahmin eder ('Ayse Yilmaz Cal 05' -> 'Ayse Yilmaz')."""
    stem = re.sub(r'[_]+', ' ', dosya_adi).strip()
    m = re.match(r'^(.*?)[\s\-]*(?:cal|trial|walk|deneme|yurume|yürüme|dyn|dynamic|gait)?[\s\-]*\d+\s*$', stem, re.I)
    aday = (m.group(1).strip() if m else stem).strip(' -_')
    if subject:
        if ascii_ad(subject).casefold() in ascii_ad(stem).casefold():
            return subject.strip()
    if aday and re.search(r'[A-Za-zÇĞİÖŞÜçğıöşü]{2,}', aday):
        return aday
    if subject:
        return subject.strip()
    return klasor or stem


_AYRAC = r'[\s._\-/]+'
_TARIH_DESEN = [
    (re.compile(r'(?<!\d)(\d{4})' + _AYRAC + r'(\d{1,2})' + _AYRAC + r'(\d{1,2})(?!\d)'), 'ymd'),
    (re.compile(r'(?<!\d)(\d{1,2})' + _AYRAC + r'(\d{1,2})' + _AYRAC + r'(\d{4})(?!\d)'), 'dmy'),
    (re.compile(r'(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)'), 'ymd'),
    (re.compile(r'(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)'), 'dmy'),
]


def metinden_tarih(metin: str):
    """Metindeki ilk geçerli tarihi bulur (GG AA YYYY, GG.AA.YYYY, YYYY-AA-GG, YYYYAAGG ...). Yoksa None."""
    for desen, tip in _TARIH_DESEN:
        for m in desen.finditer(metin or ''):
            a, b, c = (int(x) for x in m.groups())
            try:
                d = _dt.date(a, b, c) if tip == 'ymd' else _dt.date(c, b, a)
            except ValueError:
                continue
            if 1990 <= d.year <= 2100:
                return d
    return None


def _c3d_tarihi(c3d):
    """C3D parametrelerinde tarih içeren bir alan varsa onu döndürür (standart bir alan yoktur; Nexus genelde yazmaz)."""
    if c3d is None:
        return None, ''
    for grup, ps in (c3d.params or {}).items():
        if not isinstance(ps, dict):
            continue
        for ad, p in ps.items():
            if 'DATE' not in str(ad).upper():
                continue
            try:
                s = ' '.join(p.strings) if p.strings else ''
            except Exception:
                s = ''
            d = metinden_tarih(s)
            if d:
                return d, f'{grup}:{ad}'
    return None, ''


def olcum_tarihi(c3d_yolu: str, c3d=None):
    """Ölçüm tarihini bulur. Dönüş: (tarih 'YYYY-MM-DD' ya da '', kaynak açıklaması).

    Sıra: (1) C3D'nin içindeki tarih alanı, (2) dosyanın bulunduğu klasörden yukarı doğru klasör adlarındaki tarih
    (ör. '...\\Hasta Adı\\13 01 2026\\'). Bulunamazsa boş döner; tarihi kullanıcı girer.
    Nexus dosyaları (.enf, .x2d) ve dosya tarihleri kullanılmaz: process sırasında değişebilirler.
    """
    d, kaynak = _c3d_tarihi(c3d)
    if d:
        return d.isoformat(), f'C3D içi ({kaynak})'
    klasor = os.path.dirname(os.path.abspath(c3d_yolu))
    while True:
        ad = os.path.basename(klasor)
        if not ad:
            break
        d = metinden_tarih(ad)
        if d:
            return d.isoformat(), f'klasör adı ({ad})'
        ust = os.path.dirname(klasor)
        if ust == klasor:
            break
        klasor = ust
    return '', 'bulunamadı'


def hasta_klasoru(c3d_yolu: str) -> str:
    """Tarih içermeyen en yakın üst klasörün adı (hasta adı tahmini için)."""
    klasor = os.path.dirname(os.path.abspath(c3d_yolu))
    for _ in range(4):
        ad = os.path.basename(klasor)
        if ad and not metinden_tarih(ad):
            return ad
        klasor = os.path.dirname(klasor)
    return ''


# ---------------------------------------------------------------------------------
# Sinyal (eşit aralıklı örnekler)
# ---------------------------------------------------------------------------------
@dataclass
class Sinyal:
    t0: float                  # 0. örneğin zamanı (s)
    fs: float                  # örnekleme hızı (Hz)
    v: np.ndarray              # 1B değerler (NaN = veri yok)
    birim: str = ''
    temas: bool = False        # GRF gibi: temas dışında 0 sayılır
    nan_nedeni: str = 'eksik veri'

    @property
    def t_son(self):
        return self.t0 + (len(self.v) - 1) / self.fs


# ---------------------------------------------------------------------------------
# Trial
# ---------------------------------------------------------------------------------
class Trial:
    def __init__(self, yol: str, emg_eslesme: dict | None = None):
        self.yol = os.path.abspath(yol)
        self.c3d = c = read_c3d(yol)
        self.dosya = os.path.splitext(os.path.basename(yol))[0]
        self.rate = float(c.point_rate)
        self.t_first = c.t0
        self.n = c.n_frames
        self.t_last = self.t_first + (self.n - 1) / self.rate if self.n else self.t_first
        self.etiketler = c.point_labels
        self._idx = {l: i for i, l in enumerate(c.point_labels)}
        self.uyarilar = []          # (onem, mesaj, kategori)
        for w in c.warnings:
            self.uyarilar.append((UYARI, f'C3D: {w}', 'DOSYA'))

        names = c.get('SUBJECTS', 'NAMES')
        self.subject = (names[0] if isinstance(names, list) and names else (names or '')) or ''
        self.hasta_tahmini = hasta_adi_tahmin(self.dosya, self.subject, hasta_klasoru(self.yol))
        self.tarih, self.tarih_kaynagi = olcum_tarihi(yol, c)

        def proc(name):
            p = c.param('PROCESSING', name)
            if p is None:
                return None
            v = p.floats
            return float(v[0]) if v.size and np.isfinite(v[0]) and v[0] != 0 else None

        self.kutle = proc('BODYMASS')
        self.boy_mm = proc('HEIGHT')
        self.bacak_mm = {'L': proc('LLEGLENGTH'), 'R': proc('RLEGLENGTH')}

        # --- event'ler ---
        self.events = {'L': {'IC': [], 'FO': []}, 'R': {'IC': [], 'FO': []}}
        self.taninmayan = {}
        for e in c.events:
            s = taraf_kodu(e.context)
            lab = e.label.strip().lower()
            tur = 'IC' if lab in IC_ADLARI else ('FO' if lab in FO_ADLARI else None)
            if s is None or tur is None:
                key = f'{e.context}:{e.label}'
                self.taninmayan[key] = self.taninmayan.get(key, 0) + 1
                continue
            self.events[s][tur].append(float(e.time))
        for s in self.events:
            for k in self.events[s]:
                self.events[s][k].sort()
        for key, n in self.taninmayan.items():
            ctx, lab = key.split(':', 1)
            if lab.strip().lower() in ('general', 'event') or ctx.strip().lower() == 'general':
                self.uyarilar.append((BILGI, f'Genel event yok sayıldı: {key} ({n} adet)', 'EVENT'))
            else:
                self.uyarilar.append((UYARI, f'Tanınmayan event etiketi yok sayıldı: {key} ({n} adet)', 'EVENT'))
        if not any(self.events[s][k] for s in self.events for k in self.events[s]):
            self.uyarilar.append((HATA, 'Dosyada Foot Strike / Foot Off event\'i yok (statik ya da MVIC kaydı olabilir).',
                                  'EVENT'))

        # --- analog / EMG ---
        self.analog_rate = float(c.analog_rate)
        self.analog_t0 = c.analog_t0
        self.emg_eslesme = emg_eslesme or {}
        self._cache = {}
        self._yon_bul()

    # -----------------------------------------------------------------------------
    def nokta(self, etiket: str):
        i = self._idx.get(etiket)
        if i is None:
            return None
        return self.c3d.points[:, i, :]

    def var_mi(self, etiket: str) -> bool:
        return etiket in self._idx

    def zaman_indeks(self, t: float) -> float:
        return (t - self.t_first) * self.rate

    def _yon_bul(self):
        """Yürüme yönü: pelvis markerlarının yer değiştirmesi.
        - self.u: gerçek yatay doğrultu (birim vektör, adım uzunluğu için)
        - self.ilerleme_ekseni / self.ilerleme_isareti: en yakın laboratuvar ekseni (GRF ön-arka bileşeni için,
          Vicon NormalisedGRF ile aynı kural)."""
        self.u = None
        self.ilerleme_ekseni, self.ilerleme_isareti = 1, 1.0
        self.yer_degistirme_m = 0.0
        idx = [self._idx[m] for m in PELVIS_MARKERLARI if m in self._idx]
        if not idx:
            for alt in ('SACR', 'LHEE', 'RHEE', 'LANK', 'RANK'):
                if alt in self._idx:
                    idx = [self._idx[alt]]
                    self.uyarilar.append((UYARI, f'Pelvis markerları yok; yürüme yönü {alt} markerından bulundu.', 'MARKER'))
                    break
        if not idx:
            self.uyarilar.append((UYARI, 'Yürüme yönü bulunamadı (pelvis markerı yok); GRF ön-arka yönü +Y varsayıldı, '
                                         'hız ve adım uzunluğu hesaplanamaz.', 'MARKER'))
            return
        with np.errstate(all='ignore'):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', RuntimeWarning)
                merkez = np.nanmean(self.c3d.points[:, idx, :2], axis=1)
        ok = ~np.isnan(merkez).any(axis=1)
        if ok.sum() < 10:
            self.uyarilar.append((UYARI, 'Pelvis markerlarında yeterli veri yok; yürüme yönü bulunamadı.', 'MARKER'))
            return
        d = merkez[ok][-1] - merkez[ok][0]
        mesafe = float(np.linalg.norm(d))
        if mesafe < 1e-6:
            return
        self.u = d / mesafe
        self.yer_degistirme_m = mesafe / 1000.0
        ax = int(np.argmax(np.abs(d)))
        self.ilerleme_ekseni = ax
        self.ilerleme_isareti = 1.0 if d[ax] >= 0 else -1.0
        if self.yer_degistirme_m < 1.0:
            self.uyarilar.append((UYARI, f'Pelvis yer değiştirmesi kısa ({self.yer_degistirme_m:.2f} m); '
                                         'yürüme yönü güvenilir olmayabilir.', 'MARKER'))
        aci = np.degrees(np.arctan2(abs(d[1 - ax]), abs(d[ax])))
        if aci > 20:
            self.uyarilar.append((UYARI, f'Yürüme doğrultusu laboratuvar ekseninden {aci:.0f}° sapıyor; '
                                         'GRF ön-arka/medio-lateral ayrımı etkilenebilir.', 'MARKER'))

    # -----------------------------------------------------------------------------
    def grf_bilesenleri(self, taraf: str):
        """(dikey, ön-arka [+ileri], medio-lateral [+medial]) N/kg, (n,) dizileri ya da None."""
        g = self.nokta(f'{taraf}GroundReactionForce')
        if g is None:
            return None
        ax, s = self.ilerleme_ekseni, self.ilerleme_isareti
        dikey = g[:, 2]
        ap = s * g[:, ax]
        # yürüyene göre sağ yön: ileri × yukarı
        sag_yon = s * g[:, 0] if ax == 1 else -s * g[:, 1]
        ml = sag_yon if taraf == 'L' else -sag_yon
        return dikey, ap, ml
