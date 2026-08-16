# =============================================================================
# 09_tuning.py — ETAPA: búsqueda de hiperparámetros (por enfermedad y modelo)
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Qué hace: lee el artefacto de features (08) y, sobre una muestra BALANCEADA de
# TRAIN, corre RandomizedSearchCV con CV por paciente (StratifiedGroupKFold),
# métrica PR-AUC. Guarda los mejores hiperparámetros + PR-AUC/AUC por fold (para
# IC y Wilcoxon) + el umbral elegido en validación (nunca en test).
#
# Artefacto: resultados_modelado/tuning/<enfermedad>__<modelo>.json
#
# USO:  python 09_tuning.py --todas --modelo todos [--skip-existing] [--rapido]
#       python 09_tuning.py --enfermedad gota --modelo xgboost
# =============================================================================
from __future__ import annotations

import argparse
import json
import time

import _comun_alt as C
import joblib
import numpy as np


def tuning_uno(enf, modelo, args):
    art = C.DIR_FEAT / f"{enf}.joblib"
    if not art.exists():
        print(f"  [{enf}] sin features (corre 08_features primero) -> se salta")
        return False
    D = joblib.load(art)
    X, y, es_tr, grupos = D["X"], D["y"], D["es_tr"], D["grupos"]
    Xtr, ytr, gtr = X[es_tr], y[es_tr], grupos[es_tr]

    # muestra balanceada de train para la búsqueda (desbalance resuelto, rápido)
    Xb, yb, gb = C.balancear_train(Xtr, ytr, gtr, args.cap, args.ratio)
    spw = max(1.0, (len(yb) - yb.sum()) / max(1, yb.sum()))
    esp = C.espacios(spw)
    if modelo not in esp:
        print(f"  [{enf}/{modelo}] modelo no disponible -> se salta")
        return False
    est, params = esp[modelo]

    be, bp, bs = C.tunear(est, params, Xb, yb, gb, args.n_iter, args.cv)
    pr_folds, roc_folds = C.cv_por_fold(be, Xb, yb, gb, args.cv)
    thr = C.umbral_por_validacion(be, Xb, yb, gb, args.cv)

    salida = {
        "enfermedad": enf,
        "modelo": modelo,
        "best_params": {
            k: (v.item() if hasattr(v, "item") else v) for k, v in bp.items()
        },
        "best_score_cv_PR_AUC": bs,
        "cv_PR_AUC_folds": [float(x) for x in pr_folds],
        "cv_AUC_ROC_folds": [float(x) for x in roc_folds],
        "cv_PR_AUC_media": float(np.mean(pr_folds)),
        "cv_PR_AUC_sd": float(np.std(pr_folds)),
        "umbral": thr,
        "n_iter": args.n_iter,
        "cv": args.cv,
        "cap": args.cap,
        "ratio": args.ratio,
    }
    (C.DIR_TUN / f"{enf}__{modelo}.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"  [{enf}/{modelo}] CV PR-AUC={np.mean(pr_folds):.3f}±{np.std(pr_folds):.3f} (thr={thr:.2f})"
    )
    return True


def main():
    ap = argparse.ArgumentParser(
        description="ETAPA tuning de hiperparámetros (por enfermedad y modelo)."
    )
    ap.add_argument("--enfermedad")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--modelo", default="todos", choices=["todos"] + C.MODELOS_VALIDOS)
    ap.add_argument("--n-iter", type=int, default=15, dest="n_iter")
    ap.add_argument("--cv", type=int, default=3)
    ap.add_argument("--cap", type=int, default=15000)
    ap.add_argument("--ratio", type=int, default=3)
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--skip-existing", action="store_true", dest="skip_existing")
    args = ap.parse_args()
    if args.rapido:
        args.n_iter, args.cv, args.cap = 6, 3, 6000

    enfermedades = (
        [args.enfermedad]
        if args.enfermedad
        else C.enfermedades_todas() if args.todas else None
    )
    if not enfermedades:
        raise SystemExit(
            f"Indica --enfermedad <nombre> o --todas. Opciones: {C.enfermedades_todas()}"
        )
    modelos = C.MODELOS_VALIDOS if args.modelo == "todos" else [args.modelo]

    t0 = time.time()
    for enf in enfermedades:
        for mod in modelos:
            dst = C.DIR_TUN / f"{enf}__{mod}.json"
            if args.skip_existing and dst.exists():
                print(f"  [{enf}/{mod}] ya existe -> se salta")
                continue
            tuning_uno(enf, mod, args)
    print(f"Listo tuning. ({time.time()-t0:.1f}s) -> {C.DIR_TUN}")


if __name__ == "__main__":
    main()
