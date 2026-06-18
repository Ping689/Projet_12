import csv
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import analyse_donnees


STAGING_DIR = Path("staging")


def write_clean(rows, output_path):
    if not rows:
        return

    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for row in rows:
            cleaned = {
                key.strip(): (value.strip() if isinstance(value, str) else value)
                for key, value in row.items()
            }
            writer.writerow(cleaned)


def main():
    STAGING_DIR.mkdir(exist_ok=True)

    rh_rows = analyse_donnees.read_csv(analyse_donnees.RH_FILE)
    sport_rows = analyse_donnees.read_csv(analyse_donnees.SPORT_FILE)

    write_clean(rh_rows, STAGING_DIR / "rh_clean.csv")
    write_clean(sport_rows, STAGING_DIR / "sport_clean.csv")

    print(f"RH nettoyees: {len(rh_rows)} lignes")
    print(f"Sports nettoyes: {len(sport_rows)} lignes")


if __name__ == "__main__":
    main()
