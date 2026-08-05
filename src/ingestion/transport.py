"""
Couche TRANSPORT STRUCTURANT — réseau actuel + projets futurs.

Le réseau routier fin est déjà couvert par la couche OSM `roads.parquet`. Ce
module ajoute les GRANDS AXES et surtout les PROJETS FUTURS (métro, autoroutes,
ponts, voie ferrée) qui font bondir le foncier bien avant leur livraison.

⚠️  Les tracés des projets futurs sont CURÉS (projets réels connus, mais
    géométries APPROXIMATIVES simplifiées) — à affiner avec les plans officiels
    (Ministère des Transports / AGEROUTE / SICF). Statuts : existant,
    en_construction, planifié.
"""
from __future__ import annotations

import geopandas as gpd
from loguru import logger
from shapely.geometry import LineString

from config import CRS_DISPLAY, GRAND_ABIDJAN_DIR

# Style par mode (couleur) et par statut (pointillé)
MODE_COULEUR = {
    "métro": "#9333ea", "train": "#78350f", "autoroute": "#1d4ed8",
    "route": "#0891b2", "pont": "#be185d",
}
STATUT_DASH = {"existant": None, "en_construction": "12,8", "planifié": "3,10"}

# Projets structurants (waypoints en (lon, lat))
PROJETS = [
    {"nom": "Métro d'Abidjan — Ligne 1 (Anyama ↔ Port-Bouët)", "mode": "métro",
     "statut": "en_construction",
     "pts": [(-4.050, 5.495), (-4.020, 5.420), (-4.025, 5.350), (-4.020, 5.320),
             (-4.010, 5.295), (-3.990, 5.300), (-3.930, 5.255)]},
    {"nom": "Autoroute du Nord A3 (Abidjan ↔ Yamoussoukro)", "mode": "autoroute",
     "statut": "existant",
     "pts": [(-4.020, 5.420), (-4.30, 5.80), (-4.80, 6.35), (-5.276, 6.827)]},
    {"nom": "Autoroute Yamoussoukro ↔ Bouaké", "mode": "autoroute",
     "statut": "en_construction",
     "pts": [(-5.276, 6.827), (-5.10, 7.20), (-5.03, 7.69)]},
    {"nom": "Autoroute Abidjan ↔ Grand-Bassam", "mode": "autoroute",
     "statut": "existant",
     "pts": [(-3.930, 5.255), (-3.85, 5.24), (-3.738, 5.211)]},
    {"nom": "Route côtière Grand-Bassam ↔ Assinie", "mode": "route",
     "statut": "en_construction",
     "pts": [(-3.738, 5.211), (-3.596, 5.20), (-3.45, 5.16), (-3.290, 5.130)]},
    {"nom": "Y4 — Grand contournement autoroutier d'Abidjan", "mode": "autoroute",
     "statut": "planifié",
     "pts": [(-4.230, 5.340), (-4.10, 5.49), (-3.95, 5.50), (-3.85, 5.42),
             (-3.80, 5.30), (-3.85, 5.24)]},
    {"nom": "Voie ferrée Abidjan ↔ Ouagadougou (SITARAIL)", "mode": "train",
     "statut": "existant",
     "pts": [(-4.010, 5.30), (-4.02, 5.42), (-4.15, 5.90), (-4.60, 6.60), (-5.03, 7.69)]},
    {"nom": "Axe A1 Abidjan ↔ Adzopé ↔ Abengourou", "mode": "route",
     "statut": "existant",
     "pts": [(-4.020, 5.420), (-3.90, 5.80), (-3.860, 6.107), (-3.65, 6.45), (-3.491, 6.729)]},
    {"nom": "Pont de Cocody (Alassane Ouattara)", "mode": "pont",
     "statut": "existant",
     "pts": [(-3.995, 5.315), (-3.985, 5.335)]},
    {"nom": "5e pont Yopougon ↔ Plateau", "mode": "pont", "statut": "planifié",
     "pts": [(-4.055, 5.325), (-4.020, 5.322)]},
]


def curated_transport() -> gpd.GeoDataFrame:
    """Construit la couche des grands axes et projets futurs (GeoDataFrame)."""
    rows = []
    for p in PROJETS:
        rows.append({
            "nom": p["nom"], "mode": p["mode"], "statut": p["statut"],
            "couleur": MODE_COULEUR.get(p["mode"], "#555"),
            "dash": STATUT_DASH.get(p["statut"]),
            "geometry": LineString(p["pts"]),
        })
    gdf = gpd.GeoDataFrame(rows, crs=CRS_DISPLAY)
    logger.success(f"[TRANSPORT] {len(gdf)} axes structurants "
                   f"({(gdf['statut'] != 'existant').sum()} projets futurs).")
    return gdf


def build_transport() -> gpd.GeoDataFrame:
    """Sauvegarde la couche transport structurant."""
    gdf = curated_transport()
    gdf.to_parquet(GRAND_ABIDJAN_DIR / "transport.parquet")
    logger.success("[TRANSPORT] Couche transport sauvegardée.")
    return gdf


if __name__ == "__main__":
    build_transport()
