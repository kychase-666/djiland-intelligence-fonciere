"""
Module JURIDIQUE & CADASTRAL — bouclier de sécurité foncière.

⚠️  AVERTISSEMENT CAPITAL :
-----------------------------------------------------------------------------
Ce module NE se connecte PAS aux registres officiels ivoiriens (IDUFCI, SIGFU,
DGI, MCLU) : ceux-ci exigent des comptes professionnels authentifiés et n'ont
pas d'API publique ouverte. Les champs « propriétaire », « IDUFCI » et « statut
de lotissement » produits ici sont des DONNÉES DE DÉMONSTRATION, calibrées mais
FICTIVES. Elles ne doivent JAMAIS servir de base à une transaction.

La vérification officielle passe obligatoirement par les portails ci-dessous.
Le code est structuré pour brancher ces sources réelles dès que Djiland
dispose des accès professionnels (voir les connecteurs stubs).
-----------------------------------------------------------------------------
"""
from __future__ import annotations

import random

import geopandas as gpd
import numpy as np
import pandas as pd
from loguru import logger

from config import ALL_ZONES, GRAND_ABIDJAN_DIR

random.seed(7)
np.random.seed(7)

# --- Portails officiels (points d'intégration réels) ------------------------
PORTAILS = {
    "IDUFCI": {"url": "https://idufci.construction.gouv.ci",
               "role": "Identifiant Unique du Foncier — lien parcelle ↔ administrations"},
    "SIGFU": {"url": "https://sigfu.gouv.ci",
              "role": "Système Intégré de Gestion du Foncier Urbain — suivi des dossiers"},
    "DGI État Foncier": {"url": "https://econsultation.dgi.gouv.ci",
                         "role": "État foncier officiel (propriétaire, hypothèques) — 3 000 FCFA"},
    "MCLU Lotissements": {"url": "https://www.construction.gouv.ci",
                          "role": "Vérification du statut d'approbation des lotissements"},
    "GUF": {"url": "https://www.construction.gouv.ci",
            "role": "Guichet Unique du Foncier — 73 guichets, démarches et pièces"},
}

# --- Statuts de lotissement -------------------------------------------------
STATUTS = {
    "Approuvé":  {"couleur": "#16a34a", "icone": "✅", "risque": "faible"},
    "En sursis": {"couleur": "#f59e0b", "icone": "⚠️", "risque": "élevé"},
    "Annulé":    {"couleur": "#dc2626", "icone": "❌", "risque": "rédhibitoire"},
}

# Probabilités de statut par profil de zone (le périurbain/côtier est plus risqué)
POIDS_STATUT = {
    "central":    [0.86, 0.10, 0.04],   # Approuvé, Sursis, Annulé
    "populaire":  [0.70, 0.20, 0.10],
    "peripherie": [0.50, 0.30, 0.20],
}


def _profil_zone(commune: str) -> str:
    """Classe une commune pour pondérer le risque de lotissement."""
    cfg = ALL_ZONES.get(commune, {})
    prix = cfg.get("prix_m2", 40_000)
    if prix >= 110_000:
        return "central"
    if prix >= 45_000:
        return "populaire"
    return "peripherie"


# ---------------------------------------------------------------------------
# Connecteurs officiels (STUBS — prêts à brancher avec des accès pro)
# ---------------------------------------------------------------------------
def connecteur_officiel(portail: str, **params) -> dict:
    """Point d'entrée générique vers un registre officiel (non connecté).

    Retourne un statut « non connecté » + l'URL de vérification manuelle. À
    remplacer par un vrai appel API/scraping authentifié quand les accès
    professionnels Djiland seront disponibles.
    """
    info = PORTAILS.get(portail, {})
    return {
        "portail": portail,
        "connecte": False,
        "url_verification": info.get("url"),
        "role": info.get("role"),
        "message": f"Vérification manuelle requise sur {info.get('url')} "
                   f"(intégration API à activer avec un compte professionnel).",
        "params": params,
    }


# ---------------------------------------------------------------------------
# Génération des données juridiques DÉMO + enrichissement des parcelles
# ---------------------------------------------------------------------------
def enrich_juridique(parcelles: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Ajoute les champs juridiques (DÉMO) et le score de sécurité juridique.

    Colonnes ajoutées : idufci_demo, lotissement_nom, lotissement_statut,
    acd, titre_foncier, litige_parcelle, score_juridique (0-100).
    """
    p = parcelles.copy()
    statuts, idufci, lots, acd, titres, litiges, scores = [], [], [], [], [], [], []

    # Numéro de lotissement stable par petit groupe de parcelles d'une commune
    compteur: dict[str, int] = {}
    for _, row in p.iterrows():
        com = row["commune"]
        profil = _profil_zone(com)
        statut = np.random.choice(list(STATUTS), p=POIDS_STATUT[profil])

        compteur[com] = compteur.get(com, 0)
        if random.random() < 0.15:            # nouveau lotissement de temps en temps
            compteur[com] += 1
        lot_nom = f"Lot. {com} n°{compteur[com]+1:02d}"

        # IDUFCI DÉMO — format plausible mais explicitement fictif
        idu = f"IDUFCI-DÉMO-{com[:3].upper()}-{random.randint(1000000, 9999999)}"

        # Attributs conditionnels au statut
        a_acd = random.random() < {"Approuvé": 0.80, "En sursis": 0.30, "Annulé": 0.05}[statut]
        a_titre = random.random() < {"Approuvé": 0.70, "En sursis": 0.35, "Annulé": 0.10}[statut]
        a_litige = random.random() < {"Approuvé": 0.05, "En sursis": 0.22, "Annulé": 0.45}[statut]

        statuts.append(statut); idufci.append(idu); lots.append(lot_nom)
        acd.append(a_acd); titres.append(a_titre); litiges.append(a_litige)
        scores.append(_score(statut, a_acd, a_litige, a_titre))

    p["idufci_demo"] = idufci
    p["lotissement_nom"] = lots
    p["lotissement_statut"] = statuts
    p["acd"] = acd
    p["titre_foncier"] = titres
    p["litige_parcelle"] = litiges
    p["score_juridique"] = scores
    logger.success(f"[JURID] Parcelles enrichies — "
                   f"{statuts.count('Approuvé')} approuvées, "
                   f"{statuts.count('En sursis')} en sursis, "
                   f"{statuts.count('Annulé')} annulées (DÉMO).")
    return p


def _score(statut: str, acd: bool, litige: bool, titre: bool) -> int:
    """Score de sécurité juridique 0-100 (barème défini par la demande)."""
    s = 0
    s += {"Approuvé": 40, "En sursis": 15, "Annulé": 0}[statut]  # lotissement approuvé
    s += 30 if acd else 0                                         # ACD existant
    s += 0 if litige else 20                                      # pas de litige connu
    s += 10 if titre else 0                                       # propriété identifiée
    return int(s)


def score_details(row) -> list[dict]:
    """Décompose le score juridique d'une parcelle (pour affichage widget)."""
    st = row["lotissement_statut"]
    return [
        {"critere": "Lotissement approuvé", "obtenu": {"Approuvé": 40, "En sursis": 15, "Annulé": 0}[st], "max": 40},
        {"critere": "ACD / concession définitive", "obtenu": 30 if row["acd"] else 0, "max": 30},
        {"critere": "Aucun litige connu", "obtenu": 0 if row["litige_parcelle"] else 20, "max": 20},
        {"critere": "Titre / propriété identifiée", "obtenu": 10 if row["titre_foncier"] else 0, "max": 10},
    ]


# ---------------------------------------------------------------------------
# Générateur de documents (RÉEL — guidance factuelle, pas de données fictives)
# ---------------------------------------------------------------------------
def documents_a_exiger(statut: str) -> list[str]:
    """Checklist des documents à exiger du vendeur selon le statut du lotissement."""
    base = [
        "Arrêté d'Approbation du lotissement (signé du Ministre) — pièce irréfutable",
        "Plan de lotissement visé par le Ministère (parcelles, voies, espaces verts)",
        "Lettre d'attribution + attestation villageoise (origine du droit)",
        "État Foncier récent (DGI, econsultation.dgi.gouv.ci, 3 000 FCFA)",
        "Arrêté de Concession Définitive (ACD) ou Titre Foncier immatriculé",
        "Quitus fiscal / paiement des impôts fonciers à jour",
    ]
    if statut == "En sursis":
        base += ["⚠️ Motifs du sursis auprès du MCLU + preuve de levée du sursis",
                 "Attestation de non-annulation datée de moins de 3 mois"]
    if statut == "Annulé":
        return ["❌ NE PAS ACHETER : approbation retirée par l'État.",
                "Justificatif officiel de l'annulation (pour dossier)",
                "Consultation d'un notaire AVANT toute somme versée."]
    return base


def guichet_competent(commune: str) -> dict:
    """Guichet Unique du Foncier (GUF) compétent + démarches (guidance réelle)."""
    return {
        "guichet": f"Guichet Unique du Foncier — ressort de {commune}",
        "portail": PORTAILS["GUF"]["url"],
        "demarches": [
            "1. Identifier la parcelle (IDUFCI) et le lotissement.",
            "2. Vérifier le statut du lotissement (plateforme MCLU).",
            "3. Commander l'État Foncier (DGI) pour le propriétaire/hypothèques.",
            "4. Exiger l'ACD ou le Titre Foncier avant tout acompte.",
        ],
    }


def alertes_juridiques(parcelles: gpd.GeoDataFrame, n: int = 6) -> list[dict]:
    """Flux d'alertes de changement de statut (DÉMO, format réaliste)."""
    from datetime import datetime, timedelta, timezone

    risquees = parcelles[parcelles["lotissement_statut"].isin(["En sursis", "Annulé"])]
    if risquees.empty:
        return []
    ech = risquees.sample(n=min(n, len(risquees)), random_state=3)
    today = datetime.now(timezone.utc)
    out = []
    for _, r in ech.iterrows():
        st = r["lotissement_statut"]
        out.append({
            "icone": STATUTS[st]["icone"],
            "message": f"Le « {r['lotissement_nom']} » ({r['commune']}) est en statut "
                       f"**{st}** — risque {STATUTS[st]['risque']}.",
            "date": (today - timedelta(days=random.randint(1, 60))).strftime("%d/%m/%Y"),
        })
    return out


def build_juridique() -> dict:
    """Enrichit les parcelles avec les champs juridiques DÉMO et sauvegarde."""
    d = GRAND_ABIDJAN_DIR
    parcelles = gpd.read_parquet(d / "parcelles.parquet")
    parcelles = enrich_juridique(parcelles)
    parcelles.to_parquet(d / "parcelles.parquet")

    # Table lotissements agrégée (statut dominant par nom)
    lots = (parcelles.groupby(["lotissement_nom", "commune"])
            .agg(statut=("lotissement_statut", lambda s: s.mode().iloc[0]),
                 n_parcelles=("code_parcelle", "size")).reset_index())
    lots.to_parquet(d / "lotissements.parquet")
    logger.success("[JURID] Couche juridique sauvegardée.")
    return {"parcelles": parcelles, "lotissements": lots}


if __name__ == "__main__":
    build_juridique()
