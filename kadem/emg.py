"""EMG işleme: filtre, zarf, veri kaybı tespiti, aktivasyon (başlangıç/bitiş), frekans analizi, kanal önerisi.

Varsayılan zincir (Noraxon MR 4.0 ile aynı): Butterworth 4. derece, çift yönlü (sıfır faz);
önce high-pass 20 Hz, sonra low-pass 500 Hz; ardından 50 ms merkezli hareketli RMS.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
from scipy.signal import butter, sosfiltfilt, iirnotch, filtfilt, periodogram, welch

from .warnings_ import UYARI, BILGI
from .variables import KASLAR


@dataclass
class EmgAyarlari:
    hp: float = 20.0
    lp: float = 500.0
    derece: int = 4
    notch: bool = False
    notch_hz: float = 50.0
    zarf: str = 'rms'                 # 'rms' | 'lineer'
    rms_ms: float = 50.0
    lineer_lp: float = 6.0
    normalizasyon: str = 'yok'        # 'yok' | 'mvic' | 'dinamik_tepe' | 'dinamik_ort'
    ham_uv_yaz: bool = True
    esik_sd: float = 3.0
    esik_taban_tepe: float = 0.05
    sessiz_ms: float = 100.0
    min_aktif_ms: float = 25.0
    birlestir_ms: float = 25.0
    kayip_min_ms: float = 10.0        # sabit değer dizisi bu süreden uzunsa veri kaybı sayılır
    parazit_oran_esik: float = 10.0   # 50 Hz bandı / geniş bant güç oranı

    def dict(self):
        return dict(self.__dict__)

    def zincir_metni(self) -> str:
        from .dil import M
        s = M(f'Butterworth {self.derece}. derece çift yönlü; HP {self.hp:g} Hz, LP {self.lp:g} Hz',
              f'Butterworth order {self.derece}, zero-lag; HP {self.hp:g} Hz, LP {self.lp:g} Hz')
        if self.notch:
            s += M(f', çentik {self.notch_hz:g} Hz', f', notch {self.notch_hz:g} Hz')
        if self.zarf == 'rms':
            s += M(f'; {self.rms_ms:g} ms merkezli RMS', f'; {self.rms_ms:g} ms centred RMS')
        else:
            s += M(f'; tam dalga doğrultma + {self.lineer_lp:g} Hz alçak geçiren (lineer zarf)',
                   f'; full-wave rectification + {self.lineer_lp:g} Hz low-pass (linear envelope)')
        return s


BIRIM_CARPAN = {'v': 1e6, 'mv': 1e3, 'uv': 1.0, 'µv': 1.0, 'microvolt': 1.0, 'μv': 1.0}


def uv_carpani(birim: str, x: np.ndarray):
    b = str(birim or '').strip().lower()
    if b in BIRIM_CARPAN:
        return BIRIM_CARPAN[b], None
    amp = float(np.nanmax(np.abs(x))) if x.size else 0.0
    if amp < 0.1:
        return 1e6, f'EMG birimi bilinmiyor ("{birim}"); genliğe göre volt varsayıldı.'
    if amp < 100:
        return 1e3, f'EMG birimi bilinmiyor ("{birim}"); genliğe göre mV varsayıldı.'
    return 1.0, f'EMG birimi bilinmiyor ("{birim}"); genliğe göre µV varsayıldı.'


def kayip_maske(x: np.ndarray, fs: float, min_ms: float) -> np.ndarray:
    """Ardışık aynı değerlerden oluşan (>= min_ms) diziler ve NaN: veri kaybı (kablosuz paket kaybı ya da kayıt boşluğu)."""
    n = len(x)
    m = ~np.isfinite(x)
    if n < 2:
        return m
    esit = np.r_[False, np.diff(x) == 0]
    # koşu uzunlukları
    minn = max(int(round(min_ms / 1000.0 * fs)), 2)
    d = np.diff(np.r_[0, esit.astype(np.int8), 0])
    bas = np.flatnonzero(d == 1)
    son = np.flatnonzero(d == -1)
    for b, s in zip(bas, son):
        if s - b + 1 >= minn:
            m[max(b - 1, 0):s] = True
    return m


def _genislet(m: np.ndarray, k: int) -> np.ndarray:
    if k <= 0 or not m.any():
        return m
    c = np.convolve(m.astype(np.int32), np.ones(2 * k + 1, np.int32), mode='same')
    return c > 0


@dataclass
class EmgKanal:
    kas: str
    taraf: str
    kanal_adi: str
    fs: float
    t0: float
    filtreli: np.ndarray          # µV, filtrelenmiş ham sinyal
    zarf: np.ndarray              # µV, kayıp bölgeler NaN
    kayip: np.ndarray             # bool maske (zarf üzerinde)
    uyarilar: list = field(default_factory=list)
    _burst: object = None
    _esik: float = np.nan

    @property
    def t(self):
        return self.t0 + np.arange(len(self.zarf)) / self.fs


def kanal_isle(x_raw: np.ndarray, birim: str, fs: float, t0: float, ay: EmgAyarlari, kas='', taraf='', ad='') -> EmgKanal:
    uy = []
    x = np.asarray(x_raw, float)
    carp, w = uv_carpani(birim, x)
    if w:
        uy.append((UYARI, w, 'EMG'))
    x = x * carp
    kayip = kayip_maske(x, fs, ay.kayip_min_ms)
    xf = np.where(np.isfinite(x), x, 0.0)
    if np.nanstd(xf) == 0:
        uy.append((UYARI, f'EMG kanalı ({ad}) boş ya da sabit.', 'EMG'))
    y = xf
    if ay.hp and ay.hp > 0:
        y = sosfiltfilt(butter(ay.derece, ay.hp, 'highpass', fs=fs, output='sos'), y)
    if ay.lp and ay.lp > 0:
        if ay.lp < 0.5 * fs * 0.98:
            y = sosfiltfilt(butter(ay.derece, ay.lp, 'lowpass', fs=fs, output='sos'), y)
        else:
            uy.append((BILGI, f'Low-pass {ay.lp:g} Hz, Nyquist sınırına ({fs / 2:g} Hz) eşit ya da üstünde; uygulanmadı.', 'EMG'))
    if ay.notch:
        for h in (1, 2, 3):
            f0 = ay.notch_hz * h
            if f0 < 0.5 * fs * 0.98:
                b, a = iirnotch(f0, 30.0, fs=fs)
                y = filtfilt(b, a, y)
    if ay.zarf == 'lineer':
        z = sosfiltfilt(butter(4, ay.lineer_lp, 'lowpass', fs=fs, output='sos'), np.abs(y))
        z = np.clip(z, 0, None)
        gen = int(round(0.5 * fs / max(ay.lineer_lp, 1)))
    else:
        wn = max(int(round(ay.rms_ms / 1000.0 * fs)), 1)
        z = np.sqrt(np.convolve(y ** 2, np.ones(wn) / wn, mode='same'))
        gen = wn // 2 + 1
    kayip_z = _genislet(kayip, gen + int(round(0.01 * fs)))
    if kayip.any():
        ms = kayip.sum() / fs * 1000
        uy.append((UYARI, f'EMG ({ad}) sinyalinde toplam {ms:.0f} ms veri kaybı (sabit değer/boşluk); bu bölgeye giren '
                          'EMG değerleri boş bırakılır.', 'EMG'))
    z = z.copy()
    z[kayip_z] = np.nan
    # 50 Hz parazit
    try:
        f, p = welch(xf - xf.mean(), fs=fs, nperseg=min(1024, len(xf)))
        bant = (f >= 20) & (f <= min(450, fs / 2 - 1))
        p50 = (f >= ay.notch_hz - 2) & (f <= ay.notch_hz + 2)
        if bant.any() and p50.any() and p[bant].mean() > 0:
            oran = p[p50].mean() / p[bant].mean()
            if oran > ay.parazit_oran_esik and not ay.notch:
                uy.append((UYARI, f'EMG ({ad}) sinyalinde belirgin {ay.notch_hz:g} Hz şebeke paraziti '
                                  f'(güç oranı {oran:.0f}).', 'EMG'))
    except Exception:
        pass
    # doyma (clipping)
    if x.size and np.isfinite(x).any():
        mx, mn = np.nanmax(x), np.nanmin(x)
        n_uc = int(np.sum(x >= mx - 1e-9) + np.sum(x <= mn + 1e-9))
        if n_uc > max(5, 0.001 * len(x)) and (mx - mn) > 0:
            uy.append((UYARI, f'EMG ({ad}) sinyali uç değerlerde kesiliyor olabilir (doyma, {n_uc} örnek).', 'EMG'))
    return EmgKanal(kas, taraf, ad, fs, t0, y, z, kayip_z, uy)


# ---------------------------------------------------------------------------------
# Aktivasyon (N scriptiyle aynı yöntem)
# ---------------------------------------------------------------------------------
def esik_ve_burst(k: EmgKanal, a0_t: float, a1_t: float, ay: EmgAyarlari):
    """Eşik: analiz aralığında en sessiz `sessiz_ms` penceresi ortalaması + k·SD, tabanı tepe zarfın %5'i.
    Eşiğin üstünde >= min_aktif_ms süren bölgeler aktif; < birlestir_ms boşluklar birleştirilir."""
    fs = k.fs
    z = k.zarf
    a0 = max(int(round((a0_t - k.t0) * fs)), 0)
    a1 = min(int(round((a1_t - k.t0) * fs)), len(z))
    zz = z[a0:a1]
    w = int(round(ay.sessiz_ms / 1000 * fs))
    if len(zz) <= w or np.isfinite(zz).sum() <= w:
        return np.nan, []
    ok = np.isfinite(zz)
    zf = np.where(ok, zz, 0.0)
    cs = np.convolve(zf, np.ones(w) / w, mode='valid')
    cn = np.convolve(ok.astype(float), np.ones(w), mode='valid')
    cs[cn < w] = np.inf
    j = int(np.argmin(cs))
    taban = zz[j:j + w]
    esik = max(float(np.mean(taban) + ay.esik_sd * np.std(taban)), ay.esik_taban_tepe * float(np.nanmax(zz)))
    aktif = np.where(np.isfinite(z), z > esik, False)
    d = np.diff(np.r_[0, aktif.astype(int), 0])
    bas, son = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    bl = [[int(b), int(s)] for b, s in zip(bas, son)]
    bosluk = int(round(ay.birlestir_ms / 1000 * fs))
    minl = int(round(ay.min_aktif_ms / 1000 * fs))
    birl = []
    for b in bl:
        if birl and b[0] - birl[-1][1] < bosluk:
            birl[-1][1] = b[1]
        else:
            birl.append(b)
    return esik, [(b, s) for b, s in birl if s - b >= minl]


def aktivasyon(k: EmgKanal, t0: float, t1: float, ic: float, nic: float):
    """[t0, t1) penceresine kırpılmış aktivasyon. Zamanlar %GC olarak (IC=0, sonraki IC=100)."""
    fs = k.fs
    s0 = int(round((t0 - k.t0) * fs))
    s1 = int(round((t1 - k.t0) * fs))
    bl = k._burst or []
    kirp = [(max(b, s0), min(s, s1)) for b, s in bl if s > s0 and b < s1]
    sure = lambda s: k.t0 + s / fs
    gc = lambda s: 100.0 * (sure(s) - ic) / (nic - ic)
    if not kirp:
        return {'onset': np.nan, 'offset': np.nan, 'sure_ms': 0.0, 'aktif_yuzde': 0.0, 'aktif_basta': 0, 'aktif_sonda': 0}
    toplam = sum(s - b for b, s in kirp) / fs * 1000.0
    return {'onset': gc(kirp[0][0]), 'offset': gc(kirp[-1][1]), 'sure_ms': toplam,
            'aktif_yuzde': 100.0 * toplam / max((t1 - t0) * 1000.0, 1e-9),
            'aktif_basta': int(kirp[0][0] == s0), 'aktif_sonda': int(kirp[-1][1] == s1)}


def frekans(k: EmgKanal, t0: float, t1: float, ay: EmgAyarlari):
    """Medyan ve ortalama frekans (Hz): filtrelenmiş ham sinyalden, Hann pencereli periodogram."""
    fs = k.fs
    i0 = max(int(np.ceil((t0 - k.t0) * fs)), 0)
    i1 = min(int(np.floor((t1 - k.t0) * fs)) + 1, len(k.filtreli))
    seg = k.filtreli[i0:i1]
    if len(seg) < 64:
        return np.nan, np.nan, 'aralık frekans analizi için çok kısa (< 64 örnek)'
    if k.kayip[i0:i1].any():
        return np.nan, np.nan, 'aralıkta EMG veri kaybı var'
    f, p = periodogram(seg, fs=fs, window='hann', detrend='constant')
    ust = min(ay.lp if ay.lp else fs / 2, fs / 2)
    m = (f >= (ay.hp or 0)) & (f <= ust)
    f, p = f[m], p[m]
    if p.sum() <= 0:
        return np.nan, np.nan, 'aralıkta güç yok'
    mnf = float(np.sum(f * p) / np.sum(p))
    c = np.cumsum(p)
    yarim = c[-1] / 2
    j = int(np.searchsorted(c, yarim))
    if j == 0:
        mdf = float(f[0])
    else:
        mdf = float(f[j - 1] + (yarim - c[j - 1]) / max(c[j] - c[j - 1], 1e-30) * (f[j] - f[j - 1]))
    return mdf, mnf, None


# ---------------------------------------------------------------------------------
# Kanal adı önerisi ve sinyal durumu
# ---------------------------------------------------------------------------------
_KAS_DESEN = [
    ('TA', r'tib\w*[\s_.\-]*ant|t\.?\s*ant|\bta\b'),
    ('GM', r'gas\w*[\s_.\-]*med|med\w*[\s_.\-]*gas|\bgm\b|\bmg\b|gast\w*[\s_.\-]*m\b'),
    ('GL', r'gas\w*[\s_.\-]*lat|lat\w*[\s_.\-]*gas|\bgl\b|\blg\b'),
    ('SOL', r'sol(eus|eu)|\bsol\b'),
    ('PL', r'peron|fibul|\bpl\b'),
    ('RF', r'rect\w*[\s_.\-]*fem|\brf\b'),
    ('VM', r'vast\w*[\s_.\-]*med|\bvm\b|\bvmo\b'),
    ('VL', r'vast\w*[\s_.\-]*lat|\bvl\b'),
    ('BF', r'bic\w*[\s_.\-]*fem|\bbf\b|hams\w*[\s_.\-]*lat'),
    ('ST', r'semiten|\bst\b|hams\w*[\s_.\-]*med'),
    ('SM', r'semimem|\bsm\b'),
    ('GMED', r'glu\w*[\s_.\-]*med|\bgmed\b'),
    ('GMAX', r'glu\w*[\s_.\-]*max|\bgmax\b'),
    ('ADD', r'add\w*'),
    ('TFL', r'tensor|\btfl\b'),
    ('ES', r'erect|\bes\b|paraspin'),
    ('RA', r'rect\w*[\s_.\-]*abd|\bra\b'),
]


def kanal_onerisi(ad: str):
    """Kanal adından (kas, taraf) önerisi. Bulamazsa (None, None)."""
    s = re.sub(r'\.(v|emg|uv|mv)$', '', ad.strip(), flags=re.I)
    taraf = None
    m = re.match(r'^(l|r|left|right|sol|sag|sağ)[\s_.\-]+', s, re.I) or re.match(r'^(l|r)(?=[A-Z])', s)
    if m:
        taraf = 'L' if m.group(1).lower() in ('l', 'left', 'sol') else 'R'
        s2 = s[m.end():]
    else:
        m2 = re.search(r'[\s_.\-]+(l|r|left|right|sol|sag|sağ)$', s, re.I)
        if m2:
            taraf = 'L' if m2.group(1).lower() in ('l', 'left', 'sol') else 'R'
            s2 = s[:m2.start()]
        else:
            s2 = s
    kas = None
    for kod, desen in _KAS_DESEN:
        if re.search(desen, s2, re.I):
            kas = kod
            break
    return kas, taraf


def kanal_durumu(x: np.ndarray, birim: str, fs: float) -> dict:
    """Eşleştirme ekranı için kanalın sinyal durumu."""
    x = np.asarray(x, float)
    if x.size == 0 or not np.isfinite(x).any():
        return {'durum': 'bos', 'aciklama': 'Veri yok', 'rms_uv': 0.0, 'parazit_orani': 0.0}
    carp, _ = uv_carpani(birim, x)
    xu = np.where(np.isfinite(x), x, 0.0) * carp
    if np.std(xu) == 0:
        return {'durum': 'bos', 'aciklama': 'Sabit sinyal (boş kanal)', 'rms_uv': 0.0, 'parazit_orani': 0.0}
    try:
        y = sosfiltfilt(butter(4, [20, min(450, fs / 2 * 0.95)], 'bandpass', fs=fs, output='sos'), xu)
    except Exception:
        y = xu - xu.mean()
    rms = float(np.sqrt(np.mean(y ** 2)))
    f, p = welch(xu - xu.mean(), fs=fs, nperseg=min(1024, len(xu)))
    bant = (f >= 20) & (f <= min(450, fs / 2 - 1))
    p50 = (f >= 48) & (f <= 52)
    oran = float(p[p50].mean() / p[bant].mean()) if bant.any() and p50.any() and p[bant].mean() > 0 else 0.0
    if oran > 40:
        return {'durum': 'parazit', 'aciklama': f'Yalnızca 50 Hz şebeke paraziti (sensör bağlı değil?)', 'rms_uv': rms,
                'parazit_orani': oran}
    kayip = kayip_maske(xu, fs, 10.0).mean()
    acik = 'Kas sinyali'
    if kayip > 0.01:
        acik += f' (%{100 * kayip:.0f} veri kaybı)'
    return {'durum': 'sinyal', 'aciklama': acik, 'rms_uv': rms, 'parazit_orani': oran}


def emg_kanal_mi(ad: str, birim: str) -> bool:
    """Kuvvet plakası, senkron ve ayak anahtarı kanallarını ayıklar."""
    a = ad.lower()
    if re.match(r'^(force|moment|f[xyz]\d|m[xyz]\d)', a) or a.startswith(('force.', 'moment.')):
        return False
    if any(k in a for k in ('sync', 'switch', 'trigger', 'digital', 'foot switch', '.fs', 'accel', 'gyro', 'acc.', 'gyro.')):
        return False
    b = (birim or '').strip().lower()
    if b in ('n', 'nmm', 'nm', 'n.m', 'n.mm'):
        return False
    return True
