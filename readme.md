# Air Quality Data Pipeline

**ETL pipeline w Pythonie na Google Cloud Platform.**  
Pobieranie danych jakości powietrza z OpenAQ API, walidacja i zapis CSV do bucketu Google Cloud Storage.  
Uruchamiane w Google Cloud Functions, z opcją harmonogramu (Cloud Scheduler + Pub/Sub).

---

## 🛠 Stack technologiczny
- **Python 3.10** – implementacja logiki ETL  
- **Requests** – pobieranie danych z API OpenAQ  
- **Google Cloud Functions** – uruchamianie skryptu ETL  
- **Google Cloud Storage (GCS)** – przechowywanie plików wynikowych (CSV)  
- **Cloud Scheduler + Pub/Sub** – (opcjonalnie) cykliczne uruchamianie ETL  
- **Cloud Logging** – monitorowanie logów i błędów działania funkcji  

---

## ✨ Funkcjonalności
- Pobiera dane o jakości powietrza z OpenAQ API  
- Filtruje tylko **aktywne stacje pomiarowe** (dane z ostatnich 30 dni)  
- Zbiera dane z **min. 3 stacji** dla Warszawy i Nowego Jorku  
- Waliduje poprawność wartości (tylko liczbowe wartości)  
- Automatycznie wysyła plik CSV do wskazanego bucketu GCS  
- Może być uruchamiany manualnie (**HTTP trigger**) lub cyklicznie (**Cloud Scheduler + Pub/Sub**)  

---

## 📂 Struktura projektu
```bash
.
├── main.py           # Kod źródłowy funkcji ETL
├── requirements.txt  # Lista zależności Pythona
└── README.md         # Dokumentacja
⚙️ Wymagania
Aktywny projekt w Google Cloud Platform

Uprawnienia do tworzenia Cloud Functions, używania GCS i Cloud Scheduler

Python 3.10+

Klucz API do OpenAQ (ustawiany jako zmienna środowiskowa OPENAQ_API_KEY)

🚀 Deploy funkcji do Google Cloud Functions
1. Utworzenie bucketu (jeśli nie istnieje)
bash
Skopiuj kod
gsutil mb -l europe-central2 gs://NAZWA_TWOJEGO_BUCKETU
2. Deploy funkcji
bash
Skopiuj kod
gcloud functions deploy openaq_etl \
  --runtime python310 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point openaq_etl \
  --region=europe-central2 \
  --project=NAZWA_TWOJEGO_PROJEKTU \
  --set-env-vars OPENAQ_API_KEY=TWÓJ_API_KEY
🧪 Testowanie ręczne
Po deployu, funkcja dostępna jest pod publicznym URL-em:

bash
Skopiuj kod
https://europe-central2-NAZWA_TWOJEGO_PROJEKTU.cloudfunctions.net/openaq_etl
Wywołanie endpointu zwróci komunikat o sukcesie i zapisze plik CSV do wskazanego bucketu GCS.

⏱ Automatyzacja – Cloud Scheduler
1. Utwórz temat Pub/Sub
bash
Skopiuj kod
gcloud pubsub topics create openaq-trigger
2. Podepnij funkcję do Pub/Sub (zamiast HTTP)
bash
Skopiuj kod
gcloud functions deploy openaq_etl \
  --runtime python310 \
  --trigger-topic=openaq-trigger \
  --entry-point openaq_etl \
  --region=europe-central2 \
  --project=NAZWA_TWOJEGO_PROJEKTU \
  --set-env-vars OPENAQ_API_KEY=TWÓJ_API_KEY
3. Utwórz zadanie w Cloud Scheduler
bash
Skopiuj kod
gcloud scheduler jobs create pubsub openaq-job \
  --schedule="0 7 * * *" \
  --topic=openaq-trigger \
  --message-body="Start ETL" \
  --location=europe-central2
Cron 0 7 * * * oznacza codziennie o 7:00 UTC.
Możesz dostosować harmonogram według potrzeb (cron syntax).

📊 Monitoring
Cloud Logging – wszystkie logi trafiają do Stackdriver (Google Cloud Logging)

Cloud Storage – sprawdzaj bucket NAZWA_TWOJEGO_BUCKETU, czy pojawiają się pliki CSV

Cloud Scheduler – w panelu widoczne są ostatnie wykonania i ewentualne błędy

📑 Przykładowy plik CSV
csv
Skopiuj kod
city,location,parameter,value,unit,date
Warsaw,"Warszawa, ul. Wokalna",no2,35.1,µg/m³,2025-09-07T19:00:00Z
Warsaw,"Warszawa, ul. Wokalna",o3,9.1,µg/m³,2025-09-07T19:00:00Z
New York,Bronx - IS52,o3,0.027,ppm,2025-09-07T19:00:00Z
New York,Queens,pm25,10.3,µg/m³,2025-09-07T19:00:00Z
...
👤 Autor
Projekt przygotowany na potrzeby rekrutacji – Junior Data Engineer (Google Cloud, Python, OpenAQ API).

Autor: Tomasz Welcz
GitHub: tomsongracz
