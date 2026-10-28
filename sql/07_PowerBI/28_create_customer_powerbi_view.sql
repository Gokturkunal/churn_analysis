-- 28 Ekim yorum sınırı: CREATE OR ALTER view tanımını günceller; SELECT okumaları kaynak
-- müşterileri değiştirmez. Önceden toplu özetlerle de bazı filtreler uygulanabilir; müşteri seviyesi
-- kaynak burada ayrıntılı filtre kesişimlerini yeniden hesaplayabilmek için seçilmiştir.

-- Amaç: Power BI'ın etkileşimli sayfalarının (1. genel görünüm, 2. segmentler) okuyacağı müşteri seviyesinde view
--       (dbo.vw_CustomerChurn_PowerBI). Her satır bir müşteridir (10.000 satır).
-- Neden: SQL 26–27'deki view'lar önceden toplanmış özetlerdir; filtre seçilince yeniden hesaplanamazlar.
--        Power BI müşteri satırlarını okursa oran, güven aralığı ve etiketler DAX ölçüleriyle
--        seçili filtreye göre yeniden hesaplanır (ör. Kadın seçilince genel oran %25,07 olur).
-- Kaynak: dbo.CustomerChurn_EDA (SQL 16), dbo.CustomerSegment ve dbo.SegmentDefinition (SQL 25).
-- Grup kuralları SQL 27 (dbo.vw_ChurnByGroup) ile birebir aynıdır: aralıklar sol kapalı, sağ açık;
--   yaş 10 yıllık + 70+; kredi puanı 50'lik + 850 ayrı; bakiye sıfır ayrı + 50K'lık; gelir 20K'lık.
--   Kural iki dosyada yazılı olduğu için Bölüm 3'teki kontrol bu view'ı gruplayıp vw_ChurnByGroup ile
--   karşılaştırır; biri değişip diğeri değişmezse kontrol satır döndürür.
-- Her grup sütununun yanında bir sıralama sütunu (…Order) vardır. Power BI metni alfabetik sıralar
--   ("70+" "18–29"dan önce gelebilir); Power BI'da "Sütuna göre sırala" ile bu sütunlar kullanılır.
-- Segment kuralı Python'dadır (eda.segmentasyon_kur); bu view yalnızca SQL 25'teki atamayı okur.
-- Sütun adları diğer tablolar gibi İngilizcedir; değerler Türkçedir (paydaşa gidecek metin).
-- View yalnızca okur; tabloları değiştirmez. Tekrar çalıştırmak güvenlidir (CREATE OR ALTER).
-- Bulgular ilişkiseldir; nedensellik veya teklif etkisi göstermez.
USE [ChurnAnalysis];
GO

-- 1. View tanımı
CREATE OR ALTER VIEW dbo.vw_CustomerChurn_PowerBI
AS
SELECT
    e.CustomerId,

    -- Hedef: ölçüler SUM(Exited) ile ayrılan sayısını bulur.
    CAST(e.Exited AS int) AS Exited,
    CASE e.Exited WHEN 1 THEN N'Ayrıldı' ELSE N'Kaldı' END AS ExitedLabel,

    -- Ham değerler: ipucu (tooltip) ve kontrol için. Görsellerde grup sütunları kullanılır.
    e.CreditScore,
    e.Age,
    e.Tenure,
    e.Balance,
    e.NumOfProducts,
    e.EstimatedSalary,

    -- Kategorik değişkenler (SQL 27 ile aynı etiket ve sıra)
    CASE e.Geography WHEN N'France' THEN N'Fransa' WHEN N'Germany' THEN N'Almanya' WHEN N'Spain' THEN N'İspanya' END
        AS GeographyLabel,
    CASE e.Geography WHEN N'France' THEN 1 WHEN N'Germany' THEN 2 WHEN N'Spain' THEN 3 END
        AS GeographyOrder,

    CASE e.Gender WHEN N'Female' THEN N'Kadın' WHEN N'Male' THEN N'Erkek' END AS GenderLabel,
    CASE e.Gender WHEN N'Female' THEN 1 WHEN N'Male' THEN 2 END                AS GenderOrder,

    CASE e.HasCrCard WHEN 0 THEN N'Kartı yok' WHEN 1 THEN N'Kartı var' END AS HasCrCardLabel,
    CASE e.HasCrCard WHEN 0 THEN 1 WHEN 1 THEN 2 END                       AS HasCrCardOrder,

    CASE e.IsActiveMember WHEN 0 THEN N'Aktif değil' WHEN 1 THEN N'Aktif' END AS IsActiveMemberLabel,
    CASE e.IsActiveMember WHEN 0 THEN 1 WHEN 1 THEN 2 END                     AS IsActiveMemberOrder,

    CONCAT(e.NumOfProducts, N' ürün') AS NumOfProductsLabel,
    e.NumOfProducts                   AS NumOfProductsOrder,

    CAST(e.Tenure AS nvarchar(3)) AS TenureLabel,
    e.Tenure + 1                  AS TenureOrder,

    CASE WHEN e.Balance = 0 THEN N'Sıfır' ELSE N'Pozitif' END AS BalanceStatusLabel,
    CASE WHEN e.Balance = 0 THEN 1 ELSE 2 END                 AS BalanceStatusOrder,

    -- Aralıklı değişkenler (SQL 27 ve notebook Bölüm 2b ile aynı sınırlar)
    CASE WHEN e.Age < 30 THEN N'18–29' WHEN e.Age < 40 THEN N'30–39' WHEN e.Age < 50 THEN N'40–49'
         WHEN e.Age < 60 THEN N'50–59' WHEN e.Age < 70 THEN N'60–69' ELSE N'70+' END
        AS AgeLabel,
    CASE WHEN e.Age < 30 THEN 1 WHEN e.Age < 40 THEN 2 WHEN e.Age < 50 THEN 3
         WHEN e.Age < 60 THEN 4 WHEN e.Age < 70 THEN 5 ELSE 6 END
        AS AgeOrder,

    -- Kredi puanı: 50'lik aralıklar; 850 tavanı ayrı grup
    CASE WHEN e.CreditScore = 850 THEN N'850'
         ELSE CONCAT(350 + ((e.CreditScore - 350) / 50) * 50, N'–', 350 + ((e.CreditScore - 350) / 50) * 50 + 49) END
        AS CreditScoreLabel,
    CASE WHEN e.CreditScore = 850 THEN 11 ELSE (e.CreditScore - 350) / 50 + 1 END
        AS CreditScoreOrder,

    -- Bakiye: sıfır ayrı grup, pozitifler 50K'lık aralıklar
    CASE WHEN e.Balance = 0 THEN N'Sıfır' WHEN e.Balance < 50000 THEN N'<50K' WHEN e.Balance < 100000 THEN N'50–100K'
         WHEN e.Balance < 150000 THEN N'100–150K' WHEN e.Balance < 200000 THEN N'150–200K' ELSE N'200K+' END
        AS BalanceLabel,
    CASE WHEN e.Balance = 0 THEN 1 WHEN e.Balance < 50000 THEN 2 WHEN e.Balance < 100000 THEN 3
         WHEN e.Balance < 150000 THEN 4 WHEN e.Balance < 200000 THEN 5 ELSE 6 END
        AS BalanceOrder,

    -- Tahmini gelir: 20K'lık aralıklar (en büyük değer 199.992,48)
    CONCAT(CAST(FLOOR(e.EstimatedSalary / 20000) AS int) * 20, N'–',
           (CAST(FLOOR(e.EstimatedSalary / 20000) AS int) + 1) * 20, N'K')
        AS EstimatedSalaryLabel,
    CAST(FLOOR(e.EstimatedSalary / 20000) AS int) + 1
        AS EstimatedSalaryOrder,

    -- Segment (SQL 25). LEFT JOIN: ataması olmayan müşteri satırı kaybolmaz, NULL görünür (Bölüm 2 kontrolü yakalar).
    s.SegmentCode,
    d.SegmentRank,
    d.SegmentDescription
FROM dbo.CustomerChurn_EDA AS e
LEFT JOIN dbo.CustomerSegment   AS s ON s.CustomerId  = e.CustomerId
LEFT JOIN dbo.SegmentDefinition AS d ON d.SegmentCode = s.SegmentCode;
GO

-- 2. Temel kontrol. Beklenen: 10000 / 10000 / 2037 / 0 / 0.
SELECT
    COUNT_BIG(*)               AS row_count,
    COUNT(DISTINCT CustomerId) AS unique_customers,
    SUM(Exited)                AS exited_count,
    -- Tanımsız yeni bir değer gelirse etiket NULL olur.
    SUM(CASE WHEN GeographyLabel IS NULL OR GenderLabel IS NULL OR HasCrCardLabel IS NULL
                  OR IsActiveMemberLabel IS NULL THEN 1 ELSE 0 END) AS null_label_rows,
    SUM(CASE WHEN SegmentCode IS NULL OR SegmentRank IS NULL THEN 1 ELSE 0 END) AS missing_segment_rows
FROM dbo.vw_CustomerChurn_PowerBI;

-- 3. Kural tutarlılığı: bu view gruplanınca SQL 27'deki 59 grubun sayıları birebir çıkmalı.
--    Beklenen: 0 satır. Satır dönerse iki dosyadaki grup kuralları birbirinden ayrılmıştır.
WITH Grouped AS
(
    SELECT
        g.VariableName,
        g.GroupOrder,
        g.GroupLabel,
        COUNT_BIG(*)  AS CustomerCount,
        SUM(p.Exited) AS ExitedCount
    FROM dbo.vw_CustomerChurn_PowerBI AS p
    CROSS APPLY (VALUES
        (N'Geography',       p.GeographyOrder,       p.GeographyLabel),
        (N'Gender',          p.GenderOrder,          p.GenderLabel),
        (N'HasCrCard',       p.HasCrCardOrder,       p.HasCrCardLabel),
        (N'IsActiveMember',  p.IsActiveMemberOrder,  p.IsActiveMemberLabel),
        (N'NumOfProducts',   p.NumOfProductsOrder,   p.NumOfProductsLabel),
        (N'Tenure',          p.TenureOrder,          p.TenureLabel),
        (N'BalanceStatus',   p.BalanceStatusOrder,   p.BalanceStatusLabel),
        (N'Age',             p.AgeOrder,             p.AgeLabel),
        (N'CreditScore',     p.CreditScoreOrder,     p.CreditScoreLabel),
        (N'Balance',         p.BalanceOrder,         p.BalanceLabel),
        (N'EstimatedSalary', p.EstimatedSalaryOrder, p.EstimatedSalaryLabel)
    ) AS g (VariableName, GroupOrder, GroupLabel)
    GROUP BY g.VariableName, g.GroupOrder, g.GroupLabel
)
SELECT
    COALESCE(c.VariableName, v.VariableName) AS VariableName,
    COALESCE(c.GroupLabel, v.GroupLabel)     AS GroupLabel,
    c.GroupOrder    AS powerbi_order,     v.GroupOrder    AS sql27_order,
    c.CustomerCount AS powerbi_customers, v.CustomerCount AS sql27_customers,
    c.ExitedCount   AS powerbi_exited,    v.ExitedCount   AS sql27_exited
FROM Grouped AS c
FULL OUTER JOIN dbo.vw_ChurnByGroup AS v
    ON v.VariableName = c.VariableName
   AND v.GroupLabel = c.GroupLabel
WHERE c.VariableName IS NULL
   OR v.VariableName IS NULL
   OR c.GroupOrder <> v.GroupOrder
   OR c.CustomerCount <> v.CustomerCount
   OR c.ExitedCount <> v.ExitedCount;

-- 4. Segment tutarlılığı: bu view'dan sayılan segmentler SQL 26 ile aynı mı? Beklenen: 0 satır.
WITH Seg AS
(
    SELECT SegmentCode, COUNT_BIG(*) AS CustomerCount, SUM(Exited) AS ExitedCount
    FROM dbo.vw_CustomerChurn_PowerBI
    GROUP BY SegmentCode
)
SELECT
    COALESCE(c.SegmentCode, v.SegmentCode) AS SegmentCode,
    c.CustomerCount AS powerbi_customers, v.CustomerCount AS sql26_customers,
    c.ExitedCount   AS powerbi_exited,    v.ExitedCount   AS sql26_exited
FROM Seg AS c
FULL OUTER JOIN dbo.vw_SegmentSummary AS v
    ON v.SegmentCode = c.SegmentCode
WHERE c.SegmentCode IS NULL
   OR v.SegmentCode IS NULL
   OR c.CustomerCount <> v.CustomerCount
   OR c.ExitedCount <> v.ExitedCount;

-- 5. Sıralama sütunu kontrolü: Power BI'da "Sütuna göre sırala" yalnızca her etiketin tek bir sırası
--    ve her sıranın tek bir etiketi varsa çalışır. Beklenen: 0 satır.
WITH Pairs AS
(
    SELECT DISTINCT g.VariableName, g.GroupLabel, g.GroupOrder
    FROM dbo.vw_CustomerChurn_PowerBI AS p
    CROSS APPLY (VALUES
        (N'Geography',       p.GeographyLabel,       p.GeographyOrder),
        (N'Gender',          p.GenderLabel,          p.GenderOrder),
        (N'HasCrCard',       p.HasCrCardLabel,       p.HasCrCardOrder),
        (N'IsActiveMember',  p.IsActiveMemberLabel,  p.IsActiveMemberOrder),
        (N'NumOfProducts',   p.NumOfProductsLabel,   p.NumOfProductsOrder),
        (N'Tenure',          p.TenureLabel,          p.TenureOrder),
        (N'BalanceStatus',   p.BalanceStatusLabel,   p.BalanceStatusOrder),
        (N'Age',             p.AgeLabel,             p.AgeOrder),
        (N'CreditScore',     p.CreditScoreLabel,     p.CreditScoreOrder),
        (N'Balance',         p.BalanceLabel,         p.BalanceOrder),
        (N'EstimatedSalary', p.EstimatedSalaryLabel, p.EstimatedSalaryOrder),
        (N'Segment',         p.SegmentCode,          p.SegmentRank)
    ) AS g (VariableName, GroupLabel, GroupOrder)
)
SELECT VariableName, N'Etiketin birden fazla sırası var' AS problem, GroupLabel AS value
FROM Pairs GROUP BY VariableName, GroupLabel HAVING COUNT(*) > 1
UNION ALL
SELECT VariableName, N'Sıranın birden fazla etiketi var', CAST(GroupOrder AS nvarchar(10))
FROM Pairs GROUP BY VariableName, GroupOrder HAVING COUNT(*) > 1;

-- 6. Power BI'ın göreceği satırlardan örnek. Türkçe karakterler (ü, ş, ğ, İ, –) düzgün görünmeli.
SELECT TOP (5) *
FROM dbo.vw_CustomerChurn_PowerBI
ORDER BY CustomerId;

-- Not: Power BI'da bu view'ın adı "Müşteriler" yapılacak; …Order sütunları gizlenip ilgili etiket
--      sütunlarının "Sütuna göre sırala" ayarında kullanılacak.

