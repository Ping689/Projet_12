import json
import os
from pathlib import Path

import requests


SUMMARY_PATH = Path("outputs/resume_analyse.json")


def build_message():
    if SUMMARY_PATH.exists():
        summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        total = summary.get("fusion", {}).get("nb_total", "n/a")
        avec_sport = summary.get("fusion", {}).get("avec_sport", "n/a")
    else:
        total = "n/a"
        avec_sport = "n/a"

    return (
        "Pipeline Projet 12 termine. "
        f"Salaries analyses: {total}. "
        f"Salaries avec sport declare: {avec_sport}."
    )


def main():
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    message = build_message()

    if not webhook_url:
        print("SLACK_WEBHOOK_URL non defini: notification Slack ignoree.")
        print(message)
        return

    response = requests.post(webhook_url, json={"text": message}, timeout=15)
    response.raise_for_status()
    print("Notification Slack envoyee.")


if __name__ == "__main__":
    main()
