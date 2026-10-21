"""
Djiland · Land Intelligence — point d'entrée du dashboard (multi-pages).

Organisation en rubriques (navigation latérale) :
  Pilotage · Marché · Investissement · Conformité & terrain · Données & livrables.
Chaque page est un fichier de `dashboard/views/` ; le socle commun (données,
composants, charte) est dans `dashboard/core.py`.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import streamlit as st

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import APP_UPDATED, APP_VERSION, DATA_BUILT  # noqa: E402
from dashboard.core import (  # noqa: E402
    ASSETS,
    EN_LIGNE,
    gate,
    inject_css,
    mot_de_passe_requis,
    pied_de_page,
)

st.set_page_config(page_title="Djiland · Land Intelligence", page_icon=":material/landscape:",
                   layout="wide", initial_sidebar_state="auto")
inject_css()
st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "icon.svg"))
gate()

V = "views/"
pages = {
    "Pilotage": [
        st.Page(V + "accueil.py", title="Vue d'ensemble", icon=":material/space_dashboard:",
                default=True),
        st.Page(V + "carte.py", title="Carte interactive", icon=":material/map:"),
        st.Page(V + "alertes.py", title="Centre d'alertes", icon=":material/notifications_active:"),
    ],
    "Marché": [
        st.Page(V + "zones.py", title="Analyse par zone", icon=":material/location_city:"),
        st.Page(V + "tendances.py", title="Tendances des prix", icon=":material/trending_up:"),
    ],
    "Investissement": [
        st.Page(V + "opportunites.py", title="Chasseur d'opportunités",
                icon=":material/travel_explore:"),
        st.Page(V + "calculateur.py", title="Évaluation d'un terrain", icon=":material/calculate:"),
        st.Page(V + "bilan.py", title="Bilan promoteur", icon=":material/account_balance:"),
        st.Page(V + "comparateur.py", title="Comparateur de terrains",
                icon=":material/compare_arrows:"),
    ],
    "Conformité & terrain": [
        st.Page(V + "juridique.py", title="Sécurité juridique", icon=":material/gavel:"),
        st.Page(V + "annotations.py", title="Annotations terrain",
                icon=":material/edit_location_alt:"),
    ],
    "Données & livrables": [
        st.Page(V + "prix_reels.py", title="Prix réels", icon=":material/sell:"),
        st.Page(V + "rapports.py", title="Rapports PDF", icon=":material/picture_as_pdf:"),
    ],
}
page = st.navigation(pages, position="sidebar", expanded=True)

with st.sidebar:
    fr = lambda iso: f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"  # noqa: E731
    st.markdown(
        '<div class="dj-side"><b>Périmètre</b> · Grand Abidjan, corridor côtier, '
        "Yamoussoukro, Adzopé, Abengourou<br>"
        f"<b>Version</b> {APP_VERSION} · {fr(APP_UPDATED)}<br>"
        f"<b>Couches OSM</b> · {fr(DATA_BUILT)}"
        + ("<br><b>Hébergement</b> · Streamlit Cloud" if EN_LIGNE else "<br><b>Mode</b> · local")
        + "</div>", unsafe_allow_html=True)
    if mot_de_passe_requis() and st.session_state.get("auth_ok"):
        if st.button("Se déconnecter", icon=":material/logout:", width="stretch"):
            st.session_state.pop("auth_ok", None)
            st.rerun()

page.run()
pied_de_page()
