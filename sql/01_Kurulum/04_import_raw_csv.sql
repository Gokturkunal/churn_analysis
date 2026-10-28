-- Amaç: özgün CSV'yi ham tabloya yüklemek; kaynak dosyayı değiştirmez.
-- Kaynak kontrolü: 10.000 veri satırı, UTF-8, Windows CRLF satır sonları.
-- SQL Server bu yerel dosyayı okuyabilmelidir.
USE [ChurnAnalysis];
GO

SET XACT_ABORT ON;

-- Tekrar çalıştırmada aynı müşterileri ikinci kez eklemeyi önler.
IF EXISTS (SELECT 1 FROM dbo.CustomerChurn_Raw)
BEGIN
    THROW 50001, N'Ham tablo boş değil. İkinci kez yükleme yapılmadı.', 1;
END;

BEGIN TRY
    BEGIN TRANSACTION;

    BULK INSERT dbo.CustomerChurn_Raw
    FROM 'C:\Users\goktu\Churn_analysis\Churn_Modelling.csv'
    WITH
    (
        FORMAT = 'CSV',
        CODEPAGE = '65001', -- UTF-8 karakter kodlaması
        FIRSTROW = 2,      -- İlk satır sütun başlıklarıdır.
        FIELDTERMINATOR = ',',
        ROWTERMINATOR = '\n', -- Windows'ta CRLF olarak yorumlanır.
        KEEPNULLS
    );

    -- Eksik aktarım varsa yüklemeyi geri alır; kaynakta 10.000 satır var.
    IF (SELECT COUNT_BIG(*) FROM dbo.CustomerChurn_Raw) <> 10000
    BEGIN
        THROW 50002, N'Satır sayısı kaynakla uyuşmuyor. Yükleme geri alındı.', 1;
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;

SELECT COUNT_BIG(*) AS raw_row_count
FROM dbo.CustomerChurn_Raw;
