"""Centre d'alertes — hausses de prix attendues, signaux terrain, alertes juridiques."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.core import (
    alertes,
    badge,
    fcfa,
    kpi_row,
    load,
    note,
    page_header,
    pct,
    section,
)
from src.analysis import juridique as jz

communes, parcelles = load()
al = alertes()
alj = jz.alertes_juridiques(parcelles)

page_header("Centre d'alertes",
            "Ce qui bouge sur le marché : hausses de prix attendues, chantiers détectés par "
            "satellite, vallées de rattrapage et alertes juridiques.", rubrique="Pilotage")

kpi_row([
    {"l": "Zones en hausse > 10 % à 6 mois", "v": f"{int((al['hausse_pct'] > 10).sum())}", "or": True},
    {"l": "Chantiers détectés (radar)", "v": f"{int(parcelles['chantier_detecte'].astype(bool).sum())}",
     "h": "nouvelles constructions / terrassements"},
    {"l": "Vallées de rattrapage", "v": f"{int(parcelles['rattrapage'].astype(bool).sum())}",
     "h": "parcelles en retard sur leur voisinage"},
    {"l": "Alertes juridiques", "v": f"{len(alj)}", "h": "lotissements en sursis / annulés (démo)"},
])

t1, t2, t3 = st.tabs(["Hausses de prix attendues", "Signaux terrain", "Alertes juridiques"])

with t1:
    note("Projection transparente à 6 mois : croissance tendancielle de la zone + prime de "
         "dynamique spéculative. À recaler avec vos transactions réelles.")
    for _, r in al.head(10).iterrows():
        with st.container(border=True):
            x, y = st.columns([3.2, 1], vertical_alignment="center")
            x.markdown(f"**{r['commune']}** &nbsp; {badge(r['type_zone'], 'neutral')}",
                       unsafe_allow_html=True)
            x.caption(f"{fcfa(r['prix_actuel'])}/m² aujourd'hui → {fcfa(r['prix_projete_6m'])}/m² "
                      f"projeté · dynamique {r['heat']:.0f}/100 · accès Plateau "
                      f"{r['acces_min']:.0f} min")
            y.markdown(f"<div style='text-align:right'>{badge(pct(r['hausse_pct'], signe=True), 'ok')}"
                       "</div>", unsafe_allow_html=True)

with t2:
    sig = (parcelles.assign(chantiers=parcelles["chantier_detecte"].astype(bool),
                            rattrapage_=parcelles["rattrapage"].astype(bool))
           .groupby("commune").agg(chantiers=("chantiers", "sum"),
                                   rattrapage=("rattrapage_", "sum"),
                                   dynamique=("speculation_heat", "mean"))
           .reset_index().sort_values(["chantiers", "dynamique"], ascending=False))
    section("Activité détectée par zone")
    st.dataframe(pd.DataFrame(sig), width="stretch", hide_index=True, column_config={
        "commune": "Zone",
        "chantiers": st.column_config.NumberColumn("Chantiers détectés"),
        "rattrapage": st.column_config.NumberColumn("Vallées de rattrapage"),
        "dynamique": st.column_config.ProgressColumn("Dynamique", min_value=0, max_value=100,
                                                     format="%.0f")})
    note("Chantiers : changement du signal radar Sentinel-1 (terrassement, construction). Vallée "
         "de rattrapage : parcelle nettement moins dynamique que son voisinage immédiat — un "
         "signal d'achat potentiel.")

with t3:
    st.warning("Statuts de lotissement de **démonstration** : à vérifier sur les portails "
               "officiels (MCLU, DGI) avant toute transaction.", icon=":material/gavel:")
    for a in alj:
        with st.container(border=True):
            st.markdown(f"{a['message'].replace('**', '')}  \n<span class='dj-note'>{a['date']}</span>",
                        unsafe_allow_html=True)
    st.page_link("views/juridique.py", label="Ouvrir la sécurité juridique",
                 icon=":material/arrow_forward:")
