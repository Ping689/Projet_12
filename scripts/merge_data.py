import csv
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import analyse_donnees


OUTPUTS_DIR = Path("outputs")


def main():
    OUTPUTS_DIR.mkdir(exist_ok=True)

    rh_rows = analyse_donnees.read_csv(analyse_donnees.RH_FILE)
    sport_rows = analyse_donnees.read_csv(analyse_donnees.SPORT_FILE)
    merged_rows = analyse_donnees.merge_data(rh_rows, sport_rows)

    merged_path = OUTPUTS_DIR / "donnees_fusionnees.csv"
    fieldnames = list(merged_rows[0].keys())
    with merged_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(merged_rows)

    summary = {
        "rh": analyse_donnees.summarize_rh(rh_rows),
        "sport": analyse_donnees.summarize_sport(sport_rows),
        "fusion": analyse_donnees.analyse_merge(merged_rows),
    }
    serializable_summary = json.loads(json.dumps(summary, default=dict, ensure_ascii=False))
    (OUTPUTS_DIR / "resume_analyse.json").write_text(
        json.dumps(serializable_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Fichier fusionne cree: {merged_path}")
    print(f"Total salaries fusionnes: {len(merged_rows)}")


if __name__ == "__main__":
    main()
