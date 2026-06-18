# POC Avantages Sportifs

## Objectif

L'objectif est d'évaluer la faisabilité technique d'une solution encourageant l'activité physique des salariés via des incitations financières et des congés supplémentaires

Le but est de verifier les donnees RH et sportives fournies, puis de produire une premiere analyse permettant de :

- lire les fichiers RH et sport ;
- resumer les donnees principales ;
- fusionner les informations RH avec les pratiques sportives declarees ;
- verifier certaines regles de qualite liees aux deplacements domicile -> entreprise.

## Donnees fournies

Les fichiers sources utilises par le script sont :

- `Donnees+RH.csv` : informations RH des salaries ;
- `Donnees+Sportive.csv` : pratiques sportives declarees ;
- `Note de cadrage - POC Avantages Sportifs.pdf` : cadrage fonctionnel du projet.

Les fichiers de donnees ne sont pas versionnes dans Git afin de proteger les donnees RH.

## Structure actuelle

```text
.
+-- analyse_donnees.py
+-- scripts/
+   +-- clean_data.py
+   +-- merge_data.py
+   +-- calculate_distances.py
+   +-- simulate_strava.py
+   +-- validate_data_gx.py
+   `-- notify_slack.py
+-- kestra/
+   `-- analyse_donnees.yml
+-- docs/
+   `-- tests_qualite_donnees.md
+-- test_analyse_donnees.py
+-- requirements.txt
+-- .env.template
`-- README.md
```

## Installation

Creer et activer un environnement virtuel :

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Installer les dependances :

```powershell
pip install -r requirements.txt
```

## Configuration

Copier le fichier `.env.template` en `.env`, puis renseigner la cle Google Maps :

```text
GOOGLE_MAPS_API_KEY="TA_CLE_API_GOOGLE"
```

Sans cle API, le script peut lire et analyser les fichiers, mais la validation automatique des distances Google Maps ne sera pas active.

Pour les notifications Slack depuis Kestra, renseigner aussi :

```text
SLACK_WEBHOOK_URL="URL_DU_WEBHOOK_SLACK"
```

## Lancer Kestra

Le workflow `kestra/analyse_donnees.yml` monte ce projet dans les conteneurs
Python sous le chemin `/workspace`. Kestra doit donc etre lance avec les
montages Docker actives :

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

Sur Kestra 1.3.x, cette variable peut afficher un avertissement de
deprecation. L'avertissement n'est pas bloquant ; il indique seulement que
Kestra prefere maintenant une configuration plugin dediee pour `volume-enabled`.

Apres modification de `kestra/analyse_donnees.yml`, importer a nouveau le flow
dans l'interface Kestra avant de relancer l'execution.

## Lancer l'analyse

```powershell
python analyse_donnees.py
```

Le script affiche :

- un resume des donnees RH ;
- un resume des pratiques sportives ;
- un resume apres fusion RH + sport ;
- une validation des trajets domicile -> entreprise si la cle Google Maps est configuree.

## Lancer les tests

```powershell
python -m unittest -v
```

Les tests verifient actuellement :

- les schemas des vrais fichiers CSV fournis ;
- les volumes et compteurs principaux ;
- la fusion RH + sport ;
- les seuils de distance issus de la note de cadrage ;
- le signalement d'un trajet marche/running trop long.

Une documentation detaillee des controles de qualite des donnees est disponible dans
`docs/tests_qualite_donnees.md`. Elle couvre les controles de coherence
executes dans Kestra avec Great Expectations, ainsi que les evolutions possibles
avec Soda en alternative.

## Regles metier couvertes

La note de cadrage demande de verifier la coherence des modes de deplacement avec la distance domicile -> entreprise.

Regles implementees pour cette premiere etape :

- `Marche/running` : maximum 15 km ;
- `Velo/Trottinette/Autres` : maximum 25 km ;
- adresse entreprise : `1362 Av. des Platanes, 34970 Lattes, France`.

## Prochaines etapes

- Generer un historique coherent d'activites sportives sur 12 mois.
- Stocker ces activites dans une base de donnees.
- Preparer les donnees pour des messages Slack.
- Ajouter les indicateurs necessaires a la restitution PowerBI.
