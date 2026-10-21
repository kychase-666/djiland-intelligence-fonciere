"""Sécurité juridique — statut du lotissement, score, documents à exiger, démarches."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.core import badge, load, note, page_header, section, style_fig
from src.analysis import juridique as jz

communes, parcelles = load()

page_header("Sécurité juridique",
            "Le lotissement est-il approuvé ? Le terrain est-il sous litige ? Quels documents "
            "exiger du vendeur et où les vérifier ?", rubrique="Conformité & terrain")

st.error("**Données de démonstration** — statut de lotissement, IDUFCI et titre ci-dessous sont "
         "fictifs (calibrés), sans connexion aux registres officiels. Vérifiez obligatoirement "
         "sur les portails officiels avant toute transaction.", icon=":material/report:")

s1, s2 = st.columns(2)
zones = sorted(parcelles["commune"].unique())
zone_j = s1.selectbox("Zone", zones, key="jz_com")
sub_j = parcelles[parcelles["commune"] == zone_j]
code_j = s2.selectbox("Parcelle", sub_j["code_parcelle"].tolist(), key="jz_code")
row = parcelles[parcelles["code_parcelle"] == code_j].iloc[0]
statut = row["lotissement_statut"]
nat = {"Approuvé": "ok", "En sursis": "warn", "Annulé": "bad"}[statut]
oui = lambda b: badge("Oui", "ok") if b else badge("Non", "neutral")  # noqa: E731

fic, gau = st.columns([1.3, 1], gap="large")
with fic:
    section("Fiche parcellaire")
    with st.container(border=True):
        lignes = [
            ("Lotissement", row["lotissement_nom"]),
            ("Statut d'approbation", badge(statut, nat)),
            ("Identifiant IDUFCI (démo)", f"<code>{row['idufci_demo']}</code>"),
            ("Arrêté de concession définitive (ACD)", oui(row["acd"])),
            ("Titre foncier", oui(row["titre_foncier"])),
            ("Litige connu", badge("Oui — litige", "bad") if row["litige_parcelle"]
             else badge("Aucun", "ok")),
            ("Propriétaire", "<i>non vérifié</i> — commander l'État Foncier (DGI, 3 000 FCFA)"),
        ]
        st.markdown("<table style='width:100%;font-size:.9rem'>" + "".join(
            f"<tr><td style='padding:7px 4px;color:#5B6B65;width:46%'>{k}</td>"
            f"<td style='padding:7px 4px'>{v}</td></tr>" for k, v in lignes) + "</table>",
            unsafe_allow_html=True)
with gau:
    section("Score de sécurité juridique")
    score = int(row["score_juridique"])
    couleur = "#0B5D4B" if score >= 70 else "#C77700" if score >= 40 else "#B3261E"
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score, number=dict(suffix="/100", font=dict(size=34)),
        gauge={"axis": {"range": [0, 100], "tickwidth": 0}, "bar": {"color": couleur, "thickness": 0.32},
               "bgcolor": "#F1F4F3", "borderwidth": 0,
               "steps": [{"range": [0, 40], "color": "#FBEAE8"},
                         {"range": [40, 70], "color": "#FFF4E0"},
                         {"range": [70, 100], "color": "#E6F3EE"}]}))
    st.plotly_chart(style_fig(fig, hauteur=230), width="stretch", config={"displayModeBar": False})
    st.dataframe(pd.DataFrame(jz.score_details(row)), width="stretch", hide_index=True,
                 column_config={"critere": "Critère", "obtenu": "Points", "max": "Maximum"})

d1, d2 = st.columns(2, gap="large")
with d1:
    section("Documents à exiger du vendeur")
    with st.container(border=True):
        st.markdown("\n".join(f"- {d}" for d in jz.documents_a_exiger(statut)))
with d2:
    section("Guichet et démarches")
    g = jz.guichet_competent(zone_j)
    with st.container(border=True):
        st.markdown(f"**{g['guichet']}**\n\n" + "\n".join(f"- {s}" for s in g["demarches"]))

section("Vérification officielle", "portails de l'administration ivoirienne")
with st.container(border=True):
    st.markdown("\n".join(f"- **{nom}** — [{info['url']}]({info['url']}) · {info['role']}"
                          for nom, info in jz.PORTAILS.items()))
note("Le module est prêt à se connecter à ces registres dès que Djiland dispose d'accès "
     "professionnels (IDUFCI, SIGFU, DGI, MCLU).")
