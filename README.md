# Log Analyzer Kaan

log izleme ve analiz uygulaması  
Dashboard uzerinden sistem, access, trend ve security loglarını görebilirsiniz

## Ozellikler

- **System Logs**: toplam/error/warning log kartları, CPU ve memory kullanımı, en çok kaynak tüketen süreçler
- **Access Logs**: method, status grubu/kodu, endpoint ve zaman kırılımı filtreleri ile grafikler
- **Trend Logs**: başarısız giriş sayısı, basarısız giris orani ve login geçmişi
- **Security Logs**: status code dağılımı, error type dağılımı, latency trend
- **Localization (TR/EN)**: arayüz metinleri ve grafik başlıkları Türkçe/English değeiştirilebilir

## Proje Yapisi 

- `app/api/routes/`: route ve endpointler
- `app/services/`: is kurallari ve veri isleme
- `app/repositories/`: veritabani sorgulari
- `app/core/i18n.py`: ceviri sozlukleri ve dil yonetimi
- `templates/`: sayfa sablonlari
- `static/js/`: grafik ve frontend davranislari



Proje klasorunde asagidaki adimlari izleyebilirisiniz:

```bash
python setup_project.py
python run.py
```




