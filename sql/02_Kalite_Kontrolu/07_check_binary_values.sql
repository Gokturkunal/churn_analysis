-- Amaç: üç ikili alandaki değerleri ve kayıt sayılarını görmek.
-- Beklenen değerler 0 ve 1; ham tablo değiştirilmez.
USE [ChurnAnalysis];
GO

SELECT
    v.column_name,
    v.observed_value,
    COUNT_BIG(*) AS row_count,
    CASE
        WHEN v.observed_value IN (N'0', N'1') THEN N'Beklenen değer'
        ELSE N'İncelenmeli'
    END AS value_status
FROM dbo.CustomerChurn_Raw AS r
-- Üç alanı aynı kontrol mantığına açar.
-- TRIM yalnızca değerlendirmede baş/son normal boşlukları kaldırır.
CROSS APPLY (VALUES
    (1, N'Exited',         TRIM(r.Exited)),
    (2, N'HasCrCard',      TRIM(r.HasCrCard)),
    (3, N'IsActiveMember', TRIM(r.IsActiveMember))
) AS v(column_order, column_name, observed_value)
-- Örneğin Exited=0 olan kayıtlar tek grupta sayılır.
GROUP BY v.column_order, v.column_name, v.observed_value
ORDER BY v.column_order, v.observed_value;

-- Kontrol hedefi: her sütunda yalnızca 0 ve 1, durum 'Beklenen değer'.
-- Her sütunun row_count toplamı 10.000 olmalı.
-- Bu sorgu bit türüne dönüştürmeden önce yapılır: doğrudan bit dönüşümü
-- bazı beklenmeyen sayıları 1'e çevirebildiği için kaynak hatasını gizleyebilir.
