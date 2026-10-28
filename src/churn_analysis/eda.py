"""Soru odaklı EDA için ortak fonksiyonlar (notebooks/01_eda.ipynb).

Tüm veri üzerinde betimseldir; özellik seçimi veya ML içermez. Testlerin p-değerleri yalnızca referanstır.
Hazırlama, Türkçe etiket haritaları ve sayı biçimi `bivariate_eda.py` içinden yeniden kullanılır.
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, mannwhitneyu, norm

from .bivariate_eda import BLUE, CATEGORICAL, CONTINUOUS, MAPS, NAMES, hazirla, tr_sayi

__all__ = [
    "RENKLER", "MIN_N", "kisa_sayi", "hazirla", "tr_sayi", "stil_uygula", "kaydet", "wilson_aralik",
    "oran_tablosu", "aralikli_oran_tablosu", "cramers_v", "auc", "etki_buyuklugu",
    "oran_grafigi", "aralikli_oran_grafigi", "profil_tablosu", "profil_izgarasi",
    "p_metin", "ARALIKLAR", "tablo_kaydet", "kategorik_hedef", "surekli_hedef", "etki_grafigi",
    "GA_ESIK", "GUC_ESIK", "tum_gruplar", "ortalamaya_gore", "guven_etiketi", "guven_tablosu", "guven_grafigi",
    "SENARYOLAR", "duyarlilik_analizi", "bonferroni_kontrolu",
    "B4_DEGISKENLER", "REFERANS", "ILISKI_ESIK", "KARISTIRMA_ESIK", "ETKILESIM_ESIK", "bolum4_verisi",
    "iliski_matrisi", "mh_risk_farki", "karistirma_tablosu", "bakiye_ulke_tablosu", "etkilesim_tablosu",
    "capraz_oran_tablosu", "capraz_isi_haritasi",
    "AGAC_DERINLIK", "AGAC_MIN_YAPRAK", "karar_agaci", "lojistik_etkilesim_testi",
    "SEGMENT_DEGISKENLERI", "SEGMENT_ONCE_AYRILAN", "SEGMENT_DISARIDA", "KAPASITELER", "segment_verisi",
    "segmentasyon_kur", "segment_tablosu", "kisitli_agac_gruplari", "yakalama_egrisi", "segment_grafigi",
    "eda_ozeti",
]

RENKLER = {
    "mavi": "#5C9FB7", "mor": "#666599", "mint": "#7FD7BC", "sari": "#F0CD7D",
    "acik_mavi": "#A8D7F2", "gri": "#B8B8B8", "turuncu": "#C97A5A",
}
MIN_N = 100  # bunun altındaki gruplar gösterilir ama "temkinli" işaretlenir


def kisa_sayi(value, _=None):
    """Eksen etiketi: 75.000 -> 75K, 1.500.000 -> 1,5M (okunaklılık için)."""
    if abs(value) >= 1_000_000:
        return tr_sayi(value / 1_000_000, 1).rstrip("0").rstrip(",") + "M"
    if abs(value) >= 1_000:
        return tr_sayi(value / 1_000, 1).rstrip("0").rstrip(",") + "K"
    return tr_sayi(value)


def stil_uygula():
    """Tüm grafikler için tek, sade görünüm."""
    plt.rcParams.update({
        "figure.dpi": 100, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": "#EEEEEE", "axes.axisbelow": True,
        "axes.titlesize": 12, "font.size": 10,
    })


def kaydet(fig, name, output_dir):
    """Grafiği PNG olarak saklar (sunumda kullanılabilir) ve gösterir."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if fig.get_layout_engine() is None:
        fig.tight_layout()
    fig.savefig(directory / name, dpi=150, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def wilson_aralik(k, n, z=1.96):
    """%95 Wilson güven aralığı (oran, 0-1). n=0 ise NaN döner.

    Gerekçe: küçük n ve uçta oranlarda normal yaklaşımdan (p ± z·se) daha güvenilirdir.
    """
    k, n = np.asarray(k, dtype=float), np.asarray(n, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = k / n
        merkez = (p + z**2 / (2 * n)) / (1 + z**2 / n)
        yari = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return merkez - yari, merkez + yari


def _ozet(gruplar, hedef, genel_oran):
    """Gruplanmış hedeften n, ayrılan, oran, GA, lift ve temkinli işareti üretir."""
    tablo = hedef.groupby(gruplar, observed=False).agg(["size", "sum"])
    tablo.columns = ["Müşteri sayısı", "Ayrılan sayısı"]
    tablo = tablo.astype(int)
    n, k = tablo["Müşteri sayısı"], tablo["Ayrılan sayısı"]
    tablo["Ayrılma oranı (%)"] = 100 * k.div(n.where(n > 0))
    alt, ust = wilson_aralik(k, n.where(n > 0))
    tablo["GA alt (%)"], tablo["GA üst (%)"] = 100 * alt, 100 * ust
    tablo["Lift"] = tablo["Ayrılma oranı (%)"] / (100 * genel_oran)
    tablo["Temkinli (n<100)"] = n < MIN_N
    return tablo


def oran_tablosu(eda, alan):
    """Kategorik/kesikli bir alan için grup bazlı ayrılma tablosu."""
    if alan not in CATEGORICAL:
        raise ValueError(f"Desteklenen kategorik alanlar: {CATEGORICAL}")
    mapping = MAPS[alan]
    grup = pd.Series(
        pd.Categorical(eda[alan].map(mapping), categories=list(mapping.values()), ordered=True),
        index=eda.index, name=NAMES[alan],
    )
    tablo = _ozet(grup, eda["Exited"], eda["Exited"].mean())
    tablo.index.name = NAMES[alan]
    return tablo


def aralikli_oran_tablosu(eda, alan, kenarlar, etiketler=None):
    """Sürekli alanı aralıklara (sol kapalı, sağ açık) bölüp ayrılma tablosu üretir.

    `kenarlar` son aralığı da kapsamalı (ör. Age için [18, 30, ..., 100]).
    Aralık dışında kalan kayıt olursa sessizce düşmesin diye hata verilir.
    """
    if alan not in CONTINUOUS:
        raise ValueError(f"Desteklenen sürekli alanlar: {CONTINUOUS}")
    if etiketler is None:  # tamsayı kenarlar için "18–29" biçimi; sol kapalı/sağ açık aralığın okunur hali
        etiketler = [f"{a}–{b - 1}" for a, b in zip(kenarlar[:-1], kenarlar[1:])]
    grup = pd.cut(eda[alan], bins=kenarlar, right=False, labels=etiketler)
    if grup.isna().any():
        raise ValueError(f"{alan} için {int(grup.isna().sum())} kayıt belirtilen aralıkların dışında kaldı.")
    tablo = _ozet(grup, eda["Exited"], eda["Exited"].mean())
    tablo.index.name = NAMES[alan]
    return tablo


def _ki_kare(eda, alan):
    """Ki-kare testinden Cramér's V ve p-değeri (düzeltmesiz; n=10.000'de fark ihmal edilebilir)."""
    sayilar = pd.crosstab(eda[alan], eda["Exited"])
    chi2, p = chi2_contingency(sayilar, correction=False)[:2]
    return float(np.sqrt(chi2 / (sayilar.to_numpy().sum() * (min(sayilar.shape) - 1)))), float(p)


def _mann_whitney(eda, alan):
    """Mann-Whitney U testinden AUC ve p-değeri: AUC = U(ayrılan) / (n_ayrılan · n_kalan)."""
    y = eda["Exited"].eq(1)
    ayrilan, kalan = eda.loc[y, alan], eda.loc[~y, alan]
    u, p = mannwhitneyu(ayrilan, kalan, alternative="two-sided")
    return float(u / (len(ayrilan) * len(kalan))), float(p)


def cramers_v(eda, alan):
    """Kategorik alan ile Exited arasında Cramér's V (0-1; ~0,1 altı zayıf, ~0,3 üstü güçlü)."""
    return _ki_kare(eda, alan)[0]


def auc(eda, alan):
    """Sürekli alanın ayrılanları ayırma gücü (AUC).

    Rastgele bir ayrılan ile bir kalan seçildiğinde ayrılanın değerinin büyük çıkma olasılığı.
    0,5 = fark yok; 0,5'ten büyük = değer arttıkça ayrılma olasılığı artar. Bağlar yarım sayılır.
    """
    return _mann_whitney(eda, alan)[0]


def p_metin(p):
    """p-değerini okunur yazar; çok küçük değerler '<0,001' olur."""
    return "<0,001" if p < 0.001 else tr_sayi(p, 3)


def etki_buyuklugu(eda, esik=0.10):
    """Bütün değişkenleri tek tabloda sıralar: kategoriklerde V, sürekli değişkenlerde AUC.

    İki ölçü aynı ölçekte değildir; sıralama için 'Güç' sütunu kullanılır:
    V olduğu gibi, AUC için 2·|AUC − 0,5| (ikisi de 0 = ilişki yok, 1 = tam ayırma). Kaba bir sıralamadır.
    Güç ≥ `esik` olanlar Bölüm 4'e (etkileşim/karıştırıcı) taşınır; eşik önceden yazılmış kuraldır.
    p-değeri yalnızca referanstır (n=10.000'de küçük farklar da anlamlı çıkar), seçimde kullanılmaz.
    Not: Tenure ve NumOfProducts kategorik, Age/Balance/CreditScore/EstimatedSalary sürekli ele alınır.
    """
    satirlar = []
    for a in CATEGORICAL:
        v, p = _ki_kare(eda, a)
        satirlar.append({"Değişken": NAMES[a], "Ölçü": "Cramér's V", "Değer": v, "Güç": v,
                         "Test": "Ki-kare", "p-değeri (referans)": p})
    for a in CONTINUOUS:
        deger, p = _mann_whitney(eda, a)
        satirlar.append({
            "Değişken": NAMES[a], "Ölçü": "AUC", "Değer": deger, "Güç": 2 * abs(deger - 0.5),
            "Test": "Mann-Whitney U", "p-değeri (referans)": p,
            "Medyan (kalan)": eda.loc[eda["Exited"].eq(0), a].median(),
            "Medyan (ayrılan)": eda.loc[eda["Exited"].eq(1), a].median(),
        })
    tablo = pd.DataFrame(satirlar).sort_values("Güç", ascending=False).reset_index(drop=True)
    tablo["Bölüm 4'e taşınır"] = tablo["Güç"] >= esik
    return tablo


def oran_grafigi(tablo, genel_oran, ax, baslik=None):
    """Yatay çubuk: ayrılma oranı + %95 GA çizgisi; etiket oran · ayrılan/n; temkinli gruplar taralı."""
    oran = tablo["Ayrılma oranı (%)"].fillna(0)
    yer = np.arange(len(tablo))
    cubuk = ax.barh(yer, oran, color=RENKLER["mavi"], height=0.65)
    for c, temkinli in zip(cubuk, tablo["Temkinli (n<100)"]):
        if temkinli:
            c.set_facecolor(RENKLER["gri"])
            c.set_hatch("//")
    ax.errorbar(
        oran, yer,
        xerr=[(oran - tablo["GA alt (%)"].fillna(0)).clip(lower=0), (tablo["GA üst (%)"].fillna(0) - oran).clip(lower=0)],
        fmt="none", ecolor=RENKLER["mor"], capsize=3, linewidth=1.2,
    )
    ax.set_yticks(yer, tablo.index.astype(str))
    ax.invert_yaxis()
    ax.axvline(100 * genel_oran, color=RENKLER["turuncu"], linestyle="--", linewidth=1.5)
    for i, (_, s) in enumerate(tablo.iterrows()):
        ax.text(
            max(s["GA üst (%)"], 0) + 1 if pd.notna(s["GA üst (%)"]) else 1, i,
            f"%{tr_sayi(s['Ayrılma oranı (%)'], 1)} · {tr_sayi(s['Ayrılan sayısı'])}/{tr_sayi(s['Müşteri sayısı'])}",
            va="center", fontsize=9,
        )
    ax.set_xlim(0, max(100, tablo["GA üst (%)"].max() + 35) if tablo["GA üst (%)"].notna().any() else 100)
    ax.set_xlabel("Ayrılma oranı (%) · çizgi: %95 güven aralığı · kesik çizgi: genel oran")
    ax.set_title(baslik or tablo.index.name)
    ax.grid(axis="y", visible=False)


def aralikli_oran_grafigi(tablo, genel_oran, ax, baslik=None):
    """Sürekli değişkenin aralıklı ayrılma oranı eğrisi (hata çubuğu: %95 Wilson GA).

    Eksen etiketinde her aralığın n'i yazar; n<100 olan noktalar içi boş gri çizilir.
    """
    x = np.arange(len(tablo))
    oran = tablo["Ayrılma oranı (%)"]
    ax.errorbar(
        x, oran, yerr=[(oran - tablo["GA alt (%)"]).clip(lower=0), (tablo["GA üst (%)"] - oran).clip(lower=0)],
        fmt="o-", color=RENKLER["mavi"], ecolor=RENKLER["mor"], capsize=3, linewidth=1.8,
    )
    temkinli = tablo["Temkinli (n<100)"].to_numpy()
    if temkinli.any():
        ax.plot(x[temkinli], oran[temkinli], "o", markersize=8, markerfacecolor="white",
                markeredgecolor=RENKLER["gri"], markeredgewidth=2, zorder=3)
    ax.axhline(100 * genel_oran, color=RENKLER["turuncu"], linestyle="--", linewidth=1.5)
    etiket = [f"{g}\nn={tr_sayi(n)}" for g, n in zip(tablo.index.astype(str), tablo["Müşteri sayısı"])]
    ax.set_xticks(x, etiket, fontsize=8)
    ax.set_ylim(bottom=0)  # 0'dan başlar: küçük dalgalanmalar büyük fark gibi görünmesin
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: tr_sayi(v)))
    ax.set_ylabel("Ayrılma oranı (%)")
    ax.set_title(baslik or tablo.index.name)


def profil_tablosu(eda):
    """Bölüm 1: yorumu etkileyen dağılım özelliklerini tek tabloda ölçer.

    Kontroller: tek değerde yığılma (en sık değerin payı), uçta yığılma
    (min/maks sıklığı), seyrek kategori (n < MIN_N), çarpıklık ve IQR dışı sayı.
    Eşikler yalnızca işaret içindir; silme veya dönüştürme yapılmaz.
    """
    satirlar = []
    for alan in ["CreditScore", "Age", "Tenure", "Balance", "NumOfProducts", "EstimatedSalary"]:
        x = eda[alan]
        q1, q3 = x.quantile([0.25, 0.75])
        iqr = q3 - q1
        en_sik = x.value_counts()
        satirlar.append({
            "Değişken": NAMES[alan], "Tür": "Sürekli" if alan in CONTINUOUS else "Kesikli",
            "Farklı değer": x.nunique(), "Min": x.min(), "Medyan": x.median(), "Ortalama": x.mean(), "Maks": x.max(),
            "Çarpıklık": x.skew(),
            "En sık değer": en_sik.index[0], "En sık değer payı (%)": 100 * en_sik.iloc[0] / len(x),
            "Min'de n": int((x == x.min()).sum()), "Maks'ta n": int((x == x.max()).sum()),
            "IQR dışı n": int(((x < q1 - 1.5 * iqr) | (x > q3 + 1.5 * iqr)).sum()),
            "n<100 grup": int((en_sik < MIN_N).sum()) if alan in ("Tenure", "NumOfProducts") else 0,
        })
    for alan in ["Geography", "Gender", "HasCrCard", "IsActiveMember"]:
        say = eda[alan].map(MAPS[alan]).value_counts()
        satirlar.append({
            "Değişken": NAMES[alan], "Tür": "Kategorik", "Farklı değer": len(say),
            "En sık değer": say.index[0], "En sık değer payı (%)": 100 * say.iloc[0] / len(eda),
            "n<100 grup": int((say < MIN_N).sum()),
        })
    return pd.DataFrame(satirlar).set_index("Değişken")


def profil_izgarasi(eda, output_dir=None):
    """Bölüm 1 grafik ızgarası: yalnızca yorumu etkileyen 6 değişken (ikili kategorikler tabloda kalır)."""
    fig, ax = plt.subplots(2, 3, figsize=(16, 8.5), layout="constrained")
    n = len(eda)

    def ortala(a, x):  # ortalama turuncu kesik, medyan mor noktalı
        a.axvline(x.mean(), color=RENKLER["turuncu"], linestyle="--", linewidth=1.5)
        a.axvline(x.median(), color=RENKLER["mor"], linestyle=":", linewidth=2)

    a = ax[0, 0]  # Yaş: 18'den başlayan 5 yıllık aralık
    kenar = np.arange(18, eda["Age"].max() + 6, 5)
    a.hist(eda["Age"], bins=kenar, color=RENKLER["mavi"], edgecolor="white", align="mid")
    ortala(a, eda["Age"]); a.set_title("Yaş (5 yıllık aralık; sağa çarpık)"); a.set_xlabel("Yaş")
    a = ax[0, 1]  # Kredi puanı: 850 tavanındaki yığılma
    a.hist(eda["CreditScore"], bins=np.arange(350, 900, 25), color=RENKLER["mavi"], edgecolor="white")
    ortala(a, eda["CreditScore"])
    t = int((eda["CreditScore"] == 850).sum())
    a.annotate(f"850'de {tr_sayi(t)} müşteri", xy=(850, 240), xytext=(430, a.get_ylim()[1] * 0.85),
               arrowprops={"arrowstyle": "->", "color": RENKLER["gri"]}, fontsize=9)
    a.set_title("Kredi puanı (25'lik aralık)"); a.set_xlabel("Kredi puanı")
    a = ax[0, 2]  # Bakiye: sıfır ve pozitif ayrı gösterilir
    pozitif = eda.loc[eda["Balance"] > 0, "Balance"]
    sifir = int((eda["Balance"] == 0).sum())
    a.hist(pozitif, bins=40, color=RENKLER["mavi"], edgecolor="white")
    a.set_title(f"Bakiye > 0 (n={tr_sayi(len(pozitif))}); sıfır bakiye: {tr_sayi(sifir)} (%{tr_sayi(100 * sifir / n, 2)})")
    a.set_xlabel("Bakiye (para birimi bilinmiyor)"); a.xaxis.set_major_formatter(FuncFormatter(kisa_sayi))
    a = ax[1, 0]  # Tahmini gelir: düz şekil
    a.hist(eda["EstimatedSalary"], bins=40, color=RENKLER["mavi"], edgecolor="white")
    ortala(a, eda["EstimatedSalary"]); a.set_title("Tahmini gelir (yaklaşık düz)"); a.set_xlabel("Tutar (birim/dönem bilinmiyor)")
    a.xaxis.set_major_formatter(FuncFormatter(kisa_sayi))
    for a, alan, baslik in [(ax[1, 1], "Tenure", "Banka ile ilişki süresi"), (ax[1, 2], "NumOfProducts", "Ürün sayısı")]:
        say = eda[alan].value_counts().sort_index()
        c = a.bar(say.index.astype(str), say.values, color=RENKLER["mavi"], width=0.7)
        for cubuk, v in zip(c, say.values):
            if v < MIN_N:
                cubuk.set_facecolor(RENKLER["gri"]); cubuk.set_hatch("//")
            a.text(cubuk.get_x() + cubuk.get_width() / 2, v, tr_sayi(v), ha="center", va="bottom", fontsize=8)
        a.set_title(baslik + (" (taralı: n<100)" if (say < MIN_N).any() else "")); a.set_xlabel(baslik)
    for a in ax.flat:
        a.set_ylabel("Müşteri sayısı"); a.yaxis.set_major_formatter(FuncFormatter(lambda v, _: tr_sayi(v)))
    fig.suptitle(f"Veri profili | Tüm veri: {tr_sayi(n)} müşteri\nOrtalama turuncu kesik, medyan mor noktalı çizgi", fontsize=13)
    if output_dir is not None:
        kaydet(fig, "01_veri_profili.png", output_dir)
    return fig


# Bölüm 2 aralıkları (2026-10-16 kullanıcı onayı). Sol kapalı, sağ açık: [a, b).
# Tüm veriye bakılarak seçildi; ML'de kullanılırsa yalnızca eğitim verisinde yeniden belirlenir.
ARALIKLAR = {
    "Age": ([18, 30, 40, 50, 60, 70, np.inf], ["18–29", "30–39", "40–49", "50–59", "60–69", "70+"]),
    "CreditScore": (
        [*range(350, 851, 50), 851],
        [f"{a}–{a + 49}" for a in range(350, 850, 50)] + ["850"],  # 850 tavanı ayrı grup
    ),
    "Balance": (  # sıfır bakiye ayrı grup, pozitifler 50K'lık
        [0, 0.005, 50_000, 100_000, 150_000, 200_000, np.inf],
        ["Sıfır", "<50K", "50–100K", "100–150K", "150–200K", "200K+"],
    ),
    "EstimatedSalary": (
        [*range(0, 200_001, 20_000)],
        [f"{a // 1000}–{(a + 20_000) // 1000}K" for a in range(0, 200_000, 20_000)],
    ),
}


def tablo_kaydet(tablo, name, output_dir, index=True):
    """Tabloyu Excel'de Türkçe karakterlerle açılacak biçimde (utf-8-sig) CSV olarak saklar."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    tablo.to_csv(directory / name, index=index, encoding="utf-8-sig")


def kategorik_hedef(eda, output_dir=None):
    """Bölüm 2a: yedi kategorik/kesikli alanda grup bazlı ayrılma tablosu ve grafik ızgarası."""
    genel = eda["Exited"].mean()
    tablolar = {alan: oran_tablosu(eda, alan) for alan in CATEGORICAL}
    uzun = pd.concat(
        {NAMES[a]: t.rename_axis("Grup") for a, t in tablolar.items()}, names=["Değişken"]
    )
    fig, axes = plt.subplots(4, 2, figsize=(15, 17), layout="constrained")
    for ax, alan in zip(axes.flat, CATEGORICAL):
        v = cramers_v(eda, alan)
        oran_grafigi(tablolar[alan], genel, ax, f"{NAMES[alan]} · Cramér's V = {tr_sayi(v, 3)}")
    axes.flat[-1].set_visible(False)
    fig.suptitle(
        f"Gruplara göre ayrılma oranı | Tüm veri: {tr_sayi(len(eda))} müşteri · genel oran %{tr_sayi(100 * genel, 2)}\n"
        "Etiket: oran · ayrılan/müşteri · gri taralı: n<100 (temkinli)", fontsize=13,
    )
    if output_dir is not None:
        tablo_kaydet(uzun, "02a_kategorik_hedef.csv", output_dir)
        kaydet(fig, "02a_kategorik_hedef.png", output_dir)
    return uzun


def surekli_hedef(eda, output_dir=None):
    """Bölüm 2b: dört sürekli alanda aralıklı ayrılma oranı eğrisi ve AUC."""
    genel = eda["Exited"].mean()
    tablolar = {alan: aralikli_oran_tablosu(eda, alan, *ARALIKLAR[alan]) for alan in CONTINUOUS}
    uzun = pd.concat(
        {NAMES[a]: t.rename_axis("Aralık") for a, t in tablolar.items()}, names=["Değişken"]
    )
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), layout="constrained")
    for ax, alan in zip(axes.flat, CONTINUOUS):
        aralikli_oran_grafigi(tablolar[alan], genel, ax, f"{NAMES[alan]} · AUC = {tr_sayi(auc(eda, alan), 3)}")
        ax.set_xlabel(f"{NAMES[alan]} aralığı" + (" (birim bilinmiyor)" if alan in ("Balance", "EstimatedSalary") else ""))
    fig.suptitle(
        f"Aralıklara göre ayrılma oranı | Tüm veri: {tr_sayi(len(eda))} müşteri\n"
        "Dikey çizgi: %95 Wilson GA · kesik çizgi: genel oran · içi boş nokta: n<100 (temkinli)", fontsize=13,
    )
    if output_dir is not None:
        tablo_kaydet(uzun, "02b_surekli_hedef.csv", output_dir)
        kaydet(fig, "02b_surekli_hedef.png", output_dir)
    return uzun


def etki_grafigi(tablo, output_dir=None, esik=0.10):
    """Bölüm 2c: etki büyüklüğü sıralaması (yatay çubuk; renk ölçü türünü, kesik çizgi taşıma eşiğini gösterir)."""
    fig, ax = plt.subplots(figsize=(10, 6), layout="constrained")
    renk = tablo["Ölçü"].map({"Cramér's V": RENKLER["mavi"], "AUC": RENKLER["mor"]})
    yer = np.arange(len(tablo))
    ax.barh(yer, tablo["Güç"], color=renk, height=0.65)
    for i, s in tablo.iterrows():
        deger = f"V = {tr_sayi(s['Değer'], 3)}" if s["Ölçü"] == "Cramér's V" else f"AUC = {tr_sayi(s['Değer'], 3)}"
        ax.text(s["Güç"] + 0.005, i, deger, va="center", fontsize=9)
    ax.set_yticks(yer, tablo["Değişken"])
    ax.invert_yaxis()
    ax.axvline(esik, color=RENKLER["turuncu"], linestyle="--", linewidth=1.5)
    ax.text(esik + 0.005, len(tablo) - 0.4, f"Bölüm 4 eşiği: {tr_sayi(esik, 2)}", color=RENKLER["turuncu"], fontsize=9)
    ax.set_xlim(0, tablo["Güç"].max() + 0.12)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: tr_sayi(v, 1)))
    ax.set_xlabel("Güç (0 = ilişki yok, 1 = tam ayırma) · V olduğu gibi, AUC için 2·|AUC − 0,5|")
    ax.grid(axis="y", visible=False)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=RENKLER["mavi"]), plt.Rectangle((0, 0), 1, 1, color=RENKLER["mor"])],
              labels=["Kategorik: Cramér's V", "Sürekli: AUC"], loc="lower right", frameon=False)
    ax.set_title("Hedefle ilişkinin gücü: değişken sıralaması | Tüm veri: 10.000 müşteri")
    if output_dir is not None:
        tablo_kaydet(tablo, "02c_etki_buyuklugu.csv", output_dir, index=False)
        kaydet(fig, "02c_etki_buyuklugu.png", output_dir)
    return fig


# Bölüm 3 kuralları (2026-10-17 kullanıcı onayı). Bölüm 4–5'te de aynen uygulanır.
# Terimler herkesin okuyabileceği biçimde seçildi:
#   "Ortalamaya göre": grubun oranı genel orandan (%20,37) güvenilir biçimde yüksek mi, düşük mü?
#   "Güven": bu oranın düzeyine ne kadar dayanabiliriz?
GA_ESIK = 10.0   # GA genişliği (yüzde puan) bu eşiğe kadar ise oranın düzeyi kesin sayılır
GUC_ESIK = 0.10  # Bölüm 2c gücü bunun altındaki değişkenlerin grupları yorumlanmaz

ORT_YUKSEK, ORT_DUSUK, ORT_FARK_YOK, ORT_ZAYIF = "Yüksek risk", "Düşük risk", "Fark yok", "Yorumlanmaz (zayıf değişken)"
GUVEN_YUKSEK, GUVEN_ORTA, GUVEN_DUSUK = "Yüksek", "Orta", "Düşük (n < 100)"


def tum_gruplar(eda):
    """Bölüm 2a ve 2b'deki bütün grupları (26 + 33 = 59) tek uzun tabloda toplar; grafik üretmez."""
    parcalar = {NAMES[a]: oran_tablosu(eda, a).rename_axis("Grup") for a in CATEGORICAL}
    parcalar.update({NAMES[a]: aralikli_oran_tablosu(eda, a, *ARALIKLAR[a]).rename_axis("Grup") for a in CONTINUOUS})
    tablo = pd.concat(parcalar, names=["Değişken"]).reset_index()
    tablo["Grup"] = tablo["Grup"].astype(str)
    tablo.insert(1, "Tür", np.where(tablo["Değişken"].isin([NAMES[a] for a in CONTINUOUS]), "Sürekli (aralık)", "Kategorik/kesikli"))
    return tablo


def ortalamaya_gore(alt, ust, guc, genel_yuzde, guc_esik=GUC_ESIK):
    """Kural 1: grubun GA'sı genel oranın tamamen üstünde mi, altında mı?

    GA'nın genel oranı dışarıda bırakması, tek oran skor testinin %5 düzeyinde reddetmesine denktir
    (Wilson aralığı bu testin tersine çevrilmesidir). Gücü eşiğin altındaki değişkenlerin grupları
    yorumlanmaz: çok sayıda grup yan yana konduğunda birinin şans eseri sınırı aşması beklenir.
    """
    if guc < guc_esik:
        return ORT_ZAYIF
    if alt > genel_yuzde:
        return ORT_YUKSEK
    if ust < genel_yuzde:
        return ORT_DUSUK
    return ORT_FARK_YOK


def guven_etiketi(n, ga_genislik, ga_esik=GA_ESIK, min_n=MIN_N):
    """Kural 2: n < min_n ise Düşük (GA dar olsa bile); değilse GA genişliğine göre Yüksek/Orta."""
    if n < min_n:
        return GUVEN_DUSUK
    return GUVEN_YUKSEK if ga_genislik <= ga_esik else GUVEN_ORTA


def guven_tablosu(eda, etki, output_dir=None, ga_esik=GA_ESIK, guc_esik=GUC_ESIK, min_n=MIN_N):
    """Bölüm 3: 59 gruba 'Ortalamaya göre' ve 'Güven' etiketi verir. `etki`, etki_buyuklugu() çıktısıdır."""
    genel = 100 * eda["Exited"].mean()
    tablo = tum_gruplar(eda)
    tablo["GA genişliği (puan)"] = tablo["GA üst (%)"] - tablo["GA alt (%)"]
    tablo["Değişken gücü"] = tablo["Değişken"].map(dict(zip(etki["Değişken"], etki["Güç"])))
    tablo["Ortalamaya göre"] = [ortalamaya_gore(a, u, g, genel, guc_esik)
                                for a, u, g in zip(tablo["GA alt (%)"], tablo["GA üst (%)"], tablo["Değişken gücü"])]
    tablo["Güven"] = [guven_etiketi(n, w, ga_esik, min_n)
                      for n, w in zip(tablo["Müşteri sayısı"], tablo["GA genişliği (puan)"])]
    tablo = tablo.drop(columns="Temkinli (n<100)")
    if output_dir is not None:
        tablo_kaydet(tablo, "03_guven_tablosu.csv", output_dir, index=False)
    return tablo


GUVEN_RENK = {GUVEN_YUKSEK: RENKLER["mavi"], GUVEN_ORTA: RENKLER["sari"], GUVEN_DUSUK: RENKLER["turuncu"]}


def guven_grafigi(tablo, genel_oran, n_toplam, output_dir=None):
    """Bölüm 3: ortalamadan güvenilir biçimde yüksek riskli gruplar; çizgi %95 GA, nokta oran, renk güven."""
    riskli = tablo[tablo["Ortalamaya göre"].eq(ORT_YUKSEK)].sort_values("Ayrılma oranı (%)").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(11, 0.45 * len(riskli) + 1.8), layout="constrained")
    for i, s in riskli.iterrows():
        renk = GUVEN_RENK[s["Güven"]]
        ax.plot([s["GA alt (%)"], s["GA üst (%)"]], [i, i], color=renk, linewidth=5, solid_capstyle="round", alpha=0.85)
        ax.plot(s["Ayrılma oranı (%)"], i, "o", markersize=7, color=renk,
                markerfacecolor="white" if s["Güven"] == GUVEN_DUSUK else renk, markeredgewidth=2)
        ax.text(min(s["GA üst (%)"], 100) + 1.2, i,
                f"%{tr_sayi(s['Ayrılma oranı (%)'], 1)} · n={tr_sayi(s['Müşteri sayısı'])}", va="center", fontsize=9)
    ax.set_yticks(range(len(riskli)), [f"{d}: {g}" for d, g in zip(riskli["Değişken"], riskli["Grup"])])
    ax.axvline(100 * genel_oran, color=RENKLER["turuncu"], linestyle="--", linewidth=1.5)
    ax.set_xlim(0, 118)
    ax.set_xlabel("Ayrılma oranı (%) · çizgi: %95 güven aralığı (Wilson) · kesik çizgi: genel oran")
    ax.grid(axis="y", visible=False)
    ax.legend(handles=[plt.Line2D([0], [0], color=c, linewidth=5) for c in GUVEN_RENK.values()],
              labels=[f"Güven: {k}" for k in GUVEN_RENK], loc="lower right", frameon=False)
    ax.set_title(f"Ortalamadan güvenilir biçimde yüksek riskli gruplar ve güven düzeyi | Tüm veri: {tr_sayi(n_toplam)} müşteri")
    if output_dir is not None:
        kaydet(fig, "03_guven_grafigi.png", output_dir)
    return fig


# Duyarlılık analizi: eşikler makul ama kesin değil; sonuç eşiklere bağlı mı?
SENARYOLAR = [
    ("Temel", MIN_N, GA_ESIK, GUC_ESIK),
    ("Küçük grup eşiği 50", 50, GA_ESIK, GUC_ESIK),
    ("Küçük grup eşiği 200", 200, GA_ESIK, GUC_ESIK),
    ("GA eşiği 8 puan", MIN_N, 8.0, GUC_ESIK),
    ("GA eşiği 15 puan", MIN_N, 15.0, GUC_ESIK),
    ("Güç eşiği 0,05", MIN_N, GA_ESIK, 0.05),
    ("Güç eşiği 0,15", MIN_N, GA_ESIK, 0.15),
    ("Hepsi gevşek", 50, 15.0, 0.05),
    ("Hepsi sıkı", 200, 8.0, 0.15),
]


def _etiket(t):
    return t["Değişken"] + ": " + t["Grup"]


def duyarlilik_analizi(eda, etki, output_dir=None, senaryolar=SENARYOLAR):
    """Her senaryoda yüksek riskli grupları sayar ve temel senaryodan farkları yazar.

    'Güvenilir yüksek risk' = Ortalamaya göre 'Yüksek risk' ve Güven 'Yüksek'. Bu, segment tablosunun
    omurgasını oluşturacak gruplardır; analiz bu kümenin eşiklere göre ne kadar değiştiğini ölçer.
    """
    def calistir(n, w, g):
        t = guven_tablosu(eda, etki, ga_esik=w, guc_esik=g, min_n=n)
        yuksek = t[t["Ortalamaya göre"].eq(ORT_YUKSEK)]
        return set(_etiket(yuksek)), set(_etiket(yuksek[yuksek["Güven"].eq(GUVEN_YUKSEK)])), yuksek["Güven"].value_counts()

    temel_risk, temel_guvenilir, _ = calistir(*senaryolar[0][1:])
    satirlar = []
    for ad, n, w, g in senaryolar:
        risk, guvenilir, say = calistir(n, w, g)
        fark = []
        if risk - temel_risk:
            fark.append("Yüksek riske giren: " + ", ".join(sorted(risk - temel_risk)))
        if temel_risk - risk:
            fark.append("Yüksek riskten çıkan: " + ", ".join(sorted(temel_risk - risk)))
        if (guvenilir - temel_guvenilir) - (risk - temel_risk):
            fark.append("Yüksek güvene geçen: " + ", ".join(sorted((guvenilir - temel_guvenilir) - (risk - temel_risk))))
        if (temel_guvenilir - guvenilir) - (temel_risk - risk):
            fark.append("Yüksek güvenden düşen: " + ", ".join(sorted((temel_guvenilir - guvenilir) - (temel_risk - risk))))
        satirlar.append({
            "Senaryo": ad, "Küçük grup eşiği (n)": n, "GA eşiği (puan)": w, "Güç eşiği": g,
            "Yüksek riskli grup": len(risk), "Yüksek güven": int(say.get(GUVEN_YUKSEK, 0)),
            "Orta güven": int(say.get(GUVEN_ORTA, 0)), "Düşük güven (n küçük)": int(say.get(GUVEN_DUSUK, 0)),
            "Temel senaryodan farkı": "; ".join(fark) or "Fark yok",
        })
    tablo = pd.DataFrame(satirlar)
    if output_dir is not None:
        tablo_kaydet(tablo, "03_duyarlilik_analizi.csv", output_dir, index=False)
    return tablo


def bonferroni_kontrolu(guven, genel_oran, output_dir=None):
    """Yüksek riskli gruplar, 59 karşılaştırma için Bonferroni düzeltmesinden sonra da yüksek riskli mi?

    Bonferroni, her karşılaştırmanın güven düzeyini 1 − 0,05/k'ya çıkarır (k = karşılaştırma sayısı);
    aralıklar genişler. Formal bir çoklu karşılaştırma kontrolü olarak kullanılır, seçim kuralı olarak değil.
    """
    k = len(guven)
    z = float(norm.ppf(1 - 0.05 / (2 * k)))
    riskli = guven[guven["Ortalamaya göre"].eq(ORT_YUKSEK)].copy()
    alt, _ = wilson_aralik(riskli["Ayrılan sayısı"], riskli["Müşteri sayısı"], z=z)
    riskli["GA alt, Bonferroni (%)"] = 100 * alt
    riskli["Bonferroni sonrası yüksek risk"] = np.where(riskli["GA alt, Bonferroni (%)"] > 100 * genel_oran, "Evet", "Hayır")
    tablo = riskli[["Değişken", "Grup", "Müşteri sayısı", "Ayrılma oranı (%)", "GA alt (%)", "GA alt, Bonferroni (%)",
                    "Güven", "Bonferroni sonrası yüksek risk"]].sort_values("Ayrılma oranı (%)", ascending=False)
    tablo.attrs["z"], tablo.attrs["k"] = z, k
    if output_dir is not None:
        tablo_kaydet(tablo, "03_bonferroni_kontrolu.csv", output_dir, index=False)
    return tablo


# ---------------------------------------------------------------------------
# Bölüm 4: etkileşim ve karıştırıcılar (2026-10-19 kullanıcı onayı)
# Kapsam: Bölüm 2c'de Güç ≥ 0,10 olan altı değişken; çapraz tablolarda hücreler küçülmesin diye
# gruplar sadeleştirilir. Referans seviyesi her değişkende düşük riskli ve kalabalık gruptur;
# etkiler "referansa göre kaç puan" diye okunur.
# ---------------------------------------------------------------------------
B4_DEGISKENLER = ["Yaş grubu", "Ürün sayısı", "Ülke", "Aktiflik", "Bakiye durumu", "Cinsiyet"]
REFERANS = {"Yaş grubu": "18–39", "Ürün sayısı": "2 ürün", "Ülke": "Fransa", "Aktiflik": "Aktif",
            "Bakiye durumu": "Sıfır", "Cinsiyet": "Erkek"}
ILISKI_ESIK = 0.10       # değişkenler arası Cramér's V; karıştırma ancak ilişkili değişkenler arasında olur
KARISTIRMA_ESIK = 10.0   # % değişim (change-in-estimate; Greenland 1989, Mickey ve Greenland 1989)
ETKILESIM_ESIK = 10.0    # yüzde puan; pratik önem eşiği (istatistiksel koşul: farkın GA'sı 0'ı içermez)


def bolum4_verisi(eda):
    """Bölüm 4 için altı değişkenin sadeleştirilmiş, sıralı kategorik hâli ve hedef."""
    def kategori(seri, sira):
        return pd.Categorical(seri, categories=sira, ordered=True)

    yas = pd.cut(eda["Age"], [18, 40, 50, 60, 70, np.inf], right=False,
                 labels=["18–39", "40–49", "50–59", "60–69", "70+"])
    d = pd.DataFrame({
        "Yaş grubu": yas,
        "Ürün sayısı": kategori(eda["NumOfProducts"].clip(upper=3).map({1: "1 ürün", 2: "2 ürün", 3: "3+ ürün"}),
                                ["1 ürün", "2 ürün", "3+ ürün"]),
        "Ülke": kategori(eda["Geography"].map(MAPS["Geography"]), list(MAPS["Geography"].values())),
        "Aktiflik": kategori(eda["IsActiveMember"].map(MAPS["IsActiveMember"]), list(MAPS["IsActiveMember"].values())),
        "Bakiye durumu": kategori(eda["BakiyeDurumu"], ["Sıfır", "Pozitif"]),
        "Cinsiyet": kategori(eda["Gender"].map(MAPS["Gender"]), list(MAPS["Gender"].values())),
        "Exited": eda["Exited"].to_numpy(),
    }, index=eda.index)
    if d[B4_DEGISKENLER].isna().any().any():
        raise ValueError("Bölüm 4 gruplamasında boş değer oluştu; kategori tanımlarını kontrol edin.")
    return d


def _v(a, b):
    sayilar = pd.crosstab(a, b)
    chi2 = chi2_contingency(sayilar, correction=False)[0]
    return float(np.sqrt(chi2 / (sayilar.to_numpy().sum() * (min(sayilar.shape) - 1)))), int(sayilar.to_numpy().min())


def iliski_matrisi(d4, output_dir=None, esik=ILISKI_ESIK):
    """4a: altı değişken arasında Cramér's V. V ≥ eşik olan çiftler karıştırma adayıdır."""
    matris = pd.DataFrame(np.eye(len(B4_DEGISKENLER)), index=B4_DEGISKENLER, columns=B4_DEGISKENLER)
    satirlar = []
    for i, a in enumerate(B4_DEGISKENLER):
        for b in B4_DEGISKENLER[i + 1:]:
            v, en_kucuk = _v(d4[a], d4[b])
            matris.loc[a, b] = matris.loc[b, a] = v
            satirlar.append({"Değişken A": a, "Değişken B": b, "Cramér's V": v, "En küçük hücre (n)": en_kucuk,
                             "Karıştırma adayı": "Evet" if v >= esik else "Hayır"})
    ciftler = pd.DataFrame(satirlar).sort_values("Cramér's V", ascending=False).reset_index(drop=True)

    # Alt üçgen; boş kalan ilk satır ve son sütun gösterilmez
    alt_ucgen = matris.iloc[1:, :-1]
    fig, ax = plt.subplots(figsize=(7.5, 5.5), layout="constrained")
    maske = np.triu(np.ones_like(alt_ucgen, dtype=bool), k=1)
    im = ax.imshow(np.ma.masked_array(alt_ucgen.to_numpy(), mask=maske), cmap=BLUE, vmin=0, vmax=0.5)
    for i in range(alt_ucgen.shape[0]):
        for j in range(i + 1):
            v = alt_ucgen.iloc[i, j]
            ax.text(j, i, tr_sayi(v, 2), ha="center", va="center", fontsize=10,
                    fontweight="bold" if v >= esik else "normal", color="black" if v >= esik else "#707070")
    ax.set_xticks(range(alt_ucgen.shape[1]), alt_ucgen.columns, rotation=30, ha="right")
    ax.set_yticks(range(alt_ucgen.shape[0]), alt_ucgen.index)
    ax.grid(False)
    for kenar in ax.spines.values():
        kenar.set_visible(False)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Cramér's V")
    ax.set_title(f"Değişkenler arası ilişki | Tüm veri: {tr_sayi(len(d4))} müşteri\n"
                 f"Kalın: V ≥ {tr_sayi(esik, 2)} (karıştırma adayı)")
    if output_dir is not None:
        tablo_kaydet(ciftler, "04a_degiskenler_arasi_iliski.csv", output_dir, index=False)
        kaydet(fig, "04a_degiskenler_arasi_iliski.png", output_dir)
    return ciftler


def _hucre(d4, kosul):
    alt = d4.loc[kosul, "Exited"]
    return len(alt), int(alt.sum())


def mh_risk_farki(d4, a_alani, a_seviyesi, b_alani):
    """A'nın (a_seviyesi − referans) risk farkı: ham ve B katmanları içinde Mantel–Haenszel ağırlıklı.

    Ağırlık w_k = n1k·n0k / N_k. Varyans: Sato (1989) tahmincisi. Bir katmanda A seviyelerinden biri
    yoksa (ör. Almanya'da sıfır bakiye) w_k = 0 olur; katman ayarlanmış farka katkı vermez.
    Sonuçlar yüzde puandır.
    """
    ref = REFERANS[a_alani]
    n1, y1 = _hucre(d4, d4[a_alani].eq(a_seviyesi))
    n0, y0 = _hucre(d4, d4[a_alani].eq(ref))
    p1, p0 = y1 / n1, y0 / n0
    ham = p1 - p0
    ham_se = np.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)

    pay = W = P = Q = 0.0
    katki_vermeyen = []
    for seviye in d4[b_alani].cat.categories:
        k = d4[b_alani].eq(seviye)
        n1k, y1k = _hucre(d4, k & d4[a_alani].eq(a_seviyesi))
        n0k, y0k = _hucre(d4, k & d4[a_alani].eq(ref))
        if n1k == 0 or n0k == 0:
            katki_vermeyen.append(str(seviye))
            continue
        N = n1k + n0k
        pay += (y1k * n0k - y0k * n1k) / N
        W += n1k * n0k / N
        P += (n1k ** 2 * y0k - n0k ** 2 * y1k + n1k * n0k * (n0k - n1k) / 2) / N ** 2
        Q += (y1k * (n0k - y0k) + y0k * (n1k - y1k)) / (2 * N)
    ayarli = pay / W
    ayarli_se = np.sqrt((ayarli * P + Q) / W ** 2)
    return {
        "Ham fark (puan)": 100 * ham, "Ham GA alt": 100 * (ham - 1.96 * ham_se), "Ham GA üst": 100 * (ham + 1.96 * ham_se),
        "Ayarlanmış fark (puan)": 100 * ayarli,
        "Ayarlanmış GA alt": 100 * (ayarli - 1.96 * ayarli_se), "Ayarlanmış GA üst": 100 * (ayarli + 1.96 * ayarli_se),
        "Değişim (%)": 100 * (ayarli - ham) / ham,
        "Katkı vermeyen katman": ", ".join(katki_vermeyen) or "—",
    }


def karistirma_tablosu(d4, ciftler, etkilesim=None, output_dir=None, esik=KARISTIRMA_ESIK):
    """4b: karıştırma adayı çiftlerde her iki yönde: A'nın etkisi, B kontrol edildiğinde ne kadar değişiyor?

    Kural (change-in-estimate): |değişim| ≥ %10 ise 'Karıştırma var'. Etkileşim adayı olan çiftlerde tek
    ayarlanmış sayı ortalama bir değerdir; katman etkileri 4c'de ayrı okunmalıdır.
    """
    adaylar = ciftler[ciftler["Karıştırma adayı"].eq("Evet")]
    satirlar = []
    for _, c in adaylar.iterrows():
        for a, b in [(c["Değişken A"], c["Değişken B"]), (c["Değişken B"], c["Değişken A"])]:
            for seviye in d4[a].cat.categories:
                if seviye == REFERANS[a]:
                    continue
                r = mh_risk_farki(d4, a, seviye, b)
                etki_var = None
                if etkilesim is not None:
                    secim = etkilesim[(((etkilesim["Değişken A"] == a) & (etkilesim["Seviye A"] == seviye) & (etkilesim["Değişken B"] == b))
                                       | ((etkilesim["Değişken B"] == a) & (etkilesim["Seviye B"] == seviye) & (etkilesim["Değişken A"] == b)))]
                    sonuclar = set(secim["Sonuç"])
                    if "Etkileşim adayı" in sonuclar:
                        etki_var = "Evet"
                    elif "Küçük hücre (n < 100)" in sonuclar:
                        etki_var = "Küçük hücre (n < 100)"
                    elif "Değerlendirilemez (boş hücre)" in sonuclar:
                        etki_var = "Değerlendirilemez (boş hücre)"
                    else:
                        etki_var = "Hayır"
                # Ham fark 0'dan ayırt edilemiyorsa yüzde değişim anlamsızdır (paydası ~0)
                ham_belirsiz = r["Ham GA alt"] <= 0 <= r["Ham GA üst"]
                if ham_belirsiz:
                    r["Değişim (%)"] = np.nan
                    karar = "Değerlendirilemez (ham fark ≈ 0)"
                else:
                    karar = "Var" if abs(r["Değişim (%)"]) >= esik else "Yok"
                satirlar.append({
                    "Etkisi ölçülen": f"{a}: {seviye} (ref. {REFERANS[a]})", "Kontrol edilen": b, **r,
                    "Karıştırma": karar,
                    "Etkinin kalan payı (%)": np.nan if ham_belirsiz else 100 * r["Ayarlanmış fark (puan)"] / r["Ham fark (puan)"],
                    **({"Bu çiftte etkileşim adayı": etki_var} if etki_var else {}),
                })
    tablo = pd.DataFrame(satirlar)
    if output_dir is not None:
        tablo_kaydet(tablo, "04b_karistirma.csv", output_dir, index=False)
    return tablo


def bakiye_ulke_tablosu(eda, output_dir=None):
    """4b ek: bakiye aralıklarında ayrılma oranı, ülkeye göre (100–150K neden yüksek riskli?)."""
    kenar, etiket = ARALIKLAR["Balance"]
    d = pd.DataFrame({
        "Bakiye": pd.cut(eda["Balance"], bins=kenar, right=False, labels=etiket),
        "Ülke": pd.Categorical(eda["Geography"].map(MAPS["Geography"]), categories=list(MAPS["Geography"].values())),
        "Exited": eda["Exited"],
    })
    g = d.groupby(["Bakiye", "Ülke"], observed=False)["Exited"].agg(["size", "sum"])
    g.columns = ["Müşteri sayısı", "Ayrılan sayısı"]
    g["Ayrılma oranı (%)"] = 100 * g["Ayrılan sayısı"] / g["Müşteri sayısı"].where(g["Müşteri sayısı"] > 0)
    oran = g["Ayrılma oranı (%)"].unstack("Ülke")
    n = g["Müşteri sayısı"].unstack("Ülke")
    pay = d.groupby("Bakiye", observed=False)["Ülke"].value_counts(normalize=True).unstack("Ülke") * 100
    tablo = pd.concat({"Ayrılma oranı (%)": oran, "Müşteri sayısı": n, "Ülke payı (%)": pay}, axis=1)
    if output_dir is not None:
        tablo_kaydet(tablo, "04b_bakiye_ulke.csv", output_dir)
    return tablo


def etkilesim_tablosu(d4, output_dir=None, esik=ETKILESIM_ESIK, min_n=MIN_N):
    """4c: 15 çiftin her birinde A'nın etkisi B'nin seviyesine göre değişiyor mu (yüzde puan)?

    Her (a, b) seviye çifti için 2×2 fark farkı hesaplanır:
        [p(a, b) − p(ref_A, b)] − [p(a, ref_B) − p(ref_A, ref_B)]
    Bu ölçü simetriktir: 'A'nın etkisi B'ye göre' ile 'B'nin etkisi A'ya göre' aynı sayıyı verir.
    Kural: |fark farkı| ≥ eşik, %95 GA 0'ı içermiyor ve dört hücrenin hepsi n ≥ 100 ise 'Etkileşim adayı'.
    Hücrelerden biri boşsa 'Değerlendirilemez (boş hücre)'.
    Ölçek yüzde puandır; odds ratio ölçeğinde sonuç farklı olabilir.
    """
    satirlar = []
    for i, A in enumerate(B4_DEGISKENLER):
        for B in B4_DEGISKENLER[i + 1:]:
            for a in d4[A].cat.categories:
                if a == REFERANS[A]:
                    continue
                for b in d4[B].cat.categories:
                    if b == REFERANS[B]:
                        continue
                    hucreler = {}
                    for ad, (sa, sb) in {"ab": (a, b), "0b": (REFERANS[A], b), "a0": (a, REFERANS[B]),
                                         "00": (REFERANS[A], REFERANS[B])}.items():
                        n, y = _hucre(d4, d4[A].eq(sa) & d4[B].eq(sb))
                        hucreler[ad] = (n, y / n if n else np.nan)
                    p = {k: v[1] for k, v in hucreler.items()}
                    n = {k: v[0] for k, v in hucreler.items()}
                    etki_b = p["ab"] - p["0b"]
                    etki_ref = p["a0"] - p["00"]
                    fark = etki_b - etki_ref
                    se = np.sqrt(sum(p[k] * (1 - p[k]) / n[k] for k in p if n[k] > 0))
                    alt, ust = fark - 1.96 * se, fark + 1.96 * se
                    en_kucuk = min(n.values())
                    belirgin = abs(100 * fark) >= esik and (alt > 0 or ust < 0)
                    if en_kucuk == 0:
                        # Bir hücre boşsa (ör. Almanya'da sıfır bakiye yok) fark farkı hesaplanamaz
                        sonuc = "Değerlendirilemez (boş hücre)"
                    elif belirgin and en_kucuk >= min_n:
                        sonuc = "Etkileşim adayı"
                    elif belirgin:
                        sonuc = "Küçük hücre (n < 100)"
                    else:
                        sonuc = "Yok"
                    satirlar.append({
                        "Değişken A": A, "Seviye A": a, "Değişken B": B, "Seviye B": b,
                        "A'nın etkisi, B seviyesinde (puan)": 100 * etki_b,
                        "A'nın etkisi, B referansında (puan)": 100 * etki_ref,
                        "Fark farkı (puan)": 100 * fark, "GA alt": 100 * alt, "GA üst": 100 * ust,
                        "En küçük hücre (n)": en_kucuk, "Sonuç": sonuc,
                    })
    tablo = pd.DataFrame(satirlar)
    tablo = tablo.reindex(tablo["Fark farkı (puan)"].abs().sort_values(ascending=False).index).reset_index(drop=True)
    # Sağlamlık kontrolü (Bölüm 3 ile tutarlı): değerlendirilebilen k karşılaştırma için Bonferroni aralığı
    # 0'ı içeriyor mu? Yalnızca aday ve küçük hücreli satırlarda raporlanır.
    k = int(tablo["Fark farkı (puan)"].notna().sum())
    z = float(norm.ppf(1 - 0.05 / (2 * k)))
    se = (tablo["GA üst"] - tablo["GA alt"]) / (2 * 1.96)
    bonf_alt, bonf_ust = tablo["Fark farkı (puan)"] - z * se, tablo["Fark farkı (puan)"] + z * se
    raporlanan = tablo["Sonuç"].isin(["Etkileşim adayı", "Küçük hücre (n < 100)"])
    tablo["Bonferroni sonrası"] = np.where(~raporlanan, "—",
                                           np.where((bonf_alt > 0) | (bonf_ust < 0), "Korunuyor", "Korunmuyor"))
    tablo.attrs["karsilastirma_sayisi"], tablo.attrs["degerlendirilen"], tablo.attrs["z_bonferroni"] = len(tablo), k, z
    if output_dir is not None:
        tablo_kaydet(tablo, "04c_etkilesim.csv", output_dir, index=False)
    return tablo


def capraz_oran_tablosu(d4, A, B):
    """İki değişkenin her hücresinde n, ayrılan, oran ve Bölüm 3 güven etiketi."""
    g = d4.groupby([A, B], observed=False)["Exited"].agg(["size", "sum"])
    g.columns = ["Müşteri sayısı", "Ayrılan sayısı"]
    alt, ust = wilson_aralik(g["Ayrılan sayısı"], g["Müşteri sayısı"].where(g["Müşteri sayısı"] > 0))
    g["Ayrılma oranı (%)"] = 100 * g["Ayrılan sayısı"] / g["Müşteri sayısı"].where(g["Müşteri sayısı"] > 0)
    g["GA alt (%)"], g["GA üst (%)"] = 100 * alt, 100 * ust
    genel = 100 * d4["Exited"].mean()
    # Hücreler tek tek yorumlanır; değişken gücü koşulu burada uygulanmaz (guc = 1)
    g["Ortalamaya göre"] = [ORT_FARK_YOK if pd.isna(a) else ortalamaya_gore(a, u, 1.0, genel)
                            for a, u in zip(g["GA alt (%)"], g["GA üst (%)"])]
    g["Güven"] = [GUVEN_DUSUK if n < MIN_N else guven_etiketi(n, u - a)
                  for n, a, u in zip(g["Müşteri sayısı"], g["GA alt (%)"], g["GA üst (%)"])]
    return g


def capraz_isi_haritasi(d4, ciftler_listesi, output_dir=None, dosya="04c_capraz_haritalar.png"):
    """Seçilen çiftlerde hücre oranları: renk oran, yazı oran ve n; n < 100 hücreler gri italik."""
    k = len(ciftler_listesi)
    sutun = 2 if k > 1 else 1
    satir = int(np.ceil(k / sutun))
    fig, axes = plt.subplots(satir, sutun, figsize=(7.2 * sutun, 4.2 * satir), layout="constrained", squeeze=False)
    for ax, (A, B) in zip(axes.flat, ciftler_listesi):
        g = capraz_oran_tablosu(d4, A, B)
        oran = g["Ayrılma oranı (%)"].unstack(B)
        n = g["Müşteri sayısı"].unstack(B)
        im = ax.imshow(np.ma.masked_invalid(oran.to_numpy(dtype=float)), cmap=BLUE, vmin=0, vmax=100, aspect="auto")
        for i in range(oran.shape[0]):
            for j in range(oran.shape[1]):
                nn, oo = int(n.iloc[i, j]), oran.iloc[i, j]
                kucuk = nn < MIN_N
                metin = "n = 0" if nn == 0 else f"%{tr_sayi(oo, 1)}\nn = {tr_sayi(nn)}"
                ax.text(j, i, metin, ha="center", va="center", fontsize=9,
                        color="#808080" if kucuk else ("white" if oo > 60 else "black"), style="italic" if kucuk else "normal")
        ax.set_xticks(range(oran.shape[1]), [str(c) for c in oran.columns])
        ax.set_yticks(range(oran.shape[0]), [str(r) for r in oran.index])
        ax.set_xlabel(B)
        ax.set_ylabel(A)
        ax.grid(False)
        ax.set_title(f"{A} × {B}")
    for ax in list(axes.flat)[k:]:
        ax.set_visible(False)
    fig.colorbar(im, ax=axes, shrink=0.6, label="Ayrılma oranı (%)")
    fig.suptitle(f"Çapraz ayrılma oranları | Tüm veri: {tr_sayi(len(d4))} müşteri · gri italik: n < 100", fontsize=13)
    if output_dir is not None:
        kaydet(fig, dosya, output_dir)
    return fig


# ---------------------------------------------------------------------------
# Bölüm 4d: çok değişkenli kontrol (2026-10-19 kullanıcı onayı)
# Tahmin modeli değildir: tüm veride kurulur, performans iddiası yapılmaz, bulunan kesim noktaları
# ve etkileşimler ML'ye doğrudan taşınmaz (ML kararlarını yalnızca eğitim verisinde verir).
# ---------------------------------------------------------------------------
AGAC_DERINLIK = 3      # en fazla 8 yaprak; okunabilir kurallar
AGAC_MIN_YAPRAK = MIN_N  # her yaprakta en az 100 müşteri (Bölüm 3 kuralı)


def _gostergeler(d4, referanssiz=True):
    """Altı değişkenin 0/1 gösterge sütunları; ad biçimi 'Değişken = seviye'."""
    sutunlar = {}
    for a in B4_DEGISKENLER:
        for seviye in d4[a].cat.categories:
            if referanssiz and seviye == REFERANS[a]:
                continue
            sutunlar[f"{a} = {seviye}"] = d4[a].eq(seviye).astype(float).to_numpy()
    return pd.DataFrame(sutunlar, index=d4.index)


def karar_agaci(d4, output_dir=None, derinlik=AGAC_DERINLIK, min_yaprak=AGAC_MIN_YAPRAK):
    """4d-1: sığ CART karar ağacı (Gini). Ayarlar önceden sabittir, denenip seçilmez.

    Döndürür: (yaprak tablosu, model). Yaprak tablosu her yaprağın kuralını, n, ayrılan, oran, %95 Wilson
    aralığını, Bölüm 3 etiketlerini ve müşteri/ayrılan paylarını içerir.
    """
    from sklearn.tree import DecisionTreeClassifier

    X = _gostergeler(d4, referanssiz=False)
    y = d4["Exited"].to_numpy()
    model = DecisionTreeClassifier(max_depth=derinlik, min_samples_leaf=min_yaprak, random_state=0).fit(X, y)
    agac = model.tree_
    adlar = list(X.columns)

    # Her yaprağın kuralı: göstergeler 0/1 olduğundan eşik 0,5; sol dal "≠", sağ dal "="
    kurallar = {}

    def gez(dugum, kosullar):
        if agac.children_left[dugum] == -1:
            kurallar[dugum] = kosullar
            return
        ad = adlar[agac.feature[dugum]]
        degisken, seviye = ad.split(" = ", 1)
        gez(agac.children_left[dugum], kosullar + [f"{degisken} ≠ {seviye}"])
        gez(agac.children_right[dugum], kosullar + [f"{degisken} = {seviye}"])

    gez(0, [])

    def sadelestir(kosullar):
        # Aynı değişkene ait koşulları birleştirir: "≠ 3+ ürün ve ≠ 2 ürün" → "= 1 ürün"
        izinli = {}
        for k in kosullar:
            if " ≠ " in k:
                degisken, seviye = k.split(" ≠ ", 1)
                izinli.setdefault(degisken, set(map(str, d4[degisken].cat.categories))).discard(seviye)
            else:
                degisken, seviye = k.split(" = ", 1)
                izinli[degisken] = {seviye} & izinli.get(degisken, {seviye})
        parcalar = []
        for degisken, kume in izinli.items():
            hepsi = [str(c) for c in d4[degisken].cat.categories]
            secili = [c for c in hepsi if c in kume]
            disarida = [c for c in hepsi if c not in kume]
            if len(secili) == 1:
                parcalar.append(f"{degisken} = {secili[0]}")
            elif len(disarida) == 1:
                parcalar.append(f"{degisken} ≠ {disarida[0]}")
            else:
                parcalar.append(f"{degisken}: {', '.join(secili)}")
        return " ve ".join(parcalar)

    yaprak = model.apply(X)
    genel = 100 * y.mean()
    satirlar = []
    for dugum, kosullar in kurallar.items():
        m = yaprak == dugum
        n, k = int(m.sum()), int(y[m].sum())
        alt, ust = wilson_aralik(k, n)
        alt, ust = 100 * float(alt), 100 * float(ust)
        satirlar.append({
            "Yaprak": dugum, "Kural": sadelestir(kosullar), "Müşteri sayısı": n, "Ayrılan sayısı": k,
            "Ayrılma oranı (%)": 100 * k / n, "GA alt (%)": alt, "GA üst (%)": ust, "Lift": (100 * k / n) / genel,
            "Müşterilerin payı (%)": 100 * n / len(y), "Ayrılanların payı (%)": 100 * k / y.sum(),
            "Ortalamaya göre": ortalamaya_gore(alt, ust, 1.0, genel), "Güven": guven_etiketi(n, ust - alt),
        })
    tablo = pd.DataFrame(satirlar).sort_values("Ayrılma oranı (%)", ascending=False).reset_index(drop=True)
    tablo.insert(0, "Sıra", range(1, len(tablo) + 1))

    fig = agac_grafigi(model, X, y, tablo, derinlik, min_yaprak)
    if output_dir is not None:
        tablo_kaydet(tablo, "04d_agac_yapraklari.csv", output_dir, index=False)
        kaydet(fig, "04d_karar_agaci.png", output_dir)
    return tablo, model


def agac_grafigi(model, X, y, yapraklar, derinlik, min_yaprak):
    """Karar ağacını sunum biçiminde çizer: Türkçe soru, Evet/Hayır dalları, n, veri payı ve ayrılma oranı.

    Kutunun rengi ayrılma oranını gösterir; yapraklarda sıra numarası ve Bölüm 3 güven etiketi yazar.
    """
    from matplotlib.patches import FancyBboxPatch

    agac = model.tree_
    adlar = list(X.columns)
    uyelik = model.decision_path(X).toarray().astype(bool)
    sira = dict(zip(yapraklar["Yaprak"], yapraklar["Sıra"]))
    guven = dict(zip(yapraklar["Yaprak"], yapraklar["Güven"]))

    konum, yaprak_sayaci = {}, [0]

    def yerlestir(dugum, d):
        sol, sag = agac.children_left[dugum], agac.children_right[dugum]
        if sol == -1:
            konum[dugum] = (2.6 * yaprak_sayaci[0], -1.25 * d)
            yaprak_sayaci[0] += 1
            return
        yerlestir(sol, d + 1)
        yerlestir(sag, d + 1)
        konum[dugum] = ((konum[sol][0] + konum[sag][0]) / 2, -1.25 * d)

    yerlestir(0, 0)
    fig, ax = plt.subplots(figsize=(2.9 * yaprak_sayaci[0] + 1, 1.9 * (derinlik + 1) + 1), layout="constrained")
    for dugum, (x, yy) in konum.items():
        for cocuk, etiket in [(agac.children_left[dugum], "Hayır"), (agac.children_right[dugum], "Evet")]:
            if cocuk == -1:
                continue
            cx, cy = konum[cocuk]
            ax.plot([x, cx], [yy - 0.3, cy + 0.32], color=RENKLER["gri"], linewidth=1.2, zorder=1)
            ax.text((x + cx) / 2, (yy - 0.3 + cy + 0.32) / 2, etiket, ha="center", va="center", fontsize=9,
                    color=RENKLER["mor"], bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none"}, zorder=3)
    for dugum, (x, yy) in konum.items():
        m = uyelik[:, dugum]
        n, oran = int(m.sum()), 100 * y[m].mean()
        renk = BLUE(min(oran / 80, 1.0))
        yazi_rengi = "white" if oran > 50 else "black"
        if agac.children_left[dugum] == -1:
            metin = (f"Sıra {sira[dugum]}\nAyrılma %{tr_sayi(oran, 1)}\n"
                     f"n = {tr_sayi(n)} (%{tr_sayi(100 * n / len(y), 1)})\nGüven: {guven[dugum]}")
        else:
            degisken, seviye = adlar[agac.feature[dugum]].split(" = ", 1)
            metin = (f"{degisken}: {seviye} mi?\n"
                     f"n = {tr_sayi(n)} (%{tr_sayi(100 * n / len(y), 1)}) · ayrılma %{tr_sayi(oran, 1)}")
        ax.add_patch(FancyBboxPatch((x - 1.15, yy - 0.28), 2.3, 0.6, boxstyle="round,pad=0.03",
                                    fc=renk, ec=RENKLER["mor"] if agac.children_left[dugum] == -1 else RENKLER["gri"],
                                    linewidth=1.5 if agac.children_left[dugum] == -1 else 1, zorder=2))
        ax.text(x, yy + 0.02, metin, ha="center", va="center", fontsize=8.5, color=yazi_rengi, zorder=4)
    ax.set_xlim(-1.3, 2.6 * (yaprak_sayaci[0] - 1) + 1.3)
    ax.set_ylim(-1.25 * derinlik - 0.45, 0.45)
    ax.axis("off")
    ax.set_title(f"Sığ karar ağacı (CART, derinlik ≤ {derinlik}, her yaprakta en az {min_yaprak} müşteri) | "
                 f"Tüm veri: {tr_sayi(len(y))} müşteri\nRenk: ayrılma oranı (koyu = yüksek) · "
                 "betimsel kontrol, tahmin modeli değil", fontsize=12)
    return fig


def _log_olabilirlik(X, y):
    """Cezasız lojistik regresyon (C = ∞) ve log-olabilirlik."""
    import warnings
    from sklearn.linear_model import LogisticRegression

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # yakınsama uyarıları ayrıca 'Yakınsadı' sütununda raporlanır
        model = LogisticRegression(C=np.inf, max_iter=10_000, tol=1e-8).fit(X, y)
    p = np.clip(model.predict_proba(X)[:, 1], 1e-12, 1 - 1e-12)
    ll = float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))
    return ll, model, bool(model.n_iter_[0] < 10_000)


def _carpim(d4, A, a, B, b):
    return (d4[A].eq(a) & d4[B].eq(b)).astype(float).to_numpy()


def lojistik_etkilesim_testi(d4, etkilesim, output_dir=None):
    """4d-2: lojistik regresyonla etkileşim testi (olabilirlik oranı testi; odds ölçeği).

    Model 0: altı değişkenin ana etkileri. Her 4c adayı tek tek eklenir (df = 1); kural: p < 0,05 / aday sayısı
    (Bonferroni) ise 'çok değişkenli kontrolde korunuyor'. Model 1: bütün adaylar birlikte. Model 2: bütün ikili
    etkileşimler; Model 2 − Model 1 testi 4c'nin kaçırdığı ikili etkileşim olup olmadığını sınar ve ek katkı
    çift bazında ayrıştırılır (her çiftin bütün terimleri Model 1'e eklenir; kural p < 0,05 / çift sayısı).
    Boş hücreden doğan sabit veya mevcut sütunu tekrarlayan çarpımlar modele girmez (serbestlik derecesi rank
    farkıyla hesaplanır). Tüm veride kurulur; tahmin performansı iddiası yoktur.
    """
    from scipy.stats import chi2

    y = d4["Exited"].to_numpy()
    X0 = _gostergeler(d4)
    ll0, _, yak0 = _log_olabilirlik(X0, y)
    adaylar = etkilesim[etkilesim["Sonuç"].eq("Etkileşim adayı")]
    esik = 0.05 / len(adaylar)

    satirlar = []
    terimler = {}
    for _, r in adaylar.iterrows():
        ad = f"{r['Değişken A']} = {r['Seviye A']} × {r['Değişken B']} = {r['Seviye B']}"
        terimler[ad] = _carpim(d4, r["Değişken A"], r["Seviye A"], r["Değişken B"], r["Seviye B"])
        X1 = X0.assign(**{ad: terimler[ad]})
        ll1, model, yak = _log_olabilirlik(X1, y)
        lr = 2 * (ll1 - ll0)
        p = float(chi2.sf(lr, 1))
        satirlar.append({
            "Etkileşim": ad, "Fark farkı, 4c (puan)": r["Fark farkı (puan)"],
            "Odds oranı çarpanı": float(np.exp(model.coef_[0][-1])), "LR istatistiği": lr, "p-değeri": p,
            "Sonuç": "Korunuyor" if p < esik else "Korunmuyor", "Yakınsadı": "Evet" if yak else "Hayır",
        })
    tekli = pd.DataFrame(satirlar)
    tekli.attrs["bonferroni_esigi"] = esik

    # Model 1 ve Model 2
    X1 = X0.assign(**terimler)
    ll1, _, yak1 = _log_olabilirlik(X1, y)
    tum = {}
    for i, A in enumerate(B4_DEGISKENLER):
        for B in B4_DEGISKENLER[i + 1:]:
            for a in d4[A].cat.categories:
                if a == REFERANS[A]:
                    continue
                for b in d4[B].cat.categories:
                    if b == REFERANS[B]:
                        continue
                    tum[f"{A} = {a} × {B} = {b}"] = _carpim(d4, A, a, B, b)
    X2 = X0.copy()
    for ad, sutun in tum.items():
        if sutun.std() == 0 or any(np.array_equal(sutun, X2[c].to_numpy()) for c in X2.columns):
            continue  # boş hücre veya mevcut göstergenin tekrarı (ör. Almanya'da herkes pozitif bakiyeli)
        X2[ad] = sutun
    ll2, _, yak2 = _log_olabilirlik(X2, y)
    rank = np.linalg.matrix_rank
    r0, r1, r2 = rank(X0.to_numpy()), rank(X1.to_numpy()), rank(X2.to_numpy())

    def satir(ad, ll, r, yak, onceki=None):
        k = r + 1  # sabit terim dahil
        kayit = {"Model": ad, "Parametre sayısı": k, "Log-olabilirlik": ll, "AIC": 2 * k - 2 * ll,
                 "Yakınsadı": "Evet" if yak else "Hayır"}
        if onceki is not None:
            lr, df = 2 * (ll - onceki[0]), r - onceki[1]
            kayit.update({"Karşılaştırılan": onceki[2], "LR istatistiği": lr, "df": df, "p-değeri": float(chi2.sf(lr, df))})
        return kayit

    # Model 2'deki ek katkı hangi çiftten geliyor? Her çiftin bütün terimleri Model 1'e eklenir.
    cift_satirlari = []
    for i, A in enumerate(B4_DEGISKENLER):
        for B in B4_DEGISKENLER[i + 1:]:
            Xc = X1.copy()
            for ad, sutun in tum.items():
                if not ad.startswith(f"{A} = ") or f" × {B} = " not in ad or ad in Xc.columns:
                    continue
                if sutun.std() == 0 or any(np.array_equal(sutun, Xc[c].to_numpy()) for c in Xc.columns):
                    continue
                Xc[ad] = sutun
            df = rank(Xc.to_numpy()) - r1
            if df == 0:
                continue
            llc, _, _ = _log_olabilirlik(Xc, y)
            lr = 2 * (llc - ll1)
            cift_satirlari.append({"Çift": f"{A} × {B}", "Eklenen terim (df)": df, "LR istatistiği": lr,
                                   "p-değeri": float(chi2.sf(lr, df))})
    ciftler = pd.DataFrame(cift_satirlari).sort_values("LR istatistiği", ascending=False).reset_index(drop=True)
    cift_esik = 0.05 / len(ciftler)
    ciftler["Sonuç"] = np.where(ciftler["p-değeri"] < cift_esik, "Ek etkileşim var", "Yok")
    ciftler.attrs["bonferroni_esigi"] = cift_esik

    modeller = pd.DataFrame([
        satir("Model 0: ana etkiler", ll0, r0, yak0),
        satir(f"Model 1: + {len(adaylar)} etkileşim adayı (4c)", ll1, r1, yak1, (ll0, r0, "Model 0")),
        satir("Model 2: + bütün ikili etkileşimler", ll2, r2, yak2, (ll1, r1, "Model 1")),
    ])
    if output_dir is not None:
        tablo_kaydet(tekli, "04d_lojistik_etkilesim_testi.csv", output_dir, index=False)
        tablo_kaydet(modeller, "04d_lojistik_model_karsilastirma.csv", output_dir, index=False)
        tablo_kaydet(ciftler, "04d_kacirilan_etkilesim.csv", output_dir, index=False)
    return tekli, modeller, ciftler


# ---------------------------------------------------------------------------
# Bölüm 5: segment tablosu ve yakalama eğrisi (2026-10-19 kullanıcı onayı)
# Segmentasyon yeniden çalıştırılabilir bir prosedürdür: ML aşamasında yalnızca eğitim verisinde
# kurulup test verisinde ölçülecektir. Bölme kuralı ayrılma oranına bakmaz, yalnızca grup büyüklüğüne bakar.
# ---------------------------------------------------------------------------
SEGMENT_DEGISKENLERI = ["Yaş grubu", "Ürün sayısı", "Ülke grubu", "Aktiflik"]  # Bölüm 2c güç sırası
SEGMENT_ONCE_AYRILAN = ("Ürün sayısı", "3+ ürün")  # Bölüm 3 kararı: 3+ ürün tek segment
SEGMENT_DISARIDA = {"Cinsiyet": "etik: cinsiyete göre önceliklendirme yapılmaz",
                    "Bakiye durumu": "etkisi ülkeden kısmen geliyor, ürün sayısına göre yön değiştiriyor (4b)"}
KAPASITELER = [10, 20, 30]  # bakılan müşteri payı (%); gerçek kapasite bilinmediği için birkaç nokta


def segment_verisi(eda):
    """Bölüm 4 gruplarına 'Ülke grubu' (Almanya / Diğer) ekler; CustomerId korunur (eşleştirme için)."""
    d = bolum4_verisi(eda)
    d["Ülke grubu"] = pd.Categorical(np.where(d["Ülke"].eq("Almanya"), "Almanya", "Diğer"),
                                     categories=["Almanya", "Diğer"], ordered=True)
    d["CustomerId"] = eda["CustomerId"].to_numpy()
    return d


def _kademeli_bol(d, maske, degiskenler, min_n, kosullar, sonuc):
    """Değişkenleri sırayla dener; bir bölme yalnızca bütün (boş olmayan) alt grupları n ≥ min_n ise yapılır."""
    for i, v in enumerate(degiskenler):
        alt = [(s, maske & d[v].eq(s).to_numpy()) for s in d[v].cat.categories]
        alt = [(s, m) for s, m in alt if m.sum() > 0]
        if len(alt) > 1 and all(m.sum() >= min_n for _, m in alt):
            kalan = degiskenler[:i] + degiskenler[i + 1:]
            for s, m in alt:
                _kademeli_bol(d, m, kalan, min_n, kosullar + [(v, str(s))], sonuc)
            return
    sonuc.append((kosullar, maske))


def _tanim(kosullar):
    if not kosullar:
        return "Tüm müşteriler"
    parca = []
    for v, s in kosullar:
        parca.append(f"Yaş {s}" if v == "Yaş grubu" else s)
    return " · ".join(parca)


def segmentasyon_kur(d, degiskenler=SEGMENT_DEGISKENLERI, once_ayrilan=SEGMENT_ONCE_AYRILAN, min_n=MIN_N):
    """Her müşteriyi tam olarak bir segmente atar. Döndürür: (segment kuralları listesi, müşteri → segment no).

    Prosedür: (1) once_ayrilan seviyesi tek segment olur; (2) kalan müşteriler `degiskenler` sırasıyla bölünür;
    bölme yalnızca bütün alt gruplar n ≥ min_n ise yapılır, olmazsa sıradaki değişken denenir.
    Kural ayrılma oranına bakmaz. ML'de aynı fonksiyon yalnızca eğitim verisine uygulanır.
    """
    v0, s0 = once_ayrilan
    on = d[v0].eq(s0).to_numpy()
    sonuc = [([(v0, s0)], on)]
    _kademeli_bol(d, ~on, [v for v in degiskenler], min_n, [], sonuc)
    atama = np.full(len(d), -1)
    for no, (_, m) in enumerate(sonuc):
        atama[m] = no
    if (atama < 0).any():
        raise ValueError("Bazı müşteriler hiçbir segmente atanmadı.")
    return [k for k, _ in sonuc], atama


def segment_tablosu(d, kurallar, atama, output_dir=None):
    """5a: segmentleri ayrılma oranına göre sıralar; kümülatif müşteri ve ayrılan paylarıyla birlikte."""
    y = d["Exited"].to_numpy()
    genel = 100 * y.mean()
    satirlar = []
    for no, kosullar in enumerate(kurallar):
        m = atama == no
        n, k = int(m.sum()), int(y[m].sum())
        alt, ust = (100 * float(v) for v in wilson_aralik(k, n))
        satirlar.append({"_no": no, "Tanım": _tanim(kosullar), "Müşteri sayısı": n, "Ayrılan sayısı": k,
                         "Ayrılma oranı (%)": 100 * k / n, "GA alt (%)": alt, "GA üst (%)": ust,
                         "Lift": (100 * k / n) / genel,
                         "Ortalamaya göre": ortalamaya_gore(alt, ust, 1.0, genel), "Güven": guven_etiketi(n, ust - alt)})
    t = pd.DataFrame(satirlar).sort_values(["Ayrılma oranı (%)", "Müşteri sayısı"], ascending=[False, False]).reset_index(drop=True)
    t.insert(0, "Segment", [f"S{i:02d}" for i in range(1, len(t) + 1)])
    t["Müşterilerin payı (%)"] = 100 * t["Müşteri sayısı"] / len(y)
    t["Ayrılanların payı (%)"] = 100 * t["Ayrılan sayısı"] / y.sum()
    t["Kümülatif müşteri (%)"] = t["Müşterilerin payı (%)"].cumsum()
    t["Kümülatif ayrılan (%)"] = t["Ayrılanların payı (%)"].cumsum()
    kod = dict(zip(t["_no"], t["Segment"]))
    musteri = pd.DataFrame({"CustomerId": d["CustomerId"].to_numpy(), "Segment": [kod[a] for a in atama]})
    musteri = musteri.merge(t[["Segment", "Tanım"]], on="Segment", how="left")
    t = t.drop(columns="_no")
    if output_dir is not None:
        tablo_kaydet(t, "05_segment_tablosu.csv", output_dir, index=False)
        tablo_kaydet(musteri, "05_musteri_segment.csv", output_dir, index=False)
    return t, musteri


def _egri(gruplar, y):
    """Grupları ayrılma oranına göre sıralayıp kümülatif (müşteri %, ayrılan %) noktaları üretir."""
    g = pd.DataFrame({"grup": gruplar, "y": y}).groupby("grup", observed=True)["y"].agg(["size", "sum"])
    g = g.assign(oran=g["sum"] / g["size"]).sort_values(["oran", "size"], ascending=[False, False])
    x = np.r_[0, 100 * g["size"].cumsum() / len(y)]
    yy = np.r_[0, 100 * g["sum"].cumsum() / y.sum()]
    return x, yy, len(g)


def _yakalanan(x, yy, kapasite):
    # Kapasite bir grubun ortasına düşerse grup içinden rastgele seçim varsayılır (doğrusal ara değer)
    return float(np.interp(kapasite, x, yy))


def kisitli_agac_gruplari(d, degiskenler, yaprak_sayisi, min_n=MIN_N):
    """Karşılaştırma: aynı değişkenler ve aynı segment sayısıyla kısıtlı CART (yaprakta ≥ min_n)."""
    from sklearn.tree import DecisionTreeClassifier

    X = pd.concat([pd.get_dummies(d[v], prefix=v, dtype=float) for v in degiskenler], axis=1)
    model = DecisionTreeClassifier(max_leaf_nodes=yaprak_sayisi, min_samples_leaf=min_n, random_state=0)
    model.fit(X, d["Exited"].to_numpy())
    return model.apply(X)


def yakalama_egrisi(d, atama, output_dir=None, kapasiteler=KAPASITELER):
    """5b: müşterilerin %X'ine bakılırsa ayrılanların yüzde kaçı yakalanır? Yöntemler aynı veride karşılaştırılır."""
    y = d["Exited"].to_numpy()
    oran = y.mean()
    agac = kisitli_agac_gruplari(d, SEGMENT_DEGISKENLERI, len(np.unique(atama)))
    yontemler = {
        "Yalnızca yaş": d["Yaş grubu"].astype(str).to_numpy(),
        "Yaş × ürün sayısı": (d["Yaş grubu"].astype(str) + " | " + d["Ürün sayısı"].astype(str)).to_numpy(),
        "Segmentasyon (5a)": atama,
        "Kısıtlı karar ağacı (karşılaştırma)": agac,
    }
    egriler = {ad: _egri(g, y) for ad, g in yontemler.items()}

    satirlar = []
    for ad, (x, yy, k) in [("Rastgele seçim", (np.array([0, 100]), np.array([0, 100]), None))] + list(egriler.items()) + \
            [("Kusursuz sınır", (np.array([0, 100 * oran, 100]), np.array([0, 100, 100]), None))]:
        kayit = {"Yöntem": ad, "Grup sayısı": k if k is not None else "—"}
        for c in kapasiteler:
            yak = _yakalanan(x, yy, c)
            kayit[f"%{c} müşteri → yakalanan ayrılan (%)"] = yak
            kayit[f"%{c} müşteride ayrılma oranı (%)"] = yak * 100 * oran / c
        satirlar.append(kayit)
    ozet = pd.DataFrame(satirlar)

    renk = {"Yalnızca yaş": RENKLER["gri"], "Yaş × ürün sayısı": RENKLER["acik_mavi"],
            "Segmentasyon (5a)": RENKLER["mavi"], "Kısıtlı karar ağacı (karşılaştırma)": RENKLER["mor"]}
    fig, ax = plt.subplots(figsize=(10, 7), layout="constrained")
    ax.plot([0, 100], [0, 100], color=RENKLER["gri"], linestyle=":", linewidth=1.5, label="Rastgele seçim")
    ax.plot([0, 100 * oran, 100], [0, 100, 100], color=RENKLER["turuncu"], linestyle="--", linewidth=1.2,
            label="Kusursuz sınır")
    for ad, (x, yy, k) in egriler.items():
        kalin = ad == "Segmentasyon (5a)"
        ax.plot(x, yy, color=renk[ad], linewidth=2.8 if kalin else 1.6, marker="o" if kalin else None,
                markersize=3.5, label=f"{ad} ({k} grup)", zorder=3 if kalin else 2)
    xs, ys, _ = egriler["Segmentasyon (5a)"]
    for c in kapasiteler:
        yak = _yakalanan(xs, ys, c)
        ax.axvline(c, color="#DDDDDD", linewidth=1, zorder=0)
        ax.annotate(f"%{c} → %{tr_sayi(yak, 0)}", xy=(c, yak), xytext=(c + 2, yak - 9), fontsize=9,
                    color=RENKLER["mavi"], arrowprops={"arrowstyle": "-", "color": RENKLER["mavi"]})
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 102)
    ax.set_xlabel("Bakılan müşterilerin payı (%) · en riskli gruptan başlayarak")
    ax.set_ylabel("Yakalanan ayrılanların payı (%)")
    ax.legend(loc="lower right", frameon=False)
    ax.set_title(f"Yakalama eğrisi | Tüm veri: {tr_sayi(len(y))} müşteri · aynı veride kurulup ölçüldü (iyimser)")
    if output_dir is not None:
        tablo_kaydet(ozet, "05_yakalama_ozeti.csv", output_dir, index=False)
        kaydet(fig, "05_yakalama_egrisi.png", output_dir)
    return ozet


def segment_grafigi(t, genel_oran, output_dir=None):
    """5a: segmentler riske göre; çubuk oran, çizgi %95 GA, renk güven; sağda n ve kümülatif yakalama."""
    t = t.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(12, 0.38 * len(t) + 1.8), layout="constrained")
    renk = t["Güven"].map(GUVEN_RENK)
    ax.barh(range(len(t)), t["Ayrılma oranı (%)"], color=renk, height=0.7)
    ax.errorbar(t["Ayrılma oranı (%)"], range(len(t)),
                xerr=[t["Ayrılma oranı (%)"] - t["GA alt (%)"], t["GA üst (%)"] - t["Ayrılma oranı (%)"]],
                fmt="none", ecolor=RENKLER["mor"], capsize=2.5, linewidth=1)
    for i, s in t.iterrows():
        ax.text(s["GA üst (%)"] + 1.2, i, f"%{tr_sayi(s['Ayrılma oranı (%)'], 1)} · n = {tr_sayi(s['Müşteri sayısı'])} · "
                f"kümülatif: müşteri %{tr_sayi(s['Kümülatif müşteri (%)'], 1)} → ayrılan %{tr_sayi(s['Kümülatif ayrılan (%)'], 1)}",
                va="center", fontsize=8)
    ax.set_yticks(range(len(t)), [f"{a} · {b}" for a, b in zip(t["Segment"], t["Tanım"])], fontsize=8.5)
    ax.axvline(100 * genel_oran, color=RENKLER["turuncu"], linestyle="--", linewidth=1.5)
    ax.set_xlim(0, 160)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("Ayrılma oranı (%) · çizgi: %95 güven aralığı · kesik çizgi: genel oran")
    ax.grid(axis="y", visible=False)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for c in GUVEN_RENK.values()],
              labels=[f"Güven: {k}" for k in GUVEN_RENK], loc="lower right", frameon=False, fontsize=9)
    ax.set_title(f"Segmentler riske göre ({len(t)} segment, her müşteri tek segmentte) | Tüm veri: "
                 f"{tr_sayi(int(t['Müşteri sayısı'].sum()))} müşteri · aynı veride kurulup ölçüldü")
    if output_dir is not None:
        kaydet(fig, "05_segment_grafigi.png", output_dir)
    return fig


# ---------------------------------------------------------------------------
# Bölüm 6: özet. Sayılar önceki bölümlerin çıktılarından okunur; veri veya kural değişirse özet de güncellenir.
# ---------------------------------------------------------------------------
def eda_ozeti(veri, etki, yapraklar, segmentler, yakalama):
    """6c: EDA'nın yönetici özetini Markdown metni olarak üretir (sayılar elle yazılmaz)."""
    y = veri["Exited"]
    n, k = len(y), int(y.sum())
    ilk_iki = etki.head(2)
    guc = [f"{r['Değişken'].lower()} ({'AUC' if r['Ölçü'] == 'AUC' else 'V'} = {tr_sayi(r['Değer'], 2)})"
           for _, r in ilk_iki.iterrows()]
    s01 = segmentler[segmentler["Tanım"].eq("3+ ürün")].iloc[0]
    de = veri["Geography"].eq("Germany")
    de_musteri, de_ayrilan = 100 * de.mean(), 100 * y[de].sum() / k
    de_oran = 100 * y[de].mean()
    yaprak = yapraklar[yapraklar["Ortalamaya göre"].eq(ORT_YUKSEK)].sort_values("Ayrılanların payı (%)", ascending=False).iloc[0]
    seg = yakalama[yakalama["Yöntem"].eq("Segmentasyon (5a)")].iloc[0]
    kap = " · ".join(f"%{c} → %{tr_sayi(seg[f'%{c} müşteri → yakalanan ayrılan (%)'], 1)}" for c in KAPASITELER)
    yas = yakalama[yakalama["Yöntem"].eq("Yalnızca yaş")].iloc[0]["%20 müşteri → yakalanan ayrılan (%)"]
    satirlar = [
        f"1. **Genel tablo:** {tr_sayi(n)} müşteriden {tr_sayi(k)} kişi ayrılmış; ayrılma oranı %{tr_sayi(100 * k / n, 2)}.",
        f"2. **En güçlü iki değişken:** {guc[0]} ve {guc[1]}. Yaş ile risk arasındaki ilişki ters U biçiminde; "
        "ürün sayısında en düşük risk 2 üründe.",
        f"3. **İki risk tipi:** 3+ ürünlüler küçük ama çok yoğun bir risk (n = {tr_sayi(s01['Müşteri sayısı'])}, "
        f"oran %{tr_sayi(s01['Ayrılma oranı (%)'], 1)}); Almanya geniş bir risk havuzu (müşteri payı %{tr_sayi(de_musteri, 1)}, "
        f"ayrılan payı %{tr_sayi(de_ayrilan, 1)}, oran %{tr_sayi(de_oran, 1)}).",
        f"4. **Risk kombinasyonlarda yoğunlaşıyor:** Karar ağacına göre en çok ayrılanı içeren grup "
        f"\"{yaprak['Kural']}\" (müşteri payı %{tr_sayi(yaprak['Müşterilerin payı (%)'], 1)}, ayrılan payı "
        f"%{tr_sayi(yaprak['Ayrılanların payı (%)'], 1)}, oran %{tr_sayi(yaprak['Ayrılma oranı (%)'], 1)}).",
        f"5. **Kapasite:** {len(segmentler)} segmentlik kural tabanlı önceliklendirmeyle bakılan müşteri payı → yakalanan "
        f"ayrılan payı: {kap}. Karşılaştırma: yalnızca yaşa göre sıralamada %20 kapasitede yakalanan pay %{tr_sayi(yas, 1)}.",
        "6. **Sınır:** Bu sayılar aynı veride kurulup ölçüldü; bağımsız tahmin performansı değildir. "
        "Bulgular ilişkiseldir, nedensellik veya teklif etkisi göstermez; veri kökeni belgelenmemiştir. "
        "İlk EDA tüm verideydi; sonraki test bu keşiften tamamen bağımsız değildir.",
    ]
    return "\n".join(satirlar)
