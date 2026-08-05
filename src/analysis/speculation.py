"""
Speculation Heat Index — le signal d'avance sur la spéculation.

Score hybride 0-100 combinant les signaux avant-coureurs d'une flambée des prix :
  1. Proximité d'arrêtés de voirie/lotissement récents (< 500 m).
  2. Baisse du NDVI (déforestation / terrassement précoce).
  3. Détection de changement radar (nouveaux chantiers).
  4. Hausse récente des prix scrapés dans un rayon de 500 m.

Plus le score est élevé, plus la zone est « chaude » avant que l'info ne devienne
publique. C'est le cœur de l'avantage concurrentiel de Djiland.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger

# Pondérations des composantes (somme = 1)
WEIGHTS = {
    "arretes": 0.30,
    "ndvi_drop": 0.25,
    "sar_change": 0.25,
    "prix_trend": 0.20,
}


def _minmax(s: pd.Series) -> pd.Series:
    """Normalisation min-max robuste (0-1), tolérante aux séries constantes."""
    lo, hi = s.min(), s.max()
    if hi - lo < 1e-9:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - lo) / (hi - lo)


def compte_arretes_proches(parcelles: pd.DataFrame, arretes: pd.DataFrame,
                           rayon_m: float = 500.0) -> pd.Series:
    """Nombre d'arrêtés publics récents dans `rayon_m` de chaque parcelle.

    Reprojection en UTM 30N pour un rayon métrique exact.
    """
    import geopandas as gpd
    from shapely.geometry import Point

    if arretes.empty:
        return pd.Series(np.zeros(len(parcelles)), index=parcelles.index)

    gp = gpd.GeoDataFrame(
        parcelles.copy(),
        geometry=gpd.points_from_xy(parcelles["lon"], parcelles["lat"]),
        crs="EPSG:4326").to_crs(32630)
    ga = gpd.GeoDataFrame(
        arretes.copy(),
        geometry=gpd.points_from_xy(arretes["lon"], arretes["lat"]),
        crs="EPSG:4326").to_crs(32630)

    counts = []
    for geom in gp.geometry:
        counts.append(int((ga.distance(geom) <= rayon_m).sum()))
    return pd.Series(counts, index=parcelles.index)


def prix_trend_local(prix: pd.DataFrame, quartier: str, mois: int = 6) -> float:
    """Pente relative des prix au m² d'un quartier sur les `mois` derniers mois."""
    sub = prix[prix["quartier"] == quartier].copy()
    if sub.empty:
        return 0.0
    sub = sub.sort_values("date_annonce")
    recent = sub[sub["date_annonce"] >= sub["date_annonce"].max() - pd.Timedelta(days=30 * mois)]
    if len(recent) < 3:
        return 0.0
    x = (recent["date_annonce"] - recent["date_annonce"].min()).dt.days.values
    y = recent["prix_m2_fcfa"].values
    pente = np.polyfit(x, y, 1)[0]           # FCFA/m² par jour
    return float(pente / (y.mean() + 1e-6))  # pente relative


def compute_heat_index(parcelles: pd.DataFrame, indicateurs: pd.DataFrame,
                       arretes: pd.DataFrame, prix: pd.DataFrame) -> pd.DataFrame:
    """Calcule le Speculation Heat Index (0-100) par parcelle.

    Args:
        parcelles: DataFrame avec [code_parcelle, quartier, lon, lat].
        indicateurs: avec [code_parcelle, ndvi_delta_6m, changement_sar].
        arretes: arrêtés publics géolocalisés [lon, lat, date_publication].
        prix: historique de prix [quartier, prix_m2_fcfa, date_annonce].

    Returns:
        DataFrame [code_parcelle, quartier, speculation_heat] trié décroissant.
    """
    df = parcelles.merge(
        indicateurs[["code_parcelle", "ndvi_delta_6m", "changement_sar"]],
        on="code_parcelle", how="left")

    df["n_arretes"] = compte_arretes_proches(df, arretes)
    df["prix_trend"] = df["quartier"].map(
        lambda q: prix_trend_local(prix, q)).fillna(0.0)

    # Composantes normalisées (baisse NDVI => signal positif => on inverse le signe)
    c_arretes = _minmax(df["n_arretes"])
    c_ndvi = _minmax(-df["ndvi_delta_6m"].fillna(0))
    c_sar = _minmax(df["changement_sar"].fillna(0))
    c_prix = _minmax(df["prix_trend"])

    heat = 100 * (
        WEIGHTS["arretes"] * c_arretes
        + WEIGHTS["ndvi_drop"] * c_ndvi
        + WEIGHTS["sar_change"] * c_sar
        + WEIGHTS["prix_trend"] * c_prix
    )
    df["speculation_heat"] = heat.round(1)
    logger.info(f"[HEAT] Index calculé pour {len(df)} parcelles.")
    return df[["code_parcelle", "quartier", "speculation_heat",
               "n_arretes", "prix_trend"]].sort_values(
        "speculation_heat", ascending=False)
