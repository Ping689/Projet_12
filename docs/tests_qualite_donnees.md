# Tests de qualite des donnees

Ce document decrit les controles de coherence et de fonctionnalite appliques au POC Avantages Sportifs.
Ils sont executes avec Great Expectations dans le workflow Kestra via la tache `controler_qualite_donnees`.

Le rapport produit est disponible dans :

```text
outputs/rapport_qualite_great_expectations.json
```

## Objectifs

Les tests doivent securiser les traitements avant exploitation dans Power BI ou envoi de notifications.
Ils verifient que les donnees sont exploitables, coherentes avec les regles metier et suffisamment fiables
pour alimenter les indicateurs du POC.

## Controles actuellement couverts

| Controle | Donnees concernees | Regle | Criticite |
| --- | --- | --- | --- |
| Schema RH attendu | `Donnees+RH.csv` | Les colonnes obligatoires doivent etre presentes. | Bloquante |
| Schema sport attendu | `Donnees+Sportive.csv` | Les colonnes obligatoires doivent etre presentes. | Bloquante |
| Identifiants RH non vides | RH | Chaque salarie doit avoir un identifiant. | Bloquante |
| Identifiants RH uniques | RH | Un identifiant ne doit pas apparaitre plusieurs fois. | Bloquante |
| Types de contrat valides | RH | Valeurs autorisees : `CDI`, `CDD`. | Bloquante |
| Modes de deplacement valides | RH | Valeurs autorisees : marche/running, velo/trottinette/autres, transports en commun, vehicule thermique/electrique. | Bloquante |
| Dates de naissance valides | RH | Les dates doivent etre parseables. | Bloquante |
| Dates d'embauche valides | RH | Les dates doivent etre parseables. | Bloquante |
| Salaires non negatifs | RH | Le salaire brut doit etre numerique et superieur ou egal a 0. | Bloquante |
| Jours de CP non negatifs | RH | Le nombre de jours de CP doit etre numerique et superieur ou egal a 0. | Bloquante |
| Distances domicile-entreprise non negatives | Google Maps / cache | Une distance calculee ne peut pas etre negative. | Bloquante |
| Dates d'activites Strava valides | Donnees simulees Faker | Les dates d'activites doivent etre valides. | Bloquante |
| Distances Strava non negatives | Donnees simulees Faker | Une activite sportive ne peut pas avoir une distance negative. | Bloquante |

## Tests de fonctionnalite

Les tests unitaires existants dans `test_analyse_donnees.py` couvrent les fonctions principales :

- lecture des vrais fichiers CSV ;
- verification des schemas ;
- calcul des resumes RH et sport ;
- fusion RH + sport ;
- regles metier de distance domicile-entreprise ;
- detection d'un trajet marche/running trop long.

Ils se lancent avec :

```powershell
python -m unittest -v
```

## Execution dans Kestra

Dans le workflow `kestra/analyse_donnees.yml`, la tache `controler_qualite_donnees` s'execute apres :

- le nettoyage ;
- la fusion ;
- la simulation des activites Strava ;
- le calcul des distances.

Si une regle bloquante echoue, la tache retourne une erreur et l'execution Kestra passe en echec.
Cela evite de publier des donnees incoherentes vers Power BI ou de notifier Slack comme si le pipeline etait valide.

## Implementation Great Expectations

Le script de validation est disponible dans :

```text
scripts/validate_data_gx.py
```

Il utilise Great Expectations pour executer les expectations suivantes :

```text
expect_table_columns_to_match_set
expect_column_values_to_not_be_null
expect_column_values_to_be_unique
expect_column_values_to_be_in_set
expect_column_values_to_match_regex
expect_column_min_to_be_between
```

Dans le workflow Kestra, la tache installe Great Expectations puis lance :

```bash
python scripts/validate_data_gx.py
```

Si une expectation echoue, le script retourne une erreur et Kestra marque l'execution en echec.

Approche recommandee pour industrialiser cette partie :

- creer une suite `rh_suite` pour les donnees RH ;
- creer une suite `sport_suite` pour les donnees sportives ;
- creer une suite `strava_suite` pour les activites simulees ou recuperees ;
- publier les Data Docs Great Expectations comme artefact de pipeline ;
- faire echouer le flow Kestra si le checkpoint Great Expectations echoue.

## Soda

Soda reste une alternative possible, mais le POC retient Great Expectations.
Exemple de checks Soda equivalents si l'architecture evolue :

```yaml
checks for rh:
  - row_count > 0
  - missing_count(ID salarie) = 0
  - duplicate_count(ID salarie) = 0
  - invalid_count(Type de contrat) = 0:
      valid values: [CDI, CDD]
  - min(Salaire brut) >= 0
  - min(Nombre de jours de CP) >= 0

checks for distances:
  - min(distance_km) >= 0

checks for activites_strava:
  - row_count > 0
  - missing_count(activity_id) = 0
  - min(distance_km) >= 0
```

Approche possible avec Soda :

- stocker les donnees nettoyees dans PostgreSQL, BigQuery, Snowflake ou un autre entrepot ;
- executer `soda scan` depuis une tache Kestra ;
- publier le rapport Soda dans les logs et dans un espace d'artefacts ;
- ajouter une alerte Slack en cas d'echec.

## Evolutions possibles

- Ajouter un controle d'age minimum ou maximum pour detecter les dates de naissance aberrantes.
- Verifier que la date d'embauche est posterieure a la date de naissance.
- Ajouter des seuils sur les distances Strava par type d'activite.
- Comparer les volumes quotidiens avec une moyenne historique.
- Integrer Debezium pour le CDC en production afin de tester uniquement les lignes modifiees.
- Exposer les resultats de qualite dans Prometheus et Grafana.
- Ajouter un onglet Power BI dedie a la qualite des donnees.
