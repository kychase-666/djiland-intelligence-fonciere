"""
Gestion des ANNOTATIONS cartographiques (dessins + notes) de l'utilisateur.

Permet de dessiner des points, lignes ou zones sur la carte et d'y attacher une
note. Les annotations sont persistées en GeoParquet et réaffichées à chaque
ouverture du dashboard (mémoire de terrain de l'équipe Djiland).
"""
from __future__ import annotations

from datetime import datetime

import geopandas as gpd
import pandas as pd
from loguru import logger
from shapely.geometry import shape

from config import CRS_DISPLAY, GRAND_ABIDJAN_DIR

NOTES_PATH = GRAND_ABIDJAN_DIR / "notes.parquet"
COLS = ["note", "categorie", "auteur", "date", "geometry"]

# Couleurs par catégorie de note (pour l'affichage carto)
CATEGORIE_COULEUR = {
    "Opportunité": "#1a9850",
    "Risque / litige": "#d73027",
    "À visiter": "#2166ac",
    "Négociation en cours": "#f39c12",
    "Autre": "#7f7f7f",
}


def load_notes() -> gpd.GeoDataFrame:
    """Charge les annotations enregistrées (GeoDataFrame vide si aucune)."""
    if NOTES_PATH.exists():
        try:
            return gpd.read_parquet(NOTES_PATH)
        except Exception as exc:
            logger.warning(f"[NOTES] Lecture impossible ({exc}).")
    return gpd.GeoDataFrame(columns=COLS, geometry="geometry", crs=CRS_DISPLAY)


def save_note(drawing_geojson: dict, note: str, categorie: str, auteur: str) -> None:
    """Ajoute une annotation (géométrie dessinée + note) et persiste sur disque.

    Args:
        drawing_geojson: feature GeoJSON renvoyée par l'outil de dessin (Leaflet).
        note: texte libre de la note.
        categorie: catégorie parmi CATEGORIE_COULEUR.
        auteur: nom de l'agent / utilisateur.
    """
    geom = shape(drawing_geojson["geometry"])
    gdf = load_notes()
    new = gpd.GeoDataFrame(
        [{"note": note, "categorie": categorie, "auteur": auteur,
          "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "geometry": geom}],
        crs=CRS_DISPLAY)
    out = pd.concat([gdf, new], ignore_index=True)
    gpd.GeoDataFrame(out, geometry="geometry", crs=CRS_DISPLAY).to_parquet(NOTES_PATH)
    logger.success(f"[NOTES] Annotation enregistrée ({categorie}).")


def delete_note(index: int) -> None:
    """Supprime l'annotation à l'index donné."""
    gdf = load_notes()
    if 0 <= index < len(gdf):
        gdf = gdf.drop(gdf.index[index]).reset_index(drop=True)
        gdf.to_parquet(NOTES_PATH)
        logger.info(f"[NOTES] Annotation #{index} supprimée.")


def clear_notes() -> None:
    """Efface toutes les annotations."""
    if NOTES_PATH.exists():
        NOTES_PATH.unlink()
        logger.info("[NOTES] Toutes les annotations effacées.")
