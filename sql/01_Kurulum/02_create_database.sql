-- Amaç: müşteri verisi için ayrı proje veritabanı oluşturmak.
-- master, SQL Server'ın sistem veritabanıdır; proje verisini oraya yüklemeyiz.
USE [master];
GO

-- Dosya tekrar çalıştırılırsa mevcut veritabanını korur.
IF DB_ID(N'ChurnAnalysis') IS NULL
BEGIN
    CREATE DATABASE [ChurnAnalysis];
END;
GO

-- Bundan sonraki sorguların çalışacağı veritabanını seçer.
USE [ChurnAnalysis];
GO

-- Beklenen sonuç: ChurnAnalysis. Henüz tablo veya müşteri verisi yok.
SELECT DB_NAME() AS current_database;
