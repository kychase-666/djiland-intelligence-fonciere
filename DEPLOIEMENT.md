# 🚀 Déploiement permanent — Djiland (lien fixe, 24/7, Mac éteignable)

Ce guide met votre dashboard en ligne **gratuitement et de façon permanente** sur
**Streamlit Community Cloud**. Une fois fait, le lien ne change plus et votre Mac
peut être éteint.

> Tout le code est **déjà préparé et committé**. Il ne reste que 3 étapes côté vous
> (elles demandent VOTRE connexion — c'est pourquoi elles ne peuvent pas être
> automatisées).

---

## Étape 1 — Créer un compte GitHub (gratuit, 2 min)
1. Allez sur **https://github.com** → **Sign up**.
2. Créez un compte (email + mot de passe). Notez-les.

## Étape 2 — Mettre le projet sur GitHub
Le plus simple, sans rien installer :
1. Sur GitHub, cliquez **+** (en haut à droite) → **New repository**.
2. Nom : `djiland-intelligence-fonciere` · cochez **Private** · **Create repository**.
3. GitHub affiche une page « …or push an existing repository ». Copiez l'URL du dépôt
   (ex. `https://github.com/VOTRE-NOM/djiland-intelligence-fonciere.git`).
4. Dans le **Terminal**, collez (en remplaçant l'URL par la vôtre) :

```bash
cd "/Users/axelkyliandouarou/Desktop/djihiland sarl data !/ivoire_land_intelligence"
git remote add origin https://github.com/VOTRE-NOM/djiland-intelligence-fonciere.git
git branch -M main
git push -u origin main
```

GitHub vous demandera de vous connecter (une fenêtre s'ouvre) — acceptez.

## Étape 3 — Déployer sur Streamlit Cloud
1. Allez sur **https://share.streamlit.io** → **Sign in with GitHub** (autorisez).
2. Cliquez **Create app** → **Deploy a public app from GitHub**.
3. Renseignez :
   - **Repository** : `VOTRE-NOM/djiland-intelligence-fonciere`
   - **Branch** : `main`
   - **Main file path** : `dashboard/app.py`
4. Cliquez **Advanced settings** → **Secrets**, et collez :
   ```
   DJILAND_PASSWORD = "VOTRE-MOT-DE-PASSE"
   ```
   (changez le mot de passe si vous voulez.)
5. **Deploy**. Attendez 2–4 min. Vous obtenez un **lien fixe** du type
   `https://djiland-xxxx.streamlit.app` — à envoyer à votre papa. ✅

---

## Bon à savoir (honnête)
- **Lien fixe & permanent** : plus besoin que le Mac soit allumé.
- **Gratuit** (offre Community de Streamlit).
- ⚠️ **Saisies de prix/notes = temporaires en ligne** : le cloud gratuit efface les
  fichiers à chaque redémarrage de l'app. Pour un enregistrement **permanent et
  multi-utilisateur**, il faudra brancher une petite base de données (étape future).
  Pour consulter/démontrer, tout fonctionne parfaitement.
- **Mettre à jour** : après une modif, refaites `git push` — Streamlit redéploie tout seul.
