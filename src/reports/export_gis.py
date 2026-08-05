"""
Mode furtif — export des couches SIG pour le terrain (QField / Maps.me).

Exporte les parcelles enrichies (+ communes, nuisances, lagune) en :
  - GeoPackage (.gpkg) : format natif de QField (multi-couches).
  - KML (.kml) : lisible par Maps.me et Google Earth (couche parcelles).

Écrit dans un fichier temporaire à chemin « propre » (/tmp) pour éviter le
bug de parsing GDAL sur les dossiers contenant espaces/caractères spéciaux,
puis renvoie les octets pour un bouton de téléchargement Streamlit.
"""
from __future__ import annotations

import os
import tempfile

import geopandas as gpd
from loguru import logger

from config import GRAND_ABIDJAN_DIR

# Champs simples exportés en KML (le driver KML tolère mal les types complexes)
KML_FIELDS = ["code_parcelle", "commune", "prix_m2_fcfa", "surface_m2",
              "speculation_heat", "rendement_locatif", "geometry"]


def export_layers(fmt: str = "GPKG") -> tuple[bytes, str]:
    """Exporte les couches dans le format demandé.

    Args:
        fmt: "GPKG" (QField) ou "KML" (Maps.me).

    Returns:
        (contenu binaire, nom de fichier suggéré).
    """
    ext = {"GPKG": "gpkg", "KML": "kml"}[fmt]
    fd, path = tempfile.mkstemp(suffix=f".{ext}", dir="/tmp")
    os.close(fd)
    os.remove(path)  # geopandas/GDAL crée le fichier lui-même

    parcelles = gpd.read_parquet(GRAND_ABIDJAN_DIR / "parcelles.parquet")

    if fmt == "GPKG":
        parcelles.to_file(path, layer="parcelles", driver="GPKG")
        for name in ("communes", "nuisances", "lagune"):
            src = GRAND_ABIDJAN_DIR / f"{name}.parquet"
            if src.exists():
                try:
                    gpd.read_parquet(src).to_file(path, layer=name, driver="GPKG")
                except Exception as exc:
                    logger.warning(f"[EXPORT] Couche {name} ignorée ({exc}).")
    else:  # KML : une couche de points parcelles avec attributs simples
        cols = [c for c in KML_FIELDS if c in parcelles.columns]
        parcelles[cols].to_file(path, driver="KML")

    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    logger.success(f"[EXPORT] {fmt} généré ({len(data)/1e6:.1f} Mo).")
    return data, f"djiland_grand_abidjan.{ext}"
