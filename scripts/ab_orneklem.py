"""Pilot A/B testi için grup başına gereken müşteri sayısı (iki oran farkı, çift yönlü z testi).

Varsayımlar raporda açıkça yazılır: kontrol grubunda ayrılma oranı, test setinde %20 model listesinin
gözlenen ayrılma oranıdır (187 / 300); teklif etkisi "listedeki ayrılanların tutulan payı" olarak ifade edilir
ve Kapasite Senaryosu'ndaki başarı oranıyla aynı anlamdadır. Veri görülmeden etki uydurulmaz; tablo
birkaç olası etki için hesaplanır. Kullanım: .venv\\Scripts\\python.exe scripts\\ab_orneklem.py
"""

from math import ceil, sqrt

from scipy.stats import norm

KONTROL = 187 / 300  # %20 model listesinde gözlenen ayrılma oranı (son test)
ALFA, GUC = 0.05, 0.80


def grup_basina(p1, p2, alfa=ALFA, guc=GUC):
    """İki bağımsız oran için grup başına örneklem (eşit gruplar, havuzlanmış varyanslı klasik formül)."""
    za, zb = norm.ppf(1 - alfa / 2), norm.ppf(guc)
    p = (p1 + p2) / 2
    pay = za * sqrt(2 * p * (1 - p)) + zb * sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return ceil(pay ** 2 / (p1 - p2) ** 2)


if __name__ == "__main__":
    print(f"Kontrol ayrılma oranı: %{100 * KONTROL:.1f}; alfa {ALFA}, güç {GUC}")
    print("Tutulan pay | Teklif grubu ayrılma | Fark (puan) | Grup başına | Toplam")
    for basari in (0.10, 0.16, 0.20, 0.25, 0.30):
        p2 = KONTROL * (1 - basari)
        n = grup_basina(KONTROL, p2)
        print(f"%{100 * basari:.0f} | %{100 * p2:.1f} | {100 * (KONTROL - p2):.1f} | {n} | {2 * n}")
