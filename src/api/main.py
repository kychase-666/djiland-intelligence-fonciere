"""
API FastAPI — sert les rapports fonciers et les données du dashboard.

Endpoints principaux :
  GET /health                      : sonde de vie.
  GET /parcelles                   : GeoJSON des parcelles + prix + indicateurs.
  GET /parcelle/{code}/rapport     : rapport personnalisé complet d'une parcelle.
  GET /alertes                     : top zones à plus forte hausse prédite.
  GET /tendance/{quartier}         : série temporelle des prix d'un quartier.

En mode démo, l'API lit les données synthétiques ; en production, PostGIS.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import DEMO_MODE, SYNTHETIC_DIR

app = FastAPI(
    title="Ivoire Land Intelligence API",
    description="Veille foncière data-driven — Djiland SARL",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def _load(name: str) -> pd.DataFrame:
    """Charge un jeu synthétique parquet ; erreur claire s'il manque."""
    path = SYNTHETIC_DIR / name
    if not path.exists():
        raise HTTPException(503, f"Donnée absente : {name}. Lancez d'abord main.py.")
    return pd.read_parquet(path)


@app.get("/health")
def health() -> dict:
    """Sonde de vie et mode d'exécution courant."""
    return {"status": "ok", "demo_mode": DEMO_MODE}


@app.get("/parcelles")
def parcelles() -> dict:
    """Retourne les parcelles enrichies (prix moyen + heat) en GeoJSON."""
    import geopandas as gpd

    gdf = gpd.read_parquet(SYNTHETIC_DIR / "parcelles.parquet")
    indic = _load("indicateurs.parquet")
    gdf = gdf.merge(indic, on="code_parcelle", how="left", suffixes=("", "_i"))
    return json.loads(gdf.to_json())


@app.get("/parcelle/{code}/rapport")
def rapport(code: str) -> dict:
    """Rapport personnalisé complet d'une parcelle (topo, NDVI, risques, heat)."""
    indic = _load("indicateurs.parquet")
    row = indic[indic["code_parcelle"] == code]
    if row.empty:
        raise HTTPException(404, f"Parcelle {code} introuvable.")
    r = row.iloc[0].to_dict()
    return {
        "code_parcelle": code,
        "quartier": r.get("quartier"),
        "ndvi_moyen": r.get("ndvi_moyen"),
        "ndvi_delta_6m": r.get("ndvi_delta_6m"),
        "pente_moyenne_deg": r.get("pente_moyenne_deg"),
        "part_pente_sup15": r.get("part_pente_sup15"),
        "risque_inondation": r.get("risque_inondation"),
        "accessibilite_min": r.get("accessibilite_min"),
        "speculation_heat": r.get("speculation_heat"),
    }


@app.get("/alertes")
def alertes(top: int = 10) -> list[dict]:
    """Top zones à plus forte hausse de prix prédite à 6 mois."""
    path = SYNTHETIC_DIR / "predictions.parquet"
    if not path.exists():
        raise HTTPException(503, "Prédictions absentes. Lancez main.py (Phase 4).")
    df = pd.read_parquet(path).sort_values("hausse_pct", ascending=False).head(top)
    return df.to_dict(orient="records")


@app.get("/tendance/{quartier}")
def tendance(quartier: str) -> list[dict]:
    """Série mensuelle des prix au m² d'un quartier (24 derniers mois)."""
    prix = _load("prix.parquet")
    sub = prix[prix["quartier"].str.lower() == quartier.lower()].copy()
    if sub.empty:
        raise HTTPException(404, f"Aucune donnée pour {quartier}.")
    sub["mois"] = pd.to_datetime(sub["date_annonce"]).dt.to_period("M").astype(str)
    serie = sub.groupby("mois")["prix_m2_fcfa"].mean().round(0).reset_index()
    return serie.to_dict(orient="records")
