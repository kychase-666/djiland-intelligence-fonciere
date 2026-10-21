"""Évaluation d'un terrain — prix estimé, fourchette, valeur passée et future."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import QUARTIERS, QUARTIERS_GENERIQUES
from dashboard.core import fcfa, kpi_row, load, note, page_header, pct, section, style_fig
from src.analysis.evaluation import evaluate
from src.ingestion.prix_reels import SEUIL_REEL, prix_reference

communes, parcelles = load()

page_header("Évaluation d'un terrain",
            "Prix estimé selon la zone, le quartier et la surface — avec la valeur du terrain "
            "il y a 5 ans et sa projection à 5 ans.", rubrique="Investissement")

zones = sorted(parcelles["commune"].unique())
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    zone = c1.selectbox("Zone", zones,
                        index=zones.index("Bingerville") if "Bingerville" in zones else 0)
    quartiers = QUARTIERS.get(zone, QUARTIERS_GENERIQUES)
    quartier = c2.selectbox("Quartier / emplacement", list(quartiers))
    surface = c3.number_input("Surface (m²)", min_value=50, max_value=100_000, value=400, step=50)
    v1, v2 = st.columns(2)
    viabilise = v1.toggle("Terrain viabilisé (eau / électricité)", value=True)
    show_proj = v2.toggle("Évaluation temporelle (−5 ans → +5 ans)", value=True)

sub = parcelles[parcelles["commune"] == zone]
calibre = float(sub["prix_m2_fcfa"].median()) if len(sub) else None
ref = prix_reference(zone, prix_calibre=calibre)
if ref["source"] == "réel":
    p50 = ref["valeur"]
    p25, p75 = p50 * 0.85, p50 * 1.15
    st.success(f"Prix fondé sur **{ref['n_obs']} observations réelles** de {zone} "
               "(votre base propriétaire).", icon=":material/verified:")
else:
    if len(sub):
        p25, p50, p75 = sub["prix_m2_fcfa"].quantile([0.25, 0.5, 0.75])
    else:
        p50 = ref["valeur"]
        p25, p75 = p50 * 0.85, p50 * 1.15
    note(f"Prix calibré (démonstration) — {ref['n_obs']} observation(s) réelle(s) pour {zone}, "
         f"seuil {SEUIL_REEL}. Ajoutez vos transactions dans « Prix réels » pour basculer sur "
         "vos propres prix.")

facteur = quartiers[quartier]
viab = 1.08 if viabilise else 1.0
prix_m2 = p50 * facteur * viab
total = prix_m2 * surface
total_min, total_max = p25 * facteur * viab * surface, p75 * facteur * viab * surface
rdt = sub["rendement_locatif"].mean() if len(sub) else None

section("Résultat de l'évaluation", f"{surface:,.0f} m² · {zone} · {quartier}".replace(",", " "))
kpi_row([
    {"l": "Valeur estimée", "v": fcfa(total), "h": f"{fcfa(prix_m2)} / m²", "or": True},
    {"l": "Fourchette basse", "v": fcfa(total_min), "h": "25ᵉ percentile de la zone"},
    {"l": "Fourchette haute", "v": fcfa(total_max), "h": "75ᵉ percentile de la zone"},
    {"l": "Rendement locatif de la zone", "v": pct(rdt) if rdt is not None else "—",
     "h": ("vache à lait (> 8 %)" if (rdt or 0) > 8 else
           "piège à capitaux (< 4 %)" if (rdt or 99) < 4 else "dans la moyenne")},
])

if show_proj:
    lon = float(sub.geometry.x.mean()) if len(sub) else None
    lat = float(sub.geometry.y.mean()) if len(sub) else None
    heat = float(sub["speculation_heat"].mean()) if len(sub) else 50.0
    ev = evaluate(zone, prix_m2, surface, heat=heat, lon=lon, lat=lat)
    traj = pd.DataFrame(ev["trajectoire"])
    val = lambda h: traj.loc[traj["horizon"] == h, "prix_total"].iloc[0]  # noqa: E731
    v5, v0, f5 = val(-5), val(0), val(5)

    section("Trajectoire de valeur", "passé reconstitué → projection prudente")
    kpi_row([
        {"l": "Il y a 5 ans", "v": fcfa(v5), "delta": pct((v0 / v5 - 1) * 100, 0, True),
         "sens": "up", "h": "progression jusqu'à aujourd'hui"},
        {"l": "Aujourd'hui", "v": fcfa(v0)},
        {"l": "Dans 5 ans (projeté)", "v": fcfa(f5), "delta": pct((f5 / v0 - 1) * 100, 0, True),
         "sens": "up", "h": f"taux ~{pct(ev['taux_annuel_futur'])}/an", "or": True},
    ])
    fig = go.Figure()
    past, futur = traj[traj["horizon"] <= 0], traj[traj["horizon"] >= 0]
    fig.add_trace(go.Scatter(x=past["annee"], y=past["prix_total"], mode="lines+markers",
                             name="Passé → aujourd'hui", line=dict(color="#0B5D4B", width=3)))
    fig.add_trace(go.Scatter(x=futur["annee"], y=futur["prix_total"], mode="lines+markers",
                             name="Projection", line=dict(color="#B8893B", width=3, dash="dash")))
    fig.update_layout(yaxis_title="Valeur totale (FCFA)", xaxis_title="")
    st.plotly_chart(style_fig(fig, hauteur=340), width="stretch", config={"displayModeBar": False})

    moteurs = [f"taux passé ~{pct(ev['taux_annuel_passe'])}/an → futur "
               f"~{pct(ev['taux_annuel_futur'])}/an"]
    if ev["prime_transport_pts"] > 0:
        moteurs.append(f"prime transport futur +{ev['prime_transport_pts']} pts "
                       f"(à {ev['distance_transport_futur_km']} km d'un projet)")
    if ev["prime_heat_pts"] > 0:
        moteurs.append(f"prime de dynamique +{ev['prime_heat_pts']} pts")
    st.info("**Moteurs de valorisation** : " + " · ".join(moteurs) + ".",
            icon=":material/insights:")

note("Estimation indicative = prix médian de la zone × facteur quartier × viabilisation ; "
     "trajectoire = taux annuel borné et décélérant + primes transport / dynamique. Projection "
     "non garantie — à confirmer par expertise terrain et acte notarié.")
st.page_link("views/bilan.py", label="Monter un bilan promoteur sur ce terrain",
             icon=":material/account_balance:")
