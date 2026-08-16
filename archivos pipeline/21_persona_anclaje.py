# =============================================================================
# Caracterización de pacientes reumatológicos con GRD y ML — USACH · Diego Oliva
#
# Qué hace: sobre la cohorte de estudio (enfermedad en las 3 primeras posiciones),
# agrega los episodios a PERSONAS únicas dentro de cada bloque temporal enlazable
# (2019-2020 y 2021-2024; el identificador no es estable entre bloques). Para cada
# enfermedad reporta, a nivel de persona: n, % mujeres y edad mediana. Sirve para el
# anclaje demográfico persona-contra-persona .
#
# Salida: consola (tabla) + resultados_modelado_alt/anclaje_persona.csv
# =============================================================================
from __future__ import annotations
import pandas as pd
import pyarrow.parquet as pq
import _comun_alt as C

D3 = ["DIAGNOSTICO1", "DIAGNOSTICO2", "DIAGNOSTICO3"]
NOMBRE = {  # clave interna -> nombre legible
    "artritis_idiopatica_juvenil": "AIJ", "artritis_psoriasica": "Psoriásica",
    "artritis_reumatoide": "AR", "artrosis_osteoartritis": "Artrosis",
    "esclerodermia": "Esclerodermia", "espondilitis_anquilosante": "Espondilitis",
    "fibromialgia": "Fibromialgia", "lupus_eritematoso_sistemico": "Lupus",
    "miositis": "Miositis", "sindrome_de_raynaud": "Raynaud",
    "sindrome_de_sjogren": "Sjögren", "uveitis": "Uveítis",
    "gota": "Gota", "vasculitis": "Vasculitis",
}


def main():
    cols = D3 + ["grupo_paciente", "id_paciente", "anio", "sexo", "edad"]
    t = pq.read_table(C.RUTA_BASE, columns=cols).to_pandas()
    reum = t[t["grupo_paciente"] == "Reumatológico"].copy()

    # cohorte: enfermedad en las 3 primeras posiciones
    dn = [C.norm_code_series(reum[c]) for c in D3]
    en3 = pd.Series(False, index=reum.index)
    flags = {}
    for enf in C.enfermedades_todas():
        cs = C.norm_set(C.CODIGOS_REUMATICOS.get(enf, []))
        pres = dn[0].isin(cs) | dn[1].isin(cs) | dn[2].isin(cs)
        flags[enf] = pres
        en3 = en3 | pres
    coh = reum[en3.values].copy()
    for enf in flags:
        flags[enf] = flags[enf][en3.values].to_numpy(bool)

    # bloque temporal enlazable
    coh["bloque"] = coh["anio"].apply(lambda a: "2019-2020" if a in (2019, 2020) else "2021-2024")

    filas = []
    for enf in C.enfermedades_todas():
        s = coh[flags[enf]].copy()
        # persona única por bloque: una fila por (id_paciente, bloque), edad del primer egreso del bloque
        s = s.sort_values("anio").drop_duplicates(subset=["bloque", "id_paciente"], keep="first")
        n = len(s)
        mujer = round(float((s["sexo"] == 0).mean()) * 100, 1) if n else None
        edad = round(float(pd.to_numeric(s["edad"], errors="coerce").median()), 0) if n else None
        # también episodios, para comparar
        e = coh[flags[enf]]
        filas.append({"enfermedad": NOMBRE.get(enf, enf), "n_personas": n,
                      "pct_mujeres_persona": mujer, "edad_mediana_persona": edad,
                      "n_episodios": int(len(e)),
                      "pct_mujeres_episodio": round(float((e["sexo"] == 0).mean()) * 100, 1),
                      "edad_mediana_episodio": round(float(pd.to_numeric(e["edad"], errors="coerce").median()), 0)})

    df = pd.DataFrame(filas)
    dest = C.DIR_OUT / "anclaje_persona.csv"
    df.to_csv(dest, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 140, "display.max_columns", 20)
    print(df.to_string(index=False))
    print(f"\nGuardado: {dest}")


if __name__ == "__main__":
    main()
