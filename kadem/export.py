"""Excel çıktısı: hasta düzeyi (SPSS), uzun format (R), trial, döngü, uyarılar, uç değerler, sözlük, yöntem, algoritma.

- Döngü sayfası (4_Tum_Donguler) tek düzenlenebilir sayfadır. Trial, hasta düzeyi ve uzun format sayfalarındaki ortalamalar
  bu sayfaya formülle bağlıdır (AVERAGEIFS / COUNTIFS); formüller hesaplanmış değerleriyle yazılır, böylece SPSS/R
  dosyayı Excel'de açmadan da doğru okur.
- Değeri olmayan (boş) hücrelere formül yazılmaz; SPSS/R'nin boş hücreyi metin sanmaması için.
- Diğer sayfalar şifresiz kilitlenir (yanlışlıkla değiştirmeye karşı); filtre ve seçim serbesttir.
"""
from __future__ import annotations

import datetime as _dt
import re
import os

import numpy as np
import pandas as pd

from . import __version__, APP_NAME, APP_ALT_BASLIK
from . import variables as V
from .aggregate import birlestir, sorgu_duzeyi, NORM_EK
from .dil import M, _, ayarla
from .engine import Sonuc, Ayarlar
from .intervals import capa_metni
from .stats import IST, FAZ_IST, ZAMAN_BIRIMLERI, SURE_BIRIMLERI
from .warnings_ import Uyari, HATA


def taraf_metni(s):
    return {'L': M('Sol', 'Left'), 'R': M('Sag', 'Right'), 'Sol': M('Sol', 'Left'), 'Sağ': M('Sag', 'Right'),
            'Sag': M('Sag', 'Right'), '-': '-'}.get(s, s)


# Sabit sütun başlıkları (değişken sütunları dilden bağımsızdır)
BASLIK_EN = {
    'Hasta': 'Patient', 'Tarih': 'Date', 'Dosya': 'File', 'Taraf': 'Side', 'Dongu': 'Cycle', 'Kinetik': 'Kinetic',
    'Gecerli': 'Valid', 'Dislandi': 'Excluded', 'Dislama_Nedeni': 'Exclusion_Reason', 'Duzeltme_Notu': 'Correction_Note',
    'Anahtar': 'Key', 'Etkilenen_Taraf': 'Affected_Side', 'N_Dongu': 'N_Cycles', 'N_Kinetik': 'N_Kinetic',
    'Kinetik_Tamam': 'Kinetic_Complete', 'N_Trial': 'N_Trials', 'Degisken': 'Variable', 'Birim': 'Unit', 'Ortalama': 'Mean', 'SS': 'SD', 'CV_yuzde': 'CV_pct',
    'Kod': 'Code', 'Onem': 'Severity', 'Kategori': 'Category', 'Mesaj': 'Message', 'Duzey': 'Level', 'Deger': 'Value',
    'Medyan': 'Median', 'Sutun': 'Column', 'Aciklama': 'Description', 'Bilesen': 'Component', 'Isaret_kurali': 'Sign_convention',
    'Aralik': 'Window', 'Istatistik': 'Statistic', 'Zaman_birimi': 'Time_unit', 'Paket': 'Package',
    'Parametreler': 'Parameters', 'Not': 'Note', 'Wide_sutunlari': 'Wide_columns', 'Ayar': 'Setting', 'Değer': 'Value',
    'N_Adim': 'N_Steps', 'Sure_s': 'Duration_s', 'Mesafe_m': 'Distance_m', 'Hasta_Tarih': 'Patient_Date', 'Kas': 'Muscle',
    'Referans_uV': 'Reference_uV', 'Kaynak': 'Source', 'Adim': 'Step', 'Trial': 'Trial',
    'dosya': 'file', 'yol': 'path', 'hasta': 'patient', 'tarih': 'date', 'kare_hizi': 'frame_rate',
    'analog_hizi': 'analog_rate', 'kutle': 'mass_kg', 'boy_mm': 'height_mm', 'bacak_L_mm': 'leg_L_mm',
    'bacak_R_mm': 'leg_R_mm', 'dongu_L': 'cycles_L', 'dongu_R': 'cycles_R', 'kinetik_L': 'kinetic_L',
    'kinetik_R': 'kinetic_R', 'yon': 'direction', 'tarih_kaynagi': 'date_source',
}


def baslik(s: str) -> str:
    return BASLIK_EN.get(s, s) if M('', 'x') == 'x' else s


def sayfa_adlari() -> dict:
    return {
        'hasta': M('1_Hasta_Duzeyi', '1_Patient_Level'), 'uzun': M('2_Uzun_Format', '2_Long_Format'),
        'trial': M('3_Trial_Ortalamalari', '3_Trial_Means'), 'trial_zu': M('3b_Trial_Hiz_Kadans', '3b_Trial_Speed_Cadence'),
        'dongu': M('4_Tum_Donguler', '4_All_Cycles'), 'uyari': M('5_Uyarilar', '5_Warnings'),
        'uc': M('6_Uc_Degerler', '6_Outliers'), 'dislanan': M('7_Dislanan_Donguler', '7_Excluded_Cycles'),
        'sozluk': M('8_Degisken_Sozlugu', '8_Variable_Dictionary'), 'yontem': M('9_Yontem', '9_Methods'),
        'dosyalar': M('10_Dosyalar', '10_Files'), 'emg_ref': M('11_EMG_Referanslari', '11_EMG_References'),
        'algoritma': M('12_Algoritma', '12_Algorithm'),
    }


def _sozluk(snc: Sonuc, ayar: Ayarlar, sutunlar: list) -> pd.DataFrame:
    ref_adlari = {r.id: r.ad for r in snc.refler}
    rows = []
    for col, q, tur, birim in sutunlar:
        d = V.bul(q.degisken, ayar.kas_adlari)
        b = V.bilesen(d, q.bilesen) if d else None
        a = snc.araliklar.get(q.aralik) if q.aralik else None
        ist = IST.get(q.ist) or FAZ_IST.get(q.ist)
        aralik_metni = ''
        if a is not None:
            aralik_metni = _(a.ad) if not a.ozel else f'{_(a.ad)} ({_(capa_metni(a.bas, ref_adlari))} → {_(capa_metni(a.son, ref_adlari))})'
        elif d is not None and d.tur == 'faz':
            k = d.id[4:]
            v = V.FAZLAR[k]
            aralik_metni = M(f'arama penceresi: {v[3]} → {v[4]} (fazın sınırları güç eğrisinin işaret değiştirdiği noktalar)',
                             f'search window: {v[3]} → {v[4]} (phase boundaries are the zero crossings of the power curve)')
        zb = ''
        if ist is not None and ist.tur in ('zaman', 'emg_zaman'):
            zb = _(ZAMAN_BIRIMLERI.get(q.zaman_birimi, q.zaman_birimi))
        elif ist is not None and ist.tur == 'sure':
            zb = _(SURE_BIRIMLERI.get(q.zaman_birimi, q.zaman_birimi))
        par = ', '.join(f'{k}={v}' for k, v in (q.par or {}).items())
        not_ = ''
        if tur == 'norm':
            not_ = {'mvic': M('MVIC\'e göre normalize (%MVIC)', 'Normalized to MVIC (%MVIC)'),
                    'dinamik_tepe': M('Dinamik normalizasyon: hasta-tarih-taraf için döngü tepelerinin ortalamasına göre %',
                                      'Dynamic normalization: % of the mean cycle peak per patient-date-side'),
                    'dinamik_ort': M('Dinamik normalizasyon: hasta-tarih-taraf için döngü ortalamalarının ortalamasına göre %',
                                     'Dynamic normalization: % of the mean cycle mean per patient-date-side')
                    }.get(ayar.emg.normalizasyon, '')
        elif tur == 'ham':
            not_ = M('Ham EMG zarfı (µV)', 'Raw EMG envelope (µV)')
        duzey = {'dongu': M('Döngü → hasta (taraf bazında)', 'Cycle → patient (per side)'),
                 'trial': M('Trial → hasta (iki taraf birlikte)', 'Trial → patient (both sides)'),
                 'trial_taraf': M('Trial → hasta (taraf bazında)', 'Trial → patient (per side)')}[sorgu_duzeyi(q)]
        rows.append({
            'Sutun': col, 'Aciklama': _(q.aciklama), 'Degisken': _(d.ad) if d else q.degisken,
            'Bilesen': f'{_(b.ad)} ({b.kod})' if b else '', 'Isaret_kurali': _(b.isaret) if b else '',
            'Aralik': aralik_metni, 'Istatistik': _(ist.ad) if ist else q.ist, 'Zaman_birimi': zb, 'Birim': _(birim),
            'Taraf': M('karşı taraf', 'opposite side') if q.taraf == 'karsi' else M('aynı taraf', 'same side'),
            'Duzey': duzey, 'Paket': q.paket, 'Parametreler': par, 'Not': not_,
            'Wide_sutunlari': (f'L_{col}, R_{col}' if sorgu_duzeyi(q) != 'trial' else col),
        })
    return pd.DataFrame(rows)


def _yontem(snc: Sonuc, ayar: Ayarlar, n_dosya: int, ek: dict | None) -> pd.DataFrame:
    e = ayar.emg
    dg = ayar.dongu
    S = sayfa_adlari()
    satirlar = [
        (M('Program', 'Program'), f'{APP_NAME} {__version__} ({APP_ALT_BASLIK})'),
        (M('Çalıştırma zamanı', 'Run time'), _dt.datetime.now().strftime('%Y-%m-%d %H:%M')),
        (M('Dosya sayısı', 'Number of files'), n_dosya),
        (M('Döngü tanımı', 'Cycle definition'),
         M('Aynı tarafın IC (Foot Strike) event\'inden bir sonraki IC\'sine. Aynı taraf Foot Off, karşı Foot Off ve karşı IC '
           'döngünün içinden alınır.',
           'From an IC (Foot Strike) event to the next IC of the same side. Same-side Foot Off, opposite Foot Off and '
           'opposite IC are taken from within the cycle.')),
        (M('Event zamanları', 'Event times'),
         M('En yakın kareye yuvarlandı (kare bazlı hesaplama modu)', 'Rounded to the nearest frame (frame-based mode)')
         if dg.kareye_yuvarla else
         M('C3D\'deki event zamanları (saniye) kullanıldı; aralık sınırlarındaki değerler komşu kareler arasında doğrusal '
           'interpolasyonla alındı.',
           'Event times from the C3D (seconds) were used; values at window boundaries were linearly interpolated between '
           'neighbouring frames.')),
        (M('Olağan aralık kontrolleri (yalnızca uyarı)', 'Plausibility checks (warnings only)'),
         M(f'stride {dg.stride_aralik[0]}–{dg.stride_aralik[1]} s; stance oranı %{100 * dg.stance_oran[0]:.0f}–'
           f'{100 * dg.stance_oran[1]:.0f}; 1. çift destek ≤ %{100 * dg.ds1_max_oran:.0f} GC',
           f'stride {dg.stride_aralik[0]}–{dg.stride_aralik[1]} s; stance ratio {100 * dg.stance_oran[0]:.0f}–'
           f'{100 * dg.stance_oran[1]:.0f}%; first double support ≤ {100 * dg.ds1_max_oran:.0f}% GC')),
        (M('Geçersiz döngü', 'Invalid cycle'),
         M(f'stride < {dg.min_stride} s (çift event) ya da kayıt dışına taşan döngü',
           f'stride < {dg.min_stride} s (duplicate event) or cycle extending beyond the recording')),
        (M('Kinetik döngü', 'Kinetic cycle'),
         M(f'Bu tarafın stance\'inde PiG GRF büyüklüğü > {dg.kinetik_esik} N/kg. Kinetik değişkenler yalnızca kinetik '
           f'döngülerde hesaplanır.',
           f'PiG GRF magnitude > {dg.kinetik_esik} N/kg during this side\'s stance. Kinetic variables are computed only in '
           f'kinetic cycles.')),
        ('GRF', M('PiG GroundReactionForce (N/kg). Ön-arka bileşen yürüme yönüne en yakın laboratuvar eksenine göre '
                  '(+ ileri/itme), medio-lateral bileşen her taraf için + medial olacak şekilde çevrildi (Vicon NormalisedGRF '
                  'ile aynı kural). Stance dışındaki ve temasın baş/sonundaki boş kareler 0 (temas yok) sayıldı; stance '
                  'içindeki boşluklar doldurulmadı.',
                  'PiG GroundReactionForce (N/kg). The anterior-posterior component was aligned with the lab axis closest '
                  'to the walking direction (+ forward/propulsion); the medio-lateral component was flipped so that medial '
                  'is + on each side (same rule as Vicon NormalisedGRF). Empty frames outside stance and at the start/end '
                  'of contact were set to 0 (no contact); gaps within stance were not filled.')),
        (M('Eksik veri', 'Missing data'),
         M('Aralıkta eksik örnek varsa değer boş bırakıldı ve uyarı yazıldı.',
           'If samples were missing in a window, the value was left empty and a warning was written.')
         if ayar.eksik_veri == 'bos' else
         M('Aralıkta eksik örnek varsa değer mevcut örneklerle hesaplandı ve uyarı yazıldı.',
           'If samples were missing in a window, the value was computed from the available samples and a warning was '
           'written.')),
        (M('Ortalama', 'Averaging'),
         M('Döngü değerleri → hasta-tarih-taraf ortalaması (tüm döngüler eşit ağırlıklı).',
           'Cycle values → patient-date-side mean (all cycles weighted equally).')
         if ayar.ortalama_yontemi == 'dongu' else
         M('Döngü değerleri → trial ortalaması → trial ortalamalarının ortalaması.',
           'Cycle values → trial mean → mean of trial means.')),
        (M('Formüller', 'Formulas'),
         M(f'{S["trial"]}, {S["hasta"]} ve {S["uzun"]} sayfalarındaki ortalamalar {S["dongu"]} sayfasına formülle '
           f'bağlıdır (Dislandi = 0 olan döngüler). Döngü sayfasında bir değeri değiştirir ya da Dislandi\'yi 1 yaparsanız '
           f'bu sayfalar güncellenir; değişikliğin gerekçesini Duzeltme_Notu sütununa yazın. Güncellenmeyenler: uç değerler, '
           f'dinamik EMG normalizasyon referansları, dalga formları ve programın hiç değer bulamadığı (boş) hücreler. '
           f'Döngü sayfası dışındaki sayfalar yanlışlıkla değiştirmeye karşı şifresiz kilitlidir (Gözden Geçir → Sayfa '
           f'Korumasını Kaldır).',
           f'The means on {S["trial"]}, {S["hasta"]} and {S["uzun"]} are linked by formulas to {S["dongu"]} (cycles with '
           f'Excluded = 0). Changing a value on the cycle sheet or setting Excluded to 1 updates these sheets; write the '
           f'reason in the Correction_Note column. Not updated: outliers, dynamic EMG normalization references, waveforms '
           f'and cells for which the program found no value (empty). Sheets other than the cycle sheet are locked without a '
           f'password against accidental edits (Review → Unprotect Sheet).')),
        (M('Tepe tanımı', 'Peak definition'),
         M('Tepe değerleri her döngüde ayrı bulunur, sonra ortalanır (ortalama eğrinin tepesi değil).',
           'Peaks are found in each cycle and then averaged (not the peak of the mean curve).')),
        (M('Adım uzunluğu', 'Step length'),
         M(f'IC anında iki {ayar.topuk_marker} markerı arası mesafe, yürüme doğrultusunda (işaretli).',
           f'Distance between the two {ayar.topuk_marker} markers at IC, along the walking direction (signed).')),
        ('Toe clearance', M('TOE markerı yüksekliği; trial içindeki stance ortası (%25–50) TOE noktalarından kurulan, taraf '
                            'ofsetli eğik zemin düzlemine göre.',
                            'TOE marker height above an inclined floor plane fitted to mid-stance (25–50%) TOE positions '
                            'in the trial, with a per-side offset.')),
        (M('EMG zinciri', 'EMG chain'), e.zincir_metni()),
        (M('EMG normalizasyonu', 'EMG normalization'),
         {'yok': M('Yok (µV)', 'None (µV)'),
          'mvic': M('MVIC (aynı zincirle işlenmiş MVIC zarf tepesi, µV)', 'MVIC (envelope peak of the MVIC trial processed '
                                                                          'with the same chain, µV)'),
          'dinamik_tepe': M('Dinamik: hasta-tarih-taraf için döngü tepelerinin ortalaması',
                            'Dynamic: mean of cycle peaks per patient-date-side'),
          'dinamik_ort': M('Dinamik: hasta-tarih-taraf için döngü ortalamalarının ortalaması',
                           'Dynamic: mean of cycle means per patient-date-side')}[e.normalizasyon]),
        (M('EMG veri kaybı', 'EMG data loss'),
         M(f'Ham sinyalde ≥ {e.kayip_min_ms:g} ms süren sabit değer dizileri (kablosuz paket kaybı) veri kaybı sayıldı; '
           f'zarfın bu bölgeyi kullanan kısmı boş bırakıldı.',
           f'Runs of constant raw values ≥ {e.kayip_min_ms:g} ms (wireless packet loss) were treated as data loss; the '
           f'envelope samples depending on them were left empty.')),
        (M('EMG aktivasyon', 'EMG activation'),
         M(f'Eşik = analiz aralığındaki en sessiz {e.sessiz_ms:g} ms penceresinin ortalaması + {e.esik_sd:g} SD (tabanı '
           f'tepe zarfın %{100 * e.esik_taban_tepe:g}\'i); ≥ {e.min_aktif_ms:g} ms aktif bölgeler, < {e.birlestir_ms:g} ms '
           f'boşluklar birleştirildi.',
           f'Threshold = mean of the quietest {e.sessiz_ms:g} ms window in the analysis region + {e.esik_sd:g} SD (floor '
           f'{100 * e.esik_taban_tepe:g}% of the peak envelope); active regions ≥ {e.min_aktif_ms:g} ms, gaps '
           f'< {e.birlestir_ms:g} ms merged.')),
        (M('EMG frekans', 'EMG frequency'),
         M('Medyan/ortalama frekans: filtrelenmiş ham sinyal, Hann pencereli periodogram, filtre bandı içinde.',
           'Median/mean frequency: filtered raw signal, Hann-windowed periodogram, within the filter band.')),
        (M('Elektromekanik gecikme', 'Electromechanical delay'),
         M('Program kaydırma uygulamadı (EMG, C3D\'deki haliyle kullanıldı).',
           'No shift was applied by the program (EMG used as stored in the C3D).')),
        (M('Simetri', 'Symmetry'),
         M('LSI = etkilenen / sağlam × 100 (iki değer aynı işaretliyse); Fark = etkilenen − sağlam.',
           'LSI = affected / unaffected × 100 (if both values have the same sign); Difference = affected − unaffected.')),
        (M('Uç değer', 'Outliers'),
         M(f'Robust z > {ayar.uc_esik:g}. Döngü düzeyinde: döngünün, aynı hasta-taraftaki diğer döngülerin medyanından '
           f'sapması / tüm gruplardaki bu sapmaların 1,4826 × medyanı (≥ 3 döngülü gruplar). Hasta düzeyinde: hastalar '
           f'arası medyan ve 1,4826 × MAD (≥ 5 hasta). Değerler silinmedi, yalnızca listelendi.',
           f'Robust z > {ayar.uc_esik:g}. Cycle level: deviation of the cycle from the median of the other cycles of the '
           f'same patient-side / 1.4826 × median of these deviations across all groups (groups with ≥ 3 cycles). Patient '
           f'level: median and 1.4826 × MAD across patients (≥ 5 patients). Values were not removed, only listed.')),
        (M('Kinetik bütünlük', 'Kinetic completeness'),
         M(f'Kinetik_Tamam = 1: hasta + tarih için sol ve sağ tarafın her birinde en az {max(int(ayar.min_kinetik or 1), 1)} '
           f'kinetik (kuvvet plakalı) döngü var. 0 olan satırlar "Uyarılar" sayfasında Hata olarak listelenir; satırlar '
           f'çıktıdan çıkarılmaz.',
           f'Kinetic_Complete = 1: at least {max(int(ayar.min_kinetik or 1), 1)} kinetic (force-plate) cycle on each of the '
           f'left and right sides for the patient + date. Rows with 0 are listed as Errors on the "Warnings" sheet; rows '
           f'are not removed from the output.')),
        (M('Lob istatistikleri', 'Lobe statistics'),
         M(f'Loblar eğrinin sıfır geçişleriyle ayrılır. "İlk pozitif/negatif lob" istatistiklerinde süresi döngünün '
           f'%{ayar.lob_min_gc:g}\'inden kısa loblar atlanır (not yazılır); lob yoksa değer boş kalır.',
           f'Lobes are separated by zero crossings of the curve. For the "first positive/negative lobe" statistics, lobes '
           f'shorter than {ayar.lob_min_gc:g}% of the cycle are skipped (a note is written); if there is no lobe the '
           f'value is empty.')),
        (M('İşaret kuralları', 'Sign conventions'),
         M('C3D\'deki Plug-in Gait/Polygon işaretleri korunur (değişken sözlüğüne bakın).',
           'Plug-in Gait/Polygon signs in the C3D are preserved (see the variable dictionary).')),
    ]
    if ek:
        satirlar += list(ek.items())
    return pd.DataFrame(satirlar, columns=['Ayar', 'Değer'])


# ---------------------------------------------------------------------------------
# Yazım yardımcıları
# ---------------------------------------------------------------------------------
def _sutun_harfi(i: int) -> str:
    from xlsxwriter.utility import xl_col_to_name
    return xl_col_to_name(i)


def _deger(v):
    """Hücreye yazılacak Python değeri (NaN → None)."""
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        return None if not np.isfinite(v) else float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (pd.Timestamp, _dt.date)):
        return str(v)[:10]
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


class _Sayfa:
    """Bir DataFrame'i xlsxwriter sayfasına yazar; formül hücreleri için sütun harfleri tutar."""

    def __init__(self, wb, ad: str, df: pd.DataFrame, fmt: dict):
        self.ad = ad
        self.df = df
        self.ws = wb.add_worksheet(ad[:31])
        self.fmt = fmt
        self.kol = {c: i for i, c in enumerate(df.columns)}
        self.n = len(df)

    def ref(self, col: str) -> str:
        """Bu sayfadaki bir sütunun mutlak aralığı (veri satırları)."""
        h = _sutun_harfi(self.kol[col])
        son = max(self.n + 1, 2)
        return f"'{self.ad}'!${h}$2:${h}${son}"

    def hucre(self, col: str, satir: int, mutlak_sutun=True) -> str:
        h = _sutun_harfi(self.kol[col])
        return f'${h}{satir + 2}' if mutlak_sutun else f'{h}{satir + 2}'

    def yaz(self, kilitli: bool, genislik_max=45, kilitsiz_sutunlar=()):
        ws, df, F = self.ws, self.df, self.fmt
        for j, c in enumerate(df.columns):
            ws.write_string(0, j, baslik(str(c)), F['baslik'])
        kilitsiz = {self.kol[c] for c in kilitsiz_sutunlar if c in self.kol}
        for i, row in enumerate(df.itertuples(index=False, name=None)):
            for j, v in enumerate(row):
                v = _deger(v)
                f = F['acik'] if j in kilitsiz else None
                if v is None:
                    if f is not None:
                        ws.write_blank(i + 1, j, None, f)
                elif isinstance(v, bool):
                    ws.write_boolean(i + 1, j, v, f)
                elif isinstance(v, (int, float)):
                    ws.write_number(i + 1, j, v, f)
                else:
                    ws.write_string(i + 1, j, str(v), f)
        for j, c in enumerate(df.columns):
            try:
                n = max([len(baslik(str(c)))] + [len(str(v)) for v in df[c].head(200).tolist()])
            except Exception:
                n = len(str(c))
            ws.set_column(j, j, min(max(8, n + 2), genislik_max), F['acik'] if j in kilitsiz else None)
        ws.freeze_panes(1, 1 if df.shape[1] > 3 else 0)
        if self.n:
            ws.autofilter(0, 0, self.n, max(df.shape[1] - 1, 0))
        if kilitli:
            ws.protect('', {'autofilter': True, 'sort': True, 'format_columns': True, 'format_rows': True,
                            'select_locked_cells': True, 'select_unlocked_cells': True})

    def formul(self, satir: int, col: str, formul: str, deger, dizi=False):
        """Hesaplanmış değeri olan hücreye formül yazar; değer yoksa (NaN) hücre boş kalır."""
        v = _deger(deger)
        if v is None or not isinstance(v, (int, float)):
            return
        r, c = satir + 1, self.kol[col]
        if dizi:
            self.ws.write_array_formula(r, c, r, c, '{' + formul + '}', None, v)
        else:
            self.ws.write_formula(r, c, formul, None, v)


def yaz(snc: Sonuc, ayar: Ayarlar, yol: str, hasta_bilgi: dict | None = None, dislamalar: dict | None = None,
        dosya_tarih_kaynagi: dict | None = None, anonim: dict | None = None, dil: str | None = None) -> dict:
    """Excel dosyasını yazar. Dönüş: özet sözlüğü."""
    if dil:
        ayarla(dil)
    import xlsxwriter
    from .algoritma import algoritma_tablosu
    T = birlestir(snc, ayar, hasta_bilgi, dislamalar)
    genis, uzun, trial, dongu, uc = T['genis'], T['uzun'], T['trial'], T['dongu'], T['uc']
    sutunlar = T['sutunlar']
    S = sayfa_adlari()

    # anonimleştirme: hasta → P001, dosya → P001_T01
    anon_dosya = {}
    if anonim:
        say = {}
        for b in snc.dosya_bilgisi:
            kod = anonim.get(b['hasta'], b['hasta'])
            say[kod] = say.get(kod, 0) + 1
            anon_dosya[b['dosya']] = f'{kod}_T{say[kod]:02d}'

    def hazirla(df):
        if df is None:
            return pd.DataFrame()
        if df.empty:
            return df
        df = df.copy()
        if 'Taraf' in df.columns:
            df['Taraf'] = df['Taraf'].map(taraf_metni)
        if 'Tarih' in df.columns:
            df['Tarih'] = df['Tarih'].map(lambda t: '' if t is None or (isinstance(t, float) and not np.isfinite(t))
                                          else str(t)[:10])
        if anonim:
            if 'Hasta' in df.columns:
                df['Hasta'] = df['Hasta'].map(lambda h: anonim.get(h, h))
            if 'Dosya' in df.columns:
                df['Dosya'] = df['Dosya'].map(lambda d: anon_dosya.get(d, d))
        return df

    # --- döngü sayfası
    gizli = [c for c in dongu.columns if c.startswith('_')] if not dongu.empty else []
    dongu_out = dongu.drop(columns=gizli) if gizli else dongu
    dongu_degisken = [c for c, q, tur, b in sutunlar if sorgu_duzeyi(q) == 'dongu']
    if not dongu_out.empty:
        sabit = ['Hasta', 'Tarih', 'Dosya', 'Taraf', 'Dongu', 'IC_s', 'FO_s', 'Sonraki_IC_s', 'Kinetik', 'Gecerli', 'Dislandi',
                 'Dislama_Nedeni']
        degisken = [c for c in dongu_degisken if c in dongu_out.columns]
        dongu_out = dongu_out[[c for c in sabit if c in dongu_out.columns] + degisken].copy()
        dongu_out.insert(dongu_out.columns.get_loc('Dislama_Nedeni') + 1, 'Duzeltme_Notu', '')
    dongu_out = hazirla(dongu_out)
    if not dongu_out.empty:
        dongu_out['Anahtar'] = dongu_out['Hasta'].astype(str) + '|' + dongu_out['Tarih'].astype(str)

    trial_out = hazirla(trial)
    if not trial_out.empty:
        trial_out['Anahtar'] = trial_out['Hasta'].astype(str) + '|' + trial_out['Tarih'].astype(str)
    tz = hazirla(T['trial_zu'])
    if tz is not None and not tz.empty:
        ilk = [c for c in ('Hasta', 'Tarih', 'Dosya', 'Taraf') if c in tz.columns]
        tz = tz[ilk + [c for c in tz.columns if c not in ilk]]
        tz['Anahtar'] = tz['Hasta'].astype(str) + '|' + tz['Tarih'].astype(str)
    genis_out = hazirla(genis)
    if not genis_out.empty and 'Etkilenen_Taraf' in genis_out.columns:
        genis_out['Etkilenen_Taraf'] = genis_out['Etkilenen_Taraf'].map(lambda s: taraf_metni(s) if s else '')
    # kinetik bayrağı: her iki tarafta da en az `min_kinetik` kinetik döngü var mı (yoksa analiz eksik sayılır)
    kin_eksik = []
    mk = max(int(getattr(ayar, 'min_kinetik', 1) or 1), 1)
    kin_ilgili = (not dongu.empty and int(dongu['Kinetik'].sum()) > 0) or any(
        (V.bul(q.degisken, ayar.kas_adlari) is not None and V.bul(q.degisken, ayar.kas_adlari).tur in ('kinetik', 'grf', 'faz'))
        for q in snc.sorgular)
    if kin_ilgili and not genis_out.empty and 'L_N_Kinetik' in genis_out.columns and 'R_N_Kinetik' in genis_out.columns:
        nl = genis_out['L_N_Kinetik'].fillna(0).astype(int)
        nr = genis_out['R_N_Kinetik'].fillna(0).astype(int)
        genis_out.insert(genis_out.columns.get_loc('Etkilenen_Taraf') + 1 if 'Etkilenen_Taraf' in genis_out.columns else 2,
                         'Kinetik_Tamam', ((nl >= mk) & (nr >= mk)).astype(int))
        for i in range(len(genis_out)):
            for sk, nn in (('L', int(nl.iloc[i])), ('R', int(nr.iloc[i]))):
                if nn >= mk:
                    continue
                ad, tarih = genis_out['Hasta'].iloc[i], genis_out['Tarih'].iloc[i]
                gercek = genis['Hasta'].iloc[i]
                yan = 'sol' if sk == 'L' else 'sağ'
                if nn == 0:
                    m = f'{ad}, {tarih or "tarihsiz"}: {yan} tarafta kinetik döngü yok; yürüme analizi eksik.'
                else:
                    m = (f'{ad}, {tarih or "tarihsiz"}: {yan} tarafta {nn} kinetik döngü var (en az {mk} gerekli); '
                         f'yürüme analizi eksik.')
                snc.uyarilar.append(Uyari('-', sk, '-', 'KINETIK', HATA, m, 'KINETIK'))
                kin_eksik.append({'hasta': gercek, 'tarih': tarih, 'taraf': sk, 'n': nn})
    uzun_out = hazirla(uzun)
    if not uzun_out.empty and 'Birim' in uzun_out.columns:
        uzun_out['Birim'] = uzun_out['Birim'].map(_)

    uy = pd.DataFrame([u.satir() for u in snc.uyarilar])
    if not uy.empty:
        uy = uy.rename(columns={'dosya': 'Dosya', 'taraf': 'Taraf', 'dongu': 'Dongu', 'kod': 'Kod', 'onem': 'Onem',
                                'mesaj': 'Mesaj', 'kategori': 'Kategori'})
        uy = uy[['Dosya', 'Taraf', 'Dongu', 'Kod', 'Onem', 'Kategori', 'Mesaj']]
        sira = {'Hata': 0, 'Uyarı': 1, 'Bilgi': 2}
        uy = uy.sort_values(by=['Onem', 'Dosya', 'Taraf'], key=lambda s: s.map(sira) if s.name == 'Onem' else s,
                            kind='stable')
        uy['Onem'] = uy['Onem'].map(lambda o: {'Hata': M('Hata', 'Error'), 'Uyarı': M('Uyarı', 'Warning'),
                                               'Bilgi': M('Bilgi', 'Info')}.get(o, o))
        uy['Mesaj'] = uy['Mesaj'].map(_)
        uy['Kategori'] = uy['Kategori'].map(_)
        uy = hazirla(uy)
    dis = dongu[dongu['Dislandi'] == 1][['Hasta', 'Tarih', 'Dosya', 'Taraf', 'Dongu', 'Dislama_Nedeni']] \
        if not dongu.empty else pd.DataFrame()
    dis = hazirla(dis)
    if not dis.empty:
        dis['Dislama_Nedeni'] = dis['Dislama_Nedeni'].map(_)
    dosyalar = pd.DataFrame(snc.dosya_bilgisi)
    if not dosyalar.empty and dosya_tarih_kaynagi:
        dosyalar['tarih_kaynagi'] = dosyalar['dosya'].map(lambda d: _(dosya_tarih_kaynagi.get(d, '')))
    if anonim and not dosyalar.empty:
        dosyalar.insert(0, 'Trial', dosyalar['dosya'].map(lambda d: anon_dosya.get(d, d)))
        dosyalar = dosyalar.drop(columns=['yol', 'dosya', 'hasta'], errors='ignore')
    sozluk = _sozluk(snc, ayar, sutunlar)
    ek = {}
    if snc.emg_ref:
        ek[M('EMG referans sayısı', 'Number of EMG references')] = len(snc.emg_ref)
    yontem = _yontem(snc, ayar, len(snc.dosya_bilgisi), ek)
    emg_ref = pd.DataFrame([{'Hasta_Tarih': k[0], 'Kas': k[1], 'Taraf': taraf_metni(k[2]), 'Referans_uV': v,
                             'Kaynak': _(snc.emg_ref_kaynak.get(k, ''))} for k, v in snc.emg_ref.items()])
    if anonim and not emg_ref.empty:
        emg_ref = emg_ref.drop(columns=['Hasta_Tarih'])
    uc_out = hazirla(uc)
    if not uc_out.empty and 'Duzey' in uc_out.columns:
        uc_out['Duzey'] = uc_out['Duzey'].map(_)
    algoritma = algoritma_tablosu(snc, ayar, sutunlar)

    os.makedirs(os.path.dirname(os.path.abspath(yol)) or '.', exist_ok=True)
    wb = xlsxwriter.Workbook(yol, {'nan_inf_to_errors': False, 'strings_to_numbers': False,
                                   'strings_to_formulas': False, 'strings_to_urls': False})
    F = {'baslik': wb.add_format({'bold': True, 'bg_color': '#DCE6F1', 'locked': True}),
         'acik': wb.add_format({'locked': False})}
    bos = pd.DataFrame({M('Bilgi', 'Info'): [M('Bu sayfada veri yok.', 'No data on this sheet.')]})

    sira_adlari = ['hasta', 'uzun', 'trial'] + (['trial_zu'] if tz is not None and not tz.empty else []) + \
        ['dongu', 'uyari', 'uc', 'dislanan', 'sozluk', 'yontem', 'dosyalar'] + \
        (['emg_ref'] if not emg_ref.empty else []) + ['algoritma']
    veriler = {'hasta': genis_out, 'uzun': uzun_out, 'trial': trial_out, 'trial_zu': tz, 'dongu': dongu_out,
               'uyari': uy, 'uc': uc_out, 'dislanan': dis, 'sozluk': sozluk, 'yontem': yontem, 'algoritma': algoritma,
               'dosyalar': dosyalar, 'emg_ref': emg_ref}
    sayfa = {}
    for k in sira_adlari:
        df = veriler[k]
        if df is None or df.empty:
            df = bos
        sayfa[k] = _Sayfa(wb, S[k], df, F)

    # --- formüller
    D = sayfa['dongu'] if not dongu_out.empty else None
    if D is not None:
        sayfa['dongu'].yaz(kilitli=False)
        for i in range(D.n):
            D.ws.write_formula(i + 1, D.kol['Anahtar'], f'{D.hucre("Hasta", i, False)}&"|"&{D.hucre("Tarih", i, False)}',
                               None, dongu_out['Anahtar'].iloc[i])
        D.ws.set_column(D.kol['Anahtar'], D.kol['Anahtar'], 14, None, {'hidden': True})
    else:
        sayfa['dongu'].yaz(kilitli=False)

    Tr = sayfa['trial'] if not trial_out.empty else None
    if Tr is not None:
        Tr.yaz(kilitli=True)
        for i in range(Tr.n):
            Tr.ws.write_formula(i + 1, Tr.kol['Anahtar'], f'{Tr.hucre("Hasta", i, False)}&"|"&{Tr.hucre("Tarih", i, False)}',
                                None, trial_out['Anahtar'].iloc[i])
        Tr.ws.set_column(Tr.kol['Anahtar'], Tr.kol['Anahtar'], 14, None, {'hidden': True})
        if D is not None:
            kosul = lambda i: (f'{D.ref("Dosya")},{Tr.hucre("Dosya", i)},{D.ref("Taraf")},{Tr.hucre("Taraf", i)},'
                               f'{D.ref("Dislandi")},0')
            for i in range(Tr.n):
                Tr.formul(i, 'N_Dongu', f'COUNTIFS({kosul(i)})', trial_out['N_Dongu'].iloc[i])
                Tr.formul(i, 'N_Kinetik', f'SUMIFS({D.ref("Kinetik")},{kosul(i)})', trial_out['N_Kinetik'].iloc[i])
                for c in dongu_degisken:
                    if c in Tr.kol and c in D.kol:
                        Tr.formul(i, c, f'IFERROR(AVERAGEIFS({D.ref(c)},{kosul(i)}),"")', trial_out[c].iloc[i])
    else:
        sayfa['trial'].yaz(kilitli=True)

    Z = sayfa.get('trial_zu') if tz is not None and not tz.empty else None
    if Z is not None:
        Z.yaz(kilitli=True)
        for i in range(Z.n):
            Z.ws.write_formula(i + 1, Z.kol['Anahtar'], f'{Z.hucre("Hasta", i, False)}&"|"&{Z.hucre("Tarih", i, False)}',
                               None, tz['Anahtar'].iloc[i])
        Z.ws.set_column(Z.kol['Anahtar'], Z.kol['Anahtar'], 14, None, {'hidden': True})

    H = sayfa['hasta'] if not genis_out.empty else None
    if H is not None:
        H.yaz(kilitli=True)
        sol, sag = taraf_metni('L'), taraf_metni('R')
        kaynak = Tr if (ayar.ortalama_yontemi == 'trial' and Tr is not None) else D
        trial_cols = [c for c, q, tur, b in sutunlar if sorgu_duzeyi(q) == 'trial']
        trial_taraf_cols = [c for c, q, tur, b in sutunlar if sorgu_duzeyi(q) == 'trial_taraf']
        for i in range(H.n):
            anahtar = f'{H.hucre("Hasta", i)}&"|"&{H.hucre("Tarih", i)}'
            for s, sad in (('L', sol), ('R', sag)):
                if D is not None:
                    kd = f'{D.ref("Anahtar")},{anahtar},{D.ref("Taraf")},"{sad}",{D.ref("Dislandi")},0'
                    if f'{s}_N_Dongu' in H.kol:
                        H.formul(i, f'{s}_N_Dongu', f'COUNTIFS({kd})', genis_out[f'{s}_N_Dongu'].iloc[i])
                    if f'{s}_N_Kinetik' in H.kol:
                        H.formul(i, f'{s}_N_Kinetik', f'SUMIFS({D.ref("Kinetik")},{kd})', genis_out[f'{s}_N_Kinetik'].iloc[i])
                if kaynak is not None:
                    if kaynak is D:
                        kk = f'{D.ref("Anahtar")},{anahtar},{D.ref("Taraf")},"{sad}",{D.ref("Dislandi")},0'
                    else:
                        kk = f'{Tr.ref("Anahtar")},{anahtar},{Tr.ref("Taraf")},"{sad}"'
                    for c in dongu_degisken:
                        hc = f'{s}_{c}'
                        if hc in H.kol and c in kaynak.kol:
                            H.formul(i, hc, f'IFERROR(AVERAGEIFS({kaynak.ref(c)},{kk}),"")', genis_out[hc].iloc[i])
                if Z is not None:
                    for c in trial_taraf_cols:
                        hc = f'{s}_{c}'
                        if hc in H.kol and c in Z.kol:
                            H.formul(i, hc, f'IFERROR(AVERAGEIFS({Z.ref(c)},{Z.ref("Anahtar")},{anahtar},'
                                            f'{Z.ref("Taraf")},"{sad}"),"")', genis_out[hc].iloc[i])
            if 'Kinetik_Tamam' in H.kol:
                H.formul(i, 'Kinetik_Tamam', f'IF(AND({H.hucre("L_N_Kinetik", i)}>={mk},{H.hucre("R_N_Kinetik", i)}>={mk}),1,0)',
                         int(genis_out['Kinetik_Tamam'].iloc[i]))
            if Z is not None:
                for c in trial_cols:
                    if c in H.kol and c in Z.kol:
                        H.formul(i, c, f'IFERROR(AVERAGEIFS({Z.ref(c)},{Z.ref("Anahtar")},{anahtar},{Z.ref("Taraf")},"-"),"")',
                                 genis_out[c].iloc[i])
            # simetri
            etk = genis_out['Etkilenen_Taraf'].iloc[i] if 'Etkilenen_Taraf' in H.kol else ''
            if etk in (sol, sag):
                e_s, s_s = ('L', 'R') if etk == sol else ('R', 'L')
                for c in dongu_degisken + trial_taraf_cols:
                    if f'Etkilenen_{c}' not in H.kol or f'{e_s}_{c}' not in H.kol:
                        continue
                    ec, sc = H.hucre(f'{e_s}_{c}', i), H.hucre(f'{s_s}_{c}', i)
                    H.formul(i, f'Etkilenen_{c}', f'IF(ISNUMBER({ec}),{ec},"")', genis_out[f'Etkilenen_{c}'].iloc[i])
                    H.formul(i, f'Saglam_{c}', f'IF(ISNUMBER({sc}),{sc},"")', genis_out[f'Saglam_{c}'].iloc[i])
                    H.formul(i, f'Fark_{c}', f'IF(AND(ISNUMBER({ec}),ISNUMBER({sc})),{ec}-{sc},"")',
                             genis_out[f'Fark_{c}'].iloc[i])
                    H.formul(i, f'LSI_{c}', f'IF(AND(ISNUMBER({ec}),ISNUMBER({sc})),IF(AND({sc}<>0,SIGN({ec})=SIGN({sc})),'
                                            f'100*{ec}/{sc},""),"")', genis_out[f'LSI_{c}'].iloc[i])
    else:
        sayfa['hasta'].yaz(kilitli=True)

    U = sayfa['uzun'] if not uzun_out.empty else None
    if U is not None:
        U.yaz(kilitli=True)
        tr_cols = set(c for c, q, tur, b in sutunlar if sorgu_duzeyi(q) == 'trial')
        for i in range(U.n):
            c = uzun_out['Degisken'].iloc[i]
            taraf = uzun_out['Taraf'].iloc[i]
            anahtar = f'{U.hucre("Hasta", i)}&"|"&{U.hucre("Tarih", i)}'
            if c in tr_cols:
                if Z is None or c not in Z.kol:
                    continue
                kaynak_r = Z.ref(c)
                kos = f'{Z.ref("Anahtar")},{anahtar},{Z.ref("Taraf")},"-"'
                maske = f'({Z.ref("Anahtar")}={anahtar})*({Z.ref("Taraf")}="-")'
            else:
                if D is None or c not in D.kol:
                    continue
                kaynak_r = D.ref(c)
                kos = f'{D.ref("Anahtar")},{anahtar},{D.ref("Taraf")},{U.hucre("Taraf", i)},{D.ref("Dislandi")},0'
                maske = f'({D.ref("Anahtar")}={anahtar})*({D.ref("Taraf")}={U.hucre("Taraf", i)})*({D.ref("Dislandi")}=0)'
            U.formul(i, 'Ortalama', f'IFERROR(AVERAGEIFS({kaynak_r},{kos}),"")', uzun_out['Ortalama'].iloc[i])
            U.formul(i, 'N', f'COUNTIFS({kos},{kaynak_r},"<>")', uzun_out['N'].iloc[i])
            U.formul(i, 'SS', f'IFERROR(STDEV(IF({maske}*ISNUMBER({kaynak_r}),{kaynak_r})),"")', uzun_out['SS'].iloc[i],
                     dizi=True)
            o, ss = U.hucre('Ortalama', i), U.hucre('SS', i)
            U.formul(i, 'CV_yuzde', f'IF(AND(ISNUMBER({ss}),ISNUMBER({o})),IF({o}<>0,100*{ss}/ABS({o}),""),"")',
                     uzun_out['CV_yuzde'].iloc[i])
    else:
        sayfa['uzun'].yaz(kilitli=True)

    for k in sira_adlari:
        if k in ('dongu', 'trial', 'trial_zu', 'hasta', 'uzun'):
            if k == 'trial_zu' and Z is None:
                sayfa[k].yaz(kilitli=True)
            continue
        sayfa[k].yaz(kilitli=True, genislik_max=120 if k in ('algoritma', 'yontem') else 45)
    if 'algoritma' in sayfa and not algoritma.empty:
        sayfa['algoritma'].ws.set_column(len(algoritma.columns) - 1, len(algoritma.columns) - 1, 120,
                                         wb.add_format({'text_wrap': True, 'valign': 'top'}))
    if 'yontem' in sayfa:
        sayfa['yontem'].ws.set_column(1, 1, 120, wb.add_format({'text_wrap': True, 'valign': 'top'}))
    sayfa['dongu'].ws.activate()
    sayfa['hasta'].ws.activate()
    try:
        wb.close()
    except xlsxwriter.exceptions.FileCreateError as e:
        raise PermissionError(str(e))
    n_uyari = len(snc.uyarilar)
    return {'yol': yol, 'hasta': int(len(genis)), 'dongu': int(len(dongu)), 'dislanan': int(len(dis)),
            'uyari': n_uyari, 'hata': int(sum(1 for u in snc.uyarilar if u.onem == 'Hata')),
            'uc_deger': int(len(uc)), 'kinetik_eksik': kin_eksik, 'min_kinetik': mk, 'tablolar': T}


# ---------------------------------------------------------------------------------
# Dalga formları (SPM ve grafikler için ayrı dosya)
# ---------------------------------------------------------------------------------
def dalga_sutunlari(w, araliklar: dict) -> list:
    a = araliklar.get(w.aralik)
    n = max(int(w.nokta), 2)
    g0 = g1 = None
    if a is not None:
        if a.bas == {'olay': 'IC'} and a.son == {'olay': 'NIC'}:
            g0, g1 = 0.0, 100.0
        elif a.bas.get('taban') == 'GC' and 'yuzde' in a.bas and a.son.get('taban') == 'GC' and 'yuzde' in a.son:
            g0, g1 = float(a.bas['yuzde']), float(a.son['yuzde'])
    if g0 is not None:
        p = g0 + np.arange(n) * (g1 - g0) / (n - 1)
        if np.allclose(p, np.round(p)):
            return [f'GC_{int(round(x)):03d}' if x >= 0 else f'GC_m{int(round(-x)):03d}' for x in p]
    return [f'P_{j:03d}' for j in range(n)]


def _bicimle(ws, df: pd.DataFrame, genislik_max=45):
    from openpyxl.styles import Font, PatternFill, Alignment
    dolgu = PatternFill('solid', fgColor='DCE6F1')
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = dolgu
        c.alignment = Alignment(vertical='top', wrap_text=False)
    ws.freeze_panes = 'B2' if df.shape[1] > 3 else 'A2'
    for i, col in enumerate(df.columns, start=1):
        try:
            n = max([len(str(col))] + [len(str(v)) for v in df[col].head(200).tolist()])
        except Exception:
            n = len(str(col))
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(max(8, n + 2), genislik_max)


def dalga_tablolari(snc: Sonuc, ayar: Ayarlar, dislamalar: dict | None = None) -> dict:
    dis = dislamalar or {}
    out = {}
    for w in snc.dalga_tanimlari:
        satirlar = [r for r in snc.dalgalar.get(w.kod, []) if (r['Dosya'], r['Taraf'], r['Dongu']) not in dis]
        cols = dalga_sutunlari(w, snc.araliklar)
        if not satirlar:
            out[w.kod] = (pd.DataFrame(columns=['Hasta', 'Tarih', 'Dosya', 'Taraf', 'Dongu'] + cols),
                          pd.DataFrame(columns=['Hasta', 'Tarih', 'Taraf', 'N_Dongu'] + cols), cols)
            continue
        dd = pd.DataFrame([{k: r[k] for k in ('Hasta', 'Tarih', 'Dosya', 'Taraf', 'Dongu')} for r in satirlar])
        dd = pd.concat([dd, pd.DataFrame(np.vstack([r['degerler'] for r in satirlar]), columns=cols)], axis=1)
        if ayar.ortalama_yontemi == 'trial':
            tr = dd.groupby(['Hasta', 'Tarih', 'Dosya', 'Taraf'], sort=False)[cols].mean().reset_index()
            hh = tr.groupby(['Hasta', 'Tarih', 'Taraf'], sort=False)[cols].mean().reset_index()
        else:
            hh = dd.groupby(['Hasta', 'Tarih', 'Taraf'], sort=False)[cols].mean().reset_index()
        n = dd.groupby(['Hasta', 'Tarih', 'Taraf'], sort=False).size().rename('N_Dongu').reset_index()
        hh = n.merge(hh, on=['Hasta', 'Tarih', 'Taraf'])
        out[w.kod] = (dd, hh, cols)
    return out


def dalga_yaz(snc: Sonuc, ayar: Ayarlar, yol: str, dislamalar: dict | None = None, anonim: dict | None = None,
              hasta_bilgi: dict | None = None, dil: str | None = None) -> str:
    if dil:
        ayarla(dil)
    T = dalga_tablolari(snc, ayar, dislamalar)
    anon_dosya = {}
    if anonim:
        say = {}
        for bb in snc.dosya_bilgisi:
            kod = anonim.get(bb['hasta'], bb['hasta'])
            say[kod] = say.get(kod, 0) + 1
            anon_dosya[bb['dosya']] = f'{kod}_T{say[kod]:02d}'
    ref_adlari = {r.id: r.ad for r in snc.refler}
    aciklama = []
    for w in snc.dalga_tanimlari:
        d = V.bul(w.degisken, ayar.kas_adlari)
        b = V.bilesen(d, w.bilesen) if d else None
        a = snc.araliklar.get(w.aralik)
        cols = T[w.kod][2]
        aciklama.append({'Kod': w.kod, 'Aciklama': _(w.aciklama), 'Degisken': _(d.ad) if d else w.degisken,
                         'Bilesen': f'{_(b.ad)} ({b.kod}) {_(b.isaret)}' if b else '', 'Birim': _(d.birim) if d else '',
                         'Aralik': (_(a.ad) + (f' ({_(capa_metni(a.bas, ref_adlari))} → {_(capa_metni(a.son, ref_adlari))})' if a.ozel else ''))
                         if a else w.aralik, 'Nokta': w.nokta, 'Sutunlar': f'{cols[0]} … {cols[-1]}',
                         'Taraf': M('karşı taraf', 'opposite side') if w.taraf == 'karsi' else M('aynı taraf', 'same side'),
                         'Dongu_sayisi': int(len(T[w.kod][0])),
                         'Not': M('Aralık eşit aralıklı noktalara doğrusal interpolasyonla bölündü. Eksik verili döngüler '
                                  'yazılmadı. Hasta sayfası SPM girdisidir (hasta-tarih-taraf ortalaması).',
                                  'The window was divided into equally spaced points by linear interpolation. Cycles with '
                                  'missing data were not written. The patient sheet is the SPM input (patient-date-side '
                                  'mean).')})
    etk = {}
    if hasta_bilgi:
        from .engine import hasta_anahtari
        for k, v in hasta_bilgi.items():
            etk[k] = (v or {}).get('etkilenen')

    def hazirla(df, hasta_duzeyi=False):
        df = df.copy()
        if hasta_duzeyi and not df.empty and etk:
            from .engine import hasta_anahtari
            df.insert(3, 'Etkilenen', [(M('Evet', 'Yes') if etk.get(hasta_anahtari(h, t)) == s else
                                        (M('Hayir', 'No') if etk.get(hasta_anahtari(h, t)) in ('L', 'R') else ''))
                                       for h, t, s in zip(df['Hasta'], df['Tarih'], df['Taraf'])])
        if 'Taraf' in df.columns:
            df['Taraf'] = df['Taraf'].map(taraf_metni)
        if anonim and 'Hasta' in df.columns:
            df['Hasta'] = df['Hasta'].map(lambda h: anonim.get(h, h))
            if 'Dosya' in df.columns:
                df['Dosya'] = df['Dosya'].map(lambda x: anon_dosya.get(x, x))
        df.columns = [baslik(c) if c != 'Etkilenen' else M('Etkilenen', 'Affected') for c in df.columns]
        return df
    with pd.ExcelWriter(yol, engine='openpyxl') as wr:
        a = pd.DataFrame(aciklama)
        a.columns = [baslik(c) for c in a.columns]
        a.to_excel(wr, sheet_name=M('Aciklama', 'Description'), index=False)
        _bicimle(wr.sheets[M('Aciklama', 'Description')], a)
        for w in snc.dalga_tanimlari:
            dd, hh, cols = T[w.kod]
            ad = re.sub(r'[\[\]\*\?/\\:]', '_', w.kod)[:24]
            for son, df in ((f'{ad}_{M("Hasta", "Patient")}', hazirla(hh, True)), (f'{ad}_{M("Dongu", "Cycle")}', hazirla(dd))):
                if df.empty:
                    df = pd.DataFrame({M('Bilgi', 'Info'): [M('Bu dalga formu için döngü yok.', 'No cycles for this waveform.')]})
                df.to_excel(wr, sheet_name=son[:31], index=False)
                ws = wr.sheets[son[:31]]
                ws.freeze_panes = 'F2'
    return yol
