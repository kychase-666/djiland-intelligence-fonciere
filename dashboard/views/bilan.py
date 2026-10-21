"""Bilan promoteur — étude de faisabilité d'une opération (marge, TRI, sensibilité)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.core import (
    badge,
    fcfa,
    kpi_row,
    mfcfa,
    note,
    page_header,
    parcelles_scorees,
    pct,
    section,
    style_fig,
)
from src.analysis.bilan import PROGRAMMES, STANDINGS, ParamsBilan, calculer_bilan, sensibilite
from src.ingestion.prix_reels import facteurs_recalage

page_header("Bilan promoteur",
            "Étude de faisabilité d'une opération : du terrain à la vente — chiffre d'affaires, "
            "coût de revient, marge, TRI, prix d'équilibre et sensibilité.",
            rubrique="Investissement")

sc = parcelles_scorees()
facteurs = facteurs_recalage(sc)
zones = sorted(sc["commune"].unique())
arrondi = lambda x, pas=5_000: float(round(x / pas) * pas)  # noqa: E731

# --- 1 · Programme -----------------------------------------------------------
with st.container(border=True):
    st.markdown("**1 · Programme immobilier**")
    p1, p2 = st.columns([1.4, 1])
    programme = p1.selectbox("Type d'opération", list(PROGRAMMES),
                             format_func=lambda k: PROGRAMMES[k][0], index=1)
    lib, coef_def, rdt_def, cout_def = PROGRAMMES[programme]
    lotissement = programme == "lotissement"
    standing = "Standard"
    if not lotissement:
        standing = p2.segmented_control("Standing", list(STANDINGS), default="Standard",
                                        key=f"standing_{programme}") or "Standard"

# --- 2 · Terrain -------------------------------------------------------------
with st.container(border=True):
    st.markdown("**2 · Terrain**")
    t1, t2, t3 = st.columns(3)
    zone = t1.selectbox("Zone", zones, index=zones.index("Bingerville") if "Bingerville" in zones else 0)
    zsub = sc[sc["commune"] == zone]
    f_zone = facteurs.get(zone, {}).get("facteur", 1.0)
    med_zone = float(zsub["prix_m2_fcfa"].median()) * f_zone
    if lotissement:
        surface = t2.number_input("Surface du terrain brut (m²)", 1_000, 2_000_000, 20_000, 1_000)
        prix_brut = t3.number_input("Prix du terrain brut (FCFA/m²)", 0, 1_000_000,
                                    int(arrondi(med_zone * 0.35, 500)), 500,
                                    help="Terrain non loti : estimé par défaut à 35 % du prix des "
                                         "lots viabilisés de la zone. À ajuster.")
        prix_terrain = surface * prix_brut
    else:
        mode = t2.segmented_control("Origine", ["Parcelle suivie", "Saisie libre"],
                                    default="Parcelle suivie", key="bilan_origine") or "Parcelle suivie"
        if mode == "Parcelle suivie":
            choix = zsub.sort_values("score_opportunite", ascending=False)
            libs = {r["code_parcelle"]: f"{r['code_parcelle']} · {r['surface_m2']:,.0f} m² · "
                    f"{mfcfa(r['prix_total_fcfa'] * f_zone)}".replace(",", " ")
                    for _, r in choix.iterrows()}
            code = t3.selectbox("Parcelle", list(libs), format_func=libs.get)
            row = choix[choix["code_parcelle"] == code].iloc[0]
            surface = float(row["surface_m2"])
            prix_terrain = float(row["prix_total_fcfa"]) * f_zone
        else:
            surface = t3.number_input("Surface (m²)", 100, 500_000, 600, 50)
            pm2 = st.number_input("Prix du terrain (FCFA/m²)", 0, 2_000_000,
                                  int(arrondi(med_zone, 1_000)), 1_000)
            prix_terrain = surface * pm2
    note(f"Terrain : {surface:,.0f} m² pour {fcfa(prix_terrain)}".replace(",", " ")
         + (f" — prix recalé sur vos {facteurs[zone]['n_obs']} observations réelles."
            if zone in facteurs else " — prix calibré de la zone."))

# --- 3 · Construction & prix de vente ---------------------------------------
with st.container(border=True):
    st.markdown("**3 · Construction et commercialisation**")
    k1, k2, k3, k4 = st.columns(4)
    if lotissement:
        part_cess = k1.number_input("Part cessible en lots (%)", 40.0, 90.0, 70.0, 1.0,
                                    help="Le reste : voirie, espaces verts, équipements.")
        vrd = k2.number_input("Viabilisation / VRD (FCFA/m² de terrain)", 0, 100_000, 9_000, 500)
        coef, rdt_plan, cout_m2 = 0.0, 0.0, 0.0
    else:
        part_cess = 70.0
        coef = k1.number_input("Constructibilité (m² plancher / m² terrain)", 0.1, 6.0,
                               float(coef_def), 0.05, key=f"coef_{programme}")
        rdt_plan = k2.number_input("Rendement de plan (vendable / plancher)", 0.5, 1.0,
                                   float(rdt_def), 0.01, key=f"rdtp_{programme}")
        cout_m2 = k3.number_input("Coût de construction (FCFA/m² plancher)", 50_000, 2_000_000,
                                  int(cout_def * STANDINGS[standing]), 5_000,
                                  key=f"cout_{programme}_{standing}")
        vrd = k4.number_input("VRD (FCFA/m² de terrain)", 0, 100_000, 6_000, 500)

    base = ParamsBilan(surface_terrain_m2=surface, prix_terrain_total=prix_terrain,
                       prix_vente_m2=1.0, programme=programme, coef_constructibilite=coef,
                       rendement_plan=rdt_plan, cout_construction_m2=cout_m2,
                       vrd_m2_terrain=vrd, part_cessible_pct=part_cess)

    with st.expander("Hypothèses financières", icon=":material/tune:"):
        h1, h2, h3, h4 = st.columns(4)
        acq = h1.number_input("Frais d'acquisition (% du terrain)", 0.0, 30.0, 10.0, 0.5,
                              help="Notaire, enregistrement, ACD — estimation à confirmer.")
        hon = h2.number_input("Honoraires & études (% travaux)", 0.0, 25.0, 8.0, 0.5)
        imp = h3.number_input("Imprévus (% travaux)", 0.0, 25.0, 5.0, 0.5)
        com = h4.number_input("Frais commerciaux (% du CA)", 0.0, 15.0, 3.0, 0.5)
        h5, h6, h7 = st.columns(3)
        cred = h5.number_input("Part financée par crédit (%)", 0.0, 100.0, 60.0, 5.0)
        taux = h6.number_input("Taux du crédit (%/an)", 0.0, 30.0, 9.0, 0.25)
        duree = h7.number_input("Durée de l'opération (mois)", 3, 120, 18 if lotissement else 24, 1)
    base = ParamsBilan(**{**base.__dict__, "frais_acquisition_pct": acq, "honoraires_pct": hon,
                          "imprevus_pct": imp, "frais_commerciaux_pct": com,
                          "part_credit_pct": cred, "taux_credit_pct": taux,
                          "duree_mois": int(duree)})

    cible = calculer_bilan(base)["prix_marge20_m2"]
    defaut_vente = arrondi(med_zone if lotissement else (cible or 0))
    unite = "m² de lot" if lotissement else "m² vendable"
    v1, v2 = st.columns([1.3, 1], vertical_alignment="bottom")
    prix_vente = v1.number_input(
        f"Prix de vente (FCFA/{unite})", 0, 10_000_000, int(defaut_vente), 5_000,
        key=f"pv_{programme}_{zone}_{standing}",
        help=("Par défaut : prix médian des terrains de la zone (lots viabilisés)."
              if lotissement else
              "Valeur de départ = prix permettant 20 % de marge. Remplacez-le par le prix de "
              "marché constaté (annonces, notaire, vos ventes) pour juger la faisabilité."))
    v2.markdown(badge("Valeur de départ : prix médian de la zone" if lotissement
                      else "Valeur de départ : prix pour 20 % de marge", "neutral"),
                unsafe_allow_html=True)

params = ParamsBilan(**{**base.__dict__, "prix_vente_m2": float(prix_vente)})
r = calculer_bilan(params)

# --- Résultats ---------------------------------------------------------------
marge_pct = r["marge_pct_ca"]
if marge_pct is None or marge_pct < 0:
    verdict, nat = "Opération déficitaire", "bad"
elif marge_pct < 10:
    verdict, nat = "Opération risquée (marge < 10 %)", "bad"
elif marge_pct < 20:
    verdict, nat = "Opération à optimiser (marge 10–20 %)", "warn"
else:
    verdict, nat = "Opération attractive (marge ≥ 20 %)", "ok"

section("Résultats de l'opération", PROGRAMMES[programme][0]
        + ("" if lotissement else f" · {standing.lower()}") + f" · {zone}")
st.markdown(badge(verdict, nat), unsafe_allow_html=True)
st.write("")
kpi_row([
    {"l": "Chiffre d'affaires", "v": mfcfa(r["chiffre_affaires"]),
     "h": f"{r['surface_vendable_m2']:,.0f} m² vendables".replace(",", " ")},
    {"l": "Coût de revient", "v": mfcfa(r["cout_revient"]),
     "h": f"{fcfa(r['cout_revient_m2_vendable'])}/m² vendable" if r["cout_revient_m2_vendable"] else ""},
    {"l": "Marge brute", "v": mfcfa(r["marge"]),
     "delta": pct(marge_pct) + " du CA" if marge_pct is not None else None,
     "sens": "up" if (marge_pct or -1) >= 0 else "down", "or": True},
    {"l": "TRI du projet", "v": pct(r["tri_projet_pct"]) if r["tri_projet_pct"] is not None else "—",
     "h": "annualisé, avant financement"},
    {"l": "Prix d'équilibre", "v": fcfa(r["prix_equilibre_m2"]) if r["prix_equilibre_m2"] else "—",
     "h": f"par {unite} (marge nulle)"},
    {"l": "Fonds propres requis", "v": mfcfa(r["fonds_propres"]),
     "h": ("rentabilité " + pct(r["rentabilite_fonds_propres_pct"]))
     if r["rentabilite_fonds_propres_pct"] is not None else ""},
])

g, d = st.columns([1.35, 1], gap="large")
with g:
    section("Du chiffre d'affaires à la marge")
    postes = r["postes"]
    noms = list(postes)
    fig = go.Figure(go.Waterfall(
        x=["Chiffre d'affaires"] + noms + ["Marge"],
        measure=["absolute"] + ["relative"] * len(noms) + ["total"],
        y=[r["chiffre_affaires"]] + [-v for v in postes.values()] + [0],
        text=[mfcfa(r["chiffre_affaires"]).replace(" FCFA", "")]
        + [mfcfa(v).replace(" FCFA", "") for v in postes.values()]
        + [mfcfa(r["marge"]).replace(" FCFA", "")],
        textposition="outside", connector=dict(line=dict(color="#C9D3CF", width=1)),
        increasing=dict(marker=dict(color="#0B5D4B")),
        decreasing=dict(marker=dict(color="#C2553D")),
        totals=dict(marker=dict(color="#B8893B"))))
    fig.update_layout(showlegend=False, yaxis_title="FCFA")
    fig.update_xaxes(tickangle=-35)
    st.plotly_chart(style_fig(fig, hauteur=420), width="stretch", config={"displayModeBar": False})
with d:
    section("Détail du bilan")
    det = pd.DataFrame({"Poste": noms, "Montant (FCFA)": list(postes.values())})
    det["% du CA"] = det["Montant (FCFA)"] / r["chiffre_affaires"] * 100 if r["chiffre_affaires"] else 0
    det.loc[len(det)] = ["Coût de revient total", r["cout_revient"],
                         r["cout_revient"] / r["chiffre_affaires"] * 100 if r["chiffre_affaires"] else 0]
    det.loc[len(det)] = ["Marge brute", r["marge"], marge_pct or 0]
    st.dataframe(det, width="stretch", hide_index=True, column_config={
        "Montant (FCFA)": st.column_config.NumberColumn(format="localized"),
        "% du CA": st.column_config.NumberColumn(format="%.1f %%")})

section("Sensibilité de la marge", "% du chiffre d'affaires selon le prix de vente et le coût des travaux")
sens = sensibilite(params)
fig = px.imshow(sens.values, x=list(sens.columns), y=list(sens.index), text_auto=".1f",
                color_continuous_scale=["#B3261E", "#F7E7C6", "#0B5D4B"],
                color_continuous_midpoint=0, aspect="auto",
                labels=dict(x="Variation du prix de vente", y="Variation du coût des travaux",
                            color="Marge %"))
fig.update_layout(coloraxis_showscale=False)
st.plotly_chart(style_fig(fig, hauteur=330), width="stretch", config={"displayModeBar": False})
note("Lecture : chaque case donne la marge (en % du CA) si le prix de vente (colonnes) et le "
     "coût des travaux (lignes) varient. Les cases rouges signalent un risque de perte.")

section("Livrables")
a, b = st.columns(2)
contexte = {"zone": zone, "programme": PROGRAMMES[programme][0],
            "standing": None if lotissement else standing, "verdict": verdict}
if a.button("Générer le bilan PDF", type="primary", icon=":material/picture_as_pdf:",
            width="stretch"):
    from src.reports.pdf import build_bilan_pdf
    pdf = build_bilan_pdf(params, r, contexte)
    a.download_button("Télécharger le bilan", data=pdf,
                      file_name=f"bilan_promoteur_{zone}.pdf".replace(" ", "_"),
                      mime="application/pdf", icon=":material/download:", width="stretch")
b.download_button("Exporter le bilan (CSV)", data=det.to_csv(index=False).encode("utf-8-sig"),
                  file_name=f"bilan_promoteur_{zone}.csv".replace(" ", "_"), mime="text/csv",
                  icon=":material/table_view:", width="stretch")

note("Hypothèses : ventes encaissées à la livraison (prudent), travaux étalés sur la durée, "
     "crédit tiré progressivement (encours moyen ≈ 60 %). Ordres de grandeur à adapter à votre "
     "opération ; ne remplace pas l'étude d'un architecte, d'un économiste de la construction "
     "et d'un notaire.")
