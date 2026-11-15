"""Excel 'Algoritma' sayfası: her çıktı sütununun adım adım nasıl hesaplandığı.

Amaç: sayfayı okuyan biri programa bakmadan aynı sayıyı C3D'den elle hesaplayabilsin.
"""
from __future__ import annotations

import pandas as pd

from . import variables as V
from .aggregate import sorgu_duzeyi, NORM_EK
from .dil import M, _
from .engine import Ayarlar, Sonuc
from .intervals import capa_metni
from .stats import IST, FAZ_IST, ZAMAN_BIRIMLERI, SURE_BIRIMLERI

BILESEN_INDEKS = {'X': 1, 'Y': 2, 'Z': 3}


def _olay_tanimi(kod: str) -> str:
    return {
        'IC': M('IC: bu tarafın Foot Strike event\'i (döngünün başı)', 'IC: this side\'s Foot Strike event (cycle start)'),
        'NIC': M('sonraki IC: bu tarafın bir sonraki Foot Strike event\'i (döngünün sonu)',
                 'next IC: this side\'s next Foot Strike event (cycle end)'),
        'FO': M('FO: bu tarafın döngü içindeki Foot Off event\'i', 'FO: this side\'s Foot Off event within the cycle'),
        'CFO': M('karşı FO: karşı tarafın döngü içindeki ilk Foot Off event\'i',
                 'opposite FO: first opposite-side Foot Off event within the cycle'),
        'CIC': M('karşı IC: karşı tarafın döngü içindeki Foot Strike event\'i',
                 'opposite IC: opposite-side Foot Strike event within the cycle'),
        'PCIC': M('önceki karşı IC: döngünün IC\'sinden önceki son karşı taraf Foot Strike event\'i',
                  'previous opposite IC: last opposite-side Foot Strike before the cycle\'s IC'),
    }.get(kod, kod)


def _capa_aciklama(c: dict, ref_adlari: dict) -> str:
    if 'olay' in c:
        s = _olay_tanimi(c['olay'])
        if c.get('kayma_ms'):
            s += M(f'; buna {c["kayma_ms"]:+g} ms eklenir', f'; plus {c["kayma_ms"]:+g} ms')
        if c.get('kayma_gc'):
            s += M(f'; buna döngü süresinin %{c["kayma_gc"]:+g}\'i eklenir',
                   f'; plus {c["kayma_gc"]:+g}% of the cycle duration')
        return s
    if 'yuzde' in c:
        p = c['yuzde']
        taban = c.get('taban', 'GC')
        if taban == 'GC':
            return M(f'IC + döngü süresinin %{p:g}\'i', f'IC + {p:g}% of cycle duration')
        if taban == 'ST':
            return M(f'IC + stance süresinin (IC→FO) %{p:g}\'i', f'IC + {p:g}% of stance duration (IC→FO)')
        return M(f'FO + swing süresinin (FO→sonraki IC) %{p:g}\'i', f'FO + {p:g}% of swing duration (FO→next IC)')
    if 'ref' in c:
        rad = _(ref_adlari.get(c['ref']) or '') or (M(f'{c["ref"][4:]} tepe anı', f'{c["ref"][4:]} peak instant')
                                           if c['ref'].startswith('FAZ:') else c['ref'])
        s = M(f'referans an: "{rad}" (aşağıda)', f'reference instant: "{rad}" (below)')
        if c.get('kayma_ms'):
            s += M(f'; buna {c["kayma_ms"]:+g} ms eklenir', f'; plus {c["kayma_ms"]:+g} ms')
        if c.get('kayma_gc'):
            s += M(f'; buna döngü süresinin %{c["kayma_gc"]:+g}\'i eklenir',
                   f'; plus {c["kayma_gc"]:+g}% of the cycle duration')
        return s
    if 'ozel' in c:
        return {'SSMID': M('tek destek ortası = (karşı FO + karşı IC) / 2', 'mid single support = (opp. FO + opp. IC) / 2'),
                'SW33': M('FO + swing süresinin %33,3\'ü', 'FO + 33.3% of swing duration'),
                'SW50': M('FO + swing süresinin %50\'si', 'FO + 50% of swing duration')}.get(c['ozel'], c['ozel'])
    return '?'


def _kaynak(d, b, q, ayar: Ayarlar) -> str:
    taraf = M('aynı taraf (döngünün tarafı)', 'same side (the cycle\'s side)') if q.taraf != 'karsi' else \
        M('karşı taraf', 'opposite side')
    if d.tur in ('kinematik', 'kinetik'):
        etk = d.etiket.replace('{S}', 'L') + ' / ' + d.etiket.replace('{S}', 'R')
        s = M(f'C3D point "{etk}" ({taraf}), {BILESEN_INDEKS.get(b.kod, "?")}. bileşen ({b.kod})',
              f'C3D point "{etk}" ({taraf}), component {BILESEN_INDEKS.get(b.kod, "?")} ({b.kod})')
        if d.olcek != 1.0:
            s += M(f'; {d.olcek:g} ile çarpılır (Nmm/kg → Nm/kg)', f'; multiplied by {d.olcek:g} (Nmm/kg → Nm/kg)')
        s += M(f'. İşaret: {_(b.isaret)} (Plug-in Gait). Birim: {d.birim}.', f'. Sign: {_(b.isaret)} (Plug-in Gait). Unit: {d.birim}.')
        return s
    if d.tur == 'grf':
        etk = d.etiket.replace('{S}', 'L') + ' / ' + d.etiket.replace('{S}', 'R')
        ek = {
            'V': M('dikey bileşen = laboratuvar Z ekseni (yukarı +)', 'vertical = lab Z axis (up +)'),
            'AP': M('ön-arka bileşen = yürüme yönüne en yakın yatay laboratuvar ekseni (pelvis markerlarının trial boyunca '
                    'yer değiştirmesinden bulunur), yürüme yönü + (itme +, frenleme −)',
                    'anterior-posterior = horizontal lab axis closest to the walking direction (from pelvis marker '
                    'displacement over the trial), walking direction + (propulsion +, braking −)'),
            'ML': M('medio-lateral bileşen = diğer yatay eksen, her tarafta medial + olacak şekilde çevrilir',
                    'medio-lateral = the other horizontal axis, flipped so that medial is + on each side'),
        }.get(b.kod, b.kod)
        return M(f'C3D point "{etk}" ({taraf}, N/kg); {ek}. Bu tarafın stance\'i dışında ve temasın başındaki/sonundaki boş '
                 f'kareler 0 (temas yok) sayılır; stance içindeki boşluklar doldurulmaz.',
                 f'C3D point "{etk}" ({taraf}, N/kg); {ek}. Outside this side\'s stance, and empty frames at the start/end of '
                 f'contact, are set to 0 (no contact); gaps inside stance are not filled.')
    if d.tur == 'turetilmis':
        return M('TOE markerının yüksekliği (mm): trial içindeki stance ortası (%25–50 stance) TOE noktalarından en küçük '
                 'kareler ile kurulan, taraf ofsetli eğik zemin düzlemine dik uzaklık.',
                 'TOE marker height (mm): perpendicular distance to an inclined floor plane fitted by least squares to the '
                 'TOE positions in mid-stance (25–50% stance) of the trial, with a per-side offset.')
    if d.tur == 'emg':
        e = ayar.emg
        return M(f'Kas "{_(d.ad)}" ({taraf}) için EMG eşleştirmesinde seçilen analog kanal; µV\'ye çevrilir. İşleme: '
                 f'{e.zincir_metni()}. Ham sinyalde ≥ {e.kayip_min_ms:g} ms aynı kalan örnek dizileri (kablosuz paket '
                 f'kaybı) veri kaybı sayılır; zarfın bu bölgeyi kullanan kısmı (RMS penceresinin yarısı + 10 ms genişletilerek) '
                 f'boş bırakılır.',
                 f'The analog channel mapped to muscle "{_(d.ad)}" ({taraf}) in the EMG mapping; converted to µV. '
                 f'Processing: {e.zincir_metni()}. Runs of identical raw samples ≥ {e.kayip_min_ms:g} ms (wireless packet '
                 f'loss) are treated as data loss; envelope samples depending on them (widened by half the RMS window + '
                 f'10 ms) are left empty.')
    if d.tur == 'zu':
        return M(f'{_(d.ad)}: {_(d.aciklama) or "event zamanları ve markerlardan"}.',
                 f'{_(d.ad)}: {_(d.aciklama) or "from event times and markers"}.')
    if d.tur == 'faz':
        k = d.id[4:]
        eklem, var_id, isaret, bas, son, ack = V.FAZLAR[k]
        dv = V.bul(var_id)
        etk = dv.etiket.replace('{S}', 'L') + ' / ' + dv.etiket.replace('{S}', 'R')
        return M(f'C3D point "{etk}" Z bileşeni (sagittal güç, W/kg). Faz {k} ({_(ack)}): arama penceresi '
                 f'{capa_metni({"olay": bas} if bas in ("IC", "CFO", "CIC", "FO", "NIC") else {"ozel": bas})} → '
                 f'{capa_metni({"olay": son} if son in ("IC", "CFO", "CIC", "FO", "NIC") else {"ozel": son})}; pencerede '
                 f'{"en büyük pozitif" if isaret > 0 else "en büyük negatif"} örnek fazın tepesidir. Faz sınırları, tepeyi '
                 f'içeren aynı işaretli bölgenin sıfır geçişleridir (komşu kareler arasında doğrusal interpolasyon).',
                 f'C3D point "{etk}" Z component (sagittal power, W/kg). Phase {k} ({_(ack)}): search window '
                 f'{capa_metni({"olay": bas} if bas in ("IC", "CFO", "CIC", "FO", "NIC") else {"ozel": bas})} → '
                 f'{capa_metni({"olay": son} if son in ("IC", "CFO", "CIC", "FO", "NIC") else {"ozel": son})}; the '
                 f'{"largest positive" if isaret > 0 else "largest negative"} sample in the window is the phase peak. Phase '
                 f'boundaries are the zero crossings of the same-sign region containing the peak (linear interpolation '
                 f'between frames).')
    return _(d.ad)


def _istatistik(q, ist, d) -> str:
    zb = q.zaman_birimi
    zmet = _(ZAMAN_BIRIMLERI.get(zb, zb)) if ist and ist.tur in ('zaman', 'emg_zaman') else ''
    zform = {
        '%GC': '100 × (t − IC) / (sonraki IC − IC)', '%ST': '100 × (t − IC) / (FO − IC)',
        '%SW': '100 × (t − FO) / (sonraki IC − FO)', '%AR': '100 × (t − t0) / (t1 − t0)',
        's': 't − IC', 'ms_ar': '1000 × (t − t0)',
    }.get(zb, '')
    if M('', 'x') == 'x':
        zform = zform.replace('sonraki IC', 'next IC')
    zaman = M(f' Zaman birimi: {zmet} = {zform}.', f' Time unit: {zmet} = {zform}.') if zform else ''
    sinir = M(' Değer aralığın ilk ya da son örneğindeyse Uyarılar sayfasına "gerçek bir tepe olmayabilir" notu yazılır.',
              ' If the value is at the first or last sample of the window, a "may not be a true peak" note is written to '
              'the Warnings sheet.')
    yum = (q.par or {}).get('yumusatma_ms')
    yum_m = M(f' Tepe aranmadan önce eğri {yum:g} ms hareketli ortalama ile yumuşatılır.',
              f' Before searching, the curve is smoothed with a {yum:g} ms moving average.') if yum else ''
    def ilk_lob(poz):
        return M(f'Aralık baştan sona taranır; eğrinin sıfır geçişleriyle ayrılan ilk {"pozitif" if poz else "negatif"} '
                 f'bölgesi (lob) bulunur. Süresi eşikten kısa loblar atlanır (eşik: Yöntem sayfası, "Lob istatistikleri"; '
                 f'lob süresi sıfır geçişleri arasında doğrusal interpolasyonla ölçülür). Aralıkta böyle bir lob yoksa '
                 f'değer boş kalır. Lob aralığın ilk ya da son örneğine dayanıyorsa Uyarılar sayfasına not yazılır.',
                 f'The window is scanned from start to end; the first {"positive" if poz else "negative"} region (lobe) '
                 f'separated by zero crossings of the curve is found. Lobes shorter than the threshold are skipped '
                 f'(threshold: Methods sheet, "Lobe statistics"; lobe duration is measured between zero crossings by '
                 f'linear interpolation). If there is no such lobe in the window the value is empty. If the lobe touches '
                 f'the first or last sample of the window, a note is written to the Warnings sheet.')
    t = {
        'deger': M('Seçilen andaki değer (an iki kare arasındaysa komşu karelerden doğrusal interpolasyon).',
                   'Value at the selected instant (linear interpolation between neighbouring frames).'),
        'bas': M('Aralığın başındaki değer.', 'Value at the start of the window.'),
        'son': M('Aralığın sonundaki değer.', 'Value at the end of the window.'),
        'ort': M('Zamana göre ağırlıklı ortalama = ∫ x dt / (t1 − t0), integral yamuk kuralıyla.',
                 'Time-weighted mean = ∫ x dt / (t1 − t0), integral by the trapezoidal rule.'),
        'ss': M('Aralıktaki örneklerin standart sapması (ddof = 0).', 'Standard deviation of the samples in the window (ddof = 0).'),
        'max': M('Aralıktaki en büyük örnek.', 'Largest sample in the window.') + sinir,
        'min': M('Aralıktaki en küçük örnek.', 'Smallest sample in the window.') + sinir,
        'rom': M('Aralıktaki en büyük örnek − en küçük örnek.', 'Largest − smallest sample in the window.'),
        'tmax': M('En büyük örneğin zamanı.', 'Time of the largest sample.') + yum_m + zaman + sinir,
        'tmin': M('En küçük örneğin zamanı.', 'Time of the smallest sample.') + yum_m + zaman + sinir,
        'absmax': M('Mutlak değeri en büyük örnek, işaretiyle.', 'Sample with the largest absolute value, with its sign.') + sinir,
        'max_bas': M('En büyük örnek − aralık başındaki değer.', 'Largest sample − value at window start.'),
        'min_bas': M('En küçük örnek − aralık başındaki değer.', 'Smallest sample − value at window start.'),
        'sapma': M('Her örnekten aralık başındaki değer çıkarılır; mutlak değeri en büyük fark işaretiyle alınır. İki yönde '
                   'benzer büyüklükte sapma varsa işaret küçük değişikliklerle dönebilir.',
                   'The window-start value is subtracted from each sample; the difference with the largest absolute value '
                   'is taken with its sign. If deviations in both directions are similar, the sign can flip with small '
                   'changes.'),
        'alan_poz': M('∫ max(x, 0) dt (yamuk kuralı); negatif kısımlar 0 sayılır.',
                      '∫ max(x, 0) dt (trapezoidal rule); negative parts are set to 0.'),
        'alan_neg': M('∫ min(x, 0) dt (yamuk kuralı); pozitif kısımlar 0 sayılır, sonuç negatiftir.',
                      '∫ min(x, 0) dt (trapezoidal rule); positive parts are set to 0, the result is negative.'),
        'alan_net': M('∫ x dt (yamuk kuralı).', '∫ x dt (trapezoidal rule).'),
        'lob_poz': M('Sıfır geçişleriyle ayrılan pozitif bölgelerin her birinin alanı (yamuk kuralı) hesaplanır; en büyüğü alınır.',
                     'The area of each positive region separated by zero crossings is computed (trapezoidal rule); the '
                     'largest is taken.'),
        'lob_neg': M('Sıfır geçişleriyle ayrılan negatif bölgelerin her birinin alanı (yamuk kuralı) hesaplanır; mutlak '
                     'değeri en büyük olan alınır (sonuç negatiftir).',
                     'The area of each negative region separated by zero crossings is computed (trapezoidal rule); the '
                     'one with the largest absolute value is taken (the result is negative).'),
        'ilk_lob_poz': ilk_lob(True) + M(' Bu lobun alanı (yamuk kuralı) alınır.', ' The area of this lobe (trapezoidal rule) is taken.'),
        'ilk_lob_poz_max': ilk_lob(True) + M(' Bu lobun içindeki en büyük örnek alınır.', ' The largest sample within this lobe is taken.'),
        'ilk_lob_poz_tmax': ilk_lob(True) + M(' Bu lobun içindeki en büyük örneğin zamanı alınır.',
                                              ' The time of the largest sample within this lobe is taken.') + zaman,
        'ilk_lob_neg': ilk_lob(False) + M(' Bu lobun alanı (yamuk kuralı) alınır; sonuç negatiftir.',
                                          ' The area of this lobe (trapezoidal rule) is taken; the result is negative.'),
        'ilk_lob_neg_min': ilk_lob(False) + M(' Bu lobun içindeki en küçük örnek alınır.', ' The smallest sample within this lobe is taken.'),
        'ilk_lob_neg_tmin': ilk_lob(False) + M(' Bu lobun içindeki en küçük örneğin zamanı alınır.',
                                               ' The time of the smallest sample within this lobe is taken.') + zaman,
        'egim_max': M('Örnekler arası türev (numpy.gradient, merkezi fark) hesaplanır; en büyük değer alınır.',
                      'The derivative between samples (numpy.gradient, central differences) is computed; the largest '
                      'value is taken.'),
        'egim_min': M('Örnekler arası türev (numpy.gradient, merkezi fark) hesaplanır; en küçük değer alınır.',
                      'The derivative between samples (numpy.gradient, central differences) is computed; the smallest '
                      'value is taken.'),
        'tepe2': M(f'Aralık ikiye bölünür; ilk yarının en büyüğü 1. tepe, ikinci yarının en büyüğü (son %'
                   f'{100 * float((q.par or {}).get("son_atla", 0.05)):g} hariç) 2. tepedir. 2. tepe ±3 örnekte yerel '
                   f'maksimum değilse ya da iki tepe arasındaki vadi her iki tepeden en az '
                   f'{(q.par or {}).get("vadi_esik", "tepe genliğinin %3\'ü")} daha düşük değilse değer boş kalır.',
                   f'The window is split in half; the maximum of the first half is peak 1, the maximum of the second half '
                   f'(excluding the last {100 * float((q.par or {}).get("son_atla", 0.05)):g}%) is peak 2. If peak 2 is not '
                   f'a local maximum within ±3 samples, or the valley between the peaks is not at least '
                   f'{(q.par or {}).get("vadi_esik", "3% of the peak amplitude")} below both peaks, the value is empty.'),
        'sure': M('Aralığın süresi (t1 − t0).', 'Duration of the window (t1 − t0).') + (
            M(f' Birim: {_(SURE_BIRIMLERI.get(zb, zb))}.', f' Unit: {_(SURE_BIRIMLERI.get(zb, zb))}.')),
        'onset': M('Aralıktaki ilk aktif bölgenin başlangıcı (aktivasyon tanımı aşağıda).',
                   'Start of the first active region in the window (activation definition below).') + zaman,
        'offset': M('Aralıktaki son aktif bölgenin bitişi (aktivasyon tanımı aşağıda).',
                    'End of the last active region in the window (activation definition below).') + zaman,
        'aktif_ms': M('Aralık içindeki aktif örneklerin toplam süresi (ms).', 'Total duration of active samples in the window (ms).'),
        'aktif_yuzde': M('Aktif süre / aralık süresi × 100.', 'Active duration / window duration × 100.'),
        'aktif_basta': M('Aralığın ilk örneği aktifse 1, değilse 0.', '1 if the first sample of the window is active, else 0.'),
        'aktif_sonda': M('Aralığın son örneği aktifse 1, değilse 0.', '1 if the last sample of the window is active, else 0.'),
        'mdf': M('Aralıktaki filtrelenmiş ham EMG\'nin Hann pencereli periodogramı; filtre bandı içinde gücün yarısının '
                 'altında kaldığı frekans (medyan frekans).',
                 'Hann-windowed periodogram of the filtered raw EMG in the window; the frequency below which half of the '
                 'power within the filter band lies (median frequency).'),
        'mnf': M('Aralıktaki filtrelenmiş ham EMG\'nin Hann pencereli periodogramı; filtre bandı içinde güç ağırlıklı '
                 'ortalama frekans.',
                 'Hann-windowed periodogram of the filtered raw EMG in the window; power-weighted mean frequency within '
                 'the filter band.'),
        'mdf_egim': M('Trial içindeki her döngünün MDF değeri, döngünün IC zamanına karşı doğrusal regresyonla '
                      'uydurulur; eğim (Hz/s) alınır.',
                      'Each cycle\'s MDF in the trial is regressed linearly on the cycle\'s IC time; the slope (Hz/s) '
                      'is taken.'),
        'cci': M(f'Falconer–Winter: 200 × ∫ min(EMG1, EMG2) dt / ∫ (EMG1 + EMG2) dt. İkinci kas: '
                 f'{(q.par or {}).get("kas2", "?")}. Normalizasyon referansı varsa her kas kendi referansına bölünür.',
                 f'Falconer–Winter: 200 × ∫ min(EMG1, EMG2) dt / ∫ (EMG1 + EMG2) dt. Second muscle: '
                 f'{(q.par or {}).get("kas2", "?")}. If normalization references exist, each muscle is divided by its own.'),
        'tepe': M('Fazın tepe değeri (yukarıda tanımlı).', 'Phase peak value (defined above).'),
        'tepe_zamani': M('Faz tepesinin zamanı.', 'Time of the phase peak.') + zaman,
        'is': M('Faz sınırları arasındaki güç eğrisinin integrali (yamuk kuralı, J/kg).',
                'Integral of the power curve between the phase boundaries (trapezoidal rule, J/kg).'),
        'faz_bas': M('Fazın başlangıç sıfır geçişi.', 'Phase start zero crossing.') + zaman,
        'faz_son': M('Fazın bitiş sıfır geçişi.', 'Phase end zero crossing.') + zaman,
        'faz_sure': M('Faz bitişi − faz başlangıcı.', 'Phase end − phase start.'),
    }.get(q.ist)
    return t or _(ist.ad if ist else q.ist)


def algoritma_tablosu(snc: Sonuc, ayar: Ayarlar, sutunlar: list) -> pd.DataFrame:
    ref_adlari = {r.id: r.ad for r in snc.refler}
    dg = ayar.dongu
    e = ayar.emg
    rows = []
    for col, q, tur, birim in sutunlar:
        d = V.bul(q.degisken, ayar.kas_adlari)
        if d is None:
            continue
        b = V.bilesen(d, q.bilesen) if d.bilesenler else None
        ist = IST.get(q.ist) or FAZ_IST.get(q.ist)
        duzey = sorgu_duzeyi(q)
        adimlar = []

        def ekle(baslik, metin):
            adimlar.append((baslik, metin))

        ekle(M('Kaynak sinyal', 'Source signal'), _kaynak(d, b, q, ayar))
        if duzey == 'trial':
            ekle(M('Hesap', 'Computation'), M('Trial başına tek değer (iki taraf birlikte).', 'One value per trial (both sides).'))
        else:
            ekle(M('Döngü', 'Cycle'), M(
                f'Aynı tarafın IC\'sinden bir sonraki IC\'sine. FO, karşı FO ve karşı IC döngünün içinden alınır. Stride '
                f'< {dg.min_stride:g} s ya da kaydın dışına taşan döngü geçersizdir. Event zamanları '
                + ('en yakın kareye yuvarlanır.' if dg.kareye_yuvarla else 'saniye olarak kullanılır (kareye yuvarlanmaz).')
                + ('' if d.tur not in ('kinetik', 'grf', 'faz') else
                   f' Kinetik değişkenler yalnızca bu tarafın stance\'inde GRF büyüklüğü > {dg.kinetik_esik:g} N/kg olan '
                   f'(kuvvet plakasına basılan) döngülerde hesaplanır.'),
                f'From an IC to the next IC of the same side. FO, opposite FO and opposite IC are taken from within the '
                f'cycle. Cycles with stride < {dg.min_stride:g} s or extending beyond the recording are invalid. Event times '
                + ('are rounded to the nearest frame.' if dg.kareye_yuvarla else 'are used in seconds (not rounded to frames).')
                + ('' if d.tur not in ('kinetik', 'grf', 'faz') else
                   f' Kinetic variables are computed only in cycles where the GRF magnitude exceeds {dg.kinetik_esik:g} N/kg '
                   f'during this side\'s stance (force plate contact).')))
        if q.aralik and duzey != 'trial' and d.tur not in ('zu', 'faz'):
            a = snc.araliklar.get(q.aralik)
            if a is not None:
                if a.an_mi:
                    metin = M(f'An: {_(a.ad)} = {_capa_aciklama(a.bas, ref_adlari)}.',
                              f'Instant: {_(a.ad)} = {_capa_aciklama(a.bas, ref_adlari)}.')
                else:
                    metin = M(f'{_(a.ad)}. Başlangıç t0 = {_capa_aciklama(a.bas, ref_adlari)}. Bitiş t1 = '
                              f'{_capa_aciklama(a.son, ref_adlari)}.',
                              f'{_(a.ad)}. Start t0 = {_capa_aciklama(a.bas, ref_adlari)}. End t1 = '
                              f'{_capa_aciklama(a.son, ref_adlari)}.')
                    metin += M(' Aralık t0 ile t1 arasındaki tüm kareleri içerir; t0 ve t1 iki kare arasına düşüyorsa uçtaki '
                               'değerler komşu karelerden doğrusal interpolasyonla eklenir.' if not dg.kareye_yuvarla else
                               ' Aralık t0 ile t1 arasındaki tüm kareleri içerir (uçlar dahil).',
                               ' The window contains all frames between t0 and t1; if t0 or t1 falls between frames, the '
                               'end values are added by linear interpolation from neighbouring frames.' if not dg.kareye_yuvarla
                               else ' The window contains all frames between t0 and t1 (inclusive).')
                ekle(M('Aralık', 'Window'), metin)
                gorulen = set()
                for c in (a.bas, a.son):
                    if 'ref' in c and c['ref'] not in gorulen:
                        gorulen.add(c['ref'])
                        r = next((x for x in snc.refler if x.id == c['ref']), None)
                        if r is not None:
                            rv = V.bul(r.degisken, ayar.kas_adlari)
                            ra = snc.araliklar.get(r.aralik)
                            ekle(M('Referans an', 'Reference instant'), M(
                                f'"{_(r.ad)}": {_(rv.ad) if rv else r.degisken} ({r.bilesen or ""}) eğrisinin '
                                f'{_(ra.ad) if ra else r.aralik} içindeki {"en büyük" if r.ekstremum == "max" else "en küçük"} '
                                f'örneğinin zamanı' + (f' ({r.yumusatma_ms:g} ms yumuşatma sonrası)' if r.yumusatma_ms else '') + '.',
                                f'"{_(r.ad)}": time of the {"largest" if r.ekstremum == "max" else "smallest"} sample of '
                                f'{_(rv.ad) if rv else r.degisken} ({r.bilesen or ""}) within {_(ra.ad) if ra else r.aralik}'
                                + (f' (after {r.yumusatma_ms:g} ms smoothing)' if r.yumusatma_ms else '') + '.'))
                        elif c['ref'].startswith('FAZ:'):
                            ekle(M('Referans an', 'Reference instant'), M(
                                f'{c["ref"][4:]} güç fazının tepe anı (faz tanımı için değişken sözlüğüne bakın).',
                                f'Peak time of power phase {c["ref"][4:]} (see the variable dictionary for the phase definition).'))
        if d.tur != 'zu':
            ekle(M('İstatistik', 'Statistic'), _istatistik(q, ist, d))
        if d.tur == 'emg' and q.ist in ('onset', 'offset', 'aktif_ms', 'aktif_yuzde', 'aktif_basta', 'aktif_sonda'):
            ekle(M('Aktivasyon', 'Activation'), M(
                f'Eşik = trial\'ın analiz bölgesindeki (ilk IC → bu tarafın son IC\'si) en sessiz {e.sessiz_ms:g} ms penceresinin ortalaması + {e.esik_sd:g} SD (en az tepe '
                f'zarfın %{100 * e.esik_taban_tepe:g}\'i). Eşiğin üstünde ≥ {e.min_aktif_ms:g} ms kalan bölgeler aktiftir; '
                f'< {e.birlestir_ms:g} ms boşluklar birleştirilir.',
                f'Threshold = mean of the quietest {e.sessiz_ms:g} ms window in the trial\'s analysis region (first IC → this side\'s last IC) + {e.esik_sd:g} SD (at least '
                f'{100 * e.esik_taban_tepe:g}% of the peak envelope). Regions above threshold for ≥ {e.min_aktif_ms:g} ms are '
                f'active; gaps < {e.birlestir_ms:g} ms are merged.'))
        if d.tur not in ('zu', 'faz'):
            ekle(M('Eksik veri', 'Missing data'), M(
                'Aralıkta eksik örnek varsa (marker boşluğu, stance içi GRF boşluğu, EMG veri kaybı) değer boş bırakılır ve '
                'Uyarılar sayfasına yazılır.' if ayar.eksik_veri == 'bos' or d.tur == 'emg' else
                'Aralıkta eksik örnek varsa değer mevcut örneklerle hesaplanır ve Uyarılar sayfasına yazılır.',
                'If samples are missing in the window (marker gap, GRF gap within stance, EMG data loss) the value is left '
                'empty and reported on the Warnings sheet.' if ayar.eksik_veri == 'bos' or d.tur == 'emg' else
                'If samples are missing in the window, the value is computed from the available samples and reported on '
                'the Warnings sheet.'))
        if tur == 'norm':
            ekle(M('Normalizasyon', 'Normalization'), {
                'mvic': M('Değer / MVIC × 100. MVIC: hasta-tarih-kas-taraf için girilen, yürüyüşle aynı zincirle işlenmiş '
                          'MVIC zarf tepesi (µV; 11_EMG_Referanslari sayfası).',
                          'Value / MVIC × 100. MVIC: the value entered per patient-date-muscle-side, the envelope peak of the '
                          'MVIC trial processed with the same chain (µV; sheet 11_EMG_References).'),
                'dinamik_tepe': M('Değer / referans × 100. Referans: aynı hasta-tarih-taraf için dışlanmamış döngülerin tüm '
                                  'döngü zarf tepelerinin ortalaması.',
                                  'Value / reference × 100. Reference: mean of the whole-cycle envelope peaks of the '
                                  'non-excluded cycles of the same patient-date-side.'),
                'dinamik_ort': M('Değer / referans × 100. Referans: aynı hasta-tarih-taraf için dışlanmamış döngülerin tüm '
                                 'döngü zarf ortalamalarının ortalaması.',
                                 'Value / reference × 100. Reference: mean of the whole-cycle envelope means of the '
                                 'non-excluded cycles of the same patient-date-side.'),
            }.get(e.normalizasyon, ''))
        if duzey == 'trial':
            ekle(M('Birleştirme', 'Aggregation'), M(
                'Trial değerleri (3b_Trial_Hiz_Kadans) → hasta + tarih ortalaması (1_Hasta_Duzeyi, formülle bağlı).',
                'Trial values (3b_Trial_Speed_Cadence) → patient + date mean (1_Patient_Level, linked by formula).'))
        elif duzey == 'trial_taraf':
            ekle(M('Birleştirme', 'Aggregation'), M('Trial-taraf değerleri → hasta + tarih + taraf ortalaması.',
                                                    'Trial-side values → patient + date + side mean.'))
        else:
            ekle(M('Birleştirme', 'Aggregation'), M(
                'Her döngünün değeri 4_Tum_Donguler sayfasındadır. Dislandi = 0 olan döngülerin düz ortalaması alınır: trial '
                'ortalaması (3_Trial_Ortalamalari) ve '
                + ('hasta + tarih + taraf ortalaması (1_Hasta_Duzeyi; tüm döngüler eşit ağırlıklı). '
                   if ayar.ortalama_yontemi == 'dongu' else
                   'hasta + tarih + taraf için trial ortalamalarının ortalaması (1_Hasta_Duzeyi). ')
                + 'Bu sayfalar döngü sayfasına formülle bağlıdır; döngü sayfasında bir değeri değiştirince ya da Dislandi\'yi '
                  '1 yapınca ortalamalar güncellenir.',
                'Each cycle\'s value is on sheet 4_All_Cycles. The plain mean of cycles with Excluded = 0 is taken: trial '
                'mean (3_Trial_Means) and '
                + ('patient + date + side mean (1_Patient_Level; all cycles weighted equally). '
                   if ayar.ortalama_yontemi == 'dongu' else
                   'the mean of trial means per patient + date + side (1_Patient_Level). ')
                + 'These sheets are linked to the cycle sheet by formulas; changing a value on the cycle sheet or setting '
                  'Excluded to 1 updates the means.'))
        for i, (bas, metin) in enumerate(adimlar, start=1):
            rows.append({'Sutun': col, 'Adim': i, M('Baslik', 'Topic'): bas, M('Aciklama', 'Description'): metin})
    return pd.DataFrame(rows)


