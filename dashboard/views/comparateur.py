"""Comparateur de terrains — jusqu'à 4 parcelles côte à côte, profil radar."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.core import fcfa, note, page_header, parcelles_scorees, pct, section, style_fig

page_header("Comparateur de terrains",
            "Jusqu'à 4 terrains côte à côte : prix, potentiel, rendement, risques et sécurité "
            "juridique. L'étoile signale le meilleur terrain sur chaque critère.",
            rubrique="Investissement")

sc = parcelles_scorees()
libelle = {r["code_parcelle"]: f"{r['code_parcelle']} · {r['commune']} · "
           f"{r['surface_m2']:,.0f} m² · score {r['score_opportunite']:.0f}".replace(",", " ")
           for _, r in sc.iterrows()}
qualif = sc[(sc["lotissement_statut"] == "Approuvé") & (~sc["litige_parcelle"].astype(bool))]
defaut = list(qualif.sort_values("score_opportunite", ascending=False)["code_parcelle"].head(3))
choix = st.multiselect("Terrains à comparer (4 au maximum)", list(libelle), default=defaut,
                       format_func=libelle.get, max_selections=4)

if len(choix) < 2:
    st.info("Sélectionnez au moins deux terrains.", icon=":material/compare_arrows:")
    st.stop()

sel = sc.set_index("code_parcelle").loc[choix]

# (libellé, colonne, sens : +1 plus haut = mieux, -1 plus bas = mieux, 0 = info, format)
CRITERES = [
    ("Zone", "commune", 0, str),
    ("Surface", "surface_m2", 0, lambda v: f"{v:,.0f} m²".replace(",", " ")),
    ("Prix au m²", "prix_m2_fcfa", -1, fcfa),
    ("Prix total", "prix_total_fcfa", -1, fcfa),
    ("Score d'opportunité", "score_opportunite", 1, lambda v: f"{v:.0f}/100"),
    ("Verdict", "verdict", 0, str),
    ("Rendement locatif", "rendement_locatif", 1, lambda v: pct(v)),
    ("Dynamique spéculative", "speculation_heat", 1, lambda v: f"{v:.0f}/100"),
    ("Accès au Plateau", "accessibilite_min", -1, lambda v: f"{v:.0f} min"),
    ("Transport futur le plus proche", "dist_transport_km", -1, lambda v: f"{v:.1f} km".replace(".", ",")),
    ("Lotissement (démo)", "lotissement_statut", 0, str),
    ("Score juridique (démo)", "score_juridique", 1, lambda v: f"{v:.0f}/100"),
    ("Risque d'inondation", "risque_inondation", -1, lambda v: f"{v:.2f}".replace(".", ",")),
    ("Malus nuisances", "malus_nuisance", -1, lambda v: pct(v * 100, 0)),
    ("Vue lagune", "vue_lagune", 1, lambda v: "Oui" if v else "Non"),
]
tableau = {}
for lib, colname, sens, fmt in CRITERES:
    vals = sel[colname]
    meilleur = None
    if sens and vals.nunique() > 1:
        num = vals.astype(float)
        meilleur = num.idxmax() if sens > 0 else num.idxmin()
    tableau[lib] = {code: fmt(v) + ("  ★" if code == meilleur else "") for code, v in vals.items()}
df = pd.DataFrame(tableau).T
df.columns = [f"{c} ({sel.loc[c, 'commune']})" for c in df.columns]

section("Tableau comparatif")
st.dataframe(df, width="stretch", height=(len(df) + 1) * 35 + 3)

# --- Profil radar (rangs centiles sur l'ensemble des parcelles suivies) -------
section("Profil des terrains", "rang sur 100 parmi toutes les parcelles suivies (100 = meilleur)")
rang = lambda s, asc=True: s.rank(pct=True, ascending=asc) * 100  # noqa: E731
env = -(sc["risque_inondation"].fillna(0) + sc["malus_nuisance"].fillna(0))
axes = {
    "Rendement": rang(sc["rendement_locatif"]),
    "Potentiel": rang(sc["speculation_heat"]),
    "Accessibilité": rang(sc["accessibilite_min"], asc=False),
    "Transports futurs": rang(sc["dist_transport_km"], asc=False),
    "Sécurité juridique": rang(sc["score_juridique"]),
    "Environnement": rang(env),
    "Prix abordable": rang(sc["prix_m2_fcfa"], asc=False),
}
prof = pd.DataFrame(axes).set_index(sc["code_parcelle"])
couleurs = ["#0B5D4B", "#B8893B", "#2F6FA8", "#C2553D"]
fig = go.Figure()
dims = list(axes)
for i, code in enumerate(choix):
    v = prof.loc[code, dims].tolist()
    fig.add_trace(go.Scatterpolar(r=v + v[:1], theta=dims + dims[:1], fill="toself",
                                  name=f"{code} ({sel.loc[code, 'commune']})",
                                  line=dict(color=couleurs[i], width=2),
                                  fillcolor=couleurs[i], opacity=0.28))
fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], tickfont=dict(size=9),
                                             gridcolor="#E2E7EA"),
                             angularaxis=dict(gridcolor="#E2E7EA")))
st.plotly_chart(style_fig(fig, hauteur=460), width="stretch", config={"displayModeBar": False})

st.download_button("Exporter la comparaison (CSV)",
                   data=df.to_csv().encode("utf-8-sig"), file_name="djiland_comparaison.csv",
                   mime="text/csv", icon=":material/table_view:")
note("Prix calibrés et statuts juridiques de démonstration : à confirmer avant toute décision. "
     "Les rangs du radar comparent chaque terrain à l'ensemble des parcelles suivies.")
