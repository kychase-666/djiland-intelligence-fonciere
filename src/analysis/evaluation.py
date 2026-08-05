"""
Moteur d'ÉVALUATION TEMPORELLE d'un terrain (passé → présent → futur).

Reconstitue la trajectoire de valeur d'un terrain sur ±5 ans :
  - Passé : valeur estimée il y a 1, 3, 5 ans (rétro-projection du prix actuel).
  - Futur : projection à 1, 3, 5 ans, ACCÉLÉRÉE par deux moteurs spéculatifs :
      • proximité d'un futur transport (métro, autoroute, pont) — prime jusqu'à +6 pts/an,
      • intensité spéculative locale (Speculation Heat) — prime jusqu'à +4 pts/an.

⚠️  Modèle indicatif à taux borné et décélérant (la spéculation ne compose pas
    à l'infini). Ne garantit aucun prix — à recaler avec vos transactions réelles.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from loguru import logger

from config import ALL_ZONES, GRAND_ABIDJAN_DIR

ANNUAL_CAP = 0.25      # taux annuel maximum (25%) pour rester crédible
ANNUAL_FLOOR = 0.04    # plancher (4%)
FUTURE_CAP = 0.34      # taux futur max une fois les primes ajoutées
HORIZONS = [-5, -3, -1, 0, 1, 3, 5]


def _annual_rate(tendance_mensuelle: float) -> float:
    """Convertit la tendance mensuelle en taux annuel borné et crédible."""
    brut = (1 + tendance_mensuelle) ** 12 - 1
    return float(np.clip(brut, ANNUAL_FLOOR, ANNUAL_CAP))


def distance_future_transport_km(lon: float, lat: float) -> float:
    """Distance (km) au projet de transport futur le plus proche (0 si aucun)."""
    path = GRAND_ABIDJAN_DIR / "transport.parquet"
    if not path.exists():
        return 99.0
    t = gpd.read_parquet(path)
    futurs = t[t["statut"] != "existant"]
    if futurs.empty:
        return 99.0
    pt = gpd.GeoSeries([gpd.points_from_xy([lon], [lat])[0]], crs="EPSG:4326").to_crs(32630)
    lignes = futurs.to_crs(32630)
    return float(lignes.distance(pt.iloc[0]).min() / 1000.0)


def evaluate(zone: str, prix_m2_actuel: float, surface: float,
             heat: float = 50.0, lon: float | None = None,
             lat: float | None = None) -> dict:
    """Évalue la trajectoire de valeur d'un terrain sur ±5 ans.

    Args:
        zone: commune / zone (clé de ALL_ZONES).
        prix_m2_actuel: prix au m² estimé aujourd'hui (déjà ajusté quartier/viab).
        surface: surface du terrain (m²).
        heat: Speculation Heat local (0-100).
        lon, lat: position pour la prime « futur transport » (facultatif).

    Returns:
        dict avec taux, primes, distance transport et trajectoire annuelle.
    """
    cfg = ALL_ZONES.get(zone, {"tendance": 0.015})
    annual = _annual_rate(cfg["tendance"])
    annual_past = annual * 0.85          # marchés globalement plus calmes avant

    # Primes appliquées au FUTUR uniquement
    dkm = distance_future_transport_km(lon, lat) if lon is not None else 99.0
    prime_transport = float(np.clip(0.06 * (1 - dkm / 5.0), 0, 0.06)) if dkm < 5 else 0.0
    prime_heat = float(np.clip((heat - 50) / 100 * 0.08, 0, 0.04))
    annual_future = min(annual + prime_transport + prime_heat, FUTURE_CAP)

    annee0 = pd.Timestamp.utcnow().year
    traj = []
    for y in HORIZONS:
        if y < 0:
            p = prix_m2_actuel / (1 + annual_past) ** (-y)
        elif y == 0:
            p = prix_m2_actuel
        else:                             # futur : décélération progressive
            p, r = prix_m2_actuel, annual_future
            for _ in range(y):
                p *= (1 + r)
                r *= 0.95
        traj.append({"annee": annee0 + y, "horizon": y,
                     "prix_m2": round(p), "prix_total": round(p * surface)})

    return {
        "prix_m2_actuel": round(prix_m2_actuel),
        "taux_annuel_passe": round(annual_past * 100, 1),
        "taux_annuel_futur": round(annual_future * 100, 1),
        "prime_transport_pts": round(prime_transport * 100, 1),
        "prime_heat_pts": round(prime_heat * 100, 1),
        "distance_transport_futur_km": round(dkm, 1) if dkm < 90 else None,
        "trajectoire": traj,
    }
