"""Rapports PDF — dossier d'évaluation professionnel d'une parcelle."""
from __future__ import annotations

import streamlit as st

from dashboard.core import fcfa, kpi_row, load, note, page_header, parcelles_scorees, pct, section
from src.reports.pdf import build_full_report

communes, parcelles = load()
sc = parcelles_scorees()

page_header("Rapports PDF",
            "Dossier d'évaluation complet d'une parcelle, prêt à remettre à un client, un "
            "partenaire ou un investisseur.", rubrique="Données & livrables")

c1, c2 = st.columns(2)
zones = sorted(parcelles["commune"].unique())
zone_p = c1.selectbox("Zone", zones, key="pdf_com")
sub_p = sc[sc["commune"] == zone_p].sort_values("score_opportunite", ascending=False)
code = c2.selectbox("Parcelle (classées par score d'opportunité)", sub_p["code_parcelle"].tolist(),
                    key="pdf_code")

grow = sc[sc["code_parcelle"] == code].iloc[0]
row = grow.drop(labels="geometry").to_dict()
row["lon"], row["lat"] = float(grow.geometry.x), float(grow.geometry.y)

kpi_row([
    {"l": "Prix total", "v": fcfa(row["prix_total_fcfa"]), "h": f"{fcfa(row['prix_m2_fcfa'])}/m²"},
    {"l": "Verdict", "v": row["verdict"].capitalize(), "h": f"score {row['score_opportunite']:.0f}/100",
     "or": True},
    {"l": "Rendement locatif", "v": pct(row["rendement_locatif"])},
    {"l": "Score juridique (démo)", "v": f"{row['score_juridique']:.0f}/100"},
])

section("Contenu du dossier")
with st.container(border=True):
    st.markdown(
        "1. **Verdict** et score d'opportunité (identiques au Chasseur d'opportunités)\n"
        "2. **Évaluation financière** : prix, fourchette, rendement locatif\n"
        "3. **Trajectoire de valeur** : il y a 5 ans → aujourd'hui → dans 5 ans, avec graphique\n"
        "4. **Transport et infrastructures futures**\n"
        "5. **Environnement et risques** : végétation, pente, inondation, nuisances, vue lagune\n"
        "6. **Signaux spéculatifs** : dynamique, chantiers, rattrapage\n"
        "7. **Sécurité juridique** et liste des documents à exiger du vendeur")

if st.button("Générer le rapport PDF", type="primary", icon=":material/picture_as_pdf:"):
    with st.spinner("Génération du dossier…"):
        pdf = build_full_report(row)
    st.download_button("Télécharger le rapport", data=pdf,
                       file_name=f"rapport_djiland_{code}.pdf", mime="application/pdf",
                       icon=":material/download:")
    st.success("Rapport prêt.", icon=":material/check_circle:")

note("Pour une étude de faisabilité (marge, TRI) d'une opération sur ce terrain, utilisez le "
     "Bilan promoteur, qui produit son propre PDF.")
st.page_link("views/bilan.py", label="Ouvrir le Bilan promoteur", icon=":material/account_balance:")
