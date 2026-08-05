"""
Consolidation des données du GRAND ABIDJAN (District Autonome — 13 communes).

Produit un jeu de données riche, prêt pour un dashboard « ultra poussé » précis
au m², mêlant VRAIES données gratuites et indicateurs calibrés :

  RÉEL (gratuit)            : limites de communes (OSM), POIs (OSM), grandes
                             voies (OSM), fonds satellite/relief (tuiles Esri).
  CALIBRÉ (synthétique)     : prix au m² avec gradient spatial, NDVI, pentes,
                             risque inondation, accessibilité, Speculation Heat,
                             arrêtés de lotissement, relevés terrain.

Tout est sauvegardé en GeoParquet dans data/grand_abidjan/ pour un chargement
instantané du dashboard (les appels réseau ne sont faits qu'une fois).
"""
from __future__ import annotations

import json
import random
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from loguru import logger
from shapely.geometry import Point

from config import (
    ALL_ZONES,
    CRS_DISPLAY,
    GRAND_ABIDJAN_BBOX,
    GRAND_ABIDJAN_DIR,
    PLATEAU_CBD,
)

warnings.filterwarnings("ignore")
random.seed(42)
np.random.seed(42)

# POIs utiles à l'évaluation foncière (tags OSM)
POI_TAGS = {
    "amenity": ["school", "marketplace", "hospital", "clinic", "university",
                "bank", "place_of_worship", "bus_station", "fuel", "pharmacy"],
    "shop": ["supermarket", "mall"],
}
# Regroupement en familles lisibles pour la légende
POI_FAMILLE = {
    "school": "Éducation", "university": "Éducation",
    "marketplace": "Marché/Commerce", "supermarket": "Marché/Commerce", "mall": "Marché/Commerce",
    "hospital": "Santé", "clinic": "Santé", "pharmacy": "Santé",
    "bank": "Banque", "place_of_worship": "Culte",
    "bus_station": "Transport", "fuel": "Station-service",
}


# ---------------------------------------------------------------------------
# 1. Limites administratives réelles (OSM)
# ---------------------------------------------------------------------------
def fetch_communes() -> gpd.GeoDataFrame:
    """Construit les zones : limites OSM réelles (District) + tampons côtiers.

    - Communes du District : polygone administratif réel via géocodage OSM.
    - Zones côtières (clé `rayon_km`) : disque tampon autour du centre-ville,
      car leurs limites OSM départementales sont trop vastes.
    """
    import osmnx as ox

    rows = []
    for nom, cfg in ALL_ZONES.items():
        if "rayon_km" in cfg:                       # zone côtière -> tampon
            geom = Point(cfg["centre"]).buffer(cfg["rayon_km"] / 111.0)
        else:                                        # commune -> limite réelle
            geom = None
            for req in (f"{nom}, Abidjan, Côte d'Ivoire", f"{nom}, Côte d'Ivoire"):
                try:
                    geom = ox.geocode_to_gdf(req).geometry.iloc[0]
                    break
                except Exception:
                    continue
            if geom is None:
                logger.warning(f"[GA] Géocodage échoué pour {nom} — repli tampon.")
                geom = Point(cfg["centre"]).buffer(0.027)
        rows.append({
            "commune": nom, "type_zone": cfg["type"],
            "prix_m2_base": cfg["prix_m2"], "tendance": cfg["tendance"],
            "cotier": "rayon_km" in cfg, "geometry": geom,
        })
    gdf = gpd.GeoDataFrame(rows, crs=CRS_DISPLAY)
    gdf["surface_km2"] = gdf.to_crs(32630).area / 1e6
    logger.success(f"[GA] {len(gdf)} zones construites "
                   f"({gdf['cotier'].sum()} côtières + {(~gdf['cotier']).sum()} communes).")
    return gdf


# ---------------------------------------------------------------------------
# 2. Parcelles avec gradient de prix spatial + indicateurs (précision m²)
# ---------------------------------------------------------------------------
def _sample_in_polygon(poly, n: int) -> list[Point]:
    """Tire n points aléatoires strictement à l'intérieur d'un polygone."""
    minx, miny, maxx, maxy = poly.bounds
    pts, tries = [], 0
    while len(pts) < n and tries < n * 60:
        p = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
        if poly.contains(p):
            pts.append(p)
        tries += 1
    return pts


def _dist_plateau_km(lon: float, lat: float) -> float:
    """Distance haversine (km) d'un point au Plateau (CBD)."""
    lon0, lat0 = PLATEAU_CBD
    dlat, dlon = np.radians(lat - lat0), np.radians(lon - lon0)
    a = (np.sin(dlat / 2) ** 2
         + np.cos(np.radians(lat0)) * np.cos(np.radians(lat)) * np.sin(dlon / 2) ** 2)
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def generate_parcelles(communes: gpd.GeoDataFrame, par_commune: int = 55) -> gpd.GeoDataFrame:
    """Génère des parcelles dans chaque commune avec prix/m² à gradient spatial.

    Le prix au m² varie DANS la commune selon la distance au Plateau (proxy de
    centralité) et un bruit lognormal, pour une analyse fine au m².
    """
    rows, pid = [], 0
    for _, com in communes.iterrows():
        prix_base = com["prix_m2_base"]
        tendance = com["tendance"]
        periurbain = prix_base < 30_000
        centre = com.geometry.centroid
        d_centre = _dist_plateau_km(centre.x, centre.y)
        for pt in _sample_in_polygon(com.geometry, par_commune):
            pid += 1
            d = _dist_plateau_km(pt.x, pt.y)
            # Gradient : -1.2% de prix par km de distance au Plateau (borné)
            grad = np.clip(1.0 - 0.012 * (d - d_centre), 0.6, 1.4)
            prix_m2 = prix_base * grad * np.random.lognormal(0, 0.13)
            surface = round(random.uniform(200, 1500), 0)

            ndvi = float(np.clip(np.random.normal(0.55 if periurbain else 0.22, 0.14), -0.1, 0.9))
            ndvi_delta = float(np.random.normal(-0.07 if periurbain else -0.02, 0.05))
            sar = float(np.clip(np.random.normal(0.6 if periurbain else 0.3, 0.2), 0, 1))
            pente = float(abs(np.random.normal(5, 3.5)))
            accessibilite = round(8 + d * 2.4 * np.random.uniform(0.9, 1.2), 1)  # min
            heat = 100 * float(np.clip(
                0.30 * min(-ndvi_delta * 6, 1) + 0.25 * sar
                + 0.25 * (tendance / 0.03) + 0.20 * max(0, 1 - accessibilite / 90),
                0, 1))

            rows.append({
                "code_parcelle": f"DJH-{com['commune'][:3].upper()}-{pid:05d}",
                "commune": com["commune"], "type_zone": com["type_zone"],
                "surface_m2": surface,
                "prix_m2_fcfa": round(prix_m2, 0),
                "prix_total_fcfa": round(prix_m2 * surface, 0),
                "dist_plateau_km": round(d, 2),
                "ndvi_moyen": round(ndvi, 3),
                "ndvi_delta_6m": round(ndvi_delta, 3),
                "changement_sar": round(sar, 3),
                "pente_moyenne_deg": round(pente, 2),
                "part_pente_sup15": round(float(np.clip((pente - 8) / 20, 0, 1)), 3),
                "risque_inondation": round(float(np.clip(np.random.beta(2, 5), 0, 1)), 3),
                "accessibilite_min": accessibilite,
                "speculation_heat": round(heat, 1),
                "viabilise": random.random() < 0.55,
                "geometry": pt,
            })
    gdf = gpd.GeoDataFrame(rows, crs=CRS_DISPLAY)
    logger.success(f"[GA] {len(gdf)} parcelles générées (gradient spatial de prix).")
    return gdf


# ---------------------------------------------------------------------------
# 3. POIs et voirie réels (OSM)
# ---------------------------------------------------------------------------
def fetch_pois() -> gpd.GeoDataFrame:
    """Récupère les vrais POIs OSM du Grand Abidjan et les classe par famille."""
    import osmnx as ox

    gdf = ox.features_from_bbox(GRAND_ABIDJAN_BBOX, tags=POI_TAGS)
    if gdf.empty:
        return gdf
    gdf = gdf.reset_index()

    def _type(r):
        for k in ("amenity", "shop"):
            if k in r and isinstance(r[k], str):
                return r[k]
        return "autre"

    gdf["poi_type"] = gdf.apply(_type, axis=1)
    gdf["famille"] = gdf["poi_type"].map(POI_FAMILLE).fillna("Autre")
    gdf["nom"] = gdf.get("name")
    gdf["geometry"] = gdf.geometry.centroid  # points pour affichage
    gdf = gdf[["famille", "poi_type", "nom", "geometry"]].to_crs(CRS_DISPLAY)
    logger.success(f"[GA] {len(gdf)} POIs réels — {gdf['famille'].value_counts().to_dict()}")
    return gdf


def fetch_major_roads() -> gpd.GeoDataFrame:
    """Récupère les grandes voies (autoroutes, nationales, primaires) OSM."""
    import osmnx as ox

    try:
        gdf = ox.features_from_bbox(
            GRAND_ABIDJAN_BBOX,
            tags={"highway": ["motorway", "trunk", "primary", "secondary"]})
        gdf = gdf[gdf.geometry.type.isin(["LineString", "MultiLineString"])].reset_index()
        gdf["classe"] = gdf["highway"].astype(str)
        gdf = gdf[["classe", "geometry"]].to_crs(CRS_DISPLAY)
        logger.success(f"[GA] {len(gdf)} tronçons de grandes voies.")
        return gdf
    except Exception as exc:
        logger.warning(f"[GA] Voirie non récupérée ({exc}).")
        return gpd.GeoDataFrame(columns=["classe", "geometry"], crs=CRS_DISPLAY)


# ---------------------------------------------------------------------------
# 4. Signaux spéculatifs synthétiques (arrêtés, relevés terrain)
# ---------------------------------------------------------------------------
def generate_arretes(communes: gpd.GeoDataFrame, n: int = 40) -> gpd.GeoDataFrame:
    """Simule des arrêtés de lotissement / ZUP récents (points géolocalisés)."""
    from datetime import datetime, timedelta
    rows, today = [], datetime.utcnow()
    for i in range(n):
        com = communes.sample(1).iloc[0]
        p = _sample_in_polygon(com.geometry, 1)
        if not p:
            continue
        rows.append({
            "reference": f"ARR-2026-{i:03d}",
            "type_acte": random.choice(["lotissement", "ZUP", "voirie", "DUP"]),
            "commune": com["commune"],
            "date_publication": today - timedelta(days=random.randint(1, 180)),
            "resume": f"Projet d'aménagement à {com['commune']}.",
            "geometry": p[0],
        })
    return gpd.GeoDataFrame(rows, crs=CRS_DISPLAY)


def generate_releves(parcelles: gpd.GeoDataFrame, n: int = 120) -> gpd.GeoDataFrame:
    """Simule des relevés terrain (ground truth) des équipes Djiland."""
    sample = parcelles.sample(n=min(n, len(parcelles)), random_state=2).copy()
    sample["agent"] = [random.choice(["Koffi", "Aya", "Traoré", "Diomandé", "N'Guessan"])
                       for _ in range(len(sample))]
    sample["qualite_sol"] = [random.choice(["sableux", "argileux", "latéritique", "rocheux"])
                             for _ in range(len(sample))]
    sample["vue"] = [random.choice(["lagune", "rue", "dégagée", "obstruée"])
                     for _ in range(len(sample))]
    sample["nuisance_sonore"] = np.random.randint(1, 6, len(sample))
    sample["litige_foncier"] = np.random.random(len(sample)) < 0.12
    return sample[["code_parcelle", "commune", "agent", "qualite_sol", "vue",
                   "nuisance_sonore", "litige_foncier", "geometry"]]


# ---------------------------------------------------------------------------
# 5. Agrégats par commune (prix global par zone)
# ---------------------------------------------------------------------------
def aggregate_communes(communes: gpd.GeoDataFrame,
                       parcelles: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Calcule prix moyen/médian au m², heat moyen et n parcelles par commune."""
    agg = parcelles.groupby("commune").agg(
        prix_m2_moyen=("prix_m2_fcfa", "mean"),
        prix_m2_median=("prix_m2_fcfa", "median"),
        prix_m2_min=("prix_m2_fcfa", "min"),
        prix_m2_max=("prix_m2_fcfa", "max"),
        heat_moyen=("speculation_heat", "mean"),
        ndvi_moyen=("ndvi_moyen", "mean"),
        access_moyen=("accessibilite_min", "mean"),
        n_parcelles=("prix_m2_fcfa", "size"),
    ).round(0).reset_index()
    out = communes.merge(agg, on="commune", how="left")
    logger.success("[GA] Agrégats par commune calculés.")
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def build(par_commune: int = 55) -> dict:
    """Construit et sauvegarde l'ensemble des couches du Grand Abidjan."""
    logger.info("=== CONSOLIDATION GRAND ABIDJAN ===")
    communes = fetch_communes()
    parcelles = generate_parcelles(communes, par_commune)
    communes_agg = aggregate_communes(communes, parcelles)
    arretes = generate_arretes(communes)
    releves = generate_releves(parcelles)

    d = GRAND_ABIDJAN_DIR

    # Couches réseau (réelles) : réutilise les téléchargements existants pour
    # éviter un re-fetch OSM lent (les POIs/voies changent rarement).
    if (d / "pois.parquet").exists():
        pois = gpd.read_parquet(d / "pois.parquet")
        logger.info(f"[GA] POIs réutilisés depuis le cache ({len(pois)}).")
    else:
        try:
            pois = fetch_pois()
        except Exception as exc:
            logger.warning(f"[GA] POIs indisponibles ({exc}).")
            pois = gpd.GeoDataFrame(columns=["famille", "poi_type", "nom", "geometry"], crs=CRS_DISPLAY)
    if (d / "roads.parquet").exists():
        roads = gpd.read_parquet(d / "roads.parquet")
        logger.info(f"[GA] Voies réutilisées depuis le cache ({len(roads)}).")
    else:
        roads = fetch_major_roads()
    communes_agg.to_parquet(d / "communes.parquet")
    parcelles.to_parquet(d / "parcelles.parquet")
    arretes.to_parquet(d / "arretes.parquet")
    releves.to_parquet(d / "releves.parquet")
    if not pois.empty:
        pois.to_parquet(d / "pois.parquet")
    if not roads.empty:
        roads.to_parquet(d / "roads.parquet")
    logger.success(f"[GA] Toutes les couches sauvegardées dans {d}")

    return {"communes": communes_agg, "parcelles": parcelles, "pois": pois,
            "roads": roads, "arretes": arretes, "releves": releves}


if __name__ == "__main__":
    build()
