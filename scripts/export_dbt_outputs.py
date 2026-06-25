import os
import json
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = BASE_DIR / "outputs"

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
    load_dotenv(BASE_DIR / ".env")
    
    try:
        working_days = int(os.getenv("WORKING_DAYS_PER_YEAR", 251))
    except ValueError:
        working_days = 251

    # 1. Lire la table finale fct_calcul_finance de dbt
    df_finance = pd.read_sql("SELECT * FROM fct_calcul_finance", engine)

    # 2. Exporter le CSV détaillé pour Power BI
    OUTPUTS_DIR.mkdir(exist_ok=True)
    csv_path = OUTPUTS_DIR / "donnees_financieres.csv"
    df_finance.to_csv(csv_path, sep=";", index=False, encoding="utf-8")
    print(f"Fichier CSV exporté : {csv_path}")

    # 3. Calculer les métriques globales pour la synthèse JSON
    effectif_total = len(df_finance)
    masse_salariale_totale = df_finance["salaire_brut"].sum()
    
    # Nb sportifs déclarés (ayant au moins une activité ou sport renseigné dans sport_employes)
    # On peut le lire de la base de données directement
    try:
        sportifs_count = pd.read_sql("SELECT COUNT(DISTINCT id_salarie) as count FROM stg_sport_employes", engine).iloc[0]["count"]
    except Exception:
        sportifs_count = len(df_finance[df_finance["nb_activites_sportives"] > 0])
        
    prime_df = df_finance[df_finance["eligible_prime"]]
    nb_eligibles_prime = len(prime_df)
    masse_salariale_eligibles_prime = prime_df["salaire_brut"].sum()
    cout_total_prime = prime_df["montant_prime"].sum()
    
    wb_df = df_finance[df_finance["eligible_jours_bien_etre"]]
    nb_eligibles_wb = len(wb_df)
    cout_total_wb = wb_df["cout_jours_bien_etre"].sum()
    
    cout_global = cout_total_prime + cout_total_wb
    
    summary = {
        "metriques_globales": {
            "effectif_total": int(effectif_total),
            "masse_salariale_totale": round(float(masse_salariale_totale), 2),
            "nb_sportifs_declares": int(sportifs_count)
        },
        "prime_sportive": {
            "taux_prime": 0.05,
            "nb_eligibles": int(nb_eligibles_prime),
            "masse_salariale_eligibles": round(float(masse_salariale_eligibles_prime), 2),
            "cout_total_annuel": round(float(cout_total_prime), 2)
        },
        "jours_bien_etre": {
            "nb_jours_accordes": 5,
            "seuil_activites_annuel": 15,
            "jours_ouvres_an": int(working_days),
            "nb_eligibles": int(nb_eligibles_wb),
            "cout_total_annuel": round(float(cout_total_wb), 2)
        },
        "synthese_financiere": {
            "impact_financier_total_annuel": round(float(cout_global), 2),
            "pourcentage_masse_salariale": round((float(cout_global) / float(masse_salariale_totale)) * 100, 2) if masse_salariale_totale > 0 else 0.0
        }
    }

    # 4. Écrire le fichier JSON de synthèse
    json_path = OUTPUTS_DIR / "impact_financier.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fichier JSON de synthèse financière écrit : {json_path}")
    
    # 5. Mettre à jour resume_analyse.json pour la compatibilité Slack
    # notify_slack.py lit outputs/resume_analyse.json pour envoyer son rapport
    resume_path = OUTPUTS_DIR / "resume_analyse.json"
    if resume_path.exists():
        try:
            resume = json.loads(resume_path.read_text(encoding="utf-8"))
            resume["fusion"] = {
                "nb_total": int(effectif_total),
                "avec_sport": int(sportifs_count),
                "sans_sport": int(effectif_total - sportifs_count)
            }
            resume_path.write_text(json.dumps(resume, ensure_ascii=False, indent=2), encoding="utf-8")
            print("Fichier outputs/resume_analyse.json mis à jour pour Slack.")
        except Exception as e:
            print(f"Erreur lors de la mise à jour de resume_analyse.json : {e}")

    print("\n--- Export dbt pour Power BI Réussi ---")
    print(f"Coût Prime Sportive (5%) : {cout_total_prime:,.2f} €")
    print(f"Coût Jours Bien-être : {cout_total_wb:,.2f} €")
    print(f"Impact Financier Global : {cout_global:,.2f} €")

if __name__ == "__main__":
    main()
