"""ML yardımcıları (notebooks/02_ml.ipynb): veri ayrımı, iki model hattı, referanslar ve kapasite ölçütleri.

Kurallar (2026-10-23 yöntem kararları):
- Ayrım %70 eğitim / %15 geliştirme / %15 son test; sınıf oranı korunur. Son test hiçbir seçimde kullanılmaz.
- Öğrenilen her dönüşüm (ölçekleme, kodlama, spline düğümleri, SMOTENC, segment kuralı) yalnızca eğitim katında öğrenilir;
  bunu scikit-learn / imblearn Pipeline'ı sağlar.
- Kimlik alanları (RowNumber, CustomerId, Surname) ve Cinsiyet model girdisi değildir; Exited yalnızca hedeftir.
- A hattı ham değişkenleri, B hattı EDA'dan gelen özellik fikirlerini kullanır.
  Ham girdi kullanmak bütün proje seçimini önceki tüm-veri keşfinden bağımsız yapmaz.
- Ana ölçüt Average Precision; iş ölçütü kapasiteye göre yakalanan ayrılan payı (recall @ %10/20/30); Brier kalibrasyon için.
"""

from numbers import Integral

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTENC
from imblearn.pipeline import Pipeline
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, make_scorer, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, SplineTransformer, StandardScaler
from sklearn.utils.validation import check_is_fitted

from .eda import MIN_N, SEGMENT_DEGISKENLERI, SEGMENT_ONCE_AYRILAN, segmentasyon_kur, wilson_aralik
from .kapasite import beklenen_yakalama, hedef_skor_dogrula, kapasite_adedi, liste_secimi, sira_ve_dilim

__all__ = [
    "TOHUM", "KAPASITELER", "GIRDILER", "KIMLIK_DISARIDA", "veri_ayir", "bolum_ozeti", "girdiler",
    "yakalanan_pay", "olcutler", "SKORLAYICILAR", "SegmentKurali", "a_hatti", "b_hatti", "dummy",
    "IZGARALAR", "karsilastir", "gelistirme_degerlendir", "karsilastirma_grafigi",
    "SECILEN_AYAR", "KALIBRASYONLAR", "secilen_model", "kalibrasyon_karsilastir", "kalibrasyon_grafigi",
    "kapasite_tablosu", "onem_tablosu", "bootstrap_araliklari", "grup_performansi",
    "kalibre", "GB_DENEME", "RASTGELE_DENEME", "SADELIK_SIRASI", "SECIM_TOLERANSI", "gb_hatti", "rastgele_alanlar",
    "optuna_gb", "genis_arama", "aday_kur", "tekrarli_cv", "sade_secim",
    "gruplar", "kacirilan_profili", "kararlilik", "ogrenme_farki",
    "kapasite_adedi", "beklenen_yakalama", "liste_secimi", "sira_ve_dilim",
]

TOHUM = 42
KAPASITELER = [10, 20, 30]
# Model girdileri (ham CSV adlarıyla). Cinsiyet etik karar gereği dışarıda; kimlik alanları zaten girdi değil.
GIRDILER = ["CreditScore", "Geography", "Age", "Tenure", "Balance", "NumOfProducts",
            "HasCrCard", "IsActiveMember", "EstimatedSalary"]
KIMLIK_DISARIDA = ["RowNumber", "CustomerId", "Surname", "Gender"]
# SMOTENC'in sayısal olarak enterpolasyon yapmaması gereken alanlar (ara değer anlamsız olur: 1,5 ürün, 0,5 kart).
_SMOTE_KATEGORIK = ["Geography", "NumOfProducts", "HasCrCard", "IsActiveMember"]


# ---------------------------------------------------------------------------
# 1. Veri ayrımı
# ---------------------------------------------------------------------------
def veri_ayir(veri, egitim=0.70, gelistirme=0.15, tohum=TOHUM):
    """Müşteri başına bir bölüm etiketi döndürür (Eğitim / Geliştirme / Test); sınıf oranı her bölümde korunur."""
    idx = veri.index.to_numpy()
    y = veri["Exited"].to_numpy()
    egt, kalan = train_test_split(idx, train_size=egitim, stratify=y, random_state=tohum)
    gel_payi = gelistirme / (1 - egitim)
    gel, tst = train_test_split(kalan, train_size=gel_payi, stratify=veri.loc[kalan, "Exited"], random_state=tohum)
    bolum = pd.Series("Eğitim", index=veri.index, name="Bölüm")
    bolum.loc[gel] = "Geliştirme"
    bolum.loc[tst] = "Test"
    return bolum


def bolum_ozeti(veri, bolum):
    """Her bölümde müşteri, ayrılan ve oran; oranların birbirine yakın olması beklenir."""
    t = veri.groupby(bolum, sort=False)["Exited"].agg(**{"Müşteri": "size", "Ayrılan": "sum"})
    t["Ayrılma oranı (%)"] = 100 * t["Ayrılan"] / t["Müşteri"]
    t["Müşterilerin payı (%)"] = 100 * t["Müşteri"] / len(veri)
    return t.reindex(["Eğitim", "Geliştirme", "Test"])


def girdiler(veri, aktiflik=True):
    """Model girdi tablosu; aktiflik=False ise 'aktif değil' sızıntı şüphesi nedeniyle çıkarılır."""
    kolonlar = [c for c in GIRDILER if aktiflik or c != "IsActiveMember"]
    return veri[kolonlar].copy()


# ---------------------------------------------------------------------------
# 2. Ölçütler: kapasiteye göre yakalanan pay (eşitlikler adil biçimde bölünür)
# ---------------------------------------------------------------------------
def yakalanan_pay(y, skor, kapasite):
    """En fazla %kapasite müşteri: floor(n * kapasite / 100) için beklenen recall (0-1).

    Kesim noktası aynı skorlu bir grubun ortasına düşerse grup içinden rastgele seçim varsayılır (beklenen değer);
    böylece segment kuralı gibi çok sayıda eşit skor üreten yöntemler haksız avantaj ya da dezavantaj almaz.
    """
    return beklenen_yakalama(y, skor, kapasite)["Yakalanan pay"]


def olcutler(y, skor, kapasiteler=KAPASITELER):
    """Genel ölçütler ve tamsayı kapasitede eşit skorlarda beklenen recall/precision.

    Skor kırpılmaz; geçersiz değer hatadır. Ayrılan yoksa AP/recall, tek sınıfta
    ROC AUC, seçilen yoksa precision tanımsızdır ve NaN olarak döner.
    """
    y, skor = hedef_skor_dogrula(y, skor)
    if len(y) == 0:
        raise ValueError("Genel model ölçütleri boş veri üzerinde hesaplanamaz.")
    s = {"AP": average_precision_score(y, skor) if y.sum() else np.nan,
         "ROC AUC": roc_auc_score(y, skor) if len(np.unique(y)) == 2 else np.nan,
         "Brier": brier_score_loss(y, skor)}
    for k in kapasiteler:
        sonuc = beklenen_yakalama(y, skor, k)
        s[f"%{k} kapasitede yakalanan"] = sonuc["Yakalanan pay"]
        s[f"%{k} kapasitede isabet"] = sonuc["İsabet"]
    return s


def _skorlayici(fonk, buyuk_iyi=True):
    return make_scorer(fonk, response_method="predict_proba", greater_is_better=buyuk_iyi)


SKORLAYICILAR = {
    "AP": _skorlayici(average_precision_score),
    "ROC AUC": _skorlayici(roc_auc_score),
    "Brier": _skorlayici(brier_score_loss, buyuk_iyi=False),
    **{f"%{k} kapasitede yakalanan": _skorlayici(lambda y, s, k=k: yakalanan_pay(y, s, k)) for k in KAPASITELER},
}


# ---------------------------------------------------------------------------
# 3. Referanslar
# ---------------------------------------------------------------------------
def dummy():
    """Hiçbir şey bilmeyen model: herkese eğitimdeki ayrılma oranını verir."""
    return DummyClassifier(strategy="prior")


def _segment_cercevesi(X):
    """EDA Bölüm 5 gruplaması (yaş, ürün, Almanya/diğer, aktiflik); sınırlar EDA ile aynıdır."""
    def kat(seri, sira):
        return pd.Categorical(seri, categories=sira, ordered=True)

    d = pd.DataFrame(index=X.index)
    d["Yaş grubu"] = pd.cut(X["Age"], [0, 40, 50, 60, 70, np.inf], right=False,
                            labels=["18–39", "40–49", "50–59", "60–69", "70+"])
    d["Ürün sayısı"] = kat(X["NumOfProducts"].clip(upper=3).map({1: "1 ürün", 2: "2 ürün", 3: "3+ ürün"}),
                           ["1 ürün", "2 ürün", "3+ ürün"])
    d["Ülke grubu"] = kat(np.where(X["Geography"].eq("Germany"), "Almanya", "Diğer"), ["Almanya", "Diğer"])
    if "IsActiveMember" in X:
        d["Aktiflik"] = kat(X["IsActiveMember"].map({0: "Aktif değil", 1: "Aktif"}), ["Aktif değil", "Aktif"])
    return d


class SegmentKurali(ClassifierMixin, BaseEstimator):
    """EDA'nın kural tabanlı segmentasyonu, yalnızca eğitim verisinde kurulan bir sınıflandırıcı olarak.

    Segment kendi eğitim oranını ancak n ≥ min_n ise kullanır. Boş/küçük
    segmentler ve tanınmayan ülke/eşleşmeyen kural, yalnızca fit verisinin genel
    oranına döner. Bu bir belirsizlik çözümü değil, açık bir geri dönüş kuralıdır.
    Aktiflik eğitim girdisinde yoksa kurala da girmez. EDA segment tasarımı değişmez.
    """

    def __init__(self, min_n=MIN_N):
        self.min_n = min_n

    def _girdi_kontrolu(self, X, egitim=False):
        if not isinstance(X, pd.DataFrame):
            raise ValueError("Segment kuralı sütun adları olan bir DataFrame bekler.")
        gerekli = ["Age", "NumOfProducts", "Geography"]
        if not egitim and getattr(self, "aktiflik_kullanildi_", False):
            gerekli.append("IsActiveMember")
        if any(c not in X for c in gerekli):
            raise ValueError(f"Segment girdisinde gerekli sütunlar: {gerekli}")
        for c in ["Age", "NumOfProducts"]:
            if not pd.api.types.is_numeric_dtype(X[c]):
                raise ValueError(f"{c} sayısal olmalı.")
            if not np.isfinite(X[c].to_numpy(dtype=float)).all():
                raise ValueError(f"{c} eksiksiz ve sonlu olmalı.")
        if X["Age"].lt(18).any():
            raise ValueError("Bu segment kuralının yaş aralıkları 18'den başlar.")
        urun = X["NumOfProducts"].to_numpy(dtype=float)
        if ((urun < 1) | (urun != np.floor(urun))).any():
            raise ValueError("Ürün sayısı pozitif tamsayı olmalı.")
        ulke = X["Geography"].astype(object)
        if not ulke.map(lambda v: isinstance(v, str) and bool(v.strip())).all():
            raise ValueError("Geography boş olmayan metin değerleri içermeli.")
        bilinmeyen = ~ulke.isin(["France", "Germany", "Spain"]).to_numpy()
        if egitim and bilinmeyen.any():
            raise ValueError("Eğitim verisinde tanımlanmamış ülke var; veri sözleşmesini inceleyin.")
        if "IsActiveMember" in X and not X["IsActiveMember"].isin([0, 1]).all():
            raise ValueError("IsActiveMember yalnızca 0/1 içermeli.")
        return bilinmeyen

    def fit(self, X, y):
        if isinstance(self.min_n, (bool, np.bool_)) or not isinstance(self.min_n, Integral) or self.min_n < 1:
            raise ValueError("min_n pozitif bir tamsayı olmalı.")
        self._girdi_kontrolu(X, egitim=True)
        y, _ = hedef_skor_dogrula(y, np.zeros(len(X)))
        if len(y) == 0:
            raise ValueError("Boş eğitim verisinden genel oran öğrenilemez.")
        d = _segment_cercevesi(X)
        degiskenler = [v for v in SEGMENT_DEGISKENLERI if v in d]
        self.kurallar_, atama = segmentasyon_kur(d, degiskenler, SEGMENT_ONCE_AYRILAN, self.min_n)
        self.genel_oran_ = float(y.mean())
        self.segment_musteri_ = np.bincount(atama, minlength=len(self.kurallar_))
        self.segment_ayrilan_ = np.bincount(atama, weights=y, minlength=len(self.kurallar_))
        ham_oran = np.divide(self.segment_ayrilan_, self.segment_musteri_,
                            out=np.zeros(len(self.kurallar_), dtype=float), where=self.segment_musteri_ > 0)
        self.geri_donus_ = self.segment_musteri_ < self.min_n
        self.oranlar_ = np.where(self.geri_donus_, self.genel_oran_, ham_oran)
        self.aktiflik_kullanildi_ = "IsActiveMember" in X
        self.n_features_in_ = X.shape[1]
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.classes_ = np.array([0, 1])
        return self

    def ata(self, X):
        """Kural numarası; tanınmayan ülke/eşleşmeyen kural için -1 (genel eğitim oranı)."""
        check_is_fitted(self, ["genel_oran_", "kurallar_", "oranlar_"])
        bilinmeyen = self._girdi_kontrolu(X)
        d = _segment_cercevesi(X)
        atama = np.full(len(d), -1)
        for no, kosullar in enumerate(self.kurallar_):  # ilk kural (3+ ürün) önce; sonrakiler zaten ayrık
            kosul = np.ones(len(d), dtype=bool)
            for v, s in kosullar:
                kosul &= d[v].astype(str).eq(s).to_numpy()
            m = (atama < 0) & ~bilinmeyen & kosul
            atama[m] = no
        return atama

    def predict_proba(self, X):
        atama = self.ata(X)
        p = np.full(len(X), self.genel_oran_)
        eslesen = atama >= 0
        p[eslesen] = self.oranlar_[atama[eslesen]]
        if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
            raise ValueError("Segment kuralı geçersiz olasılık üretti.")
        return np.column_stack([1 - p, p])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)

    def tahmin_aciklamasi(self, X):
        """Her skorun segment oranından mı, genel eğitim oranından mı geldiğini açıklar."""
        atama = self.ata(X)
        n = np.zeros(len(X), dtype=int)
        geri = np.ones(len(X), dtype=bool)
        eslesen = atama >= 0
        n[eslesen] = self.segment_musteri_[atama[eslesen]]
        geri[eslesen] = self.geri_donus_[atama[eslesen]]
        kaynak = np.where(~eslesen, "Genel eğitim oranı · tanınmayan ülke/eşleşmeyen kural",
                         np.where(geri, "Genel eğitim oranı · boş/küçük segment", "Segment eğitim oranı"))
        return pd.DataFrame({"Segment no": atama, "Segment eğitim müşterisi": n,
                             "Geri dönüş kullanıldı": geri, "Skor kaynağı": kaynak,
                             "Skor": self.predict_proba(X)[:, 1]}, index=X.index)


# ---------------------------------------------------------------------------
# 4. Model hatları
# ---------------------------------------------------------------------------
def _smotenc(X):
    kat = [c for c in _SMOTE_KATEGORIK if c in X.columns]
    return SMOTENC(categorical_features=[X.columns.get_loc(c) for c in kat], random_state=TOHUM)


def _dengesizlik(adim_listesi, X, dengesizlik):
    """dengesizlik: 'yok', 'agirlik' (class_weight=balanced) veya 'smotenc' (yalnızca eğitim katında)."""
    if dengesizlik == "smotenc":
        return [("smotenc", _smotenc(X))] + adim_listesi
    return adim_listesi


def a_hatti(X, dengesizlik="yok"):
    """A: Ham değişkenler; ülke one-hot, geri kalanlar olduğu gibi; Random Forest.

    EDA'nın elle seçilmiş etkileşimleri girdi değildir; tüm-veri keşfi sınırı sürer.
    """
    sayisal = [c for c in X.columns if c != "Geography"]
    hazirlik = ColumnTransformer([
        ("ulke", OneHotEncoder(handle_unknown="ignore"), ["Geography"]),
        ("sayisal", "passthrough", sayisal),
    ], verbose_feature_names_out=False)
    model = RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=TOHUM,
                                   class_weight="balanced" if dengesizlik == "agirlik" else None)
    return Pipeline(_dengesizlik([("hazirlik", hazirlik), ("model", model)], X, dengesizlik))


def _b_ozellikleri(X):
    """EDA'dan taşınan fikirler (eda_findings Bölüm 6): ürün sayısı kategori, bakiye sıfır bayrağı ve
    odds ölçeğinde korunan etkileşimler (4d). Bu sınırlar EDA'da tüm veride seçildi; raporda sınır olarak yazılır."""
    d = pd.DataFrame(index=X.index)
    for c in ["Age", "CreditScore", "Tenure", "Balance", "EstimatedSalary", "HasCrCard", "Geography"]:
        d[c] = X[c]
    d["Ürün"] = X["NumOfProducts"].clip(upper=3).astype(str)
    pozitif = X["Balance"].gt(0).astype(int)
    d["Bakiye pozitif"] = pozitif
    d["1 ürün × pozitif bakiye"] = X["NumOfProducts"].eq(1).astype(int) * pozitif
    d["3+ ürün × pozitif bakiye"] = X["NumOfProducts"].ge(3).astype(int) * pozitif
    if "IsActiveMember" in X:
        pasif = 1 - X["IsActiveMember"]
        d["Aktif değil"] = pasif
        d["40–49 × aktif değil"] = X["Age"].between(40, 49).astype(int) * pasif
        d["50–59 × aktif değil"] = X["Age"].between(50, 59).astype(int) * pasif
    return d


def b_hatti(X, dengesizlik="yok"):
    """B: EDA bilgili lojistik regresyon. Yaş spline (ters U), sayısallar ölçekli, ürün ve ülke one-hot."""
    ornek = _b_ozellikleri(X.head())
    ikili = [c for c in ornek.columns if c not in ["Age", "CreditScore", "Tenure", "Balance", "EstimatedSalary",
                                                   "Geography", "Ürün"]]
    hazirlik = ColumnTransformer([
        ("yas", Pipeline([("spline", SplineTransformer(n_knots=5, degree=3)), ("olcek", StandardScaler())]), ["Age"]),
        ("sayisal", StandardScaler(), ["CreditScore", "Tenure", "Balance", "EstimatedSalary"]),
        ("kategori", OneHotEncoder(drop="first", handle_unknown="ignore"), ["Geography", "Ürün"]),
        ("ikili", "passthrough", ikili),
    ], verbose_feature_names_out=False)
    model = LogisticRegression(max_iter=5000, class_weight="balanced" if dengesizlik == "agirlik" else None)
    adimlar = [("ozellik", FunctionTransformer(_b_ozellikleri)), ("hazirlik", hazirlik), ("model", model)]
    return Pipeline(_dengesizlik(adimlar, X, dengesizlik))


IZGARALAR = {
    "A · Random Forest": {"model__min_samples_leaf": [5, 20, 50], "model__max_features": ["sqrt", 0.5]},
    "B · Lojistik regresyon": {"model__C": [0.01, 0.1, 1.0, 10.0]},
}


# ---------------------------------------------------------------------------
# 5. Çapraz doğrulama karşılaştırması (yalnızca eğitim verisi)
# ---------------------------------------------------------------------------
def karsilastir(veri_egitim, cv_kat=5, aktiflik_secenekleri=(True, False),
                dengesizlikler=("yok", "agirlik", "smotenc")):
    """Her yapılandırma için 5 katlı stratified CV; hiperparametre ızgarası AP'ye göre seçilir.

    Dönen tablo: yapılandırma başına seçilen ayar ve katların ortalaması ± standart sapması.
    Not: aynı CV'de en iyi ayarı seçmek iyimserlik yaratabilir; büyüklüğü
    burada ölçülmemiştir. Seçim için kullanılan geliştirme de bağımsız değildir.
    """
    y = veri_egitim["Exited"].to_numpy()
    cv = StratifiedKFold(n_splits=cv_kat, shuffle=True, random_state=TOHUM)
    satirlar = []
    for aktiflik in aktiflik_secenekleri:
        X = girdiler(veri_egitim, aktiflik)
        adaylar = [("Referans · Dummy", "—", dummy(), {}), ("Referans · Segment kuralı", "—", SegmentKurali(), {})]
        for dengesizlik in dengesizlikler:
            adaylar.append(("A · Random Forest", dengesizlik, a_hatti(X, dengesizlik), IZGARALAR["A · Random Forest"]))
            adaylar.append(("B · Lojistik regresyon", dengesizlik, b_hatti(X, dengesizlik),
                            IZGARALAR["B · Lojistik regresyon"]))
        for ad, dengesizlik, model, izgara in adaylar:
            arama = GridSearchCV(model, izgara or {}, scoring=SKORLAYICILAR, refit=False, cv=cv, n_jobs=1)
            arama.fit(X, y)
            r = pd.DataFrame(arama.cv_results_)
            en_iyi = r.loc[r["mean_test_AP"].idxmax()]
            kayit = {"Aktiflik": "Var" if aktiflik else "Yok", "Model": ad,
                     "Dengesizlik": {"yok": "Yok", "agirlik": "Sınıf ağırlığı", "smotenc": "SMOTENC"}.get(dengesizlik, "—"),
                     "Seçilen ayar": ", ".join(f"{k.split('__')[1]}={v}" for k, v in en_iyi["params"].items()) or "—",
                     "_dengesizlik": dengesizlik, "_ayar": dict(en_iyi["params"])}
            for olcut in SKORLAYICILAR:
                isaret = -1 if olcut == "Brier" else 1
                kayit[olcut] = isaret * en_iyi[f"mean_test_{olcut}"]
                kayit[f"{olcut} ss"] = en_iyi[f"std_test_{olcut}"]
            satirlar.append(kayit)
    return pd.DataFrame(satirlar)


def _kur(ad, X, dengesizlik, ayar):
    """Karşılaştırma tablosundaki bir satırın modelini seçilen ayarla yeniden kurar."""
    if ad == "Referans · Dummy":
        return dummy()
    if ad == "Referans · Segment kuralı":
        return SegmentKurali()
    model = (a_hatti if ad.startswith("A") else b_hatti)(X, dengesizlik)
    return model.set_params(**ayar)


def gelistirme_degerlendir(veri_egitim, veri_gelistirme, cv_tablosu):
    """Her yapılandırma tüm eğitim verisinde (7.000) eğitilir, geliştirme setinde (≈1.500) ölçülür.

    Model seçimi bu tabloyla yapılır; son test seti burada kullanılmaz.
    """
    y_egt = veri_egitim["Exited"].to_numpy()
    y_gel = veri_gelistirme["Exited"].to_numpy()
    satirlar, modeller = [], {}
    for _, r in cv_tablosu.iterrows():
        aktiflik = r["Aktiflik"] == "Var"
        X_egt, X_gel = girdiler(veri_egitim, aktiflik), girdiler(veri_gelistirme, aktiflik)
        model = _kur(r["Model"], X_egt, r["_dengesizlik"], r["_ayar"]).fit(X_egt, y_egt)
        skor = model.predict_proba(X_gel)[:, 1]
        anahtar = (r["Aktiflik"], r["Model"], r["Dengesizlik"])
        modeller[anahtar] = model
        satirlar.append({"Aktiflik": r["Aktiflik"], "Model": r["Model"], "Dengesizlik": r["Dengesizlik"],
                         "Seçilen ayar": r["Seçilen ayar"], **olcutler(y_gel, skor)})
    return pd.DataFrame(satirlar), modeller


def karsilastirma_grafigi(tablo, baslik, output_dir=None, dosya="03_karsilastirma.png"):
    """AP ve %20 kapasitede yakalanan pay. Tabloda '<ölçüt> ss' sütunu varsa ±1 standart sapma çizilir."""
    import matplotlib.pyplot as plt

    from .eda import RENKLER, kaydet, tr_sayi

    t = tablo.copy()
    t["Etiket"] = t["Model"].str.replace("Referans · ", "") + np.where(t["Dengesizlik"].eq("—"), "", " · " + t["Dengesizlik"])
    renk = {"Referans · Dummy": RENKLER["gri"], "Referans · Segment kuralı": RENKLER["sari"],
            "A · Random Forest": RENKLER["mor"], "B · Lojistik regresyon": RENKLER["mavi"]}
    from matplotlib.ticker import FuncFormatter

    fig, eksenler = plt.subplots(2, 2, figsize=(15, 10), layout="constrained")
    for satir, olcut in enumerate(["AP", "%20 kapasitede yakalanan"]):
        for sutun, aktiflik in enumerate(["Var", "Yok"]):
            ax = eksenler[satir, sutun]
            p = t[t["Aktiflik"].eq(aktiflik)].reset_index(drop=True)
            ax.barh(p.index, p[olcut], xerr=p.get(f"{olcut} ss"), color=[renk[m] for m in p["Model"]],
                    error_kw={"ecolor": "#5F6573", "capsize": 3})
            ax.set_yticks(p.index, p["Etiket"])
            ax.invert_yaxis()
            ss = p.get(f"{olcut} ss", pd.Series(0.0, index=p.index))
            for i, v in enumerate(p[olcut]):
                ax.text(v + ss.iloc[i] + 0.015, i, tr_sayi(v, 3), va="center", fontsize=9)
            seg = p.loc[p["Model"].eq("Referans · Segment kuralı"), olcut].iloc[0]
            ax.axvline(seg, color=RENKLER["turuncu"], linestyle="--", linewidth=1.2)
            ax.set_xlim(0, 1)
            ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: tr_sayi(v, 1)))
            if sutun == 1:
                ax.set_yticklabels([])
            ax.set_title(f"{olcut} · aktiflik {aktiflik.lower()}" + (" (sızıntı şüphesi)" if aktiflik == "Var" else ""))
    fig.suptitle(baslik, fontsize=13)
    if output_dir is not None:
        kaydet(fig, dosya, output_dir)
    else:
        plt.show()


# ---------------------------------------------------------------------------
# 5b. Eleştirel gözden geçirme sonrası (2026-10-23): gradient boosting (Optuna), geniş rastgele arama,
#     gürültüye dayanıklı seçim. Hepsi yalnızca eğitim verisinde; geliştirme seti yalnızca doğrulama.
# ---------------------------------------------------------------------------
GB_DENEME = 50       # Optuna (TPE) bütçesi; aramadan önce sabitlendi
RASTGELE_DENEME = 30  # Random Forest ve lojistik regresyon için rastgele arama bütçesi
SADELIK_SIRASI = ["B · Lojistik regresyon", "A · Random Forest", "A · Gradient Boosting"]  # sadeden karmaşığa
SECIM_TOLERANSI = 0.01


def gb_hatti(X):
    """A: Ham değişkenli gradient boosting (HistGradientBoosting); ülke one-hot.

    Ağaç sayısı erken durdurmayla belirlenir: eğitim katının %10'u iç doğrulamaya ayrılır, 20 tur iyileşme olmazsa durur.
    """
    from sklearn.ensemble import HistGradientBoostingClassifier

    sayisal = [c for c in X.columns if c != "Geography"]
    hazirlik = ColumnTransformer([
        ("ulke", OneHotEncoder(handle_unknown="ignore"), ["Geography"]),
        ("sayisal", "passthrough", sayisal),
    ], verbose_feature_names_out=False)
    model = HistGradientBoostingClassifier(max_iter=1000, early_stopping=True, validation_fraction=0.1,
                                           n_iter_no_change=20, random_state=TOHUM)
    return Pipeline([("hazirlik", hazirlik), ("model", model)])


def rastgele_alanlar():
    """Random Forest ve lojistik regresyon için rastgele arama alanları; sınıf ağırlığı da bir ayar olarak aranır."""
    from scipy.stats import loguniform, randint, uniform

    return {
        "B · Lojistik regresyon": (b_hatti, {
            "model__C": loguniform(1e-3, 1e2),
            "hazirlik__yas__spline__n_knots": randint(4, 9),
            "model__class_weight": [None, "balanced"],
        }),
        "A · Random Forest": (a_hatti, {
            "model__n_estimators": [300, 500],
            "model__max_features": uniform(0.2, 0.7),
            "model__min_samples_leaf": randint(1, 101),
            "model__max_depth": [None, 6, 10, 15],
            "model__max_samples": uniform(0.5, 0.5),
            "model__class_weight": [None, "balanced", "balanced_subsample"],
        }),
    }


def _gb_ayari(trial):
    """Optuna'nın gradient boosting için önerdiği ayar (arama alanı)."""
    return {
        "model__learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "model__max_leaf_nodes": trial.suggest_int("max_leaf_nodes", 8, 64),
        "model__min_samples_leaf": trial.suggest_int("min_samples_leaf", 10, 200),
        "model__l2_regularization": trial.suggest_float("l2_regularization", 1e-3, 10, log=True),
        "model__max_depth": trial.suggest_categorical("max_depth", [None, 3, 5, 8]),
        "model__max_features": trial.suggest_float("max_features", 0.5, 1.0),
        "model__class_weight": trial.suggest_categorical("class_weight", [None, "balanced"]),
    }


def optuna_gb(veri_egitim, deneme=GB_DENEME, aktiflik=False):
    """Gradient boosting için Bayesçi optimizasyon (Optuna TPE): her deneme eğitim verisinde 5 katlı CV AP'si."""
    import optuna
    from sklearn.model_selection import cross_validate

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    X, y = girdiler(veri_egitim, aktiflik), veri_egitim["Exited"].to_numpy()
    cv = StratifiedKFold(5, shuffle=True, random_state=TOHUM)

    def amac(trial):
        model = gb_hatti(X).set_params(**_gb_ayari(trial))
        s = cross_validate(model, X, y, cv=cv, scoring=SKORLAYICILAR, n_jobs=1)
        trial.set_user_attr("AP ss", float(s["test_AP"].std()))
        trial.set_user_attr("%20 kapasitede yakalanan", float(s["test_%20 kapasitede yakalanan"].mean()))
        return float(s["test_AP"].mean())

    calisma = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=TOHUM))
    calisma.optimize(amac, n_trials=deneme)
    en_iyi = _gb_ayari(optuna.trial.FixedTrial(calisma.best_params))
    return calisma, en_iyi


def genis_arama(veri_egitim, aktiflik=False):
    """Üç aile: lojistik regresyon ve Random Forest rastgele aramayla, gradient boosting Optuna ile.

    Döner: özet tablo, en iyi ayarlar (aile → ayar sözlüğü), Optuna çalışması.
    """
    from sklearn.model_selection import RandomizedSearchCV

    X, y = girdiler(veri_egitim, aktiflik), veri_egitim["Exited"].to_numpy()
    cv = StratifiedKFold(5, shuffle=True, random_state=TOHUM)
    satirlar, ayarlar = [], {}
    for ad, (kur, alan) in rastgele_alanlar().items():
        arama = RandomizedSearchCV(kur(X, "yok"), alan, n_iter=RASTGELE_DENEME, scoring=SKORLAYICILAR, refit=False,
                                   cv=cv, random_state=TOHUM, n_jobs=1)
        arama.fit(X, y)
        r = pd.DataFrame(arama.cv_results_)
        en_iyi = r.loc[r["mean_test_AP"].idxmax()]
        ayarlar[ad] = dict(en_iyi["params"])
        satirlar.append({"Model": ad, "Arama": f"Rastgele, {RASTGELE_DENEME} deneme",
                         "En iyi CV AP": en_iyi["mean_test_AP"], "AP ss": en_iyi["std_test_AP"],
                         "%20 kapasitede yakalanan": en_iyi["mean_test_%20 kapasitede yakalanan"],
                         "Denemelerin AP aralığı": f"{r['mean_test_AP'].min():.3f}–{r['mean_test_AP'].max():.3f}",
                         "Seçilen ayar": _ayar_metni(en_iyi["params"])})
    calisma, gb_ayar = optuna_gb(veri_egitim, aktiflik=aktiflik)
    ayarlar["A · Gradient Boosting"] = gb_ayar
    degerler = [t.value for t in calisma.trials if t.value is not None]
    satirlar.append({"Model": "A · Gradient Boosting", "Arama": f"Optuna (TPE), {GB_DENEME} deneme",
                     "En iyi CV AP": calisma.best_value, "AP ss": calisma.best_trial.user_attrs["AP ss"],
                     "%20 kapasitede yakalanan": calisma.best_trial.user_attrs["%20 kapasitede yakalanan"],
                     "Denemelerin AP aralığı": f"{min(degerler):.3f}–{max(degerler):.3f}",
                     "Seçilen ayar": _ayar_metni(gb_ayar)})
    return pd.DataFrame(satirlar), ayarlar, calisma


def _ayar_metni(ayar):
    def bicim(v):
        return f"{v:.3g}" if isinstance(v, float) else str(v)
    return ", ".join(f"{k.split('__')[-1]}={bicim(v)}" for k, v in ayar.items())


def aday_kur(ad, X, ayar):
    """Geniş aramada bulunan ayarla modeli kurar (eğitilmemiş)."""
    if ad == "A · Gradient Boosting":
        return gb_hatti(X).set_params(**ayar)
    kur, _ = rastgele_alanlar()[ad]
    return kur(X, "yok").set_params(**ayar)


def tekrarli_cv(veri_egitim, ayarlar, aktiflik=False, kat=5, tekrar=3):
    """Tarihsel sabit-ayar kararlılık kontrolü: 5 × 3 farklı bölme.

    Ayarlar aynı müşterilerde seçildiği için yeni bölmeler seçim iyimserliğini
    ortadan kaldırmaz; iç içe doğrulama veya bağımsız test yerine geçmez.
    """
    from sklearn.model_selection import RepeatedStratifiedKFold, cross_validate

    X, y = girdiler(veri_egitim, aktiflik), veri_egitim["Exited"].to_numpy()
    cv = RepeatedStratifiedKFold(n_splits=kat, n_repeats=tekrar, random_state=TOHUM + 1)
    adaylar = {**{ad: aday_kur(ad, X, a) for ad, a in ayarlar.items()}, "Referans · Segment kuralı": SegmentKurali()}
    satirlar = []
    for ad, model in adaylar.items():
        s = cross_validate(model, X, y, cv=cv, scoring=SKORLAYICILAR, n_jobs=1)
        satirlar.append({"Model": ad, "AP": s["test_AP"].mean(), "AP ss": s["test_AP"].std(),
                         "%20 kapasitede yakalanan": s["test_%20 kapasitede yakalanan"].mean(),
                         "%20 ss": s["test_%20 kapasitede yakalanan"].std(), "Brier": -s["test_Brier"].mean()})
    return pd.DataFrame(satirlar)


def sade_secim(tablo, tolerans=SECIM_TOLERANSI, sira=SADELIK_SIRASI):
    """Önceden yazılı kural: en yüksek AP'ye `tolerans`tan yakın modeller arasında en sade olanı seç."""
    modeller = tablo[tablo["Model"].isin(sira)].set_index("Model")
    en_iyi = modeller["AP"].max()
    return [m for m in sira if m in modeller.index and modeller.loc[m, "AP"] >= en_iyi - tolerans][0]


# ---------------------------------------------------------------------------
# 6. Seçilen model, kalibrasyon, kapasite eşikleri, açıklama
# ---------------------------------------------------------------------------
# Geliştirme setinde seçilen yapılandırma (2026-10-23): A · Random Forest, dengesizlik düzeltmesiz, aktifliksiz.
SECILEN_AYAR = {"model__max_features": 0.5, "model__min_samples_leaf": 20}
KALIBRASYONLAR = ["Ham", "Sigmoid", "İzotonik"]


def kalibre(model, kalibrasyon="Ham"):
    """Herhangi bir modeli eğitim verisinde 5 katlı CalibratedClassifierCV ile kalibre eder (Ham = dokunma)."""
    from sklearn.calibration import CalibratedClassifierCV

    if kalibrasyon == "Ham":
        return model
    yontem = {"Sigmoid": "sigmoid", "İzotonik": "isotonic"}[kalibrasyon]
    return CalibratedClassifierCV(model, method=yontem, cv=StratifiedKFold(5, shuffle=True, random_state=TOHUM))


def secilen_model(X, kalibrasyon="Ham", ayar=None):
    """Seçilen Random Forest; kalibrasyon varsa eğitim verisinde 5 katlı CalibratedClassifierCV ile öğrenilir."""
    from sklearn.calibration import CalibratedClassifierCV

    model = a_hatti(X, "yok").set_params(**(ayar or SECILEN_AYAR))
    if kalibrasyon == "Ham":
        return model
    yontem = {"Sigmoid": "sigmoid", "İzotonik": "isotonic"}[kalibrasyon]
    return CalibratedClassifierCV(model, method=yontem, cv=StratifiedKFold(5, shuffle=True, random_state=TOHUM))


def kalibrasyon_karsilastir(veri_egitim, veri_gelistirme, aktiflik=False, model_kur=None):
    """Ham ve kalibre edilmiş skorlar geliştirme setinde: Brier, AP, %20 yakalama ve ortalama skor.

    model_kur: X -> (eğitilmemiş) model; verilmezse ilk seçilen Random Forest kullanılır.
    """
    X_e, X_g = girdiler(veri_egitim, aktiflik), girdiler(veri_gelistirme, aktiflik)
    y_e, y_g = veri_egitim["Exited"].to_numpy(), veri_gelistirme["Exited"].to_numpy()
    model_kur = model_kur or (lambda X: secilen_model(X))
    satirlar, skorlar = [], {}
    for k in KALIBRASYONLAR:
        s = kalibre(model_kur(X_e), k).fit(X_e, y_e).predict_proba(X_g)[:, 1]
        skorlar[k] = s
        o = olcutler(y_g, s)
        satirlar.append({"Kalibrasyon": k, "Brier": o["Brier"], "AP": o["AP"],
                         "%20 kapasitede yakalanan": o["%20 kapasitede yakalanan"],
                         "Ortalama skor": s.mean(), "Gerçek oran": y_g.mean()})
    return pd.DataFrame(satirlar), skorlar


def kalibrasyon_grafigi(y, skorlar, output_dir=None, dosya="05_kalibrasyon.png"):
    """Güvenilirlik grafiği: 10 eşit büyüklükte skor diliminde ortalama skor ile gerçek ayrılma oranı."""
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve

    from .eda import RENKLER, kaydet, tr_sayi

    renk = {"Ham": RENKLER["mor"], "Sigmoid": RENKLER["mavi"], "İzotonik": RENKLER["turuncu"]}
    fig, ax = plt.subplots(figsize=(8, 7), layout="constrained")
    ax.plot([0, 1], [0, 1], color=RENKLER["gri"], linestyle=":", label="Kusursuz kalibrasyon")
    for k, s in skorlar.items():
        gercek, tahmin = calibration_curve(y, s, n_bins=10, strategy="quantile")
        ax.plot(tahmin, gercek, marker="o", color=renk[k],
                label=f"{k} (Brier {tr_sayi(brier_score_loss(y, s), 3)})")
    ax.set_xlabel("Modelin verdiği ortalama skor (dilim)")
    ax.set_ylabel("Dilimde gerçek ayrılma oranı")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left", frameon=False)
    ax.set_title(f"Skorlar olasılık olarak okunabilir mi? | Geliştirme seti: {tr_sayi(len(y))} müşteri\n"
                 "Her nokta 10 eşit büyüklükteki skor diliminden biri; çizgiye yakınlık = güvenilir olasılık")
    if output_dir is not None:
        kaydet(fig, dosya, output_dir)
    else:
        plt.show()


def kapasite_tablosu(y, skor, kapasiteler=KAPASITELER, musteri_id=None):
    """Somut liste: aşağı yuvarlanan adet, kimlikle çözülen eşitlikler ve gerçekleşen yakalama.

    'Beklenen ayrılan' skorların toplamıdır; eşit skorlarda beklenen yakalamadan farklıdır.
    Kesim noktasında eşitlik varsa musteri_id verilmelidir.
    """
    y, skor = hedef_skor_dogrula(y, skor)
    satirlar = []
    for k in kapasiteler:
        secilen, _ = liste_secimi(skor, k, musteri_id)
        m = len(secilen)
        satirlar.append({"Kapasite": f"%{k}", "Bakılan müşteri": m,
                         "Skor eşiği": float(skor[secilen].min()) if m else np.nan,
                         "Beklenen ayrılan (skor toplamı)": float(skor[secilen].sum()),
                         "Gerçek ayrılan": int(y[secilen].sum()),
                         "Yakalanan pay": y[secilen].sum() / y.sum() if y.sum() else np.nan,
                         "İsabet": float(y[secilen].mean()) if m else np.nan,
                         "Seçim anlamı": "Somut liste · skor azalan, eşitlikte CustomerId artan"})
    return pd.DataFrame(satirlar)


def onem_tablosu(model, X, y, tekrar=20):
    """Permutation importance: bir değişken karıştırılınca AP ne kadar düşüyor? (geliştirme setinde)

    Nedensellik değil; modelin sıralamada hangi bilgiye dayandığını gösterir.
    """
    from sklearn.inspection import permutation_importance

    from .bivariate_eda import NAMES

    r = permutation_importance(model, X, y, scoring=SKORLAYICILAR["AP"], n_repeats=tekrar,
                               random_state=TOHUM, n_jobs=1)
    t = pd.DataFrame({"Değişken": [NAMES.get(c, c) for c in X.columns], "AP düşüşü": r.importances_mean,
                      "ss": r.importances_std})
    return t.sort_values("AP düşüşü", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 6b. Testten önce tanı kontrolleri (2026-10-24). Yalnızca tanı ve raporlama: model, ayar ve kalibrasyon
#     bunlara göre değiştirilmez; ciddi sorun çıkarsa değişiklik eğitim CV'siyle doğrulanır ve raporlanır.
# ---------------------------------------------------------------------------
def gruplar(veri):
    """Grup performansı ve hata analizi için Türkçe etiketli müşteri grupları (EDA sınırlarıyla)."""
    yas = pd.cut(veri["Age"], [0, 40, 50, 60, 70, np.inf], right=False,
                 labels=["18–39", "40–49", "50–59", "60–69", "70+"]).astype(str)
    return {
        "Cinsiyet": veri["Gender"].map({"Female": "Kadın", "Male": "Erkek"}),
        "Ülke": veri["Geography"].map({"France": "Fransa", "Germany": "Almanya", "Spain": "İspanya"}),
        "Yaş grubu": yas,
        "Ürün sayısı": veri["NumOfProducts"].clip(upper=3).map({1: "1 ürün", 2: "2 ürün", 3: "3+ ürün"}),
        "Aktiflik": veri["IsActiveMember"].map({0: "Aktif değil", 1: "Aktif"}),
        "Bakiye durumu": np.where(veri["Balance"].eq(0), "Sıfır", "Pozitif"),
    }


def kacirilan_profili(veri, y, skor, kapasite=20):
    """%kapasite listesine giren (yakalanan) ve girmeyen (kaçırılan) ayrılanların sayısal profili (medyanlar)."""
    from .bivariate_eda import NAMES

    y, skor = hedef_skor_dogrula(y, skor)
    if len(veri) != len(y):
        raise ValueError("Müşteri verisi hedef ve skorla aynı uzunlukta olmalı.")
    ids = veri["CustomerId"] if "CustomerId" in veri else None
    _, listede = liste_secimi(skor, kapasite, ids)
    ayrilan = y == 1
    def medyan(degerler):
        return float(np.median(degerler)) if len(degerler) else np.nan

    satirlar = []
    for c in ["Age", "NumOfProducts", "Balance", "CreditScore", "Tenure", "EstimatedSalary"]:
        v = veri[c].to_numpy()
        satirlar.append({"Değişken": NAMES[c],
                          "Yakalanan ayrılanlar (medyan)": medyan(v[ayrilan & listede]),
                          "Kaçırılan ayrılanlar (medyan)": medyan(v[ayrilan & ~listede]),
                          "Kalan müşteriler (medyan)": medyan(v[~ayrilan])})
    ozet = {"Yakalanan ayrılan": int((ayrilan & listede).sum()), "Kaçırılan ayrılan": int((ayrilan & ~listede).sum())}
    return pd.DataFrame(satirlar), ozet


def kararlilik(veri_egitim, veri_gelistirme, model_kur, tohumlar=(0, 1, 2, 3, 4), kalibrasyon="Sigmoid"):
    """Aynı ayarla farklı rastgele tohumlar: geliştirme AP'si ve %20 yakalama ne kadar oynuyor?"""
    X_e, X_g = girdiler(veri_egitim, False), girdiler(veri_gelistirme, False)
    y_e, y_g = veri_egitim["Exited"].to_numpy(), veri_gelistirme["Exited"].to_numpy()
    satirlar = []
    for t in tohumlar:
        model = model_kur(X_e).set_params(model__random_state=t)
        s = kalibre(model, kalibrasyon).fit(X_e, y_e).predict_proba(X_g)[:, 1]
        o = olcutler(y_g, s)
        satirlar.append({"Tohum": t, "AP": o["AP"], "%20 kapasitede yakalanan": o["%20 kapasitede yakalanan"],
                         "Brier": o["Brier"]})
    return pd.DataFrame(satirlar)


def ogrenme_farki(veri_egitim, model_kur, cv_kat=5):
    """Aşırı öğrenme kontrolü: aynı model eğitim verisinin kendisinde ve 5 katlı CV'de (görmediği katlarda)."""
    from sklearn.model_selection import cross_validate

    X, y = girdiler(veri_egitim, False), veri_egitim["Exited"].to_numpy()
    cv = StratifiedKFold(cv_kat, shuffle=True, random_state=TOHUM)
    s = cross_validate(model_kur(X), X, y, cv=cv, scoring=SKORLAYICILAR, return_train_score=True, n_jobs=1)
    return pd.DataFrame([{"Ölçüt": o, "Eğitim katları": (-1 if o == "Brier" else 1) * s[f"train_{o}"].mean(),
                          "Doğrulama katları (CV)": (-1 if o == "Brier" else 1) * s[f"test_{o}"].mean()}
                         for o in ["AP", "%20 kapasitede yakalanan", "Brier"]])


# ---------------------------------------------------------------------------
# 7. Son test: bootstrap güven aralığı ve grup performansı
# ---------------------------------------------------------------------------
def bootstrap_araliklari(y, skorlar, referans, tekrar=2000, tohum=TOHUM):
    """Eşleştirilmiş bootstrap: aynı müşteri örneklemi tüm yöntemlere uygulanır; %95 yüzdelik aralıklar.

    skorlar: {yöntem adı: skor}. Fark sütunları her yöntemi `referans` yöntemiyle karşılaştırır.
    Sabit skor vektörlerine koşulludur; eğitim/seçim belirsizliğini içermez.
    """
    if isinstance(tekrar, (bool, np.bool_)) or not isinstance(tekrar, Integral) or tekrar < 2:
        raise ValueError("Bootstrap tekrar sayısı en az 2 olan tamsayı olmalı.")
    if not skorlar or referans not in skorlar:
        raise ValueError("Referans skor sözlüğünde bulunmalı.")
    validated = {ad: hedef_skor_dogrula(y, s) for ad, s in skorlar.items()}
    y = next(iter(validated.values()))[0]
    if not len(y) or not y.sum():
        raise ValueError("AP/yakalama aralığı için boş olmayan, ayrılan içeren veri gerekli.")
    skorlar = {ad: pair[1] for ad, pair in validated.items()}
    rng = np.random.default_rng(tohum)
    kayit = {ad: {"AP": [], "Yakalanan @20": []} for ad in skorlar}
    for _ in range(tekrar):
        i = rng.integers(0, len(y), len(y))
        if y[i].sum() == 0:
            continue
        for ad, s in skorlar.items():
            kayit[ad]["AP"].append(average_precision_score(y[i], s[i]))
            kayit[ad]["Yakalanan @20"].append(yakalanan_pay(y[i], s[i], 20))
    satirlar = []
    for ad, s in skorlar.items():
        satir = {"Yöntem": ad}
        for olcut, ad_tr in [("AP", "AP"), ("Yakalanan @20", "%20 kapasitede yakalanan")]:
            dizi = np.array(kayit[ad][olcut])
            fark = dizi - np.array(kayit[referans][olcut])
            nokta = average_precision_score(y, s) if olcut == "AP" else yakalanan_pay(y, s, 20)
            satir[ad_tr] = nokta
            satir[f"{ad_tr} GA alt"], satir[f"{ad_tr} GA üst"] = np.percentile(dizi, [2.5, 97.5])
            if ad != referans:
                satir[f"{ad_tr} farkı ({referans})"] = nokta - (
                    average_precision_score(y, skorlar[referans]) if olcut == "AP" else yakalanan_pay(y, skorlar[referans], 20))
                satir[f"{ad_tr} farkı GA alt"], satir[f"{ad_tr} farkı GA üst"] = np.percentile(fark, [2.5, 97.5])
        satirlar.append(satir)
    table = pd.DataFrame(satirlar)
    table.attrs["gecerli_tekrar"] = len(kayit[referans]["AP"])
    table.attrs["istenen_tekrar"] = tekrar
    return table


def grup_performansi(y, skor, gruplar, kapasite=20, musteri_id=None):
    """Tek bir genel liste (en riskli %kapasite) kurulur; her grupta ayrılanların ne kadarı listeye girdi?

    %95 Wilson aralıkları sabit listedeki oranların betimsel belirsizliğidir;
    model eğitimi/ayar seçimi ve kapasite seçim belirsizliğini içermez.
    Bütün gruplar aynı genel listenin içinden sayılır; gruplar içinde yeniden sıralama yapılmaz.
    """
    y, skor = hedef_skor_dogrula(y, skor)
    _, listede = liste_secimi(skor, kapasite, musteri_id)
    kolonlar = ["Değişken", "Grup", "Müşteri", "Ayrılan", "Listede müşteri", "Yakalanan ayrılan",
                "Kaçırılan ayrılan", "Ayrılma oranı", "Ayrılma oranı GA alt", "Ayrılma oranı GA üst", "Lift",
                "Listeye giren müşteri payı", "Listeye giren müşteri payı GA alt", "Listeye giren müşteri payı GA üst",
                "Yakalanan ayrılan payı", "Yakalanan ayrılan payı GA alt", "Yakalanan ayrılan payı GA üst",
                "İsabet", "İsabet GA alt", "İsabet GA üst", "Küçük müşteri grubu", "Az ayrılan", "Not"]
    satirlar = []
    for ad, grup in gruplar.items():
        grup = np.asarray(grup)
        if grup.ndim != 1 or len(grup) != len(y):
            raise ValueError("Grup etiketleri hedef ve skorla aynı uzunlukta olmalı.")
        grup = pd.Series(grup, dtype=object).fillna("Bilinmiyor").to_numpy()
        for seviye in pd.unique(grup):
            g = grup == seviye
            n, k = int(g.sum()), int(y[g].sum())
            l = int(listede[g].sum())
            yak = int((listede[g] & (y[g] == 1)).sum())
            oran_alt, oran_ust = (float(v) for v in wilson_aralik(k, n))
            liste_alt, liste_ust = (float(v) for v in wilson_aralik(l, n))
            yak_alt, yak_ust = (float(v) for v in wilson_aralik(yak, k))
            isabet_alt, isabet_ust = (float(v) for v in wilson_aralik(yak, l))
            notlar = []
            if n < MIN_N:
                notlar.append("n < 100 · küçük müşteri grubu")
            if k == 0:
                notlar.append("Ayrılan yok · yakalama hesaplanamaz")
            elif k < 30:
                notlar.append("Ayrılan < 30 · az olay")
            satirlar.append({"Değişken": ad, "Grup": seviye, "Müşteri": n, "Ayrılan": k,
                             "Listede müşteri": l, "Yakalanan ayrılan": yak, "Kaçırılan ayrılan": k - yak,
                             "Ayrılma oranı": k / n if n else np.nan,
                             "Ayrılma oranı GA alt": oran_alt, "Ayrılma oranı GA üst": oran_ust,
                             "Lift": (k / n) / y.mean() if n and y.sum() else np.nan,
                             "Listeye giren müşteri payı": listede[g].mean(),
                             "Listeye giren müşteri payı GA alt": liste_alt, "Listeye giren müşteri payı GA üst": liste_ust,
                             "Yakalanan ayrılan payı": yak / k if k else np.nan,
                             "Yakalanan ayrılan payı GA alt": yak_alt, "Yakalanan ayrılan payı GA üst": yak_ust,
                             "İsabet": yak / l if l else np.nan,
                             "İsabet GA alt": isabet_alt, "İsabet GA üst": isabet_ust,
                             "Küçük müşteri grubu": n < MIN_N, "Az ayrılan": k < 30, "Not": "; ".join(notlar)})
    return pd.DataFrame(satirlar, columns=kolonlar)
