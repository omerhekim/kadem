"""Dil seçimi (Türkçe / English).

- M(tr, en): yeni yazılan metinlerde iki dil yan yana.
- _(metin): Türkçe metnin İngilizce karşılığını sözlükten (ceviri_en.py) bulur; yoksa metni olduğu gibi döndürür.
  Biçimlendirilen metinlerde şablon çevrilir, sonra .format() uygulanır: _('{n} dosya').format(n=3)
Excel sütun adları (değişken kodları, L_/R_ önekleri) dilden bağımsızdır.
"""
from __future__ import annotations

import re

DIL = 'tr'
_EN: dict | None = None
_DESEN: list | None = None
_BELLEK: dict = {}
_OZEL = set('.^$*+?{}[]\\|()/')


def ayarla(dil: str | None):
    global DIL
    DIL = 'en' if (dil or '').lower().startswith('en') else 'tr'
    return DIL


def en_mi() -> bool:
    return DIL == 'en'


def M(tr: str, en: str) -> str:
    return en if DIL == 'en' else tr


def _kacis(s: str) -> str:
    """Python ve JavaScript'te aynı çalışan düzenli ifade kaçışı."""
    return ''.join('\\' + c if c in _OZEL else c for c in s)


def _sozluk():
    """(birebir sözlük, [(regex kaynağı, derlenmiş regex, ingilizce şablon)])"""
    global _EN, _DESEN
    if _EN is None:
        try:
            from .ceviri_en import EN, DESEN
        except Exception:  # noqa
            EN, DESEN = {}, []
        _EN = dict(EN)
        _DESEN = []
        for tr, en in DESEN:
            if not re.search(r'\{\d+\}', tr):
                _EN.setdefault(tr, en)
                continue
            parca = re.split(r'\{(\d+)\}', tr)
            kaynak = '^' + ''.join(_kacis(x) if i % 2 == 0 else '([\\s\\S]+?)' for i, x in enumerate(parca)) + '$'
            sira = [int(x) for x in parca[1::2]]
            _DESEN.append((kaynak, re.compile(kaynak), en, sira))
    return _EN, _DESEN


def _yerlestir(en: str, gruplar: list) -> str:
    def f(m):
        i = int(m.group(2))
        v = gruplar[i] if i < len(gruplar) else ''
        return cevir(v) if m.group(1) else v
    return re.sub(r'\{(t?)(\d+)\}', f, en)


def cevir(metin: str) -> str:
    """Türkçe metni İngilizceye çevirir (dil seçiminden bağımsız)."""
    if not isinstance(metin, str) or not metin:
        return metin
    if metin in _BELLEK:
        return _BELLEK[metin]
    tam, desen = _sozluk()
    sonuc = tam.get(metin)
    if sonuc is None:
        sonuc = metin
        for _k, rx, en, sira in desen:
            m = rx.match(metin)
            if m:
                g = list(m.groups())
                deg = [''] * (max(sira) + 1)
                for j, n in enumerate(sira):
                    deg[n] = g[j]
                sonuc = _yerlestir(en, deg)
                break
    if len(_BELLEK) < 50000:
        _BELLEK[metin] = sonuc
    return sonuc


def _(metin):
    if DIL != 'en' or not isinstance(metin, str) or not metin:
        return metin
    return cevir(metin)


def js_tablosu() -> dict:
    """Arayüz için: birebir sözlük ve desenler (regex kaynağı, ingilizce şablon, yer tutucu sırası)."""
    tam, desen = _sozluk()
    return {'tam': tam, 'desen': [[k, en, sira] for k, _rx, en, sira in desen]}
