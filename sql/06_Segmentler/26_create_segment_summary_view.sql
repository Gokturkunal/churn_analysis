-- 28 Ekim yorum sınırı: Segment oranları aynı veride keşfedilmiş/sıralanmış betimsel sonuçlardır.
-- Fark yok eşitlik; Yüksek güven kesinlik kanıtı değildir. CREATE OR ALTER view tanımını günceller;
-- view üzerinden SELECT okumaları kaynak tabloları değiştirmez. Bu adımda SQL çalıştırılmadı.

-- Amaç: Power BI segment sayfasının okuyacağı segment özet view'ı (dbo.vw_SegmentSummary).
-- Kaynak: dbo.SegmentDefinition ve dbo.CustomerSegment (SQL 25) + dbo.CustomerChurn_EDA (SQL 16).
-- Müşteri ve ayrılan sayıları SQL'de EDA tablosundan yeniden hesaplanır; Python'dan kopyalanmaz.
-- Bölüm 2'deki "Kontrol" sorgusu sonuçların Python segment tablosuyla
-- (reports/eda/05_segment_tablosu.csv) aynı olduğunu doğrular: Python, SQL ve Power BI aynı sayıları göstermeli.
-- Etiket kuralları notebook Bölüm 3 ile aynıdır:
--   VersusAverage (Ortalamaya göre): %95 Wilson aralığının tamamı genel oranın üstünde → 'Yüksek risk',
--     tamamı altında → 'Düşük risk', aralık genel oranı içeriyor → 'Fark yok'.
--   Confidence (Güven): n < 100 → 'Düşük (n < 100)'; aralık genişliği ≤ 10 puan → 'Yüksek'; daha geniş → 'Orta'.
-- Oranlar aynı veride kurulan segmentlerden gelir ve iyimserdir (notebook Bölüm 5 sınırı).
-- View yalnızca okur; tabloları değiştirmez. Tekrar çalıştırmak güvenlidir (CREATE OR ALTER).
USE [ChurnAnalysis];
GO

-- 1. View tanımı
CREATE OR ALTER VIEW dbo.vw_SegmentSummary
AS
WITH SegmentCounts AS
(
    SELECT
        d.SegmentRank,
        d.SegmentCode,
        d.SegmentDescription,
        COUNT_BIG(*)               AS CustomerCount,
        SUM(CAST(e.Exited AS int)) AS ExitedCount
    FROM dbo.SegmentDefinition AS d
    JOIN dbo.CustomerSegment   AS s ON s.SegmentCode = d.SegmentCode
    JOIN dbo.CustomerChurn_EDA AS e ON e.CustomerId  = s.CustomerId
    GROUP BY d.SegmentRank, d.SegmentCode, d.SegmentDescription
),
Totals AS
(
    SELECT
        SUM(CustomerCount) AS TotalCustomers,
        SUM(ExitedCount)   AS TotalExited
    FROM SegmentCounts
)
SELECT
    c.SegmentRank,
    c.SegmentCode,
    c.SegmentDescription,
    c.CustomerCount,
    c.ExitedCount,
    CAST(100 * r.p AS decimal(6,2))                        AS ChurnRatePct,
    CAST(100 * w.CiLower AS decimal(6,2))                  AS CiLowerPct,
    CAST(100 * w.CiUpper AS decimal(6,2))                  AS CiUpperPct,
    CAST(r.p / r.OverallRate AS decimal(6,2))              AS Lift,
    CASE
        WHEN w.CiLower > r.OverallRate THEN N'Yüksek risk'
        WHEN w.CiUpper < r.OverallRate THEN N'Düşük risk'
        ELSE N'Fark yok'
    END                                                    AS VersusAverage,
    CASE
        WHEN c.CustomerCount < 100                 THEN N'Düşük (n < 100)'
        WHEN 100 * (w.CiUpper - w.CiLower) <= 10   THEN N'Yüksek'
        ELSE N'Orta'
    END                                                    AS Confidence,
    CAST(100.0 * c.CustomerCount / t.TotalCustomers AS decimal(6,2)) AS CustomerSharePct,
    CAST(100.0 * c.ExitedCount   / t.TotalExited    AS decimal(6,2)) AS ExitedSharePct,
    -- Kümülatif paylar: en riskli segmentten başlayarak (yakalama eğrisinin noktaları)
    CAST(100.0 * SUM(c.CustomerCount) OVER (ORDER BY c.SegmentRank ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
         / t.TotalCustomers AS decimal(6,2))                         AS CumulativeCustomerPct,
    CAST(100.0 * SUM(c.ExitedCount) OVER (ORDER BY c.SegmentRank ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
         / t.TotalExited AS decimal(6,2))                            AS CumulativeExitedPct
FROM SegmentCounts AS c
CROSS JOIN Totals AS t
-- Oranlar float olarak bir kez hesaplanır; tam sayı bölmesi oluşmaz.
CROSS APPLY (
    SELECT
        CAST(c.ExitedCount AS float) / c.CustomerCount  AS p,
        CAST(c.CustomerCount AS float)                  AS n,
        CAST(t.TotalExited AS float) / t.TotalCustomers AS OverallRate
) AS r
-- %95 Wilson aralığı (z = 1,96; notebook'taki eda.wilson_aralik ile aynı formül)
CROSS APPLY (
    SELECT
        ((r.p + 1.96 * 1.96 / (2 * r.n))
            - 1.96 * SQRT(r.p * (1 - r.p) / r.n + 1.96 * 1.96 / (4 * r.n * r.n)))
            / (1 + 1.96 * 1.96 / r.n) AS CiLower,
        ((r.p + 1.96 * 1.96 / (2 * r.n))
            + 1.96 * SQRT(r.p * (1 - r.p) / r.n + 1.96 * 1.96 / (4 * r.n * r.n)))
            / (1 + 1.96 * 1.96 / r.n) AS CiUpper
) AS w;
GO

-- 2. Kontrol: SQL sonuçları Python segment tablosuyla aynı mı? Beklenen: 0 satır.
--    Beklenen değerler reports/eda/05_segment_tablosu.csv dosyasından alındı (2026-10-19).
--    Oranda yuvarlama farkı için 0,01 puan tolerans vardır. Etiketlerde Türkçe karakterler bozuk
--    görünüyorsa dosya SSMS'te UTF-8 olarak açılmamıştır.
WITH Expected AS
(
    SELECT *
    FROM (VALUES
        (N'S01', 326, 280, 85.89, N'Yüksek risk', N'Yüksek'),
        (N'S02', 150, 126, 84.00, N'Yüksek risk', N'Orta'),
        (N'S03', 184, 143, 77.72, N'Yüksek risk', N'Orta'),
        (N'S04', 247, 159, 64.37, N'Yüksek risk', N'Orta'),
        (N'S05', 157, 74, 47.13, N'Yüksek risk', N'Orta'),
        (N'S06', 212, 91, 42.92, N'Yüksek risk', N'Orta'),
        (N'S07', 532, 228, 42.86, N'Yüksek risk', N'Yüksek'),
        (N'S08', 203, 75, 36.95, N'Yüksek risk', N'Orta'),
        (N'S09', 347, 104, 29.97, N'Yüksek risk', N'Yüksek'),
        (N'S10', 263, 75, 28.52, N'Yüksek risk', N'Orta'),
        (N'S11', 473, 104, 21.99, N'Fark yok', N'Yüksek'),
        (N'S12', 138, 29, 21.01, N'Fark yok', N'Orta'),
        (N'S13', 342, 63, 18.42, N'Fark yok', N'Yüksek'),
        (N'S14', 148, 25, 16.89, N'Fark yok', N'Orta'),
        (N'S15', 143, 24, 16.78, N'Fark yok', N'Orta'),
        (N'S16', 1069, 149, 13.94, N'Düşük risk', N'Yüksek'),
        (N'S17', 404, 45, 11.14, N'Düşük risk', N'Yüksek'),
        (N'S18', 148, 13, 8.78, N'Düşük risk', N'Yüksek'),
        (N'S19', 299, 26, 8.70, N'Düşük risk', N'Yüksek'),
        (N'S20', 1095, 85, 7.76, N'Düşük risk', N'Yüksek'),
        (N'S21', 396, 29, 7.32, N'Düşük risk', N'Yüksek'),
        (N'S22', 1195, 48, 4.02, N'Düşük risk', N'Yüksek'),
        (N'S23', 342, 10, 2.92, N'Düşük risk', N'Yüksek'),
        (N'S24', 1187, 32, 2.70, N'Düşük risk', N'Yüksek')
    ) AS x (SegmentCode, CustomerCount, ExitedCount, ChurnRatePct, VersusAverage, Confidence)
)
SELECT
    COALESCE(x.SegmentCode, v.SegmentCode) AS SegmentCode,
    x.CustomerCount AS expected_customers, v.CustomerCount AS sql_customers,
    x.ExitedCount   AS expected_exited,    v.ExitedCount   AS sql_exited,
    x.ChurnRatePct  AS expected_rate,      v.ChurnRatePct  AS sql_rate,
    x.VersusAverage AS expected_versus,    v.VersusAverage AS sql_versus,
    x.Confidence    AS expected_confidence, v.Confidence   AS sql_confidence
FROM Expected AS x
FULL OUTER JOIN dbo.vw_SegmentSummary AS v
    ON v.SegmentCode = x.SegmentCode
WHERE x.SegmentCode IS NULL
   OR v.SegmentCode IS NULL
   OR x.CustomerCount <> v.CustomerCount
   OR x.ExitedCount <> v.ExitedCount
   OR ABS(x.ChurnRatePct - v.ChurnRatePct) > 0.01
   OR x.VersusAverage <> v.VersusAverage
   OR x.Confidence <> v.Confidence;

-- 3. Toplamlar. Beklenen: 24 segment / 10000 müşteri / 2037 ayrılan / son kümülatif paylar 100.00 / 100.00.
SELECT
    COUNT(*)                   AS segment_count,
    SUM(CustomerCount)         AS total_customers,
    SUM(ExitedCount)           AS total_exited,
    MAX(CumulativeCustomerPct) AS last_cumulative_customer_pct,
    MAX(CumulativeExitedPct)   AS last_cumulative_exited_pct
FROM dbo.vw_SegmentSummary;

-- 4. Power BI'ın göreceği tablo, risk sırasıyla. Beklenen ilk satır:
--    S01 · 3+ ürün · 326 · 280 · 85.89 · CI 81.69–89.25 · Yüksek risk · Yüksek · kümülatif 3.26 / 13.75.
SELECT *
FROM dbo.vw_SegmentSummary
ORDER BY SegmentRank;

-- Not: View'da ORDER BY olamaz; sıralama SegmentRank ile sorguda veya Power BI'da yapılır.
-- Not: Kümülatif paylar yakalama eğrisinin segment sınırlarındaki noktalarıdır; ara kapasiteler
--      (ör. tam %20) Power BI'da segment içinde rastgele seçim varsayımıyla hesaplanacaktır.
