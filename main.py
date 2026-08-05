"""
Pipeline complet IVOIRE LAND INTELLIGENCE (orchestrateur).

Exécute bout-en-bout : ingestion → traitement → indices → modèle → prédictions.
- DEMO_MODE=true  : tout tourne sur données synthétiques (rapide, hors-ligne).
- DEMO_MODE=false : bascule sur les vraies API (satellite STAC, OSM, scraping).

Usage :
    python main.py                 # pipeline complet
    python main.py --init-db       # crée aussi le schéma PostGIS
"""
from __future__ import annotations

import argparse
import time

from loguru import logger

from config import DEMO_MODE, SYNTHETIC_DIR


def run_demo_pipeline() -> None:
    """Pipeline de démonstration basé sur les données synthétiques."""
    from src.analysis import model as ml
    from src.analysis.speculation import compute_heat_index
    from src.ingestion.synthetic import build_all

    logger.info("=== PHASE 2 : Génération / ingestion des données (démo) ===")
    data = build_all(n_par_quartier=40)
    parcelles, prix, indic, arretes = (
        data["parcelles"], data["prix"], data["indicateurs"], data["arretes"])

    # Prépare une table 'points' (lon/lat) pour le heat index
    pts = parcelles.copy()
    pts["lon"] = pts.geometry.centroid.x
    pts["lat"] = pts.geometry.centroid.y

    logger.info("=== PHASE 3 : Speculation Heat Index ===")
    heat = compute_heat_index(pts[["code_parcelle", "quartier", "lon", "lat"]],
                              indic, arretes, prix)
    heat.to_parquet(SYNTHETIC_DIR / "heat.parquet")

    logger.info("=== PHASE 4 : Modèle prédictif XGBoost + SHAP ===")
    feat = ml.build_feature_table(prix, indic, heat)
    trained = ml.train(feat)
    preds = ml.predict_with_shap(feat, trained)
    preds.to_parquet(SYNTHETIC_DIR / "predictions.parquet")

    logger.success(f"Pipeline démo terminé — {len(preds)} prédictions de quartiers.")


def run_real_pipeline() -> None:
    """Pipeline production : vraies API satellite/OSM/scraping (esquisse)."""
    from src.ingestion import osm, satellite, scraping
    logger.warning("Mode production : nécessite accès réseau + PostGIS.")
    # 1) Satellite (STAC gratuit)
    for aoi in ("yopougon", "songon"):
        satellite.ingest_all(aoi)
    # 2) OSM
    for aoi in ("yopougon", "songon"):
        osm.fetch_pois(aoi)
    # 3) Scraping marché
    scraping.scrape_jumia_deals()
    logger.info("Brancher ici l'insertion PostGIS + traitement raster complet.")


def main() -> None:
    """Point d'entrée : parse les arguments et lance le pipeline adéquat."""
    parser = argparse.ArgumentParser(description="Pipeline Ivoire Land Intelligence")
    parser.add_argument("--init-db", action="store_true",
                        help="Initialise le schéma PostGIS avant le pipeline.")
    args = parser.parse_args()

    t0 = time.time()
    if args.init_db:
        from src.db.session import init_db
        init_db()

    if DEMO_MODE:
        run_demo_pipeline()
    else:
        run_real_pipeline()

    logger.success(f"Terminé en {time.time() - t0:.1f}s. "
                   f"Dashboard : streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
