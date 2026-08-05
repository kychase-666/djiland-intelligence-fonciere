"""
Configuration centrale du système IVOIRE LAND INTELLIGENCE.

Ce module regroupe TOUS les paramètres partagés : chemins, systèmes de
coordonnées, zones d'intérêt (AOI), sources de données et connexion base.
Aucune valeur codée en dur ailleurs dans le projet : tout passe par ici.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from shapely.geometry import box

# ---------------------------------------------------------------------------
# 1. Chemins du projet
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
MODELS_DIR = ROOT_DIR / "models"

for _p in (RAW_DIR, PROCESSED_DIR, SYNTHETIC_DIR, MODELS_DIR):
    _p.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT_DIR / ".env")

# ---------------------------------------------------------------------------
# 2. Systèmes de coordonnées
# ---------------------------------------------------------------------------
# UTM zone 30N : calculs métriques (surfaces, distances, pentes) en Côte d'Ivoire
CRS_METRIC = "EPSG:32630"
# WGS84 : affichage cartographique (Folium / Leaflet / DeckGL)
CRS_DISPLAY = "EPSG:4326"

# ---------------------------------------------------------------------------
# 3. Zones d'intérêt (Areas Of Interest)
# ---------------------------------------------------------------------------
# Emprises approximatives (lon_min, lat_min, lon_max, lat_max) en WGS84.
# Ajustez librement ; ces boîtes servent au découpage satellite et OSM.
AOIS: dict[str, dict] = {
    "abidjan_district": {
        "label": "District Autonome d'Abidjan",
        "bbox": (-4.20, 5.15, -3.75, 5.50),
        "priority": 1,
    },
    "yopougon": {"label": "Yopougon", "bbox": (-4.13, 5.32, -4.02, 5.40), "priority": 1},
    "songon": {"label": "Songon", "bbox": (-4.30, 5.28, -4.13, 5.40), "priority": 1},
    "anyama": {"label": "Anyama", "bbox": (-4.10, 5.48, -4.00, 5.56), "priority": 2},
    "dabou": {"label": "Dabou", "bbox": (-4.42, 5.30, -4.30, 5.40), "priority": 2},
    "grand_bassam": {"label": "Grand-Bassam", "bbox": (-3.78, 5.18, -3.65, 5.26), "priority": 2},
    "bouake": {"label": "Bouaké", "bbox": (-5.10, 7.65, -4.95, 7.75), "priority": 3},
    "daloa": {"label": "Daloa", "bbox": (-6.50, 6.85, -6.40, 6.93), "priority": 3},
}


def aoi_geometry(name: str):
    """Retourne la géométrie shapely (box, WGS84) d'une AOI référencée."""
    return box(*AOIS[name]["bbox"])


# ---------------------------------------------------------------------------
# 3bis. GRAND ABIDJAN — périmètre d'analyse exclusif (District Autonome)
# ---------------------------------------------------------------------------
# Emprise englobant les 13 communes du District Autonome d'Abidjan.
GRAND_ABIDJAN_BBOX = (-4.32, 5.15, -3.72, 5.58)  # (W, S, E, N)
PLATEAU_CBD = (-4.020, 5.325)                     # centre d'affaires (référence accès)

# 13 communes officielles + calibrage marché (prix médian FCFA/m², tendance
# mensuelle, centroïde de repli si le géocodage OSM échoue). Valeurs indicatives
# à recaler avec vos transactions réelles.
COMMUNES_GRAND_ABIDJAN: dict[str, dict] = {
    "Plateau":      {"prix_m2": 400_000, "tendance": 0.008, "centre": (-4.021, 5.323), "type": "affaires"},
    "Cocody":       {"prix_m2": 200_000, "tendance": 0.013, "centre": (-3.985, 5.360), "type": "résidentiel haut"},
    "Marcory":      {"prix_m2": 135_000, "tendance": 0.010, "centre": (-3.990, 5.300), "type": "résidentiel"},
    "Treichville":  {"prix_m2": 115_000, "tendance": 0.009, "centre": (-4.010, 5.295), "type": "mixte"},
    "Adjamé":       {"prix_m2": 95_000,  "tendance": 0.011, "centre": (-4.025, 5.350), "type": "commercial dense"},
    "Port-Bouët":   {"prix_m2": 70_000,  "tendance": 0.016, "centre": (-3.930, 5.255), "type": "côtier/aéroport"},
    "Attécoubé":    {"prix_m2": 62_000,  "tendance": 0.014, "centre": (-4.045, 5.335), "type": "populaire"},
    "Koumassi":     {"prix_m2": 72_000,  "tendance": 0.012, "centre": (-3.955, 5.290), "type": "populaire"},
    "Yopougon":     {"prix_m2": 55_000,  "tendance": 0.017, "centre": (-4.075, 5.345), "type": "populaire étendu"},
    "Bingerville":  {"prix_m2": 48_000,  "tendance": 0.026, "centre": (-3.895, 5.355), "type": "périurbain est"},
    "Abobo":        {"prix_m2": 40_000,  "tendance": 0.019, "centre": (-4.020, 5.420), "type": "populaire dense"},
    "Anyama":       {"prix_m2": 22_000,  "tendance": 0.028, "centre": (-4.050, 5.495), "type": "périurbain nord"},
    "Songon":       {"prix_m2": 18_000,  "tendance": 0.030, "centre": (-4.230, 5.340), "type": "périurbain ouest"},
}

# --- Zones côtières étendues (hors District) : corridor est + ouest ---------
# Ajoutées comme « zones de veille » (buffer autour du centre-ville, rayon_km)
# car leurs limites administratives OSM sont des départements trop vastes.
ZONES_COTIERES: dict[str, dict] = {
    "Jacqueville":    {"prix_m2": 15_000, "tendance": 0.030, "centre": (-4.413, 5.204), "type": "côtier ouest", "rayon_km": 4},
    "Grand-Bassam":   {"prix_m2": 35_000, "tendance": 0.024, "centre": (-3.738, 5.211), "type": "côtier historique", "rayon_km": 4},
    "Bonoua":         {"prix_m2": 12_000, "tendance": 0.028, "centre": (-3.596, 5.273), "type": "arrière-pays est", "rayon_km": 3.5},
    "Assinie-Mafia":  {"prix_m2": 28_000, "tendance": 0.038, "centre": (-3.290, 5.130), "type": "balnéaire premium", "rayon_km": 5},
    "Adiaké":         {"prix_m2": 14_000, "tendance": 0.030, "centre": (-3.304, 5.287), "type": "lagunaire est", "rayon_km": 3.5},
    "Aboisso":        {"prix_m2": 10_000, "tendance": 0.026, "centre": (-3.207, 5.467), "type": "carrefour est", "rayon_km": 4},
}

# --- Villes de l'intérieur (veille élargie) ---------------------------------
ZONES_INTERIEUR: dict[str, dict] = {
    "Yamoussoukro": {"prix_m2": 22_000, "tendance": 0.021, "centre": (-5.276, 6.827), "type": "capitale politique", "rayon_km": 6},
    "Adzopé":       {"prix_m2": 8_000,  "tendance": 0.026, "centre": (-3.860, 6.107), "type": "carrefour forestier", "rayon_km": 4},
    "Abengourou":   {"prix_m2": 9_000,  "tendance": 0.024, "centre": (-3.491, 6.729), "type": "capitale de l'Indénié", "rayon_km": 4},
}

# Ensemble des zones analysées (District + corridor côtier + intérieur)
ALL_ZONES: dict[str, dict] = {**COMMUNES_GRAND_ABIDJAN, **ZONES_COTIERES, **ZONES_INTERIEUR}

# Zone de veille spéculative : 100 km autour d'Assinie (corridor balnéaire est)
ASSINIE_CENTER = (-3.290, 5.130)      # (lon, lat)
VEILLE_RADIUS_KM = 100

# --- Quartiers indicatifs par commune (facteur de prix vs médiane communale) -
# Sert au calculateur. Facteur 1.0 = médiane de la commune ; >1 = prime.
QUARTIERS: dict[str, dict] = {
    "Cocody": {"Riviera": 1.35, "Angré": 1.15, "Deux-Plateaux": 1.28, "Cocody-Centre": 1.10,
               "Palmeraie": 1.20, "Danga": 1.30, "Faya (périphérie)": 0.80},
    "Bingerville": {"Centre-ville": 1.15, "Cité": 1.00, "Adjin": 0.90, "Gbagba": 0.82,
                    "Anga (nouveau)": 0.75, "Bord lagune": 1.28},
    "Yopougon": {"Niangon": 1.05, "Selmer": 1.12, "Sicogi": 1.00, "Toits Rouges": 0.95,
                 "Ananeraie": 0.90, "Maroc": 0.85},
    "Marcory": {"Zone 4": 1.40, "Biétry": 1.35, "Résidentiel": 1.10, "Anoumabo": 0.80},
    "Plateau": {"Centre des affaires": 1.20, "Cité administrative": 1.00},
    "Abobo": {"Abobo-Centre": 1.05, "Avocatier": 1.10, "Anonkoua-Kouté": 0.90, "Sagbé": 0.85},
    "Port-Bouët": {"Vridi": 1.20, "Gonzagueville": 0.90, "Aéroport": 1.10, "Adjouffou": 0.85},
    "Assinie-Mafia": {"Assinie-France (bord mer)": 1.65, "Assouindé": 1.25,
                      "Assinie-Mafia village": 1.00, "Arrière-lagune": 0.70},
    "Jacqueville": {"Bord de mer": 1.50, "Centre": 1.10, "Avagou": 0.85, "Arrière-pays": 0.70},
    "Grand-Bassam": {"Quartier France (historique)": 1.40, "Centre": 1.05,
                     "Moossou": 0.90, "Périphérie": 0.75},
    "Yamoussoukro": {"Millionnaire": 1.35, "Habitat": 1.10, "Morofè": 0.95,
                     "N'Zuessy": 0.90, "Kokrenou": 0.80},
}
# Zones génériques utilisées si la commune n'a pas de quartiers listés
QUARTIERS_GENERIQUES = {"Prime / centre": 1.25, "Standard": 1.00, "Périphérie": 0.78}

# Répertoire dédié aux données consolidées du Grand Abidjan
GRAND_ABIDJAN_DIR = DATA_DIR / "grand_abidjan"
GRAND_ABIDJAN_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 4. Sources satellite (STAC gratuit — pas de compte payant requis)
# ---------------------------------------------------------------------------
STAC_ENDPOINTS = {
    # Element84 Earth Search : Sentinel-2 L2A, Landsat, aucune authentification
    "earth_search": "https://earth-search.aws.element84.com/v1",
    # Microsoft Planetary Computer : Sentinel-1 RTC, Copernicus DEM, gratuit (token auto)
    "planetary_computer": "https://planetarycomputer.microsoft.com/api/stac/v1",
}

SENTINEL2_COLLECTION = "sentinel-2-l2a"
SENTINEL1_COLLECTION = "sentinel-1-rtc"          # Planetary Computer
LANDSAT_COLLECTION = "landsat-c2-l2"             # Earth Search
DEM_COLLECTION = "cop-dem-glo-30"                # Copernicus DEM 30m (Planetary Computer)

MAX_CLOUD_COVER = 20          # % de couverture nuageuse maximale tolérée
REVISIT_DAYS = 14             # cadence d'ingestion satellite (2 semaines)
TILE_SIZE = 512               # taille des tuiles de traitement (px)

# ---------------------------------------------------------------------------
# 5. Scraping (voir src/ingestion/scraping.py pour la note légale)
# ---------------------------------------------------------------------------
SCRAPING_SOURCES = {
    "jumia_deals": {
        "enabled": True,
        "base_url": "https://deals.jumia.ci",
        "respect_robots": True,
        "min_delay_s": 4.0,      # délai minimum entre requêtes (politesse)
    },
    # Désactivé par défaut : le scraping de Facebook viole ses CGU.
    "facebook_marketplace": {"enabled": False, "note": "Interdit par les CGU Facebook"},
}

# ---------------------------------------------------------------------------
# 6. Base de données PostGIS
# ---------------------------------------------------------------------------
DB_USER = os.getenv("POSTGRES_USER", "djiland")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "djiland")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "ivoire_land")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Mode démo : True => utilise les données synthétiques ; False => vraies API
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
