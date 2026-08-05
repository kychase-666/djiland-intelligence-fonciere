"""
Ingestion RÉELLE d'une AOI (satellite Sentinel-2 + OpenStreetMap).

Contrairement au mode démo synthétique, ce module va chercher de VRAIES données :
  - Sentinel-2 L2A via le catalogue STAC public Earth Search (aucune clé).
    Lecture COG *fenêtrée* sur l'emprise (pas de téléchargement de la scène
    entière) puis calcul du NDVI réel, exporté en GeoTIFF.
  - POIs et voirie OpenStreetMap via osmnx / Overpass.

Persistance : tente PostGIS ; si indisponible, bascule automatiquement sur
GeoParquet dans data/processed (le code PostGIS reste intact).
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import rasterio
from loguru import logger
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from config import AOIS, MAX_CLOUD_COVER, PROCESSED_DIR, STAC_ENDPOINTS


def _best_sentinel2_item(aoi_name: str, days_back: int = 120):
    """Trouve la scène Sentinel-2 L2A la moins nuageuse sur l'AOI (STAC réel)."""
    import pystac_client

    bbox = AOIS[aoi_name]["bbox"]
    end, start = date.today(), date.today() - timedelta(days=days_back)
    catalog = pystac_client.Client.open(STAC_ENDPOINTS["earth_search"])
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{start.isoformat()}/{end.isoformat()}",
        query={"eo:cloud_cover": {"lt": MAX_CLOUD_COVER}},
    )
    items = list(search.items())
    if not items:
        logger.warning(f"[REAL/S2] Aucune scène < {MAX_CLOUD_COVER}% pour {aoi_name}.")
        return None
    item = min(items, key=lambda it: it.properties.get("eo:cloud_cover", 100))
    logger.info(f"[REAL/S2] {aoi_name}: scène {item.id} "
                f"({item.properties['eo:cloud_cover']:.1f}% nuages, "
                f"{item.datetime:%Y-%m-%d}).")
    return item


def _read_window(href: str, bbox_wgs84) -> tuple:
    """Lit une bande COG uniquement sur l'emprise (lecture fenêtrée réseau)."""
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                      GDAL_HTTP_MULTIRANGE="YES"):
        with rasterio.open(href) as src:
            l, b, r, t = transform_bounds("EPSG:4326", src.crs, *bbox_wgs84)
            win = from_bounds(l, b, r, t, src.transform)
            data = src.read(1, window=win).astype("float32")
            return data, src.window_transform(win), src.crs


def compute_real_ndvi(aoi_name: str) -> dict | None:
    """Calcule un NDVI RÉEL pour l'AOI et l'exporte en GeoTIFF.

    Returns:
        dict de statistiques (ndvi moyen/min/max, scène source) ou None.
    """
    item = _best_sentinel2_item(aoi_name)
    if item is None:
        return None
    bbox = AOIS[aoi_name]["bbox"]

    red, transform, crs = _read_window(item.assets["red"].href, bbox)
    nir, _, _ = _read_window(item.assets["nir"].href, bbox)

    # Réflectances S2 L2A (facteur d'échelle 10000) ; NaN où pas de donnée
    red, nir = red / 10000.0, nir / 10000.0
    denom = nir + red
    ndvi = np.where(denom == 0, np.nan, (nir - red) / denom).astype("float32")

    out_tif = PROCESSED_DIR / f"{aoi_name}_ndvi.tif"
    with rasterio.open(
        out_tif, "w", driver="GTiff", height=ndvi.shape[0], width=ndvi.shape[1],
        count=1, dtype="float32", crs=crs, transform=transform, nodata=np.nan,
    ) as dst:
        dst.write(ndvi, 1)

    stats = {
        "aoi": aoi_name,
        "scene_id": item.id,
        "date": f"{item.datetime:%Y-%m-%d}",
        "cloud_cover": round(item.properties.get("eo:cloud_cover", -1), 1),
        "ndvi_moyen": round(float(np.nanmean(ndvi)), 3),
        "ndvi_min": round(float(np.nanmin(ndvi)), 3),
        "ndvi_max": round(float(np.nanmax(ndvi)), 3),
        "pixels": int(ndvi.size),
        "geotiff": str(out_tif),
    }
    logger.success(f"[REAL/S2] NDVI réel exporté -> {out_tif} "
                   f"(moyen={stats['ndvi_moyen']}).")
    return stats


def fetch_real_osm(aoi_name: str) -> dict:
    """Récupère les vrais POIs OSM de l'AOI et les persiste (PostGIS→Parquet)."""
    from src.ingestion.osm import fetch_pois

    pois = fetch_pois(aoi_name)
    out = {"n_pois": len(pois)}
    if not pois.empty:
        path = PROCESSED_DIR / f"{aoi_name}_pois.parquet"
        pois.to_parquet(path)
        out["parquet"] = str(path)
        out["categories"] = pois["categorie"].value_counts().head(6).to_dict()
    return out


def persist_pois_postgis(pois) -> bool:
    """Tente d'insérer les POIs en PostGIS ; renvoie False si base indisponible."""
    try:
        from src.db.session import engine, init_db
        init_db()
        pois.to_postgis("pois", engine, if_exists="append", index=False)
        logger.success("[REAL] POIs insérés en PostGIS.")
        return True
    except Exception as exc:
        logger.warning(f"[REAL] PostGIS indisponible ({type(exc).__name__}) — "
                       f"repli GeoParquet déjà effectué.")
        return False


def run(aoi_name: str = "songon") -> dict:
    """Orchestre l'ingestion réelle complète d'une AOI."""
    logger.info(f"=== INGESTION RÉELLE : {aoi_name} ===")
    ndvi_stats = compute_real_ndvi(aoi_name)
    osm_stats = fetch_real_osm(aoi_name)
    return {"ndvi": ndvi_stats, "osm": osm_stats}


if __name__ == "__main__":
    import json
    result = run("songon")
    print(json.dumps(result, indent=2, ensure_ascii=False))
