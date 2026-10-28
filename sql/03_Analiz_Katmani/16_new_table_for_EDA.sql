-- Amaç: Power BI ve EDA için müşteri seviyesinde, kimlikli fiziksel tablo.
-- Kaynak: dbo.vw_CustomerChurn_Analysis (12 alan). Ham tablo ve view değişmez.
-- 2026-10-07: kimliksiz ilk sürüm bu tabloyla değiştirildi.
-- Kontrol sonuçları: 10000 satır / 10000 kimlik / 2037 ayrılan; eski ve yeni tablo farkı 0 / 0;
-- CustomerId bigint NOT NULL ve PK_CustomerChurn_EDA birincil anahtarı mevcut.
-- Tekrar çalıştırmak güvenlidir: tablo ve anahtar varsa hiçbir şey değiştirmez.
USE [ChurnAnalysis];
GO

-- Tablo yoksa oluşturur. Varsa bu blok atlanır; mevcut tablonun üzerine yazılmaz.
IF OBJECT_ID(N'dbo.CustomerChurn_EDA', N'U') IS NULL
BEGIN
    SELECT
        CustomerId, CreditScore, Geography, Gender, Age, Tenure, Balance,
        NumOfProducts, HasCrCard, IsActiveMember, EstimatedSalary, Exited
    INTO dbo.CustomerChurn_EDA
    FROM dbo.vw_CustomerChurn_Analysis;

    -- View'daki CAST ifadesi sütunu NULL kabul eden türde getirir.
    -- Birincil anahtar için önce NOT NULL yapılır.
    ALTER TABLE dbo.CustomerChurn_EDA
    ALTER COLUMN CustomerId bigint NOT NULL;
END;
GO

-- Birincil anahtar yoksa ekler. GO, bu bloğun tablo oluştuktan sonra derlenmesini sağlar.
IF NOT EXISTS (
    SELECT 1
    FROM sys.key_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.CustomerChurn_EDA')
      AND type = 'PK'
)
BEGIN
    ALTER TABLE dbo.CustomerChurn_EDA
    ADD CONSTRAINT PK_CustomerChurn_EDA PRIMARY KEY (CustomerId);
END;
GO

-- Kontrol. Beklenen: 10000 / 10000 / 2037
SELECT
    COUNT_BIG(*)               AS row_count,
    COUNT(DISTINCT CustomerId) AS unique_customer_ids,
    SUM(CAST(Exited AS int))   AS exited_count
FROM dbo.CustomerChurn_EDA;

-- View değişir ve tablo yeniden oluşturulmak istenirse bu betik bunu kendiliğinden yapmaz;
-- önce tablo bilinçli olarak elle DROP edilmelidir. Bu, yanlışlıkla üzerine yazmayı önler.
