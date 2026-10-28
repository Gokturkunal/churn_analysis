-- Amaç: Age (yaş) için tek değişkenli özet, IQR uç değer sınırları ve notebook ile aynı yaş aralıkları.
-- Kaynak: dbo.CustomerChurn_EDA. Yalnızca okur; tabloyu değiştirmez.
-- Notebook karşılığı: Bölüm 1 (5 yıllık histogram) ve Bölüm 2b (10 yıllık aralıklar).
USE [ChurnAnalysis];
GO

-- 1. Özet istatistikler. PERCENTILE_CONT SQL Server'da pencere fonksiyonudur; her satıra aynı değeri
--    yazar. DISTINCT sonucu tek satıra indirir. AVG(1.0 * Age), tam sayı ortalamasının kesilmesini önler.
SELECT DISTINCT
    COUNT(*)                                          OVER () AS CustomerCount,
    CAST(AVG(1.0 * Age) OVER () AS decimal(6,2))              AS Mean,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY Age) OVER () AS Q1,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY Age) OVER () AS Median,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY Age) OVER () AS Q3,
    CAST(STDEV(Age) OVER () AS decimal(6,2))                  AS StdDev,
    MIN(Age)                                          OVER () AS MinAge,
    MAX(Age)                                          OVER () AS MaxAge
FROM dbo.CustomerChurn_EDA;
-- Beklenen: 10.000 · ortalama 38,92 · Q1 32 · medyan 37 · Q3 44 · std 10,49 · en küçük 18 · en büyük 92.

-- 2. IQR uç değer sınırları (SQL 23 ile aynı yapı): Q1 − 1,5·IQR ve Q3 + 1,5·IQR.
WITH Quartiles AS (
    SELECT DISTINCT
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY Age) OVER () AS Q1,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY Age) OVER () AS Q3
    FROM dbo.CustomerChurn_EDA
),
Bounds AS (
    SELECT
        Q1,
        Q3,
        Q3 - Q1                AS IQR,
        Q1 - 1.5 * (Q3 - Q1)   AS LowerBound,
        Q3 + 1.5 * (Q3 - Q1)   AS UpperBound
    FROM Quartiles
)
SELECT
    CAST(b.Q1 AS decimal(6,2))         AS Q1,
    CAST(b.Q3 AS decimal(6,2))         AS Q3,
    CAST(b.IQR AS decimal(6,2))        AS IQR,
    CAST(b.LowerBound AS decimal(6,2)) AS LowerBound,
    CAST(b.UpperBound AS decimal(6,2)) AS UpperBound,
    SUM(CASE WHEN e.Age < b.LowerBound THEN 1 ELSE 0 END) AS BelowLower,
    SUM(CASE WHEN e.Age > b.UpperBound THEN 1 ELSE 0 END) AS AboveUpper,
    CAST(100.0 * SUM(CASE WHEN e.Age > b.UpperBound THEN 1 ELSE 0 END) / COUNT(*) AS decimal(5,2)) AS AboveUpperPct
FROM dbo.CustomerChurn_EDA AS e
CROSS JOIN Bounds AS b
GROUP BY b.Q1, b.Q3, b.IQR, b.LowerBound, b.UpperBound;
-- Beklenen: IQR 12 · alt sınır 14 · üst sınır 62 · alt aday 0 · üst aday 359 (%3,59).

-- 3. Notebook Bölüm 2b ile aynı 10 yıllık yaş aralıkları (70 ve üstü birleşik).
--    Eşit genişlikli aralıklar seçildi; istatistiksel sınırlar (medyan, IQR) ile yaşam evresi
--    etiketleri karıştırılmaz.
SELECT
    v.AgeGroupOrder,
    v.AgeGroup,
    COUNT(*) AS CustomerCount,
    CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS decimal(5,2)) AS SharePct
FROM dbo.CustomerChurn_EDA AS e
CROSS APPLY (VALUES (
    CASE
        WHEN e.Age < 30 THEN 1
        WHEN e.Age < 40 THEN 2
        WHEN e.Age < 50 THEN 3
        WHEN e.Age < 60 THEN 4
        WHEN e.Age < 70 THEN 5
        ELSE 6
    END,
    CASE
        WHEN e.Age < 30 THEN N'18–29'
        WHEN e.Age < 40 THEN N'30–39'
        WHEN e.Age < 50 THEN N'40–49'
        WHEN e.Age < 60 THEN N'50–59'
        WHEN e.Age < 70 THEN N'60–69'
        ELSE N'70+'
    END
)) AS v (AgeGroupOrder, AgeGroup)
GROUP BY v.AgeGroupOrder, v.AgeGroup
ORDER BY v.AgeGroupOrder;
-- Beklenen: 18–29: 1.641 · 30–39: 4.346 · 40–49: 2.618 · 50–59: 869 · 60–69: 375 · 70+: 151.
-- En küçük yaş 18 olduğu için 18'den küçük grup yoktur.

-- 4. Notebook Bölüm 1 histogramıyla aynı 5 yıllık sınıflar: [18, 23), [23, 28), ...
--    Sınıf alt sınırı CROSS APPLY ile bir kez hesaplanır; SELECT, GROUP BY ve ORDER BY onu kullanır.
--    (e.Age - 18) / 5 tam sayı bölmesidir; kesirli kısım atılır.
SELECT
    b.ClassLower,
    CONCAT(N'[', b.ClassLower, N', ', b.ClassLower + 5, N')') AS HistogramClass,
    COUNT(*) AS CustomerCount,
    CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS decimal(5,2)) AS SharePct
FROM dbo.CustomerChurn_EDA AS e
CROSS APPLY (VALUES (18 + ((e.Age - 18) / 5) * 5)) AS b (ClassLower)
GROUP BY b.ClassLower
ORDER BY b.ClassLower;
-- Beklenen ilk sınıflar: [18, 23): 226 · [23, 28): 794 · [28, 33): 1.770 · [33, 38): 2.297 · [38, 43): 2.019.

-- 5. Yaş ile ilişki süresi arasındaki fark (gözlem, kalite hatası değil).
SELECT SUM(CASE WHEN Age - Tenure < 18 THEN 1 ELSE 0 END) AS AgeMinusTenureBelow18
FROM dbo.CustomerChurn_EDA;
-- Beklenen: 322. Tenure birimi ve hesap açılış yaşı kuralı bilinmediği için bu kayıtlar hata sayılmaz
-- (2026-10-14 kararı); yalnızca gözlem olarak kaydedilir.

-- Yorum:
-- 1. Ortalama (38,92) medyandan (37) büyük: dağılım sağa çarpık.
-- 2. IQR üst sınırı 62'nin üzerinde 359 müşteri (%3,59) var. Bunlar veri hatası olarak görülmez,
--    silinmez ve analizde korunur. Bu müşterilerin kim olduğu (ör. emeklilik durumu) veride yok.
-- 3. Veride 18 yaşından küçük müşteri yok. Bunun bir seçim kuralından mı yoksa verinin doğasından mı
--    kaynaklandığı bilinmiyor.
-- 4. Yaşın ayrılmayla ilişkisi (ters U) burada incelenmez; bkz. notebooks/01_eda.ipynb Bölüm 2b.
