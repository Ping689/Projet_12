import unittest
from collections import Counter
from unittest.mock import patch

import analyse_donnees


class AnalyseDonneesTest(unittest.TestCase):
    def test_real_csv_schemas_match_provided_files(self):
        rh_rows = analyse_donnees.read_csv(analyse_donnees.RH_FILE)
        sport_rows = analyse_donnees.read_csv(analyse_donnees.SPORT_FILE)

        self.assertEqual(
            list(rh_rows[0].keys()),
            [
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
            ],
        )
        self.assertEqual(
            list(sport_rows[0].keys()),
            ["ID salarié", "Pratique d'un sport"],
        )

    def test_analyse_real_csv_files(self):
        rh_rows = analyse_donnees.read_csv(analyse_donnees.RH_FILE)
        sport_rows = analyse_donnees.read_csv(analyse_donnees.SPORT_FILE)

        rh_summary = analyse_donnees.summarize_rh(rh_rows)
        sport_summary = analyse_donnees.summarize_sport(sport_rows)

        self.assertEqual(len(rh_rows), 161)
        self.assertEqual(len(sport_rows), 999)
        self.assertEqual(rh_summary["nb_salaires"], 161)
        self.assertEqual(rh_summary["salary_missing"], 0)
        self.assertEqual(rh_summary["contrats"], Counter({"CDI": 149, "CDD": 12}))
        self.assertEqual(
            rh_summary["business_units"],
            Counter({"Finance": 42, "Support": 35, "Ventes": 33, "R&D": 26, "Marketing": 25}),
        )
        self.assertEqual(
            rh_summary["transports"],
            Counter({
                "véhicule thermique/électrique": 73,
                "Vélo/Trottinette/Autres": 54,
                "Transports en commun": 20,
                "Marche/running": 14,
            }),
        )
        self.assertEqual(sport_summary["nb_lignes"], 999)
        self.assertEqual(sport_summary["no_sport_declared"], 904)
        self.assertEqual(
            sport_summary["sports"],
            Counter({
                "Runing": 18,
                "Randonnée": 16,
                "Tennis": 11,
                "Natation": 8,
                "Football": 6,
                "Rugby": 6,
                "Badminton": 5,
                "Voile": 5,
                "Judo": 4,
                "Boxe": 4,
                "Escalade": 3,
                "Triathlon": 3,
                "Équitation": 2,
                "Tennis de table": 2,
                "Basketball": 2,
            }),
        )

        merged_rows = analyse_donnees.merge_data(rh_rows, sport_rows)
        merged_summary = analyse_donnees.analyse_merge(merged_rows)

        self.assertEqual(len(merged_rows), 161)
        self.assertEqual(merged_summary["nb_total"], 161)
        self.assertEqual(merged_summary["avec_sport"], 95)
        self.assertEqual(merged_summary["sans_sport"], 66)
        self.assertEqual(
            merged_summary["transports_sportifs"],
            Counter({
                "véhicule thermique/électrique": 46,
                "Vélo/Trottinette/Autres": 29,
                "Transports en commun": 12,
                "Marche/running": 8,
            }),
        )

    def test_commute_rules_from_framing_note(self):
        self.assertEqual(analyse_donnees.COMPANY_ADDRESS, "1362 Av. des Platanes, 34970 Lattes, France")
        self.assertEqual(analyse_donnees.VALIDATION_THRESHOLDS["walking"], 15)
        self.assertEqual(analyse_donnees.VALIDATION_THRESHOLDS["bicycling"], 25)
        self.assertEqual(analyse_donnees.get_google_maps_mode("Marche/running"), "walking")
        self.assertEqual(analyse_donnees.get_google_maps_mode("Vélo/Trottinette/Autres"), "bicycling")
        self.assertEqual(analyse_donnees.get_google_maps_mode("Transports en commun"), "transit")
        self.assertEqual(analyse_donnees.get_google_maps_mode("véhicule thermique/électrique"), "driving")
        self.assertEqual(
            analyse_donnees.validate_commute("", "Marche/running"),
            {"status": "NO_ORIGIN", "mode": None, "suspicious": False},
        )

    def test_validate_commute_marks_long_walking_distance_as_suspicious(self):
        fake_distance = {
            "status": "OK",
            "distance_meters": 16_000,
            "duration_seconds": 14_400,
            "distance_text": "16 km",
            "duration_text": "4 hours",
            "mode": "walking",
        }

        with (
            patch.object(analyse_donnees, "load_cache", return_value={}),
            patch.object(analyse_donnees, "save_cache") as save_cache_mock,
            patch.object(analyse_donnees, "fetch_distance_matrix", return_value=fake_distance) as fetch_mock,
            patch.object(analyse_donnees.time, "sleep"),
        ):
            result = analyse_donnees.validate_commute(
                "10 rue Exemple, Montpellier",
                "Marche/running",
            )

        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["mode"], "walking")
        self.assertEqual(result["distance_km"], 16.0)
        self.assertTrue(result["suspicious"])
        fetch_mock.assert_called_once_with("10 rue Exemple, Montpellier", mode="walking")
        save_cache_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
