# =============================================================================
# estabilidad_iteraciones.py — Estabilidad ENTRE ITERACIONES del mejor modelo (B8, criterio c)
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Complementa a estabilidad_atributos.py (que mide estabilidad ENTRE MODELOS).
# Aquí se mide la estabilidad ENTRE ITERACIONES: se reajusta el MEJOR modelo de
# cada enfermedad sobre k pliegues del conjunto de entrenamiento y se compara la
# lista de atributos relevantes entre pliegues. Es la lectura estándar de la
# estabilidad de importancias y responde a la parte "entre iteraciones" del
# criterio (c). Se espera que sea ALTA (mismo modelo, remuestras del mismo dato).
#
# Métricas por enfermedad:
#   · Jaccard medio de los top-20 entre todos los pares de pliegues.
#   · Spearman medio de las importancias entre todos los pares de pliegues.
# Umbral declarado a priori: estable si Jaccard medio >= 0,60 y Spearman medio >= 0,70.
#
# Salida: resultados_modelado/estabilidad_iteraciones.csv
# USO:  python estabilidad_iteraciones.py [--k 5] [--top 20]
# =============================================================================
from __future__ import annotations

import argparse
import itertools
import json

import _comun_alt as C
import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold


def mejor_modelo(enf):
    metr = list(C.DIR_METR.glob(f"{enf}__*.json"))
    if not metr:
        return None
    best = max(
        (
            json.loads(f.read_text(encoding="utf-8")).get("PR_AUC", 0.0),
            json.loads(f.read_text(encoding="utf-8"))["modelo"],
        )
        for f in metr
    )
    return best[1]


def construye(modelo, params, spw):
    if modelo == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=params.get("n_estimators", 400),
            max_depth=params.get("max_depth", 5),
            learning_rate=params.get("learning_rate", 0.05),
            subsample=params.get("subsample", 0.8),
            colsample_bytree=params.get("colsample_bytree", 0.7),
            scale_pos_weight=spw,
            eval_metric="aucpr",
            tree_method="hist",
            n_jobs=-1,
            random_state=C.SEED,
        )
    if modelo == "random_forest":
        return RandomForestClassifier(
            n_estimators=params.get("n_estimators", 300),
            max_depth=params.get("max_depth", None),
            max_features=params.get("max_features", "sqrt"),
            min_samples_leaf=params.get("min_samples_leaf", 1),
            class_weight="balanced",
            n_jobs=-1,
            random_state=C.SEED,
        )
    return LogisticRegression(
        C=params.get("C", 1.0),
        penalty=params.get("penalty", "l2"),
        solver="liblinear",
        class_weight="balanced",
        max_iter=2000,
    )


def importancia(m):
    if hasattr(m, "coef_"):
        return np.abs(np.ravel(m.coef_))
    return np.asarray(m.feature_importances_, dtype=float)


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else np.nan


def main():
    ap = argparse.ArgumentParser(
        description="Estabilidad entre iteraciones del mejor modelo (B8)."
    )
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    filas = []
    for enf in C.enfermedades_todas():
        mod = mejor_modelo(enf)
        if mod is None:
            continue
        D = joblib.load(C.DIR_FEAT / f"{enf}.joblib")
        X, y, es_tr, nom = (
            D["X"],
            np.asarray(D["y"]),
            np.asarray(D["es_tr"]),
            list(D["nombres"]),
        )
        Xtr, ytr = X[es_tr], y[es_tr]
        tun = C.DIR_TUN / f"{enf}__{mod}.json"
        params = (
            json.loads(tun.read_text(encoding="utf-8")).get("best_params", {})
            if tun.exists()
            else {}
        )

        skf = StratifiedKFold(n_splits=args.k, shuffle=True, random_state=C.SEED)
        tops, imps = [], []
        for tr_idx, _ in skf.split(np.zeros(Xtr.shape[0]), ytr):
            spw = float((ytr[tr_idx] == 0).sum()) / max(
                1, int((ytr[tr_idx] == 1).sum())
            )
            m = construye(mod, params, spw)
            m.fit(
                Xtr[tr_idx].toarray() if hasattr(Xtr, "toarray") else Xtr[tr_idx],
                ytr[tr_idx],
            )
            imp = importancia(m)
            n = min(len(nom), len(imp))
            imp = imp[:n]
            imps.append(imp)
            orden = np.argsort(-imp)[: args.top]
            tops.append([nom[j] for j in orden])

        pares = list(itertools.combinations(range(args.k), 2))
        j = np.nanmean([jaccard(tops[a], tops[b]) for a, b in pares])
        s = np.nanmean([spearmanr(imps[a], imps[b]).correlation for a, b in pares])
        estable = (j >= 0.60) and (s >= 0.70)
        filas.append(
            {
                "enfermedad": enf,
                "mejor_modelo": mod,
                "jaccard_iter": round(float(j), 2),
                "spearman_iter": round(float(s), 2),
                "estable": estable,
            }
        )
        print(f"{enf:30s} {mod:14s} J={j:.2f}  rho={s:.2f}  estable={estable}")

    out = pd.DataFrame(filas).sort_values("jaccard_iter", ascending=False)
    dest = C.DIR_OUT / "estabilidad_iteraciones.csv"
    out.to_csv(dest, index=False)
    print(f"\nGuardado: {dest}")


if __name__ == "__main__":
    main()
