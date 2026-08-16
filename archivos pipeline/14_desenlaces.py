# =============================================================================
# 14_desenlaces.py — Análisis de desenlaces (criterio (b) de la hipótesis)
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Sobre la cohorte de estudio (primeras-3 posiciones) y en esquema UNO-CONTRA-RESTO
# por enfermedad, cuantifica la SEPARABILIDAD en los desenlaces operativos con
# TAMAÑO DE EFECTO e INTERVALO DE CONFIANZA (no solo significancia).
#
# Cambios que atienden las observaciones B1, B2 y B3 del profesor:
#
#   B1 (clase de referencia dominada por artrosis): el análisis se ejecuta con DOS
#       referencias y se reporta la sensibilidad:
#         - "cohorte": el resto de la cohorte reumatológica (definición original).
#         - "sin_artrosis": el resto EXCLUYENDO la artrosis de la clase negativa.
#       (Para la propia artrosis, "sin_artrosis" no aplica y se omite.)
#
#   B2 (severidad y peso GRD salen del agrupador que lee los códigos índice): se
#       separan los desenlaces en dos familias y se etiquetan:
#         - "independiente": estancia, reingreso, urgencia, uso de pabellón,
#           intervención quirúrgica y mortalidad intrahospitalaria (no derivan del
#           agrupador; sostienen el criterio (b)).
#         - "agrupador": severidad APR-DRG y peso GRD (derivan del IR-GRD; se
#           reportan con la salvedad de circularidad, no como evidencia principal).
#
#   B3 (la comorbilidad se medía con un conteo que incluía los códigos índice): la
#       comorbilidad se recalcula como el número de diagnósticos NO reumáticos del
#       episodio, excluyendo los 14 grupos de códigos que definen la cohorte
#       (misma exclusión que se aplica al pool de predictores). Se recorre las 35
#       posiciones diagnósticas.
#
# δ ∈ [-1, 1]: 0 = sin diferencia; |δ|~0,11 pequeño, ~0,28 medio, ~0,43 grande.
# Salida: resultados_modelado/desenlaces_por_enfermedad.csv
#         (columna "referencia" ∈ {cohorte, sin_artrosis}; "familia" ∈ {independiente, agrupador})
#
# USO:  python 14_desenlaces.py                 (n_boot=300)
#       python 14_desenlaces.py --rapido        (n_boot=100)
#       python 14_desenlaces.py --col-muerte CONDICION_EGRESO --val-muerte FALLECIDO
#         (si la mortalidad intrahospitalaria vive en otra columna/valor; si no se
#          indica y no se encuentra automáticamente, ese desenlace se omite)
# =============================================================================
from __future__ import annotations

import argparse

import _comun_alt as C
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.stats import mannwhitneyu

OUT = C.DIR_OUT / "desenlaces_por_enfermedad.csv"

# Desenlaces continuos/ordinales -> (etiqueta, familia)
CONT = {
    "duracion_hospitalizacion": ("Estancia (días)", "independiente"),
    "n_comorbilidad_no_reum": ("Comorbilidad no reumática (nº dx)", "independiente"),
    "IR_29301_SEVERIDAD": ("Severidad APR-DRG", "agrupador"),
    "IR_29301_PESO": ("Peso GRD (recursos)", "agrupador"),
}
# Desenlaces binarios -> (etiqueta, familia). Se comparan por diferencia de tasas.
BIN = {
    "reingreso_30d": ("Reingreso 30 días (tasa)", "independiente"),
    "es_urgencia": ("Ingreso por urgencia (tasa)", "independiente"),
    "flag_pabellon": ("Uso de pabellón (tasa)", "independiente"),
    "flag_intervencion": ("Intervención quirúrgica (tasa)", "independiente"),
    "es_muerte": ("Mortalidad intrahospitalaria (tasa)", "independiente"),
}

DIAGS = [f"DIAGNOSTICO{i}" for i in range(1, 36)]


def cliffs_delta(a, b):
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 5 or len(b) < 5:
        return np.nan
    U = mannwhitneyu(a, b, alternative="two-sided").statistic
    return 2.0 * U / (len(a) * len(b)) - 1.0


def dif_tasas(a, b):
    return np.nanmean(a) - np.nanmean(b)


def ic_boot(a, b, fn, n_boot, seed=C.SEED, cap=8000):
    r = np.random.default_rng(seed)
    vals = []
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 5 or len(b) < 5:
        return (np.nan, np.nan)
    na, nb = min(len(a), cap), min(len(b), cap)
    for _ in range(n_boot):
        sa = a[r.integers(0, len(a), na)]
        sb = b[r.integers(0, len(b), nb)]
        vals.append(fn(sa, sb))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return (float(lo), float(hi))


def detectar_col_muerte(schema_names, arg_col):
    if arg_col:
        return arg_col if arg_col in schema_names else None
    for cand in (
        "CONDICION_EGRESO",
        "CONDICION_DE_EGRESO",
        "TIPO_ALTA",
        "ESTADO_EGRESO",
        "TIPOALTA",
        "CONDICIONEGRESO",
    ):
        if cand in schema_names:
            return cand
    return None


def main():
    ap = argparse.ArgumentParser(
        description="Análisis de desenlaces (criterio b), con B1/B2/B3."
    )
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--col-muerte", default=None, dest="col_muerte")
    ap.add_argument("--val-muerte", default="FALLECIDO", dest="val_muerte")
    args = ap.parse_args()
    n_boot = 100 if args.rapido else 300

    disponibles = set(pq.read_schema(C.RUTA_BASE).names)
    col_muerte = detectar_col_muerte(disponibles, args.col_muerte)

    base_cols = DIAGS + [
        "grupo_paciente",
        "reingreso_30d",
        "duracion_hospitalizacion",
        "IR_29301_PESO",
        "IR_29301_SEVERIDAD",
        "TIPO_INGRESO",
        "flag_pabellon",
        "flag_intervencion",
    ]
    if col_muerte:
        base_cols.append(col_muerte)
    base_cols = [c for c in dict.fromkeys(base_cols) if c in disponibles]

    df = pq.read_table(
        C.RUTA_BASE,
        columns=base_cols,
        filters=[("grupo_paciente", "=", "Reumatológico")],
    ).to_pandas()

    # --- flags primeras-3 por enfermedad + unión de códigos reumáticos (B3) ---
    dn = [C.norm_code_series(df[c]) for c in DIAGS]  # 35 posiciones normalizadas
    union_reum = set()
    flags = {}
    en_p3 = pd.Series(False, index=df.index)
    for enf in C.enfermedades_todas():
        cs = C.norm_set(C.CODIGOS_REUMATICOS.get(enf, []))
        union_reum |= cs
        pres = dn[0].isin(cs) | dn[1].isin(cs) | dn[2].isin(cs)  # primeras-3
        flags[enf] = pres
        en_p3 = en_p3 | pres

    # --- comorbilidad NO reumática (B3): nº de dx presentes que no son códigos índice ---
    n_present = np.zeros(len(df), dtype=int)
    n_reum_present = np.zeros(len(df), dtype=int)
    for s in dn:
        pres = s.notna() & (s.astype(str).str.len() > 0)
        n_present += pres.to_numpy(int)
        n_reum_present += (pres & s.isin(union_reum)).to_numpy(int)
    df["n_comorbilidad_no_reum"] = n_present - n_reum_present

    # --- desenlaces binarios derivados ---
    df["es_urgencia"] = (
        df["TIPO_INGRESO"].astype(str).str.upper() == "URGENCIA"
    ).astype(int)
    for c in ("flag_pabellon", "flag_intervencion"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if col_muerte:
        df["es_muerte"] = (
            df[col_muerte]
            .astype(str)
            .str.upper()
            .str.contains(args.val_muerte.upper(), na=False)
        ).astype(int)

    # --- recorte a la cohorte primeras-3 ---
    df = df[en_p3.values].copy()
    for enf in flags:
        flags[enf] = flags[enf][en_p3.values].to_numpy(bool)
    art = flags["artrosis_osteoartritis"]
    print(
        f"Cohorte primeras-3: {len(df):,} episodios  (col. muerte: {col_muerte or 'no encontrada -> se omite'})"
    )

    def registrar(filas, enf, ref, m, mask_resto):
        for col, (lab, fam) in CONT.items():
            if col not in df.columns:
                continue
            a = pd.to_numeric(df[col][m], errors="coerce").to_numpy(float)
            b = pd.to_numeric(df[col][mask_resto], errors="coerce").to_numpy(float)
            delta = cliffs_delta(a, b)
            lo, hi = ic_boot(a, b, cliffs_delta, n_boot)
            filas.append(
                {
                    "enfermedad": enf,
                    "referencia": ref,
                    "familia": fam,
                    "desenlace": lab,
                    "tipo": "cliffs_delta",
                    "val_enf": round(float(np.nanmedian(a)), 3),
                    "val_resto": round(float(np.nanmedian(b)), 3),
                    "efecto": round(delta, 3) if delta == delta else None,
                    "ic_low": round(lo, 3) if lo == lo else None,
                    "ic_high": round(hi, 3) if hi == hi else None,
                    "n_enf": int(m.sum()),
                    "n_resto": int(mask_resto.sum()),
                }
            )
        for col, (lab, fam) in BIN.items():
            if col not in df.columns:
                continue
            a = pd.to_numeric(df[col][m], errors="coerce").to_numpy(float)
            b = pd.to_numeric(df[col][mask_resto], errors="coerce").to_numpy(float)
            dif = dif_tasas(a, b)
            lo, hi = ic_boot(a, b, dif_tasas, n_boot)
            filas.append(
                {
                    "enfermedad": enf,
                    "referencia": ref,
                    "familia": fam,
                    "desenlace": lab,
                    "tipo": "dif_tasas",
                    "val_enf": round(float(np.nanmean(a)), 3),
                    "val_resto": round(float(np.nanmean(b)), 3),
                    "efecto": round(dif, 3) if dif == dif else None,
                    "ic_low": round(lo, 3) if lo == lo else None,
                    "ic_high": round(hi, 3) if hi == hi else None,
                    "n_enf": int(m.sum()),
                    "n_resto": int(mask_resto.sum()),
                }
            )

    filas = []
    for enf in C.enfermedades_todas():
        m = flags[enf]
        if int(m.sum()) < 20:
            continue
        # B1: referencia = cohorte completa
        registrar(filas, enf, "cohorte", m, ~m)
        # B1: referencia = resto SIN artrosis (no aplica a la propia artrosis)
        if enf != "artrosis_osteoartritis":
            resto_sa = (~m) & (~art)
            registrar(filas, enf, "sin_artrosis", m, resto_sa)

    out = pd.DataFrame(filas)
    out.to_csv(OUT, index=False)
    print(f"Guardado: {OUT}  ({len(out)} filas)")

    # resumen comparativo: severidad con ambas referencias (para ver el efecto de B1)
    sev = out[(out.desenlace == "Severidad APR-DRG")].pivot_table(
        index="enfermedad", columns="referencia", values="efecto"
    )
    print("\nCliff's δ de severidad — cohorte vs sin_artrosis:")
    print(sev.to_string())


if __name__ == "__main__":
    main()
