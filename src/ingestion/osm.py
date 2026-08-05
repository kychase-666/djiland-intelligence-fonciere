"""
Ingestion des données vectorielles OpenStreetMap via `osmnx` / Overpass.

Récupère les POIs (écoles, marchés, transports, santé), le réseau routier et
les limites administratives, puis les prépare pour insertion en PostGIS.
OSM est sous licence ODbL : usage libre avec attribution.
"""
from __future__ import annotations

import json

import geopandas as gpd
from loguru import logger

from config import AOIS, CRS_DISPLAY

# Catégories de POIs pertinentes pour l'évaluation foncière
POI_TAGS = {
    "amenity": ["school", "marketplace", "hospital", "clinic", "university", "bank",
                "place_of_worship", "bus_station", "fuel"],
    "shop": ["supermarket", "mall"],
    "highway": ["bus_stop"],
    "public_transport": ["station", "stop_position"],
}


def fetch_pois(aoi_name: str) -> gpd.GeoDataFrame:
    """Télécharge les POIs OSM d'une AOI et normalise les colonnes.

    Args:
        aoi_name: clé d'AOI de config.AOIS.

    Returns:
        GeoDataFrame WGS84 avec colonnes [categorie, nom, geometry, tags].
    """
    import osmnx as ox

    # osmnx >= 2.0 attend bbox = (left, bottom, right, top) = (W, S, E, N),
    # ce qui correspond directement au format de config.AOIS.
    bbox = AOIS[aoi_name]["bbox"]  # (W, S, E, N)
    gdf = ox.features_from_bbox(bbox, tags=POI_TAGS)
    if gdf.empty:
        logger.warning(f"[OSM] Aucun POI pour {aoi_name}.")
        return gdf

    def _categorie(row):
        for key in ("amenity", "shop", "public_transport", "highway"):
            if key in row and isinstance(row[key], str):
                return row[key]
        return "autre"

    gdf = gdf.reset_index()
    gdf["categorie"] = gdf.apply(_categorie, axis=1)
    gdf["nom"] = gdf.get("name")
    gdf["tags"] = gdf.apply(lambda r: json.dumps(
        {k: str(v) for k, v in r.items() if k in POI_TAGS}, ensure_ascii=False), axis=1)
    gdf = gdf[["categorie", "nom", "geometry", "tags"]].to_crs(CRS_DISPLAY)
    logger.info(f"[OSM] {aoi_name}: {len(gdf)} POIs récupérés.")
    return gdf


def fetch_road_network(aoi_name: str) -> gpd.GeoDataFrame:
    """Télécharge le réseau routier (drivable) d'une AOI en GeoDataFrame.

    Sert de base au calcul d'accessibilité (temps de trajet vers le Plateau).
    """
    import osmnx as ox

    bbox = AOIS[aoi_name]["bbox"]  # (W, S, E, N) — format osmnx >= 2.0
    graph = ox.graph_from_bbox(bbox, network_type="drive")
    edges = ox.graph_to_gdfs(graph, nodes=False)
    edges["categorie"] = "highway"
    edges["nom"] = edges.get("name")
    logger.info(f"[OSM] {aoi_name}: {len(edges)} tronçons routiers.")
    return edges.to_crs(CRS_DISPLAY)
