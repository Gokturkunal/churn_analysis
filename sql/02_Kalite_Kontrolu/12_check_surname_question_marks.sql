-- Amaç: Surname içinde gerçek '?' karakteri bulunan kayıtları saymak.
-- SQL LIKE içinde '%' sıfır veya daha fazla karakteri temsil eder.
-- '?' burada joker değildir, gerçek soru işaretidir.
-- '?%' yalnızca soru işaretiyle BAŞLAYAN metinleri bulur.
-- '%?%' soru işaretini herhangi bir konumda bulur; H? ve L? dahildir.
USE [ChurnAnalysis];
GO

-- 1. Sonuç: toplam kayıt ve soru işareti içeren kayıt sayısı.
SELECT
    COUNT_BIG(*) AS total_rows,
    SUM(CASE WHEN Surname LIKE N'%?%' THEN 1 ELSE 0 END) AS question_mark_count  -- Herhangi bir yerinde ? bulunan "%?%"
FROM dbo.CustomerChurn_Raw;

-- 2. Sonuç: etkilenen soyadı biçimleri ve her birinin kayıt sayısı.
SELECT
    Surname COLLATE Latin1_General_100_BIN2 AS observed_surname,
    COUNT_BIG(*) AS row_count
FROM dbo.CustomerChurn_Raw
WHERE Surname LIKE N'%?%'
GROUP BY Surname COLLATE Latin1_General_100_BIN2
ORDER BY row_count DESC, observed_surname;

-- Yalnızca okur. İsim tahmin etmez, '?' karakterini kaldırmaz, müşteri silmez.
-- Bu bir eksik değer kontrolü değil, şüpheli karakter kontrolüdür.
-- Her '?' içeren kayıt bir kez sayılır; bu sayı '?' karakterlerinin toplamı değildir.
-- Surname ham tabloda korunacak; model girdisi olmayacak.

