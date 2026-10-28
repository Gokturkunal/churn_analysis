"""Tüm veri üzerinde betimsel EDA; test, özellik seçimi veya ML içermez."""

from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd


NUMERIC = ["CreditScore", "Age", "Tenure", "Balance", "NumOfProducts", "EstimatedSalary"]
CONTINUOUS = ["Age", "CreditScore", "Balance", "EstimatedSalary"]
CATEGORICAL = ["Geography", "Gender", "HasCrCard", "IsActiveMember", "NumOfProducts", "Tenure", "BakiyeDurumu"]
NAMES = {
    "CreditScore": "Kredi puanı", "Age": "Yaş", "Tenure": "Banka ile ilişki süresi",
    "Balance": "Bakiye", "NumOfProducts": "Ürün sayısı", "EstimatedSalary": "Tahmini gelir",
    "Geography": "Ülke", "Gender": "Cinsiyet", "HasCrCard": "Kredi kartı",
    "IsActiveMember": "Aktiflik", "BakiyeDurumu": "Bakiye durumu",
}
MAPS = {
    "Geography": {"France": "Fransa", "Germany": "Almanya", "Spain": "İspanya"},
    "Gender": {"Female": "Kadın", "Male": "Erkek"},
    "HasCrCard": {0: "Kartı yok", 1: "Kartı var"},
    "IsActiveMember": {0: "Aktif değil", 1: "Aktif"},
    "NumOfProducts": {i: f"{i} ürün" for i in range(1, 5)},
    "Tenure": {i: str(i) for i in range(11)},
    "BakiyeDurumu": {"Sıfır": "Sıfır", "Pozitif": "Pozitif"},
}
BLUE = LinearSegmentedColormap.from_list("churn_blue", ["#F6F8FA", "#5C9FB7"])
DIVERGING = LinearSegmentedColormap.from_list("churn_corr", ["#5C9FB7", "#FFFFFF", "#C97A5A"])


def tr_sayi(value, decimals=0):
    if pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def hazirla(df):
    """Kaynağı değiştirmeden gerekli müşteri alanlarının kopyasını hazırlar."""
    required = ["CustomerId", *NUMERIC, "Geography", "Gender", "HasCrCard", "IsActiveMember", "Exited"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"df içinde gereken sütunlar eksik: {missing}")
    eda = df[required].copy(deep=True)
    if eda.empty or eda.isna().any().any():
        raise ValueError("Bu hücreler dolu müşteri tablosunu bekliyor; boş/eksik kayıtları önce inceleyin.")
    if not eda["CustomerId"].is_unique:
        raise ValueError("CustomerId benzersiz olmalı; müşteri başına bir kayıt bekleniyor.")
    for col in [*NUMERIC, "HasCrCard", "IsActiveMember", "Exited"]:
        eda[col] = pd.to_numeric(eda[col], errors="raise")
        if not np.isfinite(eda[col].to_numpy(dtype=float)).all():
            raise ValueError(f"{col} içinde sonlu olmayan sayı var.")
    if set(eda["Exited"].unique()) != {0, 1}:
        raise ValueError("Exited hem 0 hem 1 sınıfını içermeli.")
    if (eda["Balance"] < 0).any():
        raise ValueError("Negatif bakiye bulundu; sıfır/pozitif kapsamını önce yeniden belirleyin.")
    eda["BakiyeDurumu"] = np.where(eda["Balance"].eq(0), "Sıfır", "Pozitif")
    for col in CATEGORICAL:
        if not eda[col].isin(MAPS[col]).all():
            raise ValueError(f"{col} içinde tanımlı kategoriler dışında değer var; kategori listesini inceleyin.")
    return eda


def _category(eda, col):
    if col not in CATEGORICAL:
        raise ValueError(f"Desteklenen kategorik alanlar: {CATEGORICAL}")
    mapping = MAPS[col]
    return pd.Series(
        pd.Categorical(eda[col].map(mapping), categories=list(mapping.values()), ordered=True),
        index=eda.index, name=NAMES[col],
    )


def _table(frame, name, output_dir, index=False):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    frame.to_csv(directory / name, index=index, encoding="utf-8-sig")


def _figure(fig, name, output_dir):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(directory / name, dpi=150, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def korelasyon_heatmap(eda, output_dir):
    """Yalnızca altı sayısal özellik; kimlik ve hedef matrise girmez."""
    results = {}
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, method in zip(axes, ["pearson", "spearman"]):
        corr = eda[NUMERIC].corr(method=method)
        results[method] = corr
        _table(corr, f"01_korelasyon_{method}.csv", output_dir, index=True)
        im = ax.imshow(np.ma.masked_invalid(corr.to_numpy()), vmin=-1, vmax=1, cmap=DIVERGING)
        labels = [NAMES[c] for c in NUMERIC]
        ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
        ax.set_yticks(range(len(labels)), labels)
        for row in range(len(labels)):
            for col in range(len(labels)):
                ax.text(col, row, tr_sayi(corr.iloc[row, col], 2), ha="center", va="center", fontsize=9)
        ax.set_title(f"{method.title()} korelasyonu\nMüşteri: {tr_sayi(len(eda))}")
        fig.colorbar(im, ax=ax, shrink=0.75)
    _figure(fig, "01_korelasyon_heatmap.png", output_dir)
    return results


def kategorik_tarama(eda, output_dir):
    """Yedi kategorik/kesikli alanın 21 çiftinde bütün kombinasyonları saklar."""
    records = []
    for first, second in combinations(CATEGORICAL, 2):
        counts = pd.crosstab(_category(eda, first), _category(eda, second), dropna=False)
        row_totals, col_totals = counts.sum(axis=1), counts.sum(axis=0)
        for row in counts.index:
            for col in counts.columns:
                n = int(counts.loc[row, col])
                row_n, col_n = int(row_totals.loc[row]), int(col_totals.loc[col])
                records.append({
                    "Alan 1": first, "Grup 1": str(row), "Alan 2": second, "Grup 2": str(col),
                    "Müşteri sayısı": n, "Satır toplamı": row_n, "Sütun toplamı": col_n,
                    "Satır payı (%)": 100 * n / row_n if row_n else np.nan,
                    "Sütun payı (%)": 100 * n / col_n if col_n else np.nan,
                })
    result = pd.DataFrame.from_records(records)
    _table(result, "02_tum_kategorik_ciftler.csv", output_dir)
    return result


def kategori_heatmap(eda, satir, sutun, output_dir):
    """Renk satır içi yüzdeyi; yazı müşteri sayısını ve yüzdeyi gösterir."""
    if satir == sutun:
        raise ValueError("İki farklı alan seçin.")
    counts = pd.crosstab(_category(eda, satir), _category(eda, sutun), dropna=False)
    pct = counts.div(counts.sum(axis=1).replace(0, np.nan), axis=0) * 100
    fig, ax = plt.subplots(figsize=(max(7, 1.35 * len(counts.columns)), max(4, 0.7 * len(counts))))
    im = ax.imshow(np.ma.masked_invalid(pct.to_numpy()), cmap=BLUE, vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(counts.columns)), counts.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(counts.index)), counts.index)
    for i in range(len(counts)):
        for j in range(len(counts.columns)):
            rate = pct.iloc[i, j]
            text = f"{tr_sayi(counts.iloc[i, j])}\n" + (f"%{tr_sayi(rate, 2)}" if pd.notna(rate) else "—")
            ax.text(j, i, text, ha="center", va="center", fontsize=10)
    ax.set_xlabel(NAMES[sutun])
    ax.set_ylabel(NAMES[satir])
    ax.set_title(f"{NAMES[satir]} × {NAMES[sutun]} | Müşteri: {tr_sayi(len(eda))}\nHücre: müşteri sayısı ve satır içi pay")
    fig.colorbar(im, ax=ax, label="Satır içi pay (%)")
    prefix = f"02_{satir}_{sutun}"
    _table(counts, f"{prefix}_sayilar.csv", output_dir, index=True)
    _table(pct, f"{prefix}_satir_paylari.csv", output_dir, index=True)
    _figure(fig, f"{prefix}_heatmap.png", output_dir)
    return {"sayilar": counts, "satir_paylari": pct}


def kategorik_hedef(eda, output_dir):
    """Kategorik ve kesikli gruplarda sayı, ayrılan sayısı ve ayrılma oranı."""
    records = []
    overall = 100 * eda["Exited"].mean()
    fig, axes = plt.subplots(4, 2, figsize=(16, 20))
    for ax, field in zip(axes.flat, CATEGORICAL):
        grouped = eda.groupby(_category(eda, field), observed=False)["Exited"].agg(
            **{"Müşteri sayısı": "size", "Ayrılan sayısı": "sum"}
        )
        grouped["Ayrılma oranı (%)"] = grouped["Ayrılan sayısı"].div(grouped["Müşteri sayısı"].replace(0, np.nan)) * 100
        grouped["Genel orandan fark (yüzde puan)"] = grouped["Ayrılma oranı (%)"] - overall
        for label, row in grouped.iterrows():
            records.append({"Alan": field, "Grup": str(label), **row.to_dict()})
        rates = grouped["Ayrılma oranı (%)"]
        ax.barh(range(len(grouped)), rates.fillna(0), color="#5C9FB7", height=0.65)
        ax.set_yticks(range(len(grouped)), grouped.index)
        ax.invert_yaxis()
        for pos, (_, row) in enumerate(grouped.iterrows()):
            rate = row["Ayrılma oranı (%)"]
            label = f"%{tr_sayi(rate, 2)}" if pd.notna(rate) else "—"
            label += f" · {tr_sayi(row['Ayrılan sayısı'])}/{tr_sayi(row['Müşteri sayısı'])}"
            ax.text((rate if pd.notna(rate) else 0) + 1, pos, label, va="center", fontsize=9)
        ax.axvline(overall, color="#C97A5A", linestyle="--", linewidth=1.5)
        ax.set_xlim(0, 135)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_title(NAMES[field])
        ax.set_xlabel("Ayrılma oranı (%) | Etiket: oran · ayrılan/müşteri")
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#EEEEEE")
        for side in ["top", "right"]:
            ax.spines[side].set_visible(False)
    for ax in list(axes.flat)[len(CATEGORICAL):]:
        ax.set_visible(False)
    fig.suptitle(f"Gruplara göre ayrılma | Tüm veri: {tr_sayi(len(eda))} müşteri\nKesik çizgi: genel oran %{tr_sayi(overall, 2)}", fontsize=14)
    result = pd.DataFrame.from_records(records)
    result[["Müşteri sayısı", "Ayrılan sayısı"]] = result[["Müşteri sayısı", "Ayrılan sayısı"]].astype(int)
    _table(result, "03_kategorik_hedef_ozeti.csv", output_dir)
    _figure(fig, "03_kategorik_hedef.png", output_dir)
    return result


def sayisal_hedef(eda, output_dir):
    """Dört sayısal ölçümün hedef gruplarındaki dağılımı; sıfır bakiyeler korunur."""
    records = []
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    for ax, field in zip(axes.flat, CONTINUOUS):
        groups = [eda.loc[eda["Exited"].eq(target), field] for target in [0, 1]]
        labels = [f"{label}\nn={tr_sayi(len(values))}" for label, values in zip(["Devam ediyor", "Ayrıldı"], groups)]
        box = ax.boxplot(groups, orientation="horizontal", tick_labels=labels, patch_artist=True,
                         medianprops={"color": "#666599", "linewidth": 2},
                         flierprops={"marker": "o", "markersize": 2, "alpha": 0.25, "markeredgecolor": "#707070"})
        for patch, color in zip(box["boxes"], ["#5C9FB7", "#C97A5A"]):
            patch.set_facecolor(color)
            patch.set_alpha(0.65)
        for target, values in zip([0, 1], groups):
            records.append({
                "Alan": field, "Durum": "Devam ediyor" if target == 0 else "Ayrıldı",
                "Müşteri sayısı": len(values), "Ortalama": values.mean(), "Medyan": values.median(),
                "Q1": values.quantile(0.25), "Q3": values.quantile(0.75),
                "Standart sapma": values.std(), "Minimum": values.min(), "Maksimum": values.max(),
            })
        ax.set_title(NAMES[field])
        ax.set_xlabel("Tutar (birim/dönem bilinmiyor)" if field in ["Balance", "EstimatedSalary"] else NAMES[field])
        ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: tr_sayi(value)))
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#EEEEEE")
        for side in ["top", "right"]:
            ax.spines[side].set_visible(False)
    fig.suptitle("Ayrılan ve kalan müşterilerde dağılımlar | Tüm veri\nKutu: Q1–Q3; çizgi: medyan; bıyık: 1,5 × IQR; noktalar: uç adayları", fontsize=13)
    result = pd.DataFrame.from_records(records)
    _table(result, "04_sayisal_hedef_ozeti.csv", output_dir)
    _figure(fig, "04_sayisal_hedef.png", output_dir)
    return result
