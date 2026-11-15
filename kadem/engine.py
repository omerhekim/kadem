"""Sorgu motoru: her döngü için (aralık × değişken × istatistik) değerlerini hesaplar."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, asdict

import numpy as np

from . import variables as V
from .cycles import Dongu, DonguAyarlari, donguleri_kur
from .emg import EmgAyarlari, kanal_isle, esik_ve_burst, aktivasyon, frekans
from .intervals import Aralik, HAZIR_ARALIKLAR, HAZIR_ANLAR, aralik_zamani, capa_zamani, seri, temas_uygula
from .model import Trial, Sinyal, karsi, ascii_ad
from .spatiotemporal import trial_zu, dongu_zu, zemin_duzlemi, toe_clearance_sinyali
from .stats import IST, FAZ_IST, hesapla, zaman_cevir, sure_cevir, GENLIK_ISTATISTIKLERI, _trapz
from .warnings_ import HATA, UYARI, BILGI, Uyari


# ---------------------------------------------------------------------------------
# Tanımlar
# ---------------------------------------------------------------------------------
@dataclass
class Sorgu:
    kod: str
    degisken: str
    bilesen: str | None = None
    aralik: str | None = None
    ist: str = 'max'
    zaman_birimi: str = '%GC'
    taraf: str = 'ipsi'           # ipsi | karsi
    par: dict = field(default_factory=dict)
    aciklama: str = ''
    paket: str = ''

    def dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        v = {k: d.get(k) for k in ('kod', 'degisken', 'bilesen', 'aralik', 'ist', 'zaman_birimi', 'taraf', 'par', 'aciklama',
                                   'paket') if k in d and d.get(k) is not None}
        v.setdefault('kod', '')
        v.setdefault('degisken', '')
        return Sorgu(**v)


@dataclass
class RefAn:
    id: str
    ad: str
    degisken: str
    bilesen: str | None
    aralik: str
    ekstremum: str = 'max'        # max | min
    taraf: str = 'ipsi'
    yumusatma_ms: float = 0.0

    def dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return RefAn(**{k: d[k] for k in ('id', 'ad', 'degisken', 'bilesen', 'aralik', 'ekstremum', 'taraf',
                                          'yumusatma_ms') if k in d})


@dataclass
class DalgaFormu:
    """Zaman normalize dalga formu (SPM ve grafikler için): aralık n eşit noktaya bölünür."""
    kod: str
    degisken: str
    bilesen: str | None
    aralik: str = 'GC'
    nokta: int = 101
    taraf: str = 'ipsi'
    aciklama: str = ''
    paket: str = ''

    def dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return DalgaFormu(**{k: d[k] for k in ('kod', 'degisken', 'bilesen', 'aralik', 'nokta', 'taraf', 'aciklama', 'paket')
                             if k in d})


@dataclass
class Ayarlar:
    dongu: DonguAyarlari = field(default_factory=DonguAyarlari)
    emg: EmgAyarlari = field(default_factory=EmgAyarlari)
    eksik_veri: str = 'bos'           # bos | hesapla
    topuk_marker: str = 'HEE'
    ortalama_yontemi: str = 'dongu'   # dongu | trial
    emg_eslesme: dict = field(default_factory=dict)   # kanal adı -> {'kas': 'TA', 'taraf': 'L'}
    kas_adlari: dict = field(default_factory=dict)    # özel kas kodu -> ad
    mvic: dict = field(default_factory=dict)          # 'hasta|kas|taraf' -> µV
    sinir_uyarisi: bool = True        # tepe aralık sınırındaysa bilgi notu
    uc_esik: float = 5.0              # uç değer: robust z eşiği
    lob_min_gc: float = 2.0           # "ilk lob" istatistikleri: bundan kısa (%GC) loblar atlanır
    min_kinetik: int = 1              # hasta + tarih + taraf başına en az kinetik döngü (altı: eksik analiz)

    def dict(self):
        d = {'dongu': self.dongu.dict(), 'emg': self.emg.dict()}
        for k in ('eksik_veri', 'topuk_marker', 'ortalama_yontemi', 'emg_eslesme', 'kas_adlari', 'mvic', 'sinir_uyarisi',
                  'uc_esik', 'lob_min_gc', 'min_kinetik'):
            d[k] = getattr(self, k)
        return d

    @staticmethod
    def from_dict(d):
        a = Ayarlar()
        if not d:
            return a
        for k, v in (d.get('dongu') or {}).items():
            if hasattr(a.dongu, k):
                setattr(a.dongu, k, tuple(v) if isinstance(v, list) else v)
        for k, v in (d.get('emg') or {}).items():
            if hasattr(a.emg, k):
                setattr(a.emg, k, v)
        for k in ('eksik_veri', 'topuk_marker', 'ortalama_yontemi', 'emg_eslesme', 'kas_adlari', 'mvic', 'sinir_uyarisi',
                  'uc_esik', 'lob_min_gc', 'min_kinetik'):
            if k in d:
                setattr(a, k, d[k])
        return a


def hasta_anahtari(hasta: str, tarih: str) -> str:
    return f'{hasta}|{tarih or ""}'


def mvic_anahtari(hasta: str, kas: str, taraf: str, tarih: str = '*') -> str:
    """MVIC tablosu anahtarı. tarih='*' : hastanın tüm ölçüm tarihleri için geçerli."""
    return f'{ascii_ad(hasta).casefold()}|{tarih or "*"}|{kas}|{taraf}'


def mvic_coz(anahtar: str):
    """(hasta_norm, tarih, kas, taraf). Eski 3 parçalı anahtarlar tarih='*' sayılır."""
    p = anahtar.split('|')
    if len(p) == 3:
        return p[0], '*', p[1], p[2]
    return p[0], p[1], p[2], p[3]


def mvic_bul(mvic: dict, hasta: str, tarih: str, kas: str, taraf: str):
    h = ascii_ad(hasta).casefold()
    tam = yildiz = None
    for k, v in (mvic or {}).items():
        hh, tt, kk, ss = mvic_coz(k)
        if hh != h or kk != kas or ss != taraf or not v:
            continue
        if tt == (tarih or ''):
            tam = float(v)
        elif tt == '*':
            yildiz = float(v)
    return tam if tam is not None else yildiz


@dataclass
class DosyaKaydi:
    yol: str
    hasta: str
    tarih: str = ''
    dahil: bool = True


@dataclass
class Sonuc:
    dongu_satirlari: list = field(default_factory=list)
    trial_satirlari: list = field(default_factory=list)
    uyarilar: list = field(default_factory=list)
    dosya_bilgisi: list = field(default_factory=list)
    sorgular: list = field(default_factory=list)
    refler: list = field(default_factory=list)
    araliklar: dict = field(default_factory=dict)
    emg_ref: dict = field(default_factory=dict)       # (hasta_key, kas, taraf) -> µV
    emg_ref_kaynak: dict = field(default_factory=dict)
    dalga_tanimlari: list = field(default_factory=list)
    dalgalar: dict = field(default_factory=dict)      # kod -> [satır sözlükleri]


# ---------------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------------
FAZ_CAPA = {'IC': {'olay': 'IC'}, 'CFO': {'olay': 'CFO'}, 'CIC': {'olay': 'CIC'}, 'FO': {'olay': 'FO'},
            'NIC': {'olay': 'NIC'}, 'SSMID': {'ozel': 'SSMID'}, 'SW33': {'ozel': 'SW33'}, 'SW50': {'ozel': 'SW50'}}

SIDE_TR = {'L': 'Sol', 'R': 'Sağ'}


def _sessiz(neden) -> bool:
    """Başka yerde zaten uyarılmış nedenler (eksik event, kinetik yok, sinyal yok)."""
    if not neden:
        return True
    return neden.endswith(' yok') or 'eşleştirilmemiş' in neden or "C3D'de yok" in neden or 'kinetik veri yok' in neden


def _deve(metin: str) -> str:
    """'Pik ayak bileği gücü' -> 'PikAyakBilegiGucu'"""
    return ''.join(w[:1].upper() + w[1:] for w in re.split(r'[^A-Za-z0-9]+', ascii_ad(metin)) if w)[:28]


def otomatik_kod(q: Sorgu, araliklar: dict, refler: dict) -> str:
    d = V.bul(q.degisken)
    parca = [d.kisa if d else re.sub(r'\W', '', q.degisken)]
    if q.bilesen and d and len(d.bilesenler) > 1:
        parca.append({'X': 'Sag', 'Y': 'Fro', 'Z': 'Tra', 'AP': 'AP', 'ML': 'ML', 'V': 'Vert'}.get(q.bilesen, q.bilesen))
    if q.aralik:
        a = araliklar.get(q.aralik)
        if a is not None:
            parca.append(a.kisa or re.sub(r'\W', '', a.id))
        elif q.aralik.startswith('@'):
            r = refler.get(q.aralik[1:])
            parca.append('at' + (_deve(r.ad) if r else q.aralik[1:]))
    ist = IST.get(q.ist) or FAZ_IST.get(q.ist)
    if ist and q.ist != 'deger':
        parca.append(ist.kisa or q.ist)
    if ist and ist.tur in ('zaman', 'emg_zaman') and q.zaman_birimi:
        parca.append({'%GC': 'GC', '%ST': 'pST', '%SW': 'pSW', '%AR': 'pInt', 's': 's', 'ms_ar': 'ms'}.get(q.zaman_birimi, ''))
    if q.taraf == 'karsi':
        parca.append('Contra')
    s = '_'.join(p for p in parca if p)
    return re.sub(r'[^A-Za-z0-9_]', '', ascii_ad(s))[:60]


class Baglam:
    """Bir trial'ın hesap sırasında paylaşılan önbelleği."""

    def __init__(self, trial: Trial, ayar: Ayarlar, araliklar: dict, refler: dict, hasta_key: str, emg_ref: dict):
        self.trial = trial
        self.ayar = ayar
        self.araliklar = araliklar
        self.refler = refler
        self.hasta_key = hasta_key
        self.emg_ref = emg_ref
        self._sig = {}
        self._emg = {}
        self._zemin = None
        self._zemin_hazir = False
        self.trial_notlari = []   # (onem, mesaj, kategori, taraf)
        self._kanal_haritasi = None

    # --- EMG -----------------------------------------------------------------
    def kanal_haritasi(self):
        """(kas, taraf) -> kanal indeksi, bu trial için."""
        if self._kanal_haritasi is None:
            h = {}
            c = self.trial.c3d
            for i, ad in enumerate(c.analog_labels):
                e = self.ayar.emg_eslesme.get(ad)
                if e and e.get('kas') and e.get('taraf') in ('L', 'R'):
                    key = (e['kas'], e['taraf'])
                    if key in h:
                        self.trial_notlari.append((UYARI, f'{e["kas"]} {SIDE_TR[e["taraf"]]} için birden fazla kanal '
                                                          f'eşleştirilmiş; ilki kullanıldı ({c.analog_labels[h[key]]}).',
                                                   'EMG', e['taraf']))
                        continue
                    h[key] = i
            self._kanal_haritasi = h
        return self._kanal_haritasi

    def emg_kanal(self, kas: str, taraf: str):
        key = (kas, taraf)
        if key in self._emg:
            return self._emg[key]
        h = self.kanal_haritasi()
        if key not in h:
            self._emg[key] = None
            self.trial_notlari.append((UYARI, f'{kas} {SIDE_TR[taraf]} EMG kanalı bu dosyada eşleştirilmemiş.', 'EMG', taraf))
            return None
        c = self.trial.c3d
        i = h[key]
        k = kanal_isle(c.analog[:, i], c.analog_units[i], c.analog_rate, c.analog_t0, self.ayar.emg, kas, taraf,
                       c.analog_labels[i])
        for onem, mesaj, kat in k.uyarilar:
            self.trial_notlari.append((onem, mesaj, kat, taraf))
        self._emg[key] = k
        return k

    def emg_burst(self, k):
        if k._burst is None:
            tr = self.trial
            ics_tum = tr.events['L']['IC'] + tr.events['R']['IC']
            ics = tr.events[k.taraf]['IC']
            if len(ics) >= 2 and ics_tum:
                esik, bl = esik_ve_burst(k, min(ics_tum), max(ics), self.ayar.emg)
            else:
                esik, bl = np.nan, []
            k._esik, k._burst = esik, bl
        return k

    # --- sinyaller ----------------------------------------------------------------
    def sinyal(self, d: V.Degisken, taraf: str, bilesen: str | None):
        key = (d.id, taraf, bilesen)
        if key in self._sig:
            return self._sig[key]
        tr = self.trial
        sig, neden = None, None
        if d.tur in ('kinematik', 'kinetik'):
            et = d.etiket.format(S=taraf)
            p = tr.nokta(et)
            if p is None:
                neden = f'{et} C3D\'de yok'
            else:
                j = {'X': 0, 'Y': 1, 'Z': 2}.get(bilesen or d.bilesenler[0].kod, 0)
                sig = Sinyal(tr.t_first, tr.rate, p[:, j].astype(float) * d.olcek, d.birim)
        elif d.tur == 'grf':
            gb = tr.grf_bilesenleri(taraf)
            if gb is None:
                neden = f'{taraf}GroundReactionForce C3D\'de yok'
            else:
                j = {'V': 0, 'AP': 1, 'ML': 2}.get(bilesen or 'V', 0)
                sig = Sinyal(tr.t_first, tr.rate, gb[j].astype(float), d.birim, temas=True,
                             nan_nedeni='GRF verisinde boşluk')
        elif d.tur == 'turetilmis' and d.id == 'ToeClearance':
            zf = self.zemin()
            sig = toe_clearance_sinyali(tr, taraf, zf)
            if sig is None:
                neden = 'zemin düzlemi ya da TOE markerı yok'
        elif d.tur == 'emg':
            k = self.emg_kanal(d.id[4:], taraf)
            if k is None:
                neden = 'EMG kanalı eşleştirilmemiş'
            else:
                sig = Sinyal(k.t0, k.fs, k.zarf, 'µV', nan_nedeni='EMG veri kaybı')
        else:
            neden = 'desteklenmeyen değişken'
        if sig is None and d.tur != 'emg':   # EMG için kanal uyarısı emg_kanal() içinde yazılıyor
            self.trial_notlari.append((UYARI, f'{d.ad} ({SIDE_TR.get(taraf, taraf)}): {neden}; bu değişkene bağlı değerler '
                                              'boş bırakıldı.', 'DEGISKEN', taraf))
        self._sig[key] = (sig, neden)
        return sig, neden

    def zemin(self):
        if not self._zemin_hazir:
            self._zemin, notlar = zemin_duzlemi(self.trial)
            for onem, mesaj in notlar:
                self.trial_notlari.append((onem, mesaj, 'MTC', '-'))
            self._zemin_hazir = True
        return self._zemin


# ---------------------------------------------------------------------------------
# Değerlendirme
# ---------------------------------------------------------------------------------
class DonguHesap:
    """Tek bir döngü için referans anları ve sorguları hesaplar."""

    def __init__(self, b: Baglam, d: Dongu):
        self.b = b
        self.d = d
        self._ref = {}
        self._ref_aktif = set()
        self._faz = {}
        self.notlar = []          # (kod, onem, mesaj, kategori)

    # --- referans anlar ---------------------------------------------------------
    def ref_zaman(self) -> dict:
        return _RefSozluk(self)

    def ref(self, rid: str):
        if rid in self._ref:
            return self._ref[rid]
        if rid in self._ref_aktif:
            return None, 'referans anlar birbirine döngüsel bağlı'
        self._ref_aktif.add(rid)
        try:
            if rid.startswith('FAZ:'):
                f = self.faz(rid[4:])
                r = (f['tepe_t'], None) if f.get('tepe_t') is not None else (None, f.get('neden', 'faz bulunamadı'))
                if f.get('uyari'):
                    self.notlar.append(('@' + rid, UYARI, f['uyari'], 'REF'))
            else:
                r = self._ref_hesapla(self.b.refler.get(rid))
        finally:
            self._ref_aktif.discard(rid)
        self._ref[rid] = r
        return r

    def _ref_hesapla(self, ref: RefAn | None):
        if ref is None:
            return None, 'referans an tanımsız'
        d = V.bul(ref.degisken, self.b.ayar.kas_adlari)
        if d is None:
            return None, 'değişken bulunamadı'
        taraf = self.d.taraf if ref.taraf == 'ipsi' else karsi(self.d.taraf)
        if d.tur in ('kinetik', 'grf') and not self.d.kinetik:
            return None, 'kinetik veri yok'
        a = self.b.araliklar.get(ref.aralik)
        if a is None:
            return None, 'arama aralığı tanımsız'
        t0, t1, neden = aralik_zamani(a, self.d, self.ref_zaman())
        if t0 is None:
            return None, neden
        sig, neden = self.b.sinyal(d, taraf, ref.bilesen)
        if sig is None:
            return None, neden
        if sig.temas:
            sig = temas_uygula(sig, self.d)
        tt, vv = seri(sig, t0, t1)
        if tt is None:
            return None, vv
        if np.isnan(vv).any():
            return None, f'{sig.nan_nedeni} (arama aralığında)'
        k = int(round(float(ref.yumusatma_ms or 0) / 1000.0 * sig.fs))
        w = vv
        if k > 1:
            from .stats import _yumusat
            w = _yumusat(vv, k)
        j = int(np.argmax(w)) if ref.ekstremum == 'max' else int(np.argmin(w))
        if len(w) > 2 and j in (0, len(w) - 1):
            self.notlar.append(('@' + ref.id, BILGI, f'Referans an "{ref.ad}" arama aralığının '
                                                     f'{"başında" if j == 0 else "sonunda"} bulundu.', 'REF'))
        return float(tt[j]), None

    # --- Winter güç fazları -----------------------------------------------------------
    def faz(self, kod: str) -> dict:
        if kod in self._faz:
            return self._faz[kod]
        r = self._faz_hesapla(kod)
        self._faz[kod] = r
        return r

    def _faz_hesapla(self, kod: str) -> dict:
        if kod not in V.FAZLAR:
            return {'neden': 'bilinmeyen faz'}
        eklem, var_id, isaret, bas, son, _ = V.FAZLAR[kod]
        d = self.d
        if not d.kinetik:
            return {'neden': 'kinetik veri yok'}
        dv = V.bul(var_id)
        sig, neden = self.b.sinyal(dv, d.taraf, 'Z')
        if sig is None:
            return {'neden': neden}
        t0, n0 = capa_zamani(FAZ_CAPA[bas], d)
        t1, n1 = capa_zamani(FAZ_CAPA[son], d)
        if t0 is None or t1 is None:
            return {'neden': n0 or n1}
        tt, vv = seri(sig, t0, t1)
        if tt is None:
            return {'neden': vv}
        if np.isnan(vv).any():
            return {'neden': 'arama penceresinde güç verisi eksik'}
        j = int(np.argmax(vv)) if isaret > 0 else int(np.argmin(vv))
        if (isaret > 0 and vv[j] <= 0) or (isaret < 0 and vv[j] >= 0):
            return {'neden': f'{kod} fazı bulunamadı (pencerede güç {"pozitif" if isaret > 0 else "negatif"} değil)'}
        tepe, tepe_t = float(vv[j]), float(tt[j])
        ek = {}
        if kod == 'A1' and d.nic > d.ic and (tepe_t - d.ic) / (d.nic - d.ic) < 0.10:
            ek['uyari'] = (f'A1 tepesi %{100 * (tepe_t - d.ic) / (d.nic - d.ic):.1f} GC noktasında bulundu: orta stance '
                           f'absorpsiyonu yerine IC sonrası yüklenme dalgası yakalanmış olabilir.')
        # fazın sınırları: tepeyi içeren aynı işaretli bölge (döngü içinde)
        ct, cv = seri(sig, d.ic, d.nic)
        if ct is None:
            return {'tepe': tepe, 'tepe_t': tepe_t, 'neden_sinir': 'döngü verisi yok', **ek}
        k = int(np.argmin(np.abs(ct - tepe_t)))
        sgn = np.sign(tepe)
        i = k
        while i > 0 and np.isfinite(cv[i - 1]) and np.sign(cv[i - 1]) == sgn:
            i -= 1
        e = k
        while e < len(cv) - 1 and np.isfinite(cv[e + 1]) and np.sign(cv[e + 1]) == sgn:
            e += 1
        r = {'tepe': tepe, 'tepe_t': tepe_t, **ek}
        sol_nan = i > 0 and not np.isfinite(cv[i - 1])
        sag_nan = e < len(cv) - 1 and not np.isfinite(cv[e + 1])
        if sol_nan or sag_nan:
            r['neden_sinir'] = 'faz sınırında güç verisi eksik'
            return r
        # sıfır geçişlerini doğrusal interpolasyonla bul
        def gecis(a, b_):
            va, vb = cv[a], cv[b_]
            if va == vb:
                return ct[a]
            return ct[a] + (0 - va) / (vb - va) * (ct[b_] - ct[a])
        tb = gecis(i - 1, i) if i > 0 else ct[0]
        ts = gecis(e, e + 1) if e < len(cv) - 1 else ct[-1]
        seg_t = np.r_[tb, ct[i:e + 1], ts]
        seg_v = np.r_[0.0 if i > 0 else cv[0], cv[i:e + 1], 0.0 if e < len(cv) - 1 else cv[-1]]
        r.update({'is': float(_trapz(seg_v, seg_t)), 'bas_t': float(tb), 'son_t': float(ts)})
        if i == 0 or e == len(cv) - 1:
            r['not'] = 'faz döngü sınırına kadar uzanıyor'
        return r

    # --- sorgu ---------------------------------------------------------------------
    def sorgu(self, q: Sorgu, zu_cache: dict):
        d = self.d
        b = self.b
        dv = V.bul(q.degisken, b.ayar.kas_adlari)
        if dv is None:
            return np.nan, [(UYARI, f'Bilinmeyen değişken: {q.degisken}')]
        if dv.tur == 'zu':
            if dv.duzey == 'trial':
                return np.nan, []
            return zu_cache.get(q.degisken, np.nan), []
        if dv.tur == 'faz':
            return self._faz_sorgu(q, dv)
        if dv.tur in ('kinetik', 'grf') and not d.kinetik:
            return np.nan, []
        taraf = d.taraf if q.taraf == 'ipsi' else karsi(d.taraf)
        a = b.araliklar.get(q.aralik) if q.aralik else None
        if a is None:
            return np.nan, [(UYARI, f'Aralık tanımsız: {q.aralik}')]
        t0, t1, neden = aralik_zamani(a, d, self.ref_zaman())
        if t0 is None:
            # eksik event/kinetik/sinyal zaten döngü ya da dosya düzeyinde uyarıldı; burada tekrar yazılmaz
            if _sessiz(neden):
                return np.nan, []
            onem = BILGI if neden and 'bulunamadı' in neden else UYARI
            return np.nan, [(onem, f'Aralık hesaplanamadı: {neden}')]
        if q.ist == 'cci':
            return self._cci(q, dv, taraf, t0, t1)
        sig, neden = b.sinyal(dv, taraf, q.bilesen)
        if sig is None:
            return np.nan, []          # dosya düzeyinde bir kez uyarıldı
        if sig.temas:
            sig = temas_uygula(sig, d)
        ist = IST.get(q.ist)
        if ist is None:
            return np.nan, [(UYARI, f'Bilinmeyen istatistik: {q.ist}')]
        notlar = []
        # EMG'ye özgü istatistikler
        if ist.tur in ('emg', 'emg_zaman') and dv.tur == 'emg':
            k = b.emg_kanal(dv.id[4:], taraf)
            if q.ist in ('mdf', 'mnf'):
                mdf, mnf, neden = frekans(k, t0, t1, b.ayar.emg)
                if neden:
                    return np.nan, [(UYARI, f'Frekans analizi yapılamadı: {neden}')]
                return (mdf if q.ist == 'mdf' else mnf), []
            tt, vv = seri(sig, t0, t1)
            if tt is None:
                return np.nan, [(UYARI, vv)]
            if np.isnan(vv).any():
                return np.nan, [(UYARI, f'{sig.nan_nedeni}: aralıkta {int(np.isnan(vv).sum())} örnek eksik; değer boş bırakıldı.')]
            b.emg_burst(k)
            if not np.isfinite(k._esik):
                return np.nan, [(UYARI, 'Aktivasyon eşiği hesaplanamadı (sinyal kısa).')]
            akt = aktivasyon(k, t0, t1, d.ic, d.nic)
            if q.ist in ('onset', 'offset'):
                v = akt[q.ist]
                if not np.isfinite(v):
                    return np.nan, []
                tmut = d.ic + v / 100.0 * d.sure
                return zaman_cevir(tmut, q.zaman_birimi, d.ic, d.nic, d.fo, t0, t1), []
            m = {'aktif_ms': 'sure_ms', 'aktif_yuzde': 'aktif_yuzde', 'aktif_basta': 'aktif_basta',
                 'aktif_sonda': 'aktif_sonda'}
            return float(akt[m[q.ist]]), []
        if ist.tur in ('emg', 'emg_zaman', 'emg_trial'):
            return np.nan, [(UYARI, f'"{ist.ad}" yalnızca EMG değişkenleri için hesaplanır.')]
        tt, vv = seri(sig, t0, t1)
        if tt is None:
            return np.nan, [(UYARI, f'Değer hesaplanamadı: {vv}')]
        eksik = np.isnan(vv)
        if eksik.any():
            if b.ayar.eksik_veri == 'bos' or eksik.all():
                return np.nan, [(UYARI, f'{sig.nan_nedeni}: aralıkta {int(eksik.sum())}/{len(vv)} örnek eksik; '
                                        'değer boş bırakıldı.')]
            notlar.append((UYARI, f'{sig.nan_nedeni}: aralıkta {int(eksik.sum())}/{len(vv)} örnek eksik; '
                                  'değer mevcut örneklerle hesaplandı.'))
            tt, vv = tt[~eksik], vv[~eksik]
        ctx = {'ic': d.ic, 'nic': d.nic, 'fo': d.fo, 't0': t0, 't1': t1, 'zaman_birimi': q.zaman_birimi, 'fs': sig.fs,
               'lob_min_s': float(b.ayar.lob_min_gc or 0) / 100.0 * d.sure}
        if any('ref' in c and (c.get('kayma_ms') or c.get('kayma_gc')) for c in (a.bas, a.son)):
            tol = 0.5 / sig.fs
            if t0 < d.ic - tol or t1 > d.nic + tol:
                notlar.append((BILGI, 'Kaydırılmış referans an nedeniyle aralık döngü sınırını aşıyor '
                                      f'(%{100 * (t0 - d.ic) / d.sure:.1f}–%{100 * (t1 - d.ic) / d.sure:.1f} GC); '
                                      'değer komşu döngünün verisini de içerir.'))
        try:
            v, n2 = hesapla(q.ist, tt, vv, ctx, q.par)
        except KeyError:
            return np.nan, [(UYARI, f'Bu istatistik bu değişken için hesaplanamaz: {q.ist}')]
        if not b.ayar.sinir_uyarisi:
            n2 = [x for x in n2 if not (x[0] == BILGI and ('gerçek bir tepe olmayabilir' in x[1] or
                                                           'aralığın dışında kalmış olabilir' in x[1]))]
        return v, notlar + n2

    def _faz_sorgu(self, q: Sorgu, dv):
        f = self.faz(dv.id[4:])
        d = self.d
        if 'tepe' not in f:
            if f.get('neden') == 'kinetik veri yok':
                return np.nan, []
            return np.nan, [(BILGI, f.get('neden', 'faz bulunamadı'))]
        notlar = []
        if f.get('not'):
            notlar.append((BILGI, f['not']))
        if f.get('uyari'):
            notlar.append((UYARI, f['uyari']))
        if q.ist == 'tepe':
            return f['tepe'], notlar
        if q.ist == 'tepe_zamani':
            return zaman_cevir(f['tepe_t'], q.zaman_birimi, d.ic, d.nic, d.fo, d.ic, d.nic), notlar
        if 'is' not in f:
            return np.nan, [(UYARI, f.get('neden_sinir', 'faz sınırları bulunamadı'))]
        if q.ist == 'is':
            return f['is'], notlar
        if q.ist == 'faz_bas':
            return zaman_cevir(f['bas_t'], q.zaman_birimi, d.ic, d.nic, d.fo, d.ic, d.nic), notlar
        if q.ist == 'faz_son':
            return zaman_cevir(f['son_t'], q.zaman_birimi, d.ic, d.nic, d.fo, d.ic, d.nic), notlar
        if q.ist == 'faz_sure':
            return sure_cevir(f['son_t'] - f['bas_t'], q.zaman_birimi if q.zaman_birimi in ('s', 'ms', '%GC', '%ST', '%SW')
                              else 's', d.ic, d.nic, d.fo), notlar
        return np.nan, [(UYARI, f'Bilinmeyen faz istatistiği: {q.ist}')]

    def dalga(self, w: 'DalgaFormu'):
        """Dönüş: (değerler [n] ya da None, notlar)."""
        d, b = self.d, self.b
        dv = V.bul(w.degisken, b.ayar.kas_adlari)
        if dv is None or dv.tur in ('zu', 'faz'):
            return None, [(UYARI, f'Dalga formu bu değişken için çıkarılamaz: {w.degisken}')]
        if dv.tur in ('kinetik', 'grf') and not d.kinetik:
            return None, []
        a = b.araliklar.get(w.aralik)
        if a is None or a.an_mi:
            return None, [(UYARI, f'Dalga formu aralığı tanımsız: {w.aralik}')]
        t0, t1, neden = aralik_zamani(a, d, self.ref_zaman())
        if t0 is None:
            return None, ([] if _sessiz(neden) else [(UYARI, f'Aralık hesaplanamadı: {neden}')])
        taraf = d.taraf if w.taraf == 'ipsi' else karsi(d.taraf)
        sig, neden = b.sinyal(dv, taraf, w.bilesen)
        if sig is None:
            return None, []
        if sig.temas:
            sig = temas_uygula(sig, d)
        tt, vv = seri(sig, t0, t1)
        if tt is None:
            return None, [(UYARI, f'Dalga formu çıkarılamadı: {vv}')]
        if np.isnan(vv).any():
            return None, [(UYARI, f'{sig.nan_nedeni}: dalga formunda {int(np.isnan(vv).sum())} örnek eksik; bu döngü '
                                  'dalga formuna yazılmadı.')]
        n = max(int(w.nokta), 2)
        return np.interp(np.linspace(t0, t1, n), tt, vv), []

    def _cci(self, q: Sorgu, dv, taraf, t0, t1):
        b = self.b
        if dv.tur != 'emg':
            return np.nan, [(UYARI, 'Ko-kontraksiyon yalnızca EMG için hesaplanır.')]
        kas2 = (q.par or {}).get('kas2')
        if not kas2:
            return np.nan, [(UYARI, 'Ko-kontraksiyon için ikinci kas seçilmemiş.')]
        taraf2 = taraf if (q.par or {}).get('taraf2', 'ayni') == 'ayni' else karsi(taraf)
        s1, n1 = b.sinyal(dv, taraf, 'E')
        s2, n2 = b.sinyal(V.bul(f'EMG:{kas2}', b.ayar.kas_adlari), taraf2, 'E')
        if s1 is None or s2 is None:
            return np.nan, []
        a1, v1 = seri(s1, t0, t1)
        a2, v2 = seri(s2, t0, t1)
        if a1 is None or a2 is None:
            return np.nan, [(UYARI, 'aralık kaydın dışına taşıyor')]
        if np.isnan(v1).any() or np.isnan(v2).any():
            return np.nan, [(UYARI, 'EMG veri kaybı: ko-kontraksiyon hesaplanmadı.')]
        notlar = []
        r1 = b.emg_ref.get((b.hasta_key, dv.id[4:], taraf))
        r2 = b.emg_ref.get((b.hasta_key, kas2, taraf2))
        if r1 and r2:
            v1, v2 = v1 / r1, v2 / r2
        else:
            notlar.append((UYARI, 'Normalizasyon referansı yok: ko-kontraksiyon ham µV ile hesaplandı (kaslar arası '
                                  'genlik farkı sonucu etkiler).'))
        ortak = _trapz(np.minimum(v1, v2), a1)
        toplam = _trapz(v1 + v2, a1)
        if toplam <= 0:
            return np.nan, notlar
        return float(200.0 * ortak / toplam), notlar


class _RefSozluk(dict):
    """aralik_zamani() içinde {'ref': id} çapalarını tembel çözmek için."""

    def __init__(self, h: DonguHesap):
        super().__init__()
        self.h = h

    def get(self, k, default=None):
        return self.h.ref(k)


# ---------------------------------------------------------------------------------
# Çalıştırıcı
# ---------------------------------------------------------------------------------
def aralik_sozlugu(ozel: list | None, refler: dict) -> dict:
    a = {x.id: x for x in HAZIR_ARALIKLAR + HAZIR_ANLAR}
    for x in ozel or []:
        a[x.id] = x
    for rid, r in refler.items():
        a['@' + rid] = Aralik('@' + rid, f'{r.ad} anı', {'ref': rid}, {'ref': rid}, 'at' + _deve(r.ad))
    for k in V.FAZLAR:
        a['@FAZ:' + k] = Aralik('@FAZ:' + k, f'{k} tepe anı', {'ref': 'FAZ:' + k}, {'ref': 'FAZ:' + k}, f'at{k}peak')
    return a


def calistir(dosyalar: list, sorgular: list, refler: list | None = None, ozel_araliklar: list | None = None,
             ayar: Ayarlar | None = None, ilerleme=None, iptal=None, dalgalar: list | None = None) -> Sonuc:
    ayar = ayar or Ayarlar()
    ref_d = {r.id: r for r in (refler or [])}
    aral = aralik_sozlugu(ozel_araliklar, ref_d)
    dalgalar = list(dalgalar or [])
    snc = Sonuc(sorgular=list(sorgular), refler=list(refler or []), araliklar=aral, dalga_tanimlari=dalgalar)
    for w in dalgalar:
        snc.dalgalar[w.kod] = []
    sorgular = list(sorgular)
    trial_zu_lazim = any(V.bul(q.degisken) and V.bul(q.degisken).tur == 'zu' and V.bul(q.degisken).duzey == 'trial'
                         for q in sorgular)
    dongu_zu_lazim = any(V.bul(q.degisken) and V.bul(q.degisken).tur == 'zu' and V.bul(q.degisken).duzey == 'dongu'
                         for q in sorgular)
    mdf_egim = [q for q in sorgular if q.ist == 'mdf_egim']
    cci_var = any(q.ist == 'cci' for q in sorgular)
    norm = ayar.emg.normalizasyon
    emg_kaslar = sorted({q.degisken[4:] for q in sorgular if q.degisken.startswith('EMG:')} |
                        {(q.par or {}).get('kas2') for q in sorgular if q.ist == 'cci' and (q.par or {}).get('kas2')})

    # MVIC referansları
    emg_ref = {}
    dahil = [f for f in dosyalar if f.dahil]
    if norm == 'mvic':
        kas_set = {mvic_coz(k)[2] for k in (ayar.mvic or {})}
        for f in dahil:
            hk = hasta_anahtari(f.hasta, f.tarih)
            for kas in kas_set:
                for taraf in ('L', 'R'):
                    v = mvic_bul(ayar.mvic, f.hasta, f.tarih, kas, taraf)
                    if v:
                        emg_ref[(hk, kas, taraf)] = v
                        snc.emg_ref_kaynak[(hk, kas, taraf)] = 'MVIC'
    elif norm in ('dinamik_tepe', 'dinamik_ort') and cci_var:
        emg_ref = _dinamik_ref_on_hesap(dahil, sorgular, aral, ref_d, ayar, snc)
    snc.emg_ref = emg_ref

    n = len(dahil)
    for fi, f in enumerate(dahil):
        if iptal is not None and iptal():
            break
        if ilerleme:
            ilerleme(fi, n, f.yol)
        try:
            tr = Trial(f.yol)
        except Exception as e:  # noqa
            snc.uyarilar.append(Uyari(_dosya_adi(f.yol), '-', '-', 'DOSYA', HATA, f'Dosya okunamadı: {e}', 'DOSYA'))
            continue
        hk = hasta_anahtari(f.hasta, f.tarih)
        b = Baglam(tr, ayar, aral, ref_d, hk, emg_ref)
        for onem, mesaj, kat in tr.uyarilar:
            snc.uyarilar.append(Uyari(tr.dosya, '-', '-', kat, onem, mesaj, kat))
        donguler = donguleri_kur(tr, ayar.dongu)
        snc.dosya_bilgisi.append({
            'dosya': tr.dosya, 'yol': tr.yol, 'hasta': f.hasta, 'tarih': f.tarih, 'kare_hizi': tr.rate,
            'analog_hizi': tr.analog_rate, 'kutle': tr.kutle, 'boy_mm': tr.boy_mm,
            'bacak_L_mm': tr.bacak_mm.get('L'), 'bacak_R_mm': tr.bacak_mm.get('R'),
            'dongu_L': sum(1 for d in donguler if d.taraf == 'L' and d.gecerli),
            'dongu_R': sum(1 for d in donguler if d.taraf == 'R' and d.gecerli),
            'kinetik_L': sum(1 for d in donguler if d.taraf == 'L' and d.kinetik),
            'kinetik_R': sum(1 for d in donguler if d.taraf == 'R' and d.kinetik),
            'yon': f'{"+-"[tr.ilerleme_isareti < 0]}{"XY"[tr.ilerleme_ekseni]}',
        })
        mdf_kayit = {}   # (kod, taraf) -> [(t, mdf)]
        for d in donguler:
            for onem, mesaj, kat in d.uyarilar:
                snc.uyarilar.append(Uyari(tr.dosya, d.taraf, d.no, kat, onem, mesaj, kat))
            satir = {'Dosya': tr.dosya, 'Hasta': f.hasta, 'Tarih': f.tarih, 'Taraf': d.taraf, 'Dongu': d.no,
                     'IC_s': d.ic, 'FO_s': d.fo, 'Sonraki_IC_s': d.nic, 'Kinetik': int(d.kinetik),
                     'Gecerli': int(d.gecerli)}
            if not d.gecerli:
                for q in sorgular:
                    satir[q.kod] = np.nan
                snc.dongu_satirlari.append(satir)
                continue
            h = DonguHesap(b, d)
            zu = {}
            if dongu_zu_lazim:
                zu, zn = dongu_zu(tr, d, ayar.topuk_marker)
                for onem, mesaj in zn:
                    snc.uyarilar.append(Uyari(tr.dosya, d.taraf, d.no, 'ZU', onem, mesaj, 'ZU'))
            for q in sorgular:
                if q.ist == 'mdf_egim':
                    qq = Sorgu(q.kod, q.degisken, q.bilesen, q.aralik, 'mdf', q.zaman_birimi, q.taraf, q.par)
                    v, notlar = h.sorgu(qq, zu)
                    if np.isfinite(v):
                        mdf_kayit.setdefault((q.kod, d.taraf), []).append((d.ic, v))
                    satir['_mdf_' + q.kod] = v
                    continue
                try:
                    v, notlar = h.sorgu(q, zu)
                except Exception as e:  # beklenmeyen hata tüm çalışmayı durdurmasın
                    v, notlar = np.nan, [(HATA, f'Hesap hatası: {type(e).__name__}: {e}')]
                satir[q.kod] = v
                for onem, mesaj in notlar:
                    snc.uyarilar.append(Uyari(tr.dosya, d.taraf, d.no, q.kod, onem, mesaj, 'DEGER'))
            for w in dalgalar:
                try:
                    dv_, notlar = h.dalga(w)
                except Exception as e:  # noqa
                    dv_, notlar = None, [(HATA, f'Dalga formu hatası: {type(e).__name__}: {e}')]
                for onem, mesaj in notlar:
                    snc.uyarilar.append(Uyari(tr.dosya, d.taraf, d.no, w.kod, onem, mesaj, 'DALGA'))
                if dv_ is not None:
                    snc.dalgalar[w.kod].append({'Hasta': f.hasta, 'Tarih': f.tarih, 'Dosya': tr.dosya, 'Taraf': d.taraf,
                                                'Dongu': d.no, 'Kinetik': int(d.kinetik), 'degerler': dv_})
            for kod, onem, mesaj, kat in h.notlar:
                snc.uyarilar.append(Uyari(tr.dosya, d.taraf, d.no, kod, onem, mesaj, kat))
            # dinamik normalizasyon için döngü tepe/ortalama (bu tarafın kası)
            if norm in ('dinamik_tepe', 'dinamik_ort'):
                for kas in emg_kaslar:
                    sig, _ = b.sinyal(V.bul(f'EMG:{kas}', ayar.kas_adlari), d.taraf, 'E')
                    mx = mn = np.nan
                    if sig is not None:
                        a_, v_ = seri(sig, d.ic, d.nic)
                        if a_ is not None and not np.isnan(v_).any():
                            mx = float(np.max(v_))
                            mn = float(_trapz(v_, a_) / (a_[-1] - a_[0]))
                    satir[f'_emgref_{kas}_max'] = mx
                    satir[f'_emgref_{kas}_mean'] = mn
            snc.dongu_satirlari.append(satir)
        # trial düzeyi
        if trial_zu_lazim or mdf_egim:
            tnot = []
            tz = trial_zu(tr, tnot) if trial_zu_lazim else {}
            for onem, mesaj in tnot:
                snc.uyarilar.append(Uyari(tr.dosya, '-', '-', 'ZU', onem, mesaj, 'ZU'))
            ts = {'Dosya': tr.dosya, 'Hasta': f.hasta, 'Tarih': f.tarih, 'Taraf': '-'}
            for q in sorgular:
                dv = V.bul(q.degisken)
                if dv and dv.tur == 'zu' and dv.duzey == 'trial':
                    ts[q.kod] = tz.get(q.degisken, np.nan)
            ts['N_Adim'] = tz.get('_n_adim', np.nan)
            ts['Sure_s'] = tz.get('_sure', np.nan)
            ts['Mesafe_m'] = tz.get('_mesafe', np.nan)
            snc.trial_satirlari.append(ts)
            for q in mdf_egim:
                for s in ('L', 'R'):
                    pts = mdf_kayit.get((q.kod, s), [])
                    row = {'Dosya': tr.dosya, 'Hasta': f.hasta, 'Tarih': f.tarih, 'Taraf': s}
                    if len(pts) >= 3:
                        x = np.array([p[0] for p in pts]); y = np.array([p[1] for p in pts])
                        row[q.kod] = float(np.polyfit(x, y, 1)[0])
                    else:
                        row[q.kod] = np.nan
                        snc.uyarilar.append(Uyari(tr.dosya, s, '-', q.kod, BILGI,
                                                  'MDF eğimi için en az 3 döngü gerekir.', 'EMG'))
                    snc.trial_satirlari.append(row)
        for onem, mesaj, kat, taraf in b.trial_notlari:
            snc.uyarilar.append(Uyari(tr.dosya, taraf, '-', kat, onem, mesaj, kat))
    if ilerleme:
        ilerleme(n, n, '')
    return snc


def _dosya_adi(yol):
    import os
    return os.path.splitext(os.path.basename(yol))[0]


def _dinamik_ref_on_hesap(dosyalar, sorgular, aral, ref_d, ayar, snc):
    """CCI için dinamik normalizasyon referansı: hasta+tarih, kas, taraf başına döngü tepe/ortalama değerlerinin ortalaması."""
    kaslar = set()
    for q in sorgular:
        if q.degisken.startswith('EMG:'):
            kaslar.add(q.degisken[4:])
            if q.ist == 'cci' and (q.par or {}).get('kas2'):
                kaslar.add(q.par['kas2'])
    biriken = {}
    for f in dosyalar:
        try:
            tr = Trial(f.yol)
        except Exception:
            continue
        hk = hasta_anahtari(f.hasta, f.tarih)
        b = Baglam(tr, ayar, aral, ref_d, hk, {})
        for d in donguleri_kur(tr, ayar.dongu):
            if not d.gecerli:
                continue
            for kas in kaslar:
                sig, _ = b.sinyal(V.bul(f'EMG:{kas}', ayar.kas_adlari), d.taraf, 'E')
                if sig is None:
                    continue
                tt, vv = seri(sig, d.ic, d.nic)
                if tt is None or np.isnan(vv).any():
                    continue
                val = float(np.max(vv)) if ayar.emg.normalizasyon == 'dinamik_tepe' else float(_trapz(vv, tt) / (tt[-1] - tt[0]))
                biriken.setdefault((hk, kas, d.taraf), []).append(val)
    out = {}
    for k, v in biriken.items():
        out[k] = float(np.mean(v))
        snc.emg_ref_kaynak[k] = 'dinamik'
    return out
