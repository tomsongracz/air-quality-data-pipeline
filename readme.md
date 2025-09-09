# Air Quality Data Pipeline 

ETL pipeline w Pythonie na Google Cloud Platform. Pobieranie danych jakości powietrza z API, walidacja i zapis CSV do bucketu Google Cloud Storage. Uruchamiane w Google Cloud Functions, z opcją harmonogramu (Cloud Scheduler + Pub/Sub).

---

## Stack technologiczny
- **Python 3.10** – implementacja logiki ETL  
- **Requests** – pobieranie danych z API OpenAQ  
- **Google Cloud Functions** – uruchamianie skryptu ETL  
- **Google Cloud Storage (GCS)** – przechowywanie plików wynikowych (CSV)  
- **Cloud Scheduler + Pub/Sub** – (opcjonalnie) cykliczne uruchamianie ETL  
- **Cloud Logging** – monitorowanie logów i błędów działania funkcji  

---

## Funkcjonalności
- Pobiera dane o jakości powietrza z **OpenAQ API**.
- Filtruje tylko aktywne stacje pomiarowe (dane z ostatnich 30 dni).
- Zbiera dane z **minimum 3 stacji** dla Warszawy i Nowego Jorku.
- Weryfikuje poprawność wartości (tylko liczbowe wartości).
- Automatycznie wysyła plik CSV do wskazanego **bucketu GCS**.
- Może być uruchamiany manualnie (HTTP trigger) lub cyklicznie (Cloud Scheduler + Pub/Sub).

---

## Struktura projektu


.
├── main.py # Kod źródłowy funkcji ETL
├── requirements.txt # Lista zależności Pythona
└── README.md # Dokumentacja


---

## Wymagania
- Google Cloud Platform:
  - włączony projekt GCP (`NAZWA_TWOJEGO_PROJEKTU`)
  - uprawnienia do tworzenia Cloud Functions, używania GCS i Cloud Scheduler
- Python 3.10+
- Klucz API do OpenAQ (ustawiany jako zmienna środowiskowa `OPENAQ_API_KEY`)

---

## Deploy funkcji do Google Cloud Functions

### 1. Utworzenie bucketu (jeśli nie istnieje)
```bash
gsutil mb -l europe-central2 gs://NAZWA_TWOJEGO_BUCKETU

2. Deploy funkcji
gcloud functions deploy openaq_etl \
  --runtime python310 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point openaq_etl \
  --region=europe-central2 \
  --project=NAZWA_TWOJEGO_PROJEKTU \
  --set-env-vars OPENAQ_API_KEY=TWÓJ_API_KEY

Testowanie ręczne

Po deployu, funkcja dostępna jest pod publicznym URL-em:

https://europe-central2-NAZWA_TWOJEGO_PROJEKTU.cloudfunctions.net/openaq_etl


Wywołanie endpointu zwróci komunikat o sukcesie i zapisze plik CSV do wskazanego bucketu GCS.

Automatyzacja – Cloud Scheduler

Aby uruchamiać funkcję cyklicznie (np. raz dziennie):

1. Utwórz temat Pub/Sub
gcloud pubsub topics create openaq-trigger

2. Podepnij funkcję do Pub/Sub

Funkcja musi reagować na komunikaty Pub/Sub zamiast HTTP. Zmień trigger:

gcloud functions deploy openaq_etl \
  --runtime python310 \
  --trigger-topic=openaq-trigger \
  --entry-point openaq_etl \
  --region=europe-central2 \
  --project=NAZWA_TWOJEGO_PROJEKTU \
  --set-env-vars OPENAQ_API_KEY=TWÓJ_API_KEY

3. Utwórz zadanie w Cloud Scheduler

Zadanie wyśle pustą wiadomość do tematu Pub/Sub o określonej godzinie.

Przykład: codziennie o 7:00 rano:

gcloud scheduler jobs create pubsub openaq-job \
  --schedule="0 7 * * *" \
  --topic=openaq-trigger \
  --message-body="Start ETL" \
  --location=europe-central2


Cron 0 7 * * * oznacza codziennie o 7:00 UTC.
Harmonogram możesz dostosować według potrzeb: cron syntax
.

Monitoring

Cloud Logging – wszystkie logi z funkcji trafiają do Stackdriver (Google Cloud Logging).

Cloud Storage – sprawdzaj bucket NAZWA_TWOJEGO_BUCKETU czy pojawiają się pliki CSV.

Cloud Scheduler – w panelu widać ostatnie wykonania i ewentualne błędy.

Przykładowy plik CSV
city,location,parameter,value,unit,date
Warsaw,"Warszawa, ul. Wokalna",no2,35.1,µg/m³,2025-09-07T19:00:00Z
Warsaw,"Warszawa, ul. Wokalna",o3,9.1,µg/m³,2025-09-07T19:00:00Z
New York,Bronx - IS52,o3,0.027,ppm,2025-09-07T19:00:00Z
New York,Queens,pm25,10.3,µg/m³,2025-09-07T19:00:00Z
...

Projekt przygotowany na potrzeby rekrutacji – Junior Data Engineer (Google Cloud, Python, OpenAQ API).

Autor - Tomasz Welcz
Możesz mnie znaleźć na GitHubie: [tomsongracz](https://github.com/tomsongracz)
