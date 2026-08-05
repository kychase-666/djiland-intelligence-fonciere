-- Initialisation PostGIS pour Ivoire Land Intelligence
-- Exécuté automatiquement au premier démarrage du conteneur postgis.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Les tables métier sont créées par SQLAlchemy (src/db/models.py) au lancement
-- de `python main.py --init-db`. On ne crée ici que l'extension spatiale.
