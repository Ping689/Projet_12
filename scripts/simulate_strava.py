import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

sys.path.append(str(Path(__file__).resolve().parents[1]))

import analyse_donnees


OUTPUTS_DIR = Path("outputs")
ACTIVITY_TYPES = ["Run", "Ride", "Walk", "Swim", "Hike"]


def main():
    fake = Faker("fr_FR")
    OUTPUTS_DIR.mkdir(exist_ok=True)

    rh_rows = analyse_donnees.read_csv(analyse_donnees.RH_FILE)
    start_date = date.today() - timedelta(days=365)
    rows = []

    for employee in rh_rows:
        employee_id = employee.get("ID salarié", "")
        for _ in range(random.randint(8, 30)):
            rows.append({
                "activity_id": fake.uuid4(),
                "employee_id": employee_id,
                "activity_date": start_date + timedelta(days=random.randint(0, 365)),
                "activity_type": random.choice(ACTIVITY_TYPES),
                "distance_km": round(random.uniform(1.0, 35.0), 2),
                "duration_minutes": random.randint(12, 180),
                "source": "faker_strava",
            })

    output_path = OUTPUTS_DIR / "activites_strava_simulees.csv"
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Activites Strava simulees: {len(rows)}")
    print(f"Fichier cree: {output_path}")


if __name__ == "__main__":
    main()
