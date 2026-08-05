"""
Analyse topographique à partir du MNT (Modèle Numérique de Terrain).

- Pente (%) et masque des zones > 15% (non constructibles ou coûteuses).
- Indice de risque d'inondation dérivé de l'accumulation de drainage.
Tous les calculs supposent un MNT en projection métrique (UTM 30N).
"""
from __future__ import annotations

import numpy as np
from loguru import logger


def compute_slope(dem: np.ndarray, resolution_m: float = 30.0) -> np.ndarray:
    """Calcule la pente en degrés à partir d'un MNT métrique.

    Args:
        dem: altitude (m) sur grille régulière.
        resolution_m: taille de pixel en mètres (30 m pour Copernicus DEM).

    Returns:
        Pente en degrés (0-90).
    """
    dz_dy, dz_dx = np.gradient(dem.astype("float32"), resolution_m)
    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
    return np.degrees(slope_rad)


def slope_percent(slope_deg: np.ndarray) -> np.ndarray:
    """Convertit une pente en degrés vers un pourcentage (tan)."""
    return np.tan(np.radians(slope_deg)) * 100.0


def steep_mask(slope_deg: np.ndarray, seuil_pct: float = 15.0) -> np.ndarray:
    """Masque booléen des zones dont la pente dépasse `seuil_pct` %."""
    mask = slope_percent(slope_deg) > seuil_pct
    logger.info(f"[TERRAIN] {mask.mean()*100:.1f}% de surface au-dessus de {seuil_pct}%.")
    return mask


def flood_risk_index(dem: np.ndarray) -> np.ndarray:
    """Indice simplifié de risque d'inondation (0-1) basé sur la topographie.

    Approche proxy : les zones basses relativement à leur voisinage accumulent
    l'eau. On normalise l'inverse de l'altitude relative pour obtenir un score.
    Pour une hydrologie fine, brancher `richdem` (flow accumulation).
    """
    dem = dem.astype("float32")
    lo, hi = np.nanpercentile(dem, 5), np.nanpercentile(dem, 95)
    rel = np.clip((dem - lo) / (hi - lo + 1e-6), 0, 1)
    risk = 1.0 - rel
    return risk
