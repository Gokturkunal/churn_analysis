"""Kapasite sözleşmesinin sınır ve regresyon kontrolleri; model eğitmez."""

import itertools
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from churn_analysis import ml
from churn_analysis.kapasite import beklenen_yakalama, kapasite_adedi, liste_secimi, sira_ve_dilim


class KapasiteTestleri(unittest.TestCase):
    def test_asagi_yuvarlama(self):
        self.assertEqual(kapasite_adedi(1501, 20), 300)
        self.assertEqual(kapasite_adedi(1499, 20), 299)
        self.assertEqual(kapasite_adedi(1501, 50), 750)
        self.assertEqual(kapasite_adedi(5, 50), 2)

    def test_ondalik_kayan_nokta_siniri(self):
        self.assertEqual(kapasite_adedi(100, 29), 29)
        self.assertEqual(kapasite_adedi(10000, 0.29), 29)

    def test_kapasite_ust_siniri_asilmaz(self):
        from decimal import Decimal
        for n in [0, 1, 3, 99, 1499, 1501]:
            for c in [0, 0.29, 5, 20, 33.3, 50, 99.9, 100]:
                k = kapasite_adedi(n, c)
                self.assertGreaterEqual(k, 0)
                self.assertLessEqual(Decimal(k), Decimal(n) * Decimal(str(c)) / 100)

    def test_gecersiz_kapasite(self):
        for c in [-1, 101, np.nan, np.inf, True, "20", None]:
            with self.subTest(c=c), self.assertRaises(ValueError):
                kapasite_adedi(10, c)

    def test_gecersiz_musteri_sayisi(self):
        for n in [-1, 1.5, True]:
            with self.subTest(n=n), self.assertRaises(ValueError):
                kapasite_adedi(n, 20)

    def test_bozuk_skor_sessizce_dusurulmez(self):
        for s in [[.1, np.nan], [.1, np.inf], [.1, -0.1], [.1, 1.1], [[.1], [.2]]]:
            with self.subTest(s=s), self.assertRaises(ValueError):
                beklenen_yakalama([0, 1], s, 50)

    def test_hedef_kontrolu(self):
        for y in [[0], [0, 2], [0, np.nan], [[0], [1]]]:
            with self.subTest(y=y), self.assertRaises(ValueError):
                beklenen_yakalama(y, [.1, .9], 50)

    def test_sifir_kapasite(self):
        r = beklenen_yakalama([0, 1], [.1, .9], 0)
        self.assertEqual(r["Eşit skorlarda beklenen ayrılan"], 0)
        self.assertEqual(r["Yakalanan pay"], 0)
        self.assertTrue(np.isnan(r["İsabet"]))
        self.assertEqual(len(liste_secimi([.1, .9], 0)[0]), 0)

    def test_tam_kapasite(self):
        r = beklenen_yakalama([0, 1, 1], [.1, .5, .5], 100)
        self.assertEqual(r["Yakalanan pay"], 1)
        self.assertAlmostEqual(r["İsabet"], 2 / 3)
        self.assertEqual(len(liste_secimi([.1, .5, .5], 100)[0]), 3)

    def test_bos_veri(self):
        r = beklenen_yakalama([], [], 20)
        self.assertEqual(r["Bakılan müşteri"], 0)
        self.assertTrue(np.isnan(r["Yakalanan pay"]))
        self.assertEqual(len(liste_secimi([], 20)[0]), 0)

    def test_ayrilan_yoksa_recall_tanimsiz(self):
        r = beklenen_yakalama([0, 0], [.1, .9], 50)
        self.assertTrue(np.isnan(r["Yakalanan pay"]))
        self.assertEqual(r["İsabet"], 0)

    def test_esitlik_beklentisi_olasi_listelerin_ortalamasi(self):
        y, s = np.array([1, 1, 0, 0]), np.array([.9, .5, .5, .5])
        olasi = [y[[0, *c]].sum() for c in itertools.combinations([1, 2, 3], 1)]
        self.assertAlmostEqual(beklenen_yakalama(y, s, 50)["Eşit skorlarda beklenen ayrılan"], np.mean(olasi))

    def test_dummy_beklentisi_gercek_kapasite_payi(self):
        r = beklenen_yakalama([1, 0, 0, 0, 1], [.4] * 5, 50)
        self.assertAlmostEqual(r["Yakalanan pay"], 2 / 5)

    def test_somut_liste_hedeften_bagimsiz(self):
        ids, s = np.array([11, 13, 12, 14]), np.array([.9, .8, .8, .1])
        secilen, _ = liste_secimi(s, 50, ids)
        self.assertEqual(ids[secilen].tolist(), [11, 12])
        # Fonksiyon y almaz; etiket değiştirmek seçimi etkileyemez.
        for y in [[1, 1, 0, 0], [0, 0, 1, 1]]:
            t = ml.kapasite_tablosu(y, s, [50], musteri_id=ids)
            self.assertEqual(t.iloc[0]["Bakılan müşteri"], 2)

    def test_satir_sirasi_degisse_secim_ayni(self):
        ids, s = np.array([11, 13, 12, 14]), np.array([.9, .8, .8, .1])
        for perm in itertools.permutations(range(4)):
            p = np.array(perm)
            positions, _ = liste_secimi(s[p], 50, ids[p])
            self.assertEqual(ids[p][positions].tolist(), [11, 12])

    def test_kimliksiz_sinir_esitliginde_hata(self):
        with self.assertRaisesRegex(ValueError, "CustomerId"):
            liste_secimi([.9, .8, .8, .1], 50)

    def test_kimliksiz_sinir_esitligi_yoksa_kullanilabilir(self):
        self.assertEqual(liste_secimi([.9, .8, .1, .1], 50)[0].tolist(), [0, 1])

    def test_kimlik_kontrolu(self):
        for ids in [[1], [1, 1], [1, None], [1, np.inf]]:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                liste_secimi([.9, .8], 50, ids)

    def test_liste_ve_disarida_kalanlar_tum_musteriler(self):
        for c in [0, 20, 50, 100]:
            positions, mask = liste_secimi([.9, .8, .8, .1], c, [11, 13, 12, 14])
            self.assertEqual(int(mask.sum()), kapasite_adedi(4, c))
            self.assertEqual(int(mask.sum() + (~mask).sum()), 4)
            self.assertEqual(set(positions), set(np.flatnonzero(mask)))

    def test_isabet_paydasi_secilen_adet(self):
        r = ml.olcutler([1, 0, 0], [.9, .5, .1], [50])
        self.assertEqual(r["%50 kapasitede isabet"], 1)

    def test_kapasite_tablosu_sifir_ve_tam(self):
        t = ml.kapasite_tablosu([0, 1], [.1, .9], [0, 100], musteri_id=[1, 2])
        self.assertEqual(t["Bakılan müşteri"].tolist(), [0, 2])
        self.assertTrue(np.isnan(t.iloc[0]["Skor eşiği"]))
        self.assertEqual(t.iloc[0]["Beklenen ayrılan (skor toplamı)"], 0)

    def test_grup_ve_profil_ayni_listeyi_kullanir(self):
        veri = pd.DataFrame({"CustomerId": [11, 13, 12, 14], "Age": [30, 40, 50, 60],
            "NumOfProducts": [1] * 4, "Balance": [0] * 4, "CreditScore": [600] * 4,
            "Tenure": [2] * 4, "EstimatedSalary": [100] * 4})
        y, s = np.array([1, 1, 0, 0]), np.array([.9, .8, .8, .1])
        g = ml.grup_performansi(y, s, {"Grup": ["Tümü"] * 4}, 50, musteri_id=veri.CustomerId)
        _, p = ml.kacirilan_profili(veri, y, s, 50)
        self.assertEqual(p["Yakalanan ayrılan"], 1)
        self.assertEqual(g.iloc[0]["Yakalanan ayrılan payı"], .5)

    def test_brier_gecersiz_skoru_kirpmaz(self):
        with self.assertRaises(ValueError):
            ml.olcutler([0, 1], [-.1, 1.1])

    def test_profil_kapasite_uclarinda_bos_alt_gruplar(self):
        import warnings
        veri = pd.DataFrame({"CustomerId": [1, 2], "Age": [30, 40], "NumOfProducts": [1, 2],
            "Balance": [0, 100], "CreditScore": [600, 700], "Tenure": [1, 2], "EstimatedSalary": [100, 200]})
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            t0, p0 = ml.kacirilan_profili(veri, [0, 1], [.1, .9], 0)
            t1, p1 = ml.kacirilan_profili(veri, [0, 1], [.1, .9], 100)
        self.assertEqual(p0["Yakalanan ayrılan"], 0)
        self.assertEqual(p1["Kaçırılan ayrılan"], 0)
        self.assertTrue(t0["Yakalanan ayrılanlar (medyan)"].isna().all())
        self.assertTrue(t1["Kaçırılan ayrılanlar (medyan)"].isna().all())

    def test_tek_sinifta_genel_olcutler(self):
        r = ml.olcutler([0, 0], [.1, .2], [0, 50])
        self.assertTrue(np.isnan(r["AP"]))
        self.assertTrue(np.isnan(r["ROC AUC"]))
        self.assertEqual(r["%50 kapasitede isabet"], 0)

    def test_sira_ve_dilim_listeyle_uyusur(self):
        ids = np.arange(1501)[::-1]
        s = np.full(1501, .5)
        ranks, bands = sira_ve_dilim(s, ids)
        for c in [10, 20, 30, 50, 100]:
            _, mask = liste_secimi(s, c, ids)
            np.testing.assert_array_equal(mask, ranks <= kapasite_adedi(1501, c))
        self.assertEqual(pd.Series(bands).value_counts().to_dict(),
            {"Diğer": 1051, "İlk %10": 150, "%10–20": 150, "%20–30": 150})

    def test_sira_ve_dilim_kucuk_veride_kapasiteyi_asmaz(self):
        ranks, bands = sira_ve_dilim([.9, .8, .7], [1, 2, 3])
        np.testing.assert_array_equal(ranks, [1, 2, 3])
        self.assertTrue((bands == "Diğer").all())  # floor(3 * %30) = 0


if __name__ == "__main__":
    unittest.main()
