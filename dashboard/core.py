"""
Socle commun du dashboard Djiland : données partagées, composants visuels,
formatage et accès protégé.

Chaque page (dossier `dashboard/views/`) importe d'ici ce dont elle a besoin,
ce qui garantit une présentation homogène sur toute l'application.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from config import (
    ALL_ZONES,
    APP_UPDATED,
    APP_VERSION,
    DATA_BUILT,
    GRAND_ABIDJAN_DIR,
)

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / "assets"

# Version hébergée sur Streamlit Cloud (code monté dans /mount/src) : le disque
# y est éphémère → les données saisies sont effacées à chaque mise en veille.
EN_LIGNE = str(ROOT).startswith("/mount/src")

# Palette de marque (cohérente avec .streamlit/config.toml)
VERT = "#0B5D4B"
OR = "#B8893B"
ENCRE = "#14211D"
GRIS = "#5B6B65"
ROUGE = "#B3261E"
ORANGE = "#C77700"


# ---------------------------------------------------------------------------
# Formatage (conventions françaises : espace fine pour les milliers)
# ---------------------------------------------------------------------------
def fcfa(v, suffixe: str = " F") -> str:
    """Montant formaté « 23 872 234 F » (— si vide)."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:,.0f}".replace(",", " ") + suffixe


def mfcfa(v) -> str:
    """Montant en millions « 23,9 M FCFA »."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v / 1e6:,.1f}".replace(",", " ").replace(".", ",") + " M FCFA"


def pct(v, decimales: int = 1, signe: bool = False) -> str:
    """Pourcentage « +12,4 % »."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    s = f"{v:+.{decimales}f}" if signe else f"{v:.{decimales}f}"
    return s.replace(".", ",") + " %"


def _sp(v: str) -> str:
    """(Compat) remplace la virgule des milliers par une espace fine."""
    return v.replace(",", " ")


# ---------------------------------------------------------------------------
# Styles des composants maison (le thème natif gère le reste)
# ---------------------------------------------------------------------------
_CSS = """
<style>
.block-container{max-width:1380px;padding-top:1.4rem;padding-bottom:2.5rem;}
/* En-tête de page */
.dj-overline{font:700 11px/1.2 Inter,sans-serif;letter-spacing:.16em;text-transform:uppercase;
  color:#B8893B;margin:0 0 6px;}
.dj-title{font-family:"Plus Jakarta Sans",Inter,sans-serif;font-weight:800;font-size:1.85rem;
  letter-spacing:-.02em;color:#0F1F1A;margin:0;line-height:1.15;}
.dj-sub{color:#5B6B65;font-size:.95rem;margin:6px 0 0;max-width:900px;}
.dj-head{padding:4px 0 14px;margin-bottom:18px;border-bottom:1px solid #E2E7EA;}
/* Indicateurs clés */
.dj-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin:2px 0 18px;}
.dj-kpi{background:#fff;border:1px solid #E2E7EA;border-radius:12px;padding:14px 16px 13px;
  box-shadow:0 1px 2px rgba(16,24,40,.04);position:relative;overflow:hidden;}
.dj-kpi:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:#0B5D4B;opacity:.9;}
.dj-kpi.or:before{background:#B8893B;}
.dj-kpi .l{font:600 11px/1.3 Inter,sans-serif;letter-spacing:.07em;text-transform:uppercase;color:#5B6B65;}
.dj-kpi .v{font-family:"Plus Jakarta Sans",Inter,sans-serif;font-weight:700;font-size:1.45rem;
  color:#0F1F1A;margin-top:6px;line-height:1.1;letter-spacing:-.01em;}
.dj-kpi .h{font-size:11.5px;color:#7A8A84;margin-top:5px;}
.dj-chip{display:inline-block;font:600 11px/1 Inter,sans-serif;padding:4px 7px;border-radius:999px;
  margin-left:6px;vertical-align:middle;}
.dj-chip.up{background:#E6F3EE;color:#0B5D4B;}
.dj-chip.down{background:#FBEAE8;color:#B3261E;}
.dj-chip.flat{background:#EEF1F3;color:#5B6B65;}
/* Titres de section */
.dj-sec{display:flex;align-items:baseline;gap:10px;margin:22px 0 10px;}
.dj-sec h3{font-family:"Plus Jakarta Sans",Inter,sans-serif;font-size:1.08rem;font-weight:700;
  color:#0F1F1A;margin:0;padding:0;}
.dj-sec span{font-size:.85rem;color:#7A8A84;}
.dj-sec:before{content:"";width:4px;height:16px;border-radius:2px;background:#B8893B;align-self:center;}
/* Pastilles */
.dj-badge{display:inline-block;font:600 11.5px/1 Inter,sans-serif;padding:5px 9px;border-radius:999px;
  border:1px solid transparent;white-space:nowrap;}
.dj-badge.ok{background:#E6F3EE;color:#0B5D4B;border-color:#CFE7DD;}
.dj-badge.warn{background:#FFF4E0;color:#8A5300;border-color:#F6DDB0;}
.dj-badge.bad{background:#FBEAE8;color:#B3261E;border-color:#F3CCC7;}
.dj-badge.neutral{background:#EEF1F3;color:#4A5A54;border-color:#E2E7EA;}
/* Liste « classement » compacte */
.dj-rank{display:flex;align-items:center;gap:12px;padding:10px 2px;border-bottom:1px solid #EEF1F3;}
.dj-rank:last-child{border-bottom:none;}
.dj-rank .n{width:26px;height:26px;border-radius:50%;background:#0B5D4B;color:#fff;
  font:700 12px/26px Inter,sans-serif;text-align:center;flex:none;}
.dj-rank .t{flex:1;min-width:0;}
.dj-rank .t b{color:#0F1F1A;font-size:.92rem;}
.dj-rank .t div{color:#7A8A84;font-size:.8rem;}
.dj-rank .s{font-family:"Plus Jakarta Sans",Inter,sans-serif;font-weight:700;color:#0B5D4B;}
/* Mentions & pied de page */
.dj-note{font-size:.8rem;color:#7A8A84;line-height:1.5;}
.dj-foot{margin-top:34px;padding:14px 4px 0;border-top:1px solid #E2E7EA;color:#7A8A84;
  font-size:11.5px;line-height:1.6;}
/* Connexion */
.dj-login{border:1px solid #E2E7EA;border-radius:16px;overflow:hidden;background:#fff;
  box-shadow:0 12px 32px rgba(12,31,27,.10);margin-top:7vh;}
.dj-login .top{background:#0C1F1B;padding:26px 28px 22px;}
.dj-login .top p{color:#A9C2BA;font-size:.88rem;margin:12px 0 0;}
/* Barre latérale */
[data-testid="stSidebar"] .dj-side{font-size:11.5px;color:#9DB5AD;line-height:1.55;padding:6px 2px;}
[data-testid="stSidebar"] .dj-side b{color:#E3EEEA;}
/* Téléphone */
@media (max-width:640px){
  .block-container{padding-left:.8rem;padding-right:.8rem;padding-top:.8rem;}
  .dj-title{font-size:1.45rem;}
  .dj-kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;}
  .dj-kpi .v{font-size:1.15rem;}
  .dj-login{margin-top:2vh;}
}
</style>
"""


def inject_css() -> None:
    """Injecte les styles des composants maison."""
    st.markdown(_CSS, unsafe_allow_html=True)


def _data_uri(nom: str) -> str:
    """Image du dossier assets encodée en data-URI (pour le HTML)."""
    b = (ASSETS / nom).read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(b).decode()


# ---------------------------------------------------------------------------
# Composants
# ---------------------------------------------------------------------------
def page_header(titre: str, sous_titre: str = "", rubrique: str = "") -> None:
    """En-tête de page : rubrique (sur-titre doré), titre, sous-titre."""
    st.markdown(
        '<div class="dj-head">'
        + (f'<p class="dj-overline">{rubrique}</p>' if rubrique else "")
        + f'<h1 class="dj-title">{titre}</h1>'
        + (f'<p class="dj-sub">{sous_titre}</p>' if sous_titre else "")
        + "</div>", unsafe_allow_html=True)


def kpi_row(items: list[dict]) -> None:
    """Rangée d'indicateurs. Chaque item : {l, v, delta?, sens?, h?, or?}.

    `sens` ∈ {"up", "down", "flat"} colore la pastille de variation.
    """
    html = ['<div class="dj-kpis">']
    for it in items:
        chip = ""
        if it.get("delta"):
            chip = f'<span class="dj-chip {it.get("sens", "flat")}">{it["delta"]}</span>'
        cls = "dj-kpi or" if it.get("or") else "dj-kpi"
        html.append(f'<div class="{cls}"><div class="l">{it["l"]}</div>'
                    f'<div class="v">{it["v"]}{chip}</div>'
                    + (f'<div class="h">{it["h"]}</div>' if it.get("h") else "") + "</div>")
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def section(titre: str, aide: str = "") -> None:
    """Titre de section avec filet doré."""
    st.markdown(f'<div class="dj-sec"><h3>{titre}</h3>'
                + (f"<span>{aide}</span>" if aide else "") + "</div>",
                unsafe_allow_html=True)


def badge(texte: str, nature: str = "neutral") -> str:
    """Pastille HTML (nature : ok, warn, bad, neutral)."""
    return f'<span class="dj-badge {nature}">{texte}</span>'


def note(texte: str) -> None:
    """Mention discrète (méthodologie, avertissement)."""
    st.markdown(f'<p class="dj-note">{texte}</p>', unsafe_allow_html=True)


def style_fig(fig, hauteur: int | None = None, titre: str | None = None):
    """Harmonise un graphique Plotly avec la charte (police, grilles, marges)."""
    fig.update_layout(
        font=dict(family="Inter, sans-serif", size=12, color=ENCRE),
        title=dict(text=titre, font=dict(family="Plus Jakarta Sans, Inter", size=15),
                   x=0, xanchor="left") if titre else None,
        margin=dict(l=6, r=6, t=46 if titre else 12, b=6),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                    title=None, font=dict(size=11)),
        hoverlabel=dict(font=dict(family="Inter, sans-serif")),
    )
    fig.update_xaxes(gridcolor="#EEF1F3", zeroline=False, linecolor="#E2E7EA")
    fig.update_yaxes(gridcolor="#EEF1F3", zeroline=False, linecolor="#E2E7EA")
    if hauteur:
        fig.update_layout(height=hauteur)
    return fig


def pied_de_page() -> None:
    """Pied de page : version, fraîcheur des données, avertissement."""
    fr = lambda iso: pd.Timestamp(iso).strftime("%d/%m/%Y")  # noqa: E731
    st.markdown(
        f'<div class="dj-foot"><b>Djiland · Land Intelligence</b> — version {APP_VERSION} · '
        f'mise à jour du {fr(APP_UPDATED)} · couches OSM & parcelles du {fr(DATA_BUILT)}<br>'
        "Estimations indicatives (prix calibrés, statuts juridiques de démonstration) — à "
        "confirmer par visite, État Foncier et notaire. © Djiland SARL.</div>",
        unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Accès protégé — actif seulement si DJILAND_PASSWORD est défini
# ---------------------------------------------------------------------------
def mot_de_passe_requis() -> str:
    """Mot de passe attendu (secrets Streamlit Cloud, sinon variable d'env)."""
    try:
        return str(st.secrets["DJILAND_PASSWORD"])
    except Exception:
        return os.getenv("DJILAND_PASSWORD", "")


def gate() -> None:
    """Écran de connexion (partage à distance sécurisé). Libre en local."""
    pw = mot_de_passe_requis()
    if not pw or st.session_state.get("auth_ok"):
        return
    _, centre, _ = st.columns([1, 1.25, 1])
    with centre:
        st.markdown(
            f'<div class="dj-login"><div class="top"><img src="{_data_uri("logo.svg")}" '
            'height="40" alt="Djiland"><p>Plateforme d\'intelligence foncière · '
            "Grand Abidjan & corridor côtier</p></div></div>", unsafe_allow_html=True)
        with st.form("login", border=False):
            entry = st.text_input("Mot de passe d'accès", type="password",
                                  placeholder="Saisissez votre mot de passe")
            if st.form_submit_button("Se connecter", type="primary", width="stretch"):
                if entry == pw:
                    st.session_state["auth_ok"] = True
                    st.rerun()
                else:
                    st.error("Mot de passe incorrect.")
        note("Accès réservé à l'équipe Djiland SARL. Les données affichées sont des "
             "estimations indicatives.")
    st.stop()


# ---------------------------------------------------------------------------
# Données partagées (mises en cache)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Chargement des données du Grand Abidjan…")
def load():
    """Communes/zones + parcelles enrichies (construit via OSM si absentes)."""
    import geopandas as gpd

    if not (GRAND_ABIDJAN_DIR / "parcelles.parquet").exists():
        from src.ingestion.build_grand_abidjan import build
        build()
    communes = gpd.read_parquet(GRAND_ABIDJAN_DIR / "communes.parquet")
    parcelles = gpd.read_parquet(GRAND_ABIDJAN_DIR / "parcelles.parquet")
    return communes, parcelles


@st.cache_data(show_spinner="Calcul des scores d'opportunité…")
def parcelles_scorees():
    """Parcelles + score d'opportunité / verdict / distance aux transports futurs."""
    from src.analysis.opportunites import scorer
    return scorer(load()[1])


@st.cache_data(show_spinner=False)
def transport():
    """Axes de transport structurants (existants + futurs)."""
    import geopandas as gpd
    p = GRAND_ABIDJAN_DIR / "transport.parquet"
    return gpd.read_parquet(p) if p.exists() else None


@st.cache_data(show_spinner=False)
def synth_history(_key: tuple = (), mois: int = 24) -> pd.DataFrame:
    """Historique mensuel de prix par zone (24 mois, reconstruit)."""
    rng = np.random.default_rng(7)
    today = pd.Timestamp.now(tz="UTC").normalize()
    rows = []
    for com, cfg in ALL_ZONES.items():
        for m in range(mois, -1, -1):
            date = today - pd.Timedelta(days=30 * m)
            croissance = (1 + cfg["tendance"]) ** (mois - m)
            saison = 1 + 0.035 * np.sin(2 * np.pi * m / 12)
            rows.append({"commune": com,
                         "prix_m2_fcfa": cfg["prix_m2"] * croissance * saison
                         * rng.normal(1, 0.05),
                         "date": date})
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def alertes(_key: int = 1) -> pd.DataFrame:
    """Projection transparente du prix à 6 mois par zone + justifications."""
    communes, parcelles = load()
    rows = []
    for _, c in communes.iterrows():
        cfg = ALL_ZONES[c["commune"]]
        sub = parcelles[parcelles["commune"] == c["commune"]]
        prix, heat = c["prix_m2_moyen"], c["heat_moyen"] / 100.0
        proj = prix * (1 + cfg["tendance"]) ** 6 * (1 + 0.06 * heat)
        rows.append({"commune": c["commune"], "type_zone": c["type_zone"],
                     "prix_actuel": prix, "prix_projete_6m": proj,
                     "hausse_pct": (proj / prix - 1) * 100, "heat": c["heat_moyen"],
                     "ndvi_baisse": round(-sub["ndvi_delta_6m"].mean(), 3),
                     "acces_min": c["access_moyen"]})
    return pd.DataFrame(rows).sort_values("hausse_pct", ascending=False)
