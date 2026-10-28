-- Amaç: Balance/EstimatedSalary için decimal(19,2) dönüşümünde
-- sayısal değer değişiyor mu? Yalnızca SELECT; ham veri değişmez.
USE [ChurnAnalysis];
GO

;WITH PrecisionCheck AS
(
    SELECT
        v.column_order,
        v.column_name,
        t.cleaned_value,
        n.reference_value,
        n.two_decimal_value,
        -- Referans decimal türü 18 ondalık basamak saklar.
        -- Daha uzun veya farklı biçimli bir metni sessizce geçmiş saymayız.
        CASE
            WHEN t.cleaned_value COLLATE Latin1_General_100_BIN2 LIKE N'%[^0-9.+-]%'
                OR (CHARINDEX(N'.', t.cleaned_value) > 0
                    AND LEN(t.cleaned_value) - CHARINDEX(N'.', t.cleaned_value) > 18)
            THEN 1 ELSE 0
        END AS needs_manual_check
    FROM dbo.CustomerChurn_Raw AS r
    CROSS APPLY (VALUES
        (1, N'Balance', r.Balance),
        (2, N'EstimatedSalary', r.EstimatedSalary)
    ) AS v(column_order, column_name, raw_value)
    CROSS APPLY (VALUES
        (NULLIF(TRIM(v.raw_value), N''))
    ) AS t(cleaned_value)
    CROSS APPLY (VALUES
        (TRY_CONVERT(decimal(38,18), t.cleaned_value),
         TRY_CONVERT(decimal(19,2), t.cleaned_value))
    ) AS n(reference_value, two_decimal_value)
)
SELECT
    column_name,
    COUNT_BIG(*) AS total_rows,
    SUM(CASE
        WHEN reference_value IS NULL OR two_decimal_value IS NULL THEN 1
        ELSE 0 END) AS conversion_failure_count,
    SUM(needs_manual_check) AS manual_check_count,
    SUM(CASE
        WHEN needs_manual_check = 0 AND reference_value <> two_decimal_value THEN 1
        ELSE 0 END) AS rounded_value_count,
    -- Değer değiştiyse ham metni ve iki basamaklı halini yan yana gösterir.
    MIN(CASE
        WHEN needs_manual_check = 0 AND reference_value <> two_decimal_value
        THEN CONCAT(cleaned_value, N' -> ', two_decimal_value)
    END) AS rounded_example
FROM PrecisionCheck
GROUP BY column_order, column_name
ORDER BY column_order;

-- Örnekler: 123.456 -> 123.46 değişikliktir; 123.450 -> 123.45 aynı sayıdır.
-- Kontrol hedefi: her alanda 10.000 kayıt; dönüşüm hatası, manuel kontrol
-- ve yuvarlanan değer sayıları 0; rounded_example NULL.
-- Üç sayının hepsi 0 ise bu kaynak değerleri iki basamakla sayısal kayıpsız
-- temsil edebiliriz. Metnin biçimi/sondaki sıfırlar değişebilir.
-- Manuel kontrol veya dönüşüm hatası varsa rounded_value_count=0 tek başına
-- yeterli değildir. Sonuç incelenmeden tür değişikliği veya yuvarlama yapılmaz.