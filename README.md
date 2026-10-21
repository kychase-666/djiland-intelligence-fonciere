# 🛰️ Ivoire Land Intelligence — Djiland SARL

**Système de veille foncière data-driven pour la Côte d'Ivoire.**
Croise imagerie satellite open-source, données terrain, marché immobilier scrapé
et modèle prédictif pour détecter les zones où le prix va bondir **avant** tout
le monde.

> 💡 100 % gratuit / open-source. Aucune carte bancaire, aucune API payante.
> Le système démarre immédiatement avec des **données synthétiques réalistes**
> et bascule sur les vraies sources en changeant une seule variable (`DEMO_MODE`).

---

## 🚀 Démarrage rapide (2 minutes)

### Option A — Local (Python)

```bash
cd ivoire_land_intelligence
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # config par défaut = mode démo

python main.py                # génère données + calcule indices + entraîne le modèle
streamlit run dashboard/app.py   # dashboard sur http://localhost:8501
```

### Option B — Docker (stack complète)

```bash
cp .env.example .env
docker compose up --build
```

| Service    | URL                     | Description                    |
|------------|-------------------------|--------------------------------|
| Dashboard  | http://localhost:8501   | Streamlit (4 onglets)          |
| API        | http://localhost:8000/docs | FastAPI (rapports, alertes) |
| PGAdmin    | http://localhost:5050   | Admin PostGIS (admin@djiland.ci / djiland) |
| PostGIS    | localhost:5432          | Base de données historisée     |

---

## 🆕 Nouveautés v2.0 (20/10/2026)

- **🎯 Chasseur d'opportunités** : budget + critères (surface, zones, lotissement
  approuvé, sans litige, sans nuisance, vue lagune, rendement minimum) → terrains
  classés par score d'opportunité, carte numérotée, export CSV, rapport PDF en 1 clic.
  Même verdict que le PDF (`src/analysis/opportunites.py` = source unique).
- **Prix réels → recalage automatique** : dès 3 observations réelles dans une zone,
  les estimations de cette zone sont recalées sur vos prix.
- **Enregistrement permanent en ligne** des prix réels et des notes de carte dans
  une base PostgreSQL gratuite (Neon) via le secret `DJILAND_DB_URL` — guide
  [PERSISTANCE.md](PERSISTANCE.md). Sans ce secret : fichiers locaux.
- **Sauvegarde / restauration** des prix réels et des notes de carte (CSV).
- **Correctifs** : fond de carte CARTO (devenu payant, « API KEY REQUIRED ») remplacé
  par Esri Light Gray gratuit ; carte qui ne remplissait que 60 % de son cadre
  (minuscule sur téléphone) ; carte des résultats cadrée « monde entier » dans un
  onglet caché ; import CSV qui se ré-exécutait à chaque clic (doublons).
- **Pérennité** : API Streamlit modernisées (`st.iframe`, `width="stretch"`),
  versions des dépendances figées sur les versions testées (Streamlit ≤ 1.66,
  pandas ≤ 3.0) pour que la version en ligne ne casse pas à la prochaine mise à jour.

---

## 🧭 Ce que fait le système (les 6 phases)

| Phase | Rôle | Fichiers clés |
|-------|------|---------------|
| **1. Structure** | Projet modulaire | `config.py` |
| **2. Ingestion** | Satellite + OSM + scraping + terrain | `src/ingestion/` |
| **3. Traitement** | NDVI, pentes, détection de changement, Heat Index | `src/processing/`, `src/analysis/speculation.py` |
| **4. Prédiction** | XGBoost + SHAP : prix à 6 mois | `src/analysis/model.py` |
| **5. Visualisation** | Dashboard + rapports PDF | `dashboard/app.py`, `src/reports/pdf.py` |
| **6. Flywheel** | Planification hebdo + versioning | `src/scheduler.py` |

### Le "Speculation Heat Index" (avantage concurrentiel)
Score 0-100 combinant : proximité d'arrêtés de lotissement récents (<500 m) +
baisse du NDVI (déforestation/terrassement) + détection radar de chantiers +
hausse locale des prix scrapés. Voir `src/analysis/speculation.py`.

---

## 🛰️ Sources de données (toutes gratuites)

| Donnée | Source gratuite | Module |
|--------|-----------------|--------|
| Sentinel-2 (optique, NDVI) | Element84 Earth Search (STAC, sans clé) | `ingestion/satellite.py` |
| Sentinel-1 (radar, chantiers) | Microsoft Planetary Computer | `ingestion/satellite.py` |
| Landsat 8/9 | Earth Search | `ingestion/satellite.py` |
| MNT / pentes / inondation | Copernicus DEM 30m (Planetary Computer) | `processing/terrain.py` |
| Voiries, POIs, limites | OpenStreetMap via `osmnx`/Overpass | `ingestion/osm.py` |
| Prix marché | Scraping respectueux (Jumia Deals CI...) | `ingestion/scraping.py` |
| Ground truth | Relevés GPS des équipes | table `releves_terrain` |

**Pourquoi pas SentinelHub ?** Son offre gratuite est plafonnée et demande une
carte bancaire. Les catalogues STAC (Earth Search + Planetary Computer) donnent
les **mêmes données Copernicus** sans aucun coût ni quota bloquant.

---

## ➕ Ajouter une nouvelle source de données

1. **Ingestion** — créez `src/ingestion/ma_source.py` renvoyant un `DataFrame`
   ou `GeoDataFrame` normalisé.
2. **Stockage** — ajoutez au besoin une table dans `src/db/models.py`.
3. **Pipeline** — appelez votre fonction dans `run_real_pipeline()` de `main.py`.
4. **Analyse** — intégrez la nouvelle feature dans `FEATURES`
   (`src/analysis/model.py`) et/ou dans le Heat Index (`speculation.py`).

---

## ⚖️ Note légale sur le scraping
- Seules des **données publiques agrégées** sont collectées (prix, surface,
  quartier) — jamais de données personnelles.
- `robots.txt` respecté + rate limiting intégré.
- **Facebook Marketplace est désactivé** (interdit par ses CGU). Voir l'en-tête
  de `src/ingestion/scraping.py`. Vérifiez toujours les CGU de chaque site.

---

## 🗂️ Structure du projet
```
ivoire_land_intelligence/
├── config.py                 # configuration centrale (AOI, CRS, sources)
├── main.py                   # pipeline complet
├── docker-compose.yml        # PostGIS + PGAdmin + API + Dashboard
├── requirements.txt
├── data/{raw,processed,synthetic}
├── models/                   # modèles ML sérialisés
├── src/
│   ├── ingestion/            # satellite, osm, scraping, synthetic
│   ├── processing/           # indices, terrain, tiling
│   ├── analysis/             # accessibility, speculation, model
│   ├── db/                   # models PostGIS + session
│   ├── api/                  # FastAPI
│   ├── reports/              # export PDF
│   └── scheduler.py          # flywheel hebdomadaire
└── dashboard/app.py          # Streamlit (carte, tendances, alertes, PDF)
```

---
*Conventions : calculs métriques en UTM 30N (EPSG:32630), affichage en WGS84
(EPSG:4326). Docstrings en français. Code modulaire.*
