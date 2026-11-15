"""Uyarı kaydı. Program veriyi düzeltmez; şüpheli her durumu buraya yazar."""
from __future__ import annotations

from dataclasses import dataclass, asdict

HATA, UYARI, BILGI = 'Hata', 'Uyarı', 'Bilgi'
TARAF_TR = {'L': 'Sol', 'R': 'Sağ', None: '-', '-': '-', '': '-'}


@dataclass
class Uyari:
    dosya: str
    taraf: str          # 'L', 'R' ya da '-'
    dongu: object       # 1 tabanlı döngü numarası ya da '-'
    kod: str            # sorgu kodu ya da kategori (EVENT, GRF, EMG, DOSYA ...)
    onem: str           # Hata / Uyarı / Bilgi
    mesaj: str
    kategori: str = ''

    def satir(self) -> dict:
        d = asdict(self)
        d['taraf'] = TARAF_TR.get(self.taraf, self.taraf)
        return d


class UyariListesi(list):
    def ekle(self, dosya, taraf, dongu, kod, onem, mesaj, kategori=''):
        self.append(Uyari(dosya, taraf or '-', dongu if dongu is not None else '-', kod, onem, mesaj, kategori))
