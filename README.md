# Log Analyzer Kaan

log izleme ve analiz uygulaması  
Dashboard uzerinden sistem, access, trend ve security loglarini takip edebilirsiniz.

## Ozellikler

- **System Logs**: toplam/error/warning log kartlari, CPU ve memory kullanimi, en cok kaynak tuketen surecler
- **Access Logs**: method, status grubu/kodu, endpoint ve zaman kirilimi filtreleri ile grafikler
- **Trend Logs**: basarisiz giris sayisi, basarisiz giris orani ve login gecmisi
- **Security Logs**: status code dagilimi, error type dagilimi, latency trend
- **Localization (TR/EN)**: arayuz metinleri ve grafik basliklari Turkce/English degistirilebilir

## Proje Yapisi 

- `app/api/routes/`: route ve endpointler
- `app/services/`: is kurallari ve veri isleme
- `app/repositories/`: veritabani sorgulari
- `app/core/i18n.py`: ceviri sozlukleri ve dil yonetimi
- `templates/`: sayfa sablonlari
- `static/js/`: grafik ve frontend davranislari



Proje klasorunde asagidaki adimlari izleyin:

```bash
python setup_project.py
python run.py
```




