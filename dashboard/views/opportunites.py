"""Chasseur d'opportunités — budget et critères → meilleurs terrains, classés."""
from __future__ import annotations

import folium
import pandas as pd
import streamlit as st

from dashboard.core import (
    fcfa,
    kpi_row,
    note,
    page_header,
    parcelles_scorees,
    section,
)
from src.analysis.ga_map import PLAN_CLAIR_ATTR, PLAN_CLAIR_TILES, fit_quand_visible
from src.analysis.opportunites import VERDICTS, rechercher
from src.ingestion.prix_reels import facteurs_recalage
from src.reports.pdf import build_full_report

page_header("Chasseur d'opportunités",
            "Indiquez votre budget et vos critères : les terrains sont classés par score "
            "d'opportunité (rendement, potentiel, futurs transports, vue lagune, moins les "
            "risques). Même verdict que dans les rapports PDF.", rubrique="Investissement")

sc = parcelles_scorees()

with st.container(border=True):
    st.markdown("**Critères de recherche**")
    f1, f2, f3 = st.columns(3)
    budget_m = f1.number_input("Budget maximum (millions de FCFA)", min_value=1,
                               max_value=2000, value=50, step=5,
                               help="Ex. 50 = 50 000 000 FCFA")
    budget = budget_m * 1_000_000
    surf = f2.slider("Surface (m²)", 100, 2000, (300, 1000), step=50)
    rdt_min = f3.slider("Rendement locatif minimum (%)", 0.0, 11.0, 0.0, 0.5)
    zones_opp = st.multiselect("Zones", sorted(sc["commune"].unique()),
                               placeholder="Toutes les zones (cliquez pour filtrer)")
    o1, o2, o3, o4 = st.columns(4)
    approuve = o1.checkbox("Lotissement approuvé", value=True)
    sans_lit = o2.checkbox("Sans litige", value=True)
    sans_nuis = o3.checkbox("Sans nuisance", value=False)
    vue_lag = o4.checkbox("Vue lagune", value=False)

facteurs = facteurs_recalage(sc)
res = rechercher(sc, budget, surf[0], surf[1], zones_opp, approuve, sans_lit,
                 sans_nuis, vue_lag, rdt_min, facteurs)
if facteurs:
    st.success("Prix recalés sur **vos observations réelles** pour : "
               + ", ".join(f"{c} ({v['n_obs']} obs.)" for c, v in facteurs.items()),
               icon=":material/verified:")

if res.empty:
    st.warning("Aucun terrain ne correspond à ces critères. Augmentez le budget, élargissez "
               "la surface ou décochez un filtre.", icon=":material/search_off:")
else:
    top = res.head(30)
    kpi_row([
        {"l": "Terrains trouvés", "v": f"{len(res)}"},
        {"l": "Meilleur score", "v": f"{top['score_opportunite'].iloc[0]:.0f}/100", "or": True},
        {"l": "Intéressants ou mieux",
         "v": f"{int(res['verdict_cle'].isin(['forte', 'interessant']).sum())}"},
        {"l": "Prix médian trouvé", "v": fcfa(res["prix_total_retenu"].median())},
    ])

    section("Localisation des 30 meilleurs", "pastille = rang · couleur = verdict")
    m = folium.Map(location=[top.geometry.y.mean(), top.geometry.x.mean()], zoom_start=11,
                   tiles=PLAN_CLAIR_TILES, attr=PLAN_CLAIR_ATTR, control_scale=True)
    for rang, (_, r) in enumerate(top.iterrows(), start=1):
        coul = VERDICTS[r["verdict_cle"]][1]
        folium.Marker(
            [r.geometry.y, r.geometry.x],
            icon=folium.DivIcon(icon_size=(26, 26), icon_anchor=(13, 13), html=(
                f'<div style="background:{coul};width:26px;height:26px;border-radius:50%;'
                f'border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45);color:#fff;'
                f'font:700 11px Inter,sans-serif;line-height:22px;text-align:center">{rang}</div>')),
            tooltip=f"#{rang} · {r['commune']} · {r['score_opportunite']:.0f}/100",
            popup=folium.Popup(
                f"<b>#{rang} · {r['code_parcelle']}</b><br><b>{r['verdict']}</b> "
                f"({r['score_opportunite']:.0f}/100)<br>{r['commune']} · "
                f"{r['surface_m2']:,.0f} m²<br>{r['prix_total_retenu']:,.0f} FCFA "
                f"({r['prix_m2_retenu']:,.0f} F/m²)<br>Rendement {r['rendement_locatif']} % · "
                f"transport futur à {r['dist_transport_km']} km", max_width=260),
        ).add_to(m)
    fit_quand_visible(m, (top.geometry.y.min(), top.geometry.x.min()),
                      (top.geometry.y.max(), top.geometry.x.max()))
    st.iframe(m.get_root().render(), height=440)

    section("Classement détaillé")
    tableau = top.assign(rang=range(1, len(top) + 1))[[
        "rang", "verdict", "score_opportunite", "commune", "code_parcelle", "surface_m2",
        "prix_m2_retenu", "prix_total_retenu", "rendement_locatif", "lotissement_statut",
        "dist_transport_km", "accessibilite_min", "source_prix"]]
    st.dataframe(
        pd.DataFrame(tableau), width="stretch", hide_index=True,
        column_config={
            "rang": st.column_config.NumberColumn("#", width="small"),
            "verdict": "Verdict",
            "score_opportunite": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%.0f"),
            "commune": "Zone", "code_parcelle": "Parcelle",
            "surface_m2": st.column_config.NumberColumn("Surface m²", format="localized"),
            "prix_m2_retenu": st.column_config.NumberColumn("F/m²", format="localized"),
            "prix_total_retenu": st.column_config.NumberColumn("Prix total (F)",
                                                               format="localized"),
            "rendement_locatif": st.column_config.NumberColumn("Rendement %", format="%.1f"),
            "lotissement_statut": "Lotissement (démo)",
            "dist_transport_km": st.column_config.NumberColumn("Transport futur (km)",
                                                               format="%.1f"),
            "accessibilite_min": st.column_config.NumberColumn("Accès Plateau (min)",
                                                               format="%.0f"),
            "source_prix": "Source prix"})

    export = pd.DataFrame(res.drop(columns="geometry")).assign(
        lon=res.geometry.x.round(6), lat=res.geometry.y.round(6))
    a, b = st.columns([1, 1.4])
    a.download_button("Exporter tous les résultats (Excel / CSV)",
                      data=export.to_csv(index=False).encode("utf-8-sig"),
                      file_name="djiland_opportunites.csv", mime="text/csv",
                      icon=":material/table_view:", width="stretch")

    section("Dossier d'un terrain de la liste")
    libelles = [f"#{i} · {r['code_parcelle']} · {r['commune']} · {r['verdict']}"
                for i, (_, r) in enumerate(top.iterrows(), start=1)]
    c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
    idx = c1.selectbox("Terrain", range(len(libelles)), format_func=lambda i: libelles[i],
                       key="opp_choix")
    if c2.button("Générer le rapport PDF", key="opp_pdf", type="primary",
                 icon=":material/picture_as_pdf:", width="stretch"):
        sel = top.iloc[idx]
        row = sel.drop(labels="geometry").to_dict()
        row.update(lon=float(sel.geometry.x), lat=float(sel.geometry.y),
                   prix_m2_fcfa=float(sel["prix_m2_retenu"]),
                   prix_total_fcfa=float(sel["prix_total_retenu"]))
        with st.spinner("Génération du dossier…"):
            pdf = build_full_report(row)
        st.download_button("Télécharger le rapport", data=pdf,
                           file_name=f"rapport_djiland_{sel['code_parcelle']}.pdf",
                           mime="application/pdf", key="opp_dl", icon=":material/download:")
    st.page_link("views/comparateur.py", label="Comparer plusieurs terrains côte à côte",
                 icon=":material/compare_arrows:")

note("Classement indicatif : prix calibrés (sauf zones recalées sur vos prix réels) et "
     "statuts juridiques de démonstration. À confirmer par visite, État Foncier et notaire.")
