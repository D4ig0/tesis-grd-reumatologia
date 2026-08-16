# =============================================================================
# estratificacion.py — Estratificación por tramo etario, región y previsión (B6)
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Genera las estratificaciones declaradas en los alcances y que faltaban en el
# Capítulo 5, sobre la cohorte de estudio (primeras-3 posiciones):
#   1) Perfil por TRAMO ETARIO (tramos de Vásquez, CORREGIDOS: 46-60 sin solape).
#   2) Distribución por REGIÓN.
#   3) Distribución por SISTEMA DE PREVISIÓN.
# Aplica la regla de tamaño mínimo de celda (n<5 se suprime) declarada en la ética.
#
# Salidas (en resultados_modelado/):
#   estrat_tramo_etario.csv, estrat_region.csv, estrat_prevision.csv
# USO:  python estratificacion.py
# =============================================================================
from __future__ import annotations

import _comun_alt as C
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

MIN_CEL = 5
D3 = ["DIAGNOSTICO1", "DIAGNOSTICO2", "DIAGNOSTICO3"]


def tramo(e):
    if pd.isna(e):
        return "NA"
    e = float(e)
    if e <= 18:
        return "0-18"
    if e <= 30:
        return "19-30"
    if e <= 45:
        return "31-45"
    if e <= 60:
        return "46-60"  # <-- corregido (antes 45-60, solapaba)
    return ">60"


def detecta(cols, cands):
    for c in cands:
        if c in cols:
            return c
    return None


def main():
    disp = set(pq.read_schema(C.RUTA_BASE).names)
    col_reg = detecta(
        disp, ["region", "REGION", "GLOSA_REGION", "NOMBRE_REGION", "REGION_RESIDENCIA"]
    )
    col_prev = detecta(
        disp, ["PREVISION", "prevision", "TIPO_PREVISION", "GLOSA_PREVISION"]
    )

    cols = [
        c
        for c in (
            D3
            + [
                "grupo_paciente",
                "edad",
                "sexo",
                "duracion_hospitalizacion",
                "IR_29301_SEVERIDAD",
                "reingreso_30d",
            ]
            + [c for c in (col_reg, col_prev) if c]
        )
        if c in disp
    ]
    df = pq.read_table(
        C.RUTA_BASE, columns=cols, filters=[("grupo_paciente", "=", "Reumatológico")]
    ).to_pandas()

    # cohorte primeras-3
    dn = [C.norm_code_series(df[c]) for c in D3]
    union = set()
    for enf in C.enfermedades_todas():
        union |= C.norm_set(C.CODIGOS_REUMATICOS.get(enf, []))
    en3 = dn[0].isin(union) | dn[1].isin(union) | dn[2].isin(union)
    df = df[en3.values].copy()
    n = len(df)
    print(
        f"Cohorte primeras-3: {n:,} episodios (región: {col_reg}, previsión: {col_prev})"
    )

    def suprime(t):
        t = t.copy()
        t.loc[t["n"] < MIN_CEL, t.columns.difference(["grupo"])] = np.nan
        return t

    # 1) tramo etario
    df["tramo"] = df["edad"].map(tramo)
    orden = ["0-18", "19-30", "31-45", "46-60", ">60", "NA"]
    g = df.groupby("tramo")
    te = pd.DataFrame(
        {
            "grupo": orden,
            "n": [int((df.tramo == k).sum()) for k in orden],
        }
    )
    te["%_cohorte"] = (100 * te["n"] / n).round(1)
    for k, col, fn in [
        ("%_mujer", "sexo", lambda s: round((s == 0).mean() * 100, 1)),
        ("edad_md", "edad", lambda s: round(s.median(), 0)),
        ("estancia_md", "duracion_hospitalizacion", lambda s: round(s.median(), 1)),
        ("severidad_md", "IR_29301_SEVERIDAD", lambda s: round(s.median(), 0)),
        ("reingreso_%", "reingreso_30d", lambda s: round(s.mean() * 100, 1)),
    ]:
        te[k] = [
            fn(df.loc[df.tramo == kk, col]) if (df.tramo == kk).any() else np.nan
            for kk in orden
        ]
    suprime(te).to_csv(C.DIR_OUT / "estrat_tramo_etario.csv", index=False)
    print("\n[Tramo etario]\n", te.to_string(index=False))

    # 2) región y 3) previsión
    for col, salida, titulo in [
        (col_reg, "estrat_region.csv", "Región"),
        (col_prev, "estrat_prevision.csv", "Previsión"),
    ]:
        if not col:
            print(f"\n[{titulo}] columna no encontrada -> se omite")
            continue
        vc = df[col].astype(str).value_counts(dropna=False)
        t = pd.DataFrame({"grupo": vc.index, "n": vc.values})
        t["%_cohorte"] = (100 * t["n"] / n).round(1)
        suprime(t).to_csv(C.DIR_OUT / salida, index=False)
        print(f"\n[{titulo}]\n", t.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
