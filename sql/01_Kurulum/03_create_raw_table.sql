-- Amaç: CSV'den gelen değerleri dönüşüm yapmadan tutacak ham tablo.
-- Sayısal alanlar da önce metin olarak alınır; türler kalite kontrolünden
-- sonra analiz tablosunda belirlenir. nvarchar Unicode metin saklar.
USE [ChurnAnalysis];
GO

IF OBJECT_ID(N'dbo.CustomerChurn_Raw', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.CustomerChurn_Raw
    (
        RowNumber       nvarchar(max) NULL,
        CustomerId      nvarchar(max) NULL,
        Surname         nvarchar(max) NULL,
        CreditScore     nvarchar(max) NULL,
        Geography       nvarchar(max) NULL,
        Gender          nvarchar(max) NULL,
        Age             nvarchar(max) NULL,
        Tenure          nvarchar(max) NULL,
        Balance         nvarchar(max) NULL,
        NumOfProducts   nvarchar(max) NULL,
        HasCrCard       nvarchar(max) NULL,
        IsActiveMember  nvarchar(max) NULL,
        EstimatedSalary nvarchar(max) NULL,
        Exited          nvarchar(max) NULL
    );
END;
GO

-- Yeni oluşturulan tablo için beklenen sayı: 0.
SELECT COUNT_BIG(*) AS raw_row_count
FROM dbo.CustomerChurn_Raw;
