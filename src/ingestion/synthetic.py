"""
Générateur de DONNÉES SYNTHÉTIQUES réalistes.

Objectif : démarrer à « 0 donnée » tout en ayant un dashboard vivant dès le
premier lancement. Les valeurs sont calibrées pour ressembler au marché
abidjanais (prix au m² par quartier, NDVI, pentes, chantiers, arrêtés...).

⚠️  Ce sont des données FICTIVES pour la démo. Le code de production bascule
    sur les vraies API dès que DEMO_MODE=false.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta

import geopandas as gpd
import numpy as np
import pandas as pd
from loguru import logger
from shapely.geometry import Point, box

from config import CRS_DISPLAY, SYNTHETIC_DIR

random.seed(42)
np.random.seed(42)

# Prix médian au m² (FCFA) et tendance mensuelle par quartier (calibrage réaliste)
QUARTIERS = {
    "Plateau":       {"aoi": "abidjan_district", "prix_m2": 350_000, "tendance": 0.010, "centre": (-4.020, 5.325)},
    "Cocody":        {"aoi": "abidjan_district", "prix_m2": 180_000, "tendance": 0.012, "centre": (-3.980, 5.360)},
    "Marcory":       {"aoi": "abidjan_district", "prix_m2": 120_000, "tendance": 0.009, "centre": (-3.990, 5.300)},
    "Yopougon":      {"aoi": "yopougon",         "prix_m2": 55_000,  "tendance": 0.015, "centre": (-4.075, 5.355)},
    "Abobo":         {"aoi": "abidjan_district", "prix_m2": 40_000,  "tendance": 0.018, "centre": (-4.020, 5.420)},
    "Songon":        {"aoi": "songon",           "prix_m2": 18_000,  "tendance": 0.028, "centre": (-4.230, 5.340)},
    "Anyama":        {"aoi": "anyama",           "prix_m2": 22_000,  "tendance": 0.025, "centre": (-4.050, 5.510)},
    "Dabou":         {"aoi": "dabou",            "prix_m2": 12_000,  "tendance": 0.022, "centre": (-4.370, 5.340)},
    "Grand-Bassam":  {"aoi": "grand_bassam",     "prix_m2": 35_000,  "tendance": 0.020, "centre": (-3.720, 5.210)},
    "Bingerville":   {"aoi": "abidjan_district", "prix_m2": 45_000,  "tendance": 0.024, "centre": (-3.900, 5.355)},
}

TYPES_SOL = ["sableux", "argileux", "latéritique", "rocheux"]
TYPES_VUE = ["lagune", "rue", "dégagée", "obstruée"]


def _random_polygon(centre, spread=0.01, taille=0.0006):
    """Crée un petit polygone (parcelle) autour d'un centre bruité."""
    cx = centre[0] + random.uniform(-spread, spread)
    cy = centre[1] + random.uniform(-spread, spread)
    return box(cx, cy, cx + taille, cy + taille)


def generate_parcelles(n_par_quartier: int = 40) -> gpd.GeoDataFrame:
    """Génère un parc de parcelles réparties sur tous les quartiers."""
    rows = []
    pid = 0
    for quartier, cfg in QUARTIERS.items():
        for _ in range(n_par_quartier):
            pid += 1
            poly = _random_polygon(cfg["centre"])
            rows.append({
                "code_parcelle": f"DJH-{quartier[:3].upper()}-{pid:05d}",
                "commune": quartier,
                "quartier": quartier,
                "aoi": cfg["aoi"],
                "surface_m2": round(random.uniform(200, 1200), 1),
                "geometry": poly,
            })
    gdf = gpd.GeoDataFrame(rows, crs=CRS_DISPLAY)
    logger.info(f"[SYNTH] {len(gdf)} parcelles générées.")
    return gdf


def generate_prix_history(parcelles: gpd.GeoDataFrame, mois: int = 24) -> pd.DataFrame:
    """Historise les prix au m² sur `mois` mois avec tendance + saisonnalité."""
    rows = []
    today = datetime.utcnow()
    for _, p in parcelles.sample(frac=0.6, random_state=1).iterrows():
        cfg = QUARTIERS[p["quartier"]]
        base = cfg["prix_m2"]
        for m in range(mois, -1, -1):
            date_ann = today - timedelta(days=30 * m)
            croissance = (1 + cfg["tendance"]) ** (mois - m)
            saison = 1 + 0.04 * np.sin(2 * np.pi * m / 12)
            bruit = np.random.normal(1.0, 0.08)
            prix_m2 = base * croissance * saison * bruit
            rows.append({
                "source": "synthetic",
                "quartier": p["quartier"],
                "type_bien": random.choice(["terrain", "villa", "appartement"]),
                "surface_m2": p["surface_m2"],
                "prix_m2_fcfa": round(max(prix_m2, 3000), 0),
                "prix_total_fcfa": round(max(prix_m2, 3000) * p["surface_m2"], 0),
                "lon": p.geometry.centroid.x,
                "lat": p.geometry.centroid.y,
                "date_annonce": date_ann,
            })
    df = pd.DataFrame(rows)
    logger.info(f"[SYNTH] {len(df)} observations de prix historisées.")
    return df


def generate_indicateurs(parcelles: gpd.GeoDataFrame) -> pd.DataFrame:
    """Génère NDVI, pentes, accessibilité et Speculation Heat par parcelle."""
    rows = []
    for _, p in parcelles.iterrows():
        cfg = QUARTIERS[p["quartier"]]
        periurbain = cfg["prix_m2"] < 30_000
        ndvi = np.clip(np.random.normal(0.55 if periurbain else 0.25, 0.15), -0.1, 0.9)
        ndvi_delta = np.random.normal(-0.06 if periurbain else -0.02, 0.05)
        sar = np.clip(np.random.normal(0.6 if periurbain else 0.3, 0.2), 0, 1)
        pente = abs(np.random.normal(6, 4))
        accessibilite = 10 + np.linalg.norm(
            np.array(p.geometry.centroid.coords[0]) - np.array((-4.02, 5.325))) * 900
        # Speculation Heat = f(baisse NDVI, chantiers SAR, tendance prix, accès)
        heat = 100 * np.clip(
            0.35 * min(-ndvi_delta * 6, 1)
            + 0.30 * sar
            + 0.25 * (cfg["tendance"] / 0.03)
            + 0.10 * max(0, 1 - accessibilite / 90), 0, 1)
        rows.append({
            "code_parcelle": p["code_parcelle"],
            "quartier": p["quartier"],
            "ndvi_moyen": round(float(ndvi), 3),
            "ndvi_delta_6m": round(float(ndvi_delta), 3),
            "changement_sar": round(float(sar), 3),
            "pente_moyenne_deg": round(float(pente), 2),
            "part_pente_sup15": round(float(np.clip((pente - 8) / 20, 0, 1)), 3),
            "risque_inondation": round(float(np.clip(np.random.beta(2, 5), 0, 1)), 3),
            "accessibilite_min": round(float(accessibilite), 1),
            "speculation_heat": round(float(heat), 1),
        })
    df = pd.DataFrame(rows)
    logger.info(f"[SYNTH] {len(df)} lignes d'indicateurs spatiaux.")
    return df


def generate_releves(parcelles: gpd.GeoDataFrame, n: int = 80) -> pd.DataFrame:
    """Simule des relevés terrain (ground truth) des équipes Djiland."""
    rows = []
    for _, p in parcelles.sample(n=min(n, len(parcelles)), random_state=2).iterrows():
        rows.append({
            "code_parcelle": p["code_parcelle"],
            "agent": random.choice(["Koffi", "Aya", "Traoré", "Diomandé"]),
            "lon": p.geometry.centroid.x,
            "lat": p.geometry.centroid.y,
            "qualite_sol": random.choice(TYPES_SOL),
            "vue": random.choice(TYPES_VUE),
            "nuisance_sonore": random.randint(1, 5),
            "accessibilite_reelle": random.randint(1, 5),
            "litige_foncier": random.random() < 0.12,
            "viabilise": random.random() < 0.5,
            "commentaire": "Relevé synthétique de démonstration.",
        })
    return pd.DataFrame(rows)


def generate_arretes(n: int = 25) -> pd.DataFrame:
    """Simule des arrêtés de lotissement / ZUP récents (signal spéculatif)."""
    rows = []
    today = datetime.utcnow()
    for i in range(n):
        q = random.choice(list(QUARTIERS))
        cfg = QUARTIERS[q]
        rows.append({
            "reference": f"ARR-{2025}-{i:03d}",
            "type_acte": random.choice(["lotissement", "ZUP", "voirie", "DUP"]),
            "commune": q,
            "quartier": q,
            "lon": cfg["centre"][0] + random.uniform(-0.01, 0.01),
            "lat": cfg["centre"][1] + random.uniform(-0.01, 0.01),
            "date_publication": today - timedelta(days=random.randint(1, 180)),
            "source": "synthetic",
            "resume": f"Arrêté de {q} — projet d'aménagement.",
        })
    return pd.DataFrame(rows)


def build_all(n_par_quartier: int = 40) -> dict:
    """Génère l'ensemble des jeux synthétiques et les sauvegarde sur disque.

    Les fichiers écrits dans data/synthetic/ servent de repli au dashboard
    lorsque PostGIS n'est pas disponible.
    """
    parcelles = generate_parcelles(n_par_quartier)
    prix = generate_prix_history(parcelles)
    indic = generate_indicateurs(parcelles)
    releves = generate_releves(parcelles)
    arretes = generate_arretes()

    # GeoParquet (et non GeoJSON) : I/O Python pur, robuste aux chemins avec
    # espaces/caractères spéciaux qui perturbent le parsing de GDAL.
    parcelles.to_parquet(SYNTHETIC_DIR / "parcelles.parquet")
    prix.to_parquet(SYNTHETIC_DIR / "prix.parquet")
    indic.to_parquet(SYNTHETIC_DIR / "indicateurs.parquet")
    releves.to_parquet(SYNTHETIC_DIR / "releves.parquet")
    arretes.to_parquet(SYNTHETIC_DIR / "arretes.parquet")
    logger.info(f"[SYNTH] Jeux synthétiques sauvegardés dans {SYNTHETIC_DIR}")

    return {"parcelles": parcelles, "prix": prix, "indicateurs": indic,
            "releves": releves, "arretes": arretes}


if __name__ == "__main__":
    build_all()
