import time
import requests
import json
import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DEBEZIUM_URL = "http://localhost:8083/connectors"

# Vérifier que toutes les variables de connexion requises sont définies dans le .env
required_vars = ["POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"]
missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    raise RuntimeError(f"Variables d'environnement requises manquantes dans le fichier .env : {', '.join(missing)}")

db_host = os.getenv("POSTGRES_HOST")
if db_host in ["localhost", "127.0.0.1"]:
    db_host = "host.docker.internal"

CONNECTOR_CONFIG = {
    "name": "postgres-connector",
    "config": {
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "tasks.max": "1",
        "database.hostname": db_host,
        "database.port": os.getenv("POSTGRES_PORT"),
        "database.user": os.getenv("POSTGRES_USER"),
        "database.password": os.getenv("POSTGRES_PASSWORD"),
        "database.dbname": os.getenv("POSTGRES_DB"),
        "topic.prefix": "postgres",
        "table.include.list": "public.activites_sportives",
        "plugin.name": "pgoutput",
        "decimal.handling.mode": "double"
    }
}

def mask_sensitive_data(data):
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            if k == "database.password":
                masked[k] = "*****"
            elif isinstance(v, (dict, list)):
                masked[k] = mask_sensitive_data(v)
            else:
                masked[k] = v
        return masked
    elif isinstance(data, list):
        return [mask_sensitive_data(x) for x in data]
    return data

def main():
    print("Attente du démarrage de Debezium Connect...")
    for i in range(30):
        try:
            res = requests.get("http://localhost:8083/", timeout=5)
            if res.status_code == 200:
                print("Debezium est prêt !")
                break
        except requests.RequestException:
            pass
        time.sleep(2)
    else:
        print("Erreur : Debezium n'a pas démarré après 60 secondes.")
        return

    # Vérifier si le connecteur existe déjà
    try:
        existing = requests.get(f"{DEBEZIUM_URL}/postgres-connector", timeout=5)
        if existing.status_code == 200:
            print("Le connecteur 'postgres-connector' existe déjà. Réenregistrement...")
            requests.delete(f"{DEBEZIUM_URL}/postgres-connector", timeout=5)
            time.sleep(2)
    except requests.RequestException as e:
        print(f"Erreur de vérification du connecteur : {e}")

    # Enregistrer le connecteur
    try:
        headers = {"Content-Type": "application/json"}
        response = requests.post(DEBEZIUM_URL, data=json.dumps(CONNECTOR_CONFIG), headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            print("Connecteur Debezium enregistré avec succès !")
            masked_resp = mask_sensitive_data(response.json())
            print(json.dumps(masked_resp, indent=2))
        else:
            print(f"Erreur lors de l'enregistrement du connecteur ({response.status_code}) :")
            try:
                masked_err = mask_sensitive_data(response.json())
                print(json.dumps(masked_err, indent=2))
            except Exception:
                print(response.text)
    except requests.RequestException as e:
        print(f"Erreur de connexion à Debezium : {e}")

if __name__ == "__main__":
    main()
