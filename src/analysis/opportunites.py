"""
CHASSEUR D'OPPORTUNITÉS — classe les parcelles selon leur intérêt d'achat.

Source unique du « score d'opportunité » et du verdict, utilisée à la fois par
l'onglet « 🎯 Opportunités » du dashboard et par le rapport PDF : une parcelle a
donc toujours le même verdict partout.

Barème (0-100) : rendement locatif (30) + intensité spéculative (25) + vallée
de rattrapage (20) + proximité d'un transport futur (15) + vue lagune (10),
moins les malus nuisance, inondation et lotissement en sursis. Un lotissement
annulé ou un litige foncier donne le verdict « À ÉVITER » (score 0).

⚠️  Les prix et statuts juridiques restent des estimations calibrées / démo :
    le classement aide à trier, il ne remplace pas la visite et le notaire.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from config import GRAND_ABIDJAN_DIR

# Clé de verdict -> (libellé, couleur hex, justification)
VERDICTS = {
    "evite": ("À ÉVITER", "#dc2626",
              "Situation juridique rédhibitoire (lotissement annulé ou litige foncier)."),
    "forte": ("OPPORTUNITÉ FORTE", "#16a34a", "Fort potentiel de plus-value, risques maîtrisés."),
    "interessant": ("INTÉRESSANT", "#1F6F5C", "Bon équilibre rendement / potentiel / risque."),
    "prudence": ("PRUDENCE", "#f59e0b", "Potentiel réel mais points de vigilance à lever."),
    "faible": ("FAIBLE INTÉRÊT", "#9ca3af", "Rendement/potentiel limités ou risques élevés."),
}


def _cle_depuis_score(score: float, evite: bool) -> str:
    """Traduit un score (et le drapeau juridique) en clé de verdict."""
    if evite:
        return "evite"
    if score >= 65:
        return "forte"
    if score >= 45:
        return "interessant"
    if score >= 25:
        return "prudence"
    return "faible"


def score_ligne(d: dict, dist_transport_km: float | None) -> tuple[float, str]:
    """Score d'opportunité et clé de verdict pour UNE parcelle (dict).

    Returns:
        (score 0-100, clé de verdict parmi VERDICTS).
    """
    statut = d.get("lotissement_statut")
    evite = statut == "Annulé" or bool(d.get("litige_parcelle"))
    s = 0.0
    s += min(d.get("rendement_locatif", 5) or 5, 11) / 11 * 30
    s += (d.get("speculation_heat", 50) or 50) / 100 * 25
    s += 20 if d.get("rattrapage") else 0
    if dist_transport_km is not None and dist_transport_km < 5:
        s += 15 * (1 - dist_transport_km / 5)
    s += 10 if d.get("vue_lagune") else 0
    s -= (d.get("malus_nuisance", 0) or 0) * 100 * 0.3
    s -= (d.get("risque_inondation", 0) or 0) * 10
    if statut == "En sursis":
        s -= 10
    s = 0.0 if evite else float(np.clip(s, 0, 100))
    return round(s, 1), _cle_depuis_score(s, evite)


def distances_transport_km(parcelles: gpd.GeoDataFrame) -> pd.Series:
    """Distance (km) de chaque parcelle au projet de transport FUTUR le plus proche."""
    path = GRAND_ABIDJAN_DIR / "transport.parquet"
    vide = pd.Series(99.0, index=parcelles.index)
    if not path.exists():
        return vide
    t = gpd.read_parquet(path)
    futurs = t[t["statut"] != "existant"]
    if futurs.empty:
        return vide
    lignes = futurs.to_crs(32630).geometry
    union = lignes.union_all() if hasattr(lignes, "union_all") else lignes.unary_union
    return (parcelles.to_crs(32630).geometry.distance(union) / 1000).round(2)


def _col(p: pd.DataFrame, nom: str, defaut) -> pd.Series:
    """Colonne si présente, sinon série constante (robustesse données)."""
    if nom in p.columns:
        return p[nom]
    return pd.Series(defaut, index=p.index)


def scorer(parcelles: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Ajoute dist_transport_km, score_opportunite et verdict (vectorisé)."""
    p = parcelles.copy()
    dist = distances_transport_km(p)
    statut = _col(p, "lotissement_statut", "Approuvé")
    litige = _col(p, "litige_parcelle", False).fillna(False).astype(bool)
    evite = (statut == "Annulé") | litige

    s = (_col(p, "rendement_locatif", 5).fillna(5).clip(upper=11) / 11 * 30
         + _col(p, "speculation_heat", 50).fillna(50) / 100 * 25
         + _col(p, "rattrapage", False).fillna(False).astype(bool) * 20
         + (15 * (1 - dist / 5)).where(dist < 5, 0)
         + _col(p, "vue_lagune", False).fillna(False).astype(bool) * 10
         - _col(p, "malus_nuisance", 0).fillna(0) * 100 * 0.3
         - _col(p, "risque_inondation", 0).fillna(0) * 10
         - (statut == "En sursis").astype(int) * 10)
    s = s.clip(0, 100).where(~evite, 0).round(1)

    cle = np.select([evite, s >= 65, s >= 45, s >= 25],
                    ["evite", "forte", "interessant", "prudence"], "faible")
    p["dist_transport_km"] = dist
    p["score_opportunite"] = s
    p["verdict_cle"] = cle
    p["verdict"] = [VERDICTS[k][0] for k in cle]
    return p


def rechercher(p: gpd.GeoDataFrame, budget_max: float, surface_min: float,
               surface_max: float, communes: list[str] | None = None,
               approuve_seul: bool = True, sans_litige: bool = True,
               sans_nuisance: bool = False, vue_lagune_seul: bool = False,
               rendement_min: float = 0.0,
               facteurs: dict[str, dict] | None = None) -> gpd.GeoDataFrame:
    """Filtre les parcelles scorées selon les critères et les classe.

    Args:
        p: parcelles déjà passées par `scorer()`.
        budget_max: prix total maximum (FCFA).
        facteurs: recalage des prix par commune issu des prix réels
            (voir prix_reels.facteurs_recalage) ; None = prix calibrés.

    Returns:
        Résultats triés du meilleur au moins bon score, avec colonnes
        prix_m2_retenu / prix_total_retenu / source_prix.
    """
    r = p.copy()
    facteurs = facteurs or {}
    f = r["commune"].map(lambda c: facteurs.get(c, {}).get("facteur", 1.0)).astype(float)
    r["prix_m2_retenu"] = (r["prix_m2_fcfa"] * f).round(0)
    r["prix_total_retenu"] = (r["prix_m2_retenu"] * r["surface_m2"]).round(0)
    r["source_prix"] = r["commune"].map(
        lambda c: f"réel ({facteurs[c]['n_obs']} obs.)" if c in facteurs else "calibré")

    masque = (r["prix_total_retenu"] <= budget_max) & r["surface_m2"].between(surface_min, surface_max)
    if communes:
        masque &= r["commune"].isin(communes)
    if approuve_seul:
        masque &= _col(r, "lotissement_statut", "Approuvé") == "Approuvé"
    if sans_litige:
        masque &= ~_col(r, "litige_parcelle", False).fillna(False).astype(bool)
    if sans_nuisance:
        masque &= _col(r, "malus_nuisance", 0).fillna(0) < 0.05
    if vue_lagune_seul:
        masque &= _col(r, "vue_lagune", False).fillna(False).astype(bool)
    if rendement_min > 0:
        masque &= _col(r, "rendement_locatif", 0).fillna(0) >= rendement_min
    return r[masque].sort_values(["score_opportunite", "rendement_locatif"],
                                 ascending=[False, False])
