import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

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

def main():
    engine = get_postgres_engine()
    
    # 1. Création des tables brutes si elles n'existent pas
    create_tables_sql = """
    CREATE TABLE IF NOT EXISTS raw_rh_employes (
        id_salarie TEXT PRIMARY KEY,
        nom TEXT,
        prenom TEXT,
        date_naissance TEXT,
        bu TEXT,
        date_embauche TEXT,
        salaire_brut TEXT,
        type_contrat TEXT,
        nb_jours_cp TEXT,
        adresse_domicile TEXT,
        moyen_deplacement TEXT
    );

    CREATE TABLE IF NOT EXISTS raw_sport_employes (
        id_salarie TEXT PRIMARY KEY,
        pratique_sport TEXT
    );
    """
    with engine.begin() as conn:
        conn.execute(text(create_tables_sql))
        print("Tables brutes vérifiées/créées.")

    # 2. Lecture et insertion brute de Données+RH.csv
    rh_csv = BASE_DIR / "Données+RH.csv"
    if rh_csv.exists():
        df_rh = pd.read_csv(rh_csv, sep=";")
        df_rh.columns = [col.strip().replace("\ufeff", "") for col in df_rh.columns]
        
        # Nettoyage des IDs pour éviter le format float (ex. "59019.0")
        df_rh = df_rh.dropna(subset=["ID salarié"])
        df_rh["id_salarie"] = pd.to_numeric(df_rh["ID salarié"], errors="coerce").astype(int).astype(str)

        # Mappage des autres colonnes
        column_mapping = {
            "Nom": "nom",
            "Prénom": "prenom",
            "Date de naissance": "date_naissance",
            "BU": "bu",
            "Date d'embauche": "date_embauche",
            "Salaire brut": "salaire_brut",
            "Type de contrat": "type_contrat",
            "Nombre de jours de CP": "nb_jours_cp",
            "Adresse du domicile": "adresse_domicile",
            "Moyen de déplacement": "moyen_deplacement",
        }
        for csv_col, db_col in column_mapping.items():
            df_rh[db_col] = df_rh[csv_col].astype(str).str.strip()
            
        # Sélectionner les colonnes finales
        df_rh = df_rh[["id_salarie"] + list(column_mapping.values())]

        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE raw_rh_employes CASCADE;"))
            
        df_rh.to_sql("raw_rh_employes", engine, if_exists="append", index=False)
        print(f"Importation brute de {len(df_rh)} salariés dans raw_rh_employes réussie.")
    else:
        print("rh_clean.csv introuvable.")

    # 3. Lecture et insertion brute de Données+Sportive.csv
    sport_csv = BASE_DIR / "Données+Sportive.csv"
    if sport_csv.exists():
        df_sport = pd.read_csv(sport_csv, sep=";")
        df_sport.columns = [col.strip().replace("\ufeff", "") for col in df_sport.columns]
        
        # Nettoyer les IDs (conversion float -> int -> str)
        df_sport = df_sport.dropna(subset=["ID salarié"])
        df_sport["id_salarie"] = pd.to_numeric(df_sport["ID salarié"], errors="coerce").astype(int).astype(str)
        df_sport["pratique_sport"] = df_sport["Pratique d'un sport"].astype(str).str.strip()
        
        # Filtrer les valeurs manquantes ou 'nan'
        df_sport = df_sport[df_sport["pratique_sport"].notna() & 
                            (df_sport["pratique_sport"] != "") & 
                            (df_sport["pratique_sport"] != "nan") & 
                            (df_sport["pratique_sport"] != "None")]

        df_sport = df_sport[["id_salarie", "pratique_sport"]]
        
        # Supprimer les doublons potentiels d'IDs
        df_sport = df_sport.drop_duplicates(subset=["id_salarie"])

        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE raw_sport_employes CASCADE;"))
            
        df_sport.to_sql("raw_sport_employes", engine, if_exists="append", index=False)
        print(f"Importation brute de {len(df_sport)} salariés sportifs dans raw_sport_employes réussie.")
    else:
        print("sport_clean.csv introuvable.")

if __name__ == "__main__":
    main()
