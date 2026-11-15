"""Hazır sorgu paketleri: örnek çalışma için E, S, P, W, G, N değişken setleri.

Her paket; sorgular, gerekirse özel aralıklar ve referans anlardan oluşur. Sütun adları sabittir (karşılaştırma için).
"""
from __future__ import annotations

from .engine import Sorgu, RefAn, DalgaFormu
from .intervals import Aralik, Y

PAKET_ARALIKLARI = {
    'GC0_30': Aralik('GC0_30', '%0–30 döngü', Y(0, 'GC'), Y(30, 'GC'), 'GC0to30', ozel=True),
    'ST5_100': Aralik('ST5_100', '%5–100 stance (IC sonrası ilk %5 hariç)', Y(5, 'ST'), Y(100, 'ST'), 'ST5to100', ozel=True),
    'SW25_85': Aralik('SW25_85', '%25–85 swing (MTC arama penceresi)', Y(25, 'SW'), Y(85, 'SW'), 'SW25to85', ozel=True),
    'GC0_50': Aralik('GC0_50', '%0–50 döngü', Y(0, 'GC'), Y(50, 'GC'), 'GC0to50', ozel=True),
}

DALGA_PAKETI = {
    'ad': 'W9–W12 örnek dalga formları',
    'dalgalar': [
        DalgaFormu('W9_KneeSag', 'KneeAngles', 'X', 'GC', 101, 'ipsi', 'Diz sagittal açısı, %0–100 döngü', 'W'),
        DalgaFormu('W10_AnkleSag', 'AnkleAngles', 'X', 'GC', 101, 'ipsi', 'Ayak bileği sagittal açısı, %0–100 döngü', 'W'),
        DalgaFormu('W11_KneeFro_0-50', 'KneeAngles', 'Y', 'GC0_50', 51, 'ipsi',
                   'Diz frontal açısı, %0–50 döngü (rotasyon çapraz etkisi nedeniyle ilk yarı)', 'W'),
        DalgaFormu('W12_KAM_0-50', 'KneeMoment', 'Y', 'GC0_50', 51, 'ipsi', 'KAM (diz frontal momenti), %0–50 döngü, '
                   'yalnızca plakalı döngüler', 'W'),
    ],
    'araliklar': ['GC0_50'],
}


def dalga_paketi():
    return ([DalgaFormu.from_dict(w.dict()) for w in DALGA_PAKETI['dalgalar']],
            [PAKET_ARALIKLARI[a] for a in DALGA_PAKETI['araliklar']])

PAKET_REFLERI = {
    'MTC': RefAn('MTC', 'MTC anı (en düşük parmak yüksekliği)', 'ToeClearance', 'V', 'SW25_85', 'min'),
}


def _q(kod, deg, bil, ara, ist, paket, aciklama='', zb='%GC', **par):
    return Sorgu(kod, deg, bil, ara, ist, zb, 'ipsi', par, aciklama, paket)


PAKETLER = {
    'E': {
        'ad': 'E – Erken stance / yüklenme (E1–E7)',
        'sorgular': [
            _q('E1_Ankle_IC_Sagital', 'AnkleAngles', 'X', '@IC', 'deger', 'E', 'IC anında ayak bileği sagittal açısı'),
            _q('E2_Peak_Knee_Flex_LR', 'KneeAngles', 'X', 'DS1', 'max', 'E', '1. çift destekte en yüksek diz fleksiyonu'),
            _q('E3_Peak_Knee_Moment_LR_Sagital', 'KneeMoment', 'X', 'DS1', 'max', 'E',
               '1. çift destekte en yüksek diz sagittal momenti'),
            _q('E4_KAM1_30percent', 'KneeMoment', 'Y', 'GC0_30', 'max', 'E', 'Döngünün ilk %30\'unda en yüksek KAM'),
            _q('E5_LR_Plantarflex_Excursion', 'AnkleAngles', 'X', 'DS1', 'min_bas', 'E',
               '1. çift destekte plantar fleksiyon ekskürsiyonu (min − IC değeri)'),
            _q('E6_Ankle_Moment_LR_Frontal', 'AnkleMoment', 'Y', 'DS1', 'absmax', 'E',
               '1. çift destekte ayak bileği frontal momenti (işaretli mutlak maksimum)'),
            _q('E7_Dynamic_Varus_Excursion', 'KneeAngles', 'Y', 'DS1', 'sapma', 'E',
               '1. çift destekte IC değerine göre en büyük frontal sapma (işaretli)'),
        ],
        'araliklar': ['GC0_30'], 'refler': [],
    },
    'S': {
        'ad': 'S – Stance (S1–S7)',
        'sorgular': [
            _q('S1_Max_Knee_Ext_SingleStance', 'KneeAngles', 'X', 'SS', 'min', 'S', 'Tek destekte en yüksek diz ekstansiyonu'),
            _q('S2_Knee_Sagital_ROM', 'KneeAngles', 'X', 'ST', 'rom', 'S', 'Stance diz sagittal açıklığı'),
            _q('S3_Peak_Knee_Extensor_Moment', 'KneeMoment', 'X', 'ST5_100', 'min', 'S',
               'Stance (ilk %5 hariç) diz sagittal momenti minimumu'),
            _q('S4_Mean_Knee_Varus_Valgus', 'KneeAngles', 'Y', 'ST', 'ort', 'S', 'Stance ortalama diz frontal açısı'),
            _q('S5_KAM_Impulse', 'KneeMoment', 'Y', 'ST', 'lob_poz', 'S', 'KAM impulsu (en büyük pozitif lob)'),
            _q('S5A_KAM_Impulse2', 'KneeMoment', 'Y', 'ST', 'alan_poz', 'S', 'KAM impulsu (tüm pozitif alan)'),
            _q('S6_Frontal_Knee_Excursion', 'KneeAngles', 'Y', 'ST', 'rom', 'S', 'Stance diz frontal açıklığı'),
            _q('S7_Mean_Foot_Progression', 'FootProgressAngles', 'Z', 'ST', 'ort', 'S', 'Stance ortalama ayak ilerleme açısı'),
        ],
        'araliklar': ['ST5_100'], 'refler': [],
    },
    'P': {
        'ad': 'P – İtme / terminal stance (P1–P10)',
        'sorgular': [
            _q('P1_Terminal_Stance_Plantarflexion', 'AnkleAngles', 'X', 'PO', 'min', 'P', 'İtme penceresinde en düşük ayak bileği açısı'),
            _q('P2_Peak_Ankle_Dorsiflexion_Moment', 'AnkleMoment', 'X', 'PO', 'max', 'P', 'İtme penceresinde en yüksek ayak bileği momenti'),
            _q('P3_Peak_Positive_Ankle_Power', 'AnklePower', 'Z', 'PO', 'max', 'P', 'İtme penceresinde en yüksek ayak bileği gücü'),
            _q('P4_Positive_Ankle_Work', 'AnklePower', 'Z', 'PO', 'alan_poz', 'P', 'İtme penceresinde pozitif ayak bileği işi'),
            _q('P5_Peak_Ankle_Power_Timing_GC', 'AnklePower', 'Z', 'PO', 'tmax', 'P', 'Ayak bileği güç tepesinin zamanı'),
            _q('P6_Knee_Power_Max', 'KneePower', 'Z', 'PO', 'max', 'P', 'İtme penceresinde diz gücü maksimumu'),
            _q('P6_Knee_Power_Min', 'KneePower', 'Z', 'PO', 'min', 'P', 'İtme penceresinde diz gücü minimumu'),
            _q('P7_Hip_Power_Max', 'HipPower', 'Z', 'PO', 'max', 'P', 'İtme penceresinde kalça gücü maksimumu'),
            _q('P7_Hip_Power_Min', 'HipPower', 'Z', 'PO', 'min', 'P', 'İtme penceresinde kalça gücü minimumu'),
            _q('P8_Peak_Anterior_Propulsive_GRF', 'GRF', 'AP', 'ST', 'max', 'P', 'Stance\'te en yüksek ileri (itme) GRF'),
            _q('P9_Propulsive_Impulse', 'GRF', 'AP', 'ST', 'alan_poz', 'P', 'İtme impulsu (pozitif ön-arka GRF alanı)'),
            _q('P10_Second_Vertical_GRF_Peak', 'GRF', 'V', 'ST', 'tepe2', 'P', 'Dikey GRF ikinci tepe', vadi_esik=0.3,
               son_atla=0.05),
        ],
        'araliklar': [], 'refler': [],
    },
    'W': {
        'ad': 'W – Swing (W1–W8)',
        'sorgular': [
            _q('W1_Peak_Swing_Dorsiflexion', 'AnkleAngles', 'X', 'SW', 'max', 'W', 'Swing\'de en yüksek dorsifleksiyon'),
            _q('W2_Mean_Swing_Dorsiflexion', 'AnkleAngles', 'X', 'SW', 'ort', 'W', 'Swing ortalama ayak bileği açısı'),
            _q('W3_Peak_Swing_Knee_Flexion', 'KneeAngles', 'X', 'SW', 'max', 'W', 'Swing\'de en yüksek diz fleksiyonu'),
            _q('W4_MTC_mm', 'ToeClearance', 'V', 'SW25_85', 'min', 'W', 'Minimum parmak yüksekliği (MTC)'),
            _q('W4_MTC_Zamani_Swing_Yuzde', 'ToeClearance', 'V', 'SW25_85', 'tmin', 'W', 'MTC zamanı', zb='%SW'),
            _q('W5_Ankle_Angle_at_MTC', 'AnkleAngles', 'X', '@MTC', 'deger', 'W', 'MTC anında ayak bileği açısı'),
            _q('W6_Knee_Angle_at_MTC', 'KneeAngles', 'X', '@MTC', 'deger', 'W', 'MTC anında diz açısı'),
            _q('W7_Peak_DF_Zamani_GC_Yuzde', 'AnkleAngles', 'X', 'SW', 'tmax', 'W', 'Swing dorsifleksiyon tepesinin zamanı',
               yumusatma_ms=50),
            _q('W7_Peak_DF_Zamani_Swing_Yuzde', 'AnkleAngles', 'X', 'SW', 'tmax', 'W', 'Swing dorsifleksiyon tepesinin zamanı',
               zb='%SW', yumusatma_ms=50),
            _q('W8_Ankle_Sagital_ROM', 'AnkleAngles', 'X', 'GC', 'rom', 'W', 'Döngü boyunca ayak bileği sagittal açıklığı'),
        ],
        'araliklar': ['SW25_85'], 'refler': ['MTC'],
    },
    'G': {
        'ad': 'G – Zamansal-uzamsal (G1–G5)',
        'sorgular': [
            _q('G1_Walking_Speed_ms', 'ZU:Hiz', None, None, 'deger', 'G', 'Yürüme hızı'),
            _q('G2_Step_Length_m', 'ZU:AdimUzunlugu', None, None, 'deger', 'G', 'Adım uzunluğu'),
            _q('G3_Single_Support_Time_s', 'ZU:TekDestekSuresi', None, None, 'deger', 'G', 'Tek destek süresi'),
            _q('G4_Stance_Time_s', 'ZU:StanceSuresi', None, None, 'deger', 'G', 'Stance süresi'),
            _q('G5_Cadence_stepsmin', 'ZU:Kadans', None, None, 'deger', 'G', 'Kadans'),
            _q('Stride_Time_s', 'ZU:StrideSuresi', None, None, 'deger', 'G', 'Stride süresi'),
            _q('Stride_Length_m', 'ZU:StrideUzunlugu', None, None, 'deger', 'G', 'Stride uzunluğu'),
        ],
        'araliklar': [], 'refler': [],
    },
    'N': {
        'ad': 'N – Tibialis anterior EMG (N1–N9)',
        'sorgular': [
            _q('N1_TA_Peak_LR', 'EMG:TA', 'E', 'DS1', 'max', 'N', 'TA tepe, 1. çift destek'),
            _q('N2_Peak_LR_Zamani_GC', 'EMG:TA', 'E', 'DS1', 'tmax', 'N', 'TA tepe zamanı, 1. çift destek'),
            _q('N2_Peak_LR_Zamani_LRyuzde', 'EMG:TA', 'E', 'DS1', 'tmax', 'N', 'TA tepe zamanı (% aralık)', zb='%AR'),
            _q('N3_TA_Mean_RMS_LR', 'EMG:TA', 'E', 'DS1', 'ort', 'N', 'TA ortalama RMS, 1. çift destek'),
            _q('N4_LR_Onset_GC', 'EMG:TA', 'E', 'DS1', 'onset', 'N', 'TA aktivasyon başlangıcı, 1. çift destek'),
            _q('N4_LR_Offset_GC', 'EMG:TA', 'E', 'DS1', 'offset', 'N', 'TA aktivasyon bitişi, 1. çift destek'),
            _q('N4_LR_Sure_ms', 'EMG:TA', 'E', 'DS1', 'aktif_ms', 'N', 'TA aktif süre, 1. çift destek'),
            _q('N4_LR_Aktif_Basta', 'EMG:TA', 'E', 'DS1', 'aktif_basta', 'N', 'TA IC anında aktif mi'),
            _q('N4_LR_Aktif_Sonda', 'EMG:TA', 'E', 'DS1', 'aktif_sonda', 'N', 'TA karşı FO anında aktif mi'),
            _q('N5_TA_Peak_Swing', 'EMG:TA', 'E', 'SW', 'max', 'N', 'TA tepe, swing'),
            _q('N6_Peak_Swing_Zamani_GC', 'EMG:TA', 'E', 'SW', 'tmax', 'N', 'TA tepe zamanı, swing'),
            _q('N6_Peak_Swing_Zamani_Swingyuzde', 'EMG:TA', 'E', 'SW', 'tmax', 'N', 'TA tepe zamanı (% swing)', zb='%SW'),
            _q('N7_TA_Mean_RMS_Swing', 'EMG:TA', 'E', 'SW', 'ort', 'N', 'TA ortalama RMS, swing'),
            _q('N8_Swing_Onset_GC', 'EMG:TA', 'E', 'SW', 'onset', 'N', 'TA aktivasyon başlangıcı, swing'),
            _q('N8_Swing_Offset_GC', 'EMG:TA', 'E', 'SW', 'offset', 'N', 'TA aktivasyon bitişi, swing'),
            _q('N8_Swing_Sure_ms', 'EMG:TA', 'E', 'SW', 'aktif_ms', 'N', 'TA aktif süre, swing'),
            _q('N8_Swing_Aktif_Basta', 'EMG:TA', 'E', 'SW', 'aktif_basta', 'N', 'TA FO anında aktif mi'),
            _q('N8_Swing_Aktif_Sonda', 'EMG:TA', 'E', 'SW', 'aktif_sonda', 'N', 'TA sonraki IC anında aktif mi'),
            _q('N9_Global_TA_Peak', 'EMG:TA', 'E', 'GC', 'max', 'N', 'TA tepe, tüm döngü'),
        ],
        'araliklar': [], 'refler': [],
    },
}


def paket(ad: str):
    """(sorgular, özel aralıklar, referans anlar)"""
    p = PAKETLER[ad]
    return ([Sorgu.from_dict(q.dict()) for q in p['sorgular']],
            [PAKET_ARALIKLARI[a] for a in p['araliklar']],
            [PAKET_REFLERI[r] for r in p['refler']])


def tum_paketler():
    s, a, r = [], [], []
    for k in PAKETLER:
        q, aa, rr = paket(k)
        s += q
        a += [x for x in aa if x.id not in {y.id for y in a}]
        r += [x for x in rr if x.id not in {y.id for y in r}]
    return s, a, r
