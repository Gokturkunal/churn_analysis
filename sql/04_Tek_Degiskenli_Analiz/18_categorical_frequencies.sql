-- Amaç: kategorik ve ikili alanların (Geography, Gender, HasCrCard, IsActiveMember, Exited)
-- frekansları ve payları; tek sorguyla.
-- Kaynak: dbo.CustomerChurn_EDA. Yalnızca okur; tabloyu değiştirmez.
-- Yöntem: CROSS APPLY (VALUES ...) her müşteri satırını beş satıra açar (alan adı, değer);
-- böylece aynı frekans sorgusunu beş kez kopyalamak gerekmez. Pay, her alanın kendi toplamına
-- bölünerek pencere fonksiyonuyla hesaplanır: SUM(COUNT_BIG(*)) OVER (PARTITION BY alan).
-- İkili alanlar metne çevrilir ki aynı sütunda kategorik değerlerle birlikte durabilsin.
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
    (1, N'Geography',      e.Geography),
    (2, N'Gender',         e.Gender),
    (3, N'HasCrCard',      CAST(e.HasCrCard AS nvarchar(10))),
    (4, N'IsActiveMember', CAST(e.IsActiveMember AS nvarchar(10))),
    (5, N'Exited',         CAST(e.Exited AS nvarchar(10)))
) AS v (FieldOrder, FieldName, FieldValue)
GROUP BY v.FieldOrder, v.FieldName, v.FieldValue
ORDER BY v.FieldOrder, v.FieldValue;

-- Beklenen (ham CSV ve notebook Bölüm 1 ile doğrulandı):
--   Geography:      France 5.014 (%50,14) · Germany 2.509 (%25,09) · Spain 2.477 (%24,77)
--   Gender:         Female 4.543 (%45,43) · Male 5.457 (%54,57)
--   HasCrCard:      0: 2.945 (%29,45) · 1: 7.055 (%70,55)
--   IsActiveMember: 0: 4.849 (%48,49) · 1: 5.151 (%51,51)
--   Exited:         0: 7.963 (%79,63) · 1: 2.037 (%20,37)
-- Her alanda pay toplamı %100 olmalı; beklenmeyen bir değer (ör. 0/1 dışı) ayrı satır olarak görünür.
-- Kategorilerde küçük grup yok (en küçük grup 2.477 müşteri).
-- Ayrılmayla ilişki burada incelenmez (tek değişkenli özet); bkz. notebooks/01_eda.ipynb Bölüm 2.
