# =============================================================================
# dashboard_agregados.py — Precálculo de agregados para el dashboard (B5, OE4)
# Caracterización de pacientes reumatológicos con GRD y ML — USACH · Diego Oliva
#
# Genera el archivo de agregados que consume el dashboard estático (dashboard.html).
# El dashboard NO lee datos a nivel de episodio: solo este archivo precalculado.
#
# Contenido:
#   - embudo de conformación de la cohorte,
#   - indicadores por enfermedad (a nivel de enfermedad, sin filtrar),
#   - DOS referencias: cohorte reumatológica y población hospitalizada general (B1),
#   - ejes de filtro (regiones, previsiones, tramos etarios, años),
#   - celdas de conteo por combinación (región × previsión × tramo × año), tanto de
#     la cohorte única como por enfermedad, para los filtros cruzados del dashboard.
# Regla de tamaño mínimo de celda: toda celda con n<5 no se publica (se omite del
# archivo). Como el dashboard suma solo celdas visibles, no hay recuperación por
# resta desde un total publicado.
#
# Salida: dashboard/datos_dashboard.js  (window.DATOS = {...};)
# USO:  python dashboard_agregados.py [--col-muerte CONDICION_EGRESO]
# =============================================================================
from __future__ import annotations
import argparse, json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

import _comun_alt as C

MIN_CEL = 5
D3 = ["DIAGNOSTICO1", "DIAGNOSTICO2", "DIAGNOSTICO3"]
DISP = {
    "artrosis_osteoartritis": ("artrosis", "Artrosis / osteoartritis", "degen"),
    "lupus_eritematoso_sistemico": ("lupus", "Lupus eritematoso sistémico", "sist"),
    "fibromialgia": ("fibromialgia", "Fibromialgia", "degen"),
    "vasculitis": ("vasculitis", "Vasculitis", "sist"),
    "artritis_reumatoide": ("ar", "Artritis reumatoide", "infl"),
    "miositis": ("miositis", "Miositis", "sist"),
    "sindrome_de_sjogren": ("sjogren", "Síndrome de Sjögren", "sist"),
    "gota": ("gota", "Gota", "degen"),
    "esclerodermia": ("esclerodermia", "Esclerodermia", "sist"),
    "artritis_idiopatica_juvenil": ("aij", "Artritis idiopática juvenil", "infl"),
    "uveitis": ("uveitis", "Uveítis", "degen"),
    "artritis_psoriasica": ("psoriasica", "Artritis psoriásica", "infl"),
    "sindrome_de_raynaud": ("raynaud", "Síndrome de Raynaud", "sist"),
    "espondilitis_anquilosante": ("espondilitis", "Espondilitis anquilosante", "infl"),
}
REG_NOMBRE = {  # normaliza etiquetas de región a nombre legible (según valores del registro)
    "METROPOLITANA": "Metropolitana", "BIOBIO": "Biobío", "ARAUCANIA": "La Araucanía",
    "MAULE": "Maule", "VALPARAISO": "Valparaíso", "COQUIMBO": "Coquimbo",
    "LOS_LAGOS": "Los Lagos", "OHIGGINS": "O'Higgins", "NUBLE": "Ñuble",
    "ATACAMA": "Atacama", "LOS_RIOS": "Los Ríos", "TARAPACA": "Tarapacá",
    "ANTOFAGASTA": "Antofagasta", "ARICA_PARINACOTA": "Arica y Parinacota",
    "MAGALLANES": "Magallanes", "AYSEN": "Aysén",
}
PREV_NOMBRE = {"FONASA_MAI_A": "FONASA A", "FONASA_MAI_B": "FONASA B", "FONASA_MAI_C": "FONASA C",
               "FONASA_MAI_D": "FONASA D", "FONASA_FLE": "FONASA libre elección", "NO_FONASA": "No FONASA"}


def tramo(e):
    if pd.isna(e): return None
    e = float(e)
    return "0–18" if e <= 18 else "19–30" if e <= 30 else "31–45" if e <= 45 else "46–60" if e <= 60 else ">60"


def cie_cap(code):
    """Mapea un código CIE-10 a su sistema (capítulo), en etiqueta corta en español."""
    if not code or not isinstance(code, str) or len(code) < 3:
        return None
    L = code[0].upper()
    try:
        num = int(code[1:3])
    except ValueError:
        return None
    if L in ("A", "B"): return "Infecciosas"
    if L == "C" or (L == "D" and num <= 48): return "Neoplasias"
    if L == "D" and num >= 50: return "Sangre/inmunidad"
    if L == "E": return "Endocrino/metabólico"
    if L == "F": return "Salud mental"
    if L == "G": return "Sistema nervioso"
    if L == "H" and num <= 59: return "Oftalmológico"
    if L == "H" and num >= 60: return "Otológico"
    if L == "I": return "Circulatorio"
    if L == "J": return "Respiratorio"
    if L == "K": return "Digestivo"
    if L == "L": return "Piel"
    if L == "M": return "Osteomuscular"
    if L == "N": return "Genitourinario"
    if L == "O": return "Embarazo/puerperio"
    if L == "P": return "Perinatal"
    if L == "Q": return "Malformaciones congénitas"
    if L == "R": return "Síntomas/signos"
    if L in ("S", "T"): return "Traumatismos/intoxicaciones"
    if L in ("V", "W", "X", "Y"): return "Causas externas"
    if L == "Z": return "Factores de salud/contacto"
    return None


def comorbilidades():
    """Top comorbilidades por enfermedad, agrupadas por sistema (capítulo CIE-10),
    excluyendo los 14 grupos de códigos índice (B3). Cuenta episodios (presencia por
    sistema, no ocurrencias), aplica supresión n<MIN_CEL y devuelve top-6 por enfermedad."""
    import pyarrow.dataset as ds
    d35 = [f"DIAGNOSTICO{i}" for i in range(1, 36)]
    tbl = ds.dataset(C.RUTA_BASE, format="parquet").to_table(
        columns=d35 + ["grupo_paciente"], filter=ds.field("grupo_paciente") == "Reumatológico")
    df = tbl.to_pandas()
    norm = {c: C.norm_code_series(df[c]) for c in d35}
    index_set = set()
    flags = {}
    for enf in C.enfermedades_todas():
        cs = C.norm_set(C.CODIGOS_REUMATICOS.get(enf, [])); index_set |= cs
        flags[enf] = norm["DIAGNOSTICO1"].isin(cs) | norm["DIAGNOSTICO2"].isin(cs) | norm["DIAGNOSTICO3"].isin(cs)
    allcodes = set()
    for c in d35: allcodes |= set(norm[c].dropna().unique())
    capmap = {code: (None if code in index_set else cie_cap(code)) for code in allcodes}
    cap_cols = [norm[c].map(capmap) for c in d35]
    chapset = sorted({x for cc in cap_cols for x in cc.dropna().unique()})
    presence = {L: pd.Series(False, index=df.index) for L in chapset}
    for cc in cap_cols:
        for L in chapset:
            presence[L] = presence[L] | (cc == L)
    # Se excluyen los sistemas que no son comorbilidad clínica real: los códigos Z
    # (factores/contacto con servicios de salud) y R (síntomas y signos mal definidos).
    excl = {"Factores de salud/contacto", "Síntomas/signos"}
    out = []
    for enf in C.enfermedades_todas():
        f = flags[enf].to_numpy(bool)
        cnt = [(L, int((presence[L].to_numpy(bool) & f).sum())) for L in chapset]
        cnt = sorted([(L, n) for L, n in cnt if n >= MIN_CEL and L not in excl], key=lambda t: -t[1])[:6]
        out.append([{"sis": L, "n": n} for L, n in cnt])
    return out


def cie9_cap(code):
    """Mapea un código de procedimiento CIE-9-MC a su capítulo (etiqueta corta)."""
    if not code or not isinstance(code, str):
        return None
    d = code.split(".")[0].strip()
    if not d.isdigit():
        return None
    n = int(d[:2])
    if n == 0: return "Misceláneos"
    if 1 <= n <= 5: return "Sistema nervioso"
    if 6 <= n <= 7: return "Endocrino"
    if 8 <= n <= 16: return "Oftalmológico"
    if 18 <= n <= 20: return "Otológico"
    if 21 <= n <= 29: return "Nariz/boca/faringe"
    if 30 <= n <= 34: return "Respiratorio"
    if 35 <= n <= 39: return "Cardiovascular"
    if 40 <= n <= 41: return "Hemático/linfático"
    if 42 <= n <= 54: return "Digestivo"
    if 55 <= n <= 59: return "Urinario"
    if 60 <= n <= 64: return "Genital masculino"
    if 65 <= n <= 75: return "Obstétrico/ginecológico"
    if 76 <= n <= 84: return "Musculoesquelético"
    if 85 <= n <= 86: return "Piel/mama"
    if 87 <= n <= 99: return "Diagnóstico/terapéutico"
    return None


def procedimientos():
    """Top procedimientos por enfermedad, agrupados por capítulo CIE-9-MC. Cuenta episodios
    (presencia por capítulo, no ocurrencias), aplica supresión n<MIN_CEL, top-6 por enfermedad."""
    import pyarrow.dataset as ds
    p30 = [f"PROCEDIMIENTO{i}" for i in range(1, 31)]
    d3 = ["DIAGNOSTICO1", "DIAGNOSTICO2", "DIAGNOSTICO3"]
    disp = set(pq.read_schema(C.RUTA_BASE).names)
    cols = [c for c in p30 if c in disp] + d3
    df = ds.dataset(C.RUTA_BASE, format="parquet").to_table(
        columns=cols + ["grupo_paciente"], filter=ds.field("grupo_paciente") == "Reumatológico").to_pandas()
    dn = [C.norm_code_series(df[c]) for c in d3]
    flags = {}
    for enf in C.enfermedades_todas():
        cs = C.norm_set(C.CODIGOS_REUMATICOS.get(enf, []))
        flags[enf] = dn[0].isin(cs) | dn[1].isin(cs) | dn[2].isin(cs)
    pcols = [c for c in p30 if c in df.columns]
    allc = set()
    for c in pcols: allc |= set(df[c].dropna().astype(str).unique())
    capmap = {code: cie9_cap(code) for code in allc}
    cap_cols = [df[c].astype(str).map(capmap) for c in pcols]
    chapset = sorted({x for cc in cap_cols for x in cc.dropna().unique()})
    presence = {L: pd.Series(False, index=df.index) for L in chapset}
    for cc in cap_cols:
        for L in chapset:
            presence[L] = presence[L] | (cc == L)
    # Se excluyen los capítulos que no describen la vía de atención de la enfermedad, sino el
    # cuidado de soporte ubicuo de toda hospitalización: "Diagnóstico/terapéutico" (87-99:
    # inyecciones, sueros, laboratorio, imagenología, kinesioterapia) y "Misceláneos" (00). Es la
    # misma lógica con que se excluyen los códigos Z y R en las comorbilidades: son tan frecuentes
    # que tapan los procedimientos que sí caracterizan a cada enfermedad (cirugía por órgano).
    excl = {"Diagnóstico/terapéutico", "Misceláneos"}
    out = []
    for enf in C.enfermedades_todas():
        f = flags[enf].to_numpy(bool)
        cnt = [(L, int((presence[L].to_numpy(bool) & f).sum())) for L in chapset]
        cnt = sorted([(L, n) for L, n in cnt if n >= MIN_CEL and L not in excl], key=lambda t: -t[1])[:6]
        out.append([{"sis": L, "n": n} for L, n in cnt])
    return out


def detecta(cols, cands):
    for c in cands:
        if c in cols: return c
    return None


def indicadores(df, col_muerte):
    def med(c): return round(float(pd.to_numeric(df[c], errors="coerce").median()), 1)
    def tasa(m): return round(float(np.asarray(m, float).mean()) * 100, 1)
    r = {"edad": round(float(pd.to_numeric(df["edad"], errors="coerce").median()), 0),
         "mujer": round(float((df["sexo"] == 0).mean()) * 100, 1),
         "hombre": round(float((df["sexo"] == 1).mean()) * 100, 1),
         "estancia": med("duracion_hospitalizacion"),
         "sev": round(float(df["IR_29301_SEVERIDAD"].median()), 0),
         "peso": round(float(df["IR_29301_PESO"].median()), 2),
         "reing": tasa(pd.to_numeric(df["reingreso_30d"], errors="coerce") == 1),
         "urg": tasa(df["TIPO_INGRESO"].astype(str).str.upper() == "URGENCIA"),
         "cir": tasa(pd.to_numeric(df["flag_intervencion"], errors="coerce") == 1)}
    r["mort"] = (tasa(df[col_muerte].astype(str).str.upper().str.contains("FALLEC", na=False))
                 if col_muerte and col_muerte in df.columns else None)
    return r


def celdas_crudas(df, ejes, con_enf=None):
    """Todas las celdas [ (enfIdx,) regIdx, prevIdx, tramoIdx, anioIdx, n ] SIN suprimir."""
    ri = {v: i for i, v in enumerate(ejes["reg"])}
    pi = {v: i for i, v in enumerate(ejes["prev"])}
    ti = {v: i for i, v in enumerate(ejes["tramo"])}
    ai = {v: i for i, v in enumerate(ejes["anio"])}
    g = df.groupby(["_reg", "_prev", "_tramo", "_anio"], dropna=True).size()
    out = []
    for (r, p, t, a), n in g.items():
        if t is None: continue
        base = [ri[r], pi[p], ti[t], ai[a], int(n)]
        out.append(([con_enf] + base) if con_enf is not None else base)
    return out


def suprime_complementaria(cells, n_pos, key_dims):
    """Supresión primaria (n<MIN_CEL) + complementaria: dentro de cada margen protegido
    (definido por cada dimensión de key_dims) nunca se deja EXACTAMENTE una celda suprimida;
    si ocurre, se suprime además la celda superviviente más pequeña de ese margen. Se itera
    hasta estabilizar. Esto evita que una celda se recupere por resta desde un total publicado
    (p. ej. los totales por enfermedad de la Tabla 5.1 o las distribuciones marginales del anexo)."""
    supp = set(i for i, c in enumerate(cells) if c[n_pos] < MIN_CEL)
    cambiado = True
    while cambiado:
        cambiado = False
        for d in key_dims:
            grupos = {}
            for i, c in enumerate(cells):
                grupos.setdefault(c[d], []).append(i)
            for idxs in grupos.values():
                sup = [i for i in idxs if i in supp]
                if len(sup) == 1:
                    surv = [i for i in idxs if i not in supp]
                    if surv:
                        supp.add(min(surv, key=lambda i: cells[i][n_pos]))
                        cambiado = True
    return [c for i, c in enumerate(cells) if i not in supp]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--col-muerte", default=None, dest="col_muerte")
    args = ap.parse_args()

    disp = set(pq.read_schema(C.RUTA_BASE).names)
    cm = detecta(disp, [args.col_muerte] if args.col_muerte else
                 ["CONDICION_EGRESO", "CONDICION_DE_EGRESO", "TIPO_ALTA", "TIPOALTA"])
    cr = detecta(disp, ["region", "REGION"]); cp = detecta(disp, ["PREVISION", "prevision"])
    ca = detecta(disp, ["anio", "ANIO", "year"])
    base_cols = [f"DIAGNOSTICO{i}" for i in range(1, 4)] + ["grupo_paciente", "edad", "sexo",
        "duracion_hospitalizacion", "IR_29301_PESO", "IR_29301_SEVERIDAD", "reingreso_30d",
        "TIPO_INGRESO", "flag_intervencion"] + [x for x in (cm, cr, cp, ca) if x]
    todo = pq.read_table(C.RUTA_BASE, columns=[c for c in dict.fromkeys(base_cols) if c in disp]).to_pandas()
    reum = todo[todo["grupo_paciente"] == "Reumatológico"].copy()

    dn = [C.norm_code_series(reum[c]) for c in D3]
    flags, en3 = {}, pd.Series(False, index=reum.index)
    for enf in C.enfermedades_todas():
        cs = C.norm_set(C.CODIGOS_REUMATICOS.get(enf, []))
        pres = dn[0].isin(cs) | dn[1].isin(cs) | dn[2].isin(cs)
        flags[enf] = pres; en3 = en3 | pres
    coh = reum[en3.values].copy()
    for enf in flags: flags[enf] = flags[enf][en3.values].to_numpy(bool)

    # Los faltantes de región/previsión (~0,03% de la cohorte) se dejan como NaN: el
    # groupby(dropna=True) los excluye de las celdas y no aparecen como categoría "Sin dato".
    def limpia(s):
        return s.astype(str).replace({"None": np.nan, "nan": np.nan, "NaN": np.nan, "": np.nan})
    coh["_reg"] = limpia(coh[cr]) if cr else np.nan
    coh["_prev"] = limpia(coh[cp]) if cp else np.nan
    coh["_anio"] = coh[ca].astype("Int64").astype(str) if ca else "Sin dato"
    coh["_tramo"] = coh["edad"].map(tramo)

    ejes = {"reg": sorted(coh["_reg"].dropna().unique()),
            "prev": sorted(coh["_prev"].dropna().unique()),
            "tramo": ["0–18", "19–30", "31–45", "46–60", ">60"],
            "anio": sorted(coh["_anio"].dropna().unique())}

    D = {"funnel": [
            {"label": "Egresos GRD (2019–2024)", "n": 5808536},
            {"label": "Registros depurados", "n": 5801611},
            {"label": "Con la enfermedad en cualquier diagnóstico (máx. 35)", "n": int(len(reum))},
            {"label": "Con la enfermedad entre los 3 diagnósticos principales", "n": int(len(coh))}],
         "ejes": {"regiones": [REG_NOMBRE.get(r, r) for r in ejes["reg"]],
                  "previsiones": [PREV_NOMBRE.get(p, p) for p in ejes["prev"]],
                  "tramos": ejes["tramo"], "anios": ejes["anio"]},
         "ref_cohorte": indicadores(coh, cm),
         "ref_general": indicadores(todo[todo["grupo_paciente"] != "Reumatológico"], cm)}

    D["enfermedades"] = []
    for i, enf in enumerate(C.enfermedades_todas()):
        sid, nombre, grupo = DISP[enf]; s = coh[flags[enf]]; ind = indicadores(s, cm)
        D["enfermedades"].append({"id": sid, "nombre": nombre, "grupo": grupo, "n": int(len(s)), **ind})

    # Cohorte: proteger las marginales 1-D publicadas en el anexo (región, previsión, tramo, año)
    coh_crudas = celdas_crudas(coh, ejes)
    D["celdas_cohorte"] = suprime_complementaria(coh_crudas, n_pos=4, key_dims=[0, 1, 2, 3])
    # Por enfermedad: proteger el total por enfermedad (Tabla 5.1), que es el externamente conocido
    enf_crudas = []
    for i, enf in enumerate(C.enfermedades_todas()):
        enf_crudas += celdas_crudas(coh[flags[enf]], ejes, con_enf=i)
    D["celdas_enf"] = suprime_complementaria(enf_crudas, n_pos=5, key_dims=[0])
    print(f"  supresion cohorte: {len(coh_crudas)}->{len(D['celdas_cohorte'])} | "
          f"enf: {len(enf_crudas)}->{len(D['celdas_enf'])}")

    D["comorbilidades"] = comorbilidades()
    D["procedimientos"] = procedimientos()

    dest = C.DIR_OUT.parent.parent / "dashboard" / "datos_dashboard.js"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("window.DATOS = " + json.dumps(D, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"Guardado: {dest}")
    print(f"  celdas cohorte: {len(D['celdas_cohorte'])} | celdas x enfermedad: {len(D['celdas_enf'])}")
    print(f"  ref_general (muerte={cm}): {D['ref_general']}")


if __name__ == "__main__":
    main()
