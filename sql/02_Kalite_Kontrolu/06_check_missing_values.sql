-- Amaç: 14 sütunun her birinde eksik değer biçimlerini ayrı saymak.
-- Yalnızca SELECT kullanır; ham veriyi değiştirmez.
-- NA / N/A / NULL / NaN metinleri eksik değer ADAYIDIR.
-- Sıfır ve Surname içindeki '?' eksik sayılmaz.
USE [ChurnAnalysis];
GO

;WITH MissingCheck AS
(
    SELECT
        v.column_order,
        v.column_name,
        CASE
            WHEN v.raw_value IS NULL THEN 1
            WHEN DATALENGTH(v.raw_value) = 0 THEN 2
            WHEN DATALENGTH(n.normalized_value) = 0 THEN 3
            WHEN UPPER(n.normalized_value) IN (N'NA', N'N/A', N'NULL', N'NAN') THEN 4
            ELSE 0
        END AS missing_kind
    FROM dbo.CustomerChurn_Raw AS r
    -- Her müşteri satırının 14 alanını (sütun adı, değer) satırlarına açar.
    -- Böylece tek bir sayma mantığı bütün sütunlara uygulanır.
    CROSS APPLY (VALUES
        (1,  N'RowNumber',       r.RowNumber),
        (2,  N'CustomerId',      r.CustomerId),
        (3,  N'Surname',         r.Surname),
        (4,  N'CreditScore',     r.CreditScore),
        (5,  N'Geography',       r.Geography),
        (6,  N'Gender',          r.Gender),
        (7,  N'Age',             r.Age),
        (8,  N'Tenure',          r.Tenure),
        (9,  N'Balance',         r.Balance),
        (10, N'NumOfProducts',   r.NumOfProducts),
        (11, N'HasCrCard',       r.HasCrCard),
        (12, N'IsActiveMember',  r.IsActiveMember),
        (13, N'EstimatedSalary', r.EstimatedSalary),
        (14, N'Exited',          r.Exited)
    ) AS v(column_order, column_name, raw_value)
    -- Kontrol sırasında tab, CR, LF ve bölünmez boşluğu normal boşluğa çevirir.
    -- TRIM baş/son normal boşlukları kaldırır; ham alanlar olduğu gibi kalır.
    CROSS APPLY (VALUES
        (TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
            v.raw_value,
            NCHAR(9), N' '),
            NCHAR(13), N' '),
            NCHAR(10), N' '),
            NCHAR(160), N' ')))
    ) AS n(normalized_value)
)
SELECT
    column_name,
    COUNT_BIG(*) AS total_rows,
    SUM(CASE WHEN missing_kind = 1 THEN 1 ELSE 0 END) AS null_count,
    SUM(CASE WHEN missing_kind = 2 THEN 1 ELSE 0 END) AS empty_string_count,
    SUM(CASE WHEN missing_kind = 3 THEN 1 ELSE 0 END) AS whitespace_only_count,
    SUM(CASE WHEN missing_kind = 4 THEN 1 ELSE 0 END) AS na_marker_count,
    SUM(CASE WHEN missing_kind <> 0 THEN 1 ELSE 0 END) AS missing_candidate_count
FROM MissingCheck
GROUP BY column_order, column_name
ORDER BY column_order;

