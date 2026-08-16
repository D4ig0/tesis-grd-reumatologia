# =============================================================================
# 13_shap_resumen.py — ETAPA: interpretación legible de SHAP (por enfermedad)
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Qué hace: toma los valores SHAP crudos (11_shap: shap_<enf>_<modelo>.npy), los une
# con los NOMBRES de las variables (features del 08) y produce, por enfermedad, un
# ranking legible: qué variable pesa más (importancia = media de |SHAP|) y en qué
# DIRECCIÓN influye sobre el target (hacia / en contra), usando la correlación entre
# el valor de la variable y su SHAP. Esto responde OE2 (atributos relevantes) y el
# criterio (c) (interpretabilidad).
#
# Artefactos: resultados_modelado/shap/shap_top_<enfermedad>.csv (por enfermedad)
#             resultados_modelado/shap_resumen_top.csv           (consolidado)
#
# USO:  python 13_shap_resumen.py --todas [--skip-existing] [--top-n 25]
#       python 13_shap_resumen.py --enfermedad gota
# =============================================================================
from __future__ import annotations

import argparse
import time

import joblib
import numpy as np
import pandas as pd

import _comun_alt as C


def resumen_una(enf, top_n):
    npys = list(C.DIR_SHAP.glob(f"shap_{enf}_*.npy"))
    if not npys:
        print(f"  [{enf}] sin SHAP (.npy) -> corre 11_shap")
        return None
    fnpy = npys[0]
    modelo = fnpy.stem.replace(f"shap_{enf}_", "")
    fart = C.DIR_FEAT / f"{enf}.joblib"
    if not fart.exists():
        print(f"  [{enf}] sin features -> corre 08_features")
        return None

    D = joblib.load(fart)
    nombres = list(D["nombres"])
    sv = np.load(fnpy, allow_pickle=True)
    if sv.ndim == 3:  # algunos modelos: (n, features, clases) -> clase positiva
        sv = sv[:, :, -1]

    # alinear dimensiones por seguridad
    m = min(sv.shape[1], len(nombres))
    sv, nombres = sv[:, :m], nombres[:m]

    # Importancia = magnitud media |SHAP|. Dirección = SHAP MEDIO con signo (robusto en
    # binarias raras): si la contribución promedio es consistentemente + o -, empuja
    # hacia / en contra; si se cancela (|medio| pequeño vs magnitud), es "mixta/depende".
    importancia = np.abs(sv).mean(axis=0)
    shap_medio = sv.mean(axis=0)
    ratio = shap_medio / (importancia + 1e-12)  # -1..1: consistencia del signo

    df = pd.DataFrame(
        {
            "enfermedad": enf,
            "modelo": modelo,
            "feature": nombres,
            "importancia_shap": importancia,
            "shap_medio": shap_medio,
            "consistencia_signo": ratio,
        }
    )
    df["direccion"] = np.where(
        ratio > 0.2,
        "hacia (↑ prob.)",
        np.where(ratio < -0.2, "en contra (↓ prob.)", "mixta/depende"),
    )
    df = (
        df.sort_values("importancia_shap", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    df.to_csv(C.DIR_SHAP / f"shap_top_{enf}.csv", index=False)
    print(
        f"  [{enf}/{modelo}] top {len(df)} -> shap_top_{enf}.csv "
        f"(1ª: {df['feature'].iloc[0]} {df['direccion'].iloc[0]})"
    )
    return df


def main():
    ap = argparse.ArgumentParser(
        description="ETAPA resumen legible de SHAP por enfermedad."
    )
    ap.add_argument("--enfermedad")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--top-n", type=int, default=25, dest="top_n")
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
    todos = []
    for enf in enfermedades:
        if args.skip_existing and (C.DIR_SHAP / f"shap_top_{enf}.csv").exists():
            print(f"  [{enf}] ya existe -> se salta")
            todos.append(pd.read_csv(C.DIR_SHAP / f"shap_top_{enf}.csv"))
            continue
        r = resumen_una(enf, args.top_n)
        if r is not None:
            todos.append(r)
    if todos:
        pd.concat(todos, ignore_index=True).to_csv(
            C.DIR_OUT / "shap_resumen_top.csv", index=False
        )
        print(f"Consolidado -> {C.DIR_OUT / 'shap_resumen_top.csv'}")
    print(f"Listo SHAP resumen. ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
