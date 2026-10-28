-- Amaç: view'ın sütun türlerini ve eksik değer oluşturup oluşturmadığını görmek.
-- Yalnızca SELECT; view tanımını veya ham kayıtları değiştirmez.
USE [ChurnAnalysis];
GO

-- 1. Sonuç: SQL Server'ın sakladığı gerçek sütun bilgileri.
-- INFORMATION_SCHEMA.COLUMNS verinin kendisini değil, sütun tanımlarını gösterir.
SELECT
    COLUMN_NAME AS column_name,
    DATA_TYPE AS data_type,
    NUMERIC_PRECISION AS numeric_precision,
    NUMERIC_SCALE AS numeric_scale
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = N'dbo'
  AND TABLE_NAME = N'vw_CustomerChurn_Analysis'
ORDER BY ORDINAL_POSITION;

-- Beklenen: 12 sütun. CustomerId bigint; CreditScore/Age/Tenure/NumOfProducts int;
-- Balance/EstimatedSalary decimal, precision=19 ve scale=2;
-- HasCrCard/IsActiveMember/Exited tinyint; Geography/Gender nvarchar.
-- Metinlerde numeric_precision/numeric_scale NULL olması normaldir.

-- 2. Sonuç: en az bir eksik alanı olan müşteri kaydı sayısı.
-- OR: bu koşullardan herhangi biri doğruysa kayıt sayılır.
-- IS NULL: eksik değer kontrolü; '= NULL' kullanılmaz.
SELECT COUNT_BIG(*) AS rows_with_missing_value
FROM dbo.vw_CustomerChurn_Analysis
WHERE CustomerId IS NULL
   OR CreditScore IS NULL
   OR NULLIF(TRIM(Geography), N'') IS NULL
   OR NULLIF(TRIM(Gender), N'') IS NULL
   OR Age IS NULL
   OR Tenure IS NULL
   OR Balance IS NULL
   OR NumOfProducts IS NULL
   OR HasCrCard IS NULL
   OR IsActiveMember IS NULL
   OR EstimatedSalary IS NULL
   OR Exited IS NULL;

-- Beklenen sayı: 0. Bir satırda birden fazla eksik varsa yine bir kez sayılır.
-- Bu sorgu bütün değer eşleşmelerini kanıtlamaz; o kontrol sonraki adımdır.
