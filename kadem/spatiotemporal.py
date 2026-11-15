"""Zamansal-uzamsal parametreler ve zemin düzlemine göre parmak yüksekliği (toe clearance)."""
from __future__ import annotations

import numpy as np

from .model import Trial, Sinyal, karsi, PELVIS_MARKERLARI
from .cycles import Dongu
from .warnings_ import HATA, UYARI, BILGI

G = 9.81
ZEMIN_STANCE_PENCERE = (0.25, 0.50)
ZEMIN_MAX_REZIDU_MM = 5.0


def konum_zamanda(trial: Trial, etiket: str, t: float):
    p = trial.nokta(etiket)
    if p is None:
        return np.full(3, np.nan)
    f = (t - trial.t_first) * trial.rate
    f0 = int(np.floor(f))
    if abs(f - round(f)) < 1e-6:
        j = int(round(f))
        return p[j].astype(float) if 0 <= j < len(p) else np.full(3, np.nan)
    if f0 < 0 or f0 + 1 >= len(p):
        return np.full(3, np.nan)
    w = f - f0
    return (1 - w) * p[f0] + w * p[f0 + 1]


def _bacak_m(trial: Trial):
    v = [x for x in trial.bacak_mm.values() if x]
    return (sum(v) / len(v) / 1000.0) if v else None


def trial_zu(trial: Trial, notlar: list) -> dict:
    """İki taraf birlikte: hız ve kadans. notlar: (onem, mesaj) eklenir."""
    out = {'ZU:Hiz': np.nan, 'ZU:Kadans': np.nan, 'ZU:HizBoyutsuz': np.nan}
    tum = sorted([(t, 'L') for t in trial.events['L']['IC']] + [(t, 'R') for t in trial.events['R']['IC']])
    if len(tum) < 3:
        notlar.append((UYARI, 'Hız ve kadans için yeterli IC yok (en az 3 gerekir).'))
        return out
    zam = [t for t, _ in tum]
    taraf = [s for _, s in tum]
    sure = zam[-1] - zam[0]
    n_adim = len(tum) - 1
    if not all(taraf[i] != taraf[i + 1] for i in range(len(taraf) - 1)):
        notlar.append((UYARI, 'IC dizisi sağ/sol dönüşümlü değil (eksik ya da fazla event?); kadans süreye göre '
                              'hesaplandı, dikkatli yorumlayın.'))
    out['ZU:Kadans'] = 60.0 * n_adim / sure
    out['_n_adim'] = n_adim
    out['_sure'] = sure
    idx = [m for m in PELVIS_MARKERLARI if trial.var_mi(m)]
    if trial.u is not None and idx:
        def pelvis(t):
            with np.errstate(all='ignore'):
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', RuntimeWarning)
                    return np.nanmean([konum_zamanda(trial, m, t)[:2] for m in idx], axis=0)
        mesafe = abs(float((pelvis(zam[-1]) - pelvis(zam[0])) @ trial.u)) / 1000.0
        out['ZU:Hiz'] = mesafe / sure
        out['_mesafe'] = mesafe
        L = _bacak_m(trial)
        if L:
            out['ZU:HizBoyutsuz'] = out['ZU:Hiz'] / np.sqrt(G * L)
        else:
            notlar.append((BILGI, 'Bacak uzunluğu C3D\'de yok; boyutsuz hız hesaplanmadı.'))
    else:
        notlar.append((UYARI, 'Pelvis markerı ya da yürüme yönü yok; hız hesaplanmadı.'))
    return out


def dongu_zu(trial: Trial, d: Dongu, topuk: str = 'HEE') -> tuple:
    """Bir döngünün zamansal-uzamsal değerleri. Dönüş: (değerler, notlar)."""
    v = {}
    notlar = []
    st = d.sure
    v['ZU:StrideSuresi'] = st
    if d.fo is not None:
        v['ZU:StanceSuresi'] = d.fo - d.ic
        v['ZU:SwingSuresi'] = d.nic - d.fo
        v['ZU:StanceYuzde'] = 100 * (d.fo - d.ic) / st
        v['ZU:SwingYuzde'] = 100 * (d.nic - d.fo) / st
    if d.cfo is not None:
        v['ZU:CiftDestek1Suresi'] = d.cfo - d.ic
        v['ZU:KarsiFOYuzde'] = 100 * (d.cfo - d.ic) / st
    if d.cic is not None:
        v['ZU:KarsiICYuzde'] = 100 * (d.cic - d.ic) / st
    if d.cfo is not None and d.cic is not None:
        v['ZU:TekDestekSuresi'] = d.cic - d.cfo
        v['ZU:TekDestekYuzde'] = 100 * (d.cic - d.cfo) / st
    if d.cic is not None and d.fo is not None:
        v['ZU:CiftDestek2Suresi'] = d.fo - d.cic
        if d.cfo is not None:
            v['ZU:CiftDestekToplam'] = (d.cfo - d.ic) + (d.fo - d.cic)
    if d.pcic is not None:
        v['ZU:AdimSuresi'] = d.ic - d.pcic
    s, k = d.taraf, karsi(d.taraf)
    u = trial.u
    h_ip, h_k = f'{s}{topuk}', f'{k}{topuk}'
    if u is None:
        notlar.append((UYARI, 'Yürüme yönü yok; adım/stride uzunluğu hesaplanmadı.'))
    elif not trial.var_mi(h_ip):
        notlar.append((UYARI, f'{h_ip} markerı yok; adım/stride uzunluğu hesaplanmadı.'))
    else:
        h0 = konum_zamanda(trial, h_ip, d.ic)
        h1 = konum_zamanda(trial, h_ip, d.nic)
        stride_len = float((h1[:2] - h0[:2]) @ u) / 1000.0
        v['ZU:StrideUzunlugu'] = stride_len
        v['ZU:DonguHizi'] = stride_len / st
        if trial.var_mi(h_k):
            hk = konum_zamanda(trial, h_k, d.ic)
            adim = float((h0[:2] - hk[:2]) @ u) / 1000.0
            v['ZU:AdimUzunlugu'] = adim
            nrm = np.array([-u[1], u[0]])
            v['ZU:AdimGenisligi'] = abs(float((h0[:2] - hk[:2]) @ nrm)) / 1000.0
            if np.isfinite(adim) and adim <= 0:
                notlar.append((UYARI, f'Adım uzunluğu sıfır ya da negatif ({adim:.3f} m): öndeki ayak karşı ayağı geçmiyor '
                                      '(step-to yürüyüş?) ya da event hatası.'))
        L = _bacak_m(trial)
        if L:
            if 'ZU:AdimUzunlugu' in v:
                v['ZU:AdimUzunluguOran'] = v['ZU:AdimUzunlugu'] / L
            v['ZU:StrideUzunluguOran'] = stride_len / L
    return v, notlar


# ---------------------------------------------------------------------------------
# Zemin düzlemi ve toe clearance (W4)
# ---------------------------------------------------------------------------------
def zemin_duzlemi(trial: Trial):
    """Statik çekim olmadan zemin referansı: stance ortası (%25–50) TOE noktalarından
    z = ofset(taraf) + eğim × s düzlemi (s: noktaların ana doğrultusu boyunca konum).
    Global z, kalibrasyon eğimi nedeniyle adımdan adıma ~20–30 mm değişebilir; trial minimumu yanlış referanstır.
    Dönüş: (düzlem sözlüğü ya da None, notlar)."""
    notlar = []
    P = []
    for s in ('L', 'R'):
        toe = trial.nokta(f'{s}TOE')
        if toe is None:
            continue
        t = trial.t_first + np.arange(trial.n) / trial.rate
        for ic in trial.events[s]['IC']:
            fo = [x for x in trial.events[s]['FO'] if x > ic]
            if not fo:
                continue
            fo = fo[0]
            if not (0.4 <= fo - ic <= 1.0):
                continue
            a, b = ic + ZEMIN_STANCE_PENCERE[0] * (fo - ic), ic + ZEMIN_STANCE_PENCERE[1] * (fo - ic)
            m = (t >= a - 1e-9) & (t <= b + 1e-9)
            seg = toe[m]
            if seg.shape[0] == 0 or np.isnan(seg).any():
                continue
            P.append((s, seg[:, 0].mean(), seg[:, 1].mean(), float(np.median(seg[:, 2]))))
    if len(P) < 3:
        notlar.append((UYARI, 'Zemin düzlemi kurulamadı (yeterli stance/TOE noktası yok); toe clearance hesaplanamaz.'))
        return None, notlar
    sides = [p[0] for p in P]
    xy = np.array([[p[1], p[2]] for p in P])
    z = np.array([p[3] for p in P])
    c = xy.mean(0)
    u = np.linalg.svd(xy - c)[2][0]
    sv = (xy - c) @ u
    tl = np.array([x == 'L' for x in sides], float)
    tr = 1.0 - tl
    cols, names = [], []
    if tl.sum() > 0:
        cols.append(tl); names.append('L')
    if tr.sum() > 0:
        cols.append(tr); names.append('R')
    A = np.column_stack(cols + [sv])
    coef = np.linalg.lstsq(A, z, rcond=None)[0]
    rez = z - A @ coef
    zf = {'c': c, 'u': u, 'ofset': dict(zip(names, coef[:-1])), 'egim': coef[-1], 'rezidu_sd': float(rez.std()),
          'n': len(P), 'nparam': A.shape[1]}
    if zf['n'] <= zf['nparam']:
        notlar.append((UYARI, f'Zemin düzlemi {zf["n"]} noktadan kuruldu, uyum doğrulanamaz; toe clearance dikkatli '
                              'yorumlanmalı.'))
    elif zf['rezidu_sd'] > ZEMIN_MAX_REZIDU_MM:
        notlar.append((UYARI, f'Zemin düzlemi uyumu zayıf (artık SD {zf["rezidu_sd"]:.1f} mm); toe clearance şüpheli.'))
    return zf, notlar


def toe_clearance_sinyali(trial: Trial, taraf: str, zf: dict):
    toe = trial.nokta(f'{taraf}TOE')
    if toe is None or zf is None or taraf not in zf['ofset']:
        return None
    s = (toe[:, :2] - zf['c']) @ zf['u']
    v = toe[:, 2] - (zf['ofset'][taraf] + zf['egim'] * s)
    return Sinyal(trial.t_first, trial.rate, v.astype(float), 'mm')
