"""
Modèle prédictif du « Prix Futur au m² à 6 mois » (XGBoost + explicabilité SHAP).

Construit une table de features par quartier à partir des prix historisés et des
signaux satellite/spéculatifs, entraîne un régresseur, sauvegarde le modèle et
produit des prédictions expliquées (top features SHAP) prêtes à historiser.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from loguru import logger

from config import MODELS_DIR

MODEL_PATH = MODELS_DIR / "xgb_prix_6m.joblib"
FEATURES = [
    "prix_m2_actuel",
    "prix_trend_6m",
    "nb_chantiers_sar",
    "ndvi_delta_moyen",
    "accessibilite_min",
    "n_arretes_proches",
    "volume_annonces",
]


def build_feature_table(prix: pd.DataFrame, indicateurs: pd.DataFrame,
                        heat: pd.DataFrame) -> pd.DataFrame:
    """Agrège les données au niveau QUARTIER pour l'entraînement.

    La cible `prix_m2_futur_6m` est reconstruite en décalant l'historique :
    pour chaque quartier, on relie l'état à t-6mois au prix observé aujourd'hui.
    """
    prix = prix.copy()
    prix["date_annonce"] = pd.to_datetime(prix["date_annonce"])
    ref = prix["date_annonce"].max()

    lignes = []
    for quartier, g in prix.groupby("quartier"):
        g = g.sort_values("date_annonce")
        prix_actuel = g[g["date_annonce"] >= ref - pd.Timedelta(days=30)]["prix_m2_fcfa"].mean()
        prix_passe = g[(g["date_annonce"] >= ref - pd.Timedelta(days=210)) &
                       (g["date_annonce"] <= ref - pd.Timedelta(days=150))]["prix_m2_fcfa"].mean()
        if np.isnan(prix_actuel) or np.isnan(prix_passe):
            continue

        ind_q = indicateurs[indicateurs["quartier"] == quartier]
        heat_q = heat[heat["quartier"] == quartier]

        # Tendance 6 mois (relative) reconstruite depuis l'historique
        recent = g[g["date_annonce"] >= ref - pd.Timedelta(days=180)]
        x = (recent["date_annonce"] - recent["date_annonce"].min()).dt.days.values
        trend = float(np.polyfit(x, recent["prix_m2_fcfa"].values, 1)[0]) if len(recent) > 3 else 0.0

        lignes.append({
            "quartier": quartier,
            "prix_m2_actuel": prix_passe,               # état à t-6mois = features
            "prix_trend_6m": trend / (prix_passe + 1e-6),
            "nb_chantiers_sar": ind_q["changement_sar"].mean(),
            "ndvi_delta_moyen": ind_q["ndvi_delta_6m"].mean(),
            "accessibilite_min": ind_q["accessibilite_min"].mean(),
            "n_arretes_proches": heat_q["n_arretes"].mean() if "n_arretes" in heat_q else 0.0,
            "volume_annonces": len(g),
            "prix_m2_futur_6m": prix_actuel,            # cible = prix observé aujourd'hui
        })
    df = pd.DataFrame(lignes).fillna(0.0)
    logger.info(f"[ML] Table de features : {len(df)} quartiers.")
    return df


def _build_regressor():
    """Retourne le meilleur régresseur d'arbres disponible.

    Priorité à XGBoost ; repli automatique sur GradientBoosting (scikit-learn)
    si XGBoost ne peut pas se charger (ex. runtime OpenMP/libomp absente sur
    macOS). Les deux sont compatibles avec l'explicabilité SHAP TreeExplainer.
    """
    try:
        from xgboost import XGBRegressor

        XGBRegressor()  # force le chargement de la lib native (déclenche l'erreur ici)
        return XGBRegressor(
            n_estimators=300, max_depth=3, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9, random_state=42)
    except Exception as exc:  # ImportError, XGBoostError (libomp), etc.
        from sklearn.ensemble import GradientBoostingRegressor

        logger.warning(f"[ML] XGBoost indisponible ({type(exc).__name__}) — "
                       f"repli sur GradientBoostingRegressor (scikit-learn).")
        return GradientBoostingRegressor(
            n_estimators=300, max_depth=3, learning_rate=0.05,
            subsample=0.9, random_state=42)


def train(df: pd.DataFrame):
    """Entraîne le régresseur (XGBoost ou repli sklearn) et sauvegarde le modèle."""
    from sklearn.model_selection import train_test_split

    X, y = df[FEATURES], df["prix_m2_futur_6m"]
    model = _build_regressor()
    if len(df) >= 6:
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=1)
        model.fit(Xtr, ytr)
        score = model.score(Xte, yte)
        logger.info(f"[ML] R² test = {score:.3f}")
    else:
        model.fit(X, y)
        logger.warning("[ML] Peu d'échantillons : entraînement sans hold-out.")
    joblib.dump({"model": model, "features": FEATURES}, MODEL_PATH)
    logger.info(f"[ML] Modèle sauvegardé -> {MODEL_PATH}")
    return model


def predict_with_shap(df: pd.DataFrame, model=None) -> pd.DataFrame:
    """Prédit le prix à 6 mois et joint les 3 principaux facteurs SHAP.

    Returns:
        DataFrame [quartier, prix_m2_actuel, prix_m2_predit_6m, hausse_pct,
                   top_features(JSON)].
    """
    import shap

    if model is None:
        bundle = joblib.load(MODEL_PATH)
        model, feats = bundle["model"], bundle["features"]
    else:
        feats = FEATURES

    X = df[feats]
    preds = model.predict(X)
    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(X)

    out = []
    for i, (_, row) in enumerate(df.iterrows()):
        contribs = sorted(
            zip(feats, shap_vals[i]), key=lambda kv: abs(kv[1]), reverse=True)[:3]
        actuel = row["prix_m2_actuel"]
        pred = float(preds[i])
        out.append({
            "quartier": row["quartier"],
            "prix_m2_actuel": round(actuel, 0),
            "prix_m2_predit_6m": round(pred, 0),
            "hausse_pct": round((pred / actuel - 1) * 100, 1) if actuel else 0.0,
            "top_features": json.dumps(
                [{"feature": f, "impact": round(float(v), 1)} for f, v in contribs],
                ensure_ascii=False),
        })
    res = pd.DataFrame(out).sort_values("hausse_pct", ascending=False)
    logger.info(f"[ML] {len(res)} prédictions générées (avec SHAP).")
    return res
