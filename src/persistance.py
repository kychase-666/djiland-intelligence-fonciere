"""
PERSISTANCE des données saisies par l'utilisateur (prix réels, notes de carte).

Deux modes, choisis automatiquement :
  - BASE EN LIGNE (PostgreSQL gratuit : Neon, Supabase…) dès que l'adresse de
    connexion DJILAND_DB_URL est fournie (Secrets Streamlit Cloud, variable
    d'environnement ou fichier .env). Indispensable en ligne : le disque de
    Streamlit Cloud est effacé à chaque mise en veille / redéploiement.
  - FICHIERS PARQUET locaux sinon (usage sur le Mac, inchangé) — géré par les
    modules appelants (prix_reels, notes).

Les tables sont créées automatiquement au premier usage. À leur création, le
contenu du fichier parquet local éventuel y est recopié UNE seule fois : les
données déjà présentes ne sont pas perdues lors du passage à la base en ligne.

Lecture : cache en mémoire de quelques secondes (une page Streamlit lit les
mêmes tables plusieurs fois par affichage), invalidé à chaque écriture.
En cas de base injoignable : les lectures renvoient une table vide et
`etat()["erreur"]` est renseigné (le dashboard l'affiche) ; les écritures
lèvent `BaseIndisponible` pour que l'utilisateur sache que rien n'a été
enregistré.
"""
from __future__ import annotations

import math
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

import pandas as pd
from loguru import logger

CLE_SECRET = "DJILAND_DB_URL"
TTL_CACHE = 30          # s — durée de vie du cache de lecture
TTL_ERREUR = 20         # s — on ne réessaie pas une base injoignable avant ce délai
DELAI_CONNEXION = 10    # s — Neon gratuit se réveille en ~1 s après une pause

NUMERIQUE = "double precision"
TEXTE = "text"


class BaseIndisponible(RuntimeError):
    """La base en ligne est configurée mais injoignable (écriture impossible)."""


@dataclass(frozen=True)
class Table:
    """Description d'une table : nom, colonnes {nom: type SQL}, contenu initial."""
    nom: str
    colonnes: dict[str, str]
    graine: Callable[[], pd.DataFrame] | None = None


_verrou = threading.Lock()
_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_pretes: set[str] = set()
_erreur: dict[str, object] = {"msg": None, "t": 0.0}


def db_url() -> str | None:
    """Adresse de connexion PostgreSQL (Secrets Streamlit puis environnement)."""
    url = ""
    try:
        import streamlit as st
        url = str(st.secrets[CLE_SECRET])
    except Exception:
        url = os.getenv(CLE_SECRET, "")
    url = url.strip().strip('"').strip("'")
    if not url:
        return None
    # Tolère les formats SQLAlchemy (postgresql+psycopg2://) et Heroku (postgres://)
    return re.sub(r"^postgres(?:ql)?(?:\+\w+)?://", "postgresql://", url)


def actif() -> bool:
    """True si la base en ligne est configurée (sinon : fichiers locaux)."""
    return db_url() is not None


def etat() -> dict:
    """Mode de stockage courant, pour affichage (jamais le mot de passe).

    Returns:
        {"mode": "base"|"fichier", "hote": str|None, "erreur": str|None}.
    """
    url = db_url()
    if not url:
        return {"mode": "fichier", "hote": None, "erreur": None}
    hote = urlsplit(url).hostname
    recent = time.monotonic() - float(_erreur["t"]) < 300
    return {"mode": "base", "hote": hote, "erreur": _erreur["msg"] if recent else None}


def _connexion():
    import psycopg
    # prepare_threshold=None : compatible avec les « poolers » (PgBouncer) de Neon/Supabase
    return psycopg.connect(db_url(), connect_timeout=DELAI_CONNEXION,
                           prepare_threshold=None, autocommit=True)


def _signaler(exc: Exception) -> str:
    msg = f"{type(exc).__name__} : {str(exc).strip().splitlines()[0] if str(exc).strip() else ''}"
    _erreur.update(msg=msg, t=time.monotonic())
    logger.error(f"[BASE] {msg}")
    return msg


def _valeur(v, type_sql: str):
    """Convertit une valeur Python/numpy/pandas en valeur SQL (None si vide)."""
    if v is None or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if type_sql == NUMERIQUE:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return None if math.isnan(f) else f
    return str(v)


def _cols(t: Table) -> str:
    return ", ".join(f'"{c}"' for c in t.colonnes)


def _inserer(cur, t: Table, lignes: list[dict]) -> None:
    cols = list(t.colonnes)
    sql = (f"INSERT INTO {t.nom} ({_cols(t)}) "
           f"VALUES ({', '.join(['%s'] * len(cols))})")
    cur.executemany(sql, [tuple(_valeur(r.get(c), t.colonnes[c]) for c in cols)
                          for r in lignes])


def _preparer(conn, t: Table) -> None:
    """Crée la table si besoin ; à sa création, y recopie le fichier local."""
    if t.nom in _pretes:
        return
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) IS NULL", (t.nom,))
        nouvelle = cur.fetchone()[0]
        if nouvelle:
            defs = ", ".join(f'"{c}" {typ}' for c, typ in t.colonnes.items())
            cur.execute(f"CREATE TABLE IF NOT EXISTS {t.nom} (id bigserial PRIMARY KEY, "
                        f"cree_le timestamptz NOT NULL DEFAULT now(), {defs})")
            graine = t.graine() if t.graine else None
            if graine is not None and len(graine):
                _inserer(cur, t, graine.to_dict("records"))
                logger.success(f"[BASE] {t.nom} créée — {len(graine)} ligne(s) "
                               "recopiée(s) depuis le fichier local.")
            else:
                logger.success(f"[BASE] Table {t.nom} créée.")
    _pretes.add(t.nom)


def _vide(t: Table) -> pd.DataFrame:
    return pd.DataFrame(columns=list(t.colonnes))


def lire(t: Table) -> pd.DataFrame:
    """Contenu de la table dans l'ordre d'insertion (vide si base injoignable)."""
    with _verrou:
        hit = _cache.get(t.nom)
        if hit and time.monotonic() - hit[0] < TTL_CACHE:
            return hit[1].copy()
        if time.monotonic() - float(_erreur["t"]) < TTL_ERREUR:
            return _vide(t)
        cols = list(t.colonnes)
        try:
            with _connexion() as conn:
                _preparer(conn, t)
                with conn.cursor() as cur:
                    cur.execute(f"SELECT {_cols(t)} FROM {t.nom} ORDER BY id")
                    lignes = cur.fetchall()
        except Exception as exc:
            _signaler(exc)
            return _vide(t)
        _erreur.update(msg=None, t=0.0)
        df = pd.DataFrame(lignes, columns=cols) if lignes else _vide(t)
        for c, typ in t.colonnes.items():
            if typ == NUMERIQUE:
                df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
        _cache[t.nom] = (time.monotonic(), df)
        return df.copy()


def _ecrire(t: Table, action: Callable) -> object:
    """Exécute une écriture ; lève BaseIndisponible si la base ne répond pas."""
    with _verrou:
        _cache.pop(t.nom, None)
        try:
            with _connexion() as conn:
                _preparer(conn, t)
                with conn.cursor() as cur:
                    res = action(cur)
        except Exception as exc:
            raise BaseIndisponible(_signaler(exc)) from exc
        _erreur.update(msg=None, t=0.0)
        return res


def ajouter(t: Table, lignes: list[dict]) -> None:
    """Ajoute des lignes (dict colonne → valeur ; colonnes absentes = vides)."""
    if lignes:
        _ecrire(t, lambda cur: _inserer(cur, t, lignes))


def supprimer_position(t: Table, position: int) -> bool:
    """Supprime la ligne à la position donnée (ordre d'insertion, 0 = la plus ancienne)."""
    def _suppr(cur):
        cur.execute(f"DELETE FROM {t.nom} WHERE id = (SELECT id FROM {t.nom} "
                    "ORDER BY id OFFSET %s LIMIT 1)", (int(position),))
        return cur.rowcount > 0
    return bool(position >= 0 and _ecrire(t, _suppr))


def vider(t: Table) -> None:
    """Supprime toutes les lignes de la table."""
    _ecrire(t, lambda cur: cur.execute(f"DELETE FROM {t.nom}"))
