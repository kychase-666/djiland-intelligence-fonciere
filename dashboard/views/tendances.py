"""Tendances des prix — évolution sur 24 mois et variations par zone."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.core import note, page_header, pct, section, style_fig, synth_history

page_header("Tendances des prix",
            "Évolution du prix au m² sur 24 mois et variations comparées des zones.",
            rubrique="Marché")

hist = synth_history().copy()
hist["mois"] = hist["date"].dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
zones = sorted(hist["commune"].unique())

c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
choix = c1.multiselect("Zones à comparer", zones,
                       default=[z for z in ["Cocody", "Yopougon", "Songon", "Bingerville",
                                            "Assinie-Mafia"] if z in zones])
vue = c2.segmented_control("Affichage", ["FCFA/m²", "Indice base 100"], default="FCFA/m²",
                           key="tend_vue") or "FCFA/m²"

if choix:
    serie = (hist[hist["commune"].isin(choix)]
             .groupby(["mois", "commune"])["prix_m2_fcfa"].mean().reset_index())
    if vue == "Indice base 100":
        serie["valeur"] = serie["prix_m2_fcfa"] / serie.groupby("commune")["prix_m2_fcfa"] \
            .transform("first") * 100
        ytitre = "Indice (base 100)"
    else:
        serie["valeur"] = serie["prix_m2_fcfa"]
        ytitre = "FCFA/m²"
    fig = px.line(serie, x="mois", y="valeur", color="commune",
                  labels={"valeur": ytitre, "mois": "", "commune": ""})
    fig.update_traces(line=dict(width=2.4))
    st.plotly_chart(style_fig(fig, hauteur=420), width="stretch", config={"displayModeBar": False})
else:
    st.info("Sélectionnez au moins une zone.", icon=":material/trending_up:")

section("Variations par zone")
piv = hist.groupby(["commune", "mois"])["prix_m2_fcfa"].mean().unstack().sort_index(axis=1)
fin = pd.DataFrame({
    "prix_actuel": piv.iloc[:, -1],
    "var_12m": (piv.iloc[:, -1] / piv.iloc[:, -13] - 1) * 100,
    "var_24m": (piv.iloc[:, -1] / piv.iloc[:, 0] - 1) * 100,
}).reset_index().sort_values("var_12m", ascending=False)
st.dataframe(fin, width="stretch", hide_index=True, column_config={
    "commune": "Zone",
    "prix_actuel": st.column_config.NumberColumn("Prix actuel F/m²", format="localized"),
    "var_12m": st.column_config.NumberColumn("Variation 12 mois", format="%+.1f %%"),
    "var_24m": st.column_config.NumberColumn("Variation 24 mois", format="%+.1f %%")})
note("Historique reconstitué à partir des tendances calibrées de chaque zone (démonstration). "
     f"Il sera remplacé par vos prix réels au fil des saisies. Médiane 12 mois : "
     f"{pct(fin['var_12m'].median(), signe=True)}.")
