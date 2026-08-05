"""
Ingestion satellite via catalogues STAC GRATUITS.

Pourquoi pas SentinelHub ? Son quota gratuit est limité et demande une carte.
On utilise à la place :
  - Element84 Earth Search (AWS) : Sentinel-2 L2A + Landsat, SANS authentification.
  - Microsoft Planetary Computer : Sentinel-1 RTC + Copernicus DEM, token signé
    automatiquement (gratuit, sans carte bancaire).

Les données sont chargées directement en `xarray.DataArray` via `stackstac`,
puis peuvent être découpées en tuiles 512x512 (voir src/processing/tiling.py).
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from loguru import logger

from config import (
    AOIS,
    DEM_COLLECTION,
    MAX_CLOUD_COVER,
    REVISIT_DAYS,
    SENTINEL1_COLLECTION,
    SENTINEL2_COLLECTION,
    STAC_ENDPOINTS,
)


def _open_catalog(endpoint_key: str):
    """Ouvre un client STAC ; signe les requêtes pour Planetary Computer."""
    import planetary_computer
    import pystac_client

    modifier = (
        planetary_computer.sign_inplace
        if endpoint_key == "planetary_computer"
        else None
    )
    return pystac_client.Client.open(STAC_ENDPOINTS[endpoint_key], modifier=modifier)


def search_sentinel2(aoi_name: str, days_back: int = REVISIT_DAYS) -> list:
    """Recherche les scènes Sentinel-2 L2A récentes couvrant une AOI.

    Args:
        aoi_name: clé d'AOI définie dans config.AOIS.
        days_back: profondeur temporelle (jours) de la recherche.

    Returns:
        Liste d'items STAC (peut être vide si trop de nuages).
    """
    bbox = AOIS[aoi_name]["bbox"]
    end = date.today()
    start = end - timedelta(days=days_back)
    catalog = _open_catalog("earth_search")
    search = catalog.search(
        collections=[SENTINEL2_COLLECTION],
        bbox=bbox,
        datetime=f"{start.isoformat()}/{end.isoformat()}",
        query={"eo:cloud_cover": {"lt": MAX_CLOUD_COVER}},
    )
    items = list(search.items())
    logger.info(f"[S2] {aoi_name}: {len(items)} scènes < {MAX_CLOUD_COVER}% nuages.")
    return items


def load_stack(items: list, assets: list[str], resolution: int = 10):
    """Empile des items STAC en un `xarray.DataArray` (reprojeté UTM 30N).

    Args:
        items: items STAC issus d'une recherche.
        assets: bandes à charger, ex. ["red", "nir", "green", "scl"].
        resolution: résolution cible en mètres.

    Returns:
        xarray.DataArray (time, band, y, x) en EPSG:32630.
    """
    import stackstac

    stack = stackstac.stack(
        items,
        assets=assets,
        epsg=32630,               # UTM 30N pour des mesures métriques cohérentes
        resolution=resolution,
        chunksize=512,            # tuiles Dask alignées sur TILE_SIZE
    )
    return stack


def apply_cloud_mask(stack, scl_band: str = "scl"):
    """Masque les nuages/ombres Sentinel-2 à partir de la bande SCL.

    Les classes SCL 3 (ombre), 8/9 (nuages), 10 (cirrus) sont mises à NaN.
    """
    scl = stack.sel(band=scl_band)
    invalid = scl.isin([3, 8, 9, 10])
    masked = stack.where(~invalid)
    logger.info("[S2] Masque nuageux SCL appliqué.")
    return masked


def search_sentinel1(aoi_name: str, days_back: int = 180) -> list:
    """Recherche Sentinel-1 RTC (radar) — utile pour détecter les chantiers.

    Le radar traverse les nuages : idéal en saison des pluies ivoirienne pour
    repérer terrassements et nouvelles constructions (rétrodiffusion accrue).
    """
    bbox = AOIS[aoi_name]["bbox"]
    end = date.today()
    start = end - timedelta(days=days_back)
    catalog = _open_catalog("planetary_computer")
    search = catalog.search(
        collections=[SENTINEL1_COLLECTION],
        bbox=bbox,
        datetime=f"{start.isoformat()}/{end.isoformat()}",
    )
    items = list(search.items())
    logger.info(f"[S1] {aoi_name}: {len(items)} scènes radar.")
    return items


def download_dem(aoi_name: str):
    """Télécharge le MNT Copernicus 30m (drainage, pentes, risque inondation).

    Returns:
        xarray.DataArray d'altitude (m) reprojeté en UTM 30N.
    """
    bbox = AOIS[aoi_name]["bbox"]
    catalog = _open_catalog("planetary_computer")
    search = catalog.search(collections=[DEM_COLLECTION], bbox=bbox)
    items = list(search.items())
    if not items:
        logger.warning(f"[DEM] Aucun tuile MNT pour {aoi_name}.")
        return None
    import stackstac

    dem = stackstac.stack(items, epsg=32630, resolution=30).squeeze()
    logger.info(f"[DEM] MNT chargé pour {aoi_name}.")
    return dem


def ingest_all(aoi_name: str) -> dict:
    """Orchestre l'ingestion satellite complète d'une AOI (S2 + S1 + DEM)."""
    s2 = search_sentinel2(aoi_name)
    stack = None
    if s2:
        stack = apply_cloud_mask(
            load_stack(s2, assets=["red", "green", "blue", "nir", "scl"])
        )
    return {
        "sentinel2": stack,
        "sentinel1_items": search_sentinel1(aoi_name),
        "dem": download_dem(aoi_name),
    }
