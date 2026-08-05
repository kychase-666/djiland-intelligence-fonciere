"""
Dashboard Streamlit — DJILAND · Intelligence Foncière du GRAND ABIDJAN.

Design professionnel épuré. Périmètre : 13 communes du District Autonome.
Onglets : Carte multi-calques · Analyse au m² · Tendances · Alertes ·
Annoter (dessin + notes persistantes) · Rapport PDF.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    ALL_ZONES,
    GRAND_ABIDJAN_DIR,
    QUARTIERS,
    QUARTIERS_GENERIQUES,
)
from src.reports.pdf import build_report                       # noqa: E402

st.set_page_config(page_title="Djiland · Grand Abidjan", layout="wide", page_icon="🛰️")

# ---------------------------------------------------------------------------
# Design — CSS professionnel épuré
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family:'Inter',sans-serif; }
#MainMenu, footer, header {visibility:hidden;}
.block-container {padding-top:1.2rem; padding-bottom:2rem; max-width:1500px;}

/* En-tête */
.dj-header{
  background:linear-gradient(110deg,#123c33 0%,#1F6F5C 55%,#2a8f77 100%);
  border-radius:18px; padding:22px 28px; margin-bottom:18px;
  box-shadow:0 8px 26px rgba(18,60,51,.28); color:#fff;
  display:flex; align-items:center; gap:18px;
}
.dj-header .logo{font-size:38px; line-height:1;}
.dj-header h1{margin:0; font-size:26px; font-weight:800; letter-spacing:-.4px;}
.dj-header p{margin:3px 0 0; font-size:13px; opacity:.85; font-weight:400;}
.dj-badge{margin-left:auto; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.25);
  padding:6px 14px; border-radius:999px; font-size:12px; font-weight:600;}

/* Cartes de métriques */
[data-testid="stMetric"]{
  background:#fff; border:1px solid #e6e4dc; border-radius:14px; padding:14px 16px;
  box-shadow:0 2px 8px rgba(20,36,31,.05); border-top:3px solid #1F6F5C;
}
[data-testid="stMetricLabel"]{opacity:.7; font-weight:600; font-size:12px;}
[data-testid="stMetricValue"]{font-weight:800; font-size:24px; color:#123c33;
  white-space:normal; overflow-wrap:anywhere;}

/* Rangée de KPI responsive (ne se coupe jamais, contrairement aux colonnes) */
.dj-kpis{display:flex; flex-wrap:wrap; gap:10px; margin:4px 0 16px;}
.dj-kpi{flex:1 1 140px; background:#fff; border:1px solid #e6e4dc; border-top:3px solid #1F6F5C;
  border-radius:14px; padding:12px 15px; box-shadow:0 2px 8px rgba(20,36,31,.05);}
.dj-kpi .k-label{font-size:12px; color:#5b6b64; font-weight:600;}
.dj-kpi .k-value{font-size:22px; font-weight:800; color:#123c33; margin-top:3px; line-height:1.15;}

/* Onglets */
.stTabs [data-baseweb="tab-list"]{gap:4px; border-bottom:1px solid #e6e4dc;}
.stTabs [data-baseweb="tab"]{
  border-radius:10px 10px 0 0; padding:9px 16px; font-weight:600; font-size:14px;
}
.stTabs [aria-selected="true"]{background:#eaf3f0; color:#1F6F5C;}

/* Conteneurs bordurés */
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:14px;}
h2,h3{color:#123c33; font-weight:700;}
.stButton>button{border-radius:10px; font-weight:600; min-height:44px;}
iframe{border-radius:14px; border:1px solid #e6e4dc;}

/* --- Optimisation mobile (téléphone) --- */
@media (max-width: 640px){
  .block-container{padding-left:.6rem; padding-right:.6rem; padding-top:.6rem;}
  .dj-header{flex-direction:column; text-align:center; gap:8px; padding:16px 18px;}
  .dj-header h1{font-size:20px;}
  .dj-header p{font-size:12px;}
  .dj-badge{margin:6px auto 0;}
  [data-testid="stMetricValue"]{font-size:20px;}
  [data-testid="stMetricLabel"]{font-size:11px;}
  .stTabs [data-baseweb="tab"]{padding:7px 10px; font-size:13px;}
  h2,h3{font-size:17px;}
  .dj-kpi{flex:1 1 44%;}
  .dj-kpi .k-value{font-size:18px;}
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Accès protégé — actif seulement si la variable DJILAND_PASSWORD est définie
# ---------------------------------------------------------------------------
def _gate():
    """Porte d'accès par mot de passe (pour un partage à distance sécurisé).

    Sans mot de passe configuré (usage local), l'accès reste libre.
    """
    import os

    # Mot de passe : secrets Streamlit Cloud en priorité, sinon variable d'environnement
    pw = ""
    try:
        pw = str(st.secrets["DJILAND_PASSWORD"])
    except Exception:
        pw = os.getenv("DJILAND_PASSWORD", "")
    if not pw or st.session_state.get("auth_ok"):
        return
    st.markdown('<div class="dj-header"><div class="logo">🛰️</div><div>'
                '<h1>Djiland · Intelligence Foncière</h1>'
                '<p>Accès réservé — veuillez entrer le mot de passe</p></div></div>',
                unsafe_allow_html=True)
    with st.form("login"):
        entry = st.text_input("🔒 Mot de passe d'accès", type="password")
        if st.form_submit_button("Entrer", type="primary"):
            if entry == pw:
                st.session_state["auth_ok"] = True
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")
    st.stop()


_gate()


# ---------------------------------------------------------------------------
# Données
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Chargement des données du Grand Abidjan…")
def load():
    """Charge communes + parcelles (construit via OSM si absentes)."""
    import geopandas as gpd

    if not (GRAND_ABIDJAN_DIR / "parcelles.parquet").exists():
        from src.ingestion.build_grand_abidjan import build
        build()
    communes = gpd.read_parquet(GRAND_ABIDJAN_DIR / "communes.parquet")
    parcelles = gpd.read_parquet(GRAND_ABIDJAN_DIR / "parcelles.parquet")
    return communes, parcelles


@st.cache_data(show_spinner=False)
def synth_history(_key: tuple, mois: int = 24) -> pd.DataFrame:
    """Historique mensuel de prix par commune (24 mois, reconstruit)."""
    rng = np.random.default_rng(7)
    today = pd.Timestamp.utcnow().normalize()
    rows = []
    for com, cfg in ALL_ZONES.items():
        for m in range(mois, -1, -1):
            date = today - pd.Timedelta(days=30 * m)
            croissance = (1 + cfg["tendance"]) ** (mois - m)
            saison = 1 + 0.035 * np.sin(2 * np.pi * m / 12)
            rows.append({"commune": com,
                         "prix_m2_fcfa": cfg["prix_m2"] * croissance * saison * rng.normal(1, 0.05),
                         "date": date})
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def alertes(_key: int) -> pd.DataFrame:
    """Projection transparente du prix à 6 mois par commune + justifications."""
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


communes, parcelles = load()

# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="dj-header"><div class="logo">🛰️</div>'
    '<div><h1>Djiland · Intelligence Foncière</h1>'
    '<p>Grand Abidjan — District Autonome · satellite · marché · terrain · précision au m²</p>'
    '</div><div class="dj-badge">GRAND ABIDJAN</div></div>',
    unsafe_allow_html=True)

with st.expander("👋 Comment utiliser — guide rapide (2 min)"):
    st.markdown(
        "**Bienvenue !** Cet outil vous dit *où*, *combien* et *si c'est sûr* d'acheter un terrain "
        "dans le Grand Abidjan.\n\n"
        "- 🗺️ **Carte** — les **zones colorées** montrent les prix (bleu = bon marché → rouge = cher). "
        "**Tapez une parcelle** pour voir tout son détail. Les traits animés = **futurs métro/autoroutes**.\n"
        "- 🧮 **Calculateur** — entrez une commune, un quartier et une surface → le **prix estimé**, "
        "et **combien ce terrain valait il y a 5 ans et vaudra dans 5 ans**.\n"
        "- ⚖️ **Sécurité juridique** — le lotissement est-il **approuvé** ? Quels documents exiger du vendeur ?\n"
        "- 🚨 **Alertes** — les zones où le prix va **le plus grimper**.\n"
        "- 📄 **Rapport PDF** — un dossier complet à télécharger/partager.\n\n"
        "📱 *Sur téléphone, la carte s'ouvre en version allégée (rapide). Tout se fait au doigt.*")

def _sp(v: str) -> str:
    """Sépare les milliers par une espace fine (lisible en FCFA)."""
    return v.replace(",", " ")


_kpis = [
    ("Zones suivies", f"{communes['commune'].nunique()}"),
    ("Parcelles", _sp(f"{len(parcelles):,}")),
    ("Prix médian /m²", _sp(f"{parcelles['prix_m2_fcfa'].median():,.0f} F")),
    ("Prix max /m²", _sp(f"{parcelles['prix_m2_fcfa'].max():,.0f} F")),
    ("🔥 Zones chaudes", f"{int((communes['heat_moyen'] >= 50).sum())}"),
]
st.markdown(
    '<div class="dj-kpis">'
    + "".join(f'<div class="dj-kpi"><div class="k-label">{lbl}</div>'
              f'<div class="k-value">{val}</div></div>' for lbl, val in _kpis)
    + "</div>", unsafe_allow_html=True)

(tab_carte, tab_zone, tab_calc, tab_prix, tab_tend, tab_alertes, tab_jurid,
 tab_annot, tab_pdf) = st.tabs(
    ["🗺️ Carte", "💰 Analyse au m²", "🧮 Calculateur", "🏷️ Prix réels",
     "📈 Tendances", "🚨 Alertes", "⚖️ Sécurité juridique", "✏️ Annoter la carte",
     "📄 Rapport PDF"])

# ---------------------------------------------------------------------------
# Onglet 1 — Carte multi-calques
# ---------------------------------------------------------------------------
with tab_carte:
    from src.analysis.ga_map import build_map, build_map_lite

    t1, t2 = st.columns([2, 1])
    metric = t1.radio("Colorer les parcelles par :",
                      ["Prix/m²", "Speculation Heat", "NDVI", "Risque inondation"],
                      horizontal=True)
    mode_complet = t2.toggle("🖥️ Carte complète (ordinateur)", value=False,
                             help="Toutes les couches (POIs, voirie, NIMBY…). Plus lourde. "
                                  "Sur téléphone, laissez décoché.")
    col = {"Prix/m²": "prix_m2_fcfa", "Speculation Heat": "speculation_heat",
           "NDVI": "ndvi_moyen", "Risque inondation": "risque_inondation"}[metric]
    nonce = st.session_state.get("map_nonce", 0)

    @st.cache_data(show_spinner="Chargement de la carte…")
    def _lite_html(metric_col: str, _n: int) -> str:
        return build_map_lite(metric_col)._repr_html_()

    @st.cache_data(show_spinner="Chargement de la carte complète…")
    def _full_html(metric_col: str, _n: int) -> str:
        return build_map(metric_col)._repr_html_()

    if mode_complet:
        if st.button("⏳ Charger la carte complète (lourde)"):
            st.session_state["load_full"] = True
        if st.session_state.get("load_full"):
            components.html(_full_html(col, nonce), height=680, scrolling=False)
            st.info("🧰 Règle = mesure au m² · ✏️ crayon = dessiner · calques (haut-droite) = "
                    "satellite, relief, NIMBY, vue lagune, rendement, chantiers… · "
                    "tap sur une parcelle = détail complet.")
        else:
            st.info("👉 Cliquez « Charger la carte complète » — réservée à l'ordinateur "
                    "(toutes les couches, plus lourde).")
    else:
        components.html(_lite_html(col, nonce), height=560, scrolling=False)
        st.success("📱 **Carte allégée** (rapide sur téléphone) : zones colorées par prix, "
                   "parcelles à taper pour le détail, projets de transport futurs. "
                   "Bouton **calques** en haut à droite. Activez « Carte complète » sur ordinateur.")

    with st.expander("🗺️ Légende de la carte", expanded=False):
        from src.analysis.ga_map import legend_body
        st.markdown(
            f'<div style="font-size:13px;line-height:1.7">{legend_body(complet=mode_complet)}</div>',
            unsafe_allow_html=True)

    with st.expander("📤 Mode furtif — exporter les couches pour le terrain (QField / Maps.me)"):
        st.caption("Chargez le fichier sur le smartphone de vos agents : ils verront les "
                   "zones chaudes directement sur leur GPS, sur le terrain.")
        e1, e2 = st.columns(2)
        with e1:
            if st.button("🗂️ Générer GeoPackage (QField)"):
                from src.reports.export_gis import export_layers
                data, name = export_layers("GPKG")
                st.download_button("⬇️ Télécharger .gpkg", data=data, file_name=name,
                                   mime="application/geopackage+sqlite3")
        with e2:
            if st.button("🌍 Générer KML (Maps.me / Earth)"):
                from src.reports.export_gis import export_layers
                data, name = export_layers("KML")
                st.download_button("⬇️ Télécharger .kml", data=data, file_name=name,
                                   mime="application/vnd.google-earth.kml+xml")

# ---------------------------------------------------------------------------
# Onglet 2 — Analyse au m² par zone
# ---------------------------------------------------------------------------
with tab_zone:
    st.subheader("Analyse fine au m² par commune")
    com = st.selectbox("Commune", sorted(parcelles["commune"].unique()))
    sub = parcelles[parcelles["commune"] == com]
    info = communes[communes["commune"] == com].iloc[0]

    a, b, c, d = st.columns(4)
    a.metric("Prix moyen /m²", f"{sub['prix_m2_fcfa'].mean():,.0f} F")
    b.metric("Prix médian /m²", f"{sub['prix_m2_fcfa'].median():,.0f} F")
    c.metric("Fourchette /m²", f"{sub['prix_m2_fcfa'].min():,.0f}–{sub['prix_m2_fcfa'].max():,.0f}")
    d.metric("Superficie", f"{info['surface_km2']:.0f} km²")
    a, b, c, d = st.columns(4)
    a.metric("Heat moyen", f"{sub['speculation_heat'].mean():.0f}/100")
    b.metric("NDVI moyen", f"{sub['ndvi_moyen'].mean():.2f}")
    c.metric("Accès Plateau", f"{sub['accessibilite_min'].mean():.0f} min")
    d.metric("% pente > 15%", f"{(sub['part_pente_sup15'] > 0.5).mean()*100:.0f}%")

    g1, g2 = st.columns(2)
    with g1:
        st.plotly_chart(px.histogram(
            sub, x="prix_m2_fcfa", nbins=30, title=f"Distribution du prix au m² — {com}",
            labels={"prix_m2_fcfa": "FCFA/m²"}, color_discrete_sequence=["#1F6F5C"]),
            use_container_width=True)
    with g2:
        st.plotly_chart(px.scatter(
            sub, x="dist_plateau_km", y="prix_m2_fcfa", color="speculation_heat",
            color_continuous_scale="RdYlGn_r", title="Prix au m² vs distance au Plateau",
            labels={"dist_plateau_km": "Distance Plateau (km)", "prix_m2_fcfa": "FCFA/m²"}),
            use_container_width=True)

    st.markdown("**Parcelles les plus chaudes (précision m²)**")
    st.dataframe(sub.sort_values("speculation_heat", ascending=False)
                 [["code_parcelle", "prix_m2_fcfa", "surface_m2", "prix_total_fcfa",
                   "speculation_heat", "ndvi_moyen", "accessibilite_min", "viabilise"]]
                 .head(15).reset_index(drop=True), use_container_width=True)

# ---------------------------------------------------------------------------
# Onglet — Calculateur de prix
# ---------------------------------------------------------------------------
with tab_calc:
    st.subheader("🧮 Calculateur de prix d'un terrain")
    st.caption("Estimez le prix d'un terrain selon la commune, le quartier et la surface.")

    cc1, cc2, cc3 = st.columns(3)
    zone = cc1.selectbox("Commune / zone", sorted(parcelles["commune"].unique()),
                         index=sorted(parcelles["commune"].unique()).index("Bingerville")
                         if "Bingerville" in parcelles["commune"].values else 0)
    quartiers = QUARTIERS.get(zone, QUARTIERS_GENERIQUES)
    quartier = cc2.selectbox("Quartier / emplacement", list(quartiers))
    surface = cc3.number_input("Surface (m²)", min_value=50, max_value=100_000,
                               value=400, step=50)

    v1, v2 = st.columns(2)
    viabilise = v1.checkbox("Terrain viabilisé (eau / électricité)", value=True)
    show_proj = v2.checkbox("Afficher l'évaluation temporelle (−5 ans → +5 ans)", value=True)

    from src.ingestion.prix_reels import prix_reference

    sub = parcelles[parcelles["commune"] == zone]
    calibre = float(sub["prix_m2_fcfa"].median()) if len(sub) else None
    ref = prix_reference(zone, prix_calibre=calibre)
    if ref["source"] == "réel":
        p50 = ref["valeur"]; p25, p75 = p50 * 0.85, p50 * 1.15
        st.success(f"✅ Prix basé sur **{ref['n_obs']} observations RÉELLES** de {zone} "
                   f"(votre base propriétaire).")
    else:
        if len(sub):
            p25, p50, p75 = sub["prix_m2_fcfa"].quantile([0.25, 0.5, 0.75])
        else:
            p50 = ref["valeur"]; p25, p75 = p50 * 0.85, p50 * 1.15
        st.caption(f"ℹ️ Prix **calibré** (démo) — {ref['n_obs']} obs. réelles pour {zone} "
                   f"(seuil {3}). Ajoutez vos transactions dans l'onglet « 🏷️ Prix réels ».")
    facteur = quartiers[quartier]
    viab = 1.08 if viabilise else 1.0
    prix_m2 = p50 * facteur * viab
    total = prix_m2 * surface
    total_min, total_max = p25 * facteur * viab * surface, p75 * facteur * viab * surface

    st.markdown("### Résultat")
    r1, r2, r3 = st.columns(3)
    r1.metric("Prix estimé /m²", f"{prix_m2:,.0f} F")
    r2.metric(f"Prix total · {surface:,.0f} m²", f"{total:,.0f} F")
    r3.metric("Fourchette totale", f"{total_min:,.0f} – {total_max:,.0f} F")

    st.success(f"**Un terrain de {surface:,.0f} m² à {zone} ({quartier}) ≈ "
               f"{total:,.0f} FCFA** — fourchette {total_min:,.0f} à {total_max:,.0f} FCFA.")

    if "rendement_locatif" in sub.columns and len(sub):
        rdt = sub["rendement_locatif"].mean()
        verdict = ("🐄 vache à lait (>8%)" if rdt > 8 else
                   "⚠️ piège à capitaux (<4%)" if rdt < 4 else "correct")
        st.metric("Rendement locatif brut estimé de la zone", f"{rdt:.1f}%", help=verdict)
        st.caption(f"Interprétation : {verdict}.")

    if show_proj:
        import plotly.graph_objects as go

        from src.analysis.evaluation import evaluate

        lon = float(sub.geometry.x.mean()) if len(sub) else None
        lat = float(sub.geometry.y.mean()) if len(sub) else None
        heat = float(sub["speculation_heat"].mean()) if len(sub) else 50.0
        ev = evaluate(zone, prix_m2, surface, heat=heat, lon=lon, lat=lat)
        traj = pd.DataFrame(ev["trajectoire"])

        def _val(h):
            return traj.loc[traj["horizon"] == h, "prix_total"].iloc[0]

        st.markdown("### 📅 Évaluation temporelle (passé → futur)")
        m1, m2, m3 = st.columns(3)
        v5, v0, f5 = _val(-5), _val(0), _val(5)
        m1.metric("Il y a 5 ans", f"{v5:,.0f} F", f"{(v0/v5-1)*100:+.0f}% → aujourd'hui")
        m2.metric("Aujourd'hui", f"{v0:,.0f} F")
        m3.metric("Dans 5 ans (projeté)", f"{f5:,.0f} F", f"{(f5/v0-1)*100:+.0f}% vs aujourd'hui")

        fig = go.Figure()
        past = traj[traj["horizon"] <= 0]
        futur = traj[traj["horizon"] >= 0]
        fig.add_trace(go.Scatter(x=past["annee"], y=past["prix_total"], mode="lines+markers",
                                 name="Passé → présent", line=dict(color="#1F6F5C", width=3)))
        fig.add_trace(go.Scatter(x=futur["annee"], y=futur["prix_total"], mode="lines+markers",
                                 name="Projection future", line=dict(color="#e11d48", width=3, dash="dash")))
        fig.update_layout(height=340, title=f"Trajectoire de valeur — {surface:,.0f} m² à {zone}",
                          yaxis_title="Valeur totale (FCFA)", xaxis_title="Année",
                          margin=dict(t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

        moteurs = f"taux passé ~{ev['taux_annuel_passe']}%/an → futur ~{ev['taux_annuel_futur']}%/an"
        if ev["prime_transport_pts"] > 0:
            moteurs += (f" · 🚈 **prime futur transport +{ev['prime_transport_pts']} pts** "
                        f"(à {ev['distance_transport_futur_km']} km d'un projet)")
        if ev["prime_heat_pts"] > 0:
            moteurs += f" · 🔥 prime spéculation +{ev['prime_heat_pts']} pts"
        st.info(f"📈 Moteurs de valorisation : {moteurs}.")

    st.caption("Estimation indicative = prix médian observé dans la zone × facteur quartier × "
               "viabilisation ; trajectoire = taux annuel borné/décélérant + primes transport/spéculation. "
               "Projection NON garantie — à confirmer par expertise terrain et acte notarié.")

# ---------------------------------------------------------------------------
# Onglet — Prix réels (MOAT propriétaire)
# ---------------------------------------------------------------------------
with tab_prix:
    from src.ingestion import prix_reels as pr

    st.subheader("🏷️ Base de prix réels — votre MOAT propriétaire")
    st.caption("Chaque transaction, relevé terrain ou annonce saisie devient une donnée "
               "EXCLUSIVE. Dès qu'une zone atteint 3 observations, tout le système "
               "(calculateur, évaluation, tendances) bascule automatiquement sur vos prix réels.")

    obs = pr.load_prix_reels()
    rz = pr.resume_par_zone()
    k1, k2, k3 = st.columns(3)
    k1.metric("Observations réelles", len(obs))
    k2.metric("Zones couvertes", obs["commune"].nunique() if len(obs) else 0)
    k3.metric("Zones ≥ seuil (3)", int((rz["n_obs"] >= pr.SEUIL_REEL).sum()) if len(rz) else 0)

    st.markdown("#### ➕ Saisir une observation")
    with st.form("prix_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        commune = c1.selectbox("Commune / zone", sorted(ALL_ZONES))
        quartier = c2.text_input("Quartier (optionnel)")
        type_bien = c3.selectbox("Type de bien", pr.TYPES_BIEN)
        c4, c5, c6 = st.columns(3)
        surface = c4.number_input("Surface (m²)", min_value=1.0, value=400.0, step=10.0)
        prix_total = c5.number_input("Prix total (FCFA)", min_value=0, value=0, step=100_000)
        prix_m2 = c6.number_input("ou Prix au m² (FCFA)", min_value=0, value=0, step=1_000)
        c7, c8, c9 = st.columns(3)
        type_source = c7.selectbox("Source", pr.TYPES_SOURCE)
        date_obs = c8.date_input("Date d'observation")
        note = c9.text_input("Note (optionnel)")
        if st.form_submit_button("💾 Ajouter l'observation", type="primary"):
            if not (prix_total or prix_m2):
                st.error("Renseignez le prix total OU le prix au m².")
            else:
                pr.add_observation({
                    "date_obs": str(date_obs), "type_source": type_source, "source": type_source,
                    "commune": commune, "quartier": quartier or None, "type_bien": type_bien,
                    "surface_m2": surface, "prix_total_fcfa": prix_total or None,
                    "prix_m2_fcfa": prix_m2 or None, "note": note or None})
                st.cache_data.clear()
                st.rerun()

    st.markdown("#### 📥 Import CSV en masse")
    st.caption("Colonnes : commune, quartier, type_bien, surface_m2, "
               "prix_total_fcfa (ou prix_m2_fcfa), date_obs, source")
    up = st.file_uploader("Fichier CSV", type=["csv"])
    if up is not None:
        try:
            n = pr.import_csv(pd.read_csv(up))
            st.success(f"{n} ligne(s) importée(s).")
            st.cache_data.clear()
        except Exception as exc:
            st.error(f"Import impossible : {exc}")

    st.markdown("#### 📊 Couverture par zone (réel)")
    if len(rz):
        st.dataframe(rz, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune donnée réelle pour l'instant. Commencez par saisir vos transactions "
                "ci-dessus — c'est le début de votre avantage exclusif.")

    if len(obs):
        st.markdown("#### 🗂️ Dernières observations")
        st.dataframe(obs.tail(20)[::-1], use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Onglet 3 — Tendances
# ---------------------------------------------------------------------------
with tab_tend:
    hist = synth_history(tuple(ALL_ZONES))
    hist["mois"] = hist["date"].dt.to_period("M").astype(str)
    choix = st.multiselect("Communes à comparer", sorted(hist["commune"].unique()),
                           default=["Cocody", "Yopougon", "Songon", "Bingerville"])
    if choix:
        serie = (hist[hist["commune"].isin(choix)]
                 .groupby(["mois", "commune"])["prix_m2_fcfa"].mean().reset_index())
        st.plotly_chart(px.line(
            serie, x="mois", y="prix_m2_fcfa", color="commune", markers=True,
            labels={"prix_m2_fcfa": "FCFA/m²", "mois": "Mois"},
            title="Évolution du prix au m² par commune (24 mois)"), use_container_width=True)

# ---------------------------------------------------------------------------
# Onglet 4 — Alertes spéculatives
# ---------------------------------------------------------------------------
with tab_alertes:
    st.subheader("🚨 Communes où le prix devrait le plus grimper (6 mois)")
    st.caption("Projection transparente : croissance tendancielle + prime spéculative (Heat). "
               "À recaler avec vos transactions réelles.")
    for _, r in alertes(1).head(10).iterrows():
        with st.container(border=True):
            x, y = st.columns([3, 1])
            x.markdown(f"### 📍 {r['commune']} · *{r['type_zone']}*")
            x.markdown(f"Actuel **{r['prix_actuel']:,.0f}** → Projeté **{r['prix_projete_6m']:,.0f}** FCFA/m²")
            x.caption(f"Heat {r['heat']:.0f}/100 · baisse NDVI {r['ndvi_baisse']} · accès {r['acces_min']:.0f} min")
            y.metric("Hausse projetée", f"+{r['hausse_pct']:.1f}%")

# ---------------------------------------------------------------------------
# Onglet — Sécurité juridique & cadastre
# ---------------------------------------------------------------------------
with tab_jurid:
    import plotly.graph_objects as go

    from src.analysis import juridique as jz

    st.subheader("⚖️ Sécurité juridique & cadastre")
    st.error("**DÉMONSTRATION** — Statut de lotissement, IDUFCI et propriété ci-dessous sont "
             "**FICTIFS** (calibrés), sans connexion aux registres officiels. "
             "Vérifiez **obligatoirement** via les portails officiels avant toute transaction.")

    st.markdown("#### 🔎 Recherche parcellaire")
    s1, s2 = st.columns(2)
    zone_j = s1.selectbox("Commune / zone", sorted(parcelles["commune"].unique()), key="jz_com")
    sub_j = parcelles[parcelles["commune"] == zone_j]
    code_j = s2.selectbox("Parcelle", sub_j["code_parcelle"].tolist(), key="jz_code")
    row = parcelles[parcelles["code_parcelle"] == code_j].iloc[0]
    statut = row["lotissement_statut"]
    ic = {"Approuvé": "✅", "En sursis": "⚠️", "Annulé": "❌"}[statut]

    fic, gau = st.columns([1.3, 1])
    with fic:
        st.markdown(f"**Lotissement :** {row['lotissement_nom']}")
        st.markdown(f"**Statut (démo) :** {ic} **{statut}**")
        st.markdown(f"**IDUFCI (démo) :** `{row['idufci_demo']}`")
        st.markdown(f"**ACD :** {'oui' if row['acd'] else 'non'} · "
                    f"**Titre foncier :** {'oui' if row['titre_foncier'] else 'non'}")
        st.markdown(f"**Litige connu :** {'⚖️ OUI' if row['litige_parcelle'] else 'non'}")
        st.markdown("**Propriétaire :** 🔒 *non vérifié* — commander l'État Foncier "
                    "(DGI, 3 000 FCFA).")
    with gau:
        score = int(row["score_juridique"])
        couleur = "#16a34a" if score >= 70 else "#f59e0b" if score >= 40 else "#dc2626"
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=score,
            title={"text": "Score sécurité juridique"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": couleur},
                   "steps": [{"range": [0, 40], "color": "#fde2e2"},
                             {"range": [40, 70], "color": "#fef3d6"},
                             {"range": [70, 100], "color": "#dcfce7"}]}))
        fig.update_layout(height=240, margin=dict(t=50, b=10, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(pd.DataFrame(jz.score_details(row)), use_container_width=True, hide_index=True)

    d1, d2 = st.columns(2)
    with d1:
        st.markdown("#### 📄 Documents à exiger du vendeur")
        for doc in jz.documents_a_exiger(statut):
            st.markdown(f"- {doc}")
    with d2:
        st.markdown("#### 🧭 Guichet & démarches")
        g = jz.guichet_competent(zone_j)
        st.markdown(f"**{g['guichet']}**")
        for step in g["demarches"]:
            st.markdown(f"- {step}")

    st.markdown("#### 🔔 Alertes juridiques (démo)")
    for a in jz.alertes_juridiques(parcelles):
        st.warning(f"{a['icone']} {a['message']}  \n_{a['date']}_")

    st.markdown("#### 🌐 Vérification officielle — portails réels")
    for nom, info in jz.PORTAILS.items():
        st.markdown(f"- **{nom}** — [{info['url']}]({info['url']}) · {info['role']}")

# ---------------------------------------------------------------------------
# Onglet 5 — Annoter la carte (dessin + notes persistantes)
# ---------------------------------------------------------------------------
with tab_annot:
    from streamlit_folium import st_folium

    from src.analysis import notes as notes_mod
    from src.analysis.ga_map import build_annotation_map

    st.subheader("✏️ Dessiner & annoter la carte")
    st.caption("Outils de dessin en haut-gauche : point, ligne, zone ou rectangle. "
               "Dessinez, puis enregistrez une note à droite. Vos notes réapparaissent "
               "aussi sur la carte principale.")

    left, right = st.columns([3, 1.15])
    with left:
        out = st_folium(build_annotation_map(), height=560, use_container_width=True,
                        key="annot_map", returned_objects=["last_active_drawing"])
    with right:
        draw = out.get("last_active_drawing") if out else None
        if draw:
            st.success("Forme dessinée — ajoutez votre note :")
            with st.form("note_form", clear_on_submit=True):
                cat = st.selectbox("Catégorie", list(notes_mod.CATEGORIE_COULEUR))
                auteur = st.text_input("Auteur", value="Djiland")
                texte = st.text_area("Note", placeholder="Ex : terrain viabilisé, prix négociable…")
                if st.form_submit_button("💾 Enregistrer", type="primary"):
                    notes_mod.save_note(draw, texte, cat, auteur)
                    st.cache_data.clear()
                    st.session_state["map_nonce"] = st.session_state.get("map_nonce", 0) + 1
                    st.rerun()
        else:
            st.info("👉 Dessinez d'abord une forme sur la carte, puis annotez-la ici.")

        st.divider()
        existing = notes_mod.load_notes()
        st.markdown(f"**{len(existing)} annotation(s) enregistrée(s)**")
        for i, r in existing.iterrows():
            with st.container(border=True):
                st.markdown(f"**{r['categorie']}** — {r['note'] or '_(sans texte)_'}")
                st.caption(f"{r['auteur']} · {r['date']}")
                if st.button("🗑️ Supprimer", key=f"del{i}"):
                    notes_mod.delete_note(i)
                    st.cache_data.clear()
                    st.session_state["map_nonce"] = st.session_state.get("map_nonce", 0) + 1
                    st.rerun()

# ---------------------------------------------------------------------------
# Onglet 6 — Rapport PDF
# ---------------------------------------------------------------------------
with tab_pdf:
    from src.reports.pdf import build_full_report

    st.subheader("📄 Rapport d'évaluation professionnel (livrable complet)")
    st.caption("Dossier PDF multi-sections : verdict, évaluation, trajectoire de valeur "
               "(−5 → +5 ans), transport, environnement, spéculation, sécurité juridique "
               "+ checklist documents. Prêt à remettre à un client ou un investisseur.")

    pc1, pc2 = st.columns(2)
    zone_p = pc1.selectbox("Commune / zone", sorted(parcelles["commune"].unique()), key="pdf_com")
    sub_p = parcelles[parcelles["commune"] == zone_p]
    code = pc2.selectbox("Parcelle", sub_p["code_parcelle"].tolist(), key="pdf_code")

    grow = parcelles[parcelles["code_parcelle"] == code].iloc[0]
    row = grow.to_dict()
    row["lon"] = float(grow.geometry.x)
    row["lat"] = float(grow.geometry.y)
    row.pop("geometry", None)

    v1, v2, v3, v4 = st.columns(4)
    v1.metric("Prix /m²", f"{row.get('prix_m2_fcfa', 0):,.0f} F")
    v2.metric("Heat", f"{row.get('speculation_heat', 0):.0f}/100")
    v3.metric("Rendement", f"{row.get('rendement_locatif', 0)}%")
    v4.metric("Score juridique", f"{row.get('score_juridique', 0)}/100")

    if st.button("🖨️ Générer le rapport PDF complet", type="primary"):
        with st.spinner("Génération du dossier…"):
            pdf = build_full_report(row)
        st.download_button("⬇️ Télécharger le rapport PDF", data=pdf,
                           file_name=f"rapport_djiland_{code}.pdf", mime="application/pdf")
        st.success("Rapport généré ✅")
