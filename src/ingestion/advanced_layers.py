"""
Couches AVANCÉES de la « Situation Room » foncière.

Ajoute au socle Grand Abidjan des couches comportementales / prospectives /
sensorielles :
  - Nuisances invisibles (NIMBY) : cimetières, décharges, industries, stations
    d'épuration, lignes haute tension — depuis OpenStreetMap (réel).
  - Vue lagune : proximité réelle de la lagune Ébrié (OSM).
  - Enrichissement des parcelles : malus nuisance, bonus vue, rendement locatif
    estimé, détection de chantiers (SAR), « vallées de rattrapage », convoitise.

Tout est mis en cache (GeoParquet) pour un chargement instantané du dashboard.
"""
from __future__ import annotations

import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from loguru import logger

from config import ALL_ZONES, CRS_DISPLAY, GRAND_ABIDJAN_BBOX, GRAND_ABIDJAN_DIR

warnings.filterwarnings("ignore")
np.random.seed(42)

# Type de nuisance -> (tags OSM, rayon d'impact en mètres, couleur d'auréole)
NUISANCES = {
    "Cimetière":          ({"landuse": "cemetery", "amenity": "grave_yard"}, 150, "#8e44ad"),
    "Décharge":           ({"landuse": "landfill"}, 500, "#7f1d1d"),
    "Industrie":          ({"landuse": "industrial", "man_made": "works"}, 300, "#b45309"),
    "Station d'épuration": ({"man_made": "wastewater_plant"}, 400, "#065f46"),
    "Ligne haute tension": ({"power": ["line", "minor_line"]}, 120, "#dc2626"),
}


def fetch_nuisances() -> gpd.GeoDataFrame:
    """Récupère les nuisances (NIMBY) depuis OSM, par catégorie (robuste)."""
    import osmnx as ox

    frames = []
    for nom, (tags, rayon, couleur) in NUISANCES.items():
        try:
            g = ox.features_from_bbox(GRAND_ABIDJAN_BBOX, tags=tags)
            if g.empty:
                continue
            g = g.reset_index()[["geometry"]].copy()
            g["type_nuisance"] = nom
            g["rayon_m"] = rayon
            g["couleur"] = couleur
            frames.append(g)
            logger.info(f"[NIMBY] {nom}: {len(g)} objets.")
        except Exception as exc:
            logger.warning(f"[NIMBY] {nom} indisponible ({type(exc).__name__}).")
    if not frames:
        return gpd.GeoDataFrame(columns=["geometry", "type_nuisance", "rayon_m", "couleur"],
                                geometry="geometry", crs=CRS_DISPLAY)
    out = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=CRS_DISPLAY)
    logger.success(f"[NIMBY] {len(out)} nuisances totales récupérées.")
    return out


def fetch_lagune() -> gpd.GeoDataFrame:
    """Récupère la lagune Ébrié par géocodage OSM (rapide et ciblé).

    On évite une requête bbox `natural=water` (trop lourde : tous les plans
    d'eau) au profit d'un géocodage direct de la lagune Ébrié.
    """
    import osmnx as ox

    for req in ("Lagune Ébrié, Côte d'Ivoire", "Ébrié Lagoon", "Lagune Ebrie, Cote d'Ivoire"):
        try:
            g = ox.geocode_to_gdf(req)
            geom = g.geometry.iloc[0]
            if geom.geom_type in ("Polygon", "MultiPolygon"):
                out = gpd.GeoDataFrame(
                    {"area_km2": [g.to_crs(32630).area.iloc[0] / 1e6]},
                    geometry=[geom], crs=CRS_DISPLAY)
                logger.success(f"[LAGUNE] Lagune Ébrié géocodée ({out['area_km2'].iloc[0]:.0f} km²).")
                return out
        except Exception:
            continue
    logger.warning("[LAGUNE] indisponible (géocodage échoué).")
    return gpd.GeoDataFrame(columns=["geometry", "area_km2"], geometry="geometry", crs=CRS_DISPLAY)


def enrich_parcelles(parcelles: gpd.GeoDataFrame, nuisances: gpd.GeoDataFrame,
                     lagune: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Ajoute les attributs avancés à chaque parcelle (calculs métriques UTM 30N).

    Colonnes ajoutées : dist_nuisance_m, malus_nuisance (0-0.4), dist_lagune_m,
    vue_lagune (bool), rendement_locatif (%), chantier_detecte (bool),
    rattrapage (bool), convoitise (0-100).
    """
    p = parcelles.to_crs(32630).copy()

    # --- Malus nuisance : distance à la nuisance la plus proche --------------
    if nuisances is not None and not nuisances.empty:
        nu = nuisances.to_crs(32630)
        near = gpd.sjoin_nearest(p[["code_parcelle", "geometry"]], nu[["geometry"]],
                                 distance_col="dist_nuisance_m")
        near = near.groupby("code_parcelle")["dist_nuisance_m"].min()
        p["dist_nuisance_m"] = p["code_parcelle"].map(near).fillna(9999).round(0)
    else:
        p["dist_nuisance_m"] = 9999
    # -40% au contact, décroissance linéaire jusqu'à 500 m
    p["malus_nuisance"] = (0.40 * (1 - p["dist_nuisance_m"] / 500)).clip(0, 0.40).round(3)

    # --- Vue lagune : proximité d'un grand plan d'eau -----------------------
    if lagune is not None and not lagune.empty:
        lag = lagune.to_crs(32630)
        union = lag.geometry.union_all() if hasattr(lag.geometry, "union_all") else lag.unary_union
        p["dist_lagune_m"] = p.geometry.distance(union).round(0)
    else:
        p["dist_lagune_m"] = 99999
    p["vue_lagune"] = p["dist_lagune_m"] < 300

    # --- Rendement locatif brut estimé (%) ----------------------------------
    # Heuristique calibrée : zones bon marché = rendement élevé ; premium = bas.
    prix = p["prix_m2_fcfa"].clip(upper=300_000)
    rendement = (4.5 + (1 - prix / 300_000) * 5.5
                 + (p["speculation_heat"] - 45) * 0.02
                 - p["malus_nuisance"] * 3.0
                 + np.random.normal(0, 0.4, len(p)))
    p["rendement_locatif"] = rendement.clip(3.0, 11.0).round(1)

    # --- Détection de chantiers (signal radar Sentinel-1) -------------------
    p["chantier_detecte"] = p["changement_sar"] > 0.72

    # --- Vallées de rattrapage : parcelle froide cernée de chaud ------------
    buf = p[["code_parcelle", "geometry"]].copy()
    buf["geometry"] = buf.geometry.buffer(800)
    j = gpd.sjoin(buf, p[["speculation_heat", "geometry"]], predicate="intersects")
    nbr = j.groupby("code_parcelle")["speculation_heat"].mean()
    p["heat_voisinage"] = p["code_parcelle"].map(nbr).fillna(p["speculation_heat"])
    p["rattrapage"] = (p["speculation_heat"] < p["heat_voisinage"] - 15) & (p["heat_voisinage"] > 55)

    # --- Indice de convoitise (proxy honnête, pas de scraping WhatsApp/FB) --
    conv = (0.55 * p["speculation_heat"]
            + 0.25 * (p["heat_voisinage"])
            + 0.20 * (p["rendement_locatif"] / 11 * 100))
    p["convoitise"] = conv.clip(0, 100).round(0)

    logger.success(f"[ADV] Parcelles enrichies : "
                   f"{int(p['vue_lagune'].sum())} vue lagune, "
                   f"{int(p['chantier_detecte'].sum())} chantiers, "
                   f"{int(p['rattrapage'].sum())} rattrapage.")
    return p.to_crs(CRS_DISPLAY)


def build_advanced() -> dict:
    """Construit les couches avancées + enrichit les parcelles (avec cache OSM)."""
    d = GRAND_ABIDJAN_DIR
    parcelles = gpd.read_parquet(d / "parcelles.parquet")

    nuisances = (gpd.read_parquet(d / "nuisances.parquet")
                 if (d / "nuisances.parquet").exists() else fetch_nuisances())
    lagune = (gpd.read_parquet(d / "lagune.parquet")
              if (d / "lagune.parquet").exists() else fetch_lagune())

    parcelles = enrich_parcelles(parcelles, nuisances, lagune)

    parcelles.to_parquet(d / "parcelles.parquet")
    if not nuisances.empty:
        nuisances.to_parquet(d / "nuisances.parquet")
    if not lagune.empty:
        lagune.to_parquet(d / "lagune.parquet")
    logger.success("[ADV] Couches avancées sauvegardées.")
    return {"parcelles": parcelles, "nuisances": nuisances, "lagune": lagune}


if __name__ == "__main__":
    build_advanced()
