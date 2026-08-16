# =============================================================================
# ablacion_artrosis.py — Análisis de ablación de procedimientos definitorios (M4/B1)
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# QUÉ HACE (y por qué): el modelo de artrosis alcanza un PR-AUC casi perfecto en
# parte porque entre sus atributos de mayor peso están la artroplastia de rodilla
# y cadera (proc_8151, proc_8154) y el implante articular (Z96.6), que son el
# TRATAMIENTO de la artrosis, no la enfermedad. Esto introduce una circularidad
# (fuga por indicación de tratamiento). La ablación cuantifica ese efecto:
# reentrena el modelo SIN esos códigos y mide cuánto cae el PR-AUC.
#
# Reentrena con ponderación de clases (scale_pos_weight), como la corrida canónica,
# usando los hiperparámetros ya ajustados. Evalúa sobre el conjunto de prueba.
#
# Salida: imprime PR-AUC (IC 95% bootstrap) con y sin los códigos ablados, y su caída.
#
# USO:  python ablacion_artrosis.py
#       python ablacion_artrosis.py --enfermedad artrosis_osteoartritis \
#              --excluir proc_8151,proc_8154,proc_0077,proc_0074,Z966
# =============================================================================
from __future__ import annotations

import argparse
import json

import _comun_alt as C
import joblib
import numpy as np
from sklearn.metrics import average_precision_score
from xgboost import XGBClassifier

DEF_EXCLUIR = "proc_8151,proc_8154,proc_0077,proc_0074,Z966"  # artroplastia rodilla/cadera + implante


def pr_auc_ic(y, p, n_boot=500, seed=C.SEED):
    ap = average_precision_score(y, p)
    r = np.random.default_rng(seed)
    vals = []
    idx = np.arange(len(y))
    for _ in range(n_boot):
        s = r.integers(0, len(y), len(y))
        if y[s].sum() == 0:  # evita muestras sin positivos
            continue
        vals.append(average_precision_score(y[s], p[s]))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return ap, lo, hi


def entrena_evalua(Xtr, ytr, Xte, yte, params):
    spw = float((ytr == 0).sum()) / max(1, int((ytr == 1).sum()))
    m = XGBClassifier(
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
    m.fit(Xtr, ytr)
    p = m.predict_proba(Xte)[:, 1]
    return pr_auc_ic(np.asarray(yte), p)


def main():
    ap = argparse.ArgumentParser(description="Ablación de procedimientos definitorios.")
    ap.add_argument("--enfermedad", default="artrosis_osteoartritis")
    ap.add_argument(
        "--excluir",
        default=DEF_EXCLUIR,
        help="lista separada por comas de nombres de atributo a ablar",
    )
    args = ap.parse_args()
    enf = args.enfermedad
    excluir = [c.strip() for c in args.excluir.split(",") if c.strip()]

    D = joblib.load(C.DIR_FEAT / f"{enf}.joblib")
    X, y, es_tr, nombres = (
        D["X"],
        np.asarray(D["y"]),
        np.asarray(D["es_tr"]),
        list(D["nombres"]),
    )
    tun = C.DIR_TUN / f"{enf}__xgboost.json"
    params = (
        json.loads(tun.read_text(encoding="utf-8")).get("best_params", {})
        if tun.exists()
        else {}
    )

    Xtr, ytr = X[es_tr].toarray(), y[es_tr]
    Xte, yte = X[~es_tr].toarray(), y[~es_tr]

    # índices de columnas a ablar
    faltan = [c for c in excluir if c not in nombres]
    idx_abl = [nombres.index(c) for c in excluir if c in nombres]
    keep = [j for j in range(len(nombres)) if j not in set(idx_abl)]

    print(
        f"[{enf}] atributos totales: {len(nombres)} | a ablar presentes: "
        f"{[nombres[j] for j in idx_abl]}"
    )
    if faltan:
        print(f"  (no encontrados, se ignoran: {faltan})")

    ap_full = entrena_evalua(Xtr, ytr, Xte, yte, params)
    ap_abl = entrena_evalua(Xtr[:, keep], ytr, Xte[:, keep], yte, params)

    print("\nResultado de la ablación (PR-AUC en test, IC 95% bootstrap):")
    print(
        f"  Con todos los atributos ......... {ap_full[0]:.3f}  [{ap_full[1]:.3f}; {ap_full[2]:.3f}]"
    )
    print(
        f"  Sin los códigos de tratamiento .. {ap_abl[0]:.3f}  [{ap_abl[1]:.3f}; {ap_abl[2]:.3f}]"
    )
    print(f"  Caída absoluta de PR-AUC ........ {ap_full[0]-ap_abl[0]:.3f}")


if __name__ == "__main__":
    main()
