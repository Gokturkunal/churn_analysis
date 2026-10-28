-- Amaç: her satırın dolu ve benzersiz müşteri kimliği taşıdığını kontrol etmek.
-- Yalnızca okur; ham tablodaki değerleri değiştirmez.
USE [ChurnAnalysis];
GO

SELECT
    COUNT_BIG(*) AS total_rows,
    -- TRIM: baştaki/sondaki normal boşlukları değerlendirmede kaldırır.
    -- NULLIF: boş metni NULL olarak değerlendirir.
    -- COUNT(DISTINCT ...): NULL olmayan farklı kimlikleri sayar.
    COUNT(DISTINCT NULLIF(TRIM(CustomerId), N'')) AS unique_customer_ids,
    -- Eksik kimlikte 1, dolu kimlikte 0; SUM bu 1'leri toplar.
    SUM(CASE
        WHEN NULLIF(TRIM(CustomerId), N'') IS NULL THEN 1
        ELSE 0
    END) AS missing_customer_ids
FROM dbo.CustomerChurn_Raw;

-- Kontrol hedefi: total_rows = unique_customer_ids = 10000,
-- Bu kontrol sayısal biçimi veya tam satır tekrarlarını ayrıca incelemez.


-- Sonuç on bin satırlık verinin tamamında müşteri id leri benzersizdir.
