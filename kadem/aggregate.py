"""Sonuçların birleştirilmesi: EMG normalizasyonu, döngü → trial → hasta ortalamaları, simetri, uç değerler."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import variables as V
from .engine import Sonuc, Sorgu, Ayarlar, hasta_anahtari, mvic_anahtari
from .intervals import seri
from .stats import IST, FAZ_IST, GENLIK_ISTATISTIKLERI
from .model import ascii_ad

TARAF_ADI = {'L': 'Sol', 'R': 'Sağ'}
NORM_EK = {'mvic': '_pctMVIC', 'dinamik_tepe': '_pctDynPeak', 'dinamik_ort': '_pctDynMean'}


# ---------------------------------------------------------------------------------
# Sütun tanımları
# ---------------------------------------------------------------------------------
def birim(q: Sorgu, kas_adlari=None) -> str:
    d = V.bul(q.degisken, kas_adlari)
    if d is None:
        return ''
    ist = IST.get(q.ist) or FAZ_IST.get(q.ist)
    if ist is None:
        return d.birim
    if d.tur == 'faz':
        if q.ist == 'is':
            return 'J/kg'
        if ist.tur == 'zaman':
            return q.zaman_birimi
        if ist.tur == 'sure':
            return q.zaman_birimi
        return d.birim
    if ist.tur in ('deger', 'an'):
        return d.birim
    if ist.tur in ('zaman', 'emg_zaman'):
        return q.zaman_birimi
    if ist.tur == 'sure':
        return q.zaman_birimi
    if ist.tur == 'alan':
        return {'W/kg': 'J/kg'}.get(d.birim, f'{d.birim}·s')
    if ist.tur == 'egim':
        return f'{d.birim}/s'
    if q.ist in ('mdf', 'mnf'):
        return 'Hz'
    if q.ist == 'mdf_egim':
        return 'Hz/s'
    if q.ist == 'aktif_ms':
        return 'ms'
    if q.ist in ('aktif_yuzde', 'cci'):
        return '%'
    if q.ist in ('aktif_basta', 'aktif_sonda'):
        return '0/1'
    return d.birim


def emg_genlik_mi(q: Sorgu) -> bool:
    return q.degisken.startswith('EMG:') and q.ist in GENLIK_ISTATISTIKLERI


def sorgu_duzeyi(q: Sorgu) -> str:
    d = V.bul(q.degisken)
    if d is not None and d.tur == 'zu' and d.duzey == 'trial':
        return 'trial'
    if q.ist == 'mdf_egim':
        return 'trial_taraf'
    return 'dongu'


def cikti_sutunlari(sorgular: list, ayar: Ayarlar) -> list:
    """Her sorgunun çıktı sütunları: [(sütun, sorgu, tür ['ham'|'norm'|'deger'], birim)]."""
    out = []
    norm = ayar.emg.normalizasyon
    for q in sorgular:
        b = birim(q, ayar.kas_adlari)
        if emg_genlik_mi(q):
            if norm == 'yok' or ayar.emg.ham_uv_yaz:
                out.append((f'{q.kod}_uV', q, 'ham', b.replace('µV', 'µV')))
            if norm != 'yok':
                nb = b.replace('µV', '%')
                out.append((f'{q.kod}{NORM_EK[norm]}', q, 'norm', nb))
        else:
            out.append((q.kod, q, 'deger', b))
    return out


# ---------------------------------------------------------------------------------
# EMG normalizasyonu
# ---------------------------------------------------------------------------------
def emg_referanslari(snc: Sonuc, df: pd.DataFrame, ayar: Ayarlar) -> dict:
    """(hasta_key, kas, taraf) -> µV. MVIC tablosundan ya da dinamik (döngü tepe/ortalama ortalaması)."""
    norm = ayar.emg.normalizasyon
    if norm == 'mvic':
        return dict(snc.emg_ref)
    if norm not in ('dinamik_tepe', 'dinamik_ort'):
        return {}
    ref = {}
    alan = '_max' if norm == 'dinamik_tepe' else '_mean'
    for c in [c for c in df.columns if c.startswith('_emgref_') and c.endswith(alan)]:
        kas = c[len('_emgref_'):-len(alan)]
        g = df[df['Dislandi'] == 0].groupby(['Hasta', 'Tarih', 'Taraf'])[c].mean()
        for (h, t, s), v in g.items():
            if np.isfinite(v) and v > 0:
                ref[(hasta_anahtari(h, t), kas, s)] = float(v)
                snc.emg_ref_kaynak[(hasta_anahtari(h, t), kas, s)] = 'dinamik'
    return ref


def emg_normalize(df: pd.DataFrame, sorgular: list, ayar: Ayarlar, ref: dict) -> pd.DataFrame:
    norm = ayar.emg.normalizasyon
    if norm == 'yok' or df.empty:
        return df
    keys = [hasta_anahtari(h, t) for h, t in zip(df['Hasta'], df['Tarih'])]
    ek = {}
    for q in sorgular:
        if not emg_genlik_mi(q) or q.kod not in df.columns:
            continue
        kas = q.degisken[4:]
        taraf = df['Taraf'] if q.taraf == 'ipsi' else df['Taraf'].map({'L': 'R', 'R': 'L'})
        r = np.array([ref.get((k, kas, s), np.nan) for k, s in zip(keys, taraf)], float)
        ek[f'{q.kod}{NORM_EK[norm]}'] = df[q.kod].to_numpy(float) / r * 100.0
    if not ek:
        return df
    return pd.concat([df.drop(columns=[c for c in ek if c in df.columns]), pd.DataFrame(ek, index=df.index)], axis=1)


# ---------------------------------------------------------------------------------
# Birleştirme
# ---------------------------------------------------------------------------------
def dongu_tablosu(snc: Sonuc, ayar: Ayarlar, dislamalar: dict | None = None) -> pd.DataFrame:
    df = pd.DataFrame(snc.dongu_satirlari)
    if df.empty:
        return df
    dis = dislamalar or {}
    anahtar = list(zip(df['Dosya'], df['Taraf'], df['Dongu']))
    df['Dislandi'] = [1 if k in dis else 0 for k in anahtar]
    df['Dislama_Nedeni'] = [dis.get(k, '') for k in anahtar]
    df.loc[df['Gecerli'] == 0, 'Dislandi'] = 1
    df.loc[(df['Gecerli'] == 0) & (df['Dislama_Nedeni'] == ''), 'Dislama_Nedeni'] = 'event hatası (döngü geçersiz)'
    ref = emg_referanslari(snc, df, ayar)
    snc.emg_ref.update(ref)
    df = emg_normalize(df, snc.sorgular, ayar, snc.emg_ref)
    return df


def _ortalama(df: pd.DataFrame, grup: list, cols: list):
    if df.empty or not cols:
        return pd.DataFrame(columns=grup + cols)
    g = df.groupby(grup, sort=False)
    m = g[cols].mean()
    return m.reset_index()


def birlestir(snc: Sonuc, ayar: Ayarlar, hasta_bilgi: dict | None = None, dislamalar: dict | None = None) -> dict:
    """Dönüş: tablolar sözlüğü (pandas DataFrame)."""
    hasta_bilgi = hasta_bilgi or {}
    sutunlar = cikti_sutunlari(snc.sorgular, ayar)
    dongu_cols = [c for c, q, tur, b in sutunlar if sorgu_duzeyi(q) == 'dongu']
    trial_cols = [c for c, q, tur, b in sutunlar if sorgu_duzeyi(q) == 'trial']
    trial_taraf_cols = [c for c, q, tur, b in sutunlar if sorgu_duzeyi(q) == 'trial_taraf']

    dd = dongu_tablosu(snc, ayar, dislamalar)
    if not dd.empty:
        ek = {}
        for c, q, tur, b in sutunlar:
            if tur == 'ham' and q.kod in dd.columns:
                ek[c] = dd[q.kod]
        for c in dongu_cols:
            if c not in dd.columns and c not in ek:
                ek[c] = np.nan
        if ek:
            dd = pd.concat([dd.drop(columns=[c for c in ek if c in dd.columns]),
                            pd.DataFrame(ek, index=dd.index)], axis=1)
    kullan = dd[dd['Dislandi'] == 0] if not dd.empty else dd

    # trial düzeyi
    tt = pd.DataFrame(snc.trial_satirlari)
    trial_ort = _ortalama(kullan, ['Hasta', 'Tarih', 'Dosya', 'Taraf'], dongu_cols) if not kullan.empty else pd.DataFrame()
    if not kullan.empty:
        n = kullan.groupby(['Hasta', 'Tarih', 'Dosya', 'Taraf'], sort=False).size().rename('N_Dongu').reset_index()
        nk = kullan.groupby(['Hasta', 'Tarih', 'Dosya', 'Taraf'], sort=False)['Kinetik'].sum().rename('N_Kinetik').reset_index()
        trial_ort = n.merge(nk, on=['Hasta', 'Tarih', 'Dosya', 'Taraf']).merge(trial_ort, on=['Hasta', 'Tarih', 'Dosya', 'Taraf'])

    # hasta düzeyi (taraf bazlı)
    if ayar.ortalama_yontemi == 'trial' and not trial_ort.empty:
        hasta_taraf = _ortalama(trial_ort, ['Hasta', 'Tarih', 'Taraf'], dongu_cols)
    else:
        hasta_taraf = _ortalama(kullan, ['Hasta', 'Tarih', 'Taraf'], dongu_cols)
    if not kullan.empty:
        cnt = kullan.groupby(['Hasta', 'Tarih', 'Taraf'], sort=False).agg(N_Dongu=('Dongu', 'size'), N_Kinetik=('Kinetik', 'sum'),
                                                                         N_Trial=('Dosya', 'nunique')).reset_index()
        hasta_taraf = cnt.merge(hasta_taraf, on=['Hasta', 'Tarih', 'Taraf'], how='left')

    # trial düzeyi sorgular (hız, kadans)
    tt_tr = tt[tt['Taraf'] == '-'] if not tt.empty else tt
    tt_ts = tt[tt['Taraf'] != '-'] if not tt.empty else tt
    hasta_trial = _ortalama(tt_tr, ['Hasta', 'Tarih'], [c for c in trial_cols if c in tt_tr.columns]) if not tt_tr.empty else None
    hasta_trial_taraf = _ortalama(tt_ts, ['Hasta', 'Tarih', 'Taraf'],
                                  [c for c in trial_taraf_cols if c in tt_ts.columns]) if not tt_ts.empty else None

    # geniş tablo
    hastalar = []
    for df_ in (hasta_taraf, hasta_trial, hasta_trial_taraf):
        if df_ is not None and not df_.empty:
            hastalar += list(zip(df_['Hasta'], df_['Tarih']))
    sira = list(dict.fromkeys(hastalar))
    genis = pd.DataFrame(sira, columns=['Hasta', 'Tarih'])
    genis['Etkilenen_Taraf'] = [TARAF_ADI.get((hasta_bilgi.get(hasta_anahtari(h, t)) or {}).get('etkilenen'), '')
                                for h, t in sira]
    if hasta_trial is not None and not hasta_trial.empty:
        genis = genis.merge(hasta_trial, on=['Hasta', 'Tarih'], how='left')
    anahtarlar = list(zip(genis['Hasta'], genis['Tarih']))
    yeni = {}
    taraf_idx = {}
    for s in ('L', 'R'):
        taraf_idx[s] = hasta_taraf[hasta_taraf['Taraf'] == s].set_index(['Hasta', 'Tarih']) \
            if not hasta_taraf.empty else pd.DataFrame()
    for c in dongu_cols:
        for s in ('L', 'R'):
            m = taraf_idx[s]
            yeni[f'{s}_{c}'] = [m[c].get(k, np.nan) for k in anahtarlar] if (not m.empty and c in m.columns) \
                else [np.nan] * len(anahtarlar)
    if hasta_trial_taraf is not None and not hasta_trial_taraf.empty:
        for c in trial_taraf_cols:
            for s in ('L', 'R'):
                m = hasta_trial_taraf[hasta_trial_taraf['Taraf'] == s].set_index(['Hasta', 'Tarih'])[c]
                yeni[f'{s}_{c}'] = [m.get(k, np.nan) for k in anahtarlar]
    # sayılar
    for s in ('L', 'R'):
        m = taraf_idx[s]
        for k in ('N_Dongu', 'N_Kinetik'):
            if not m.empty and k in m.columns:
                yeni[f'{s}_{k}'] = [m[k].get(kk, 0) for kk in anahtarlar]
    genis = pd.concat([genis, pd.DataFrame(yeni, index=genis.index)], axis=1)

    # simetri (etkilenen / sağlam)
    simetri = []
    for c in dongu_cols + trial_taraf_cols:
        if f'L_{c}' not in genis.columns:
            continue
        etk, slm, fark, lsi = [], [], [], []
        for _, r in genis.iterrows():
            e = (hasta_bilgi.get(hasta_anahtari(r['Hasta'], r['Tarih'])) or {}).get('etkilenen')
            if e in ('L', 'R'):
                ve, vs = r[f'{e}_{c}'], r[f'{"R" if e == "L" else "L"}_{c}']
                etk.append(ve); slm.append(vs); fark.append(ve - vs)
                lsi.append(100.0 * ve / vs if np.isfinite(ve) and np.isfinite(vs) and vs != 0 and np.sign(ve) == np.sign(vs)
                           else np.nan)
            else:
                etk.append(np.nan); slm.append(np.nan); fark.append(np.nan); lsi.append(np.nan)
        simetri.append((c, etk, slm, fark, lsi))
    if any(np.isfinite(x).any() for _, e, *_ in simetri for x in [np.array(e, float)]):
        sim = {}
        for c, etk, slm, fark, lsi in simetri:
            sim[f'Etkilenen_{c}'] = etk
            sim[f'Saglam_{c}'] = slm
            sim[f'Fark_{c}'] = fark
            sim[f'LSI_{c}'] = lsi
        genis = pd.concat([genis, pd.DataFrame(sim, index=genis.index)], axis=1)

    # uzun format
    uzun = []
    if not kullan.empty:
        for (h, t, s), g in kullan.groupby(['Hasta', 'Tarih', 'Taraf'], sort=False):
            for c, q, tur, b in sutunlar:
                if c not in g.columns:
                    continue
                x = g[c].to_numpy(float)
                x = x[np.isfinite(x)]
                if not len(x):
                    continue
                ort = float(np.mean(x))
                ss = float(np.std(x, ddof=1)) if len(x) > 1 else np.nan
                uzun.append({'Hasta': h, 'Tarih': t, 'Taraf': TARAF_ADI.get(s, s), 'Degisken': c, 'Birim': b,
                             'Ortalama': ort, 'SS': ss, 'N': len(x),
                             'CV_yuzde': 100 * ss / abs(ort) if np.isfinite(ss) and ort != 0 else np.nan})
    if hasta_trial is not None and not hasta_trial.empty and not tt_tr.empty:
        for (h, t), g in tt_tr.groupby(['Hasta', 'Tarih'], sort=False):
            for c in trial_cols:
                if c not in g.columns:
                    continue
                x = g[c].to_numpy(float); x = x[np.isfinite(x)]
                if not len(x):
                    continue
                ort = float(np.mean(x)); ss = float(np.std(x, ddof=1)) if len(x) > 1 else np.nan
                b = next((bb for cc, q, tur, bb in sutunlar if cc == c), '')
                uzun.append({'Hasta': h, 'Tarih': t, 'Taraf': '-', 'Degisken': c, 'Birim': b, 'Ortalama': ort, 'SS': ss,
                             'N': len(x), 'CV_yuzde': 100 * ss / abs(ort) if np.isfinite(ss) and ort != 0 else np.nan})
    uzun = pd.DataFrame(uzun)

    uc = uc_degerler(kullan, genis, dongu_cols, float(getattr(ayar, 'uc_esik', 5.0) or 5.0))
    return {'genis': genis, 'uzun': uzun, 'trial': trial_ort, 'trial_zu': tt, 'dongu': dd, 'uc': uc,
            'sutunlar': sutunlar, 'hasta_taraf': hasta_taraf}


def uc_degerler(kullan: pd.DataFrame, genis: pd.DataFrame, cols: list, esik: float = 3.5) -> pd.DataFrame:
    """Robust z. Döngü düzeyi: döngünün kendi hasta-taraf medyanından sapması / havuzlanmış ölçek
    (tüm hasta-taraf gruplarındaki sapmaların 1,4826 × medyanı; küçük gruplarda tek grubun MAD'i kararsız olduğu için).
    Hasta düzeyi: hastalar arası medyan ve MAD (n >= 5). Değerler silinmez, yalnızca listelenir."""
    rows = []
    if not kullan.empty:
        gruplar = [g.index.to_numpy() for _, g in kullan.groupby(['Hasta', 'Tarih', 'Taraf'], sort=False)]
        pos = {ix: i for i, ix in enumerate(kullan.index)}
        for c in cols:
            if c not in kullan.columns:
                continue
            x = kullan[c].to_numpy(float)
            sap = np.full(len(x), np.nan)
            ref = np.full(len(x), np.nan)
            for gi in gruplar:
                ii = np.array([pos[k] for k in gi])
                v = x[ii]
                ok = np.isfinite(v)
                if ok.sum() < 3:
                    continue
                for j in np.flatnonzero(ok):
                    diger = v[ok & (np.arange(len(v)) != j)]
                    m = np.median(diger)
                    ref[ii[j]] = m
                    sap[ii[j]] = v[j] - m          # kendisi hariç (leave-one-out) medyandan sapma
            ok = np.isfinite(sap)
            if ok.sum() < 6:
                continue
            olcek = 1.4826 * np.median(np.abs(sap[ok]))
            if not np.isfinite(olcek) or olcek <= 0:
                continue
            z = sap / olcek
            for i in np.flatnonzero(ok & (np.abs(z) > esik)):
                r = kullan.iloc[i]
                rows.append({'Duzey': 'Döngü (aynı hasta-taraftaki diğer döngülere göre)', 'Hasta': r['Hasta'],
                             'Tarih': r['Tarih'], 'Dosya': r['Dosya'], 'Taraf': TARAF_ADI.get(r['Taraf'], r['Taraf']),
                             'Dongu': int(r['Dongu']), 'Degisken': c, 'Deger': x[i], 'Medyan': ref[i], 'Robust_z': z[i]})
    for c in [c for c in genis.columns if c[:2] in ('L_', 'R_') and c[2:] in cols]:
        x = genis[c].to_numpy(float)
        ok = np.isfinite(x)
        if ok.sum() < 5:
            continue
        med = np.median(x[ok]); mad = 1.4826 * np.median(np.abs(x[ok] - med))
        if mad <= 0:
            continue
        z = (x - med) / mad
        for i in np.flatnonzero(ok & (np.abs(z) > esik)):
            rows.append({'Duzey': 'Hasta (hastalar arasında)', 'Hasta': genis['Hasta'].iloc[i], 'Tarih': genis['Tarih'].iloc[i],
                         'Dosya': '', 'Taraf': TARAF_ADI.get(c[0], c[0]), 'Dongu': '', 'Degisken': c[2:], 'Deger': x[i],
                         'Medyan': med, 'Robust_z': z[i]})
    return pd.DataFrame(rows)
