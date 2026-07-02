import os
from random import randint, uniform, choice
import pandas as pd
from dotenv import load_dotenv
from faker import Faker
from sqlalchemy import create_engine, text
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = BASE_DIR / "outputs"

# Requêter les tables d'ingestion brute
QUERY_EMPLOYEES_WITH_SPORT = """
SELECT
    rh.id_salarie,
    sp.pratique_sport
FROM rh_employes rh
JOIN sport_employes sp
    ON TRIM(rh.id_salarie) = TRIM(sp.id_salarie)
WHERE sp.pratique_sport IS NOT NULL AND TRIM(sp.pratique_sport) != ''
"""

SPORT_TO_STRAVA = {
    "Runing": "Run",
    "Triathlon": "Run",
    "Tennis": "Run",
    "Badminton": "Run",
    "Tennis de table": "Run",
    "Football": "Run",
    "Rugby": "Run",
    "Basketball": "Run",
    "Judo": "Walk",
    "Boxe": "Walk",
    "Randonnée": "Hike",
    "Escalade": "Hike",
    "Équitation": "Hike",
    "Natation": "Swim",
    "Voile": "Swim"
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

def build_activities(employees):
    fake = Faker("fr_FR")
    db_activities = []
    csv_activities = []

    for _, row in employees.iterrows():
        emp_id = str(row["id_salarie"]).strip()
        declared_sport = str(row["pratique_sport"]).strip()
        strava_type = SPORT_TO_STRAVA.get(declared_sport, "Run")

        # Générer entre 15 et 60 activités par salarié sur l'année
        for _ in range(randint(15, 60)):
            activity_id = fake.uuid4()
            start_time = fake.date_time_between(start_date="-12M", end_date="now")
            
            # Paramètres de distance et temps réalistes
            if strava_type == "Ride":
                dist_km = round(uniform(5.0, 50.0), 2)
                duration_min = randint(20, 150)
            elif strava_type == "Swim":
                dist_km = round(uniform(0.5, 3.0), 2)
                duration_min = randint(15, 90)
            elif strava_type == "Hike":
                dist_km = round(uniform(3.0, 25.0), 2)
                duration_min = randint(60, 240)
            else:  # Run, Walk
                dist_km = round(uniform(2.0, 15.0), 2)
                duration_min = randint(15, 90)
                
            dist_m = int(dist_km * 1000)
            duration_sec = int(duration_min * 60)
            
            # Données brutes pour la base de données
            db_activities.append({
                "id_salarie": emp_id,
                "date_debut": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "sport_type": declared_sport,
                "distance_m": str(dist_m),
                "temps_ecoule_s": str(duration_sec),
                "commentaire": ""
            })
            
            # Données pour le CSV Strava (tel qu'attendu par Great Expectations)
            csv_activities.append({
                "activity_id": activity_id,
                "employee_id": int(emp_id),
                "activity_date": start_time.strftime("%Y-%m-%d"),
                "activity_type": strava_type,
                "distance_km": dist_km,
                "duration_minutes": duration_min,
                "source": "faker_strava"
            })

    return pd.DataFrame(db_activities), pd.DataFrame(csv_activities)

def main():
    engine = get_postgres_engine()
    
    # 1. S'assurer de la présence de la table brute
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS activites_sportives (
        id SERIAL PRIMARY KEY,
        id_salarie TEXT,
        date_debut TEXT,
        sport_type TEXT,
        distance_m TEXT,
        temps_ecoule_s TEXT,
        commentaire TEXT
    );
    """
    with engine.begin() as conn:
        conn.execute(text(create_table_sql))
        
    employees = pd.read_sql(QUERY_EMPLOYEES_WITH_SPORT, engine)
    
    if employees.empty:
        print("Aucun salarié sportif trouvé dans sport_employes.")
        return
        
    db_df, csv_df = build_activities(employees)

    # 2. Ingestion brute dans PostgreSQL (TRUNCATE désactivé pour la démo live)
    # with engine.begin() as conn:
    #     conn.execute(text("TRUNCATE TABLE activites_sportives;"))
        
    db_df.to_sql(
        "activites_sportives",
        engine,
        if_exists="append",
        index=False,
    )
    print(f"{len(db_df)} activités brutes chargées dans PostgreSQL (table activites_sportives).")

    # 3. Écriture CSV unifié pour Power BI / Great Expectations
    OUTPUTS_DIR.mkdir(exist_ok=True)
    csv_path = OUTPUTS_DIR / "activites_strava_simulees.csv"
    csv_df.to_csv(csv_path, sep=";", index=False, encoding="utf-8")
    print(f"Fichier CSV de simulation unifié écrit dans : {csv_path}")

if __name__ == "__main__":
    main()
