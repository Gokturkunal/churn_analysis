"""Seçili kapasitedeki genel model listesinin grup dökümü (Power BI Sayfa 3 tablosunun Python karşılığı).

Liste, kayıtlı test skorlarından ortak kapasite kuralıyla bir kez kurulur (skor azalan, eşitlikte
CustomerId artan); gruplar bu tek listenin içinde sayılır, grup içinde yeniden sıralama yapılmaz.
Model eğitmez; Exited yalnızca sayım için kullanılır. Çıktı: reports/validation/<klasör>/beklenen_degerler.csv

Kullanım: .venv\\Scripts\\python.exe scripts\\liste_grup_dokumu.py reports/validation/liste_grup_dokumu_2026-10-28
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "src"))
from churn_analysis.eda import wilson_aralik  # noqa: E402
from churn_analysis.kapasite import liste_secimi  # noqa: E402

KAPASITELER = (10, 20, 30, 50)


def gruplar(veri):
    """Sayfa 4 ile aynı 10 grup; yaş 18–39 birleşik (Power BI'da AgeOrder 1–2)."""
    yas = pd.cut(veri["Age"], [0, 40, 50, 60, 70, np.inf], right=False,
                 labels=["18–39", "40–49", "50–59", "60–69", "70+"]).astype(str)
    return {
        "Cinsiyet": veri["Gender"].map({"Female": "Kadın", "Male": "Erkek"}),
        "Ülke": veri["Geography"].map({"France": "Fransa", "Germany": "Almanya", "Spain": "İspanya"}),
        "Yaş grubu": yas,
    }


def dokum(veri, skor, kapasite):
    _, listede = liste_secimi(skor, kapasite, veri["CustomerId"])
    y = veri["Exited"].to_numpy()
    satirlar = []
    for degisken, etiket in gruplar(veri).items():
        etiket = etiket.to_numpy()
        for grup in pd.unique(etiket):
            g = etiket == grup
            n, k = int(g.sum()), int(y[g].sum())
            l, yak = int(listede[g].sum()), int((listede[g] & (y[g] == 1)).sum())
            alt, ust = (float(v) for v in wilson_aralik(yak, k))
            satirlar.append({
                "Kapasite": kapasite, "Değişken": degisken, "Grup": grup,
                "Müşteri": n, "Ayrılan": k, "Listede": l, "Yakalanan": yak,
                "Kaçırılan": k - yak, "Listede ayrılmayan": l - yak,
                "Liste dışı ayrılmayan": n - k - (l - yak),
                "Yakalanan payı (%)": round(100 * yak / k, 1) if k else np.nan,
                "GA alt (%)": round(100 * alt, 1), "GA üst (%)": round(100 * ust, 1),
                "İsabet (%)": round(100 * yak / l, 1) if l else np.nan,
            })
    return pd.DataFrame(satirlar)


def main(cikti):
    skorlar = pd.read_csv(KOK / "data/processed/ml_test_skorlari.csv", encoding="utf-8-sig")
    ham = pd.read_csv(KOK / "Churn_Modelling.csv", usecols=["CustomerId", "Age", "Gender", "Geography", "Exited"])
    veri = skorlar[["CustomerId", "Model skoru"]].merge(ham, on="CustomerId", how="left", validate="one_to_one")
    if len(veri) != 1501 or veri.isna().any().any():
        raise ValueError("1.501 eşleşen test müşterisi bekleniyordu.")
    tablo = pd.concat([dokum(veri, veri["Model skoru"].to_numpy(), k) for k in KAPASITELER], ignore_index=True)
    hedef = KOK / cikti
    hedef.mkdir(parents=True, exist_ok=True)
    tablo.to_csv(hedef / "beklenen_degerler.csv", index=False, encoding="utf-8-sig")
    return tablo


if __name__ == "__main__":
    t = main(sys.argv[1] if len(sys.argv) > 1 else "reports/validation/liste_grup_dokumu_2026-10-28")
    pd.set_option("display.width", 200)
    print(t.to_string(index=False))
