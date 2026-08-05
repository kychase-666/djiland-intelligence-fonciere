"""
Score d'accessibilité pondérée : temps de trajet estimé vers le Plateau (CBD).

Construit un graphe routier OSM, pondère chaque arête par un temps de parcours
tenant compte d'un facteur d'embouteillage théorique par type de route, puis
calcule le plus court chemin (en temps) depuis chaque parcelle vers le Plateau.
"""
from __future__ import annotations

import numpy as np
from loguru import logger

# Plateau (centre d'affaires d'Abidjan) — destination de référence
PLATEAU_LATLON = (5.325, -4.020)

# Vitesses effectives (km/h) par type de voie, embouteillage théorique intégré
VITESSE_EFFECTIVE = {
    "motorway": 60, "trunk": 45, "primary": 30, "secondary": 22,
    "tertiary": 18, "residential": 14, "unclassified": 12, "default": 15,
}


def _edge_time_minutes(length_m: float, highway) -> float:
    """Temps de parcours (min) d'une arête selon sa longueur et son type."""
    if isinstance(highway, list):
        highway = highway[0]
    v = VITESSE_EFFECTIVE.get(highway, VITESSE_EFFECTIVE["default"])
    return (length_m / 1000.0) / v * 60.0


def build_time_weighted_graph(graph):
    """Ajoute un attribut `travel_time` (min) à chaque arête d'un graphe OSMnx."""
    import networkx as nx

    for u, v, k, data in graph.edges(keys=True, data=True):
        length = data.get("length", 0.0)
        data["travel_time"] = _edge_time_minutes(length, data.get("highway", "default"))
    logger.info("[ACCESS] Graphe pondéré par le temps de trajet théorique.")
    return graph


def accessibility_minutes(graph, points_latlon: list[tuple]) -> list[float]:
    """Temps de trajet (min) de chaque point vers le Plateau via le graphe.

    Args:
        graph: graphe routier OSMnx pondéré (`travel_time`).
        points_latlon: liste de (lat, lon) des parcelles.

    Returns:
        Liste des temps de trajet estimés en minutes (inf si non atteignable).
    """
    import networkx as nx
    import osmnx as ox

    dest = ox.nearest_nodes(graph, PLATEAU_LATLON[1], PLATEAU_LATLON[0])
    temps = []
    for lat, lon in points_latlon:
        try:
            src = ox.nearest_nodes(graph, lon, lat)
            t = nx.shortest_path_length(graph, src, dest, weight="travel_time")
        except (nx.NetworkXNoPath, Exception):
            t = float("inf")
        temps.append(round(t, 1))
    return temps


def haversine_fallback(points_latlon: list[tuple], vitesse_kmh: float = 20.0) -> list[float]:
    """Repli hors-ligne : estime le temps via distance à vol d'oiseau x 1.4.

    Utile quand le graphe OSM n'est pas disponible (mode démo/synthétique).
    """
    lat0, lon0 = PLATEAU_LATLON
    out = []
    for lat, lon in points_latlon:
        dlat = np.radians(lat - lat0)
        dlon = np.radians(lon - lon0)
        a = (np.sin(dlat / 2) ** 2
             + np.cos(np.radians(lat0)) * np.cos(np.radians(lat)) * np.sin(dlon / 2) ** 2)
        km = 6371 * 2 * np.arcsin(np.sqrt(a)) * 1.4  # facteur de sinuosité routière
        out.append(round(km / vitesse_kmh * 60, 1))
    return out
