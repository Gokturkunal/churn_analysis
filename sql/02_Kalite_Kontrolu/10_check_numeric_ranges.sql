-- Amaç: altı sayısal özelliğin değer aralıklarını ve negatif/sıfır sayılarını görmek.
-- Genel kalite kontrolüdür; Exited ile ilişkiler veya model seçimleri incelenmez.
-- Ham veriyi değiştirmez. Bulgular otomatik silme/doldurma kararı değildir.
USE [ChurnAnalysis];
GO

SELECT
    v.column_name,
    COUNT_BIG(*) AS total_rows,
    COUNT_BIG(v.numeric_value) AS numeric_rows,
    MIN(v.numeric_value) AS min_value,
    MAX(v.numeric_value) AS max_value,
    SUM(CASE WHEN v.numeric_value < 0 THEN 1 ELSE 0 END) AS negative_count,
    SUM(CASE WHEN v.numeric_value = 0 THEN 1 ELSE 0 END) AS zero_count
FROM dbo.CustomerChurn_Raw AS r
CROSS APPLY (VALUES
    (1, N'CreditScore',     TRY_CONVERT(int, NULLIF(TRIM(r.CreditScore), N''))),
    (2, N'Age',             TRY_CONVERT(int, NULLIF(TRIM(r.Age), N''))),
    (3, N'Tenure',          TRY_CONVERT(int, NULLIF(TRIM(r.Tenure), N''))),
    (4, N'Balance',         TRY_CONVERT(decimal(38,10), NULLIF(TRIM(r.Balance), N''))),
    (5, N'NumOfProducts',   TRY_CONVERT(int, NULLIF(TRIM(r.NumOfProducts), N''))),
    (6, N'EstimatedSalary', TRY_CONVERT(decimal(38,10), NULLIF(TRIM(r.EstimatedSalary), N'')))
) AS v(column_order, column_name, numeric_value)
GROUP BY v.column_order, v.column_name
ORDER BY v.column_order;

-- COUNT_BIG(*) bütün kayıtları; COUNT_BIG(numeric_value) yalnızca NULL olmayan
-- sayıları sayar. İkisi de 10.000 olmalı; farklıysa önce dönüşüm incelenir.
-- MIN/MAX NULL değerleri saymaz; bu nedenle numeric_rows ayrıca gösterilir.
-- Ortak VALUES sütunu sayı türlerini ortak decimal türünde gösterir;
-- yaş gibi tam sayılarda sonuçta .0000000000 görünmesi hata değildir.
-- Para alanlarında şimdilik 10 ondalık basamakla bakılır. Kalıcı analiz
-- türü kararı ve iki ondalık basamağa dönüşümde kayıp kontrolü ayrı yapılacak.

-- Yorumlama:
-- Age <= 0: yaş tanımı açısından incelenmeli.
-- NumOfProducts <= 0: ürün kapsamına göre incelenmeli; otomatik silinmez.
-- Negatif Tenure: süre tanımı açısından incelenmeli; birimi henüz bilinmiyor.
-- Negatif Balance: kredili/eksi hesap gibi bir anlamı olabilir; otomatik hata sayılmaz.
-- Balance=0 ve Tenure=0: eksik değer sayılmaz; iş tanımlarıyla değerlendirilir.
-- CreditScore ölçeği, maaş dönemi ve para birimi bilinmediğinden bunlara
-- dışarıdan kesin üst/alt sınır uydurulmaz. Büyük değerler tek başına hata değildir.
