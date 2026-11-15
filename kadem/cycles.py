"""Yürüme döngüleri ve event kontrolleri."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .model import Trial, karsi
from .warnings_ import HATA, UYARI, BILGI


@dataclass
class DonguAyarlari:
    stride_aralik: tuple = (0.7, 2.5)       # s, dışındaysa uyarı
    stance_oran: tuple = (0.45, 0.75)       # stance/stride, dışındaysa uyarı
    ds1_max_oran: float = 0.25              # 1. çift destek / stride, üstündeyse uyarı
    min_stride: float = 0.25                # s, altındaysa döngü geçersiz (çift event)
    kinetik_esik: float = 5.0               # N/kg, GRF büyüklüğü
    kareye_yuvarla: bool = False            # kare bazlı mod: event zamanlarını en yakın kareye yuvarla

    def dict(self):
        return dict(self.__dict__)


@dataclass
class Dongu:
    trial: Trial
    taraf: str
    no: int
    ic: float
    nic: float
    fo: float | None = None
    cfo: float | None = None
    cic: float | None = None
    pcic: float | None = None
    kinetik: bool = False
    gecerli: bool = True
    grf_bas: float | None = None
    grf_son: float | None = None
    uyarilar: list = field(default_factory=list)   # (onem, mesaj, kategori)

    @property
    def sure(self) -> float:
        return self.nic - self.ic

    def olay(self, ad: str):
        return {'IC': self.ic, 'NIC': self.nic, 'FO': self.fo, 'CFO': self.cfo, 'CIC': self.cic,
                'PCIC': self.pcic}.get(ad)

    def uyar(self, onem, mesaj, kategori='EVENT'):
        self.uyarilar.append((onem, mesaj, kategori))

    @property
    def anahtar(self):
        return (self.trial.dosya, self.taraf, self.no)


OLAY_ADLARI = {
    'IC': 'IC (topuk teması)', 'CFO': 'karşı Foot Off', 'CIC': 'karşı IC', 'FO': 'Foot Off', 'NIC': 'sonraki IC',
    'PCIC': 'önceki karşı IC',
}


def _icinde(liste, a, b):
    return [t for t in liste if a < t < b]


def donguleri_kur(trial: Trial, ay: DonguAyarlari | None = None) -> list:
    ay = ay or DonguAyarlari()
    rate = trial.rate
    ev = {s: {k: list(v) for k, v in trial.events[s].items()} for s in trial.events}
    if ay.kareye_yuvarla:
        for s in ev:
            for k in ev[s]:
                ev[s][k] = [int(round(t * rate)) / rate for t in ev[s][k]]
    tol = 0.5 / rate
    t_pts = trial.t_first + np.arange(trial.n) / rate
    sonuc = []
    for s in ('L', 'R'):
        k = karsi(s)
        ics, fos = ev[s]['IC'], ev[s]['FO']
        kfos, kics = ev[k]['FO'], ev[k]['IC']
        gb = trial.grf_bilesenleri(s)
        for i in range(len(ics) - 1):
            ic, nic = ics[i], ics[i + 1]
            d = Dongu(trial, s, i + 1, ic, nic)
            sonuc.append(d)
            if ic < trial.t_first - tol or nic > trial.t_last + tol:
                d.gecerli = False
                d.uyar(HATA, 'Döngü kaydın dışına taşıyor; hesaplanmadı.')
                continue
            if nic - ic < ay.min_stride:
                d.gecerli = False
                d.uyar(HATA, f'Döngü çok kısa ({nic - ic:.3f} s): IC event\'i çift işaretlenmiş olabilir; hesaplanmadı.')
                continue
            # aynı taraf FO
            f = _icinde(fos, ic, nic)
            if not f:
                d.uyar(UYARI, 'Döngüde aynı tarafın Foot Off event\'i yok: stance, swing ve FO\'ya bağlı aralıklar hesaplanamaz.')
            else:
                if len(f) > 1:
                    d.uyar(UYARI, f'Döngüde {len(f)} adet aynı taraf Foot Off var; ilki kullanıldı.')
                d.fo = f[0]
            # karşı FO / IC
            cf = _icinde(kfos, ic, nic)
            if not cf:
                d.uyar(UYARI, 'Döngüde karşı tarafın Foot Off event\'i yok: 1. çift destek ve tek destek hesaplanamaz.')
            else:
                if len(cf) > 1:
                    d.uyar(UYARI, f'Döngüde {len(cf)} adet karşı Foot Off var; ilki kullanıldı.')
                d.cfo = cf[0]
            ci = _icinde(kics, ic, nic)
            if not ci:
                d.uyar(UYARI, 'Döngüde karşı tarafın IC event\'i yok: tek destek ve 2. çift destek hesaplanamaz.')
            else:
                if len(ci) > 1:
                    d.uyar(UYARI, f'Döngüde {len(ci)} adet karşı IC var.')
                    sonra = [t for t in ci if d.cfo is None or t > d.cfo]
                    d.cic = sonra[0] if sonra else ci[0]
                else:
                    d.cic = ci[0]
            onceki = [t for t in kics if t < ic]
            d.pcic = onceki[-1] if onceki else None
            # sıra kontrolü: IC < CFO < CIC < FO < NIC
            if d.cfo is not None and d.cic is not None and not d.cfo < d.cic:
                d.uyar(UYARI, 'Karşı taraf event sırası beklenmedik (karşı IC, karşı FO\'dan önce); '
                               'karşı event\'lere bağlı aralıklar hesaplanmadı.')
                d.cfo = d.cic = None
            if d.cic is not None and d.fo is not None and not d.cic < d.fo:
                d.uyar(UYARI, 'Karşı IC, aynı taraf Foot Off\'tan sonra geliyor (uçuş fazı ya da event hatası); '
                               'karşı IC kullanılmadı.')
                d.cic = None
            if d.cfo is not None and d.fo is not None and not d.cfo < d.fo:
                d.uyar(UYARI, 'Karşı Foot Off, aynı taraf Foot Off\'tan sonra geliyor; karşı FO kullanılmadı.')
                d.cfo = None
            # makullük kontrolleri (yalnızca uyarı)
            st = nic - ic
            if not (ay.stride_aralik[0] <= st <= ay.stride_aralik[1]):
                d.uyar(UYARI, f'Stride süresi olağan aralığın dışında ({st:.2f} s).')
            if d.fo is not None:
                oran = (d.fo - ic) / st
                if not (ay.stance_oran[0] <= oran <= ay.stance_oran[1]):
                    d.uyar(UYARI, f'Stance oranı olağan aralığın dışında (%{100 * oran:.0f}).')
            if d.cfo is not None and (d.cfo - ic) / st > ay.ds1_max_oran:
                d.uyar(UYARI, f'1. çift destek uzun (%{100 * (d.cfo - ic) / st:.0f} GC): event hatası olabilir.')
            # kinetik (kuvvet plakası)
            if gb is not None:
                dikey, ap, ml = gb
                st_son = d.fo if d.fo is not None else nic
                sec = (t_pts >= ic - tol) & (t_pts <= st_son + tol)
                mag = np.sqrt(dikey ** 2 + ap ** 2 + ml ** 2)
                gecerli = sec & ~np.isnan(mag)
                if gecerli.any():
                    mx = float(np.nanmax(mag[gecerli]))
                    if mx > ay.kinetik_esik:
                        d.kinetik = True
                        j = np.flatnonzero(gecerli)
                        d.grf_bas, d.grf_son = float(t_pts[j[0]]), float(t_pts[j[-1]])
                        ic_fark = d.grf_bas - ic
                        if ic_fark > 2.5 / rate:
                            d.uyar(UYARI, f'GRF, IC\'den {1000 * ic_fark:.0f} ms sonra başlıyor: kısmi basış ya da '
                                           'event ile plaka uyumsuzluğu olabilir.', 'GRF')
                        if d.fo is not None:
                            fo_fark = d.fo - d.grf_son
                            if fo_fark > 2.5 / rate:
                                d.uyar(UYARI, f'GRF, Foot Off\'tan {1000 * fo_fark:.0f} ms önce bitiyor: kısmi basış ya da '
                                               'event ile plaka uyumsuzluğu olabilir.', 'GRF')
                        ic_ = mag[j[0]:j[-1] + 1]
                        bos = int(np.isnan(ic_).sum())
                        if bos:
                            d.uyar(UYARI, f'GRF\'de stance içinde {bos} karelik boşluk var; bu aralığa giren kinetik '
                                           'değerler boş bırakılır.', 'GRF')
                    else:
                        d.uyar(BILGI, f'Stance\'te GRF var ama çok düşük (en fazla {mx:.1f} N/kg); kinetik sayılmadı.', 'GRF')
    return sonuc
