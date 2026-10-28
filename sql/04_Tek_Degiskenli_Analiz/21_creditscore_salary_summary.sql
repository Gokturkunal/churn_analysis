-- Amaç: CreditScore (kredi puanı) ve EstimatedSalary (tahmini gelir) için tek değişkenli özetler
-- ve uç değer sayımları.
-- Kaynak: dbo.CustomerChurn_EDA. Yalnızca okur; tabloyu değiştirmez.
-- Notebook karşılığı: Bölüm 1 (veri profili).
USE [ChurnAnalysis];
GO

-- 1. CreditScore özeti
SELECT DISTINCT
    COUNT(*)                                                  OVER () AS CustomerCount,
    CAST(AVG(1.0 * CreditScore) OVER () AS decimal(8,2))              AS Mean,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY CreditScore) OVER () AS Q1,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY CreditScore) OVER () AS Median,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY CreditScore) OVER () AS Q3,
    CAST(STDEV(CreditScore) OVER () AS decimal(8,2))                  AS StdDev,
    MIN(CreditScore)                                          OVER () AS MinScore,
    MAX(CreditScore)                                          OVER () AS MaxScore
FROM dbo.CustomerChurn_EDA;
-- Beklenen: ortalama 650,53 · Q1 584 · medyan 652 · Q3 718 · std 96,65 · en küçük 350 · en büyük 850.
-- IQR = 134; IQR sınırları 383 ve 919 (üst sınır ölçeğin dışında kalır).

-- 2. EstimatedSalary özeti
SELECT DISTINCT
    COUNT(*)                                                                                     OVER () AS CustomerCount,
    CAST(AVG(EstimatedSalary) OVER () AS decimal(12,2))                                                  AS Mean,
    CAST(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY EstimatedSalary) OVER () AS decimal(12,2))         AS Q1,
    CAST(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY EstimatedSalary) OVER () AS decimal(12,2))         AS Median,
    CAST(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY EstimatedSalary) OVER () AS decimal(12,2))         AS Q3,
    CAST(STDEV(EstimatedSalary) OVER () AS decimal(12,2))                                                AS StdDev,
    MIN(EstimatedSalary)                                                                         OVER () AS MinSalary,
    MAX(EstimatedSalary)                                                                         OVER () AS MaxSalary
FROM dbo.CustomerChurn_EDA;
-- Beklenen: ortalama 100.090,24 · Q1 51.002,11 · medyan 100.193,92 · Q3 149.388,25 · std 57.510,49 ·
-- en küçük 11,58 · en büyük 199.992,48. Para birimi ve dönem (aylık/yıllık) bilinmiyor.

-- 3. Uçlardaki yığılma ve küçük değer sayımları
SELECT
    SUM(CASE WHEN CreditScore = 850 THEN 1 ELSE 0 END)      AS Score_850,
    SUM(CASE WHEN CreditScore = 849 THEN 1 ELSE 0 END)      AS Score_849,
    SUM(CASE WHEN CreditScore = 350 THEN 1 ELSE 0 END)      AS Score_350,
    SUM(CASE WHEN CreditScore < 383 THEN 1 ELSE 0 END)      AS Score_below_iqr_lower,
    SUM(CASE WHEN EstimatedSalary < 1000 THEN 1 ELSE 0 END)  AS Salary_below_1000,
    SUM(CASE WHEN EstimatedSalary < 10000 THEN 1 ELSE 0 END) AS Salary_below_10000
FROM dbo.CustomerChurn_EDA;
-- Beklenen: 233 · 8 · 5 · 15 · 59 · 508.

-- Yorum:
-- 1. Kredi puanı yaklaşık simetrik; ancak 850'de 233 müşteri (%2,33) yığılıyor, 849'da yalnızca 8.
--    Olası açıklamalar ölçek tavanı veya üst değerlerin 850'ye kırpılması; kaynak tanımı olmadan
--    hangisinin doğru olduğu doğrulanamaz.
-- 2. IQR alt sınırı 383'ün altında 15 müşteri var; bunlar silinmez.
-- 3. Tahmini gelirin çeyrekleri ve standart sapması yaklaşık düz (uniform) bir dağılımla uyumlu.
--    Gerçek gelir dağılımları genellikle sağa çarpıktır; bu düzgünlük verinin yapay üretilmiş
--    olabileceğini düşündürür. Kaynak ve gelir tanımı doğrulanmadı.
-- 4. Bu dosya tek değişkenli özettir; ayrılmayla ilişki burada yorumlanmaz.
--    Notebook Bölüm 2b: kredi puanı ve gelir ayrılmayla ilişkili değil (AUC 0,48 ve 0,51);
--    850 grubu genel orandan farklı değil. Tek istisna alt uçta: kalan müşterilerin en düşük puanı 405
--    ve 405'in altındaki 21 müşterinin hepsi ayrılmış (grup çok küçük; yapay veri özelliği olabilir).
