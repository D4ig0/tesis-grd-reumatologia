# =============================================================================
# 11_shap.py — ETAPA: explicabilidad (SHAP) sobre el mejor modelo por enfermedad
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Qué hace: por enfermedad, elige el mejor modelo (por PR-AUC en test), carga sus
# pesos (10) y las features (08), y calcula SHAP sobre una muestra de test. Guarda
# los valores SHAP. Es opcional y va aparte porque es lo más lento.
#
# Artefacto: resultados_modelado/shap/shap_<enfermedad>_<modelo>.npy
#
# USO:  python 11_shap.py --todas [--skip-existing] [--shap-n 2000]
#       python 11_shap.py --enfermedad gota
# =============================================================================
from __future__ import annotations

import argparse
import json
import time

import joblib
import numpy as np

import _comun_alt as C


def shap_una(enf, shap_n):
    if not C.HAY_SHAP:
        print("  shap no instalado (pip install shap) -> se omite")
        return False
    # mejor modelo por PR-AUC en test (entre las métricas disponibles de esa enfermedad)
    metr = list(C.DIR_METR.glob(f"{enf}__*.json"))
    if not metr:
        print(f"  [{enf}] sin métricas -> corre 10_entrenar_evaluar")
        return False
    mejores = []
    for f in metr:
        d = json.loads(f.read_text(encoding="utf-8"))
        mejores.append((d.get("PR_AUC", 0.0), d["modelo"]))
    _, modelo = max(mejores)

    mart = C.DIR_MOD / f"{enf}__{modelo}.joblib"
    fart = C.DIR_FEAT / f"{enf}.joblib"
    if not (mart.exists() and fart.exists()):
        print(f"  [{enf}] faltan artefactos de modelo/features -> se salta")
        return False
    M = joblib.load(mart)
    D = joblib.load(fart)
    import shap

    X, es_tr, nombres = D["X"], D["es_tr"], M["features"]
    Xte = X[~es_tr]
    muestra = Xte[:shap_n].toarray()
    modelo_repr = M["modelos"][0]
    if isinstance(modelo_repr, bytes):
        import pickle

        modelo_repr = pickle.loads(modelo_repr)

    try:
        sv = shap.Explainer(modelo_repr, feature_names=nombres)(muestra)
        np.save(C.DIR_SHAP / f"shap_{enf}_{modelo}.npy", sv.values)
        print(f"  [{enf}/{modelo}] SHAP OK (n={muestra.shape[0]})")
        return True
    except Exception as e:
        print(f"  [{enf}/{modelo}] SHAP omitido ({e})")
        return False


def main():
    ap = argparse.ArgumentParser(
        description="ETAPA SHAP (mejor modelo por enfermedad)."
    )
    ap.add_argument("--enfermedad")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--shap-n", type=int, default=2000, dest="shap_n")
    ap.add_argument("--skip-existing", action="store_true", dest="skip_existing")
    args = ap.parse_args()

    enfermedades = (
        [args.enfermedad]
        if args.enfermedad
        else C.enfermedades_todas() if args.todas else None
    )
    if not enfermedades:
        raise SystemExit(
            f"Indica --enfermedad <nombre> o --todas. Opciones: {C.enfermedades_todas()}"
        )

    t0 = time.time()
    for enf in enfermedades:
        if args.skip_existing and list(C.DIR_SHAP.glob(f"shap_{enf}_*.npy")):
            print(f"  [{enf}] SHAP ya existe -> se salta")
            continue
        shap_una(enf, args.shap_n)
    print(f"Listo SHAP. ({time.time()-t0:.1f}s) -> {C.DIR_SHAP}")


if __name__ == "__main__":
    main()
