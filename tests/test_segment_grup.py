"""Boş/küçük segment geri dönüşü ve sabit listede grup belirsizliği kontrolleri."""
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.exceptions import NotFittedError
from sklearn.model_selection import cross_val_predict, StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from churn_analysis.ml import SegmentKurali, grup_performansi
from churn_analysis.powerbi_cikti import sayfa4_grup_tablosu


def girdiler(urunler):
    return pd.DataFrame({"Age": [35] * len(urunler), "NumOfProducts": urunler,
                         "Geography": ["France"] * len(urunler)})


class SegmentTestleri(unittest.TestCase):
    def test_egitimde_olmayan_ozel_segment(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            m = SegmentKurali().fit(girdiler([1, 2, 1, 2]), [0, 1, 0, 1])
            p = m.predict_proba(girdiler([3]))
        np.testing.assert_allclose(p, [[.5, .5]])
        self.assertTrue(m.tahmin_aciklamasi(girdiler([3])).iloc[0]["Geri dönüş kullanıldı"])

    def test_egitimde_yalniz_ozel_segment(self):
        m = SegmentKurali(min_n=2).fit(girdiler([3, 3, 3, 3]), [0, 1, 0, 1])
        np.testing.assert_allclose(m.predict_proba(girdiler([1])), [[.5, .5]])

    def test_kucuk_segment_kendi_uc_oranini_kullanmaz(self):
        m = SegmentKurali(min_n=3).fit(girdiler([1, 1, 1, 1, 3]), [0, 0, 1, 0, 1])
        self.assertAlmostEqual(m.predict_proba(girdiler([3]))[0, 1], .4)
        self.assertIn("küçük", m.tahmin_aciklamasi(girdiler([3])).iloc[0]["Skor kaynağı"])

    def test_esigi_saglayan_segment_kendi_oranini_kullanir(self):
        m = SegmentKurali(min_n=2).fit(girdiler([1, 1, 3, 3]), [0, 0, 1, 1])
        self.assertEqual(m.predict_proba(girdiler([3]))[0, 1], 1)
        self.assertFalse(m.tahmin_aciklamasi(girdiler([3])).iloc[0]["Geri dönüş kullanıldı"])

    def test_bilinmeyen_ulke_genel_egitim_orani(self):
        m = SegmentKurali(min_n=1).fit(girdiler([1, 1, 3, 3]), [0, 0, 1, 1])
        yeni = girdiler([3]);yeni["Geography"] = "Italy"
        np.testing.assert_allclose(m.predict_proba(yeni), [[.5, .5]])
        self.assertEqual(m.ata(yeni)[0], -1)

    def test_genel_oran_tahmin_kitlesinden_ogrenilmez(self):
        m = SegmentKurali().fit(girdiler([1, 1, 1, 1]), [0, 0, 0, 1])
        p = m.predict_proba(girdiler([3] * 100))
        np.testing.assert_allclose(p[:, 1], .25)
        self.assertEqual(m.genel_oran_, .25)

    def test_bos_egitim_reddedilir(self):
        with self.assertRaises(ValueError):
            SegmentKurali().fit(girdiler([]), [])

    def test_bos_tahmin_sekli(self):
        m = SegmentKurali().fit(girdiler([1, 2]), [0, 1])
        self.assertEqual(m.predict_proba(girdiler([])).shape, (0, 2))

    def test_tek_hedef_sinifi(self):
        for target in [0, 1]:
            m = SegmentKurali().fit(girdiler([1, 2]), [target, target])
            np.testing.assert_allclose(m.predict_proba(girdiler([3]))[0], [1 - target, target])

    def test_fit_oncesi_tahmin(self):
        with self.assertRaises(NotFittedError):
            SegmentKurali().predict_proba(girdiler([1]))

    def test_klon_egitim_bilgisi_tasimaz(self):
        m = SegmentKurali(min_n=2).fit(girdiler([1, 2]), [0, 1])
        yeni = clone(m)
        self.assertEqual(yeni.min_n, 2)
        with self.assertRaises(NotFittedError):
            yeni.predict_proba(girdiler([1]))

    def test_gecersiz_egitim_hedefi(self):
        for y in [[0], [0, 2], [0, np.nan]]:
            with self.subTest(y=y), self.assertRaises(ValueError):
                SegmentKurali().fit(girdiler([1, 2]), y)

    def test_gecersiz_esik(self):
        for v in [0, -1, 2.5, True]:
            with self.subTest(v=v), self.assertRaises(ValueError):
                SegmentKurali(v).fit(girdiler([1, 2]), [0, 1])

    def test_gecersiz_girdiler(self):
        for col, val in [("Age", np.nan), ("Age", 17), ("NumOfProducts", 0),
                         ("NumOfProducts", 1.5), ("Geography", None), ("Geography", "Italy")]:
            x = girdiler([1, 2]);x[col] = val
            with self.subTest(col=col, val=val), self.assertRaises(ValueError):
                SegmentKurali().fit(x, [0, 1])

    def test_gerekli_aktiflik_eksik_olamaz(self):
        x = girdiler([1, 2]);x["IsActiveMember"] = [0, 1]
        m = SegmentKurali().fit(x, [0, 1])
        with self.assertRaises(ValueError):
            m.predict_proba(girdiler([1]))

    def test_satir_permutasyonu_tahmini_degistirmez(self):
        x = girdiler([1, 1, 3, 3]);y = np.array([0, 0, 1, 1])
        a = SegmentKurali(2).fit(x, y)
        idx = [3, 0, 2, 1]
        b = SegmentKurali(2).fit(x.iloc[idx], y[idx])
        np.testing.assert_allclose(a.predict_proba(x), b.predict_proba(x))

    def test_cv_kucuk_katlarda_sonlu_olasilik_uretir(self):
        x = girdiler([1, 2] * 10)
        y = np.array([0, 1] * 10)
        p = cross_val_predict(SegmentKurali(), x, y,
            cv=StratifiedKFold(2, shuffle=True, random_state=42), method="predict_proba")
        self.assertEqual(p.shape, (20, 2))
        self.assertTrue(np.isfinite(p).all())
        np.testing.assert_allclose(p.sum(axis=1), 1)


class GrupTestleri(unittest.TestCase):
    def test_yakalanan_ve_kacirilan_sayisi(self):
        t = grup_performansi([1, 0, 1, 0], [.9, .8, .7, .1], {"Grup": ["A", "A", "B", "B"]}, 50)
        self.assertEqual(t["Yakalanan ayrılan"].sum(), 1)
        self.assertEqual(t["Kaçırılan ayrılan"].sum(), 1)
        self.assertEqual(t["Listede müşteri"].tolist(), [2, 0])

    def test_sifir_yakalama_kesin_sifir_degil(self):
        t = grup_performansi([1, 1, 0, 0], [.1, .2, .9, .8], {"Grup": ["A"] * 4}, 50)
        self.assertEqual(t.iloc[0]["Yakalanan ayrılan payı"], 0)
        self.assertAlmostEqual(t.iloc[0]["Yakalanan ayrılan payı GA üst"], 3.8416 / 5.8416)

    def test_tam_yakalamada_alt_sinir_bir_degil(self):
        t = grup_performansi([1, 1], [.9, .8], {"Grup": ["A", "A"]}, 100)
        self.assertEqual(t.iloc[0]["Yakalanan ayrılan payı"], 1)
        self.assertLess(t.iloc[0]["Yakalanan ayrılan payı GA alt"], 1)

    def test_n_buyuk_olay_az_ayri_isaretlenir(self):
        y = np.r_[np.ones(2), np.zeros(198)]
        t = grup_performansi(y, np.linspace(.99, .01, 200), {"Grup": ["A"] * 200}, 20)
        self.assertFalse(t.iloc[0]["Küçük müşteri grubu"])
        self.assertTrue(t.iloc[0]["Az ayrılan"])
        self.assertNotIn("n < 100", t.iloc[0]["Not"])
        self.assertIn("az olay", t.iloc[0]["Not"])

    def test_ayrilan_yoksa_aralik_tanimsiz(self):
        t = grup_performansi([0, 0], [.9, .1], {"Grup": ["A", "A"]}, 50)
        for c in ["Yakalanan ayrılan payı", "Yakalanan ayrılan payı GA alt", "Yakalanan ayrılan payı GA üst"]:
            self.assertTrue(np.isnan(t.iloc[0][c]))
        self.assertIn("Ayrılan yok", t.iloc[0]["Not"])

    def test_sifir_kapasite_isabet_tanimsiz(self):
        t = grup_performansi([0, 1], [.9, .1], {"Grup": ["A", "A"]}, 0)
        self.assertEqual(t.iloc[0]["Yakalanan ayrılan"], 0)
        self.assertTrue(np.isnan(t.iloc[0]["İsabet GA alt"]))

    def test_eksik_grup_sessizce_kaybolmaz(self):
        t = grup_performansi([1, 0], [.9, .1], {"Grup": [None, "A"]}, 50)
        self.assertEqual(t["Müşteri"].sum(), 2)
        self.assertIn("Bilinmiyor", set(t.Grup))

    def test_bos_veride_sema_korunur(self):
        t = grup_performansi([], [], {"Grup": []}, 20)
        self.assertTrue(t.empty)
        self.assertIn("Yakalanan ayrılan payı GA üst", t)

    def test_gruplar_icinde_yeniden_siralama_yok(self):
        t = grup_performansi([1, 1, 0, 0], [.99, .98, .2, .1], {"Grup": ["A", "A", "B", "B"]}, 50)
        self.assertEqual(t.loc[t.Grup.eq("A"), "Listede müşteri"].iloc[0], 2)
        self.assertEqual(t.loc[t.Grup.eq("B"), "Listede müşteri"].iloc[0], 0)

    def test_panelde_olay_sayisi_uyarisi_korunur(self):
        y = np.r_[np.ones(2), np.zeros(198)]
        t = grup_performansi(y, np.linspace(.99, .01, 200), {"Cinsiyet": ["Kadın"] * 200}, 20)
        p = sayfa4_grup_tablosu(t)
        self.assertIn("Az ayrılan", p.iloc[0]["Güven notu"])
        self.assertNotIn("n < 100", p.iloc[0]["Güven notu"])
        self.assertIn("Yakalanan pay GA üst", p)

    def test_eski_kaynakta_aralik_uydurulmaz(self):
        eski = pd.DataFrame({"Değişken": ["Cinsiyet"], "Grup": ["Kadın"], "Müşteri": [200], "Ayrılan": [2],
            "Ayrılma oranı": [.01], "Listeye giren müşteri payı": [.2], "Yakalanan ayrılan payı": [.5]})
        p = sayfa4_grup_tablosu(eski)
        self.assertTrue(np.isnan(p.iloc[0]["Yakalanan pay GA üst"]))
        self.assertTrue(np.isnan(p.iloc[0]["Yakalanan ayrılan"]))
        self.assertIn("eski kaynakta yok", p.iloc[0]["Güven notu"])


if __name__ == "__main__":
    unittest.main()
