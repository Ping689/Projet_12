import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import analyse_donnees


OUTPUTS_DIR = Path("outputs")


def main():
    OUTPUTS_DIR.mkdir(exist_ok=True)

    rh_rows = analyse_donnees.read_csv(analyse_donnees.RH_FILE)
    results = []

    for row in rh_rows:
        validation = analyse_donnees.validate_commute(
            row.get("Adresse du domicile", ""),
            row.get("Moyen de déplacement", ""),
        )
        results.append({
            "id_salarie": row.get("ID salarié", ""),
            "nom": row.get("Nom", ""),
            "prenom": row.get("Prénom", ""),
            "mode_deplacement": row.get("Moyen de déplacement", ""),
            "adresse": row.get("Adresse du domicile", ""),
            **validation,
        })

    output_path = OUTPUTS_DIR / "validation_distances.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    ok_count = sum(1 for item in results if item.get("status") == "OK")
    suspicious_count = sum(1 for item in results if item.get("suspicious"))
    print(f"Distances calculees avec succes: {ok_count}/{len(results)}")
    print(f"Trajets suspects: {suspicious_count}")
    print(f"Fichier cree: {output_path}")


if __name__ == "__main__":
    main()
