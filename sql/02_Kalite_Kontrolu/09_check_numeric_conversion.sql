-- Amaç: Sayı gibi görünen ham verilerin gerçekten sayı olarak kullanılabilip kullanılamayacağını görmek istiyoruz.
-- Örneğin Age sütunundaki herhangi bir yaş şuanda string formatında duruyor.(nvarchar). 
-- İşlem yapabilmemiz için sayısal formata çevirmemiz gerekiyor.
-- Yalnızca SELECT kullanır; tablo türlerini ve ham değerleri değiştirmez.
-- İkili alanların 0/1 kontrolü 07 numaralı sorguda yapıldı.
USE [ChurnAnalysis];
GO

SELECT
    v.column_name,
    v.target_type,
    COUNT_BIG(*) AS total_rows,
    SUM(v.conversion_failed) AS conversion_failure_count,
    -- Hatalı değer varsa bir örnek gösterir; yoksa NULL döner.
    MIN(CASE WHEN v.conversion_failed = 1 THEN v.raw_value END) AS invalid_example
FROM dbo.CustomerChurn_Raw AS r
CROSS APPLY (VALUES
    (1, N'RowNumber', N'int', r.RowNumber,
        CASE WHEN TRY_CONVERT(int, NULLIF(TRIM(r.RowNumber), N'')) IS NULL THEN 1 ELSE 0 END),
    (2, N'CustomerId', N'bigint', r.CustomerId,
        CASE WHEN TRY_CONVERT(bigint, NULLIF(TRIM(r.CustomerId), N'')) IS NULL THEN 1 ELSE 0 END),
    (3, N'CreditScore', N'int', r.CreditScore,
        CASE WHEN TRY_CONVERT(int, NULLIF(TRIM(r.CreditScore), N'')) IS NULL THEN 1 ELSE 0 END),
    (4, N'Age', N'int', r.Age,
        CASE WHEN TRY_CONVERT(int, NULLIF(TRIM(r.Age), N'')) IS NULL THEN 1 ELSE 0 END),
    (5, N'Tenure', N'int', r.Tenure,
        CASE WHEN TRY_CONVERT(int, NULLIF(TRIM(r.Tenure), N'')) IS NULL THEN 1 ELSE 0 END),
    (6, N'Balance', N'decimal(19,2)', r.Balance,
        CASE WHEN TRY_CONVERT(decimal(19,2), NULLIF(TRIM(r.Balance), N'')) IS NULL THEN 1 ELSE 0 END),
    (7, N'NumOfProducts', N'int', r.NumOfProducts,
        CASE WHEN TRY_CONVERT(int, NULLIF(TRIM(r.NumOfProducts), N'')) IS NULL THEN 1 ELSE 0 END),
    (8, N'EstimatedSalary', N'decimal(19,2)', r.EstimatedSalary,
        CASE WHEN TRY_CONVERT(decimal(19,2), NULLIF(TRIM(r.EstimatedSalary), N'')) IS NULL THEN 1 ELSE 0 END)
) AS v(column_order, column_name, target_type, raw_value, conversion_failed)
GROUP BY v.column_order, v.column_name, v.target_type
ORDER BY v.column_order;

-- Beklenti: her alanda 10.000 kayıt, 0 dönüşüm hatası, NULL hatalı örnek.
-- TRY_CONVERT başarısız dönüşümde sorguyu durdurmak yerine NULL döndürür.
-- CustomerId sayısal biçimde kontrol edilir; model özelliği yapılmaz.