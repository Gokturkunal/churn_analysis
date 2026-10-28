-- 28 Ekim yorum sınırı: Fark yok etiketi eşitlik kanıtı değildir; aralık genel oranı içeriyor demektir.
-- Genel oran aynı müşterileri içerir; bu bağımsız iki grup fark testi değildir. Güven etiketi
-- n/aralık genişliğine dayanan sunum kuralıdır; kesinlik, nedensellik veya eşzamanlı aralık garantisi vermez.

-- Amaç: Power BI 1. sayfasının (genel görünüm) okuyacağı iki view:
--   dbo.vw_ChurnByGroup      → her değişken ve grup için müşteri sayısı, ayrılan, oran, %95 güven aralığı,
--                              lift ve paydaşın okuyabileceği etiketler (notebook Bölüm 2–3'teki 59 grup).
--   dbo.vw_VariableStrength  → her değişkenin ayrılmayla ilişkisinin gücü ve sade etiketi (notebook Bölüm 2c).
-- Kaynak: dbo.CustomerChurn_EDA (SQL 16) ve bu dosyada yüklenen dbo.VariableStrength.
-- Grup sayıları SQL'de yeniden hesaplanır; Bölüm 3'teki kontrol 59 grubu Python'un Bölüm 3 tablosuyla
-- (reports/eda/03_guven_tablosu.csv) karşılaştırır: Python, SQL ve Power BI aynı sayıları göstermeli.
-- Değişken gücü (Cramér's V / AUC) Python'da hesaplanır (reports/eda/02c_etki_buyuklugu.csv); SQL bu
-- istatistikleri yeniden hesaplamaz, yalnızca saklar ve "Ortalamaya göre" kuralında kullanır.
-- Kurallar notebook Bölüm 3 ile aynıdır:
--   VersusAverage (Ortalamaya göre): değişken gücü < 0,10 → 'Yorumlanmaz (zayıf değişken)'; aksi hâlde
--     %95 Wilson aralığının tamamı genel oranın üstünde → 'Yüksek risk', altında → 'Düşük risk', içeriyor → 'Fark yok'.
--   Confidence (Güven): n < 100 → 'Düşük (n < 100)'; aralık genişliği ≤ 10 puan → 'Yüksek'; daha geniş → 'Orta'.
--   StrengthLabel (İlişki gücü): ≥ 0,30 → 'Güçlü'; ≥ 0,10 → 'Küçük ama belirgin'; aksi hâlde 'İhmal edilebilir'.
-- Grup adları Türkçedir (paydaşa gidecek metin); değişken anahtarları diğer tablolar gibi İngilizcedir.
-- Aralık sınırları notebook Bölüm 2b ile aynıdır (sol kapalı, sağ açık). Tekrar çalıştırmak güvenlidir.
-- Bulgular ilişkiseldir; nedensellik veya teklif etkisi göstermez (Power BI sayfasında da yazacak).
USE [ChurnAnalysis];
GO

-- 1. Değişken gücü tablosu: yoksa oluşturulur, her çalıştırmada Python değerleriyle yenilenir.
IF OBJECT_ID(N'dbo.VariableStrength', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.VariableStrength
    (
        VariableName  nvarchar(50)  NOT NULL CONSTRAINT PK_VariableStrength PRIMARY KEY,
        VariableLabel nvarchar(100) NOT NULL,
        VariableOrder int           NOT NULL,
        VariableType  nvarchar(30)  NOT NULL,
        Measure       nvarchar(20)  NOT NULL,
        MeasureValue  decimal(6,4)  NOT NULL,
        Strength      decimal(6,4)  NOT NULL
    );
END;
GO

SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    DELETE FROM dbo.VariableStrength;

    -- Kaynak: reports/eda/02c_etki_buyuklugu.csv (2026-10-19). Güç: V olduğu gibi; AUC için 2·|AUC − 0,5|.
    -- Python'da yeniden hesaplanırsa bu değerler de güncellenir.
    INSERT INTO dbo.VariableStrength
        (VariableName, VariableLabel, VariableOrder, VariableType, Measure, MeasureValue, Strength)
    VALUES
        (N'Geography',       N'Ülke',                    1,  N'Kategorik/kesikli', N'Cramér''s V', 0.1736, 0.1736),
        (N'Gender',          N'Cinsiyet',                2,  N'Kategorik/kesikli', N'Cramér''s V', 0.1065, 0.1065),
        (N'HasCrCard',       N'Kredi kartı',             3,  N'Kategorik/kesikli', N'Cramér''s V', 0.0071, 0.0071),
        (N'IsActiveMember',  N'Aktiflik',                4,  N'Kategorik/kesikli', N'Cramér''s V', 0.1561, 0.1561),
        (N'NumOfProducts',   N'Ürün sayısı',             5,  N'Kategorik/kesikli', N'Cramér''s V', 0.3878, 0.3878),
        (N'Tenure',          N'Banka ile ilişki süresi', 6,  N'Kategorik/kesikli', N'Cramér''s V', 0.0373, 0.0373),
        (N'BalanceStatus',   N'Bakiye durumu',           7,  N'Kategorik/kesikli', N'Cramér''s V', 0.1224, 0.1224),
        (N'Age',             N'Yaş',                     8,  N'Sürekli (aralık)',  N'AUC',         0.7321, 0.4641),
        (N'CreditScore',     N'Kredi puanı',             9,  N'Sürekli (aralık)',  N'AUC',         0.4833, 0.0334),
        (N'Balance',         N'Bakiye',                  10, N'Sürekli (aralık)',  N'AUC',         0.5777, 0.1555),
        (N'EstimatedSalary', N'Tahmini gelir',           11, N'Sürekli (aralık)',  N'AUC',         0.5087, 0.0173);

    IF (SELECT COUNT_BIG(*) FROM dbo.VariableStrength) <> 11
    BEGIN
        THROW 50201, N'11 değişken bekleniyordu. Yükleme geri alındı.', 1;
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

-- 2a. Değişken gücü view'ı (Power BI: "Hangi özellikler ayrılmayla ilişkili?" görseli)
CREATE OR ALTER VIEW dbo.vw_VariableStrength
AS
SELECT
    VariableName,
    VariableLabel,
    VariableType,
    Measure,
    MeasureValue,
    Strength,
    RANK() OVER (ORDER BY Strength DESC) AS StrengthRank,
    CASE
        WHEN Strength >= 0.30 THEN N'Güçlü'
        WHEN Strength >= 0.10 THEN N'Küçük ama belirgin'
        ELSE N'İhmal edilebilir'
    END AS StrengthLabel
FROM dbo.VariableStrength;
GO

-- 2b. Gruplara göre ayrılma view'ı
CREATE OR ALTER VIEW dbo.vw_ChurnByGroup
AS
WITH Grouped AS
(
    -- Her müşteri satırı 11 satıra açılır (her değişkende bir grup); sonra gruplanır.
    -- Tanımlı olmayan yeni bir değer gelirse grup adı NULL olur ve tabloda ayrı satır olarak görünür.
    SELECT
        g.VariableName,
        g.GroupOrder,
        g.GroupLabel,
        COUNT_BIG(*)               AS CustomerCount,
        SUM(CAST(e.Exited AS int)) AS ExitedCount
    FROM dbo.CustomerChurn_EDA AS e
    CROSS APPLY (VALUES
        (N'Geography',
            CASE e.Geography WHEN N'France' THEN 1 WHEN N'Germany' THEN 2 WHEN N'Spain' THEN 3 END,
            CASE e.Geography WHEN N'France' THEN N'Fransa' WHEN N'Germany' THEN N'Almanya' WHEN N'Spain' THEN N'İspanya' END),
        (N'Gender',
            CASE e.Gender WHEN N'Female' THEN 1 WHEN N'Male' THEN 2 END,
            CASE e.Gender WHEN N'Female' THEN N'Kadın' WHEN N'Male' THEN N'Erkek' END),
        (N'HasCrCard',
            CASE e.HasCrCard WHEN 0 THEN 1 WHEN 1 THEN 2 END,
            CASE e.HasCrCard WHEN 0 THEN N'Kartı yok' WHEN 1 THEN N'Kartı var' END),
        (N'IsActiveMember',
            CASE e.IsActiveMember WHEN 0 THEN 1 WHEN 1 THEN 2 END,
            CASE e.IsActiveMember WHEN 0 THEN N'Aktif değil' WHEN 1 THEN N'Aktif' END),
        (N'NumOfProducts',
            e.NumOfProducts,
            CONCAT(e.NumOfProducts, N' ürün')),
        (N'Tenure',
            e.Tenure + 1,
            CAST(e.Tenure AS nvarchar(3))),
        (N'BalanceStatus',
            CASE WHEN e.Balance = 0 THEN 1 ELSE 2 END,
            CASE WHEN e.Balance = 0 THEN N'Sıfır' ELSE N'Pozitif' END),
        (N'Age',
            CASE WHEN e.Age < 30 THEN 1 WHEN e.Age < 40 THEN 2 WHEN e.Age < 50 THEN 3
                 WHEN e.Age < 60 THEN 4 WHEN e.Age < 70 THEN 5 ELSE 6 END,
            CASE WHEN e.Age < 30 THEN N'18–29' WHEN e.Age < 40 THEN N'30–39' WHEN e.Age < 50 THEN N'40–49'
                 WHEN e.Age < 60 THEN N'50–59' WHEN e.Age < 70 THEN N'60–69' ELSE N'70+' END),
        -- Kredi puanı: 50'lik aralıklar; 850 tavanı ayrı grup (notebook Bölüm 2b)
        (N'CreditScore',
            CASE WHEN e.CreditScore = 850 THEN 11 ELSE (e.CreditScore - 350) / 50 + 1 END,
            CASE WHEN e.CreditScore = 850 THEN N'850'
                 ELSE CONCAT(350 + ((e.CreditScore - 350) / 50) * 50, N'–', 350 + ((e.CreditScore - 350) / 50) * 50 + 49) END),
        -- Bakiye: sıfır ayrı grup, pozitifler 50K'lık aralıklar
        (N'Balance',
            CASE WHEN e.Balance = 0 THEN 1 WHEN e.Balance < 50000 THEN 2 WHEN e.Balance < 100000 THEN 3
                 WHEN e.Balance < 150000 THEN 4 WHEN e.Balance < 200000 THEN 5 ELSE 6 END,
            CASE WHEN e.Balance = 0 THEN N'Sıfır' WHEN e.Balance < 50000 THEN N'<50K' WHEN e.Balance < 100000 THEN N'50–100K'
                 WHEN e.Balance < 150000 THEN N'100–150K' WHEN e.Balance < 200000 THEN N'150–200K' ELSE N'200K+' END),
        -- Tahmini gelir: 20K'lık aralıklar (en büyük değer 199.992,48)
        (N'EstimatedSalary',
            CAST(FLOOR(e.EstimatedSalary / 20000) AS int) + 1,
            CONCAT(CAST(FLOOR(e.EstimatedSalary / 20000) AS int) * 20, N'–',
                   (CAST(FLOOR(e.EstimatedSalary / 20000) AS int) + 1) * 20, N'K'))
    ) AS g (VariableName, GroupOrder, GroupLabel)
    GROUP BY g.VariableName, g.GroupOrder, g.GroupLabel
),
Totals AS
(
    SELECT
        COUNT_BIG(*)               AS TotalCustomers,
        SUM(CAST(Exited AS int))   AS TotalExited
    FROM dbo.CustomerChurn_EDA
)
SELECT
    v.VariableOrder,
    c.VariableName,
    v.VariableLabel,
    v.VariableType,
    c.GroupOrder,
    c.GroupLabel,
    c.CustomerCount,
    c.ExitedCount,
    CAST(100 * r.p AS decimal(6,2))            AS ChurnRatePct,
    CAST(100 * w.CiLower AS decimal(6,2))      AS CiLowerPct,
    CAST(100 * w.CiUpper AS decimal(6,2))      AS CiUpperPct,
    CAST(r.p / r.OverallRate AS decimal(6,2))  AS Lift,
    CAST(100 * r.OverallRate AS decimal(6,2))  AS OverallRatePct,
    CASE
        WHEN v.Strength < 0.10         THEN N'Yorumlanmaz (zayıf değişken)'
        WHEN w.CiLower > r.OverallRate THEN N'Yüksek risk'
        WHEN w.CiUpper < r.OverallRate THEN N'Düşük risk'
        ELSE N'Fark yok'
    END                                        AS VersusAverage,
    CASE
        WHEN c.CustomerCount < 100                 THEN N'Düşük (n < 100)'
        WHEN 100 * (w.CiUpper - w.CiLower) <= 10   THEN N'Yüksek'
        ELSE N'Orta'
    END                                        AS Confidence,
    v.Strength                                 AS VariableStrength,
    CASE
        WHEN v.Strength >= 0.30 THEN N'Güçlü'
        WHEN v.Strength >= 0.10 THEN N'Küçük ama belirgin'
        ELSE N'İhmal edilebilir'
    END                                        AS StrengthLabel,
    CAST(100.0 * c.CustomerCount / t.TotalCustomers AS decimal(6,2)) AS CustomerSharePct,
    CAST(100.0 * c.ExitedCount   / t.TotalExited    AS decimal(6,2)) AS ExitedSharePct
FROM Grouped AS c
JOIN dbo.VariableStrength AS v
    ON v.VariableName = c.VariableName
CROSS JOIN Totals AS t
CROSS APPLY (
    SELECT
        CAST(c.ExitedCount AS float) / c.CustomerCount  AS p,
        CAST(c.CustomerCount AS float)                  AS n,
        CAST(t.TotalExited AS float) / t.TotalCustomers AS OverallRate
) AS r
-- %95 Wilson aralığı (z = 1,96; SQL 26 ve notebook'taki eda.wilson_aralik ile aynı formül)
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

-- 3. Kontrol: 59 grubun sayıları, oranları ve etiketleri Python'un Bölüm 3 tablosuyla aynı mı?
--    Beklenen: 0 satır. Beklenen değerler reports/eda/03_guven_tablosu.csv dosyasından alındı (2026-10-19).
--    Oranda yuvarlama farkı için 0,01 puan tolerans vardır.
WITH Expected AS
(
    SELECT *
    FROM (VALUES
        (N'Ülke', N'Fransa', 5014, 810, 16.15, N'Düşük risk', N'Yüksek'),
        (N'Ülke', N'Almanya', 2509, 814, 32.44, N'Yüksek risk', N'Yüksek'),
        (N'Ülke', N'İspanya', 2477, 413, 16.67, N'Düşük risk', N'Yüksek'),
        (N'Cinsiyet', N'Kadın', 4543, 1139, 25.07, N'Yüksek risk', N'Yüksek'),
        (N'Cinsiyet', N'Erkek', 5457, 898, 16.46, N'Düşük risk', N'Yüksek'),
        (N'Kredi kartı', N'Kartı yok', 2945, 613, 20.81, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Kredi kartı', N'Kartı var', 7055, 1424, 20.18, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Aktiflik', N'Aktif değil', 4849, 1302, 26.85, N'Yüksek risk', N'Yüksek'),
        (N'Aktiflik', N'Aktif', 5151, 735, 14.27, N'Düşük risk', N'Yüksek'),
        (N'Ürün sayısı', N'1 ürün', 5084, 1409, 27.71, N'Yüksek risk', N'Yüksek'),
        (N'Ürün sayısı', N'2 ürün', 4590, 348, 7.58, N'Düşük risk', N'Yüksek'),
        (N'Ürün sayısı', N'3 ürün', 266, 220, 82.71, N'Yüksek risk', N'Yüksek'),
        (N'Ürün sayısı', N'4 ürün', 60, 60, 100.00, N'Yüksek risk', N'Düşük (n < 100)'),
        (N'Banka ile ilişki süresi', N'0', 413, 95, 23.00, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Banka ile ilişki süresi', N'1', 1035, 232, 22.42, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Banka ile ilişki süresi', N'2', 1048, 201, 19.18, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Banka ile ilişki süresi', N'3', 1009, 213, 21.11, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Banka ile ilişki süresi', N'4', 989, 203, 20.53, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Banka ile ilişki süresi', N'5', 1012, 209, 20.65, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Banka ile ilişki süresi', N'6', 967, 196, 20.27, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Banka ile ilişki süresi', N'7', 1028, 177, 17.22, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Banka ile ilişki süresi', N'8', 1025, 197, 19.22, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Banka ile ilişki süresi', N'9', 984, 213, 21.65, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Banka ile ilişki süresi', N'10', 490, 101, 20.61, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Bakiye durumu', N'Sıfır', 3617, 500, 13.82, N'Düşük risk', N'Yüksek'),
        (N'Bakiye durumu', N'Pozitif', 6383, 1537, 24.08, N'Yüksek risk', N'Yüksek'),
        (N'Yaş', N'18–29', 1641, 124, 7.56, N'Düşük risk', N'Yüksek'),
        (N'Yaş', N'30–39', 4346, 473, 10.88, N'Düşük risk', N'Yüksek'),
        (N'Yaş', N'40–49', 2618, 806, 30.79, N'Yüksek risk', N'Yüksek'),
        (N'Yaş', N'50–59', 869, 487, 56.04, N'Yüksek risk', N'Yüksek'),
        (N'Yaş', N'60–69', 375, 132, 35.20, N'Yüksek risk', N'Yüksek'),
        (N'Yaş', N'70+', 151, 15, 9.93, N'Düşük risk', N'Yüksek'),
        (N'Kredi puanı', N'350–399', 19, 19, 100.00, N'Yorumlanmaz (zayıf değişken)', N'Düşük (n < 100)'),
        (N'Kredi puanı', N'400–449', 166, 42, 25.30, N'Yorumlanmaz (zayıf değişken)', N'Orta'),
        (N'Kredi puanı', N'450–499', 447, 89, 19.91, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Kredi puanı', N'500–549', 958, 211, 22.03, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Kredi puanı', N'550–599', 1444, 299, 20.71, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Kredi puanı', N'600–649', 1866, 389, 20.85, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Kredi puanı', N'650–699', 1952, 364, 18.65, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Kredi puanı', N'700–749', 1525, 303, 19.87, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Kredi puanı', N'750–799', 968, 193, 19.94, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Kredi puanı', N'800–849', 422, 85, 20.14, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Kredi puanı', N'850', 233, 43, 18.45, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Bakiye', N'Sıfır', 3617, 500, 13.82, N'Düşük risk', N'Yüksek'),
        (N'Bakiye', N'<50K', 75, 26, 34.67, N'Yüksek risk', N'Düşük (n < 100)'),
        (N'Bakiye', N'50–100K', 1509, 300, 19.88, N'Fark yok', N'Yüksek'),
        (N'Bakiye', N'100–150K', 3830, 987, 25.77, N'Yüksek risk', N'Yüksek'),
        (N'Bakiye', N'150–200K', 935, 205, 21.93, N'Fark yok', N'Yüksek'),
        (N'Bakiye', N'200K+', 34, 19, 55.88, N'Yüksek risk', N'Düşük (n < 100)'),
        (N'Tahmini gelir', N'0–20K', 986, 198, 20.08, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Tahmini gelir', N'20–40K', 969, 196, 20.23, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Tahmini gelir', N'40–60K', 1006, 191, 18.99, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Tahmini gelir', N'60–80K', 1027, 212, 20.64, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Tahmini gelir', N'80–100K', 1002, 196, 19.56, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Tahmini gelir', N'100–120K', 1027, 211, 20.55, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Tahmini gelir', N'120–140K', 1007, 196, 19.46, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Tahmini gelir', N'140–160K', 982, 206, 20.98, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Tahmini gelir', N'160–180K', 1009, 225, 22.30, N'Yorumlanmaz (zayıf değişken)', N'Yüksek'),
        (N'Tahmini gelir', N'180–200K', 985, 206, 20.91, N'Yorumlanmaz (zayıf değişken)', N'Yüksek')
    ) AS x (VariableLabel, GroupLabel, CustomerCount, ExitedCount, ChurnRatePct, VersusAverage, Confidence)
)
SELECT
    COALESCE(x.VariableLabel, v.VariableLabel) AS VariableLabel,
    COALESCE(x.GroupLabel, v.GroupLabel)       AS GroupLabel,
    x.CustomerCount AS expected_customers,  v.CustomerCount AS sql_customers,
    x.ExitedCount   AS expected_exited,     v.ExitedCount   AS sql_exited,
    x.ChurnRatePct  AS expected_rate,       v.ChurnRatePct  AS sql_rate,
    x.VersusAverage AS expected_versus,     v.VersusAverage AS sql_versus,
    x.Confidence    AS expected_confidence, v.Confidence    AS sql_confidence
FROM Expected AS x
FULL OUTER JOIN dbo.vw_ChurnByGroup AS v
    ON v.VariableLabel = x.VariableLabel
   AND v.GroupLabel = x.GroupLabel
WHERE x.VariableLabel IS NULL
   OR v.VariableLabel IS NULL
   OR x.CustomerCount <> v.CustomerCount
   OR x.ExitedCount <> v.ExitedCount
   OR ABS(x.ChurnRatePct - v.ChurnRatePct) > 0.01
   OR x.VersusAverage <> v.VersusAverage
   OR x.Confidence <> v.Confidence;

-- 4. Her değişkenin grupları bütün müşterileri bir kez kapsamalı.
--    Beklenen: 11 satır; her satırda 10000 müşteri ve 2037 ayrılan.
SELECT
    VariableOrder,
    VariableLabel,
    COUNT(*)           AS group_count,
    SUM(CustomerCount) AS total_customers,
    SUM(ExitedCount)   AS total_exited
FROM dbo.vw_ChurnByGroup
GROUP BY VariableOrder, VariableLabel
ORDER BY VariableOrder;
-- Beklenen grup sayıları: Ülke 3 · Cinsiyet 2 · Kredi kartı 2 · Aktiflik 2 · Ürün sayısı 4 ·
-- Banka ile ilişki süresi 11 · Bakiye durumu 2 · Yaş 6 · Kredi puanı 11 · Bakiye 6 · Tahmini gelir 10 (toplam 59).

-- 5. Değişken gücü. Beklenen sıra: Yaş (Güçlü) · Ürün sayısı (Güçlü) · Ülke · Aktiflik · Bakiye ·
--    Bakiye durumu · Cinsiyet (Küçük ama belirgin) · Banka ile ilişki süresi · Kredi puanı · Tahmini gelir ·
--    Kredi kartı (İhmal edilebilir).
SELECT *
FROM dbo.vw_VariableStrength
ORDER BY StrengthRank;

-- 6. Power BI'ın göreceği tablo. Beklenen ilk satırlar: Ülke · Fransa · 5014 · 810 · 16.15 · Düşük risk · Yüksek;
--    Ülke · Almanya · 2509 · 814 · 32.44 · Yüksek risk · Yüksek.
SELECT *
FROM dbo.vw_ChurnByGroup
ORDER BY VariableOrder, GroupOrder;

-- Not: Bakiye durumu ve Bakiye aralıklarındaki "Sıfır" grubu aynı 3.617 müşteridir (notebook Bölüm 3).
-- Not: Power BI'da teknik sütunlar (CiLowerPct, CiUpperPct, Lift, VariableStrength) yalnızca ayrıntı ipucunda
--      (tooltip) gösterilir; görsellerde sade etiketler (VersusAverage, Confidence, StrengthLabel) kullanılır.
