# Power BI paneli

`Churn_Analysis.pbix` dört sayfadan oluşur (1920 × 1080):

| Sayfa | İçerik | Veri |
|---|---|---|
| Genel Görünüm | Gruplara göre ayrılma oranı (müşteri sayısı, %95 güven aralığı, genel oran çizgisi), değişkenlerin gücü, altı filtre | 10.000 müşteri |
| Segmentler | 24 segment, yakalama eğrisi, segment tablosu | 10.000 müşteri |
| Kapasite Senaryosu | Kapasite, teklif başarı oranı, teklif maliyeti ve müşteri değeri kaydırıcıları; model, segment kuralı ve rastgele seçim için net fayda ve başabaş başarı oranı; karışıklık matrisi | 1.501 test müşterisi |
| Model Güvenilirliği | Yöntemlerin test sonuçları, gruplara göre yakalama oranı ve güven aralıkları, kör noktalar | 1.501 test müşterisi |

Kapasite Senaryosu'ndaki maliyet ve değer rakamları varsayımdır. Rapor her açılışta referans değerlerle başlar: %20 kapasite, %20 başarı, 50 maliyet, 500 müşteri değeri. Filtre seçildiğinde liste yalnızca seçilen müşterilerden yeniden kurulur.

**Dosyalar**

- `03_dax_olculeri.md` — Genel Görünüm ve Segmentler sayfalarının DAX ölçüleri
- `04_sayfa3_olculeri.dax`, `05_sayfa3_matris.dax` — Kapasite Senaryosu ölçüleri ve karışıklık matrisi
- `tema_churn_acik.json` — renk ve yazı teması
- `veri/` — Model Güvenilirliği sayfasının CSV kaynakları (`src/churn_analysis/powerbi_cikti.py` ile üretilir)

**Veri kaynakları:** Müşteri, segment ve test skoru tabloları SQL Server görünümlerinden (`sql/07_PowerBI`, `sql/08_ML_Skorlari`), Model Güvenilirliği tabloları `veri/` klasöründen okunur. Dosyayı başka bir bilgisayarda açarken Power Query'de sunucu adını ve CSV yollarını güncellemek gerekir.

Panelin rakamları Python ve SQL sonuçlarıyla karşılaştırılarak doğrulandı.
