"""
Scraping RESPECTUEUX des annonces immobilières et annonces légales.

⚖️  NOTE LÉGALE ET ÉTHIQUE (à lire avant activation) :
-----------------------------------------------------------------------------
- On ne collecte que des DONNÉES PUBLIQUES (prix, surface, quartier), jamais
  de données personnelles nominatives (noms, téléphones, e-mails de vendeurs).
- On respecte `robots.txt` et on applique un délai (rate limiting) pour ne pas
  surcharger les serveurs.
- Facebook Marketplace est DÉSACTIVÉ : son scraping viole les CGU de Meta.
  Utilisez plutôt les plateformes qui l'autorisent, ou des accords d'API.
- Vérifiez toujours les CGU de chaque site avant de l'activer en production.
  En cas de doute, privilégiez un partenariat de données ou une API officielle.
-----------------------------------------------------------------------------

Ce module fournit un socle générique + un exemple pour Jumia Deals CI.
Le parsing HTML dépend du DOM réel du site (susceptible de changer) : les
sélecteurs sont donc isolés et faciles à mettre à jour.
"""
from __future__ import annotations

import re
import time
import urllib.robotparser as robotparser
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from loguru import logger

from config import SCRAPING_SOURCES

USER_AGENT = "DjilandLandIntelligence/1.0 (veille foncière ; contact@djiland.ci)"


@dataclass
class Annonce:
    """Représentation normalisée d'une annonce immobilière scrapée."""

    source: str
    url: str
    quartier: str | None = None
    type_bien: str | None = None
    surface_m2: float | None = None
    prix_total_fcfa: float | None = None
    prix_m2_fcfa: float | None = None
    date_annonce: datetime = field(default_factory=datetime.utcnow)

    def finalize(self) -> "Annonce":
        """Calcule le prix au m² si absent mais dérivable."""
        if self.prix_m2_fcfa is None and self.prix_total_fcfa and self.surface_m2:
            self.prix_m2_fcfa = round(self.prix_total_fcfa / self.surface_m2, 2)
        return self


def _robots_allows(base_url: str, path: str = "/") -> bool:
    """Vérifie via robots.txt que le chemin est autorisé au scraping."""
    parsed = urlparse(base_url)
    rp = robotparser.RobotFileParser()
    rp.set_url(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        logger.warning(f"robots.txt illisible pour {base_url} — abstention.")
        return False
    return rp.can_fetch(USER_AGENT, urljoin(base_url, path))


def _parse_prix_fcfa(texte: str) -> float | None:
    """Extrait un montant en FCFA depuis un texte libre ('12 000 000 FCFA')."""
    if not texte:
        return None
    digits = re.sub(r"[^\d]", "", texte)
    return float(digits) if digits else None


def _parse_surface(texte: str) -> float | None:
    """Extrait une surface en m² depuis un texte ('300 m²', '2 lots')."""
    m = re.search(r"(\d[\d\s.,]*)\s*m", texte or "", flags=re.I)
    if m:
        return float(re.sub(r"[^\d.]", "", m.group(1).replace(",", ".")))
    return None


def scrape_jumia_deals(max_pages: int = 3) -> list[Annonce]:
    """Scrape les annonces foncières/immobilières de Jumia Deals CI.

    Politesse garantie : robots.txt + délai minimal entre requêtes.
    Retourne une liste d'`Annonce` normalisées (peut être vide).
    """
    cfg = SCRAPING_SOURCES["jumia_deals"]
    if not cfg["enabled"]:
        return []
    base = cfg["base_url"]
    if cfg["respect_robots"] and not _robots_allows(base, "/immobilier/"):
        logger.warning("[SCRAPE] robots.txt interdit /immobilier/ — arrêt.")
        return []

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    annonces: list[Annonce] = []

    for page in range(1, max_pages + 1):
        url = f"{base}/immobilier/?page={page}"
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning(f"[SCRAPE] Échec page {page}: {exc}")
            break

        soup = BeautifulSoup(resp.text, "lxml")
        # Sélecteurs à adapter au DOM réel (isolés volontairement) :
        cards = soup.select("article, .product, .ann-item")
        for card in cards:
            titre = card.get_text(" ", strip=True)
            a = card.find("a", href=True)
            annonce = Annonce(
                source="jumia_deals",
                url=urljoin(base, a["href"]) if a else url,
                type_bien="terrain" if "terrain" in titre.lower() else "bien",
                surface_m2=_parse_surface(titre),
                prix_total_fcfa=_parse_prix_fcfa(titre),
            ).finalize()
            if annonce.prix_total_fcfa:
                annonces.append(annonce)

        time.sleep(cfg["min_delay_s"])  # rate limiting = politesse

    logger.info(f"[SCRAPE] Jumia Deals: {len(annonces)} annonces valides.")
    return annonces


def scrape_arretes_publics() -> list[dict]:
    """Point d'entrée pour scraper les annonces légales / arrêtés de lotissement.

    À brancher sur le Journal Officiel de Côte d'Ivoire et les sites des mairies.
    Retourne une liste de dictionnaires prêts pour la table `arretes_publics`.
    Implémentation laissée ouverte car les sources varient par commune.
    """
    logger.info("[SCRAPE] Arrêtés publics : brancher les sources locales ici.")
    return []
