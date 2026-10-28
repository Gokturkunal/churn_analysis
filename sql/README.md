# SQL sorguları

SQL Server (Express) üzerinde, `ChurnAnalysis` veritabanında çalışır. Dosya numaraları çalıştırma sırasını gösterir. Her dosyanın başında amacı ve beklenen sonucu açıklanmıştır.

| Klasör | Dosyalar | Ne yapar? |
|---|---|---|
| `01_Kurulum` | 01–04 | Bağlantı kontrolü, veritabanı, ham tablo ve CSV yükleme (10.000 satır) |
| `02_Kalite_Kontrolu` | 05–12 | Müşteri kimlikleri, eksik değerler, 0/1 alanlar, kategoriler, sayısal dönüşüm ve aralıklar, soyadı karakterleri |
| `03_Analiz_Katmani` | 13–16 | Uygun veri türleriyle analiz görünümü (view), kontrolleri ve analiz tablosu |
| `04_Tek_Degiskenli_Analiz` | 17–23 | Kapsam, kategori sıklıkları, yaş / kredi puanı / maaş / bakiye özetleri |
| `05_Iki_Degiskenli_Analiz` | 24, 27 | İlişki süresi ile sıfır bakiye; gruplara göre ayrılma oranı ve güven aralığı görünümü |
| `06_Segmentler` | 25–26 | Python'da kurulan segmentlerin yüklenmesi ve segment özeti |
| `07_PowerBI` | 28 | Power BI için Türkçe etiketli müşteri görünümü |
| `08_ML_Skorlari` | 29 | Model test skorlarının yüklenmesi ve Power BI görünümü |

**Kalite kontrollerinin sonucu:** 10.000 satır ve 10.000 benzersiz müşteri; eksik değer, geçersiz 0/1 değeri ve sayısal dönüşüm hatası yok. 92 kaydın soyadında bozuk karakter var; soyadı analizde kullanılmadığı için sonuçları etkilemiyor.

**Not:** `04`, `25` ve `29` numaralı dosyalardaki `BULK INSERT` satırları dosyaları yerel bir yoldan okur; kendi bilgisayarınızda bu yolları değiştirmeniz gerekir.
