# Hazırlanmış veriler

`notebooks/02_ml.ipynb` tarafından üretilir.

- `ml_veri_bolumu.csv` — Her müşterinin hangi bölümde olduğu: eğitim (7.000), geliştirme (1.499), son test (1.501). Ayrılma oranı korunarak, sabit bir rastgelelik tohumuyla ayrıldı.
- `ml_test_skorlari.csv` — Son test müşterilerinin model skoru, sırası, kapasite dilimi ve segment kuralı skoru. SQL 29 ile SQL Server'a yüklenir ve Power BI'da kullanılır.

Ham veri proje kökündeki `Churn_Modelling.csv` dosyasıdır; hiçbir adımda değiştirilmez.
