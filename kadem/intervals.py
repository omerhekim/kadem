"""Aralıklar (event tabanlı), anlar ve aralık içi seri çıkarma.

Çapa (anchor) türleri:
  {'olay': 'IC'|'CFO'|'CIC'|'FO'|'NIC'|'PCIC', 'kayma_ms': 0, 'kayma_gc': 0}
  {'yuzde': p, 'taban': 'GC'|'ST'|'SW'}           # %GC, %stance, %swing noktası
  {'ref': '<referans an id>', 'kayma_ms': 0, 'kayma_gc': 0}   # referans an (ör. A2 tepe anı), isteğe bağlı kayma
  {'ozel': 'SSMID'|'SW33'|'SW50'}                    # güç fazı arama pencereleri için
Aralık: başlangıç ve bitiş çapası. Başlangıç = bitiş ise 'an'.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .cycles import Dongu, OLAY_ADLARI
from .dil import _


@dataclass
class Aralik:
    id: str
    ad: str
    bas: dict
    son: dict
    kisa: str = ''
    aciklama: str = ''
    ozel: bool = False        # kullanıcı tanımlı

    @property
    def an_mi(self) -> bool:
        return self.bas == self.son

    def dict(self):
        return {'id': self.id, 'ad': self.ad, 'bas': self.bas, 'son': self.son, 'kisa': self.kisa,
                'aciklama': self.aciklama, 'ozel': self.ozel, 'an': self.an_mi}

    @staticmethod
    def from_dict(d):
        return Aralik(d['id'], d['ad'], d['bas'], d['son'], d.get('kisa', ''), d.get('aciklama', ''), d.get('ozel', True))


def O(ad, **kw):
    d = {'olay': ad}
    d.update(kw)
    return d


def Y(p, taban='GC'):
    return {'yuzde': float(p), 'taban': taban}


HAZIR_ARALIKLAR = [
    Aralik('GC', 'Tüm döngü (IC → sonraki IC)', O('IC'), O('NIC'), 'GC'),
    Aralik('ST', 'Stance (IC → Foot Off)', O('IC'), O('FO'), 'Stance'),
    Aralik('SW', 'Swing (Foot Off → sonraki IC)', O('FO'), O('NIC'), 'Swing'),
    Aralik('DS1', '1. çift destek (IC → karşı Foot Off)', O('IC'), O('CFO'), 'DS1'),
    Aralik('SS', 'Tek destek (karşı Foot Off → karşı IC)', O('CFO'), O('CIC'), 'SS'),
    Aralik('DS2', '2. çift destek (karşı IC → Foot Off)', O('CIC'), O('FO'), 'DS2'),
    Aralik('PO', 'İtme penceresi (Foot Off öncesi döngünün %20\'si → Foot Off)', O('FO', kayma_gc=-20.0), O('FO'), 'PushOff'),
    Aralik('ST1', 'Stance ilk yarısı (%0–50 stance)', Y(0, 'ST'), Y(50, 'ST'), 'Stance1'),
    Aralik('ST2', 'Stance ikinci yarısı (%50–100 stance)', Y(50, 'ST'), Y(100, 'ST'), 'Stance2'),
]
HAZIR_ANLAR = [
    Aralik('@IC', 'IC anı', O('IC'), O('IC'), 'atIC'),
    Aralik('@CFO', 'Karşı Foot Off anı', O('CFO'), O('CFO'), 'atOppFO'),
    Aralik('@CIC', 'Karşı IC anı', O('CIC'), O('CIC'), 'atOppIC'),
    Aralik('@FO', 'Foot Off anı', O('FO'), O('FO'), 'atFO'),
]


def capa_metni(c: dict, ref_adlari: dict | None = None) -> str:
    if 'olay' in c:
        s = OLAY_ADLARI.get(c['olay'], c['olay'])
        if c.get('kayma_ms') or c.get('kayma_gc'):
            s = _(s)        # kayma eklenince bütün metin sözlükte bulunmaz; adı burada çevir
        if c.get('kayma_ms'):
            s += f' {c["kayma_ms"]:+g} ms'
        if c.get('kayma_gc'):
            s += f' {c["kayma_gc"]:+g} %GC'
        return s
    if 'yuzde' in c:
        return f'%{c["yuzde"]:g} {dict(GC="GC", ST="stance", SW="swing")[c.get("taban", "GC")]}'
    if 'ref' in c:
        s = (ref_adlari or {}).get(c['ref']) or (f'{c["ref"][4:]} tepe anı' if c['ref'].startswith('FAZ:') else c['ref'])
        if c.get('kayma_ms') or c.get('kayma_gc'):
            s = _(s)
        if c.get('kayma_ms'):
            s += f' {c["kayma_ms"]:+g} ms'
        if c.get('kayma_gc'):
            s += f' {c["kayma_gc"]:+g} %GC'
        return s
    if 'ozel' in c:
        return {'SSMID': 'tek destek ortası', 'SW33': 'swing %33', 'SW50': 'swing %50'}.get(c['ozel'], c['ozel'])
    return '?'


def capa_zamani(c: dict, d: Dongu, ref_zaman: dict | None = None):
    """Çapanın bu döngüdeki zamanı (s). Dönüş: (t, None) ya da (None, neden)."""
    if 'olay' in c:
        t = d.olay(c['olay'])
        if t is None:
            return None, f'{OLAY_ADLARI.get(c["olay"], c["olay"])} yok'
        t = t + float(c.get('kayma_ms', 0) or 0) / 1000.0 + float(c.get('kayma_gc', 0) or 0) / 100.0 * d.sure
        return t, None
    if 'yuzde' in c:
        p = float(c['yuzde']) / 100.0
        taban = c.get('taban', 'GC')
        if taban == 'GC':
            return d.ic + p * d.sure, None
        if d.fo is None:
            return None, 'Foot Off yok'
        if taban == 'ST':
            return d.ic + p * (d.fo - d.ic), None
        return d.fo + p * (d.nic - d.fo), None
    if 'ref' in c:
        if ref_zaman is None:
            return None, 'referans an tanımsız'
        r = ref_zaman.get(c['ref'])
        if r is None:
            return None, 'referans an tanımsız'
        t, neden = r
        if t is None:
            return None, neden
        t = t + float(c.get('kayma_ms', 0) or 0) / 1000.0 + float(c.get('kayma_gc', 0) or 0) / 100.0 * d.sure
        return t, None
    if 'ozel' in c:
        o = c['ozel']
        if o == 'SSMID':
            if d.cfo is None or d.cic is None:
                return None, 'tek destek (karşı FO/IC) yok'
            return 0.5 * (d.cfo + d.cic), None
        if o in ('SW33', 'SW50'):
            if d.fo is None:
                return None, 'Foot Off yok'
            return d.fo + (1 / 3 if o == 'SW33' else 0.5) * (d.nic - d.fo), None
    return None, 'bilinmeyen çapa'


def aralik_zamani(a: Aralik, d: Dongu, ref_zaman: dict | None = None):
    t0, n0 = capa_zamani(a.bas, d, ref_zaman)
    if t0 is None:
        return None, None, n0
    if a.an_mi:
        return t0, t0, None
    t1, n1 = capa_zamani(a.son, d, ref_zaman)
    if t1 is None:
        return None, None, n1
    if t1 < t0:
        return None, None, 'aralığın sonu başından önce'
    return t0, t1, None


# ---------------------------------------------------------------------------------
# Seri çıkarma
# ---------------------------------------------------------------------------------
TOL = 1e-3   # örnek cinsinden: event zamanı bu kadar yakınsa örneğin kendisi sayılır


def _interp(v: np.ndarray, p: float) -> float:
    n = len(v)
    i = int(np.floor(p))
    if abs(p - round(p)) < TOL:
        j = int(round(p))
        return float(v[j]) if 0 <= j < n else np.nan
    if i < 0 or i + 1 >= n:
        return np.nan
    w = p - i
    a, b = v[i], v[i + 1]
    if np.isnan(a) or np.isnan(b):
        return np.nan
    return float((1 - w) * a + w * b)


def seri(sig, t0: float, t1: float):
    """[t0, t1] aralığındaki örnekler + interpolasyonla uç değerler.
    Dönüş: (tt, vv) ya da (None, neden)."""
    v = sig.v
    n = len(v)
    p0 = (t0 - sig.t0) * sig.fs
    p1 = (t1 - sig.t0) * sig.fs
    if p0 < -TOL or p1 > n - 1 + TOL:
        return None, 'aralık kaydın dışına taşıyor'
    if t1 == t0:
        return np.array([t0]), np.array([_interp(v, p0)])
    i0 = int(np.ceil(p0 - TOL))
    i1 = int(np.floor(p1 + TOL))
    idx = np.arange(max(i0, 0), min(i1, n - 1) + 1)
    tt = sig.t0 + idx / sig.fs
    vv = v[idx].astype(float)
    if abs(p0 - round(p0)) >= TOL:
        tt = np.r_[t0, tt]
        vv = np.r_[_interp(v, p0), vv]
    if abs(p1 - round(p1)) >= TOL:
        tt = np.r_[tt, t1]
        vv = np.r_[vv, _interp(v, p1)]
    return tt, vv


def temas_uygula(sig, d: Dongu):
    """GRF için: bu döngünün stance'i dışında ve stance'in baş/son NaN dizilerinde değer 0 (temas yok).
    Stance içindeki iç boşluklar NaN kalır."""
    from .model import Sinyal
    v = sig.v.copy()
    t = sig.t0 + np.arange(len(v)) / sig.fs
    st_son = d.fo if d.fo is not None else d.nic
    tol = 0.5 / sig.fs
    ic_mask = (t >= d.ic - tol) & (t <= st_son + tol)
    disari = ~ic_mask & np.isnan(v)
    v[disari] = 0.0
    j = np.flatnonzero(ic_mask)
    if len(j):
        seg = v[j]
        ok = np.flatnonzero(~np.isnan(seg))
        if len(ok) == 0:
            seg[:] = 0.0
        else:
            seg[:ok[0]] = 0.0
            seg[ok[-1] + 1:] = 0.0
        v[j] = seg
    return Sinyal(sig.t0, sig.fs, v, sig.birim, False, sig.nan_nedeni)
