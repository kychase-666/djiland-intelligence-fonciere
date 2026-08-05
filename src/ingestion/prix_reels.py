"""
MOAT — Base de PRIX RÉELS propriétaires de Djiland.

Le vrai avantage concurrentiel n'est pas le scraping de sites protégés (bloqués,
contraires aux CGU), mais la donnée EXCLUSIVE que Djiland collecte :
  - ses transactions réelles (achats/ventes),
  - les prix relevés par ses agents sur le terrain,
  - les annonces vues via son réseau (courtiers, notaires),
  - un import CSV en masse.

Chaque observation est horodatée et alimente les analyses (tendances, alertes,
calculateur, évaluation). Dès qu'une zone atteint un seuil d'observations
réelles, le système utilise le PRIX RÉEL au lieu du prix calibré.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
from loguru import logger

from config import ALL_ZONES, GRAND_ABIDJAN_DIR

PRIX_REELS_PATH = GRAND_ABIDJAN_DIR / "prix_reels.parquet"
SEUIL_REEL = 3            # nb minimal d'observations pour utiliser le prix réel

COLONNES = ["date_obs", "type_source", "source", "commune", "quartier",
            "type_bien", "surface_m2", "prix_total_fcfa", "prix_m2_fcfa",
            "lon", "lat", "note"]

TYPES_SOURCE = ["Transaction Djiland", "Relevé agent terrain",
                "Annonce (courtier/notaire)", "Import CSV", "Autre"]
TYPES_BIEN = ["terrain nu", "terrain loti", "villa", "appartement", "immeuble", "autre"]


def load_prix_reels() -> pd.DataFrame:
    """Charge la base de prix réels (DataFrame vide si aucune donnée)."""
    if PRIX_REELS_PATH.exists():
        try:
            return pd.read_parquet(PRIX_REELS_PATH)
        except Exception as exc:
            logger.warning(f"[PRIX] Lecture impossible ({exc}).")
    return pd.DataFrame(columns=COLONNES)


def _finalize(obs: dict) -> dict:
    """Complète le prix au m² si dérivable et normalise la date."""
    if not obs.get("prix_m2_fcfa") and obs.get("prix_total_fcfa") and obs.get("surface_m2"):
        obs["prix_m2_fcfa"] = round(obs["prix_total_fcfa"] / obs["surface_m2"], 0)
    if not obs.get("date_obs"):
        obs["date_obs"] = datetime.utcnow().strftime("%Y-%m-%d")
    return obs


def add_observation(obs: dict) -> None:
    """Ajoute une observation de prix réel et persiste."""
    obs = _finalize({k: obs.get(k) for k in COLONNES})
    df = load_prix_reels()
    df = pd.concat([df, pd.DataFrame([obs])], ignore_index=True)
    df.to_parquet(PRIX_REELS_PATH)
    logger.success(f"[PRIX] Observation ajoutée ({obs['commune']} — "
                   f"{obs['prix_m2_fcfa']} F/m²). Total : {len(df)}.")


def import_csv(df_in: pd.DataFrame) -> int:
    """Importe un lot d'observations depuis un CSV (colonnes tolérantes).

    Colonnes attendues (souples) : commune, quartier, type_bien, surface_m2,
    prix_total_fcfa (ou prix_m2_fcfa), date_obs, source, lon, lat.

    Returns:
        Nombre de lignes importées valides.
    """
    df_in = df_in.rename(columns={c: c.strip().lower() for c in df_in.columns})
    rows = []
    for _, r in df_in.iterrows():
        obs = _finalize({
            "date_obs": str(r.get("date_obs", "")) or None,
            "type_source": r.get("type_source", "Import CSV"),
            "source": r.get("source", "csv"),
            "commune": r.get("commune"),
            "quartier": r.get("quartier"),
            "type_bien": r.get("type_bien", "terrain nu"),
            "surface_m2": _num(r.get("surface_m2")),
            "prix_total_fcfa": _num(r.get("prix_total_fcfa")),
            "prix_m2_fcfa": _num(r.get("prix_m2_fcfa")),
            "lon": _num(r.get("lon")), "lat": _num(r.get("lat")),
            "note": r.get("note"),
        })
        if obs["commune"] and obs["prix_m2_fcfa"]:
            rows.append(obs)
    if rows:
        df = pd.concat([load_prix_reels(), pd.DataFrame(rows)], ignore_index=True)
        df.to_parquet(PRIX_REELS_PATH)
    logger.success(f"[PRIX] Import CSV : {len(rows)} lignes valides.")
    return len(rows)


def _num(v):
    """Convertit en float en tolérant les espaces/virgules ; None si vide."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(str(v).replace(" ", "").replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return None


def resume_par_zone() -> pd.DataFrame:
    """Résumé des prix réels par commune (médiane, min, max, nb observations)."""
    df = load_prix_reels()
    if df.empty:
        return pd.DataFrame(columns=["commune", "n_obs", "prix_m2_median",
                                     "prix_m2_min", "prix_m2_max"])
    g = df.groupby("commune").agg(
        n_obs=("prix_m2_fcfa", "size"),
        prix_m2_median=("prix_m2_fcfa", "median"),
        prix_m2_min=("prix_m2_fcfa", "min"),
        prix_m2_max=("prix_m2_fcfa", "max")).round(0).reset_index()
    return g.sort_values("n_obs", ascending=False)


def prix_reference(commune: str, prix_calibre: float | None = None) -> dict:
    """Prix de référence d'une commune : RÉEL si assez d'observations, sinon calibré.

    Returns:
        dict {valeur, source ('réel'|'calibré'), n_obs}.
    """
    df = load_prix_reels()
    sub = df[df["commune"] == commune] if not df.empty else df
    n = len(sub)
    if n >= SEUIL_REEL:
        return {"valeur": float(sub["prix_m2_fcfa"].median()), "source": "réel", "n_obs": n}
    calibre = prix_calibre if prix_calibre is not None else ALL_ZONES.get(
        commune, {}).get("prix_m2", 0)
    return {"valeur": float(calibre), "source": "calibré", "n_obs": n}
