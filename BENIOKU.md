# KADEM

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24401203.svg)](https://doi.org/10.5281/zenodo.24401203)

**Kinematic–Kinetic Automated Data Extraction in Motion** (English: [README.md](README.md))

Plug-in Gait ile işlenmiş C3D dosyalarından yürüme analizi değişkenlerini çeken masaüstü programı.
Aralık, değişken ve istatistik açılır listelerden seçilir; sonuçlar SPSS'e ve R'a hazır tek bir Excel dosyasına yazılır.

## Kurulum

Program Windows 10 ve 11'de çalışır. Kendi penceresinde açılır (Windows'taki Microsoft Edge'in uygulama modu); pencereyi
kapatınca program da kapanır. Bilgisayar dışına veri gönderilmez; program yalnızca bu bilgisayarın içinde (127.0.0.1) çalışır.

### A) İndirip çalıştırma (Python gerekmez)

1. [Releases](https://github.com/omerhekim/kadem/releases) sayfasından en son sürümün `KADEM_Windows.zip` dosyasını indirin.
2. Zip'i istediğiniz bir klasöre çıkarın ve **`KADEM.exe`** dosyasını çalıştırın. Yanındaki `_internal` klasörü
   programın parçasıdır; ikisi aynı yerde kalmalı. `.exe` için masaüstüne kısayol oluşturabilirsiniz.
3. Program imzasız olduğu için Windows ilk açılışta SmartScreen uyarısı verebilir: "Ek bilgi → Yine de çalıştır".
   Kurum bilgisayarlarında bilgi işlem onayı gerekebilir.

### B) Kaynaktan çalıştırma (geliştiriciler için)

Python 3.10 ya da daha yeni bir sürüm gerekir (kurulumda **"Add python.exe to PATH"** kutusunu işaretleyin).
`calistir.bat` dosyasına çift tıklayın; ilk çalıştırmada gerekli paketleri kurar (internet gerekir), sonra programı açar.
`build_exe.bat` aynı bilgisayarda `dist\KADEM\KADEM.exe` dosyasını derler; Releases sayfasındaki sürümler de aynı
yöntemle GitHub üzerinde derlenir.

## Kullanım

Sağ üstteki **English / Türkçe** düğmesiyle (ya da Ayarlar → Dil) arayüz, uyarılar ve Excel çıktısının dili değiştirilir;
seçim bir sonraki açılışta da hatırlanır.

Soldaki altı adımı sırayla izleyin. Her adım sonradan tekrar açılıp değiştirilebilir. Çalışmanızı **Kaydet** ile bir proje
dosyası (`.c3dproj`) olarak saklayın. Proje; dosya listesini, EMG eşleştirmelerini, sorguları, hasta bilgilerini ve ayarları içerir.

1. **Dosyalar**: "Klasör ekle…" ile bir klasör seçin; alt klasörlerdeki tüm C3D dosyaları eklenir.
   - Hasta adı dosya adından alınır ("Ayse Yilmaz Cal 05" → "Ayse Yilmaz"). Gerekirse tabloda düzeltin.
   - **Ölçüm tarihi** önce C3D'nin içinde aranır (Nexus genelde yazmaz), sonra dosyanın bulunduğu klasörün adından okunur:
     `…\Hasta Adı\13 01 2026\Hasta Adı Cal 05.c3d` → 2026-01-13. `13.01.2026`, `13-01-2026`, `2026-01-13` biçimleri de olur.
     Klasör adında tarih yoksa tarih boş kalır ve sarı **!** ile işaretlenir; tabloda girin ya da birden fazla dosyayı seçip
     "Tarih ata…" kullanın. Nexus dosyaları (`.enf`, `.x2d`) ve dosya tarihleri kullanılmaz; bunlar process edilince değişir.
     Ortalamalar **hasta + tarih** bazında alınır.
   - Yazımı benzeyen hasta adları (Yılmaz/Yilmaz gibi) üstte uyarı olarak gösterilir.
   - **Baştaki tik = hesaplamaya dahil.** Dosyalar tikli gelir; tiki kaldırılan dosya listede kalır ama hesaplanmaz.
     Başlıktaki kutu listede görünen (aramayla süzülmüş) dosyaların tümünü açar ya da kapatır.
   - Toplu işlem (hasta adı ata, tarih ata, listeden çıkar) için satırlara tıklayın; Ctrl ile tek tek, Shift ile aralık seçilir.
2. **EMG kanalları**: Dosyalardaki EMG kanalları listelenir. Her kanalı bir kasa ve tarafa eşleştirin.
   - Kanal adı farklı dosyalarda farklıysa (`L_Tib_Ant.v`, `L_Tibialis_Anterior.v`) her birini aynı kasa eşleştirin.
   - Program eşleştirmeleri hatırlar; aynı kanal adı sonraki projelerde otomatik eşleşir.
   - "Yalnızca 50 Hz parazit" yazan kanallarda sensör bağlı değildir.
3. **Sorgular**: Her sorgu Excel'de bir değişken (sütun) olur.
   - **1 Aralık ya da an** → **2 Değişken** → **3 İstatistik** seçip "Listeye ekle".
   - Aralıklar event'lere dayanır: tüm döngü, stance, swing, 1. çift destek, tek destek, 2. çift destek, itme penceresi.
   - **Özel aralık…**: istediğiniz %GC aralığı (ör. %0–2, %48–52), %stance/%swing aralığı ya da bir event'e ya da referans
     ana göre kaydırılmış pencere. Kayma ms ya da %GC olarak girilir; pozitif değer sonrasını, negatif değer öncesini gösterir
     (ör. IC öncesi 100 ms için −100; H2 tepe anından sonraki %10 GC için başlangıç 0, bitiş 10).
   - **Referans an…**: ör. "pik ayak bileği gücü anı". Sonra o andaki herhangi bir değişkeni (kalça ve diz gücü, EMG) çekebilir
     ya da aralık sınırı olarak kullanabilirsiniz. Winter güç fazlarının (A1–A2, K1–K4, H1–H3) tepe anları hazır gelir.
   - **Düzenleme ve silme**: özel aralıklar ve referans anlar kalem simgesiyle düzenlenir (adı ve tanımı); onları kullanan
     sorgular korunur ve yeni tanımla hesaplanır. Kullanılan bir aralık silinirken onunla birlikte silinecek sorgular önce gösterilir.
   - **Lob istatistikleri** (güç, moment gibi işaret değiştiren eğriler için): en büyük pozitif / negatif lobun alanı; ilk pozitif /
     negatif lobun alanı, uç değeri ve zamanı. "İlk lob" aranırken süresi %2 GC'den kısa loblar atlanır (Ayarlar'dan değişir).
   - **Örnek çalışma paketleri**: E, S, P, W, G, N adlı hazır değişken setleri. Kendi çalışmanız için başlangıç noktası olarak kullanabilirsiniz.
   - **Şablon**: sorgu listesini bir dosyaya kaydedip başka projede ya da meslektaşınızın bilgisayarında yükleyebilirsiniz.
   - **Dalga formları** (isteğe bağlı): seçilen aralık eşit noktalara bölünür (ör. 101 nokta). Ayrı bir Excel dosyasına yazılır;
     hasta sayfası SPM girdisidir. "Örnek dalga formları (W9–W12)" düğmesi diz/ayak bileği sagittal, diz frontal ve KAM eğrilerini ekler.
4. **Hastalar ve MVIC**: Etkilenen tarafı girerseniz Excel'e etkilenen/sağlam, fark ve LSI sütunları eklenir (zorunlu değil).
   Tarafları tek tek seçebilir ya da **"Tarafları toplu yapıştır…"** ile Excel'den `Hasta | Taraf` (isteğe bağlı `Tarih`) sütunlarını
   yapıştırabilirsiniz; uygulamadan önce eşleşen ve eşleşmeyen satırlar gösterilir. "Hasta listesini kopyala" listeyi Excel'e
   götürür. Bir taraf kutusu seçiliyken Ctrl+V, yapıştırılan sütunu o satırdan aşağı doldurur.
   EMG'yi %MVIC olarak istiyorsanız MVIC değerlerini buraya girin ya da Excel'den içe aktarın
   (`Hasta | Taraf | TA_MVIC_uV` gibi tek kaslı tablolar da okunur).
5. **Ayarlar**: EMG filtre zinciri (varsayılan: Butterworth 4. derece, HP 20 Hz, LP 500 Hz, 50 ms RMS), EMG normalizasyonu,
   eksik veri kuralı, ortalama yöntemi gibi ayarlar. Hepsi Excel'in "Yöntem" sayfasına yazılır.
6. **Çalıştır ve sonuçlar**: Çıktı klasörünü ve dosya adını seçip "Çalıştır". Aynı adla bir çıktı varsa program üzerine
   yazmadan önce sorar ve sonuna `_2`, `_3` eklenmiş yeni bir ad önerir. EMG genlik değişkeni varken normalizasyon seçilmemişse uyarır. Bittiğinde uyarılar, uç değerler ve hasta
   tablosunun önizlemesi görünür. "Döngüleri dışla" sekmesinden tek tek döngüleri gerekçesiyle dışlayabilirsiniz
   (bir sonraki çalıştırmada uygulanır).

## Excel çıktısı

| Sayfa | İçerik |
|---|---|
| 1_Hasta_Duzeyi | Hasta + tarih başına tek satır. Taraf bazlı değişkenler `L_` ve `R_` önekiyle. SPSS'e hazır. `Kinetik_Tamam` = 1: iki tarafta da en az bir kinetik döngü var. |
| 2_Uzun_Format | Hasta, taraf, değişken, ortalama, SS, N, CV. R için. |
| 3_Trial_Ortalamalari | Dosya (trial) düzeyinde ortalamalar. |
| 3b_Trial_Hiz_Kadans | Hız ve kadans (iki taraf birlikte, trial başına). |
| 4_Tum_Donguler | Her döngünün değerleri. **Düzenlenebilen tek sayfa** (aşağıya bakın). |
| 5_Uyarilar | Programın gördüğü her şüpheli durum (Hata / Uyarı / Bilgi). |
| 6_Uc_Degerler | Uç değerler. Silinmez, yalnızca listelenir. |
| 7_Dislanan_Donguler | Dışlanan döngüler ve gerekçeleri. |
| 8_Degisken_Sozlugu | Her sütunun tanımı: değişken, bileşen ve işaret kuralı, aralık, istatistik, birim. |
| 9_Yontem | Kullanılan ayarlar ve yöntem metni (makalenin yöntem bölümü için). |
| 10_Dosyalar | Dosya listesi, kare hızları, kütle, bacak uzunluğu, döngü sayıları, tarihin kaynağı. |
| 11_EMG_Referanslari | EMG normalizasyonunda kullanılan MVIC ya da dinamik referanslar. |
| 12_Algoritma | Her sütunun adım adım hesaplanışı: C3D'deki kaynak sinyal, aralık sınırları, istatistik formülü, eksik veri kuralı, döngüden hastaya birleştirme. |

**Döngü sayfasında düzeltme.** 3_Trial_Ortalamalari, 1_Hasta_Duzeyi ve 2_Uzun_Format sayfalarındaki ortalamalar
4_Tum_Donguler'e formülle bağlıdır. Bir döngünün değerini değiştirirseniz ya da `Dislandi` sütununa 1 yazarsanız trial
ortalaması, hasta değeri, Fark/LSI ve uzun formattaki ortalama/SS/N kendiliğinden güncellenir. Ne değiştirdiğinizi
`Duzeltme_Notu` sütununa yazın. Güncellenmeyenler: uç değerler, dinamik EMG normalizasyon referansları, dalga formları ve
programın hiç değer bulamadığı (boş) hücreler; bunlar için programı yeniden çalıştırın.

**Kilitli sayfalar.** Döngü sayfası dışındaki sayfalar yanlışlıkla değiştirmeye karşı şifresiz kilitlidir. Filtreleme,
seçme ve kopyalama serbesttir. Gerekirse "Gözden Geçir → Sayfa Korumasını Kaldır" ile açılır.

Program İngilizce kullanılıyorsa sayfa ve sabit sütun adları da İngilizce yazılır (`1_Patient_Level`, `Excluded`,
`Correction_Note` …). Değişken sütunlarının adları (ör. `L_E2_Peak_Knee_Flex_LR`) iki dilde de aynıdır.

## Program ne yapar, ne yapmaz

- **Veriyi düzeltmez.** C3D'de ne varsa onunla hesaplar; şüpheli her durumu "Uyarılar" sayfasına yazar. Event düzeltmesi Nexus'ta yapılır.
- **Eksik veri doldurulmaz.** Bir aralıkta eksik örnek varsa (GRF'de stance içi boşluk, EMG paket kaybı, marker boşluğu) o değer
  boş bırakılır ve uyarı yazılır. Ayarlardan "mevcut örneklerle hesapla" seçilebilir.
- **Event zamanları kareye yuvarlanmaz.** Aralık sınırındaki değer komşu kareler arasından interpolasyonla alınır.
  Kare bazlı çalışan başka bir yöntemle birebir karşılaştırma için Ayarlar'da "En yakın kareye yuvarla" seçeneği vardır.
- **Kinetik değişkenler** yalnızca kuvvet plakasına basılan döngülerde hesaplanır. Nexus plakaya basmayan bacak için de moment
  eğrisi yazar; program o tarafın yer tepki kuvvetine bakar ve plakasız döngülerdeki momenti kullanmaz.
- **Kinetik bütünlük.** Bir hasta + tarihte bir tarafta hiç kinetik döngü yoksa satır silinmez; `Kinetik_Tamam` = 0 yazılır,
  "Uyarılar" sayfasında Hata olarak listelenir ve çalıştırma sonunda ekranda gösterilir. En az döngü sayısı Ayarlar'dan değişir.
- **Tepe değerleri** her döngüde ayrı bulunur, sonra ortalanır (ortalama eğrinin tepesi değil). Tepe aralığın tam ucundaysa
  "Bilgi" notu yazılır (eğri aralık bittiğinde hâlâ yükseliyor olabilir).
- **GRF ön-arka bileşeni** yürüme yönüne göre çevrilir (+ = ileri/itme); medio-lateral bileşen her tarafta + = medial.
- **EMG veri kaybı**: kablosuz sensörde paket kaybolduğunda sinyal sabit kalır. Program bu bölgeleri bulur, bu bölgelere
  denk gelen EMG değerlerini boş bırakır.

## Sorun giderme

- **Pencere açılmıyor:** Program Edge'i bulamazsa varsayılan tarayıcıda açılır. Hiçbir şey açılmazsa programı tekrar başlatın.
- **Windows Defender / SmartScreen uyarısı:** İmzasız programlarda görülebilir. "Ek bilgi → Yine de çalıştır".
  Kurum bilgisayarlarında bilgi işlem onayı gerekebilir.
- **Excel yazılamadı:** Çıktı dosyası Excel'de açıksa kapatıp tekrar çalıştırın.
- **Hata kaydı:** `%LOCALAPPDATA%\KADEM\hata_kaydi.txt`. Bir hata olursa bu dosyayı gönderin.
- **Eski sürümden geçiş:** v0.2 (C3D Veri Çekici) projeleri (`.c3dproj`) ve şablonları olduğu gibi açılır; EMG kanal
  eşleştirmeleri ve dil tercihi ilk açılışta taşınır.

## Atıf

KADEM Zenodo'da arşivlenmiştir. Bir yayında kullandıysanız lütfen kullandığınız sürüme atıf verin:

> Hekim Ö. *KADEM: Kinematic–Kinetic Automated Data Extraction in Motion* (Version 0.3.1) [Computer software].
> Zenodo; 2026. https://doi.org/10.5281/zenodo.24401204

[10.5281/zenodo.24401203](https://doi.org/10.5281/zenodo.24401203) DOI'si tüm sürümleri kapsar ve her zaman en son sürüme yönlendirir; her sürümün kendi
DOI'si o Zenodo sayfasında listelenir. Atıf bilgileri: [CITATION.cff](CITATION.cff).

## Kapsam ve sorumluluk

KADEM araştırma amaçlı bir yazılımdır; tıbbi cihaz değildir ve tanı ya da tedavi kararı için tek başına kullanılmamalıdır.
Program, Vicon Nexus'ta Plug-in Gait alt ekstremite modeliyle işlenmiş C3D dosyaları için yazılmış ve bu dosyalarla
sınanmıştır. Conventional Gait Model 2.2 (pyCGM2) alt ekstremite çıktılarıyla da denenmiş ve çalışmaktadır. Aynı çıktı
adlarını kullanan başka modellerin de çalışması beklenir ama denenmemiştir; üst ekstremite çıktıları denenmemiştir. Vicon, Nexus, Polygon ve Plug-in Gait, Vicon Motion Systems Ltd.'nin; Noraxon ve
myoRESEARCH, Noraxon USA Inc.'in markalarıdır. KADEM bu şirketlerle bağlantılı değildir ve onların yazılımını içermez.
