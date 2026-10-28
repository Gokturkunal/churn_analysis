"""Power BI Sayfa 4 (Model Güvenilirliği) için son test özet tabloları.

Kaynak: notebooks/02_ml.ipynb Bölüm 8–9 çıktıları (reports/ml/08_*.csv, 09_*.csv). Değerler yeniden hesaplanmaz,
yalnızca Power BI'ın okuyacağı sade biçime (Türkçe sütun adları, 0–100 yüzdeler, sıra sütunları) dönüştürülür.
Bu tablolar son testin sabit sonucudur; filtrelerden etkilenmez.
"""

from pathlib import Path

import pandas as pd

YONTEM_ADI = {
    "Random Forest · aktifliksiz (ana model)": ("Model (ana)", 1),
    "Gradient Boosting · aktifliksiz": ("Gradient boosting", 2),
    "Lojistik regresyon · aktifliksiz": ("Lojistik regresyon", 3),
    "Segment kuralı · aktifliksiz": ("Segment kuralı", 4),
    "Random Forest · aktiflikli": ("Model, aktiflikli (sızıntı şüphesi)", 5),
    "Segment kuralı · aktiflikli": ("Segment kuralı, aktiflikli", 6),
    "Dummy": ("Rastgele seçim", 7),
}
GRUP_SIRASI = {"Kadın": 1, "Erkek": 2, "Fransa": 1, "Almanya": 2, "İspanya": 3,
               "18–39": 1, "40–49": 2, "50–59": 3, "60–69": 4, "70+": 5,
               "1 ürün": 1, "2 ürün": 2, "3+ ürün": 3, "Aktif değil": 1, "Aktif": 2, "Sıfır": 1, "Pozitif": 2}
DEGISKEN_SIRASI = {"Cinsiyet": 1, "Ülke": 2, "Yaş grubu": 3, "Ürün sayısı": 4, "Aktiflik": 5, "Bakiye durumu": 6}


def sayfa4_grup_tablosu(g):
    """Grup sayıları ve belirsizliği için panel aktarımı; oranları 0–100'e çevirir.

    Eski kaynakta yakalanan adet/GA yoksa uydurulmaz, boş bırakılır ve açıkça
    belirtilir. n ve ayrılan eşiğini geçmek 'yüksek güven' olarak adlandırılmaz.
    """
    gerekli = ["Değişken", "Grup", "Müşteri", "Ayrılan", "Ayrılma oranı",
               "Listeye giren müşteri payı", "Yakalanan ayrılan payı"]
    if any(c not in g for c in gerekli):
        raise ValueError(f"Grup tablosunda gerekli sütunlar: {gerekli}")
    n, k = g["Müşteri"], g["Ayrılan"]
    if n.isna().any() or k.isna().any() or ((n < 0) | (k < 0) | (k > n)).any():
        raise ValueError("Müşteri ve ayrılan sayıları geçerli olmalı.")
    ga_var = all(c in g for c in ["Yakalanan ayrılan payı GA alt", "Yakalanan ayrılan payı GA üst"])
    notlar = []
    for ni, ki in zip(n, k):
        notlar_tek = []
        if ni < 100:
            notlar_tek.append("Küçük müşteri grubu (n < 100)")
        if ki == 0:
            notlar_tek.append("Ayrılan yok; yakalama hesaplanamaz")
        elif ki < 30:
            notlar_tek.append("Az ayrılan (k < 30)")
        if not ga_var:
            notlar_tek.append("Aralık bu eski kaynakta yok")
        notlar.append("; ".join(notlar_tek) or "Küçük grup/az olay uyarısı yok; aralığı inceleyin")
    grup = pd.DataFrame({
        "Değişken": g["Değişken"], "Değişken sırası": g["Değişken"].map(DEGISKEN_SIRASI).fillna(999),
        "Grup": g["Grup"], "Grup sırası": g["Grup"].map(GRUP_SIRASI).fillna(999),
        "Müşteri": n, "Ayrılan": k,
        "Listede müşteri": g.get("Listede müşteri", float("nan")),
        "Yakalanan ayrılan": g.get("Yakalanan ayrılan", float("nan")),
        "Kaçırılan ayrılan": g.get("Kaçırılan ayrılan", float("nan")),
        "Ayrılma oranı": (100 * g["Ayrılma oranı"]).round(1),
        "Listeye giren müşteri payı": (100 * g["Listeye giren müşteri payı"]).round(1),
        "Yakalanan ayrılan payı": (100 * g["Yakalanan ayrılan payı"]).round(1),
        "Yakalanan pay GA alt": (100 * g["Yakalanan ayrılan payı GA alt"]).round(1) if ga_var else float("nan"),
        "Yakalanan pay GA üst": (100 * g["Yakalanan ayrılan payı GA üst"]).round(1) if ga_var else float("nan"),
        "Güven notu": notlar,
    }).sort_values(["Değişken sırası", "Grup sırası"])
    return grup


def sayfa4_tablolari(ml_klasoru, cikti_klasoru):
    """İki CSV yazar: test ölçütleri (yöntem başına) ve grup performansı. Yazılan yolları döndürür."""
    ml_klasoru, cikti_klasoru = Path(ml_klasoru), Path(cikti_klasoru)
    cikti_klasoru.mkdir(parents=True, exist_ok=True)
    test = pd.read_csv(ml_klasoru / "08_son_test.csv", encoding="utf-8-sig")
    bt = pd.read_csv(ml_klasoru / "08_son_test_bootstrap.csv", encoding="utf-8-sig")
    t = test.merge(bt, on=["Yöntem", "AP", "%20 kapasitede yakalanan"], how="left")
    fark = "%20 kapasitede yakalanan farkı (Segment kuralı · aktifliksiz)"
    olcut = pd.DataFrame({
        "Yöntem": t["Yöntem"].map(lambda v: YONTEM_ADI[v][0]),
        "Sıra": t["Yöntem"].map(lambda v: YONTEM_ADI[v][1]),
        "AP": t["AP"].round(4),
        "AP GA alt": t["AP GA alt"].round(4),
        "AP GA üst": t["AP GA üst"].round(4),
        "Yakalanan %10": (100 * t["%10 kapasitede yakalanan"]).round(1),
        "Yakalanan %20": (100 * t["%20 kapasitede yakalanan"]).round(1),
        "Yakalanan %20 GA alt": (100 * t["%20 kapasitede yakalanan GA alt"]).round(1),
        "Yakalanan %20 GA üst": (100 * t["%20 kapasitede yakalanan GA üst"]).round(1),
        "Yakalanan %30": (100 * t["%30 kapasitede yakalanan"]).round(1),
        "İsabet %20": (100 * t["%20 kapasitede isabet"]).round(1),
        "Brier": t["Brier"].round(4),
        "Kurala göre fark %20 (puan)": (100 * t[fark]).round(1),
        "Fark GA alt (puan)": (100 * t[f"%20 kapasitede yakalanan farkı GA alt"]).round(1),
        "Fark GA üst (puan)": (100 * t[f"%20 kapasitede yakalanan farkı GA üst"]).round(1),
    }).sort_values("Sıra")

    g = pd.read_csv(ml_klasoru / "09_grup_performansi.csv", encoding="utf-8-sig")
    grup = sayfa4_grup_tablosu(g)

    yol1, yol2 = cikti_klasoru / "sayfa4_test_olcutleri.csv", cikti_klasoru / "sayfa4_grup_performansi.csv"
    # Power BI Türkçe bölge ayarında okur: ondalık virgül, sınırlayıcı noktalı virgül.
    olcut.to_csv(yol1, index=False, encoding="utf-8-sig", sep=";", decimal=",")
    grup.to_csv(yol2, index=False, encoding="utf-8-sig", sep=";", decimal=",")
    return yol1, yol2, olcut, grup
