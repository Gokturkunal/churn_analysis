-- 28 Ekim sürüm notu: Bu dosya ilk RF/Sigmoid sürümünün korunmuş 1.501 test skorunu yükler.
-- Yeni yöntem-v2 eğitim/geliştirme sonuçları bu dosyayla panele aktarılmadı. İlk EDA tüm verideydi,
-- test daha önce görüldü; yeni geliştirmelerde yeni bağımsız test diye sunulamaz. Skor gelecek
-- 30/60/90 günlük olay veya teklif yanıt olasılığı değildir. Bu yorum revizyonunda SQL çalıştırılmadı.

-- Amaç: ML son testindeki (notebooks/02_ml.ipynb Bölüm 8–9) 1.501 müşterinin skorlarını SQL'e yüklemek ve
--       Power BI Sayfa 3–4'ün okuyacağı view'ı kurmak.
-- Kaynak: data/processed/ml_test_skorlari.csv (UTF-8 BOM'lu, CRLF; 1.501 satır). Kaynak dosya değiştirilmez.
-- Model Python'dadır (Random Forest, aktifliksiz, Sigmoid kalibrasyon; 8.499 müşteride eğitildi). SQL modeli
-- yeniden hesaplamaz, yalnızca skorları saklar. Yalnızca son test müşterileri yüklenir: eğitim ve geliştirme
-- müşterilerinin skorları bağımsız tahmin sayılmadığı için dışa aktarılmadı ve panelde gösterilmez.
-- Ayrılma bilgisi burada yüklenmez; view EDA tablosundan alır (tek kaynak).
-- Yükleme kalıbı SQL 25 ile aynıdır: geçici tablo + transaction; kontrollerden biri başarısız olursa ROLLBACK.
-- Tekrar çalıştırmak güvenlidir: türetilmiş veri olduğu için tablo her çalıştırmada aynı dosyadan yenilenir.
-- BULK INSERT yolu bu bilgisayara özeldir; proje taşınırsa değiştirilmelidir.
USE [ChurnAnalysis];
GO

-- 1. Tablo yoksa oluşturulur; varsa yapısına dokunulmaz.
IF OBJECT_ID(N'dbo.CustomerScore', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.CustomerScore
    (
        CustomerId       bigint        NOT NULL CONSTRAINT PK_CustomerScore PRIMARY KEY
            CONSTRAINT FK_CustomerScore_EDA REFERENCES dbo.CustomerChurn_EDA (CustomerId),
        DataSplit        nvarchar(20)  NOT NULL,
        ModelScore       decimal(9,6)  NOT NULL,
        ScoreRank        int           NOT NULL CONSTRAINT UQ_CustomerScore_Rank UNIQUE,
        CapacityBand     nvarchar(20)  NOT NULL,
        SegmentRuleScore decimal(9,6)  NOT NULL,
        ModelVersion     nvarchar(200) NOT NULL
    );
END;
GO

DROP TABLE IF EXISTS #ScoreStage;
CREATE TABLE #ScoreStage
(
    CustomerId       nvarchar(50)  NULL,
    DataSplit        nvarchar(20)  NULL,
    ModelScore       nvarchar(50)  NULL,
    ScoreRank        nvarchar(50)  NULL,
    CapacityBand     nvarchar(20)  NULL,
    SegmentRuleScore nvarchar(50)  NULL,
    ModelVersion     nvarchar(200) NULL
);
GO

SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    BULK INSERT #ScoreStage
    FROM 'C:\Users\goktu\Churn_analysis\data\processed\ml_test_skorlari.csv'
    WITH
    (
        FORMAT = 'CSV',
        CODEPAGE = '65001',   -- UTF-8 (Türkçe karakterler: "Diğer", "İlk %10")
        FIRSTROW = 2,         -- İlk satır sütun başlıkları
        FIELDTERMINATOR = ',',
        ROWTERMINATOR = '\n', -- Windows'ta CRLF olarak yorumlanır
        KEEPNULLS
    );

    -- 2. Kontroller: herhangi biri başarısızsa yükleme geri alınır.
    IF (SELECT COUNT_BIG(*) FROM #ScoreStage) <> 1501
        THROW 50301, N'Dosyada 1.501 satır bekleniyordu. Yükleme geri alındı.', 1;

    IF EXISTS (
        SELECT 1 FROM #ScoreStage
        WHERE TRY_CONVERT(bigint, CustomerId) IS NULL
           OR TRY_CONVERT(decimal(9,6), ModelScore) IS NULL
           OR TRY_CONVERT(int, ScoreRank) IS NULL
           OR TRY_CONVERT(decimal(9,6), SegmentRuleScore) IS NULL
           OR NULLIF(TRIM(DataSplit), N'') IS NULL
           OR NULLIF(TRIM(CapacityBand), N'') IS NULL
    )
        THROW 50302, N'Boş veya sayıya çevrilemeyen değer var. Yükleme geri alındı.', 1;

    IF (SELECT COUNT(DISTINCT TRY_CONVERT(bigint, CustomerId)) FROM #ScoreStage) <> 1501
        THROW 50303, N'CustomerId tekrar ediyor. Yükleme geri alındı.', 1;

    -- Her skorlanan müşteri EDA tablosunda olmalı.
    IF EXISTS (
        SELECT 1 FROM #ScoreStage AS s
        LEFT JOIN dbo.CustomerChurn_EDA AS e ON e.CustomerId = TRY_CONVERT(bigint, s.CustomerId)
        WHERE e.CustomerId IS NULL
    )
        THROW 50304, N'Skor dosyasındaki bazı müşteriler EDA tablosunda yok. Yükleme geri alındı.', 1;

    -- Sıra 1..1501 arasında ve tekrarsız; skorlar 0–1 aralığında; yalnızca test bölümü.
    IF (SELECT COUNT(DISTINCT TRY_CONVERT(int, ScoreRank)) FROM #ScoreStage) <> 1501
       OR (SELECT MIN(TRY_CONVERT(int, ScoreRank)) FROM #ScoreStage) <> 1
       OR (SELECT MAX(TRY_CONVERT(int, ScoreRank)) FROM #ScoreStage) <> 1501
        THROW 50305, N'Sıra 1..1.501 arasında tekrarsız olmalı. Yükleme geri alındı.', 1;

    IF EXISTS (
        SELECT 1 FROM #ScoreStage
        WHERE TRY_CONVERT(decimal(9,6), ModelScore) NOT BETWEEN 0 AND 1
           OR TRY_CONVERT(decimal(9,6), SegmentRuleScore) NOT BETWEEN 0 AND 1
           OR TRIM(DataSplit) <> N'Test'
    )
        THROW 50306, N'Skor 0–1 dışında veya bölüm Test değil. Yükleme geri alındı.', 1;

    -- 3. Tablo yenilenir.
    DELETE FROM dbo.CustomerScore;

    INSERT INTO dbo.CustomerScore
        (CustomerId, DataSplit, ModelScore, ScoreRank, CapacityBand, SegmentRuleScore, ModelVersion)
    SELECT
        CAST(CustomerId AS bigint), TRIM(DataSplit), CAST(ModelScore AS decimal(9,6)), CAST(ScoreRank AS int),
        TRIM(CapacityBand), CAST(SegmentRuleScore AS decimal(9,6)), TRIM(ModelVersion)
    FROM #ScoreStage;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

-- 4. Power BI view'ı: skorlar + ayrılma bilgisi ve Türkçe grup etiketleri (SQL 28 view'ından).
--    Kapasite payı (sıra ÷ 1.501) Power BI'daki kapasite kaydırıcısı için hazır verilir.
CREATE OR ALTER VIEW dbo.vw_TestScores_PowerBI
AS
SELECT
    s.CustomerId,
    s.DataSplit,
    s.ModelScore,
    s.ScoreRank,
    CAST(100.0 * s.ScoreRank / COUNT_BIG(*) OVER () AS decimal(6,2)) AS RankPct,
    s.CapacityBand,
    CASE s.CapacityBand WHEN N'İlk %10' THEN 1 WHEN N'%10–20' THEN 2 WHEN N'%20–30' THEN 3 ELSE 4 END
        AS CapacityBandOrder,
    s.SegmentRuleScore,
    s.ModelVersion,
    p.Exited,
    p.GeographyLabel, p.GenderLabel, p.AgeLabel, p.AgeOrder, p.NumOfProductsLabel, p.IsActiveMemberLabel,
    p.SegmentCode
FROM dbo.CustomerScore AS s
JOIN dbo.vw_CustomerChurn_PowerBI AS p
    ON p.CustomerId = s.CustomerId;
GO

-- 5. Kontrol. Beklenen: 1501 / 1501 / 306 / kapasite dilimleri 150 · 150 · 150 · 1051.
--    306, notebook Bölüm 1'deki test setinin ayrılan sayısıdır.
SELECT
    COUNT_BIG(*)               AS scored_customers,
    COUNT(DISTINCT CustomerId) AS unique_customers,
    SUM(Exited)                AS exited_in_test
FROM dbo.vw_TestScores_PowerBI;

SELECT CapacityBandOrder, CapacityBand, COUNT_BIG(*) AS customers, SUM(Exited) AS exited
FROM dbo.vw_TestScores_PowerBI
GROUP BY CapacityBandOrder, CapacityBand
ORDER BY CapacityBandOrder;
-- Beklenen ayrılan: İlk %10 → 119, %10–20 → 68 (ilk %20 toplamı 187), %20–30 → 39 (ilk %30 toplamı 226).

-- 6. Örnek: en riskli 5 müşteri. Türkçe karakterler düzgün görünmeli.
SELECT TOP (5) CustomerId, ModelScore, ScoreRank, CapacityBand, SegmentRuleScore, Exited, AgeLabel, GeographyLabel
FROM dbo.vw_TestScores_PowerBI
ORDER BY ScoreRank;

-- Hata kodları: 50301 satır sayısı, 50302 boş/çevrilemeyen değer, 50303 tekrar eden müşteri,
-- 50304 EDA tablosunda olmayan müşteri, 50305 sıra aralığı, 50306 skor aralığı veya bölüm.
