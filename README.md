# POC Avantages Sportifs

## Objectif

L'objectif est d'évaluer la faisabilité technique d'une solution encourageant l'activité physique des salariés via des incitations financières (prime sportive) et des congés supplémentaires (jours bien-être).

Le but est de charger et valider les données RH et sportives fournies, puis d'exécuter un pipeline de transformation moderne (**ELT**) avec **dbt-core** permettant de :

- Charger les fichiers RH et sport d'origine (données brutes) directement dans PostgreSQL ;
- Simuler un historique réaliste d'activités sportives (Strava-like) sur les 12 derniers mois ;
- Valider la cohérence des trajets domicile-travail à l'aide de l'API Google Maps ;
- Exécuter les transformations et les calculs d'impact financier en SQL natif avec dbt ;
- Exporter les indicateurs et tables calculés (format CSV/JSON) prêts pour Power BI.

---

## Données fournies

Les fichiers sources utilisés par le projet sont :

- `Donnees+RH.csv` : informations RH des salariés ;
- `Donnees+Sportive.csv` : pratiques sportives déclarées ;
- `Note+de+cadrage+_+POC+Avantages+Sportifs+(1).pdf` : cadrage fonctionnel du projet.

Les fichiers de données ne sont pas versionnés dans Git afin de protéger les données RH (exclus via le fichier `.gitignore`).

---

## Structure actuelle

```text
.
├── dbt_avantages_sportifs/   # Projet dbt pour les transformations SQL
│   ├── dbt_project.yml       # Configuration principale dbt
│   ├── profiles.yml          # Connexion PostgreSQL (Jinja + .env)
│   └── models/               # Modèles SQL (Staging et Finance)
├── scripts/
│   ├── init_db.py            # Initialisation et chargement brut PostgreSQL
│   ├── simulate_strava.py    # Simulation d'activités Strava et export CSV
│   ├── calculate_distances.py# Validation des distances avec l'API Google Maps
│   ├── notify_slack.py       # Notifications Slack des activités individuelles
│   ├── notify_pipeline.py    # Notification Slack de résumé final du pipeline
│   ├── validate_data_gx.py   # Validation de qualité de données Great Expectations
│   └── export_dbt_outputs.py # Export des calculs dbt (CSV/JSON) pour Power BI
├── kestra/
│   └── analyse_donnees.yml   # Workflow d'orchestration Kestra
├── docs/
│   └── tests_qualite_donnees.md
├── test_analyse_donnees.py   # Tests unitaires du projet
├── test_slack.py             # Tests unitaires des notifications Slack
├── requirements.txt          # Dépendances Python du projet
├── .env.template             # Modèle de configuration des variables d'environnement
└── README.md
```

---

## Installation

Créer et activer un environnement virtuel :

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Installer les dépendances :

```powershell
pip install -r requirements.txt
```

---

## Configuration

Copier le fichier `.env.template` en `.env`, puis renseigner la clé Google Maps et les informations de notre base de données locale PostgreSQL :

```text
GOOGLE_MAPS_API_KEY="TA_CLE_API_GOOGLE"
SLACK_WEBHOOK_URL="URL_DU_WEBHOOK_SLACK"

POSTGRES_USER="postgres"
POSTGRES_PASSWORD="VotreMotDePasse"
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"
POSTGRES_DB="sport_data_solution"
```

Sans clé API Google Maps, le script peut s'exécuter, mais la validation automatique des distances ne sera pas active (le cache local `google_maps_cache.json` sera utilisé s'il contient déjà les adresses).

Les tables d'ingestion brutes et de calculs gérées dans PostgreSQL sont :
- `raw_rh_employes` (données RH brutes)
- `raw_sport_employes` (sports déclarés bruts)
- `raw_activites_sportives` (activités simulées brutes)
- `raw_validation_distances` (retours d'API Google Maps)
- `fct_calcul_finance` (table finale calculée par dbt)

---

## Lancer Kestra

Le workflow `kestra/analyse_donnees.yml` monte ce projet dans les conteneurs Python sous le chemin `/workspace`. Kestra doit donc être lancé avec les montages Docker activés :

```powershell
docker run -d --name projet12-kestra `
  -p 8081:8080 `
  -v projet12_kestra_data:/app/storage `
  -v /var/run/docker.sock:/var/run/docker.sock `
  -v /tmp:/tmp `
  -e KESTRA_TASKS_SCRIPTS_DOCKER_VOLUME_ENABLED=true `
  --user root `
  kestra/kestra:latest server local
```

Après modification de `kestra/analyse_donnees.yml`, importez à nouveau le workflow dans l'interface Kestra avant de relancer l'exécution.

---

## Lancer l'analyse (Pipeline ELT)

Pour exécuter le pipeline d'analyse complet en local :

1. Charger les données brutes dans PostgreSQL :
```powershell
python scripts/init_db.py
```

2. Générer les activités Strava simulées :
```powershell
python scripts/simulate_strava.py
```

3. Valider les distances domicile-travail :
```powershell
python scripts/calculate_distances.py
```

4. Exécuter les transformations dbt :
```powershell
cd dbt_avantages_sportifs
dbt run --profiles-dir .
cd ..
```

5. Exporter les calculs financiers dbt pour Power BI :
```powershell
python scripts/export_dbt_outputs.py
```

---

## Lancer les tests

```powershell
python -m unittest -v
```

Les tests vérifient actuellement :
- Les règles métiers de distance Google Maps (seuils de 15 km et 25 km) ;
- Le signalement automatique d'un trajet marche/running trop long ;
- La validité et la structure des fichiers de sortie exportés par dbt pour Power BI ;
- Le bon formatage des notifications Slack.

---

## Règles métier couvertes

La note de cadrage demande de vérifier la cohérence des modes de déplacement déclarés avec la distance réelle domicile-travail.

Règles implémentées pour cette étape :
- **Marche / Running** : distance maximale autorisée de **15 km** ;
- **Vélo / Trottinette / Autres** : distance maximale autorisée de **25 km** ;
- Adresse de l'entreprise : `1362 Av. des Platanes, 34970 Lattes, France`.

---

## Prochaines étapes de production

- Industrialiser le schéma PostgreSQL avec des migrations SQL versionnées (ex. Flyway, Liquibase).
- Activer l'architecture streaming temps réel avec Debezium et Redpanda (prévus dans le docker-compose) pour capturer les événements Strava à la volée.
- Brancher les fichiers générés dans `outputs/` ou les tables PostgreSQL finales directement sur nos rapports de visualisation Power BI.
