# 🔒 Enregistrement PERMANENT des données saisies en ligne (gratuit)

**Le problème** : l'hébergement gratuit Streamlit Cloud efface son disque à chaque
mise en veille ou mise à jour. Vos **prix réels** et **notes de carte** saisis en
ligne disparaissaient donc.

**La solution** : brancher une petite **base de données gratuite** (PostgreSQL).
Le code est **déjà prêt** : il suffit de créer la base et de coller son adresse
dans les Secrets de Streamlit. Aucune carte bancaire.

| | **Neon** ✅ recommandé | Supabase |
|---|---|---|
| Prix | Gratuit (1 Go, largement assez) | Gratuit (500 Mo) |
| Mise en pause | Se rendort seule après 5 min d'inactivité et **se réveille toute seule** en ~1 s | **Mise en pause après 7 jours sans utilisation** : il faut aller la relancer à la main sur supabase.com |
| Création | 3 min, connexion avec GitHub | 5 min |

👉 **Prenez Neon** : rien à surveiller. (Le code marche aussi avec Supabase, voir
en bas.)

---

## Étape 1 — Créer la base Neon (3 min)
1. Allez sur **https://neon.com** → **Sign up** → **Continue with GitHub**
   (votre compte `kychase-666`). Autorisez.
2. Créez un projet :
   - **Project name** : `djiland`
   - **Postgres version** : laissez la valeur proposée
   - **Region** : choisissez **AWS US East (N. Virginia)** — c'est là que tourne
     Streamlit Cloud, donc l'app sera plus rapide.
   - **Create project**.
3. Sur la page du projet, cliquez **Connect** (ou « Connection string »).
4. Copiez l'adresse affichée. Elle ressemble à :
   ```
   postgresql://neondb_owner:XXXXXXXX@ep-xxxx-xxxx.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```
   ⚠️ Elle contient un **mot de passe** : ne l'envoyez à personne, ne la mettez
   dans aucun fichier du projet (le dépôt GitHub est **public**).

## Étape 2 — La coller dans les Secrets Streamlit (2 min)
1. Allez sur **https://share.streamlit.io** → votre app
   `djiland-intelligence-fonciere` → les **⋮** à droite → **Settings** → **Secrets**.
2. Vous y voyez déjà la ligne du mot de passe. **Ajoutez une ligne en dessous**
   (gardez bien les guillemets) :
   ```
   DJILAND_PASSWORD = "votre-mot-de-passe-actuel"
   DJILAND_DB_URL = "postgresql://neondb_owner:XXXXXXXX@ep-xxxx.us-east-1.aws.neon.tech/neondb?sslmode=require"
   ```
3. **Save changes**. L'app redémarre toute seule (~1 min).

## Étape 3 — Vérifier (1 min)
1. Ouvrez l'app → onglet **🏷️ Prix réels** → section « Sauvegarde ».
   Vous devez voir le bandeau vert **« 🔒 Enregistrement permanent activé »**.
2. Saisissez une transaction, et une note sur la carte (onglet ✏️ Annoter).
3. Dans share.streamlit.io : **⋮ → Reboot app** (équivalent d'une mise en veille).
4. Rouvrez l'app : la transaction et la note sont **toujours là**. ✅

Les tables se créent toutes seules au premier lancement, et les notes déjà
présentes dans le projet y sont recopiées automatiquement.

---

## Bon à savoir
- **Bandeau rouge « Base de données en ligne injoignable »** : la base ne répond
  pas (coupure réseau, adresse mal collée). Rien n'est perdu ; les saisies sont
  refusées avec un message tant que la base ne répond pas. Vérifiez la ligne
  `DJILAND_DB_URL` dans les Secrets (guillemets, pas d'espace).
- **Voir vos données brutes** : sur neon.com → votre projet → **Tables**.
- **Sauvegarde CSV** (onglet Prix réels) : toujours disponible, utile comme archive.
- **Sur votre Mac** : rien ne change (fichiers locaux). Pour que le Mac utilise la
  même base que la version en ligne, ajoutez la même ligne `DJILAND_DB_URL=...`
  (sans guillemets) dans un fichier `.env` à la racine du projet.
- **Changer de mot de passe de base** : sur Neon, « Reset password », puis
  recollez la nouvelle adresse dans les Secrets.

## Variante Supabase (si vous préférez)
1. **https://supabase.com** → Start your project → connexion GitHub → **New project**
   (région **East US (North Virginia)**, notez le mot de passe de base choisi).
2. Bouton **Connect** en haut → onglet **Connection string** → choisissez
   **Session pooler** (important : l'adresse « Direct connection » ne marche pas
   depuis Streamlit Cloud).
3. Remplacez `[YOUR-PASSWORD]` par votre mot de passe de base, puis collez
   l'adresse dans les Secrets exactement comme à l'étape 2 (`DJILAND_DB_URL = "..."`).
4. ⚠️ Si personne n'ouvre l'app pendant 7 jours, Supabase met la base en pause :
   allez sur supabase.com → votre projet → **Restore project**.
