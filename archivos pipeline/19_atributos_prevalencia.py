# =============================================================================
# atributos_prevalencia.py — Atributos característicos por enfermedad (opción iii)
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Respaldo auditable y SIN MODELO para la caracterización por atributos (obs.
# B4 / 10.2, opción iii). Para cada enfermedad (uno-contra-resto, cohorte de
# estudio = primeras-3, SOLO conjunto de TEST) calcula, por cada atributo binario,
# la razón de prevalencias (risk ratio) entre la enfermedad y el resto, con
# intervalo de confianza al 95 % (método logarítmico de Katz):
#
#     RR = p1/p0 ,  p1 = prevalencia en la enfermedad, p0 = prevalencia en el resto
#     IC95 = exp( ln RR  ±  1.96 * sqrt(1/a - 1/n1 + 1/c - 1/n0) )
#
# Es puramente descriptivo: no depende de SHAP ni de ningún clasificador, por lo
# que no está expuesto a las fallas de las matrices SHAP ni al cuestionamiento de
# fuga. Reusa los mismos artefactos de features (08) para respetar exactamente la
# misma matriz de predictores (con los códigos definitorios ya excluidos).
#
# Salida: resultados_modelado/atributos_prevalencia_por_enfermedad.csv
#
# USO:  python atributos_prevalencia.py --todas [--top 8] [--min-casos 10]
# =============================================================================
from __future__ import annotations

import argparse

import _comun_alt as C
import joblib
import numpy as np
import pandas as pd

Z = 1.959963985  # 97.5 percentil normal


def rr_con_ic(a, n1, c, n0):
    """Risk ratio y su IC95 (Katz). Corrección de continuidad si hay ceros."""
    b, d = n1 - a, n0 - c
    if min(a, b, c, d) == 0:
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
        n1c, n0c = a + b, c + d
    else:
        n1c, n0c = n1, n0
    p1, p0 = a / n1c, c / n0c
    rr = p1 / p0
    se = np.sqrt(1 / a - 1 / n1c + 1 / c - 1 / n0c)
    lo, hi = np.exp(np.log(rr) - Z * se), np.exp(np.log(rr) + Z * se)
    return p1, p0, rr, lo, hi


def una(enf, top, min_casos):
    D = joblib.load(C.DIR_FEAT / f"{enf}.joblib")
    X, y, es_tr, nombres = D["X"], np.asarray(D["y"]), D["es_tr"], list(D["nombres"])
    Xte = X[~es_tr].tocsc()
    yte = y[~es_tr]
    n1, n0 = int((yte == 1).sum()), int((yte == 0).sum())
    filas = []
    for j, nom in enumerate(nombres):
        col = Xte[:, j].toarray().ravel()
        vals = np.unique(col)
        if not np.isin(vals, [0, 1]).all():
            continue  # solo atributos binarios (0/1)
        pos = col == 1
        a = int(((yte == 1) & pos).sum())  # enfermos con el atributo
        c = int(((yte == 0) & pos).sum())  # resto con el atributo
        if a < min_casos:
            continue  # evita RR inestables por baja frecuencia
        p1, p0, rr, lo, hi = rr_con_ic(a, n1, c, n0)
        signif = (lo > 1) or (hi < 1)  # IC excluye 1
        filas.append(
            dict(
                enfermedad=enf,
                atributo=nom,
                n1=n1,
                a=a,
                prev_enf=round(100 * p1, 1),
                prev_resto=round(100 * p0, 1),
                RR=round(rr, 2),
                IC_low=round(lo, 2),
                IC_high=round(hi, 2),
                signif=signif,
            )
        )
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["logRR_abs"] = np.abs(np.log(df["RR"].clip(lower=1e-6)))
    df = df[df["signif"]].sort_values("logRR_abs", ascending=False).head(top)
    return df.drop(columns="logRR_abs")


def main():
    ap = argparse.ArgumentParser(
        description="Atributos característicos por prevalencia (opción iii)."
    )
    ap.add_argument("--enfermedad")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--top", type=int, default=8, help="atributos por enfermedad")
    ap.add_argument(
        "--min-casos",
        type=int,
        default=10,
        dest="min_casos",
        help="mínimo de enfermos con el atributo para reportarlo",
    )
    args = ap.parse_args()
    enfs = (
        [args.enfermedad]
        if args.enfermedad
        else C.enfermedades_todas() if args.todas else None
    )
    if not enfs:
        raise SystemExit(
            f"Indica --enfermedad <nombre> o --todas. Opciones: {C.enfermedades_todas()}"
        )
    partes = []
    for enf in enfs:
        try:
            d = una(enf, args.top, args.min_casos)
            if not d.empty:
                partes.append(d)
                print(f"[{enf}] {len(d)} atributos característicos")
        except Exception as e:
            print(f"[{enf}] ERROR: {e!r}")
    if partes:
        out = C.DIR_OUT / "atributos_prevalencia_por_enfermedad.csv"
        pd.concat(partes, ignore_index=True).to_csv(out, index=False)
        print(f"\nGuardado -> {out}")


if __name__ == "__main__":
    main()
