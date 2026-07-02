import os
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = BASE_DIR / "outputs"
CACHE_FILE = BASE_DIR / "google_maps_cache.json"

COMPANY_ADDRESS = "1362 Av. des Platanes, 34970 Lattes, France"
MODE_MAP = {
    "Marche/running": "walking",
    "Vélo/Trottinette/Autres": "bicycling",
    "Transports en commun": "transit",
    "véhicule thermique/électrique": "driving",
}
VALIDATION_THRESHOLDS = {
    "walking": 15,
    "bicycling": 25,
}

def get_postgres_engine():
    load_dotenv(BASE_DIR / ".env")
    required_vars = [
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
    ]
    missing = [name for name in required_vars if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Variables PostgreSQL manquantes: {', '.join(missing)}")

    host = os.getenv("POSTGRES_HOST")
    if (host == "localhost" or host == "127.0.0.1") and (os.path.exists("/.dockerenv") or os.getenv("KESTRA_EXECUTION_ID")):
        host = "host.docker.internal"

    return create_engine(
        "postgresql+psycopg2://"
        f"{os.getenv('POSTGRES_USER')}:"
        f"{os.getenv('POSTGRES_PASSWORD')}@"
        f"{host}:"
        f"{os.getenv('POSTGRES_PORT')}/"
        f"{os.getenv('POSTGRES_DB')}"
    )

def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}

def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def get_google_maps_mode(deplacement):
    return MODE_MAP.get(deplacement.strip(), "driving")

def fetch_distance_matrix(origin, mode="driving", api_key=None):
    if not api_key:
        return {
            "status": "NO_API_KEY",
            "distance_meters": None,
            "duration_seconds": None,
            "distance_text": None,
            "duration_text": None,
            "mode": mode,
        }
    params = {
        "origins": origin,
        "destinations": COMPANY_ADDRESS,
        "mode": mode,
        "key": api_key,
    }
    if mode == "transit":
        params["departure_time"] = int(time.time())
    url = "https://maps.googleapis.com/maps/api/distancematrix/json?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {
            "status": f"HTTP_{exc.code}",
            "distance_meters": None,
            "duration_seconds": None,
            "distance_text": None,
            "duration_text": None,
            "mode": mode,
        }
    except urllib.error.URLError as exc:
        return {
            "status": f"NETWORK_ERROR: {exc.reason}",
            "distance_meters": None,
            "duration_seconds": None,
            "distance_text": None,
            "duration_text": None,
            "mode": mode,
        }
    status = payload.get("status")
    if status != "OK":
        return {
            "status": status,
            "distance_meters": None,
            "duration_seconds": None,
            "distance_text": None,
            "duration_text": None,
            "mode": mode,
        }
    element = payload["rows"][0]["elements"][0]
    if element.get("status") != "OK":
        return {
            "status": element.get("status"),
            "distance_meters": None,
            "duration_seconds": None,
            "distance_text": None,
            "duration_text": None,
            "mode": mode,
        }
    distance = element["distance"]
    duration = element["duration"]
    return {
        "status": "OK",
        "distance_meters": distance["value"],
        "duration_seconds": duration["value"],
        "distance_text": distance["text"],
        "duration_text": duration["text"],
        "mode": mode,
    }

def validate_commute(origin, deplacement, api_key):
    origin = origin.strip()
    if not origin:
        return {"status": "NO_ORIGIN", "mode": None, "suspicious": False, "distance_meters": None, "distance_text": None, "duration_text": None}
    mode = get_google_maps_mode(deplacement)
    cache = load_cache()
    cache_key = f"{origin}|{mode}"
    
    if cache_key in cache and not (api_key and cache[cache_key].get("status") == "NO_API_KEY"):
        result = cache[cache_key]
    else:
        result = fetch_distance_matrix(origin, mode=mode, api_key=api_key)
        if not str(result["status"]).startswith(("HTTP_", "NETWORK_ERROR")):
            cache[cache_key] = result
            save_cache(cache)
        time.sleep(0.2)
        
    distance_km = None
    suspicious = False
    if result["distance_meters"] is not None:
        distance_km = result["distance_meters"] / 1000.0
        threshold = VALIDATION_THRESHOLDS.get(mode)
        if threshold is not None and distance_km > threshold:
            suspicious = True
            
    return {
        "status": result["status"],
        "mode": mode,
        "distance_km": distance_km,
        "distance_text": result["distance_text"],
        "duration_text": result["duration_text"],
        "suspicious": suspicious,
    }

def main():
    engine = get_postgres_engine()
    load_dotenv(BASE_DIR / ".env")
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    
    # S'assurer de la présence de la table brute dans PostgreSQL
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS validation_distances (
        id_salarie TEXT,
        distance_km NUMERIC,
        status TEXT,
        mode TEXT,
        suspicious BOOLEAN
    );
    """
    with engine.begin() as conn:
        conn.execute(text(create_table_sql))

    # Lire les salariés depuis rh_employes
    df_rh = pd.read_sql("SELECT id_salarie, adresse_domicile, moyen_deplacement FROM rh_employes", engine)
    
    results_json = []
    results_db = []

    for _, row in df_rh.iterrows():
        emp_id = str(row["id_salarie"]).strip()
        adresse = str(row["adresse_domicile"]).strip()
        deplacement = str(row["moyen_deplacement"]).strip()
        
        validation = validate_commute(adresse, deplacement, api_key)
        
        results_json.append({
            "id_salarie": emp_id,
            "mode_deplacement": deplacement,
            "adresse": adresse,
            **validation
        })
        
        results_db.append({
            "id_salarie": emp_id,
            "distance_km": validation["distance_km"],
            "status": validation["status"],
            "mode": validation["mode"],
            "suspicious": validation["suspicious"]
        })

    # Écrire validation_distances.json
    OUTPUTS_DIR.mkdir(exist_ok=True)
    output_path = OUTPUTS_DIR / "validation_distances.json"
    output_path.write_text(json.dumps(results_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fichier validation_distances.json écrit : {output_path}")

    # Charger les résultats de validation dans PostgreSQL
    df_db = pd.DataFrame(results_db)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE validation_distances;"))
    df_db.to_sql("validation_distances", engine, if_exists="append", index=False)
    print(f"Chargement de {len(df_db)} validations dans PostgreSQL (table validation_distances).")

if __name__ == "__main__":
    main()
