"""Annotations terrain — dessiner sur la carte et y attacher des notes persistantes."""
from __future__ import annotations

import streamlit as st
from streamlit_folium import st_folium

from dashboard.core import MSG_NON_ENREGISTRE, alerte_base, badge, page_header, section
from src import persistance
from src.analysis import notes as notes_mod
from src.analysis.ga_map import build_annotation_map

page_header("Annotations terrain",
            "Dessinez un point, une ligne ou une zone sur l'image satellite, puis attachez-y une "
            "note (opportunité, risque, visite…). Les notes apparaissent aussi sur la carte "
            "principale.", rubrique="Conformité & terrain")


def _rafraichir() -> None:
    st.cache_data.clear()
    st.session_state["map_nonce"] = st.session_state.get("map_nonce", 0) + 1
    st.rerun()


left, right = st.columns([3, 1.2], gap="large")
with left:
    out = st_folium(build_annotation_map(), height=600, use_container_width=True,
                    key="annot_map", returned_objects=["last_active_drawing"])
with right:
    draw = out.get("last_active_drawing") if out else None
    section("Nouvelle note")
    if draw:
        with st.form("note_form", clear_on_submit=True, border=True):
            cat = st.selectbox("Catégorie", list(notes_mod.CATEGORIE_COULEUR))
            auteur = st.text_input("Auteur", value="Djiland")
            texte = st.text_area("Note", placeholder="Ex. : terrain viabilisé, prix négociable…")
            if st.form_submit_button("Enregistrer la note", type="primary",
                                     icon=":material/save:", width="stretch"):
                try:
                    notes_mod.save_note(draw, texte, cat, auteur)
                except persistance.BaseIndisponible:
                    st.error(MSG_NON_ENREGISTRE)
                else:
                    _rafraichir()
    else:
        st.info("Dessinez d'abord une forme avec les outils en haut à gauche de la carte.",
                icon=":material/draw:")

    existing = notes_mod.load_notes()
    alerte_base()
    section("Notes enregistrées", f"{len(existing)}")
    for i, r in existing.iterrows():
        with st.container(border=True):
            st.markdown(f"{badge(r['categorie'], 'neutral')}  \n{r['note'] or '_(sans texte)_'}",
                        unsafe_allow_html=True)
            c1, c2 = st.columns([2, 1], vertical_alignment="center")
            c1.caption(f"{r['auteur']} · {r['date']}")
            if c2.button("Supprimer", key=f"del{i}", icon=":material/delete:"):
                try:
                    notes_mod.delete_note(i)
                except persistance.BaseIndisponible:
                    st.error(MSG_NON_ENREGISTRE)
                else:
                    _rafraichir()
