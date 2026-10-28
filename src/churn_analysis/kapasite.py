"""Kapasite sözleşmesi: en fazla yüzde kapasite, tamsayı adet ve iki ayrı seçim anlamı.

Yöntem karşılaştırması, sınırdaki eşit skorlardan rastgele seçim yapılsaydı
yakalanacak ayrılanların beklenen değerini kullanır. Somut liste, skor azalan
ve CustomerId artan sırasını kullanır; seçim fonksiyonu hedef etiketi almaz.
"""

from decimal import Decimal, ROUND_FLOOR
from numbers import Integral, Real

import numpy as np
import pandas as pd


def kapasite_adedi(musteri_sayisi, kapasite):
    """floor(n * yüzde / 100); 0–100 kabul edilir. Ondalık sınırda kayan nokta kaybı yoktur."""
    if isinstance(musteri_sayisi, (bool, np.bool_)) or not isinstance(musteri_sayisi, Integral):
        raise ValueError("Müşteri sayısı negatif olmayan bir tamsayı olmalı.")
    if musteri_sayisi < 0:
        raise ValueError("Müşteri sayısı negatif olamaz.")
    if isinstance(kapasite, (bool, np.bool_)) or not isinstance(kapasite, (Real, Decimal)):
        raise ValueError("Kapasite 0–100 arasında sonlu bir sayı olmalı.")
    yuzde = Decimal(str(kapasite))
    if not yuzde.is_finite() or not Decimal(0) <= yuzde <= Decimal(100):
        raise ValueError("Kapasite 0–100 arasında sonlu bir sayı olmalı.")
    return int((Decimal(int(musteri_sayisi)) * yuzde / 100).to_integral_value(rounding=ROUND_FLOOR))


def skor_dogrula(skor):
    """Geçersiz skorları düşürmek/kırpmak yerine hatayla durur; boş vektöre izin verir."""
    try:
        s = np.asarray(skor, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Skorlar sayısal olmalı.") from exc
    if s.ndim != 1 or not np.isfinite(s).all() or ((s < 0) | (s > 1)).any():
        raise ValueError("Skorlar tek boyutlu, sonlu ve 0–1 arasında olmalı.")
    return s


def hedef_skor_dogrula(y, skor):
    """Hedef ve skor aynı sıradaki müşterilere aittir; indekslere göre örtük eşleştirme yapılmaz."""
    s = skor_dogrula(skor)
    try:
        hedef = np.asarray(y, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Hedef yalnızca 0/1 içermeli.") from exc
    if hedef.ndim != 1 or len(hedef) != len(s) or not np.isin(hedef, [0, 1]).all():
        raise ValueError("Hedef tek boyutlu, skorla aynı uzunlukta ve yalnızca 0/1 olmalı.")
    return hedef, s


def beklenen_yakalama(y, skor, kapasite):
    """Tamsayı k için eşit skorlarda beklenen yakalama; gerçek müşteri listesi değildir.

    Ayrılan yoksa recall; seçilen yoksa precision tanımsızdır (NaN).
    Seçilen/ayrılan sayısı sıfır olduğunda yakalanan adet sıfırdır.
    """
    y, s = hedef_skor_dogrula(y, skor)
    k = kapasite_adedi(len(y), kapasite)
    tablo = pd.DataFrame({"skor": s, "hedef": y}).groupby("skor")["hedef"].agg(["size", "sum"])
    tablo = tablo.sort_index(ascending=False)
    once = tablo["size"].cumsum() - tablo["size"]
    secilen = np.clip(k - once, 0, tablo["size"])
    yakalanan = float((tablo["sum"] * secilen / tablo["size"]).sum())
    return {
        "Bakılan müşteri": k,
        "Eşit skorlarda beklenen ayrılan": yakalanan,
        "Yakalanan pay": yakalanan / y.sum() if y.sum() else np.nan,
        "İsabet": yakalanan / k if k else np.nan,
    }


def liste_secimi(skor, kapasite, musteri_id=None):
    """Somut listenin satır konumlarını ve maskesini döndürür; Exited kullanılmaz.

    Eşit skorlar CustomerId artan sırasıyla çözülür. Kimlik olmadan kesim
    noktasında eşit skor varsa sessizce satır sırasına başvurulmaz, hata verilir.
    Kimliksiz kullanım yalnızca seçilen küme zaten tekil olarak belirliyse uygundur.
    """
    s = skor_dogrula(skor)
    k = kapasite_adedi(len(s), kapasite)
    tablo = pd.DataFrame({"skor": s, "konum": np.arange(len(s))})
    if musteri_id is not None:
        ids = np.asarray(musteri_id)
        if ids.ndim != 1 or len(ids) != len(s):
            raise ValueError("CustomerId skorla aynı uzunlukta, tek boyutlu olmalı.")
        index = pd.Index(ids)
        if index.hasnans or not index.is_unique:
            raise ValueError("CustomerId dolu ve benzersiz olmalı.")
        if pd.api.types.is_numeric_dtype(ids.dtype) and not np.isfinite(ids).all():
            raise ValueError("Sayısal CustomerId sonlu olmalı.")
        tablo["kimlik"] = ids
        try:
            sirali = tablo.sort_values(["skor", "kimlik"], ascending=[False, True])
        except TypeError as exc:
            raise ValueError("CustomerId değerleri ortak bir türde sıralanabilmeli.") from exc
    else:
        sirali = tablo.sort_values("skor", ascending=False, kind="stable")
        if 0 < k < len(s) and sirali["skor"].iloc[k - 1] == sirali["skor"].iloc[k]:
            raise ValueError("Kesim noktasında eşit skor var; somut liste için CustomerId gerekli.")
    konumlar = sirali["konum"].to_numpy(dtype=int)[:k]
    maske = np.zeros(len(s), dtype=bool)
    maske[konumlar] = True
    return konumlar, maske


def sira_ve_dilim(skor, musteri_id):
    """Dışa aktarılan skorlar için aynı seçimden sıra ve %10/%20/%30 dilimleri.

    Power BI'a altı ondalıklı skor aktarılıyorsa bu fonksiyona da aynı
    hassasiyette skor verilmelidir; sıralama ile panel eşitlikleri uyuşur.
    """
    konumlar, _ = liste_secimi(skor, 100, musteri_id)
    n = len(konumlar)
    sira = np.empty(n, dtype=int)
    sira[konumlar] = np.arange(1, n + 1)
    dilim = np.full(n, "Diğer", dtype=object)
    for alt, ust, etiket in [(0, 10, "İlk %10"), (10, 20, "%10–20"), (20, 30, "%20–30")]:
        dilim[(sira > kapasite_adedi(n, alt)) & (sira <= kapasite_adedi(n, ust))] = etiket
    return sira, dilim
