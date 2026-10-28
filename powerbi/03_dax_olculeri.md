# DAX ölçüleri

Kaynak tablo: `Müşteriler` (= `dbo.vw_CustomerChurn_PowerBI`, SQL 28; 10.000 müşteri satırı). Bütün ölçüler bu tablodadır. Tablo adında Türkçe karakter olduğu için DAX'ta tek tırnakla yazılır: `'Müşteriler'`.

**Neden ölçü?** Oran, güven aralığı ve etiketler seçili filtreye göre yeniden hesaplanmalı (ör. Kadın seçilince genel oran %25,07). SQL'deki özet view'lar (SQL 26–27) sabit olduğu için yalnızca doğrulama kaynağıdır; filtre yokken her ölçü onlarla birebir aynı çıkmalıdır. Doğrulama: doğrulama kayıtları.

## Temel ölçüler (Sayfa 1 kartları)

| Ölçü | Tanım | Biçim | Filtre yokken |
|---|---|---|---|
| Müşteri Sayısı | `COUNTROWS ( 'Müşteriler' )` | #,0 | 10.000 |
| Ayrılan Sayısı | `SUM ( 'Müşteriler'[Exited] )` | #,0 | 2.037 |
| Kalan Sayısı | `[Müşteri Sayısı] - [Ayrılan Sayısı]` | #,0 | 7.963 |
| Ayrılma Oranı | `DIVIDE ( [Ayrılan Sayısı], [Müşteri Sayısı] )` | %0,00 | %20,37 |

## Risk etiketleri (renk, ipucu, genel oran çizgisi)

Kurallar EDA Bölüm 3 ve SQL 27 ile aynıdır: grubun %95 Wilson aralığı seçili genel oranın tamamen üstündeyse Yüksek risk, tamamen altındaysa Düşük risk, içeriyorsa Fark yok; n < 100 → Güven "Düşük (n < 100)", aralık ≤ 10 puan → "Yüksek", daha geniş → "Orta".

```DAX
Seçili Genel Oran = CALCULATE ( [Ayrılma Oranı], ALLSELECTED ( 'Müşteriler' ) )
```
`ALLSELECTED` grafiğin kendi gruplamasını (ör. yaş grubu) kaldırır ama dilimleyici ve çapraz filtre seçimlerini korur. Böylece referans, "seçili müşterilerin tamamının oranı" olur. Filtre yokken %20,37; Cinsiyet = Kadın iken %25,07; Ülke = Almanya iken %32,44.

```DAX
Wilson Alt =
VAR n = [Müşteri Sayısı]
VAR p = [Ayrılma Oranı]
VAR z = 1.96
RETURN
    IF ( n > 0,
        ( p + z ^ 2 / ( 2 * n ) - z * SQRT ( p * ( 1 - p ) / n + z ^ 2 / ( 4 * n ^ 2 ) ) ) / ( 1 + z ^ 2 / n ) )

Wilson Üst =
VAR n = [Müşteri Sayısı]
VAR p = [Ayrılma Oranı]
VAR z = 1.96
RETURN
    IF ( n > 0,
        ( p + z ^ 2 / ( 2 * n ) + z * SQRT ( p * ( 1 - p ) / n + z ^ 2 / ( 4 * n ^ 2 ) ) ) / ( 1 + z ^ 2 / n ) )

Ortalamaya Göre =
SWITCH ( TRUE (),
    ISBLANK ( [Wilson Alt] ), BLANK (),
    [Wilson Alt] > [Seçili Genel Oran], "Yüksek risk",
    [Wilson Üst] < [Seçili Genel Oran], "Düşük risk",
    "Fark yok" )

Güven =
SWITCH ( TRUE (),
    [Müşteri Sayısı] < 100, "Düşük (n < 100)",
    ( [Wilson Üst] - [Wilson Alt] ) * 100 <= 10, "Yüksek",
    "Orta" )

Risk Rengi =
SWITCH ( [Ortalamaya Göre],
    "Yüksek risk", "#C97A5A",
    "Düşük risk", "#4E91AA",
    "#8A8F96" )

Güven Rengi =
SWITCH ( [Güven],
    "Düşük (n < 100)", "#F0CD7D",
    "Orta", "#FBF3DD" )
```
Wilson formülü SQL 26–27 ve `eda.wilson_aralik` ile aynıdır. `Risk Rengi` sütun grafiklerinde **Sütunlar → Renk → fx → Alan değeri**; `Güven Rengi` segment tablosunda yalnızca Güven sütununun arka planına bağlıdır. `Seçili Genel Oran`, `Wilson Alt` ve `Wilson Üst` yüzde, 2 ondalık.

## Segment sayfası (yakalama eğrisi)

```DAX
Kümülatif Müşteri Payı =
VAR r = MAX ( 'Müşteriler'[SegmentRank] )
RETURN
    DIVIDE (
        CALCULATE ( [Müşteri Sayısı], ALLSELECTED ( 'Müşteriler' ), 'Müşteriler'[SegmentRank] <= r ),
        CALCULATE ( [Müşteri Sayısı], ALLSELECTED ( 'Müşteriler' ) ) )

Kümülatif Ayrılan Payı =
VAR r = MAX ( 'Müşteriler'[SegmentRank] )
RETURN
    DIVIDE (
        CALCULATE ( [Ayrılan Sayısı], ALLSELECTED ( 'Müşteriler' ), 'Müşteriler'[SegmentRank] <= r ),
        CALCULATE ( [Ayrılan Sayısı], ALLSELECTED ( 'Müşteriler' ) ) )
```
Segment sırası (`SegmentRank`, S01 en riskli) EDA'da tüm veride belirlendi ve sabittir; filtre seçilince paylar yeniden hesaplanır, sıra değişmez. Filtre yokken SQL 26'daki kümülatif paylarla aynı (S01 %3,26 / %13,75; S08 %20,11 / %57,73). Biçim: yüzde, 1 ondalık. Grafiğin X ekseni `Segment Kodu`'na göre **artan** sıralanmalıdır.

## Notlar

- Ölçü adları büyük harfle başlar (kullanıcı tercihi). DAX ad eşleştirmesinde büyük/küçük harf duyarlı değildir.
- Hazır "Ortalama çizgisi" (Analiz bölmesi) çubukların düz ortalamasını aldığı için kullanılmadı (yaşta ≈ %25,1, yanlış); bunun yerine `Seçili Genel Oran`'a bağlı **sabit çizgi** kullanıldı.
- Rapor ayarı: varsayılan etkileşim **çapraz filtreleme** (vurgulama değil). Oran grafiklerinde vurgulama, alt kümenin oranını bütünün parçası gibi gösterdiği için yanıltıcıdır.
