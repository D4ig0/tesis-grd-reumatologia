# =============================================================================
# 10_entrenar_evaluar.py — ETAPA: entrenamiento final + evaluación en TEST
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Qué hace: lee features (08) + hiperparámetros (09), reconstruye el modelo con los
# mejores parámetros, entrena en TODO el train (adaptativo: simple o bootstrap para
# raras) y evalúa en TEST UNA sola vez (PR-AUC, AUC, IC, Brier, F1). Guarda el modelo
# (pesos) y las métricas.
#
# Artefactos: resultados_modelado/modelos/<enf>__<modelo>.joblib
#             resultados_modelado/metricas/<enf>__<modelo>.json
#
# USO:  python 10_entrenar_evaluar.py --todas --modelo todos [--skip-existing]
#       python 10_entrenar_evaluar.py --enfermedad gota --modelo xgboost
# =============================================================================
from __future__ import annotations

import argparse
import json
import time

import joblib
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

import _comun_alt as C


def entrenar_uno(enf, modelo, args):
    fart = C.DIR_FEAT / f"{enf}.joblib"
    tart = C.DIR_TUN / f"{enf}__{modelo}.json"
    if not fart.exists():
        print(f"  [{enf}] sin features -> corre 08_features")
        return False
    if not tart.exists():
        print(f"  [{enf}/{modelo}] sin tuning -> corre 09_tuning")
        return False

    D = joblib.load(fart)
    T = json.loads(tart.read_text(encoding="utf-8"))
    X, y, es_tr, grupos, nombres = D["X"], D["y"], D["es_tr"], D["grupos"], D["nombres"]
    Xtr, Xte = X[es_tr], X[~es_tr]
    ytr, yte = y[es_tr], y[~es_tr]
    gtr = grupos[es_tr]
    n_pos_tr = int(ytr.sum())

    # Reconstruir el estimador con los mejores hiperparámetros
    spw = max(1.0, (len(ytr) - ytr.sum()) / max(1, ytr.sum()))
    est_base, _ = C.espacios(spw)[modelo]
    est = est_base.set_params(**T["best_params"])
    if modelo == "xgboost":
        prevalencia = max(1e-5, float(ytr.sum()) / len(ytr))
        est.set_params(base_score=prevalencia)

    modelos, modo = C.entrenar_final(
        est,
        Xtr,
        ytr,
        gtr,
        n_pos_tr,
        args.umbral_estable,
        args.cap,
        args.ratio,
        args.k_boot,
    )
    thr = float(T.get("umbral", 0.5))
    p_te = C.proba_ensamble(modelos, Xte)

    m = C.evaluar(yte, p_te, thr)
    m.update(
        {
            "enfermedad": enf,
            "modelo": modelo,
            "umbral_elegido": thr,
            "modo_entrenamiento": modo,
            "PR_AUC_ic95": C.ic_bootstrap(yte, p_te, average_precision_score),
            "AUC_ROC_ic95": C.ic_bootstrap(yte, p_te, roc_auc_score),
            "brier": float(brier_score_loss(yte, p_te)),
            "cv_PR_AUC_media": T.get("cv_PR_AUC_media"),
            "cv_PR_AUC_sd": T.get("cv_PR_AUC_sd"),
            "cv_PR_AUC_folds": T.get("cv_PR_AUC_folds"),
        }
    )
    (C.DIR_METR / f"{enf}__{modelo}.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    joblib.dump(
        {
            "modelos": modelos,
            "features": nombres,
            "orden": D["orden"],
            "enfermedad": enf,
            "modelo": modelo,
            "modo": modo,
            "umbral": thr,
        },
        C.DIR_MOD / f"{enf}__{modelo}.joblib",
    )
    print(
        f"  [{enf}/{modelo}] TEST PR-AUC={m['PR_AUC']:.3f} AUC={m['AUC_ROC']:.3f} "
        f"F1={m['F1']:.3f} (thr={thr:.2f}) [{modo}]"
    )
    return True


def main():
    ap = argparse.ArgumentParser(
        description="ETAPA entrenamiento final + evaluación en test."
    )
    ap.add_argument("--enfermedad")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--modelo", default="todos", choices=["todos"] + C.MODELOS_VALIDOS)
    ap.add_argument("--cap", type=int, default=15000)
    ap.add_argument("--ratio", type=int, default=3)
    ap.add_argument("--umbral-estable", type=int, default=2000, dest="umbral_estable")
    ap.add_argument("--k-boot", type=int, default=100, dest="k_boot")
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--skip-existing", action="store_true", dest="skip_existing")
    args = ap.parse_args()
    if args.rapido:
        args.cap, args.k_boot = 6000, 30

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
            dst = C.DIR_METR / f"{enf}__{mod}.json"
            if args.skip_existing and dst.exists():
                print(f"  [{enf}/{mod}] ya existe -> se salta")
                continue
            entrenar_uno(enf, mod, args)
    print(f"Listo entrenamiento/evaluación. ({time.time()-t0:.1f}s) -> {C.DIR_METR}")


if __name__ == "__main__":
    main()
