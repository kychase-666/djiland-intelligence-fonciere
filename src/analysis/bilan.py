"""
BILAN PROMOTEUR — étude de faisabilité d'une opération immobilière.

Reconstitue le compte d'une opération : acquisition du terrain, construction
(ou viabilisation pour un lotissement), honoraires, imprévus, frais financiers,
frais commerciaux et chiffre d'affaires de vente. Produit la marge, le TRI du
projet, le prix de vente d'équilibre et une table de sensibilité.

Hypothèses simplificatrices (affichées à l'utilisateur) :
  - les ventes sont encaissées à la livraison (dernier mois) — approche prudente ;
  - les dépenses de travaux sont étalées uniformément sur la durée ;
  - le crédit est tiré progressivement (encours moyen ≈ 60 % du montant).
Les valeurs par défaut sont des ordres de grandeur à ajuster par l'utilisateur.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import numpy as np
import pandas as pd

# Programme -> (libellé, coef. de constructibilité m² plancher / m² terrain,
#               rendement de plan m² vendables / m² plancher, coût FCFA/m² standard)
PROGRAMMES = {
    "villas": ("Villas individuelles", 0.45, 0.88, 220_000),
    "r2": ("Petit immeuble R+2", 1.20, 0.82, 250_000),
    "r4": ("Immeuble R+4", 2.00, 0.80, 290_000),
    "lotissement": ("Lotissement viabilisé (vente de lots)", 0.0, 0.0, 0),
}
STANDINGS = {"Économique": 0.80, "Standard": 1.00, "Haut standing": 1.50}


@dataclass
class ParamsBilan:
    """Paramètres d'une opération (montants en FCFA)."""

    surface_terrain_m2: float
    prix_terrain_total: float
    prix_vente_m2: float                 # FCFA / m² vendable (ou m² de lot)
    programme: str = "r2"
    coef_constructibilite: float = 1.20
    rendement_plan: float = 0.82
    cout_construction_m2: float = 250_000
    vrd_m2_terrain: float = 6_000        # viabilisation / VRD par m² de terrain
    part_cessible_pct: float = 70.0      # lotissement : part vendue en lots
    frais_acquisition_pct: float = 10.0  # notaire, enregistrement, ACD (estimation)
    honoraires_pct: float = 8.0          # architecte, BET, géomètre
    imprevus_pct: float = 5.0
    frais_commerciaux_pct: float = 3.0
    part_credit_pct: float = 60.0
    taux_credit_pct: float = 9.0
    duree_mois: int = 24


def _surfaces(p: ParamsBilan) -> tuple[float, float]:
    """(surface de plancher, surface vendable) en m²."""
    if p.programme == "lotissement":
        return 0.0, p.surface_terrain_m2 * p.part_cessible_pct / 100
    plancher = p.surface_terrain_m2 * p.coef_constructibilite
    return plancher, plancher * p.rendement_plan


def _couts_hors_commerciaux(p: ParamsBilan) -> dict[str, float]:
    """Postes de coût indépendants du prix de vente."""
    plancher, _ = _surfaces(p)
    construction = plancher * p.cout_construction_m2
    vrd = p.surface_terrain_m2 * p.vrd_m2_terrain
    base_travaux = construction + vrd
    postes = {
        "Terrain": p.prix_terrain_total,
        "Frais d'acquisition": p.prix_terrain_total * p.frais_acquisition_pct / 100,
        "Construction": construction,
        "Viabilisation / VRD": vrd,
        "Honoraires & études": base_travaux * p.honoraires_pct / 100,
        "Imprévus": base_travaux * p.imprevus_pct / 100,
    }
    avant_fin = sum(postes.values())
    # Encours moyen de crédit ≈ 60 % du montant emprunté sur la durée
    emprunt = avant_fin * p.part_credit_pct / 100
    postes["Frais financiers"] = emprunt * p.taux_credit_pct / 100 * p.duree_mois / 12 * 0.6
    return postes


def _tri_annuel(flux: list[float]) -> float | None:
    """TRI annualisé d'une série de flux MENSUELS (bissection). None si indéfini."""
    flux = np.asarray(flux, dtype=float)
    if not (flux.min() < 0 < flux.max()):
        return None

    def van(r):
        return float(np.sum(flux / (1 + r) ** np.arange(len(flux))))

    bas, haut = -0.99, 1.0
    if van(bas) * van(haut) > 0:
        return None
    for _ in range(200):
        mil = (bas + haut) / 2
        if van(bas) * van(mil) <= 0:
            haut = mil
        else:
            bas = mil
    return (1 + (bas + haut) / 2) ** 12 - 1


def calculer_bilan(p: ParamsBilan) -> dict:
    """Calcule le bilan complet d'une opération.

    Returns:
        dict : surfaces, postes de coût, CA, coût de revient, marge (FCFA, % CA,
        % coût), fonds propres, rentabilité des fonds propres, TRI projet,
        prix d'équilibre et prix pour 20 % de marge.
    """
    plancher, vendable = _surfaces(p)
    postes = _couts_hors_commerciaux(p)
    ca = vendable * p.prix_vente_m2
    postes["Frais commerciaux"] = ca * p.frais_commerciaux_pct / 100
    cout_total = sum(postes.values())
    marge = ca - cout_total

    hors_comm = cout_total - postes["Frais commerciaux"]
    c = p.frais_commerciaux_pct / 100

    def prix_pour_marge(m: float) -> float | None:
        denom = vendable * (1 - c - m)
        return hors_comm / denom if vendable > 0 and denom > 0 else None

    # Flux mensuels du projet AVANT financement (pour le TRI projet)
    d = max(int(p.duree_mois), 2)
    travaux = (postes["Construction"] + postes["Viabilisation / VRD"]
               + postes["Honoraires & études"] + postes["Imprévus"])
    flux = [-(postes["Terrain"] + postes["Frais d'acquisition"])]
    flux += [-travaux / (d - 1)] * (d - 1)
    flux.append(ca - postes["Frais commerciaux"])

    tri = _tri_annuel(flux)
    emprunt = (cout_total - postes["Frais financiers"] - postes["Frais commerciaux"]) \
        * p.part_credit_pct / 100
    fonds_propres = cout_total - emprunt
    return {
        "surface_plancher_m2": plancher,
        "surface_vendable_m2": vendable,
        "postes": postes,
        "chiffre_affaires": ca,
        "cout_revient": cout_total,
        "marge": marge,
        "marge_pct_ca": marge / ca * 100 if ca else None,
        "marge_pct_cout": marge / cout_total * 100 if cout_total else None,
        "emprunt": emprunt,
        "fonds_propres": fonds_propres,
        "rentabilite_fonds_propres_pct": marge / fonds_propres * 100 if fonds_propres > 0 else None,
        "tri_projet_pct": tri * 100 if tri is not None else None,
        "prix_equilibre_m2": prix_pour_marge(0.0),
        "prix_marge20_m2": prix_pour_marge(0.20),
        "cout_revient_m2_vendable": cout_total / vendable if vendable else None,
    }


def sensibilite(p: ParamsBilan, variations=(-15, -10, -5, 0, 5, 10, 15)) -> pd.DataFrame:
    """Marge (% du CA) selon les variations du prix de vente et du coût de construction.

    Lignes = variation du coût de construction (ou VRD pour un lotissement),
    colonnes = variation du prix de vente.
    """
    lignes = {}
    for dc in variations:
        q = replace(p, cout_construction_m2=p.cout_construction_m2 * (1 + dc / 100),
                    vrd_m2_terrain=p.vrd_m2_terrain * (1 + dc / 100)
                    if p.programme == "lotissement" else p.vrd_m2_terrain)
        lignes[f"{dc:+d} %"] = {
            f"{dv:+d} %": calculer_bilan(replace(q, prix_vente_m2=p.prix_vente_m2 * (1 + dv / 100)))
            ["marge_pct_ca"] for dv in variations}
    df = pd.DataFrame(lignes).T
    df.index.name = "Coût travaux"
    df.columns.name = "Prix de vente"
    return df


def params_vers_dict(p: ParamsBilan) -> dict:
    """Paramètres sérialisables (export)."""
    return asdict(p)
