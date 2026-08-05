"""
Schéma de la base PostGIS — cœur historisé du système.

Chaque table est pensée pour ne JAMAIS perdre l'historique : les prix, les
détections satellite et les scores sont horodatés. On peut ainsi reconstruire
une courbe de tendance même en partant de zéro donnée aujourd'hui.
"""
from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Parcelle(Base):
    """Unité foncière élémentaire (parcelle ou maille d'analyse).

    La géométrie est stockée en WGS84 (SRID 4326) ; les calculs métriques se
    font à la volée par reprojection en UTM 30N côté Python.
    """

    __tablename__ = "parcelles"

    id = Column(Integer, primary_key=True)
    code_parcelle = Column(String(64), unique=True, index=True)
    commune = Column(String(120), index=True)
    quartier = Column(String(120), index=True)
    aoi = Column(String(64), index=True)
    surface_m2 = Column(Float)
    geom = Column(Geometry("POLYGON", srid=4326))
    created_at = Column(DateTime, default=datetime.utcnow)

    prix = relationship("PrixAnnonce", back_populates="parcelle")
    indicateurs = relationship("IndicateurSpatial", back_populates="parcelle")
    releves = relationship("ReleveTerrain", back_populates="parcelle")


class PrixAnnonce(Base):
    """Annonce immobilière scrapée = observation de prix transactionnel.

    Historisée : chaque scrape crée une nouvelle ligne (jamais d'écrasement),
    ce qui permet de tracer l'évolution des prix au m² dans le temps.
    """

    __tablename__ = "prix_annonces"

    id = Column(Integer, primary_key=True)
    parcelle_id = Column(Integer, ForeignKey("parcelles.id"), nullable=True, index=True)
    source = Column(String(64), index=True)          # jumia_deals, notaire, ...
    url = Column(Text)
    quartier = Column(String(120), index=True)
    type_bien = Column(String(64))                   # terrain, villa, appartement
    surface_m2 = Column(Float)
    prix_total_fcfa = Column(Float)
    prix_m2_fcfa = Column(Float, index=True)
    geom = Column(Geometry("POINT", srid=4326))
    date_annonce = Column(DateTime, index=True)
    scraped_at = Column(DateTime, default=datetime.utcnow, index=True)

    parcelle = relationship("Parcelle", back_populates="prix")


class IndicateurSpatial(Base):
    """Résultat de traitement satellite/SIG pour une parcelle à une date.

    Regroupe NDVI, pente, accessibilité, détection de changement et le
    « Speculation Heat Index ». Une ligne par parcelle et par run.
    """

    __tablename__ = "indicateurs_spatiaux"

    id = Column(Integer, primary_key=True)
    parcelle_id = Column(Integer, ForeignKey("parcelles.id"), index=True)
    date_calcul = Column(DateTime, default=datetime.utcnow, index=True)

    ndvi_moyen = Column(Float)
    ndvi_delta_6m = Column(Float)          # variation NDVI sur 6 mois (déforestation < 0)
    changement_sar = Column(Float)         # score de changement radar (nouveaux chantiers)
    pente_moyenne_deg = Column(Float)
    part_pente_sup15 = Column(Float)       # fraction de surface avec pente > 15%
    risque_inondation = Column(Float)      # dérivé du DEM (accumulation de drainage)
    accessibilite_min = Column(Float)      # temps de trajet estimé vers le Plateau (min)
    speculation_heat = Column(Float, index=True)  # 0-100

    parcelle = relationship("Parcelle", back_populates="indicateurs")


class ReleveTerrain(Base):
    """Ground truth : relevés GPS des équipes terrain (Djiland).

    Ce que le satellite ne voit pas : qualité du sol, nuisance sonore réelle,
    vue, accessibilité effective. Enrichit et corrige le modèle.
    """

    __tablename__ = "releves_terrain"

    id = Column(Integer, primary_key=True)
    parcelle_id = Column(Integer, ForeignKey("parcelles.id"), index=True)
    agent = Column(String(120))
    geom = Column(Geometry("POINT", srid=4326))
    qualite_sol = Column(String(64))           # sableux, argileux, latéritique, rocheux
    vue = Column(String(64))                    # lagune, rue, dégagée, obstruée
    nuisance_sonore = Column(Integer)           # échelle 1-5
    accessibilite_reelle = Column(Integer)      # échelle 1-5
    litige_foncier = Column(Boolean, default=False)
    viabilise = Column(Boolean, default=False)  # eau/électricité présentes
    commentaire = Column(Text)
    date_releve = Column(DateTime, default=datetime.utcnow)

    parcelle = relationship("Parcelle", back_populates="releves")


class POI(Base):
    """Point d'intérêt / voirie OSM (école, marché, route, transport)."""

    __tablename__ = "pois"

    id = Column(Integer, primary_key=True)
    osm_id = Column(String(64), index=True)
    categorie = Column(String(64), index=True)  # school, marketplace, highway, ...
    nom = Column(String(255))
    geom = Column(Geometry("GEOMETRY", srid=4326))
    tags = Column(Text)                         # JSON brut des tags OSM
    ingested_at = Column(DateTime, default=datetime.utcnow)


class ArretePublic(Base):
    """Arrêté de lotissement / décret ZUP / annonce légale (scraping public)."""

    __tablename__ = "arretes_publics"

    id = Column(Integer, primary_key=True)
    reference = Column(String(120))
    type_acte = Column(String(64))              # lotissement, ZUP, voirie, DUP
    commune = Column(String(120), index=True)
    quartier = Column(String(120), index=True)
    geom = Column(Geometry("GEOMETRY", srid=4326), nullable=True)
    date_publication = Column(DateTime, index=True)
    source = Column(Text)
    resume = Column(Text)
    scraped_at = Column(DateTime, default=datetime.utcnow)


class PredictionPrix(Base):
    """Sortie du modèle ML : prix futur prédit à 6 mois pour un quartier."""

    __tablename__ = "predictions_prix"

    id = Column(Integer, primary_key=True)
    quartier = Column(String(120), index=True)
    aoi = Column(String(64), index=True)
    prix_m2_actuel = Column(Float)
    prix_m2_predit_6m = Column(Float)
    hausse_pct = Column(Float, index=True)
    top_features = Column(Text)                 # explications SHAP (JSON)
    date_prediction = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (UniqueConstraint("quartier", "date_prediction", name="uq_pred_quartier_date"),)
