"""
Calcul des indices spectraux et détection de changement.

- NDVI : densité du couvert végétal (agriculture/forêt vs sol nu/bâti).
- Différence de NDVI sur 6 mois : repère déforestation / terrassement précoce.
- Détection de changement radar (Sentinel-1) : nouveaux chantiers sous les nuages.
"""
from __future__ import annotations

import numpy as np
from loguru import logger


def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Calcule le NDVI = (NIR - RED) / (NIR + RED).

    Args:
        nir: bande proche infrarouge (float).
        red: bande rouge (float).

    Returns:
        Tableau NDVI dans [-1, 1] ; les divisions par ~0 renvoient NaN.
    """
    nir = nir.astype("float32")
    red = red.astype("float32")
    denom = nir + red
    ndvi = np.where(denom == 0, np.nan, (nir - red) / denom)
    return ndvi


def ndvi_from_stack(stack):
    """NDVI moyen temporel à partir d'un stack Sentinel-2 xarray (bandes nir/red)."""
    nir = stack.sel(band="nir")
    red = stack.sel(band="red")
    ndvi = (nir - red) / (nir + red)
    return ndvi.mean(dim="time", skipna=True)


def ndvi_change(ndvi_t0, ndvi_t1):
    """Différence de NDVI entre deux dates (t1 - t0).

    Une baisse marquée (< -0.15) signale une perte de végétation typique d'un
    début de chantier ou d'un défrichement à visée spéculative.
    """
    delta = ndvi_t1 - ndvi_t0
    logger.info("[NDVI] Carte de changement calculée (t1 - t0).")
    return delta


def sar_change_detection(vv_t0: np.ndarray, vv_t1: np.ndarray) -> np.ndarray:
    """Détection de changement radar par ratio log de rétrodiffusion VV.

    Le bâti et les surfaces terrassées augmentent la rétrodiffusion : un ratio
    log positif élevé indique une construction/terrassement récent, même par
    temps couvert (avantage clé en saison des pluies).

    Returns:
        Carte de score de changement (dB), positif = densification probable.
    """
    eps = 1e-6
    change = 10.0 * np.log10((vv_t1 + eps) / (vv_t0 + eps))
    return change


def zonal_mean(raster: np.ndarray, mask: np.ndarray) -> float:
    """Moyenne d'un raster sur les pixels d'un masque de parcelle (ignore NaN)."""
    vals = raster[mask]
    vals = vals[~np.isnan(vals)]
    return float(np.mean(vals)) if vals.size else float("nan")
