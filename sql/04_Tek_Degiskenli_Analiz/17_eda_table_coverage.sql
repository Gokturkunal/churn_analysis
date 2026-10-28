-- Amaç: Power BI ve EDA'nın okuduğu dbo.CustomerChurn_EDA tablosunda kapsam ve eksik değer özeti.
-- SQL 14 (view) ve SQL 16 (tablo oluşturma) kontrollerinin, tek değişkenli analize başlamadan
-- bu tablo üzerinde bilinçli olarak tekrarıdır: analiz edilen tablo eksiksiz mi?
-- Yalnızca okur; tabloyu değiştirmez.
USE [ChurnAnalysis];
GO

SELECT
    COUNT_BIG(*)                          AS row_count,
    COUNT(DISTINCT CustomerId)            AS unique_customer_ids,
    COUNT_BIG(*) - COUNT(CreditScore)     AS CreditScore_missing,
    COUNT_BIG(*) - COUNT(Geography)       AS Geography_missing,
    COUNT_BIG(*) - COUNT(Gender)          AS Gender_missing,
    COUNT_BIG(*) - COUNT(Age)             AS Age_missing,
    COUNT_BIG(*) - COUNT(Tenure)          AS Tenure_missing,
    COUNT_BIG(*) - COUNT(Balance)         AS Balance_missing,
    COUNT_BIG(*) - COUNT(NumOfProducts)   AS NumOfProducts_missing,
    COUNT_BIG(*) - COUNT(HasCrCard)       AS HasCrCard_missing,
    COUNT_BIG(*) - COUNT(IsActiveMember)  AS IsActiveMember_missing,
    COUNT_BIG(*) - COUNT(EstimatedSalary) AS EstimatedSalary_missing,
    COUNT_BIG(*) - COUNT(Exited)          AS Exited_missing
FROM dbo.CustomerChurn_EDA;

-- Sonuç (kullanıcı SSMS sonucu, 2026-10-07): 10.000 satır, 10.000 farklı müşteri, bütün alanlarda 0 eksik.
-- COUNT(alan) NULL olmayan değerleri sayar; COUNT_BIG(*) - COUNT(alan) eksik değer sayısıdır.
-- Boş metin veya boşluk gibi "gizli eksikler" ham tabloda SQL 06'da ayrıca denetlendi.
