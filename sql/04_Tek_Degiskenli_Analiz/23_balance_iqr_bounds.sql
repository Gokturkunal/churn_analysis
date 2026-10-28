-- Amaç: pozitif bakiyelerde IQR uç değer sınırları ve sınır dışındaki müşteri sayıları.
-- Sıfır bakiyeler hesaba katılmaz; aksi hâlde Q1 sıfıra düşer ve sınırlar anlamsızlaşır (SQL 22).
-- Kaynak: dbo.CustomerChurn_EDA. Yalnızca okur; tabloyu değiştirmez.
-- Yapı SQL 20'deki yaş IQR sorgusuyla aynıdır.
USE [ChurnAnalysis];
GO

WITH Quartiles AS (
    -- Yalnızca pozitif bakiyelerde Q1 ve Q3
    SELECT DISTINCT
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY Balance) OVER () AS Q1,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY Balance) OVER () AS Q3
    FROM dbo.CustomerChurn_EDA
    WHERE Balance > 0
),
Bounds AS (
    -- IQR ve uç değer sınırları: Q1 − 1,5·IQR ve Q3 + 1,5·IQR
    SELECT
        Q1 - 1.5 * (Q3 - Q1) AS LowerBound,
        Q3 + 1.5 * (Q3 - Q1) AS UpperBound
    FROM Quartiles
)
SELECT
    CAST(b.LowerBound AS decimal(12,2)) AS LowerBound,
    CAST(b.UpperBound AS decimal(12,2)) AS UpperBound,
    SUM(CASE WHEN e.Balance > 0 AND e.Balance < b.LowerBound THEN 1 ELSE 0 END) AS BelowLower,
    SUM(CASE WHEN e.Balance > b.UpperBound                  THEN 1 ELSE 0 END) AS AboveUpper,
    SUM(CASE WHEN e.Balance > 0                             THEN 1 ELSE 0 END) AS PositiveTotal
FROM dbo.CustomerChurn_EDA AS e
CROSS JOIN Bounds AS b
GROUP BY b.LowerBound, b.UpperBound;

-- Beklenen: alt sınır 41.186,50 · üst sınır 198.507,76 · alt aday 36 · üst aday 37 · pozitif toplam 6.383.
-- Yorum: Sınır dışındaki 73 müşteri pozitif bakiyelilerin %1,14'ü. Adaylar veri hatası sayılmaz ve silinmez.
-- IQR kuralı bir işaretleme yöntemidir; dağılımın normal olduğunu tek başına kanıtlamaz.
-- 2026-10-19: dosya adı 24_balance_ucsınırlar.sql idi; numara sırası ve klasörü düzeltilerek 23 yapıldı.
