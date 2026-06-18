import json
import sys
from pathlib import Path

import pandas as pd
from great_expectations.dataset import PandasDataset

sys.path.append(str(Path(__file__).resolve().parents[1]))

import analyse_donnees


OUTPUTS_DIR = Path("outputs")
REPORT_PATH = OUTPUTS_DIR / "rapport_qualite_great_expectations.json"


def add_result(results, dataset_name, result):
    payload = result.to_json_dict()
    payload["dataset"] = dataset_name
    results.append(payload)


def validate_rh(results):
    rows = analyse_donnees.read_csv(analyse_donnees.RH_FILE)
    df = pd.DataFrame(rows)
    df["Salaire brut numeric"] = pd.to_numeric(df["Salaire brut"].str.replace(",", "."), errors="coerce")
    df["Nombre de jours de CP numeric"] = pd.to_numeric(
        df["Nombre de jours de CP"].str.replace(",", "."),
        errors="coerce",
    )

    dataset = PandasDataset(df)
    expected_columns = [
        "ID salarié",
        "Nom",
        "Prénom",
        "Date de naissance",
        "BU",
        "Date d'embauche",
        "Salaire brut",
        "Type de contrat",
        "Nombre de jours de CP",
        "Adresse du domicile",
        "Moyen de déplacement",
        "Salaire brut numeric",
        "Nombre de jours de CP numeric",
    ]

    add_result(results, "rh", dataset.expect_table_columns_to_match_set(expected_columns, exact_match=True))
    add_result(results, "rh", dataset.expect_column_values_to_not_be_null("ID salarié"))
    add_result(results, "rh", dataset.expect_column_values_to_be_unique("ID salarié"))
    add_result(results, "rh", dataset.expect_column_values_to_not_be_null("Adresse du domicile"))
    add_result(results, "rh", dataset.expect_column_values_to_be_in_set("Type de contrat", ["CDI", "CDD"]))
    add_result(
        results,
        "rh",
        dataset.expect_column_values_to_be_in_set(
            "Moyen de déplacement",
            [
                "Marche/running",
                "Vélo/Trottinette/Autres",
                "Transports en commun",
                "véhicule thermique/électrique",
            ],
        ),
    )
    add_result(
        results,
        "rh",
        dataset.expect_column_values_to_match_regex("Date de naissance", r"^\d{1,2}/\d{1,2}/\d{4}$"),
    )
    add_result(
        results,
        "rh",
        dataset.expect_column_values_to_match_regex("Date d'embauche", r"^\d{1,2}/\d{1,2}/\d{4}$"),
    )
    add_result(results, "rh", dataset.expect_column_values_to_not_be_null("Salaire brut numeric"))
    add_result(results, "rh", dataset.expect_column_min_to_be_between("Salaire brut numeric", min_value=0))
    add_result(results, "rh", dataset.expect_column_values_to_not_be_null("Nombre de jours de CP numeric"))
    add_result(results, "rh", dataset.expect_column_min_to_be_between("Nombre de jours de CP numeric", min_value=0))


def validate_sport(results):
    rows = analyse_donnees.read_csv(analyse_donnees.SPORT_FILE)
    dataset = PandasDataset(pd.DataFrame(rows))

    add_result(
        results,
        "sport",
        dataset.expect_table_columns_to_match_set(["ID salarié", "Pratique d'un sport"], exact_match=True),
    )
    add_result(results, "sport", dataset.expect_column_values_to_not_be_null("ID salarié"))


def validate_distances(results):
    distance_file = OUTPUTS_DIR / "validation_distances.json"
    if not distance_file.exists():
        results.append({
            "dataset": "distances",
            "success": False,
            "expectation_config": {"expectation_type": "file_exists"},
            "result": {"observed_value": str(distance_file), "details": "Fichier absent"},
        })
        return

    df = pd.DataFrame(json.loads(distance_file.read_text(encoding="utf-8")))
    dataset = PandasDataset(df)

    add_result(results, "distances", dataset.expect_column_values_to_not_be_null("id_salarie"))
    if "distance_km" in df.columns and df["distance_km"].notna().any():
        add_result(
            results,
            "distances",
            dataset.expect_column_min_to_be_between("distance_km", min_value=0),
        )


def validate_strava(results):
    strava_file = OUTPUTS_DIR / "activites_strava_simulees.csv"
    if not strava_file.exists():
        results.append({
            "dataset": "strava",
            "success": False,
            "expectation_config": {"expectation_type": "file_exists"},
            "result": {"observed_value": str(strava_file), "details": "Fichier absent"},
        })
        return

    df = pd.read_csv(strava_file, sep=";")
    dataset = PandasDataset(df)

    add_result(results, "strava", dataset.expect_column_values_to_not_be_null("activity_id"))
    add_result(results, "strava", dataset.expect_column_values_to_be_unique("activity_id"))
    add_result(results, "strava", dataset.expect_column_values_to_not_be_null("employee_id"))
    add_result(results, "strava", dataset.expect_column_values_to_match_regex("activity_date", r"^\d{4}-\d{2}-\d{2}$"))
    add_result(results, "strava", dataset.expect_column_values_to_be_in_set("activity_type", ["Run", "Ride", "Walk", "Swim", "Hike"]))
    add_result(results, "strava", dataset.expect_column_min_to_be_between("distance_km", min_value=0))
    add_result(results, "strava", dataset.expect_column_min_to_be_between("duration_minutes", min_value=0))


def main():
    OUTPUTS_DIR.mkdir(exist_ok=True)
    results = []

    validate_rh(results)
    validate_sport(results)
    validate_distances(results)
    validate_strava(results)

    report = {
        "framework": "Great Expectations",
        "status": "PASS" if all(result["success"] for result in results) else "FAIL",
        "results": results,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Rapport Great Expectations cree: {REPORT_PATH}")
    print(f"Statut qualite: {report['status']}")

    if report["status"] != "PASS":
        failed = [
            f"{result['dataset']}::{result['expectation_config']['expectation_type']}"
            for result in results
            if not result["success"]
        ]
        raise SystemExit(f"Expectations en echec: {failed}")


if __name__ == "__main__":
    main()
