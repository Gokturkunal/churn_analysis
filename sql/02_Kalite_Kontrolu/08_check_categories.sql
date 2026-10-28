-- Amaç: Geography ve Gender kategorilerini, sayılarını ve baş/son boşlukları görmek.
-- Ham tablo değiştirilmez; kategori adları sayısal kodlara çevrilmez.
USE [ChurnAnalysis];
GO

SELECT
    v.column_name,
    TRIM(v.raw_value) COLLATE Latin1_General_100_BIN2 AS observed_value,
    COUNT_BIG(*) AS row_count,
    SUM(CASE
        WHEN DATALENGTH(v.raw_value) <> DATALENGTH(TRIM(v.raw_value)) THEN 1
        ELSE 0
    END) AS edge_space_count
FROM dbo.CustomerChurn_Raw AS r
CROSS APPLY (VALUES
    (1, N'Geography', r.Geography),
    (2, N'Gender',    r.Gender)
) AS v(column_order, column_name, raw_value)
-- BIN2 karşılaştırması France / france gibi yazım farklarını ayrı gösterir.
-- TRIM normal baş/son boşlukları gruplamada kaldırır; bunlar ayrıca sayılır.
-- DATALENGTH metnin byte uzunluğunu verir; normal son boşlukları da sayar.
GROUP BY
    v.column_order,
    v.column_name,
    TRIM(v.raw_value) COLLATE Latin1_General_100_BIN2
ORDER BY v.column_order, observed_value;

-- Her alan için row_count toplamı 10.000 olmalı.
-- Yeni/farklı kategoriler otomatik hata sayılmaz; anlamları incelenir.
-- Bu sorgu normal boşlukları kontrol eder; tüm görünmez Unicode karakterleri kapsamaz.
