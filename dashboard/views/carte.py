"""Carte interactive — prix, dynamique, environnement, projets de transport."""
from __future__ import annotations

import streamlit as st

from dashboard.core import note, page_header, section
from src.analysis.ga_map import build_map, build_map_lite, legend_body

page_header("Carte interactive",
            "Zones colorées par prix, parcelles cliquables, futurs métro et autoroutes. "
            "Touchez une parcelle pour sa fiche complète.", rubrique="Pilotage")

c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
metric = c1.segmented_control(
    "Colorer les parcelles par", ["Prix au m²", "Dynamique spéculative", "Végétation (NDVI)",
                                  "Risque d'inondation"],
    default="Prix au m²", key="carte_metric") or "Prix au m²"
mode_complet = c2.toggle("Carte complète (ordinateur)", value=False,
                         help="Toutes les couches : équipements, voirie, nuisances, vue lagune, "
                              "rendement, chantiers, statut juridique… Plus lourde : à réserver "
                              "à un ordinateur.")
col = {"Prix au m²": "prix_m2_fcfa", "Dynamique spéculative": "speculation_heat",
       "Végétation (NDVI)": "ndvi_moyen", "Risque d'inondation": "risque_inondation"}[metric]
nonce = st.session_state.get("map_nonce", 0)


@st.cache_data(show_spinner="Chargement de la carte…")
def _lite_html(metric_col: str, _n: int) -> str:
    return build_map_lite(metric_col).get_root().render()


@st.cache_data(show_spinner="Chargement de la carte complète…")
def _full_html(metric_col: str, _n: int) -> str:
    return build_map(metric_col).get_root().render()


if mode_complet:
    if not st.session_state.get("load_full"):
        st.info("La carte complète contient toutes les couches d'analyse (environ 11 Mo). "
                "Chargez-la sur un ordinateur.", icon=":material/desktop_windows:")
        if st.button("Charger la carte complète", icon=":material/layers:", type="primary"):
            st.session_state["load_full"] = True
            st.rerun()
    else:
        st.iframe(_full_html(col, nonce), height=700)
else:
    st.iframe(_lite_html(col, nonce), height=600)

note("Outils sur la carte : bouton des calques (en haut à droite) pour changer de fond "
     "(plan, satellite, relief) et activer les couches · règle = mesure de surface au m² · "
     "crayon = dessiner (carte complète).")

section("Légende")
with st.container(border=True):
    st.markdown(f'<div style="font-size:.88rem;line-height:1.75">'
                f'{legend_body(complet=mode_complet)}</div>', unsafe_allow_html=True)

with st.expander("Exporter les couches pour le terrain (QField · Maps.me · Google Earth)",
                 icon=":material/download:"):
    st.caption("Chargez le fichier sur le smartphone de vos agents : les zones à potentiel "
               "s'affichent directement sur leur GPS, sur le terrain.")
    e1, e2 = st.columns(2)
    with e1:
        if st.button("Préparer le GeoPackage (QField)", width="stretch"):
            from src.reports.export_gis import export_layers
            data, name = export_layers("GPKG")
            st.download_button("Télécharger le .gpkg", data=data, file_name=name,
                               mime="application/geopackage+sqlite3", icon=":material/download:")
    with e2:
        if st.button("Préparer le KML (Maps.me · Earth)", width="stretch"):
            from src.reports.export_gis import export_layers
            data, name = export_layers("KML")
            st.download_button("Télécharger le .kml", data=data, file_name=name,
                               mime="application/vnd.google-earth.kml+xml",
                               icon=":material/download:")
