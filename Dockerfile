FROM python:3.12-slim

WORKDIR /workspace

# Installer les dépendances système nécessaires (ex: git ou compilateurs si besoin)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copier et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
