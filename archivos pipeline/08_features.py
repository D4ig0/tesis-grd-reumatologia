# =============================================================================
# 08_features.py — ETAPA: construcción de features + selección chi² top-N (por enfermedad)
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Qué hace: por cada enfermedad, construye el bloque de features (seguras + alta
# cardinalidad como presencia binaria, excluyendo los códigos que DEFINEN la
# enfermedad = anti-fuga) y selecciona las TOP-N por chi² (SOLO train). Guarda un
# artefacto por enfermedad para que las etapas siguientes no recomputen nada.
#
# Artefacto: resultados_modelado/features/<enfermedad>.joblib
#   {X (csr, seguras+seleccionadas), y, es_tr, grupos, nombres, orden, enfermedad}
# + ranking chi²: resultados_modelado/features/ranking_chi2_<enfermedad>.csv
#
# USO:  python 08_features.py --todas [--skip-existing] [--top-n 100] [--piso 30]
#       python 08_features.py --enfermedad gota
# =============================================================================
from __future__ import annotations

import argparse
import time

import _comun_alt as C
import joblib
from scipy import sparse


def features_una(base, enf, top_n, piso, drop_sev):
    D = C.construir_features(base, enf, piso, drop_sev=drop_sev)
    y, es_tr = D["y"], D["es_tr"]
    n_pos_tr, n_pos_te = int(y[es_tr].sum()), int(y[~es_tr].sum())
    if n_pos_tr < 20 or n_pos_te < 5:
        print(
            f"  [{enf}] muy pocos casos (train={n_pos_tr}, test={n_pos_te}) -> se omite"
        )
        return False
    orden, ranking = C.top_n_chi2(D["Xalta"], y, es_tr, D["nombres_alta"], top_n)
    ranking.to_csv(C.DIR_FEAT / f"ranking_chi2_{enf}.csv", index=False)
    X = sparse.hstack([D["Xseg"], D["Xalta"][:, orden]], format="csr")
    nombres = D["nombres_seg"] + list(D["nombres_alta"][orden])
    joblib.dump(
        {
            "X": X,
            "y": y,
            "es_tr": es_tr,
            "grupos": D["grupos"],
            "nombres": nombres,
            "orden": orden,
            "enfermedad": enf,
        },
        C.DIR_FEAT / f"{enf}.joblib",
    )
    print(
        f"  [{enf}] OK -> {X.shape[0]:,}x{X.shape[1]} | pos train={n_pos_tr} test={n_pos_te}"
    )
    return True


def main():
    ap = argparse.ArgumentParser(
        description="ETAPA features + selección chi² top-N (por enfermedad)."
    )
    ap.add_argument("--enfermedad")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--top-n", type=int, default=100, dest="top_n")
    ap.add_argument("--piso", type=int, default=30)
    ap.add_argument("--sin-severidad", action="store_true", dest="sin_severidad")
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        dest="skip_existing",
        help="salta enfermedades cuyo artefacto ya existe (reanudar)",
    )
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
    print("Cargando cohorte reumatológica (una vez)…")
    base = C.cargar_cohorte()
    print(f"  cohorte: {len(base):,} episodios")

    for enf in enfermedades:
        art = C.DIR_FEAT / f"{enf}.joblib"
        if args.skip_existing and art.exists():
            print(f"  [{enf}] ya existe -> se salta")
            continue
        features_una(base, enf, args.top_n, args.piso, args.sin_severidad)
    print(f"Listo features. ({time.time()-t0:.1f}s) -> {C.DIR_FEAT}")


if __name__ == "__main__":
    main()
