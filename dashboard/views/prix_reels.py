"""Prix réels — la base propriétaire de Djiland (transactions, relevés, annonces)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import ALL_ZONES
from dashboard.core import (
    EN_LIGNE,
    MSG_NON_ENREGISTRE,
    alerte_base,
    kpi_row,
    note,
    page_header,
    section,
)
from src import persistance
from src.analysis import notes as notes_bk
from src.ingestion import prix_reels as pr

page_header("Prix réels",
            "Votre base exclusive : chaque transaction, relevé terrain ou annonce saisi ici "
            "devient une donnée propriétaire. Dès 3 observations dans une zone, toute la "
            "plateforme bascule sur vos prix réels.", rubrique="Données & livrables")

obs = pr.load_prix_reels()
rz = pr.resume_par_zone()
etat_base = persistance.etat()
kpi_row([
    {"l": "Observations réelles", "v": f"{len(obs)}", "or": True},
    {"l": "Zones couvertes", "v": f"{obs['commune'].nunique() if len(obs) else 0}"},
    {"l": f"Zones ≥ {pr.SEUIL_REEL} observations",
     "v": f"{int((rz['n_obs'] >= pr.SEUIL_REEL).sum()) if len(rz) else 0}",
     "h": "prix réels utilisés par la plateforme"},
    {"l": "Enregistrement", "v": "Permanent" if etat_base["mode"] == "base" else
     ("Temporaire" if EN_LIGNE else "Local"),
     "h": "base de données en ligne" if etat_base["mode"] == "base" else
     ("effacé à la mise en veille" if EN_LIGNE else "fichiers sur cet ordinateur")},
])
alerte_base()

t1, t2, t3 = st.tabs(["Saisir une observation", "Import en masse", "Sauvegarde & restauration"])

with t1:
    with st.form("prix_form", clear_on_submit=True, border=True):
        c1, c2, c3 = st.columns(3)
        commune = c1.selectbox("Zone", sorted(ALL_ZONES))
        quartier = c2.text_input("Quartier (optionnel)")
        type_bien = c3.selectbox("Type de bien", pr.TYPES_BIEN)
        c4, c5, c6 = st.columns(3)
        surface = c4.number_input("Surface (m²)", min_value=1.0, value=400.0, step=10.0)
        prix_total = c5.number_input("Prix total (FCFA)", min_value=0, value=0, step=100_000)
        prix_m2 = c6.number_input("ou prix au m² (FCFA)", min_value=0, value=0, step=1_000)
        c7, c8, c9 = st.columns(3)
        type_source = c7.selectbox("Source", pr.TYPES_SOURCE)
        date_obs = c8.date_input("Date d'observation", format="DD/MM/YYYY")
        note_txt = c9.text_input("Note (optionnel)")
        if st.form_submit_button("Ajouter l'observation", type="primary", icon=":material/add:"):
            if not (prix_total or prix_m2):
                st.error("Renseignez le prix total ou le prix au m².")
            else:
                try:
                    pr.add_observation({
                        "date_obs": str(date_obs), "type_source": type_source,
                        "source": type_source, "commune": commune,
                        "quartier": quartier or None, "type_bien": type_bien,
                        "surface_m2": surface, "prix_total_fcfa": prix_total or None,
                        "prix_m2_fcfa": prix_m2 or None, "note": note_txt or None})
                except persistance.BaseIndisponible:
                    st.error(MSG_NON_ENREGISTRE)
                else:
                    st.cache_data.clear()
                    st.rerun()

with t2:
    note("Colonnes acceptées : commune, quartier, type_bien, surface_m2, prix_total_fcfa (ou "
         "prix_m2_fcfa), date_obs, source. Un fichier de sauvegarde Djiland convient aussi.")
    up = st.file_uploader("Fichier CSV", type=["csv"])
    # Garde-fou : un même fichier n'est importé qu'une fois (sinon chaque clic
    # ailleurs dans la page ré-importait le fichier → doublons).
    if up is not None and not st.session_state.get(f"prix_ok_{up.file_id}"):
        try:
            n = pr.import_csv(pd.read_csv(up))
            st.session_state[f"prix_ok_{up.file_id}"] = True
            st.success(f"{n} ligne(s) importée(s).", icon=":material/check_circle:")
            st.cache_data.clear()
        except Exception as exc:
            st.error(f"Import impossible : {exc}")

with t3:
    if etat_base["mode"] == "base":
        fournisseur = ".".join((etat_base["hote"] or "").split(".")[-2:])
        st.success(f"**Enregistrement permanent activé** : vos prix réels et notes de carte sont "
                   f"stockés dans votre base de données en ligne ({fournisseur}). Ils survivent "
                   "aux mises en veille et aux mises à jour. La sauvegarde CSV reste utile "
                   "comme archive.", icon=":material/cloud_done:")
    elif EN_LIGNE:
        st.warning("**Version en ligne** : l'hébergement gratuit **efface les données saisies** "
                   "(prix réels, notes de carte) à chaque mise en veille ou mise à jour. "
                   "**Téléchargez une sauvegarde** après chaque saisie, et restaurez-la au besoin. "
                   "Pour un enregistrement permanent, ajoutez le secret `DJILAND_DB_URL` "
                   "(guide PERSISTANCE.md).", icon=":material/cloud_off:")
    else:
        note("Gardez une copie de vos données : utile pour les transférer vers la version en "
             "ligne ou les archiver.")
    b1, b2 = st.columns(2)
    b1.download_button("Sauvegarder mes prix réels (CSV)", data=pr.export_csv(),
                       file_name="djiland_prix_reels.csv", mime="text/csv",
                       disabled=not len(obs), width="stretch", icon=":material/download:")
    b2.download_button("Sauvegarder mes notes de carte (CSV)",
                       data=notes_bk.export_notes_csv(), file_name="djiland_notes_carte.csv",
                       mime="text/csv", disabled=notes_bk.load_notes().empty, width="stretch",
                       icon=":material/download:")
    note("Restaurer les prix réels : utilisez l'onglet « Import en masse » avec votre fichier de "
         "sauvegarde.")
    up_notes = st.file_uploader("Restaurer des notes de carte (fichier de sauvegarde CSV)",
                                type=["csv"], key="restore_notes")
    if up_notes is not None and not st.session_state.get(f"notes_ok_{up_notes.file_id}"):
        try:
            n_notes = notes_bk.import_notes_csv(pd.read_csv(up_notes))
            st.session_state[f"notes_ok_{up_notes.file_id}"] = True
            st.success(f"{n_notes} note(s) restaurée(s) — visibles sur la carte.",
                       icon=":material/check_circle:")
            st.cache_data.clear()
        except Exception as exc:
            st.error(f"Restauration impossible : {exc}")

section("Couverture par zone")
if len(rz):
    st.dataframe(rz, width="stretch", hide_index=True, column_config={
        "commune": "Zone", "n_obs": "Observations",
        "prix_m2_median": st.column_config.NumberColumn("Médiane F/m²", format="localized"),
        "prix_m2_min": st.column_config.NumberColumn("Min F/m²", format="localized"),
        "prix_m2_max": st.column_config.NumberColumn("Max F/m²", format="localized")})
else:
    st.info("Aucune donnée réelle pour l'instant. Saisissez vos premières transactions : c'est "
            "le début de votre avantage exclusif.", icon=":material/database:")

if len(obs):
    section("Dernières observations")
    st.dataframe(obs.tail(20)[::-1], width="stretch", hide_index=True)
