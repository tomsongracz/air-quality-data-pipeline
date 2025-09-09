import os
import csv
import requests
from datetime import datetime, timedelta, timezone
from google.cloud import storage
from math import radians, cos, sin, asin

# Konfiguracja

# Definiujemy miasta, dla których chcemy pobrać dane
CITY_CFG = {
    "Warsaw": {
        "iso": "PL",
        "coords": (52.2297, 21.0122),   # współrzędne centrum Warszawy
        "radius_m": 25000               # promień wyszukiwania stacji w metrach
    },
    "New York": {
        "iso": "US",
        "coords": (40.7128, -74.0060),  # współrzędne centrum NYC
        "radius_m": 25000
    },
}

# Parametry jakości powietrza, które nas interesują
PARAMETERS = {"pm25", "pm10", "o3", "no2"}

# Nazwa bucketa w Google Cloud Storage, do którego wrzucamy CSV
BUCKET_NAME = "alterdata-rekrutacja-5-bucket"

# Klucz API pobieramy ze zmiennej środowiskowej (ustawiony przy deployu)
API_KEY = os.environ.get("OPENAQ_API_KEY")
BASE = "https://api.openaq.org/v3"
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

# Ile dni wstecz dane uznajemy za "świeże"
FRESH_DAYS = 30
# Limit kandydatów (stacji) branych pod uwagę
MAX_CANDIDATES = 40
# Timeout na requesty
TIMEOUT = 15


# Funkcje 

def _get_json(path, params=None, timeout=TIMEOUT):
    """
    Funkcja do wykonywania requestów GET do API OpenAQ.
    Obsługuje błędy i zwraca JSON albo None.
    """
    url = path if path.startswith("http") else f"{BASE}{path}"
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[ERROR] HTTP GET {url} failed: {e}")
        return None


def _parse_dt(dt_str):
    """
    Parsuje datę w formacie ISO z API.
    Obsługuje format z 'Z' (UTC) i bez.
    """
    if not dt_str:
        return None
    try:
        if dt_str.endswith("Z"):
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def _haversine_m(lat1, lon1, lat2, lon2):
    """
    Oblicza odległość (metry) między dwoma punktami na podstawie współrzędnych.
    Używane do filtrowania stacji w pobliżu miasta.
    """
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (sin(dlat / 2) ** 2 +
         cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2)
    c = 2 * asin(min(1, a ** 0.5))
    return R * c


def _valid_active_location(loc):
    """
    Sprawdza, czy stacja jest aktywna (ma pomiary w ciągu ostatnich FRESH_DAYS).
    """
    last = loc.get("datetimeLast") or {}
    last_utc = _parse_dt(last.get("utc"))
    if not last_utc:
        return False
    return (datetime.now(timezone.utc) - last_utc) <= timedelta(days=FRESH_DAYS)


def _collect_locations_for_city(city_name):
    """
    Pobiera listę stacji pomiarowych dla danego miasta.
    Zwraca kandydatów z aktywnymi sensorami i pasującymi parametrami.
    """
    cfg = CITY_CFG[city_name]
    lat, lon = cfg["coords"]
    params = {
        "iso": cfg["iso"],
        "coordinates": f"{lat},{lon}",
        "radius": cfg["radius_m"],
        "limit": 100,
        "monitor": True,
        "mobile": False
    }
    print(f"[INFO] /locations dla {city_name}")

    # Pobranie stacji w pobliżu miasta
    payload = _get_json("/locations", params=params)
    results = (payload or {}).get("results", [])

    # Jeśli za mało wyników – fallback: pobierz wszystkie stacje w kraju i filtruj po odległości
    if len(results) < 10:
        print(f"[WARN] Mało wyników, fallback na ISO={cfg['iso']}")
        merged = []
        page = 1
        while page <= 5:
            p = _get_json("/locations", params={"iso": cfg["iso"], "limit": 100, "page": page})
            rows = (p or {}).get("results", [])
            if not rows:
                break
            merged.extend(rows)
            page += 1

        filtered = []
        for loc in merged:
            c = (loc.get("coordinates") or {})
            la, lo = c.get("latitude"), c.get("longitude")
            if la is None or lo is None:
                continue
            dist = _haversine_m(lat, lon, la, lo)
            if dist <= 75000:
                loc["_distance_m"] = dist
                filtered.append(loc)
        results = sorted(filtered, key=lambda x: x.get("_distance_m", 1e12))

    # Kandydaci: stacje, które mają aktywne sensory z interesującymi parametrami
    candidates = []
    for loc in results:
        if not _valid_active_location(loc):
            continue
        sensors = loc.get("sensors") or []
        sensor_map = {}
        for s in sensors:
            sid = s.get("id")
            pinfo = (s.get("parameter") or {})
            pname = pinfo.get("name", "")
            if sid and pname:
                sensor_map[int(sid)] = {
                    "parameter": pname.lower(),
                    "unit": pinfo.get("units") or s.get("units") or s.get("unit") or ""
                }
        matches = {sid: info for sid, info in sensor_map.items() if info["parameter"] in PARAMETERS}
        if matches:
            candidates.append({
                "loc": loc,
                "sensor_map": sensor_map,
                "matches_count": len(matches)
            })

    # Sortujemy wg liczby pokrytych parametrów i zwracamy top N
    candidates.sort(key=lambda x: x["matches_count"], reverse=True)
    return candidates[:MAX_CANDIDATES]


def _latest_for_location(loc_id):
    """
    Pobiera najnowsze pomiary dla danej stacji.
    """
    payload = _get_json(f"/locations/{loc_id}/latest")
    return (payload or {}).get("results", [])


def _extract_unit(sensor_map, sid, meas):
    """
    Ekstraktuje jednostkę pomiaru – głównie z definicji sensora.
    """
    unit = (sensor_map.get(sid) or {}).get("unit")
    if unit:
        return unit
    if meas.get("unit"):
        return meas.get("unit")
    if isinstance(meas.get("value"), dict):
        return (meas.get("value") or {}).get("unit") or ""
    return ""


# Główna funkcja Cloud Function
def openaq_etl(request):
    """
    Główna funkcja uruchamiana w Google Cloud Functions.
    1. Pobiera dane z API dla Warszawy i Nowego Jorku
    2. Wybiera co najmniej 3 aktywne stacje
    3. Zapisuje dane do CSV
    4. Uploaduje plik do Google Cloud Storage
    """
    all_rows = []

    # Iteracja po dwóch miastach
    for city in ("Warsaw", "New York"):
        candidates = _collect_locations_for_city(city)
        if not candidates:
            print(f"[WARN] {city}: brak kandydatów")
            continue

        print(f"[INFO] {city}: znaleziono {len(candidates)} kandydatów")
        covered = set()
        used_locations = set()

        # Iterujemy po stacjach
        for item in candidates:
            loc = item["loc"]
            loc_id = loc.get("id")
            loc_name = loc.get("name") or loc.get("locality") or f"id:{loc_id}"
            sensor_map = item["sensor_map"]

            latest = _latest_for_location(loc_id)
            if not latest:
                continue

            city_rows_added = 0
            for meas in latest:
                # Identyfikacja sensora
                sid = meas.get("sensorsId") or meas.get("sensors_id") or meas.get("sensorId")
                try:
                    sid = int(sid) if sid is not None else None
                except Exception:
                    sid = None
                if not sid or sid not in sensor_map:
                    continue

                param = sensor_map[sid]["parameter"]
                if param not in PARAMETERS:
                    continue

                # Walidacja wartości
                value = meas.get("value")
                if value is None:
                    continue
                try:
                    float(value)
                except Exception:
                    continue

                unit = _extract_unit(sensor_map, sid, meas)
                dt = meas.get("datetime") or {}
                date_utc = dt.get("utc") or dt.get("local") or meas.get("date") or ""
                dt_parsed = _parse_dt(date_utc)
                if dt_parsed and (datetime.now(timezone.utc) - dt_parsed) > timedelta(days=FRESH_DAYS):
                    continue

                # Dodanie rekordu do listy
                all_rows.append({
                    "city": city,
                    "location": loc_name,
                    "parameter": param,
                    "value": value,
                    "unit": unit,
                    "date": date_utc
                })
                covered.add(param)
                city_rows_added += 1

            if city_rows_added > 0:
                used_locations.add(loc_id)
                print(f"[INFO] {city}: użyto stacji '{loc_name}'")

            # Jeśli mamy 3 stacje i wszystkie parametry, kończymy dla miasta
            if len(used_locations) >= 3 and covered.issuperset(PARAMETERS):
                break

        print(f"[SUMMARY] {city}: stacje={len(used_locations)}, pokryte parametry={sorted(list(covered))}")

    # Zapis do CSV
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    local_path = f"/tmp/openaq_data_{timestamp}.csv"
    try:
        with open(local_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["city", "location", "parameter", "value", "unit", "date"])
            writer.writeheader()
            writer.writerows(all_rows)
    except Exception as e:
        print(f"[ERROR] Nie udało się zapisać pliku CSV: {e}")
        return f"Błąd zapisu CSV: {e}", 500

    # Upload do GCS
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(os.path.basename(local_path))
        blob.upload_from_filename(local_path)
    except Exception as e:
        print(f"[ERROR] Upload do GCS nieudany: {e}")
        return f"Błąd uploadu do GCS: {e}", 500

    msg = f"Sukces: {len(all_rows)} pomiarów zapisano do {os.path.basename(local_path)} w bucket {BUCKET_NAME}"
    print(msg)
    if not all_rows:
        print("[WARN] Brak pobranych rekordów (stacje mogły być nieaktywne)")
    return msg
