"""
Construction de la carte interactive « ultra poussée » du Grand Abidjan.

Assemble une carte Folium riche à destination du dashboard :
  - 4 fonds de carte : Satellite (Esri), Relief/Terrain (Esri), Plan clair, OSM.
  - Choroplèthes par commune (prix au m², Speculation Heat) = « prix global par zone ».
  - Couches parcellaires précises au m² (prix, heat, NDVI, risque inondation).
  - POIs réels OSM regroupés par famille (éducation, santé, commerce, banque, transport).
  - Grandes voies, arrêtés/ZUP, relevés terrain, limites de communes.
  - Outils : mesure de surface au m², plein écran, mini-carte, coordonnées souris.
  - Panneau de LÉGENDE complet (15+ entrées) + échelle de couleurs des prix.

Toutes les couches sont des groupes activables/désactivables côté client via le
contrôleur de calques (aucun rechargement serveur nécessaire).
"""
from __future__ import annotations

import branca.colormap as cm
import folium
import geopandas as gpd
import numpy as np
import pandas as pd
from folium.plugins import (
    AntPath,
    Draw,
    FastMarkerCluster,
    Fullscreen,
    MeasureControl,
    MiniMap,
    MousePosition,
)

from config import ASSINIE_CENTER, GRAND_ABIDJAN_DIR, PLATEAU_CBD, VEILLE_RADIUS_KM
from src.analysis.notes import CATEGORIE_COULEUR, load_notes

# Familles de POIs -> (couleur, icône FontAwesome, activé par défaut).
# Défaut épuré : toutes les couches POI sont masquées au départ, l'utilisateur
# les active à la demande via le contrôleur de calques.
POI_STYLE = {
    "Éducation":       ("#2563eb", "graduation-cap", False),
    "Santé":           ("#dc2626", "plus-square", False),
    "Marché/Commerce": ("#ea580c", "shopping-cart", False),
    "Banque":          ("#16a34a", "university", False),
    "Transport":       ("#7c3aed", "bus", False),
    "Station-service": ("#92400e", "gas-pump", False),
    "Culte":           ("#64748b", "place-of-worship", False),
}


def _notes_layer(show: bool = True) -> folium.FeatureGroup:
    """Construit le calque des annotations utilisateur (dessins + notes)."""
    fg = folium.FeatureGroup(name="🖊️ Mes notes", show=show)
    notes = load_notes()
    for _, n in notes.iterrows():
        couleur = CATEGORIE_COULEUR.get(n["categorie"], "#7f7f7f")
        popup = folium.Popup(html=(
            f"<b>{n['categorie']}</b><br>{n['note']}<br>"
            f"<i>{n['auteur']} · {n['date']}</i>"), max_width=260)
        geom = n.geometry
        if geom.geom_type == "Point":
            folium.CircleMarker([geom.y, geom.x], radius=8, color="#111",
                                fill=True, fill_color=couleur, fill_opacity=0.9,
                                popup=popup).add_to(fg)
        else:
            folium.GeoJson(geom.__geo_interface__,
                           style_function=lambda x, c=couleur: {
                               "fillColor": c, "color": c, "weight": 2,
                               "fillOpacity": 0.35},
                           popup=popup).add_to(fg)
    return fg


def _load(name: str):
    """Charge une couche GeoParquet du Grand Abidjan (None si absente)."""
    path = GRAND_ABIDJAN_DIR / name
    return gpd.read_parquet(path) if path.exists() else None


def _circle_layer(parcelles, valeur_col, label, colormap, show=False):
    """Crée un FeatureGroup de cercles colorés par une métrique (précision m²)."""
    fg = folium.FeatureGroup(name=label, show=show)
    for _, p in parcelles.iterrows():
        v = p[valeur_col]
        # Champs avancés (présents après enrichissement)
        extra = ""
        if "rendement_locatif" in p:
            vue = " · 🌅 vue lagune" if p.get("vue_lagune") else ""
            malus = (f" · ⚠️ nuisance −{p['malus_nuisance']*100:.0f}%"
                     if p.get("malus_nuisance", 0) > 0.05 else "")
            extra = (f"<hr style='margin:3px 0'>"
                     f"💵 Rendement locatif : <b>{p['rendement_locatif']}%</b>{vue}{malus}<br>"
                     f"Convoitise : {p.get('convoitise', '—')}/100"
                     f"{' · 🏗️ chantier' if p.get('chantier_detecte') else ''}"
                     f"{' · 🔵 rattrapage' if p.get('rattrapage') else ''}")
        if "lotissement_statut" in p:
            icone = {"Approuvé": "✅", "En sursis": "⚠️", "Annulé": "❌"}.get(
                p["lotissement_statut"], "")
            extra += (f"<hr style='margin:3px 0'>"
                      f"⚖️ <b>Lotissement {icone} {p['lotissement_statut']}</b> "
                      f"(<i>démo</i>)<br>"
                      f"Score juridique : <b>{p['score_juridique']}/100</b><br>"
                      f"{p['idufci_demo']}"
                      f"{' · ⚖️ LITIGE' if p.get('litige_parcelle') else ''}")
        popup = folium.Popup(html=(
            f"<b>{p['code_parcelle']}</b> — {p['commune']}<br>"
            f"<b>Prix : {p['prix_m2_fcfa']:,.0f} FCFA/m²</b><br>"
            f"Surface : {p['surface_m2']:,.0f} m² &nbsp;|&nbsp; "
            f"Total : {p['prix_total_fcfa']:,.0f} FCFA<br>"
            f"Heat spéculatif : {p['speculation_heat']}/100<br>"
            f"NDVI : {p['ndvi_moyen']} &nbsp;|&nbsp; Pente : {p['pente_moyenne_deg']}°<br>"
            f"Risque inondation : {p['risque_inondation']}<br>"
            f"Accès Plateau : {p['accessibilite_min']} min &nbsp;|&nbsp; "
            f"Distance : {p['dist_plateau_km']} km<br>"
            f"Viabilisé : {'oui' if p['viabilise'] else 'non'}{extra}"),
            max_width=300)
        folium.CircleMarker(
            location=[p.geometry.y, p.geometry.x], radius=4,
            color=None, fill=True, fill_color=colormap(v), fill_opacity=0.85,
            popup=popup,
        ).add_to(fg)
    return fg


def _advanced_layers(m, parcelles, communes) -> None:
    """Ajoute les couches « Situation Room » : NIMBY, vue lagune, rendement,
    chantiers satellite, vallées de rattrapage, vides juridiques, flèches
    d'expansion urbaine. Toutes masquées par défaut (vue épurée)."""
    nuisances = _load("nuisances.parquet")
    lagune = _load("lagune.parquet")
    releves = _load("releves.parquet")

    # --- Nuisances invisibles (NIMBY) : auréoles fusionnées par type --------
    if nuisances is not None and not nuisances.empty:
        fg = folium.FeatureGroup(name="🏭 Nuisances (NIMBY)", show=False)
        nu = nuisances.to_crs(32630)
        nu["aura"] = nu.geometry.buffer(nu["rayon_m"])
        for typ, grp in nu.groupby("type_nuisance"):
            merged = grp.set_geometry("aura").geometry.union_all()
            aura = gpd.GeoSeries([merged], crs=32630).to_crs(4326).iloc[0]
            couleur = grp["couleur"].iloc[0]
            folium.GeoJson(aura.__geo_interface__, name=typ,
                           style_function=lambda x, c=couleur: {
                               "fillColor": c, "color": c, "weight": 0, "fillOpacity": 0.20},
                           tooltip=f"Nuisance : {typ}").add_to(fg)
        for _, n in nuisances.sample(n=min(150, len(nuisances)), random_state=1).iterrows():
            ctr = n.geometry.centroid
            folium.CircleMarker([ctr.y, ctr.x], radius=3, color=n["couleur"], fill=True,
                                fill_opacity=0.9,
                                popup=f"{n['type_nuisance']} — impact {n['rayon_m']} m").add_to(fg)
        fg.add_to(m)

    # --- Vue lagune : plan d'eau + parcelles dorées -------------------------
    if lagune is not None and not lagune.empty and "vue_lagune" in parcelles.columns:
        fg = folium.FeatureGroup(name="🌅 Vue lagune (or)", show=False)
        folium.GeoJson(lagune.to_json(), style_function=lambda x: {
            "fillColor": "#3b82f6", "color": "#1d4ed8", "weight": 1, "fillOpacity": 0.25}).add_to(fg)
        for _, p in parcelles[parcelles["vue_lagune"]].iterrows():
            folium.CircleMarker([p.geometry.y, p.geometry.x], radius=5, color="#b8860b",
                                fill=True, fill_color="#f1c40f", fill_opacity=0.95,
                                popup=(f"🌅 <b>Vue lagune</b> — {p['code_parcelle']}<br>"
                                       f"{p['prix_m2_fcfa']:,.0f} FCFA/m² (+ prime vue)")).add_to(fg)
        fg.add_to(m)

    # --- Investisseur augmenté : rendement locatif --------------------------
    if "rendement_locatif" in parcelles.columns:
        cmap_r = cm.LinearColormap(["#d73027", "#ffffbf", "#1a9850"], vmin=3, vmax=11,
                                   caption="Rendement locatif brut estimé (%)")
        _circle_layer(parcelles, "rendement_locatif", "💰 Rendement locatif", cmap_r,
                      show=False).add_to(m)

    # --- Chantiers détectés (SAR) + vallées de rattrapage -------------------
    if "chantier_detecte" in parcelles.columns:
        fg = folium.FeatureGroup(name="🏗️ Chantiers détectés (satellite)", show=False)
        for _, p in parcelles[parcelles["chantier_detecte"]].iterrows():
            folium.Marker([p.geometry.y, p.geometry.x],
                          icon=folium.DivIcon(html='<div style="font-size:16px">🏗️</div>'),
                          popup=f"Chantier détecté (radar) — {p['code_parcelle']}").add_to(fg)
        fg.add_to(m)

        fg2 = folium.FeatureGroup(name="🔵 Vallées de rattrapage", show=False)
        for _, p in parcelles[parcelles["rattrapage"]].iterrows():
            folium.CircleMarker([p.geometry.y, p.geometry.x], radius=7, color="#0044ff",
                                weight=2, fill=True, fill_color="#00aaff", fill_opacity=0.85,
                                popup=(f"🔵 <b>Vallée de rattrapage</b> — {p['code_parcelle']}<br>"
                                       f"Parcelle froide (heat {p['speculation_heat']}) cernée de "
                                       f"chaud (voisinage {p['heat_voisinage']:.0f}) → signal d'achat")).add_to(fg2)
        fg2.add_to(m)

    # --- Vides juridiques : litiges fonciers (violet) -----------------------
    if releves is not None and "litige_foncier" in releves.columns:
        lit = releves[releves["litige_foncier"]]
        if not lit.empty:
            fg = folium.FeatureGroup(name="⚖️ Vides juridiques (litige)", show=False)
            for _, r in lit.iterrows():
                folium.RegularPolygonMarker(
                    [r.geometry.y, r.geometry.x], number_of_sides=4, radius=7, rotation=45,
                    color="#6b21a8", fill_color="#a855f7", fill_opacity=0.8,
                    popup=f"⚖️ Litige foncier — {r['commune']} ({r['agent']})").add_to(fg)
            fg.add_to(m)

    # --- Flèches d'expansion urbaine (vecteurs animés) ----------------------
    if communes is not None:
        fg = folium.FeatureGroup(name="➡️ Flèches d'expansion", show=False)
        for _, c in communes.iterrows():
            heat = c["heat_moyen"]
            if pd.isna(heat) or heat < 45:
                continue
            cen = c.geometry.centroid
            v = np.array([cen.y - PLATEAU_CBD[1], cen.x - PLATEAU_CBD[0]])
            norm = np.linalg.norm(v)
            if norm == 0:
                continue
            u = v / norm
            length = 0.015 + 0.05 * (heat / 100)
            end = [cen.y + u[0] * length, cen.x + u[1] * length]
            AntPath([[cen.y, cen.x], end], color="#e11d48", weight=2 + heat / 25,
                    delay=800, dash_array=[10, 20],
                    tooltip=f"Poussée urbaine {c['commune']} (heat {heat:.0f})").add_to(fg)
        fg.add_to(m)

    # --- Transport structurant : réseau existant + projets futurs -----------
    transport = _load("transport.parquet")
    if transport is not None and not transport.empty:
        fg_exist = folium.FeatureGroup(name="🛣️ Grands axes (existant)", show=False)
        fg_futur = folium.FeatureGroup(name="🏗️ Projets futurs (métro/train/route)", show=True)
        for _, t in transport.iterrows():
            coords = [[y, x] for x, y in t.geometry.coords]
            libelle = f"{t['nom']} — {t['mode']} ({t['statut'].replace('_', ' ')})"
            if t["statut"] == "existant":
                folium.PolyLine(coords, color=t["couleur"], weight=4, opacity=0.85,
                                tooltip=libelle).add_to(fg_exist)
            else:
                AntPath(coords, color=t["couleur"], weight=5, delay=600,
                        dash_array=[12, 24], tooltip=libelle).add_to(fg_futur)
        fg_exist.add_to(m)
        fg_futur.add_to(m)

    # --- Statut de lotissement (sécurité juridique) — DÉMO ------------------
    if "lotissement_statut" in parcelles.columns:
        couleurs = {"Approuvé": "#16a34a", "En sursis": "#f59e0b", "Annulé": "#dc2626"}
        fg = folium.FeatureGroup(name="⚖️ Statut lotissement (démo)", show=False)
        for _, p in parcelles.iterrows():
            st_ = p["lotissement_statut"]
            folium.CircleMarker(
                [p.geometry.y, p.geometry.x], radius=4, color=None, fill=True,
                fill_color=couleurs.get(st_, "#777"), fill_opacity=0.85,
                popup=(f"⚖️ <b>{p['lotissement_nom']}</b><br>"
                       f"Statut : <b>{st_}</b> (démo)<br>"
                       f"Score juridique : {p['score_juridique']}/100<br>"
                       f"{p['idufci_demo']}<br>"
                       f"<i>À vérifier officiellement (MCLU / DGI).</i>")).add_to(fg)
        fg.add_to(m)


def build_map(metric_parcelle: str = "prix_m2_fcfa") -> folium.Map:
    """Construit la carte complète du Grand Abidjan avec toutes les couches.

    Args:
        metric_parcelle: colonne parcellaire mise en avant (non bloquant : les
            4 couches parcellaires sont de toute façon disponibles).

    Returns:
        Objet folium.Map prêt à être rendu par st_folium.
    """
    communes = _load("communes.parquet")
    parcelles = _load("parcelles.parquet")
    pois = _load("pois.parquet")
    roads = _load("roads.parquet")
    arretes = _load("arretes.parquet")
    releves = _load("releves.parquet")

    centre = [5.345, -4.02]
    m = folium.Map(location=centre, zoom_start=11, tiles=None, control_scale=True,
                   prefer_canvas=True)

    # --- 1. Fonds de carte (base layers) ------------------------------------
    folium.TileLayer("CartoDB positron", name="🗺️ Plan clair", control=True).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="🛰️ Satellite", control=True, show=True).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Terrain", name="⛰️ Relief / Terrain", control=True).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Shaded Relief", name="🏔️ Ombrage relief", control=True).add_to(m)

    # --- 2. Choroplèthes par commune (prix global par zone) -----------------
    if communes is not None:
        cmap_prix = cm.LinearColormap(
            ["#2c7bb6", "#ffffbf", "#d7191c"],
            vmin=float(communes["prix_m2_moyen"].min()),
            vmax=float(communes["prix_m2_moyen"].max()),
            caption="Prix moyen FCFA/m² par commune")
        cmap_heat = cm.LinearColormap(
            ["#1a9850", "#ffffbf", "#d73027"], vmin=0, vmax=100,
            caption="Speculation Heat par commune (0-100)")

        fg_prix = folium.FeatureGroup(name="💰 Prix/m² par commune", show=True)
        fg_heat = folium.FeatureGroup(name="🔥 Heat par commune", show=False)
        for _, c in communes.iterrows():
            tip = (f"<b>{c['commune']}</b> ({c['type_zone']})<br>"
                   f"Prix moyen : {c['prix_m2_moyen']:,.0f} FCFA/m²<br>"
                   f"Fourchette : {c['prix_m2_min']:,.0f} – {c['prix_m2_max']:,.0f}<br>"
                   f"Heat moyen : {c['heat_moyen']}/100<br>"
                   f"Accès Plateau : {c['access_moyen']} min<br>"
                   f"Parcelles suivies : {int(c['n_parcelles'])}")
            folium.GeoJson(
                c.geometry.__geo_interface__,
                style_function=lambda x, col=cmap_prix(c["prix_m2_moyen"]): {
                    "fillColor": col, "color": "#333", "weight": 1, "fillOpacity": 0.55},
                tooltip=tip).add_to(fg_prix)
            folium.GeoJson(
                c.geometry.__geo_interface__,
                style_function=lambda x, col=cmap_heat(c["heat_moyen"]): {
                    "fillColor": col, "color": "#333", "weight": 1, "fillOpacity": 0.55},
                tooltip=tip).add_to(fg_heat)
        fg_prix.add_to(m)
        fg_heat.add_to(m)
        cmap_prix.add_to(m)

        # Limites + étiquettes des communes
        fg_lim = folium.FeatureGroup(name="🧭 Limites communes", show=True)
        for _, c in communes.iterrows():
            folium.GeoJson(c.geometry.__geo_interface__, style_function=lambda x: {
                "fillColor": "#00000000", "color": "#000", "weight": 1.4, "fillOpacity": 0}
            ).add_to(fg_lim)
            folium.map.Marker(
                [c.geometry.centroid.y, c.geometry.centroid.x],
                icon=folium.DivIcon(html=(
                    f'<div style="font-size:11px;font-weight:700;color:#111;'
                    f'text-shadow:0 0 3px #fff;">{c["commune"]}</div>'))).add_to(fg_lim)
        fg_lim.add_to(m)

    # --- 3. Couche parcellaire sélectionnée (précision m², optimisée) -------
    # Pour la performance, une seule couche parcellaire est construite : celle
    # de la métrique choisie (le sélecteur du dashboard reconstruit la carte).
    if parcelles is not None:
        specs = {
            "prix_m2_fcfa": ("💵 Parcelles · Prix/m²",
                             cm.LinearColormap(["#2c7bb6", "#ffffbf", "#d7191c"],
                                               vmin=float(parcelles["prix_m2_fcfa"].quantile(0.05)),
                                               vmax=float(parcelles["prix_m2_fcfa"].quantile(0.95)))),
            "speculation_heat": ("🔥 Parcelles · Speculation Heat",
                                 cm.LinearColormap(["#1a9850", "#ffffbf", "#d73027"], vmin=0, vmax=100)),
            "ndvi_moyen": ("🌳 Parcelles · Végétation NDVI",
                           cm.LinearColormap(["#a6611a", "#f5f5f5", "#1a9641"], vmin=0, vmax=0.8)),
            "risque_inondation": ("🌊 Parcelles · Risque inondation",
                                  cm.LinearColormap(["#f7fbff", "#2171b5", "#08306b"], vmin=0, vmax=1)),
        }
        label, cmap_sel = specs.get(metric_parcelle, specs["prix_m2_fcfa"])
        _circle_layer(parcelles, metric_parcelle, label, cmap_sel, show=True).add_to(m)

    # --- 4. POIs réels OSM par famille (FastMarkerCluster = léger) -----------
    # FastMarkerCluster passe des tableaux de coordonnées bruts : rendu fluide
    # même avec des milliers de points (bien plus léger que MarkerCluster).
    if pois is not None:
        for famille, (couleur, icone, defaut) in POI_STYLE.items():
            sub = pois[pois["famille"] == famille]
            if sub.empty:
                continue
            fg = folium.FeatureGroup(name=f"📍 {famille} ({len(sub)})", show=defaut)
            coords = [[g.y, g.x] for g in sub.geometry]
            FastMarkerCluster(coords).add_to(fg)
            fg.add_to(m)

    # --- 5. Grandes voies réelles -------------------------------------------
    if roads is not None and not roads.empty:
        majeures = roads[roads["classe"].isin(["motorway", "trunk", "primary"])].copy()
        majeures["geometry"] = majeures.geometry.simplify(0.0004)
        fg_roads = folium.FeatureGroup(name="🛣️ Grandes voies", show=False)
        couleur_voie = {"motorway": "#e31a1c", "trunk": "#fb9a29", "primary": "#4575b4"}
        for _, r in majeures.iterrows():
            folium.GeoJson(r.geometry.__geo_interface__,
                           style_function=lambda x, c=couleur_voie.get(r["classe"], "#666"): {
                               "color": c, "weight": 2}).add_to(fg_roads)
        fg_roads.add_to(m)

    # --- 6. Arrêtés / ZUP (signal spéculatif) -------------------------------
    if arretes is not None and not arretes.empty:
        fg_arr = folium.FeatureGroup(name="📜 Arrêtés / ZUP", show=False)
        for _, a in arretes.iterrows():
            folium.Marker(
                [a.geometry.y, a.geometry.x],
                icon=folium.Icon(color="orange", icon="file-text", prefix="fa"),
                popup=f"{a['type_acte'].upper()} — {a['commune']}<br>{a['reference']}"
                      f"<br>{a['date_publication']:%d/%m/%Y}").add_to(fg_arr)
        fg_arr.add_to(m)

    # --- 7. Relevés terrain (ground truth) ----------------------------------
    if releves is not None and not releves.empty:
        fg_rel = folium.FeatureGroup(name="🧑‍🌾 Relevés terrain", show=False)
        for _, r in releves.iterrows():
            litige = " ⚠️ LITIGE" if r["litige_foncier"] else ""
            folium.CircleMarker(
                [r.geometry.y, r.geometry.x], radius=5, color="#111",
                fill=True, fill_color="#ffd400", fill_opacity=0.9,
                popup=(f"Relevé {r['agent']} — {r['commune']}<br>"
                       f"Sol : {r['qualite_sol']} | Vue : {r['vue']}<br>"
                       f"Nuisance sonore : {r['nuisance_sonore']}/5{litige}")).add_to(fg_rel)
        fg_rel.add_to(m)

    # --- 7ter. Couches avancées « Situation Room » --------------------------
    _advanced_layers(m, parcelles, communes)

    # --- 7bis. Zone de veille : 100 km autour d'Assinie ---------------------
    fg_veille = folium.FeatureGroup(name="🎯 Veille Assinie (100 km)", show=True)
    folium.Circle(
        location=[ASSINIE_CENTER[1], ASSINIE_CENTER[0]], radius=VEILLE_RADIUS_KM * 1000,
        color="#e11d48", weight=2, dash_array="8", fill=True, fill_color="#e11d48",
        fill_opacity=0.05,
        popup=f"Zone de veille spéculative — {VEILLE_RADIUS_KM} km autour d'Assinie").add_to(fg_veille)
    folium.Marker(
        [ASSINIE_CENTER[1], ASSINIE_CENTER[0]],
        icon=folium.Icon(color="red", icon="star", prefix="fa"),
        popup="Assinie-Mafia — centre de la zone de veille").add_to(fg_veille)
    fg_veille.add_to(m)

    # --- 8. Annotations existantes ------------------------------------------
    _notes_layer(show=True).add_to(m)

    # Cadrage automatique sur l'ensemble des zones (District + corridor côtier)
    if communes is not None:
        minx, miny, maxx, maxy = communes.total_bounds
        m.fit_bounds([[miny, minx], [maxy, maxx]])

    # --- 9. Outils & légende ------------------------------------------------
    MeasureControl(primary_length_unit="meters", primary_area_unit="sqmeters",
                   position="topleft").add_to(m)   # mesure précise au m²
    Draw(export=True, position="topleft",           # dessiner + exporter en GeoJSON
         draw_options={"poly": True, "polygon": True, "rectangle": True,
                       "circle": False, "marker": True, "polyline": True},
         edit_options={"edit": True}).add_to(m)
    Fullscreen(position="topleft").add_to(m)
    MiniMap(toggle_display=True, position="bottomleft").add_to(m)
    MousePosition(prefix="Coord :", num_digits=5, position="bottomright").add_to(m)
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    # Légende affichée HORS carte (dans la page Streamlit) — voir legend_body().
    return m


def build_map_lite(metric_parcelle: str = "prix_m2_fcfa", n_sample: int = 130) -> folium.Map:
    """Carte ALLÉGÉE optimisée MOBILE (rapide, tactile, sans bug de zoom).

    Optimisations téléphone : rendu `canvas` (prefer_canvas), vue centrée sur
    Abidjan (pas de dézoom régional qui rendait la carte illisible/lente sur
    petit écran), fonds réduits (satellite + plan), échantillon de parcelles
    réduit, légende déplaçable. Aucune couche lourde (POIs, voirie, avancées).
    """
    communes = _load("communes.parquet")
    parcelles = _load("parcelles.parquet")
    transport = _load("transport.parquet")

    # prefer_canvas : rendu des points sur canvas → beaucoup plus fluide sur mobile.
    # scrollWheelZoom désactivé : le défilement de la PAGE ne zoome plus la carte
    # par accident (zoom via les boutons +/− ou le pincement à deux doigts).
    m = folium.Map(location=[5.345, -4.02], zoom_start=11, tiles=None,
                   control_scale=True, prefer_canvas=True, scrollWheelZoom=False)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri", name="🛰️ Satellite", show=True).add_to(m)
    folium.TileLayer("CartoDB positron", name="🗺️ Plan clair").add_to(m)

    if communes is not None:
        cmap = cm.LinearColormap(
            ["#2c7bb6", "#ffffbf", "#d7191c"],
            vmin=float(communes["prix_m2_moyen"].min()),
            vmax=float(communes["prix_m2_moyen"].max()),
            caption="Prix FCFA/m²")
        cmap.width = 220  # barre de couleur compacte (ne déborde pas sur mobile)
        fg = folium.FeatureGroup(name="💰 Prix/m² par zone", show=True)
        for _, c in communes.iterrows():
            folium.GeoJson(
                c.geometry.__geo_interface__,
                style_function=lambda x, col=cmap(c["prix_m2_moyen"]): {
                    "fillColor": col, "color": "#333", "weight": 1, "fillOpacity": 0.5},
                tooltip=(f"<b>{c['commune']}</b><br>{c['prix_m2_moyen']:,.0f} FCFA/m²<br>"
                         f"Heat {c['heat_moyen']}/100")).add_to(fg)
            folium.map.Marker(
                [c.geometry.centroid.y, c.geometry.centroid.x],
                icon=folium.DivIcon(html=(
                    f'<div style="font-size:10px;font-weight:700;color:#111;'
                    f'text-shadow:0 0 3px #fff">{c["commune"]}</div>'))).add_to(fg)
        fg.add_to(m)
        cmap.add_to(m)

    if parcelles is not None:
        samp = parcelles.sample(n=min(n_sample, len(parcelles)), random_state=1)
        cmap_p = cm.LinearColormap(
            ["#2c7bb6", "#ffffbf", "#d7191c"],
            vmin=float(parcelles["prix_m2_fcfa"].quantile(0.05)),
            vmax=float(parcelles["prix_m2_fcfa"].quantile(0.95)))
        _circle_layer(samp, metric_parcelle, "📍 Parcelles (échantillon)", cmap_p,
                      show=True).add_to(m)

    if transport is not None and not transport.empty:
        fg = folium.FeatureGroup(name="🏗️ Projets futurs", show=True)
        for _, t in transport[transport["statut"] != "existant"].iterrows():
            AntPath([[y, x] for x, y in t.geometry.coords], color=t["couleur"],
                    weight=5, delay=600, dash_array=[12, 24],
                    tooltip=f"{t['nom']} ({t['statut'].replace('_', ' ')})").add_to(fg)
        fg.add_to(m)

    fg_v = folium.FeatureGroup(name="🎯 Veille Assinie 100 km", show=False)
    folium.Circle([ASSINIE_CENTER[1], ASSINIE_CENTER[0]], radius=VEILLE_RADIUS_KM * 1000,
                  color="#e11d48", weight=2, dash_array="8", fill=True,
                  fill_color="#e11d48", fill_opacity=0.05).add_to(fg_v)
    fg_v.add_to(m)

    _notes_layer(show=True).add_to(m)

    # Vue centrée sur Abidjan (zoom 11), SANS fit_bounds régional : évite le
    # dézoom illisible/lent sur petit écran. Les zones éloignées restent pannables.

    MeasureControl(primary_area_unit="sqmeters", position="topleft").add_to(m)
    Fullscreen(position="topleft").add_to(m)
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    # Légende/guide affichés HORS carte (dans la page) — voir legend_body(False).
    return m


def build_annotation_map() -> folium.Map:
    """Carte allégée dédiée au DESSIN et à l'ajout de NOTES persistantes.

    Fond satellite + limites de communes + annotations existantes + outil de
    dessin. Pensée pour st_folium (capture des géométries dessinées côté serveur).
    """
    m = folium.Map(location=[5.345, -4.02], zoom_start=11, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="🛰️ Satellite", show=True).add_to(m)
    folium.TileLayer("CartoDB positron", name="🗺️ Plan clair").add_to(m)

    communes = _load("communes.parquet")
    if communes is not None:
        for _, c in communes.iterrows():
            folium.GeoJson(c.geometry.__geo_interface__, style_function=lambda x: {
                "fillColor": "#00000000", "color": "#fbbf24", "weight": 1.5, "fillOpacity": 0},
                tooltip=c["commune"]).add_to(m)

    _notes_layer(show=True).add_to(m)
    Draw(export=True, position="topleft",
         draw_options={"polygon": True, "rectangle": True, "marker": True,
                       "polyline": True, "circle": False, "circlemarker": False},
         edit_options={"edit": True, "remove": True}).add_to(m)
    MeasureControl(primary_length_unit="meters", primary_area_unit="sqmeters",
                   position="topleft").add_to(m)
    Fullscreen(position="topleft").add_to(m)
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    return m


_PANEL_TMPL = """
<div id="__ID__" style="position:fixed;__POS__z-index:9999;background:rgba(255,255,255,.96);
  border:1px solid #bbb;border-radius:10px;font-size:11px;max-width:__MAXW__px;
  box-shadow:0 3px 12px rgba(0,0,0,.30);overflow:hidden;">
  <div id="__ID__-h" style="cursor:move;background:#1F6F5C;color:#fff;padding:6px 10px;
    font-weight:700;font-size:11px;display:flex;justify-content:space-between;align-items:center;
    user-select:none;-webkit-user-select:none;touch-action:none;">
    <span>__TITLE__ &nbsp;<span style="opacity:.7;font-weight:400">⠿ glisser</span></span>
    <span id="__ID__-t" style="cursor:pointer;padding:0 5px;font-size:13px;">&#9662;</span>
  </div>
  <div id="__ID__-b" style="padding:8px 11px;max-height:40vh;overflow-y:auto;">__INNER__</div>
</div>
<script>
(function(){
  var el=document.getElementById("__ID__"),h=document.getElementById("__ID__-h"),
      b=document.getElementById("__ID__-b"),t=document.getElementById("__ID__-t");
  if(!el||!h){return;}
  var dr=false,ox=0,oy=0;
  function s(x,y){dr=true;var r=el.getBoundingClientRect();ox=x-r.left;oy=y-r.top;
    el.style.bottom="auto";el.style.right="auto";el.style.left=r.left+"px";el.style.top=r.top+"px";}
  function mv(x,y){if(dr){el.style.left=(x-ox)+"px";el.style.top=(y-oy)+"px";}}
  function en(){dr=false;}
  h.addEventListener("mousedown",function(e){if(e.target===t)return;s(e.clientX,e.clientY);e.preventDefault();});
  document.addEventListener("mousemove",function(e){mv(e.clientX,e.clientY);});
  document.addEventListener("mouseup",en);
  h.addEventListener("touchstart",function(e){if(e.target===t)return;var p=e.touches[0];s(p.clientX,p.clientY);},{passive:true});
  document.addEventListener("touchmove",function(e){if(dr){var p=e.touches[0];mv(p.clientX,p.clientY);e.preventDefault();}},{passive:false});
  document.addEventListener("touchend",en);
  t.addEventListener("click",function(e){e.stopPropagation();
    if(b.style.display==="none"){b.style.display="block";t.innerHTML="&#9662;";}
    else{b.style.display="none";t.innerHTML="&#9656;";}});
})();
</script>
"""


def _draggable_panel(inner: str, title: str, pid: str,
                     pos: str = "bottom:24px;left:12px;", maxw: int = 250) -> str:
    """Enveloppe un contenu HTML dans un panneau DÉPLAÇABLE et repliable.

    Compatible souris et tactile : l'utilisateur peut glisser la légende où il
    veut et la replier pour dégager la vue (utile sur téléphone).
    """
    return (_PANEL_TMPL.replace("__ID__", pid).replace("__TITLE__", title)
            .replace("__POS__", pos).replace("__MAXW__", str(maxw))
            .replace("__INNER__", inner))


def legend_body(complet: bool = True) -> str:
    """Contenu HTML de la légende — destiné à être affiché HORS de la carte.

    Args:
        complet: True = toutes les couches (carte complète) ; False = version
            allégée (mobile) avec seulement les calques présents en mode lite.
    """
    base = (
        '<b>Prix</b> (bleu → jaune → rouge) : 💰 par commune · 💵 par parcelle<br>'
        '<b>Spéculation</b> (vert → rouge) : 🔥 Heat spéculatif<br>'
        '<b>Transport</b> : 🏗️ projets futurs animés '
        '(🟣 métro · 🟤 train · 🔵 autoroute · 🩷 pont)<br>'
        '🎯 Veille Assinie 100 km · 🖊️ Mes notes')
    if not complet:
        return base + ('<hr style="margin:6px 0"><i>Astuce : tapez une parcelle pour son '
                       'détail · bouton ☰ (haut-droite) pour les calques · règle = mesure m².</i>')
    return base + (
        '<hr style="margin:6px 0"><b>Environnement</b> : 🌳 NDVI (brun→vert) · '
        '🌊 Risque inondation (bleu foncé)<br>'
        '<b>Équipements réels (OSM)</b> : '
        '<span style="color:#2563eb">●</span> Éducation '
        '<span style="color:#dc2626">●</span> Santé '
        '<span style="color:#ea580c">●</span> Commerce '
        '<span style="color:#16a34a">●</span> Banque '
        '<span style="color:#7c3aed">●</span> Transport · 🛣️ Grandes voies · 🧭 Limites<br>'
        '<b>Situation Room</b> : 🏭 Nuisances (NIMBY) · 🌅 Vue lagune · 💰 Rendement locatif · '
        '🏗️ Chantiers · 🔵 Rattrapage · ⚖️ Vides juridiques · ➡️ Expansion<br>'
        '<b>Juridique</b> : ⚖️ Lotissement (🟢 approuvé · 🟠 sursis · 🔴 annulé)<br>'
        '<hr style="margin:6px 0"><i>Outils carte : règle = surface m² · ✏️ = dessiner · '
        '☰ (haut-droite) = activer/désactiver les calques.</i>')


def _legend_html() -> str:
    """(Compat) légende déplaçable en overlay — plus utilisée (légende hors carte)."""
    return _draggable_panel(legend_body(), "🗺️ Légende", "djleg", "bottom:24px;left:12px;", 250)
