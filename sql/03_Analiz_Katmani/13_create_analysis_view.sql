-- Amaç: ham tabloyu koruyup analiz için uygun türlerle ayrı görünüm oluşturmak.
-- View verinin fiziksel kopyası değildir; aşağıdaki SELECT tanımını saklar.
-- CustomerId eşleştirme için kalır; model özelliği değildir.
-- RowNumber ve Surname bu görünümde seçilmez, ham tablodan silinmez.
USE [ChurnAnalysis];
GO

-- View yoksa oluşturur; varsa aynı view'ın tanımını günceller.
CREATE OR ALTER VIEW dbo.vw_CustomerChurn_Analysis
AS
SELECT
    CAST(NULLIF(TRIM(CustomerId), N'') AS bigint) AS CustomerId,
    CAST(NULLIF(TRIM(CreditScore), N'') AS int) AS CreditScore,
    TRIM(Geography) AS Geography,
    TRIM(Gender) AS Gender,
    CAST(NULLIF(TRIM(Age), N'') AS int) AS Age,
    CAST(NULLIF(TRIM(Tenure), N'') AS int) AS Tenure,
    CAST(NULLIF(TRIM(Balance), N'') AS decimal(19,2)) AS Balance,
    CAST(NULLIF(TRIM(NumOfProducts), N'') AS int) AS NumOfProducts,
    CAST(NULLIF(TRIM(HasCrCard), N'') AS tinyint) AS HasCrCard,
    CAST(NULLIF(TRIM(IsActiveMember), N'') AS tinyint) AS IsActiveMember,
    CAST(NULLIF(TRIM(EstimatedSalary), N'') AS decimal(19,2)) AS EstimatedSalary,
    CAST(NULLIF(TRIM(Exited), N'') AS tinyint) AS Exited
FROM dbo.CustomerChurn_Raw;
GO

-- İlk kontrol: filtre koymadık; bütün müşteriler görünümde kalmalı.
SELECT
    (SELECT COUNT_BIG(*) FROM dbo.CustomerChurn_Raw) AS raw_rows,
    COUNT_BIG(*) AS analysis_rows,
    COUNT(DISTINCT CustomerId) AS unique_customer_ids
FROM dbo.vw_CustomerChurn_Analysis;

-- CAST: doğrulanan metni ilgili sayı türünde gösterir; hamı değiştirmez.
-- TRIM: görünümde baş/son normal boşlukları kaldırır.
-- NULLIF(..., N''): ileride boş metin gelirse bunu 0'a çevirmek yerine NULL yapar.
-- CAST başarısızsa hata verir; TRY_CONVERT gibi sessizce NULL üretmez.
-- tinyint 0/1 göstergeleri sayısal tutar; 0/1 dışı yeni değerler ayrıca doğrulanmalı.
-- Kategori metinlerinde uzunluk kısaltması, sayısal kodlama veya ad değişikliği yok.
-- WHERE, DELETE veya UPDATE yok; sıfır bakiyeli/süreli müşteriler dahil kalır.
-- View bütün veriyi kapsar ve ham değişirse sonucu da değişir. 
-- 2026-10-07 kullanıcı kararı: ilk EDA/Power BI paneli bu view'daki tüm 10.000 müşteriyi kullanacak.
-- ML veri ayrımı ilk panelden sonra ele alınacak; bu yorum view tanımını değiştirmez.
