-- Amaç: view'daki 0/1 göstergelerini ve müşteri bazında ham/view değer eşleşmesini kontrol etmek.
-- Yalnızca okuma yapar; ham tabloyu veya view tanımını değiştirmez.
USE [ChurnAnalysis];
GO

-- 1. Sonuç: üç göstergeden en az biri NULL veya 0/1 dışında olan kayıt sayısı.
SELECT COUNT_BIG(*) AS rows_with_invalid_binary_value
FROM dbo.vw_CustomerChurn_Analysis
WHERE HasCrCard IS NULL OR HasCrCard NOT IN (0, 1)
   OR IsActiveMember IS NULL OR IsActiveMember NOT IN (0, 1)
   OR Exited IS NULL OR Exited NOT IN (0, 1);

-- 2. Sonuç: eşleşmeyen müşteri veya en az bir farklı alan içeren kayıt sayısı.
-- CustomerId ile eşleştirilir; kalan 11 alan tek tek karşılaştırılır.
-- Para alanlarında daha hassas ham referans kullanılır (SQL 11'de doğrulanan biçim).
SELECT COUNT_BIG(*) AS rows_with_raw_view_mismatch
FROM dbo.CustomerChurn_Raw AS r
FULL OUTER JOIN dbo.vw_CustomerChurn_Analysis AS a
    ON CAST(NULLIF(TRIM(r.CustomerId), N'') AS bigint) = a.CustomerId
WHERE r.CustomerId IS NULL
   OR a.CustomerId IS NULL
   OR CAST(NULLIF(TRIM(r.CreditScore), N'') AS int) IS DISTINCT FROM a.CreditScore
   OR CAST(TRIM(r.Geography) AS varbinary(max)) IS DISTINCT FROM CAST(a.Geography AS varbinary(max))
   OR CAST(TRIM(r.Gender) AS varbinary(max)) IS DISTINCT FROM CAST(a.Gender AS varbinary(max))
   OR CAST(NULLIF(TRIM(r.Age), N'') AS int) IS DISTINCT FROM a.Age
   OR CAST(NULLIF(TRIM(r.Tenure), N'') AS int) IS DISTINCT FROM a.Tenure
   OR CAST(NULLIF(TRIM(r.Balance), N'') AS decimal(38,18)) IS DISTINCT FROM a.Balance
   OR CAST(NULLIF(TRIM(r.NumOfProducts), N'') AS int) IS DISTINCT FROM a.NumOfProducts
   OR CAST(NULLIF(TRIM(r.HasCrCard), N'') AS int) IS DISTINCT FROM a.HasCrCard
   OR CAST(NULLIF(TRIM(r.IsActiveMember), N'') AS int) IS DISTINCT FROM a.IsActiveMember
   OR CAST(NULLIF(TRIM(r.EstimatedSalary), N'') AS decimal(38,18)) IS DISTINCT FROM a.EstimatedSalary
   OR CAST(NULLIF(TRIM(r.Exited), N'') AS int) IS DISTINCT FROM a.Exited;

-- Kontrol hedefi: iki sonuç da 0. 2026-10-07 tarihinde çalıştırıldı; iki sonuç da 0 çıktı.
-- Bir müşteride birden fazla alan farklıysa ikinci sonuçta yine bir kez sayılır.
-- Metinler TRIM sonrası tam karakter karşılığıyla karşılaştırılır; harf farkı gizlenmez.
-- SQL 13'te doğrulanan benzersiz kimlikler esas alınır; bu sorgu yeni tekrar kontrolü değildir.
-- Kontrol CSV ile ham tablonun tüm değerlerini karşılaştırmaz; ham ile view arasını denetler.
-- Sorgu hata verirse kontrol tamamlanmış sayılmaz; hata/sonuç incelenir.
