-- Amaç: Balance (bakiye) için tek değişkenli özet. Sıfır bakiye ayrı incelenir, çünkü müşterilerin
-- üçte biri sıfırda yığılıyor ve bu yığılma tüm-veri ortalamasını yanıltıcı yapar.
-- Kaynak: dbo.CustomerChurn_EDA. Yalnızca okur; tabloyu değiştirmez.
-- Notebook karşılığı: Bölüm 1 (veri profili).
USE [ChurnAnalysis];
GO

-- 1. Sıfır ve pozitif bakiye dağılımı
SELECT
    v.BalanceStatus,
    COUNT(*) AS CustomerCount,
    CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS decimal(5,2)) AS SharePct
FROM dbo.CustomerChurn_EDA AS e
CROSS APPLY (VALUES (CASE WHEN e.Balance = 0 THEN N'Sıfır' ELSE N'Pozitif' END)) AS v (BalanceStatus)
GROUP BY v.BalanceStatus
ORDER BY v.BalanceStatus DESC;
-- Beklenen: Sıfır 3.617 (%36,17) · Pozitif 6.383 (%63,83). Negatif bakiye yok (SQL 10).

-- 2. Tüm müşterilerde Balance özeti (sıfırlar dahil)
SELECT DISTINCT
    COUNT(*)                                                                             OVER () AS CustomerCount,
    CAST(AVG(Balance) OVER () AS decimal(12,2))                                                  AS Mean,
    CAST(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY Balance) OVER () AS decimal(12,2))         AS Q1,
    CAST(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY Balance) OVER () AS decimal(12,2))         AS Median,
    CAST(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY Balance) OVER () AS decimal(12,2))         AS Q3,
    CAST(STDEV(Balance) OVER () AS decimal(12,2))                                                AS StdDev,
    MIN(Balance)                                                                         OVER () AS MinBalance,
    MAX(Balance)                                                                         OVER () AS MaxBalance
FROM dbo.CustomerChurn_EDA;
-- Beklenen: ortalama 76.485,89 · Q1 0 · medyan 97.198,54 · Q3 127.644,24 · en büyük 250.898,09.

-- 3. Yalnızca pozitif bakiyeli müşterilerde Balance özeti
SELECT DISTINCT
    COUNT(*)                                                                             OVER () AS CustomerCount,
    CAST(AVG(Balance) OVER () AS decimal(12,2))                                                  AS Mean,
    CAST(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY Balance) OVER () AS decimal(12,2))         AS Q1,
    CAST(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY Balance) OVER () AS decimal(12,2))         AS Median,
    CAST(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY Balance) OVER () AS decimal(12,2))         AS Q3,
    CAST(STDEV(Balance) OVER () AS decimal(12,2))                                                AS StdDev,
    MIN(Balance)                                                                         OVER () AS MinBalance,
    MAX(Balance)                                                                         OVER () AS MaxBalance
FROM dbo.CustomerChurn_EDA
WHERE Balance > 0;
-- Beklenen: 6.383 · ortalama 119.827,49 · Q1 100.181,98 · medyan 119.839,69 · Q3 139.512,29 ·
-- std 30.095,06 · en küçük 3.768,69 · en büyük 250.898,09.

-- Yorum:
-- 1. Müşterilerin %36,17'sinin bakiyesi tam sıfır. Bu yüzden tüm-veri ortalaması (76.486) pozitif
--    bakiyelerin ortalamasından (119.827) çok düşük; bakiye "sıfır mı?" ve "pozitifse ne kadar?" diye
--    iki parçada incelenir.
-- 2. Pozitif bakiyelerde ortalama ile medyan çok yakın (yaklaşık 120 bin); dağılım yaklaşık simetrik ve
--    çan şeklinde (notebook Bölüm 1 histogramı). Bu özet normal dağılımı tek başına kanıtlamaz.
-- 3. Sıfır bakiyenin iş anlamı (kapalı hesap, yalnızca kart kullanımı vb.) veride yok. Almanya'da sıfır
--    bakiyeli müşteri yok; bu durumun ayrılma analizine etkisi notebook Bölüm 4b'de incelendi.
