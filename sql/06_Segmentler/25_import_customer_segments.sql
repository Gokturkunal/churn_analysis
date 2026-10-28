-- Amaç: Python'da kurulan EDA segmentlerini (notebooks/01_eda.ipynb Bölüm 5) SQL'e yüklemek.
-- Power BI segment sayfası bu tablolardan ve SQL 26'daki view'dan beslenir.
-- Kaynak: reports/eda/05_musteri_segment.csv (CustomerId, Segment, Tanım; UTF-8, CRLF;
--         10.000 müşteri, 24 segment). Kaynak dosya değiştirilmez.
-- Segment kuralı Python'dadır (eda.segmentasyon_kur). SQL kuralı yeniden yazmaz, yalnızca atamayı saklar;
-- böylece kural tek yerde kalır. Ayrılma sayıları burada yüklenmez, SQL 26 bunları EDA tablosundan hesaplar.
-- Tekrar çalıştırmak güvenlidir: türetilmiş veri olduğu için tablolar her çalıştırmada aynı dosyadan yenilenir.
-- Kontrollerden biri başarısız olursa hiçbir değişiklik kalıcı olmaz (ROLLBACK).
-- SQL Server bu yerel dosyayı okuyabilmelidir (SQL 04 ile aynı proje klasörü). Proje başka bir yere
-- taşınırsa BULK INSERT satırındaki yol değiştirilmelidir.
USE [ChurnAnalysis];
GO

-- 1. Tablolar yoksa oluşturulur; varsa yapılarına dokunulmaz.
--    Adlar diğer tablolar gibi İngilizcedir; Türkçe görünen adlar Power BI'da verilir.
IF OBJECT_ID(N'dbo.SegmentDefinition', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.SegmentDefinition
    (
        SegmentCode        nvarchar(10)  NOT NULL CONSTRAINT PK_SegmentDefinition PRIMARY KEY,
        SegmentRank        int           NOT NULL CONSTRAINT UQ_SegmentDefinition_Rank UNIQUE,
        SegmentDescription nvarchar(200) NOT NULL
    );
END;
GO

IF OBJECT_ID(N'dbo.CustomerSegment', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.CustomerSegment
    (
        CustomerId  bigint       NOT NULL CONSTRAINT PK_CustomerSegment PRIMARY KEY,
        SegmentCode nvarchar(10) NOT NULL
            CONSTRAINT FK_CustomerSegment_SegmentDefinition
            REFERENCES dbo.SegmentDefinition (SegmentCode)
    );
END;
GO

-- Dosya önce metin olarak geçici tabloya alınır; tür ve eşleşme kontrolleri buradan yapılır.
-- # ile başlayan tablo geçicidir; oturum kapanınca silinir. Ayrı bir grupta (GO) oluşturulur ki
-- aşağıdaki BULK INSERT derlenirken tablo hazır olsun.
DROP TABLE IF EXISTS #SegmentStage;
CREATE TABLE #SegmentStage
(
    CustomerId         nvarchar(50)  NULL,
    SegmentCode        nvarchar(10)  NULL,
    SegmentDescription nvarchar(200) NULL
);
GO

SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    BULK INSERT #SegmentStage
    FROM 'C:\Users\goktu\Churn_analysis\reports\eda\05_musteri_segment.csv'
    WITH
    (
        FORMAT = 'CSV',
        CODEPAGE = '65001',   -- UTF-8 karakter kodlaması (Tanım sütunundaki Türkçe karakterler için)
        FIRSTROW = 2,         -- İlk satır sütun başlıklarıdır.
        FIELDTERMINATOR = ',',
        ROWTERMINATOR = '\n', -- Windows'ta CRLF olarak yorumlanır.
        KEEPNULLS
    );

    -- 2. Kontroller: herhangi biri başarısızsa yükleme geri alınır.
    IF (SELECT COUNT_BIG(*) FROM #SegmentStage) <> 10000
    BEGIN
        THROW 50101, N'Dosyada 10.000 satır bekleniyordu. Yükleme geri alındı.', 1;
    END;

    IF EXISTS (
        SELECT 1
        FROM #SegmentStage
        WHERE TRY_CONVERT(bigint, CustomerId) IS NULL
           OR NULLIF(TRIM(SegmentCode), N'') IS NULL
           OR NULLIF(TRIM(SegmentDescription), N'') IS NULL
    )
    BEGIN
        THROW 50102, N'Boş veya sayıya çevrilemeyen değer var. Yükleme geri alındı.', 1;
    END;

    IF (SELECT COUNT(DISTINCT TRY_CONVERT(bigint, CustomerId)) FROM #SegmentStage) <> 10000
    BEGIN
        THROW 50103, N'CustomerId tekrar ediyor. Yükleme geri alındı.', 1;
    END;

    -- Dosyadaki her müşteri EDA tablosunda olmalı; EDA tablosundaki her müşterinin de segmenti olmalı.
    IF EXISTS (
        SELECT 1
        FROM #SegmentStage AS s
        FULL OUTER JOIN dbo.CustomerChurn_EDA AS e
            ON TRY_CONVERT(bigint, s.CustomerId) = e.CustomerId
        WHERE s.CustomerId IS NULL OR e.CustomerId IS NULL
    )
    BEGIN
        THROW 50104, N'Segment dosyası ile EDA tablosunun müşterileri eşleşmiyor. Yükleme geri alındı.', 1;
    END;

    IF (SELECT COUNT(DISTINCT TRIM(SegmentCode)) FROM #SegmentStage) <> 24
    BEGIN
        THROW 50105, N'24 segment bekleniyordu. Yükleme geri alındı.', 1;
    END;

    -- Her segment kodunun tek bir tanımı olmalı.
    IF EXISTS (
        SELECT TRIM(SegmentCode)
        FROM #SegmentStage
        GROUP BY TRIM(SegmentCode)
        HAVING COUNT(DISTINCT TRIM(SegmentDescription)) > 1
    )
    BEGIN
        THROW 50106, N'Bir segment kodunda birden fazla tanım var. Yükleme geri alındı.', 1;
    END;

    -- 3. Tablolar yenilenir: önce müşteri ataması (yabancı anahtar nedeniyle), sonra tanımlar.
    DELETE FROM dbo.CustomerSegment;
    DELETE FROM dbo.SegmentDefinition;

    -- Segment sırası koddan gelir: S01 en riskli segmenttir (Python'da ayrılma oranına göre sıralandı).
    INSERT INTO dbo.SegmentDefinition (SegmentCode, SegmentRank, SegmentDescription)
    SELECT
        TRIM(SegmentCode),
        CAST(SUBSTRING(TRIM(SegmentCode), 2, 10) AS int),
        MIN(TRIM(SegmentDescription))
    FROM #SegmentStage
    GROUP BY TRIM(SegmentCode);

    INSERT INTO dbo.CustomerSegment (CustomerId, SegmentCode)
    SELECT CAST(CustomerId AS bigint), TRIM(SegmentCode)
    FROM #SegmentStage;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

-- 4. Sonuç. Beklenen: 10000 / 10000 / 24 / 24.
SELECT
    (SELECT COUNT_BIG(*) FROM dbo.CustomerSegment)                AS customer_segment_rows,
    (SELECT COUNT(DISTINCT CustomerId) FROM dbo.CustomerSegment)  AS unique_customers,
    (SELECT COUNT_BIG(*) FROM dbo.SegmentDefinition)              AS segment_definitions,
    (SELECT COUNT(DISTINCT SegmentCode) FROM dbo.CustomerSegment) AS used_segments;

-- 5. Tanımların okunduğunu görmek için: Türkçe karakterler (ü, ş, ğ, ·, –) düzgün görünmeli.
--    Beklenen ilk satırlar: S01 · 3+ ürün; S02 · Yaş 50–59 · 1 ürün · Diğer · Aktif değil.
SELECT SegmentRank, SegmentCode, SegmentDescription
FROM dbo.SegmentDefinition
ORDER BY SegmentRank;

-- Hata kodları: 50101 satır sayısı, 50102 boş/çevrilemeyen değer, 50103 tekrar eden müşteri,
-- 50104 EDA tablosuyla eşleşmeme, 50105 segment sayısı, 50106 bir koda birden fazla tanım.
-- Hata 4861 / "Cannot bulk load": SQL Server hizmeti dosyayı okuyamıyor; yol ve klasör izni kontrol edilir.
