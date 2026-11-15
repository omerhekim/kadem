"""Aralık istatistikleri."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .warnings_ import BILGI, UYARI

_trapz = getattr(np, 'trapezoid', None) or np.trapz


@dataclass(frozen=True)
class Ist:
    id: str
    ad: str
    tur: str          # deger | zaman | alan | egim | sure | emg | emg_zaman | emg_trial | an
    aciklama: str = ''
    kisa: str = ''


ISTATISTIKLER = [
    Ist('ort', 'Ortalama', 'deger', 'Zamana göre ağırlıklı ortalama (integral / süre).', 'Mean'),
    Ist('max', 'Maksimum', 'deger', '', 'Max'),
    Ist('min', 'Minimum', 'deger', '', 'Min'),
    Ist('rom', 'Açıklık (Maks − Min)', 'deger', '', 'ROM'),
    Ist('bas', 'Aralık başındaki değer', 'deger', '', 'Start'),
    Ist('son', 'Aralık sonundaki değer', 'deger', '', 'End'),
    Ist('tmax', 'Maksimumun zamanı', 'zaman', '', 'tMax'),
    Ist('tmin', 'Minimumun zamanı', 'zaman', '', 'tMin'),
    Ist('absmax', 'İşaretli mutlak maksimum', 'deger', 'Mutlak değeri en büyük örnek, işaretiyle.', 'AbsMax'),
    Ist('max_bas', 'Maksimum − başlangıç değeri', 'deger', '', 'MaxMinusStart'),
    Ist('min_bas', 'Minimum − başlangıç değeri', 'deger', '', 'MinMinusStart'),
    Ist('sapma', 'Başlangıca göre en büyük sapma (işaretli)', 'deger',
        'Başlangıç değerinden mutlak olarak en uzak sapma, yönüyle.', 'MaxDev'),
    Ist('alan_poz', 'Pozitif alan (integral, negatif kısımlar 0)', 'alan',
        'Güç için iş (J/kg), kuvvet için impuls.', 'PosArea'),
    Ist('alan_neg', 'Negatif alan (integral, pozitif kısımlar 0)', 'alan', '', 'NegArea'),
    Ist('alan_net', 'Net alan (integral)', 'alan', '', 'NetArea'),
    Ist('lob_poz', 'En büyük pozitif lobun alanı', 'alan',
        'Sıfır geçişleriyle ayrılan pozitif bölgelerden alanı en büyük olanı.', 'MaxPosLobe'),
    Ist('lob_neg', 'En büyük negatif lobun alanı', 'alan',
        'Sıfır geçişleriyle ayrılan negatif bölgelerden alanı (mutlak) en büyük olanı; sonuç negatiftir.', 'MaxNegLobe'),
    Ist('ilk_lob_poz', 'İlk pozitif lobun alanı', 'alan',
        'Aralığın başından itibaren ilk pozitif bölgenin alanı. Çok kısa loblar atlanır (Ayarlar).', 'FirstPosLobe'),
    Ist('ilk_lob_poz_max', 'İlk pozitif lobun maksimumu', 'deger', '', 'FirstPosLobeMax'),
    Ist('ilk_lob_poz_tmax', 'İlk pozitif lobun maksimumunun zamanı', 'zaman', '', 'tFirstPosLobeMax'),
    Ist('ilk_lob_neg', 'İlk negatif lobun alanı', 'alan',
        'Aralığın başından itibaren ilk negatif bölgenin alanı; sonuç negatiftir. Çok kısa loblar atlanır (Ayarlar).',
        'FirstNegLobe'),
    Ist('ilk_lob_neg_min', 'İlk negatif lobun minimumu', 'deger', '', 'FirstNegLobeMin'),
    Ist('ilk_lob_neg_tmin', 'İlk negatif lobun minimumunun zamanı', 'zaman', '', 'tFirstNegLobeMin'),
    Ist('egim_max', 'Maksimum eğim', 'egim', 'Örn. dikey GRF yüklenme hızı.', 'MaxSlope'),
    Ist('egim_min', 'Minimum eğim', 'egim', '', 'MinSlope'),
    Ist('tepe2', 'İkinci tepe (çift tepe, vadi koşullu)', 'deger',
        'Aralığın ikinci yarısındaki tepe; ilk tepeyle arasında yeterli vadi yoksa boş.', 'Peak2'),
    Ist('ss', 'Aralık içi standart sapma', 'deger', '', 'SD'),
    Ist('sure', 'Aralığın süresi', 'sure', '', 'Dur'),
    Ist('deger', 'Değer', 'an', 'Seçilen andaki değer.', 'Val'),
    # EMG'ye özgü
    Ist('onset', 'Aktivasyon başlangıcı', 'emg_zaman', 'Aralıktaki ilk aktif bölgenin başlangıcı.', 'Onset'),
    Ist('offset', 'Aktivasyon bitişi', 'emg_zaman', 'Aralıktaki son aktif bölgenin bitişi.', 'Offset'),
    Ist('aktif_ms', 'Aktif süre (ms)', 'emg', '', 'ActiveMs'),
    Ist('aktif_yuzde', 'Aktif süre (% aralık)', 'emg', '', 'ActivePct'),
    Ist('aktif_basta', 'Aralık başında aktif mi (1/0)', 'emg', '', 'ActiveAtStart'),
    Ist('aktif_sonda', 'Aralık sonunda aktif mi (1/0)', 'emg', '', 'ActiveAtEnd'),
    Ist('mdf', 'Medyan frekans (Hz)', 'emg', 'Filtrelenmiş ham sinyal, Hann pencereli periodogram.', 'MDF'),
    Ist('mnf', 'Ortalama frekans (Hz)', 'emg', '', 'MNF'),
    Ist('mdf_egim', 'Yorgunluk: medyan frekans eğimi (trial içi, Hz/s)', 'emg_trial',
        'Döngülerin MDF değerlerinin zamana göre doğrusal eğimi. Kısa trial\'larda ve yürüyüşte yorumu sınırlıdır.',
        'MDFSlope'),
    Ist('cci', 'Ko-kontraksiyon indeksi (%)', 'cci', 'Falconer–Winter: 2 × ortak alan / toplam alan × 100.', 'CCI'),
]
IST = {i.id: i for i in ISTATISTIKLER}

# Faz (Winter) istatistikleri
FAZ_ISTATISTIKLERI = [
    Ist('tepe', 'Tepe değeri', 'deger', '', 'Peak'),
    Ist('tepe_zamani', 'Tepe zamanı', 'zaman', '', 'tPeak'),
    Ist('is', 'İş (fazın alanı, J/kg)', 'alan', '', 'Work'),
    Ist('faz_bas', 'Faz başlangıcı', 'zaman', '', 'Start'),
    Ist('faz_son', 'Faz bitişi', 'zaman', '', 'End'),
    Ist('faz_sure', 'Faz süresi', 'sure', '', 'Dur'),
]
FAZ_IST = {i.id: i for i in FAZ_ISTATISTIKLERI}

ZAMAN_BIRIMLERI = {
    '%GC': '% döngü (IC = 0)',
    '%ST': '% stance',
    '%SW': '% swing',
    '%AR': '% aralık',
    's': 's (IC\'den itibaren)',
    'ms_ar': 'ms (aralık başından)',
}
SURE_BIRIMLERI = {'s': 's', 'ms': 'ms', '%GC': '% döngü', '%ST': '% stance', '%SW': '% swing'}

GENLIK_ISTATISTIKLERI = {'ort', 'max', 'min', 'rom', 'bas', 'son', 'absmax', 'max_bas', 'min_bas', 'sapma',
                         'alan_poz', 'alan_neg', 'alan_net', 'lob_poz', 'lob_neg', 'ilk_lob_poz',
                         'ilk_lob_poz_max', 'ilk_lob_neg', 'ilk_lob_neg_min', 'egim_max', 'egim_min', 'tepe2', 'ss', 'deger',
                         'tepe', 'is'}


def zaman_cevir(t: float, birim: str, ic: float, nic: float, fo, t0: float, t1: float):
    if t is None or not np.isfinite(t):
        return np.nan
    if birim == '%GC':
        return 100.0 * (t - ic) / (nic - ic)
    if birim == '%ST':
        return 100.0 * (t - ic) / (fo - ic) if fo is not None else np.nan
    if birim == '%SW':
        return 100.0 * (t - fo) / (nic - fo) if fo is not None else np.nan
    if birim == '%AR':
        return 100.0 * (t - t0) / (t1 - t0) if t1 > t0 else np.nan
    if birim == 's':
        return t - ic
    if birim == 'ms_ar':
        return 1000.0 * (t - t0)
    return 100.0 * (t - ic) / (nic - ic)


def sure_cevir(dt: float, birim: str, ic, nic, fo):
    if birim == 's':
        return dt
    if birim == 'ms':
        return 1000.0 * dt
    if birim == '%GC':
        return 100.0 * dt / (nic - ic)
    if birim == '%ST':
        return 100.0 * dt / (fo - ic) if fo is not None else np.nan
    if birim == '%SW':
        return 100.0 * dt / (nic - fo) if fo is not None else np.nan
    return dt


def _yumusat(vv, k):
    if k <= 1 or len(vv) < 3:
        return vv
    pad = np.pad(vv, (k // 2, k // 2), mode='edge')
    sm = np.convolve(pad, np.ones(k) / k, mode='valid')
    return sm[:len(vv)]


def ikinci_tepe(fz: np.ndarray, vadi_esik: float, son_atla: float = 0.05):
    """P10 yöntemi: aralığın ikinci yarısındaki tepe; iki tepe arasında vadi_esik kadar çukur yoksa NaN."""
    n = len(fz)
    if n < 20:
        return np.nan, None
    h = n // 2
    i1 = int(np.argmax(fz[:h]))
    son = n - max(int(round(son_atla * n)), 1)
    if son - h < 3:
        return np.nan, None
    i2 = h + int(np.argmax(fz[h:son]))
    if i2 <= i1 + 2:
        return np.nan, None
    k = 3
    if i2 - k < 0 or i2 + k >= n or fz[i2] < fz[i2 - k:i2 + k + 1].max() - 1e-12:
        return np.nan, None
    vadi = np.min(fz[i1:i2 + 1])
    if vadi <= min(fz[i1], fz[i2]) - vadi_esik:
        return float(fz[i2]), i2
    return np.nan, None


def pozitif_loblar(tt, vv):
    alanlar = []
    i, n = 0, len(vv)
    while i < n:
        if vv[i] > 0:
            j = i
            while j < n and vv[j] > 0:
                j += 1
            a, b = max(i - 1, 0), min(j + 1, n)
            alanlar.append(float(_trapz(np.clip(vv[a:b], 0, None), tt[a:b])))
            i = j
        else:
            i += 1
    return alanlar


def loblar(tt, vv, isaret: int):
    """Sıfır geçişleriyle ayrılan, işareti `isaret` (+1/−1) olan bölgeler.
    Her lob: alan (işaretli, pozitif_loblar ile aynı kural), tepe (lobun uç değeri), tepe_t, sure (s; sıfır geçişleri
    doğrusal interpolasyonla), basta/sonda (lob aralığın ilk/son örneğine dayanıyor mu)."""
    w = np.asarray(vv, float) * isaret
    out = []
    i, n = 0, len(w)
    while i < n:
        if w[i] > 0:
            j = i
            while j < n and w[j] > 0:
                j += 1
            a, b = max(i - 1, 0), min(j + 1, n)
            alan = float(_trapz(np.clip(w[a:b], 0, None), tt[a:b])) * isaret
            k = i + int(np.argmax(w[i:j]))
            if i > 0:
                tb = tt[i - 1] + (0 - w[i - 1]) / (w[i] - w[i - 1]) * (tt[i] - tt[i - 1])
            else:
                tb = tt[0]
            if j < n:
                ts = tt[j - 1] + (0 - w[j - 1]) / (w[j] - w[j - 1]) * (tt[j] - tt[j - 1])
            else:
                ts = tt[n - 1]
            out.append({'alan': alan, 'tepe': float(vv[k]), 'tepe_t': float(tt[k]), 'sure': float(ts - tb),
                        'basta': i == 0, 'sonda': j == n})
            i = j
        else:
            i += 1
    return out


def hesapla(ist: str, tt: np.ndarray, vv: np.ndarray, ctx: dict, par: dict | None = None):
    """Genel istatistik. ctx: ic, nic, fo, t0, t1, zaman_birimi. Dönüş: (değer, notlar[list[(onem, mesaj)]])."""
    par = par or {}
    notlar = []
    ic, nic, fo, t0, t1 = ctx['ic'], ctx['nic'], ctx.get('fo'), ctx['t0'], ctx['t1']
    zb = ctx.get('zaman_birimi', '%GC')
    n = len(vv)

    def sinir(j, ad):
        if n > 2 and (j == 0 or j == n - 1):
            if j == 0:
                notlar.append((BILGI, f'{ad} aralığın ilk örneğinde (eğri aralığa girerken zaten bu yönde '
                                      f'ilerliyor); gerçek bir tepe olmayabilir.'))
            else:
                notlar.append((BILGI, f'{ad} aralığın son örneğinde (aralık bittiğinde eğri hâlâ bu yönde '
                                      f'ilerliyor); gerçek bir tepe olmayabilir.'))

    if ist in ('deger', 'bas'):
        return float(vv[0]), notlar
    if ist == 'son':
        return float(vv[-1]), notlar
    if ist == 'ort':
        if n == 1 or tt[-1] == tt[0]:
            return float(vv[0]), notlar
        return float(_trapz(vv, tt) / (tt[-1] - tt[0])), notlar
    if ist == 'ss':
        return float(np.std(vv)), notlar
    if ist == 'max':
        j = int(np.argmax(vv)); sinir(j, 'Maksimum')
        return float(vv[j]), notlar
    if ist == 'min':
        j = int(np.argmin(vv)); sinir(j, 'Minimum')
        return float(vv[j]), notlar
    if ist == 'rom':
        return float(np.max(vv) - np.min(vv)), notlar
    if ist in ('tmax', 'tmin'):
        k = int(round(float(par.get('yumusatma_ms', 0) or 0) / 1000.0 * ctx.get('fs', 100.0)))
        w = _yumusat(vv, k) if k > 1 else vv
        j = int(np.argmax(w)) if ist == 'tmax' else int(np.argmin(w))
        sinir(j, 'Maksimum' if ist == 'tmax' else 'Minimum')
        return zaman_cevir(float(tt[j]), zb, ic, nic, fo, t0, t1), notlar
    if ist == 'absmax':
        j = int(np.argmax(np.abs(vv))); sinir(j, 'Mutlak maksimum')
        return float(vv[j]), notlar
    if ist == 'max_bas':
        return float(np.max(vv) - vv[0]), notlar
    if ist == 'min_bas':
        return float(np.min(vv) - vv[0]), notlar
    if ist == 'sapma':
        dd = vv - vv[0]
        return float(dd[int(np.argmax(np.abs(dd)))]), notlar
    if ist == 'alan_poz':
        return float(_trapz(np.clip(vv, 0, None), tt)), notlar
    if ist == 'alan_neg':
        return float(_trapz(np.clip(vv, None, 0), tt)), notlar
    if ist == 'alan_net':
        return float(_trapz(vv, tt)), notlar
    if ist == 'lob_poz':
        al = pozitif_loblar(tt, vv)
        return (max(al) if al else 0.0), notlar
    if ist == 'lob_neg':
        ll = loblar(tt, vv, -1)
        return (min(x['alan'] for x in ll) if ll else 0.0), notlar
    if ist.startswith('ilk_lob_'):
        poz = ist.startswith('ilk_lob_poz')
        yon = 'pozitif' if poz else 'negatif'
        ll = loblar(tt, vv, 1 if poz else -1)
        esik = float(ctx.get('lob_min_s', 0.0) or 0.0)
        atlanan = 0
        sec = None
        for x in ll:
            if x['sure'] < esik - 1e-9:
                atlanan += 1
                continue
            sec = x
            break
        if atlanan:
            notlar.append((BILGI, f'İlk {yon} lob aranırken eşikten kısa {atlanan} lob atlandı '
                                  f'(en kısa lob süresi {1000 * esik:.0f} ms).'))
        if sec is None:
            notlar.append((BILGI, f'Aralıkta {yon} lob bulunamadı; değer boş bırakıldı.'))
            return np.nan, notlar
        if sec['basta']:
            notlar.append((BILGI, f'İlk {yon} lob aralığın ilk örneğinde başlıyor (eğri aralığa girerken zaten {yon}); '
                                  f'lobun başı aralığın dışında kalmış olabilir.'))
        if sec['sonda']:
            notlar.append((BILGI, f'İlk {yon} lob aralığın son örneğine kadar sürüyor (aralık bittiğinde eğri hâlâ {yon}); '
                                  f'lobun sonu aralığın dışında kalmış olabilir.'))
        if ist in ('ilk_lob_poz', 'ilk_lob_neg'):
            return sec['alan'], notlar
        if ist in ('ilk_lob_poz_max', 'ilk_lob_neg_min'):
            return sec['tepe'], notlar
        return zaman_cevir(sec['tepe_t'], zb, ic, nic, fo, t0, t1), notlar
    if ist in ('egim_max', 'egim_min'):
        if n < 3:
            return np.nan, [(UYARI, 'Eğim için aralıkta yeterli örnek yok.')]
        g = np.gradient(vv, tt)
        j = int(np.argmax(g)) if ist == 'egim_max' else int(np.argmin(g))
        return float(g[j]), notlar
    if ist == 'tepe2':
        esik = par.get('vadi_esik')
        if esik is None:
            esik = 0.03 * float(np.max(np.abs(vv))) if n else 0.0
        v2, _ = ikinci_tepe(vv, float(esik), float(par.get('son_atla', 0.05)))
        if not np.isfinite(v2):
            notlar.append((BILGI, 'Çift tepe bulunamadı (tek tepeli profil ya da vadi yetersiz).'))
        return v2, notlar
    if ist == 'sure':
        return sure_cevir(t1 - t0, zb, ic, nic, fo), notlar
    raise KeyError(ist)
