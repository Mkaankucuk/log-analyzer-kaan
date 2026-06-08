# Log Analyzer Kaan

log izleme ve analiz uygulaması  
Dashboard uzerinden sistem, access, trend, security loglarını ve canlı izleme/alarmları görebilirsiniz

## Özellikler

- **System Logs**: toplam/error/warning log kartları, CPU ve memory kullanımı, en çok kaynak tüketen süreçler
- **Access Logs**: method, status grubu/kodu, endpoint ve zaman kırılımı filtreleri ile grafikler
- **Trend Logs**: başarısız giriş sayısı, basarısız giris orani ve login geçmişi
- **Security Logs**: status code dağılımı, error type dağılımı, latency trend
- **Live Monitor**: canlı log akışı, gecikme ve durum kodu grafikleri, anomali takibi
- **Alarmlar**: cron job ile log taraması, aktif alarm listesi ve onaylama
- **Mail Yönetimi**: SMTP bildirimleri, gönderim aralığı ve alıcı ayarları
- **AI Log Analizi**: access/security log veya yüklenen dosya ile Ollama (llama3) analizi, TR/EN yanıt
- **Dosya Yükleme**: log dosyası önizleme ve AI analiz için geçici kayıt
- **Localization (TR/EN)**: arayüz metinleri ve grafik başlıkları Türkçe/English değiştirilebilir

## Proje Yapisi 

- `app/api/routes/`: route ve endpointler
- `app/services/`: is kurallari ve veri isleme
- `app/repositories/`: veritabani sorgulari
- `app/core/i18n.py`: çeviri sözlükleri ve dil yönetimi
- `templates/`: sayfa şablonları
- `static/js/`: grafik ve frontend davranışları



Proje klasorunde asagidaki adimlari izleyebilirisiniz:

```bash
python setup_project.py
python run.py
```

Mail ve AI analiz için `.env.example` dosyasını `.env` olarak kopyalayıp düzenleyin.

