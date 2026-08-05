"""
Le « Flywheel » — planification des tâches récurrentes.

Exécute le pipeline complet chaque dimanche soir et sauvegarde une copie
horodatée des sorties (data versioning simple, sans dépendance externe).
Pour une montée en charge, remplacer `schedule` par Celery + Redis (déjà
prévu dans le docker-compose commenté).
"""
from __future__ import annotations

import shutil
import time
from datetime import datetime

import schedule
from loguru import logger

from config import PROCESSED_DIR, SYNTHETIC_DIR


def versionner_sorties() -> None:
    """Sauvegarde horodatée des sorties (backup simple = data versioning)."""
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    backup = PROCESSED_DIR / f"snapshot_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)
    for f in SYNTHETIC_DIR.glob("*.parquet"):
        shutil.copy2(f, backup / f.name)
    logger.info(f"[FLYWHEEL] Snapshot versionné -> {backup}")


def job_pipeline_complet() -> None:
    """Job hebdomadaire : ingestion → traitement → ML → versioning."""
    logger.info("[FLYWHEEL] Démarrage du pipeline hebdomadaire.")
    from main import DEMO_MODE, run_demo_pipeline, run_real_pipeline

    (run_demo_pipeline if DEMO_MODE else run_real_pipeline)()
    versionner_sorties()
    logger.success("[FLYWHEEL] Pipeline hebdomadaire terminé.")


def start() -> None:
    """Démarre le planificateur (dimanche 22h + scraping quotidien 6h)."""
    schedule.every().sunday.at("22:00").do(job_pipeline_complet)
    schedule.every().day.at("06:00").do(
        lambda: __import__("src.ingestion.scraping", fromlist=["scrape_jumia_deals"]
                           ).scrape_jumia_deals())
    logger.info("[FLYWHEEL] Planificateur actif. Ctrl+C pour arrêter.")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    start()
