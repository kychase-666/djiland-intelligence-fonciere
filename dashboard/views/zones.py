"""Analyse par zone — fiche détaillée au m² et classement comparatif des zones."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.core import fcfa, kpi_row, load, page_header, pct, section, style_fig

communes, parcelles = load()

page_header("Analyse par zone",
            "Fiche détaillée d'une zone, au m² près, et classement comparatif de toutes les "
            "zones suivies.", rubrique="Marché")

zones = sorted(parcelles["commune"].unique())
com = st.selectbox("Zone analysée", zones,
                   index=zones.index("Cocody") if "Cocody" in zones else 0)
sub = parcelles[parcelles["commune"] == com]
info = communes[communes["commune"] == com].iloc[0]

kpi_row([
    {"l": "Prix médian au m²", "v": fcfa(sub["prix_m2_fcfa"].median()),
     "h": f"moyenne {fcfa(sub['prix_m2_fcfa'].mean())}"},
    {"l": "Fourchette au m²", "v": f"{sub['prix_m2_fcfa'].quantile(.1)/1e3:,.0f}–"
                                 f"{sub['prix_m2_fcfa'].quantile(.9)/1e3:,.0f} k F",
     "h": "10ᵉ – 90ᵉ percentile"},
    {"l": "Rendement locatif", "v": pct(sub["rendement_locatif"].median()), "h": "brut médian"},
    {"l": "Dynamique spéculative", "v": f"{sub['speculation_heat'].mean():.0f}/100", "or": True},
    {"l": "Accès au Plateau", "v": f"{sub['accessibilite_min'].mean():.0f} min",
     "h": f"superficie {info['surface_km2']:,.0f} km²".replace(",", " ")},
    {"l": "Vue lagune", "v": pct(sub["vue_lagune"].astype(bool).mean() * 100, 0),
     "h": "des parcelles suivies"},
])

g1, g2 = st.columns(2, gap="large")
with g1:
    section("Distribution des prix au m²")
    fig = px.histogram(sub, x="prix_m2_fcfa", nbins=28, labels={"prix_m2_fcfa": "FCFA/m²"},
                       color_discrete_sequence=["#0B5D4B"])
    fig.update_layout(bargap=0.06, yaxis_title="Parcelles")
    st.plotly_chart(style_fig(fig, hauteur=320), width="stretch", config={"displayModeBar": False})
with g2:
    section("Prix et distance au Plateau", "couleur = dynamique")
    fig = px.scatter(sub, x="dist_plateau_km", y="prix_m2_fcfa", color="speculation_heat",
                     color_continuous_scale=["#CFE3DB", "#B8893B", "#B3261E"],
                     labels={"dist_plateau_km": "Distance au Plateau (km)",
                             "prix_m2_fcfa": "FCFA/m²", "speculation_heat": "Dyn."})
    fig.update_traces(marker=dict(size=8, line=dict(width=0)))
    st.plotly_chart(style_fig(fig, hauteur=320), width="stretch", config={"displayModeBar": False})

section("Parcelles à plus forte dynamique", f"{com}")
st.dataframe(
    sub.sort_values("speculation_heat", ascending=False)
    [["code_parcelle", "prix_m2_fcfa", "surface_m2", "prix_total_fcfa", "speculation_heat",
      "rendement_locatif", "accessibilite_min", "viabilise"]].head(15),
    width="stretch", hide_index=True,
    column_config={
        "code_parcelle": "Parcelle",
        "prix_m2_fcfa": st.column_config.NumberColumn("F/m²", format="localized"),
        "surface_m2": st.column_config.NumberColumn("Surface m²", format="localized"),
        "prix_total_fcfa": st.column_config.NumberColumn("Prix total (F)", format="localized"),
        "speculation_heat": st.column_config.ProgressColumn("Dynamique", min_value=0,
                                                            max_value=100, format="%.0f"),
        "rendement_locatif": st.column_config.NumberColumn("Rendement %", format="%.1f"),
        "accessibilite_min": st.column_config.NumberColumn("Accès (min)", format="%.0f"),
        "viabilise": st.column_config.CheckboxColumn("Viabilisé")})

section("Classement comparatif des zones")
cl = (parcelles.groupby("commune").agg(
    prix_median=("prix_m2_fcfa", "median"), rendement=("rendement_locatif", "median"),
    dynamique=("speculation_heat", "mean"), acces=("accessibilite_min", "mean"),
    parcelles=("code_parcelle", "size")).reset_index()
    .merge(communes[["commune", "type_zone"]], on="commune")
    .sort_values("prix_median", ascending=False))
st.dataframe(
    pd.DataFrame(cl), width="stretch", hide_index=True,
    column_config={
        "commune": "Zone", "type_zone": "Profil",
        "prix_median": st.column_config.NumberColumn("Prix médian F/m²", format="localized"),
        "rendement": st.column_config.NumberColumn("Rendement %", format="%.1f"),
        "dynamique": st.column_config.ProgressColumn("Dynamique", min_value=0, max_value=100,
                                                     format="%.0f"),
        "acces": st.column_config.NumberColumn("Accès Plateau (min)", format="%.0f"),
        "parcelles": st.column_config.NumberColumn("Parcelles")},
    column_order=["commune", "type_zone", "prix_median", "rendement", "dynamique", "acces",
                  "parcelles"])
