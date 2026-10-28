-- Amaç: iki özellik arasında kontrol: ilişki süresi (Tenure) arttıkça sıfır bakiye payı değişiyor mu?
-- Soru: Tenure = 0 grubunun sıfır bakiye payı diğer Tenure gruplarından farklı mı?
-- Tenure birimi ve hesap açılışı tanımı yok; para yatırma davranışı bu sorguda gözlenmez.
-- Kaynak: dbo.CustomerChurn_EDA. Yalnızca okur; tabloyu değiştirmez.
-- Bu, hedefle (Exited) değil iki özellik arasındaki ilişkiye bakar.
USE [ChurnAnalysis];
GO

SELECT
    Tenure,
    COUNT(*) AS CustomerCount,
    SUM(CASE WHEN Balance = 0 THEN 1 ELSE 0 END) AS ZeroBalanceCount,
    CAST(100.0 * SUM(CASE WHEN Balance = 0 THEN 1 ELSE 0 END) / COUNT(*) AS decimal(5,2)) AS ZeroBalancePct
FROM dbo.CustomerChurn_EDA
GROUP BY Tenure
ORDER BY Tenure;

-- Beklenen: Tenure = 0'da sıfır bakiye payı %33,17 (137 / 413); diğer değerlerde %33,72–37,95 arası;
-- genel pay %36,17.
-- Yorum: Tenure = 0 grubunda sıfır bakiye payı genel paydan yüksek değil (biraz düşük). "Sıfır bakiye =
-- yeni müşteri" açıklaması bu veride desteklenmiyor. Tenure'un birimi ve yeni müşteri tanımı
-- doğrulanmadığı için sıfır bakiyenin anlamı açık kalıyor.
-- 2026-10-19: dosya adı 23_tenure_x_sıfırbakiye.sql idi; numara sırası düzeltilerek 24 yapıldı.
