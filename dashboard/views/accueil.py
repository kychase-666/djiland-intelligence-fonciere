"""Vue d'ensemble — tableau de bord de direction (pilotage du marché)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import COMMUNES_GRAND_ABIDJAN
from dashboard.core import (
    alertes,
    badge,
    fcfa,
    kpi_row,
    load,
    mfcfa,
    note,
    page_header,
    parcelles_scorees,
    pct,
    section,
    style_fig,
    synth_history,
    transport,
)

communes, parcelles = load()
sc = parcelles_scorees()
hist = synth_history()
al = alertes()
tr = transport()

page_header("Vue d'ensemble du marché foncier",
            "Grand Abidjan, corridor côtier et villes de l'intérieur · "
            f"{communes['commune'].nunique()} zones · "
            + f"{len(parcelles):,} parcelles suivies".replace(",", " "),
            rubrique="Pilotage")

# --- Indice des prix (base 100 il y a 24 mois) ------------------------------
hist = hist.copy()
hist["mois"] = hist["date"].dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
base = hist.sort_values("date").groupby("commune")["prix_m2_fcfa"].transform("first")
hist["indice"] = hist["prix_m2_fcfa"] / base * 100
hist["groupe"] = hist["commune"].map(
    lambda c: "District d'Abidjan" if c in COMMUNES_GRAND_ABIDJAN else "Corridor & intérieur")
idx = hist.groupby("mois")["indice"].median()
var12 = (idx.iloc[-1] / idx.iloc[-13] - 1) * 100 if len(idx) > 12 else None

eligibles = sc[(sc["lotissement_statut"] == "Approuvé") & (~sc["litige_parcelle"].astype(bool))]
qualifiees = int(eligibles["verdict_cle"].isin(["forte", "interessant"]).sum())
futurs = int((tr["statut"] != "existant").sum()) if tr is not None else 0

kpi_row([
    {"l": "Prix médian au m²", "v": fcfa(parcelles["prix_m2_fcfa"].median()),
     "delta": pct(var12, signe=True) + " / 12 mois" if var12 is not None else None,
     "sens": "up" if (var12 or 0) >= 0 else "down", "h": "Terrains, toutes zones"},
    {"l": "Rendement locatif médian", "v": pct(parcelles["rendement_locatif"].median()),
     "h": "Brut estimé, avant charges"},
    {"l": "Opportunités qualifiées", "v": f"{qualifiees}",
     "h": "Lotissement approuvé, sans litige", "or": True},
    {"l": "Zones en forte dynamique", "v": f"{int((communes['heat_moyen'] >= 50).sum())}",
     "h": "Indice spéculatif ≥ 50/100"},
    {"l": "Projets d'infrastructure", "v": f"{futurs}",
     "h": "Métro, autoroutes, ponts à venir"},
])

# --- Prix par zone + meilleures opportunités --------------------------------
g, d = st.columns([1.55, 1], gap="large")
with g:
    section("Prix médian au m² par zone", "terrains, FCFA")
    pz = (parcelles.groupby("commune")["prix_m2_fcfa"].median().rename("prix").reset_index()
          .merge(communes[["commune", "heat_moyen"]], on="commune")
          .sort_values("prix"))
    fig = px.bar(pz, x="prix", y="commune", orientation="h", color="heat_moyen",
                 color_continuous_scale=["#CFE3DB", "#0B5D4B"],
                 labels={"prix": "FCFA/m²", "commune": "", "heat_moyen": "Dynamique"},
                 hover_data={"prix": ":,.0f", "heat_moyen": ":.0f"})
    fig.update_traces(marker_line_width=0)
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(style_fig(fig, hauteur=560), width="stretch", config={"displayModeBar": False})

with d:
    section("Meilleures opportunités", "score sur 100")
    top = eligibles.sort_values(["score_opportunite", "rendement_locatif"],
                                ascending=False).head(6)
    lignes = []
    for i, (_, r) in enumerate(top.iterrows(), start=1):
        lignes.append(
            f'<div class="dj-rank" title="{r["code_parcelle"]}"><div class="n">{i}</div>'
            f'<div class="t"><b>{r["commune"]}</b><div>{mfcfa(r["prix_total_fcfa"])} · '
            + f'{r["surface_m2"]:,.0f} m² · '.replace(",", " ")
            + f'{pct(r["rendement_locatif"])}</div></div>'
            f'<div class="s">{r["score_opportunite"]:.0f}</div></div>')
    with st.container(border=True):
        st.markdown("".join(lignes), unsafe_allow_html=True)
    st.page_link("views/opportunites.py", label="Ouvrir le Chasseur d'opportunités",
                 icon=":material/arrow_forward:")

    section("Hausses attendues à 6 mois")
    with st.container(border=True):
        for _, r in al.head(5).iterrows():
            c1, c2 = st.columns([2.2, 1])
            c1.markdown(f"**{r['commune']}**  \n<span class='dj-note'>{r['type_zone']}</span>",
                        unsafe_allow_html=True)
            c2.markdown(badge(pct(r["hausse_pct"], signe=True), "ok"), unsafe_allow_html=True)
    st.page_link("views/alertes.py", label="Voir le centre d'alertes",
                 icon=":material/arrow_forward:")

# --- Indice des prix ---------------------------------------------------------
section("Indice des prix fonciers", "base 100 il y a 24 mois · médiane des zones")
ig = hist.groupby(["mois", "groupe"])["indice"].median().reset_index()
ig = pd.concat([ig, idx.rename("indice").reset_index().assign(groupe="Ensemble")])
fig = px.line(ig, x="mois", y="indice", color="groupe",
              color_discrete_map={"Ensemble": "#0B5D4B", "District d'Abidjan": "#B8893B",
                                  "Corridor & intérieur": "#2F6FA8"},
              labels={"mois": "", "indice": "Indice", "groupe": ""})
fig.update_traces(line=dict(width=2.6))
st.plotly_chart(style_fig(fig, hauteur=330), width="stretch", config={"displayModeBar": False})

# --- Grands projets ----------------------------------------------------------
if tr is not None:
    section("Grands projets d'infrastructure", "moteurs de valorisation à moyen terme")
    statut_badge = {"existant": ("En service", "neutral"), "en_construction": ("En construction", "warn"),
                    "planifié": ("Planifié", "ok")}
    lignes = ["<table style='width:100%;border-collapse:collapse;font-size:.88rem'>"]
    for _, t in tr.sort_values("statut").iterrows():
        lib, nat = statut_badge.get(t["statut"], (t["statut"], "neutral"))
        lignes.append(f"<tr style='border-bottom:1px solid #EEF1F3'><td style='padding:8px 4px'>"
                      f"<b>{t['nom']}</b></td><td style='padding:8px 4px;color:#5B6B65'>"
                      f"{t['mode'].capitalize()}</td><td style='padding:8px 4px;text-align:right'>"
                      f"{badge(lib, nat)}</td></tr>")
    lignes.append("</table>")
    with st.container(border=True):
        st.markdown("".join(lignes), unsafe_allow_html=True)
    note("Tracés des projets futurs : curés à partir des projets connus, géométries approximatives.")

# --- Accès rapide & aide -----------------------------------------------------
section("Accès rapide")
a, b, c, e = st.columns(4)
a.page_link("views/carte.py", label="Carte interactive", icon=":material/map:")
b.page_link("views/bilan.py", label="Bilan promoteur", icon=":material/account_balance:")
c.page_link("views/comparateur.py", label="Comparer des terrains", icon=":material/compare_arrows:")
e.page_link("views/rapports.py", label="Rapports PDF", icon=":material/picture_as_pdf:")

with st.expander("Comment utiliser la plateforme"):
    st.markdown(
        "- **Pilotage** — cette vue, la **carte** (zones colorées par prix, parcelles cliquables, "
        "futurs métro/autoroutes) et le **centre d'alertes**.\n"
        "- **Marché** — analyse fine par zone et tendances des prix.\n"
        "- **Investissement** — le **Chasseur d'opportunités** (votre budget → les meilleurs "
        "terrains), l'**évaluation** d'un terrain (valeur passée et future), le **bilan promoteur** "
        "(marge, TRI, prix d'équilibre) et le **comparateur**.\n"
        "- **Conformité & terrain** — sécurité juridique (lotissement, documents à exiger) et "
        "annotations de terrain.\n"
        "- **Données & livrables** — vos **prix réels** (qui recalent automatiquement les "
        "estimations) et les **rapports PDF** à remettre à un client ou un investisseur.\n\n"
        "Sur téléphone, le menu s'ouvre avec le bouton en haut à gauche.")
