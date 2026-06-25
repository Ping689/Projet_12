import unittest
from unittest.mock import patch
import pandas as pd
import json
from pathlib import Path

# Importer les scripts à tester
import scripts.calculate_distances as calculate_distances

class DistancesValidationTest(unittest.TestCase):
    def test_commute_rules_from_framing_note(self):
        self.assertEqual(calculate_distances.COMPANY_ADDRESS, "1362 Av. des Platanes, 34970 Lattes, France")
        self.assertEqual(calculate_distances.VALIDATION_THRESHOLDS["walking"], 15)
        self.assertEqual(calculate_distances.VALIDATION_THRESHOLDS["bicycling"], 25)
        self.assertEqual(calculate_distances.get_google_maps_mode("Marche/running"), "walking")
        self.assertEqual(calculate_distances.get_google_maps_mode("Vélo/Trottinette/Autres"), "bicycling")
        self.assertEqual(calculate_distances.get_google_maps_mode("Transports en commun"), "transit")
        self.assertEqual(calculate_distances.get_google_maps_mode("véhicule thermique/électrique"), "driving")
        self.assertEqual(
            calculate_distances.validate_commute("", "Marche/running", None),
            {"status": "NO_ORIGIN", "mode": None, "suspicious": False, "distance_meters": None, "distance_text": None, "duration_text": None},
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
            patch.object(calculate_distances, "load_cache", return_value={}),
            patch.object(calculate_distances, "save_cache") as save_cache_mock,
            patch.object(calculate_distances, "fetch_distance_matrix", return_value=fake_distance) as fetch_mock,
            patch.object(calculate_distances.time, "sleep"),
        ):
            result = calculate_distances.validate_commute(
                "10 rue Exemple, Montpellier",
                "Marche/running",
                "FAKE_KEY"
            )

        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["mode"], "walking")
        self.assertEqual(result["distance_km"], 16.0)
        self.assertTrue(result["suspicious"])
        fetch_mock.assert_called_once_with("10 rue Exemple, Montpellier", mode="walking", api_key="FAKE_KEY")
        save_cache_mock.assert_called_once()

class FinanceCalculationTest(unittest.TestCase):
    def test_finance_indicators_from_csv(self):
        csv_path = Path("outputs/donnees_financieres.csv")
        json_path = Path("outputs/impact_financier.json")
        
        self.assertTrue(csv_path.exists())
        self.assertTrue(json_path.exists())
        
        df = pd.read_csv(csv_path, sep=";")
        self.assertIn("eligible_prime", df.columns)
        self.assertIn("eligible_jours_bien_etre", df.columns)
        self.assertIn("avantage_financier_total", df.columns)
        
        with open(json_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
            
        self.assertEqual(summary["metriques_globales"]["effectif_total"], 161)
        self.assertEqual(summary["prime_sportive"]["nb_eligibles"], 68)
        self.assertEqual(summary["jours_bien_etre"]["nb_eligibles"], 95)

if __name__ == "__main__":
    unittest.main()
