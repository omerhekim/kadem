"""Değişken kataloğu: Plug-in Gait çıktıları, GRF, türetilmiş sinyaller, EMG, güç fazları ve
zamansal-uzamsal parametreler. İşaret kuralları C3D'deki (Plug-in Gait/Polygon) haliyle korunur.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Bilesen:
    kod: str        # X, Y, Z, AP, ML, V
    ad: str         # 'Sagittal'
    isaret: str = ''  # 'fleksiyon +'

    def dict(self):
        return {'kod': self.kod, 'ad': self.ad, 'isaret': self.isaret}


@dataclass(frozen=True)
class Degisken:
    id: str
    grup: str
    ad: str
    birim: str
    tur: str                      # kinematik | kinetik | grf | turetilmis | emg | faz | zu
    bilesenler: tuple = ()
    etiket: str = ''              # C3D etiketi, {S} = L/R
    olcek: float = 1.0
    aciklama: str = ''
    duzey: str = 'dongu'          # zu için: dongu | trial
    kisa: str = ''                # otomatik kod üretiminde kullanılan kısa ad (ASCII)

    def dict(self):
        return {'id': self.id, 'grup': self.grup, 'ad': self.ad, 'birim': self.birim, 'tur': self.tur,
                'bilesenler': [b.dict() for b in self.bilesenler], 'aciklama': self.aciklama,
                'duzey': self.duzey, 'kisa': self.kisa}


SAG, FRO, TRA = 'Sagittal', 'Frontal', 'Transvers'


def _b3(x, y, z):
    return (Bilesen('X', SAG, x), Bilesen('Y', FRO, y), Bilesen('Z', TRA, z))


KINEMATIK = [
    Degisken('PelvisAngles', 'Kinematik', 'Pelvis açısı', '°', 'kinematik',
             _b3('anterior tilt +', 'yukarı (oblikite) +', 'iç rotasyon (öne dönme) +'), '{S}PelvisAngles', kisa='Pelvis'),
    Degisken('HipAngles', 'Kinematik', 'Kalça açısı', '°', 'kinematik',
             _b3('fleksiyon +', 'adduksiyon +', 'iç rotasyon +'), '{S}HipAngles', kisa='Hip'),
    Degisken('KneeAngles', 'Kinematik', 'Diz açısı', '°', 'kinematik',
             _b3('fleksiyon +', 'varus +', 'iç rotasyon +'), '{S}KneeAngles', kisa='Knee'),
    Degisken('AnkleAngles', 'Kinematik', 'Ayak bileği açısı', '°', 'kinematik',
             _b3('dorsifleksiyon +', 'PiG frontal (inversiyon +)', 'ayak iç rotasyonu +'), '{S}AnkleAngles', kisa='Ankle'),
    Degisken('FootProgressAngles', 'Kinematik', 'Ayak ilerleme açısı', '°', 'kinematik',
             (Bilesen('Z', TRA, 'içe basma +'), Bilesen('X', SAG, 'PiG'), Bilesen('Y', FRO, 'PiG')),
             '{S}FootProgressAngles', kisa='FootProg'),
    Degisken('AbsAnkleAngle', 'Kinematik', 'Mutlak ayak bileği açısı (PiG)', '°', 'kinematik',
             _b3('PiG', 'PiG', 'PiG'), '{S}AbsAnkleAngle', kisa='AbsAnkle'),
    Degisken('ThoraxAngles', 'Kinematik', 'Toraks açısı', '°', 'kinematik', _b3('PiG', 'PiG', 'PiG'), '{S}ThoraxAngles', kisa='Thorax'),
    Degisken('SpineAngles', 'Kinematik', 'Omurga açısı', '°', 'kinematik', _b3('PiG', 'PiG', 'PiG'), '{S}SpineAngles', kisa='Spine'),
    Degisken('HeadAngles', 'Kinematik', 'Baş açısı', '°', 'kinematik', _b3('PiG', 'PiG', 'PiG'), '{S}HeadAngles', kisa='Head'),
    Degisken('NeckAngles', 'Kinematik', 'Boyun açısı', '°', 'kinematik', _b3('PiG', 'PiG', 'PiG'), '{S}NeckAngles', kisa='Neck'),
    Degisken('ShoulderAngles', 'Kinematik', 'Omuz açısı', '°', 'kinematik', _b3('PiG', 'PiG', 'PiG'), '{S}ShoulderAngles', kisa='Shoulder'),
    Degisken('ElbowAngles', 'Kinematik', 'Dirsek açısı', '°', 'kinematik', _b3('PiG', 'PiG', 'PiG'), '{S}ElbowAngles', kisa='Elbow'),
    Degisken('WristAngles', 'Kinematik', 'El bileği açısı', '°', 'kinematik', _b3('PiG', 'PiG', 'PiG'), '{S}WristAngles', kisa='Wrist'),
]

_MOM = 'iç moment, PiG işareti'
KINETIK = [
    Degisken('HipMoment', 'Kinetik', 'Kalça momenti', 'Nm/kg', 'kinetik',
             _b3('iç ekstansör +', 'iç abduktör + (dış adduksiyon)', _MOM), '{S}HipMoment', 0.001, kisa='HipMom'),
    Degisken('KneeMoment', 'Kinetik', 'Diz momenti', 'Nm/kg', 'kinetik',
             _b3('iç ekstansör + (dış fleksiyon)', 'iç abduktör + (dış adduksiyon, KAM)', _MOM), '{S}KneeMoment', 0.001,
             kisa='KneeMom'),
    Degisken('AnkleMoment', 'Kinetik', 'Ayak bileği momenti', 'Nm/kg', 'kinetik',
             _b3('iç plantar fleksör + (dış dorsifleksiyon)', _MOM, _MOM), '{S}AnkleMoment', 0.001, kisa='AnkleMom'),
    Degisken('HipPower', 'Kinetik', 'Kalça gücü', 'W/kg', 'kinetik',
             (Bilesen('Z', 'Toplam', 'üretim (konsantrik) +'),), '{S}HipPower', kisa='HipPow'),
    Degisken('KneePower', 'Kinetik', 'Diz gücü', 'W/kg', 'kinetik',
             (Bilesen('Z', 'Toplam', 'üretim (konsantrik) +'),), '{S}KneePower', kisa='KneePow'),
    Degisken('AnklePower', 'Kinetik', 'Ayak bileği gücü', 'W/kg', 'kinetik',
             (Bilesen('Z', 'Toplam', 'üretim (konsantrik) +'),), '{S}AnklePower', kisa='AnklePow'),
    Degisken('HipForce', 'Kinetik', 'Kalça eklem kuvveti', 'N/kg', 'kinetik', _b3('PiG', 'PiG', 'PiG'), '{S}HipForce', kisa='HipFor'),
    Degisken('KneeForce', 'Kinetik', 'Diz eklem kuvveti', 'N/kg', 'kinetik', _b3('PiG', 'PiG', 'PiG'), '{S}KneeForce', kisa='KneeFor'),
    Degisken('AnkleForce', 'Kinetik', 'Ayak bileği eklem kuvveti', 'N/kg', 'kinetik', _b3('PiG', 'PiG', 'PiG'), '{S}AnkleForce',
             kisa='AnkleFor'),
]

GRF = [
    Degisken('GRF', 'Yer tepki kuvveti', 'Yer tepki kuvveti (GRF)', 'N/kg', 'grf',
             (Bilesen('V', 'Dikey', 'yukarı +'), Bilesen('AP', 'Ön-arka', 'ileri (itme) +, geri (frenleme) −'),
              Bilesen('ML', 'Medio-lateral', 'medial +')),
             '{S}GroundReactionForce',
             aciklama='PiG GroundReactionForce; ön-arka ve medio-lateral bileşenler yürüme yönüne göre çevrilir. '
                      '%VA için 100/9,81 ile çarpın.', kisa='GRF'),
]

TURETILMIS = [
    Degisken('ToeClearance', 'Türetilmiş', 'Parmak yüksekliği (zemin düzlemine göre)', 'mm', 'turetilmis',
             (Bilesen('V', 'Yükseklik', ''),), '{S}TOE',
             aciklama='TOE markerının, trial içindeki stance ortası noktalarından kurulan zemin düzlemine göre yüksekliği.',
             kisa='ToeClr'),
]

FAZLAR = {
    'A1': ('Ayak bileği', 'AnklePower', -1, 'IC', 'CIC', 'stance ortası negatif (eksantrik plantar fleksör)'),
    'A2': ('Ayak bileği', 'AnklePower', +1, 'CFO', 'FO', 'itme (push-off) pozitif'),
    'K1': ('Diz', 'KneePower', -1, 'IC', 'SSMID', 'yüklenme negatif (eksantrik ekstansör)'),
    'K2': ('Diz', 'KneePower', +1, 'CFO', 'CIC', 'orta stance pozitif (konsantrik ekstansör)'),
    'K3': ('Diz', 'KneePower', -1, 'CIC', 'SW33', 'geç stance / erken swing negatif'),
    'K4': ('Diz', 'KneePower', -1, 'SW50', 'NIC', 'terminal swing negatif (eksantrik fleksör)'),
    'H1': ('Kalça', 'HipPower', +1, 'IC', 'SSMID', 'erken stance pozitif (konsantrik ekstansör)'),
    'H2': ('Kalça', 'HipPower', -1, 'CFO', 'FO', 'orta-geç stance negatif (eksantrik fleksör)'),
    'H3': ('Kalça', 'HipPower', +1, 'CIC', 'SW50', 'pre-swing / erken swing pozitif (konsantrik fleksör)'),
}

FAZ_DEGISKENLER = [
    Degisken(f'FAZ:{k}', 'Güç fazları (Winter)', f'{k} – {v[0]} {v[5]}', 'W/kg', 'faz', (), aciklama=v[5], kisa=k)
    for k, v in FAZLAR.items()
]

ZU = [
    Degisken('ZU:Hiz', 'Zamansal-uzamsal', 'Yürüme hızı', 'm/s', 'zu', duzey='trial', kisa='Speed',
             aciklama='Pelvis merkezinin ilk IC ile son IC arasında yürüme doğrultusundaki yer değiştirmesi / süre (iki taraf birlikte).'),
    Degisken('ZU:Kadans', 'Zamansal-uzamsal', 'Kadans', 'adım/dk', 'zu', duzey='trial', kisa='Cadence',
             aciklama='60 × adım sayısı / (son IC − ilk IC); adım = ardışık iki IC (iki ayak birlikte).'),
    Degisken('ZU:HizBoyutsuz', 'Zamansal-uzamsal', 'Yürüme hızı (boyutsuz, v/√(g·L))', '-', 'zu', duzey='trial',
             kisa='SpeedNorm', aciklama='Froude tabanlı boyutsuz hız; L = sağ ve sol bacak uzunluğu ortalaması.'),
    Degisken('ZU:AdimUzunlugu', 'Zamansal-uzamsal', 'Adım uzunluğu (step)', 'm', 'zu', kisa='StepLen',
             aciklama='Bu tarafın IC anında iki topuk markerı arası mesafe (yürüme doğrultusunda, işaretli).'),
    Degisken('ZU:AdimUzunluguOran', 'Zamansal-uzamsal', 'Adım uzunluğu / bacak uzunluğu', '-', 'zu', kisa='StepLenNorm'),
    Degisken('ZU:StrideUzunlugu', 'Zamansal-uzamsal', 'Stride uzunluğu', 'm', 'zu', kisa='StrideLen',
             aciklama='Aynı topuk markerının IC ile sonraki IC arasındaki yer değiştirmesi.'),
    Degisken('ZU:StrideUzunluguOran', 'Zamansal-uzamsal', 'Stride uzunluğu / bacak uzunluğu', '-', 'zu', kisa='StrideLenNorm'),
    Degisken('ZU:AdimGenisligi', 'Zamansal-uzamsal', 'Adım genişliği', 'm', 'zu', kisa='StepWidth',
             aciklama='Bu tarafın IC anında iki topuk markerı arası medio-lateral mesafe.'),
    Degisken('ZU:StrideSuresi', 'Zamansal-uzamsal', 'Stride süresi', 's', 'zu', kisa='StrideTime'),
    Degisken('ZU:AdimSuresi', 'Zamansal-uzamsal', 'Adım süresi (step)', 's', 'zu', kisa='StepTime',
             aciklama='Önceki karşı IC ile bu tarafın IC anı arası süre.'),
    Degisken('ZU:StanceSuresi', 'Zamansal-uzamsal', 'Stance süresi', 's', 'zu', kisa='StanceTime'),
    Degisken('ZU:SwingSuresi', 'Zamansal-uzamsal', 'Swing süresi', 's', 'zu', kisa='SwingTime'),
    Degisken('ZU:TekDestekSuresi', 'Zamansal-uzamsal', 'Tek destek süresi', 's', 'zu', kisa='SingleSupTime',
             aciklama='Karşı FO ile karşı IC arası süre.'),
    Degisken('ZU:CiftDestek1Suresi', 'Zamansal-uzamsal', '1. çift destek süresi', 's', 'zu', kisa='DS1Time'),
    Degisken('ZU:CiftDestek2Suresi', 'Zamansal-uzamsal', '2. çift destek süresi', 's', 'zu', kisa='DS2Time'),
    Degisken('ZU:CiftDestekToplam', 'Zamansal-uzamsal', 'Toplam çift destek süresi', 's', 'zu', kisa='DSTime'),
    Degisken('ZU:StanceYuzde', 'Zamansal-uzamsal', 'Stance oranı (%GC)', '%', 'zu', kisa='StancePct'),
    Degisken('ZU:SwingYuzde', 'Zamansal-uzamsal', 'Swing oranı (%GC)', '%', 'zu', kisa='SwingPct'),
    Degisken('ZU:TekDestekYuzde', 'Zamansal-uzamsal', 'Tek destek oranı (%GC)', '%', 'zu', kisa='SingleSupPct'),
    Degisken('ZU:KarsiFOYuzde', 'Zamansal-uzamsal', 'Karşı Foot Off zamanı (%GC)', '%', 'zu', kisa='OppFOPct'),
    Degisken('ZU:KarsiICYuzde', 'Zamansal-uzamsal', 'Karşı IC zamanı (%GC)', '%', 'zu', kisa='OppICPct'),
    Degisken('ZU:DonguHizi', 'Zamansal-uzamsal', 'Döngü hızı (stride uzunluğu / süre)', 'm/s', 'zu', kisa='StrideSpeed'),
]

STATIK = KINEMATIK + KINETIK + GRF + TURETILMIS + FAZ_DEGISKENLER + ZU
_BY_ID = {d.id: d for d in STATIK}


# --- EMG -------------------------------------------------------------------
KASLAR = [
    ('TA', 'Tibialis anterior'), ('GM', 'Gastrocnemius medialis'), ('GL', 'Gastrocnemius lateralis'),
    ('SOL', 'Soleus'), ('PL', 'Peroneus longus'), ('RF', 'Rectus femoris'), ('VM', 'Vastus medialis'),
    ('VL', 'Vastus lateralis'), ('BF', 'Biceps femoris'), ('ST', 'Semitendinosus'), ('SM', 'Semimembranosus'),
    ('GMED', 'Gluteus medius'), ('GMAX', 'Gluteus maximus'), ('ADD', 'Adduktor longus'), ('TFL', 'Tensor fascia latae'),
    ('ES', 'Erector spinae'), ('RA', 'Rectus abdominis'),
]
KAS_ADI = dict(KASLAR)


def emg_degisken(kas_kodu: str, kas_adi: str | None = None) -> Degisken:
    ad = kas_adi or KAS_ADI.get(kas_kodu, kas_kodu)
    return Degisken(f'EMG:{kas_kodu}', 'EMG', f'{ad} ({kas_kodu}) EMG', 'µV', 'emg',
                    (Bilesen('E', 'Zarf', ''),), aciklama='İşlenmiş EMG zarfı (filtre + RMS ya da lineer zarf).',
                    kisa=kas_kodu)


def bul(degisken_id: str, kas_adlari: dict | None = None) -> Degisken | None:
    if degisken_id in _BY_ID:
        return _BY_ID[degisken_id]
    if degisken_id.startswith('EMG:'):
        k = degisken_id[4:]
        return emg_degisken(k, (kas_adlari or {}).get(k))
    return None


def bilesen(d: Degisken, kod: str | None) -> Bilesen | None:
    if not d.bilesenler:
        return None
    if kod is None:
        return d.bilesenler[0]
    for b in d.bilesenler:
        if b.kod == kod:
            return b
    return None
