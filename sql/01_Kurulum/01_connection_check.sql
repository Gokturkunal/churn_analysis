-- Amaç: SSMS'de kurduğumuz bağlantıyı tanımak.
-- Bu sorgu veri/veritabanı oluşturmaz veya değiştirmez.
-- @@SERVERNAME: sunucunun adı.
-- SERVERPROPERTY: SQL Server sürümü ve edition bilgisi.
-- DB_NAME(): sorgunun şu anda çalıştığı veritabanı.

SELECT
    @@SERVERNAME AS server_name,
    SERVERPROPERTY('ProductVersion') AS product_version,
    SERVERPROPERTY('Edition') AS edition,
    DB_NAME() AS current_database;
