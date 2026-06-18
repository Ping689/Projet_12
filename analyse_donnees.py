import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def load_env_file(path):
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return

    load_dotenv(path)


load_env_file(BASE_DIR / ".env")
RH_FILE = BASE_DIR / "Données+RH.csv"
SPORT_FILE = BASE_DIR / "Données+Sportive.csv"
COMPANY_ADDRESS = "1362 Av. des Platanes, 34970 Lattes, France"
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
CACHE_FILE = BASE_DIR / "google_maps_cache.json"
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


def read_csv(path):
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k is not None}
            for row in reader
        ]


def summarize_rh(rows):
    transports = Counter()
    contrats = Counter()
    bu = Counter()
    salary_missing = 0
    for row in rows:
        transports[row.get("Moyen de déplacement", "").strip()] += 1
        contrats[row.get("Type de contrat", "").strip()] += 1
        bu[row.get("BU", "").strip()] += 1
        if not row.get("Salaire brut", "").strip():
            salary_missing += 1
    return {
        "nb_salaires": len(rows),
        "transports": transports,
        "contrats": contrats,
        "business_units": bu,
        "salary_missing": salary_missing,
    }


def summarize_sport(rows):
    sports = Counter()
    no_sport = 0
    for row in rows:
        sport = row.get("Pratique d'un sport", "").strip()
        if sport:
            sports[sport] += 1
        else:
            no_sport += 1
    return {
        "nb_lignes": len(rows),
        "sports": sports,
        "no_sport_declared": no_sport,
    }


def merge_data(rh_rows, sport_rows):
    sport_by_id = {row["ID salarié"].strip(): row for row in sport_rows}
    merged = []
    for row in rh_rows:
        sid = row.get("ID salarié", "").strip()
        sport_row = sport_by_id.get(sid, {})
        merged.append({
            **row,
            "Pratique d'un sport": sport_row.get("Pratique d'un sport", ""),
        })
    return merged


def analyse_merge(merged_rows):
    count_with_sport = sum(1 for row in merged_rows if row.get("Pratique d'un sport", "").strip())
    count_without_sport = len(merged_rows) - count_with_sport
    transports_sportifs = Counter()
    for row in merged_rows:
        if row.get("Pratique d'un sport", "").strip():
            transports_sportifs[row.get("Moyen de déplacement", "").strip()] += 1
    return {
        "nb_total": len(merged_rows),
        "avec_sport": count_with_sport,
        "sans_sport": count_without_sport,
        "transports_sportifs": transports_sportifs,
    }


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


def fetch_distance_matrix(origin, mode="driving"):
    if not GOOGLE_MAPS_API_KEY:
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
        "key": GOOGLE_MAPS_API_KEY,
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


def validate_commute(origin, deplacement):
    origin = origin.strip()
    if not origin:
        return {"status": "NO_ORIGIN", "mode": None, "suspicious": False}
    mode = get_google_maps_mode(deplacement)
    cache = load_cache()
    cache_key = f"{origin}|{mode}"
    if cache_key in cache and not (
        GOOGLE_MAPS_API_KEY and cache[cache_key].get("status") == "NO_API_KEY"
    ):
        result = cache[cache_key]
    else:
        result = fetch_distance_matrix(origin, mode=mode)
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


def print_counter(title, counter, top_n=20):
    print(title)
    for value, count in counter.most_common(top_n):
        print(f"  {value or '(vide)'}: {count}")
    print()


if __name__ == "__main__":
    rh_rows = read_csv(RH_FILE)
    sport_rows = read_csv(SPORT_FILE)

    print("=== Résumé Données RH ===")
    rh_summary = summarize_rh(rh_rows)
    print(f"Lignes RH: {rh_summary['nb_salaires']}")
    print(f"Salaires manquants: {rh_summary['salary_missing']}")
    print_counter("BU", rh_summary["business_units"])
    print_counter("Type de contrat", rh_summary["contrats"])
    print_counter("Moyens de déplacement", rh_summary["transports"])

    print("=== Résumé Données Sportives ===")
    sport_summary = summarize_sport(sport_rows)
    print(f"Lignes sportives: {sport_summary['nb_lignes']}")
    print(f"Salariés sans pratique déclarée: {sport_summary['no_sport_declared']}")
    print_counter("Activités sportives déclarées", sport_summary["sports"])

    merged_rows = merge_data(rh_rows, sport_rows)
    merged_summary = analyse_merge(merged_rows)
    print("=== Résumé après merge RH + sport ===")
    print(f"Salariés au total: {merged_summary['nb_total']}")
    print(f"Salariés avec sport déclaré: {merged_summary['avec_sport']}")
    print(f"Salariés sans sport déclaré: {merged_summary['sans_sport']}")
    print_counter("Transports des salariés sportifs", merged_summary["transports_sportifs"])

    print("=== Validation des déplacements domicile -> entreprise ===")
    if not GOOGLE_MAPS_API_KEY:
        print("Attention : la variable d'environnement GOOGLE_MAPS_API_KEY n'est pas définie.")
        print("Configure une clé Google Maps pour activer la validation des distances.")
    else:
        total_validated = 0
        suspicious_results = []
        for row in rh_rows:
            validation = validate_commute(row.get("Adresse du domicile", ""), row.get("Moyen de déplacement", ""))
            if validation["status"] == "OK":
                total_validated += 1
            if validation["suspicious"]:
                suspicious_results.append({
                    "id": row.get("ID salarié", ""),
                    "nom": row.get("Nom", ""),
                    "prenom": row.get("Prénom", ""),
                    "deplacement": row.get("Moyen de déplacement", ""),
                    "adresse": row.get("Adresse du domicile", ""),
                    "distance_km": validation["distance_km"],
                    "distance_text": validation["distance_text"],
                })
        print(f"Trajets validés avec Google Maps : {total_validated}/{len(rh_rows)}")
        print(f"Trajets potentiellement incohérents : {len(suspicious_results)}")
        for item in suspicious_results[:10]:
            print(f"  {item['id']} {item['nom']} {item['prenom']} - {item['deplacement']} - {item['distance_text']} ({item['adresse']})")
