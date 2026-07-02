import os
import json
import requests
import time
import sys
from kafka import KafkaConsumer
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from pathlib import Path

# Configurer la sortie standard pour un affichage en temps réel sans tampon (buffering)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

def get_postgres_engine():
    host = os.getenv("POSTGRES_HOST", "localhost")
    return create_engine(
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@"
        f"{host}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )

def load_employee_cache():
    engine = get_postgres_engine()
    cache = {}
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT TRIM(id_salarie) as id, prenom, nom FROM rh_employes"))
            for row in result:
                cache[row.id] = (row.prenom, row.nom)
        print(f"Cache de {len(cache)} salariés chargé avec succès.")
    except Exception as e:
        print(f"Avertissement: Impossible de charger le cache des salariés ({e}).")
    return cache

def main():
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("SLACK_WEBHOOK_URL non configuré, le consommateur s'arrête.")
        return

    # Charger le dictionnaire des noms des employés
    employees = load_employee_cache()

    print("Connexion à Redpanda en tant que consommateur Slack...")
    consumer = None
    for i in range(15):
        try:
            consumer = KafkaConsumer(
                "postgres.public.activites_sportives",
                bootstrap_servers=["localhost:9092"],
                auto_offset_reset="latest",
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                consumer_timeout_ms=10000000000000000000 # Très grand timeout pour écouter indéfiniment
            )
            print("Connecté à Redpanda sur le topic postgres.public.activites_sportives !")
            break
        except Exception as e:
            print(f"Tentative {i+1}/15 échouée: Redpanda pas encore disponible ({e})...")
            time.sleep(3)
    else:
        print("Impossible de se connecter à Redpanda. Arrêt du script.")
        return

    print("Écoute des nouvelles activités sportives en cours...")
    try:
        for message in consumer:
            val = message.value
            if not val or "payload" not in val:
                continue

            payload = val["payload"]
            op = payload.get("op")
            after = payload.get("after")

            # CDC operations: 'c' (create) or 'u' (update)
            if op in ["c", "u"] and after:
                id_salarie = str(after.get("id_salarie", "")).strip()
                sport_type = after.get("sport_type", "")
                
                try:
                    distance_m = float(after.get("distance_m", 0))
                    temps_ecoule_s = float(after.get("temps_ecoule_s", 0))
                except (ValueError, TypeError):
                    distance_m = 0
                    temps_ecoule_s = 0

                prenom, nom = employees.get(id_salarie, ("Salarié", id_salarie))

                distance_km = round(distance_m / 1000, 1)
                temps_min = round(temps_ecoule_s / 60)

                slack_payload = {
                    "text": (
                        f"Bravo {prenom} {nom} !\n"
                        f"Tu viens de réaliser {distance_km} km en {temps_min} min.\n"
                        f"Sport : {sport_type}\n"
                        "Quelle énergie !"
                    )
                }

                try:
                    res = requests.post(webhook_url, json=slack_payload, timeout=10)
                    res.raise_for_status()
                    print(f"Notification Slack envoyée en temps réel pour {prenom} {nom} ({sport_type})")
                except Exception as e:
                    print(f"Erreur d'envoi Slack : {e}")

    except KeyboardInterrupt:
        print("Consommateur arrêté manuellement.")
    finally:
        if consumer:
            consumer.close()

if __name__ == "__main__":
    main()
