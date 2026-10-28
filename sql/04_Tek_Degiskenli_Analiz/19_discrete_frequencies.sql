-- Amaç: kesikli sayısal alanların (NumOfProducts, Tenure) frekansları ve payları; tek sorguyla.
-- Kaynak: dbo.CustomerChurn_EDA. Yalnızca okur; tabloyu değiştirmez.
-- Yöntem SQL 18 ile aynıdır: CROSS APPLY (VALUES ...) ve SUM(COUNT_BIG(*)) OVER (PARTITION BY alan).
-- Değerler tam sayı olarak kalır; böylece 10 değeri 2'den sonra sıralanır (metin sıralamasında olmazdı).
USE [ChurnAnalysis];
GO

SELECT
    v.FieldOrder,
    v.FieldName,
    v.FieldValue,
    COUNT_BIG(*) AS CustomerCount,
    CAST(100.0 * COUNT_BIG(*) / SUM(COUNT_BIG(*)) OVER (PARTITION BY v.FieldName) AS decimal(5,2)) AS SharePct
FROM dbo.CustomerChurn_EDA AS e
CROSS APPLY (VALUES
    (1, N'NumOfProducts', e.NumOfProducts),
    (2, N'Tenure',        e.Tenure)
) AS v (FieldOrder, FieldName, FieldValue)
GROUP BY v.FieldOrder, v.FieldName, v.FieldValue
ORDER BY v.FieldOrder, v.FieldValue;

-- Beklenen (ham CSV ve notebook Bölüm 1 ile doğrulandı):
--   NumOfProducts: 1: 5.084 · 2: 4.590 · 3: 266 · 4: 60. Müşterilerin %96,74'ü 1 veya 2 ürünlü.
--     4 ürünlü grup 100 müşterinin altında; oranları tek başına yorumlanmaz (notebook Bölüm 3 kuralı).
--   Tenure: 0: 413 · 1: 1.035 · 2: 1.048 · 3: 1.009 · 4: 989 · 5: 1.012 · 6: 967 · 7: 1.028 ·
--           8: 1.025 · 9: 984 · 10: 490.
-- Gözlem: Tenure 1–9 arasında frekanslar birbirine çok yakın; 0 ve 10'da yaklaşık yarısı.
-- Bu düzgünlük verinin yapay üretilmiş olabileceğini düşündürür. 0 ve 10'un neden düşük olduğu veride yok
-- (tam yıla yuvarlama bir olasılık; Tenure birimi ve tanımı doğrulanmadı).
