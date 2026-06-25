import os

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine


QUERY_RECENT_ACTIVITIES = """
SELECT
    rh.nom,
    rh.prenom,
    a.sport_type,
    a.distance_m,
    a.temps_ecoule_s
FROM stg_activites_sportives a
JOIN stg_rh_employes rh
    ON a.id_salarie = rh.id_salarie
ORDER BY RANDOM()
LIMIT 3
"""


def get_postgres_engine():
    load_dotenv()
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


def build_message(activity):
    distance_km = round(activity["distance_m"] / 1000, 1)
    temps_min = round(activity["temps_ecoule_s"] / 60)

    return {
        "text": (
            f"Bravo {activity['prenom']} {activity['nom']} !\n"
            f"Tu viens de realiser {distance_km} km en {temps_min} min.\n"
            f"Sport : {activity['sport_type']}\n"
            "Quelle energie !"
        )
    }


def main():
    load_dotenv()
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("SLACK_WEBHOOK_URL non defini: notifications d'activites ignorees.")
        return

    engine = get_postgres_engine()
    activities = pd.read_sql(QUERY_RECENT_ACTIVITIES, engine)

    for _, activity in activities.iterrows():
        response = requests.post(webhook_url, json=build_message(activity), timeout=15)
        response.raise_for_status()
        print(f"Notification activite envoyee: {response.status_code}")


if __name__ == "__main__":
    main()
