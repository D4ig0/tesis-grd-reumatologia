# =============================================================================
# 00_orquestador.py — "PLAY": corre todo el pipeline de modelado, en orden,
# registrando el avance y REANUDANDO desde donde quedó.
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Qué hace:
#   · Corre las etapas en orden: 07_split → 08_features → 09_tuning →
#     10_entrenar_evaluar → 11_shap → 12_resumen.
#   · Guarda el ESTADO de cada etapa en resultados_modelado/pipeline_estado.json
#     (pendiente / en_curso / completado / error, con tiempos e intentos).
#   · Si se corta o falla, al volver a darle "play" REANUDA desde la última etapa
#     no completada (y con --skip-existing cada etapa salta lo ya hecho por dentro).
#   · Guarda un LOG por etapa en resultados_modelado/logs/ y AVISA claramente
#     en qué etapa falló y dónde mirar.
#
# USO (lo típico — darle play a todo):
#   python 00_orquestador.py --todas                 # las 14 enfermedades, reanudable
#   python 00_orquestador.py --todas --rapido        # prueba rápida end-to-end
#   python 00_orquestador.py --enfermedad gota       # una sola enfermedad
#   python 00_orquestador.py --todas --sin-shap      # sin la etapa SHAP (más rápido)
# Control fino:
#   --desde 09_tuning     empieza en esa etapa
#   --solo 10_entrenar_evaluar   corre solo esa etapa
#   --forzar              re-corre etapas aunque estén "completado"
#   --continuar-con-errores   no se detiene si una etapa falla
# =============================================================================
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DIR_OUT = AQUI / "resultados_modelado_alt"
DIR_LOG = DIR_OUT / "logs"
RUTA_EST = DIR_OUT / "pipeline_estado.json"
RUTA_SPLIT = AQUI.parent / "output" / "split_train_test.parquet"  # salida de 07
DIR_LOG.mkdir(parents=True, exist_ok=True)

# Etapas en orden. 'acepta' = qué flags globales se le pasan a cada script.
ETAPAS = [
    {
        "nombre": "10_entrenar_evaluar_alt",
        "script": "10_entrenar_evaluar_alt.py",
        "acepta": ["target", "modelo", "rapido", "skip"],
    },
    {
        "nombre": "11_shap_alt",
        "script": "11_shap_alt.py",
        "acepta": ["target", "skip"],
        "opcional": True,
    },
    {"nombre": "12_resumen_alt", "script": "12_resumen_alt.py", "acepta": []},
    {
        "nombre": "13_shap_resumen_alt",
        "script": "13_shap_resumen_alt.py",
        "acepta": ["target", "skip"],
        "opcional": True,
    },
]


def cargar_estado():
    if RUTA_EST.exists():
        texto = RUTA_EST.read_text(encoding="utf-8").strip()
        if texto:
            try:
                return json.loads(texto)
            except json.JSONDecodeError:
                pass
    return {"actualizado": None, "etapas": {}}


def guardar_estado(est):
    est["actualizado"] = datetime.now().isoformat(timespec="seconds")
    RUTA_EST.write_text(json.dumps(est, ensure_ascii=False, indent=2), encoding="utf-8")


def fmt_dur(seg):
    """Segundos -> '1h 03m 20s' / '3m 12s' / '45s' (para dimensionar de un vistazo)."""
    if seg is None:
        return "-"
    seg = int(round(seg))
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def resumen_tiempos(est):
    """Imprime una tabla de tiempos por etapa y la guarda en tiempos_etapas.csv."""
    filas = []
    total = 0.0
    print("\n" + "-" * 62)
    print(f"{'ETAPA':<24}{'ESTADO':<13}{'DURACIÓN':>12}{'INTENTOS':>9}")
    print("-" * 62)
    for e in ETAPAS:
        d = est["etapas"].get(e["nombre"], {})
        dur = d.get("duracion_s")
        if dur:
            total += dur
        print(
            f"{e['nombre']:<24}{d.get('estado','-'):<13}{fmt_dur(dur):>12}{d.get('intentos','-'):>9}"
        )
        filas.append(
            {
                "etapa": e["nombre"],
                "estado": d.get("estado", "-"),
                "duracion_s": dur,
                "duracion": fmt_dur(dur),
                "intentos": d.get("intentos"),
                "inicio": d.get("inicio"),
                "fin": d.get("fin"),
            }
        )
    print("-" * 62)
    print(f"{'TOTAL (etapas con tiempo)':<37}{fmt_dur(total):>12}")
    print("-" * 62)
    try:
        import csv

        with open(
            DIR_OUT / "tiempos_etapas.csv", "w", newline="", encoding="utf-8"
        ) as fh:
            w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
            w.writeheader()
            w.writerows(filas)
        print(f"Tiempos guardados en: {DIR_OUT / 'tiempos_etapas.csv'}")
    except Exception:
        pass


def construir_args(acepta, g):
    a = []
    if "target" in acepta:
        a += ["--enfermedad", g.enfermedad] if g.enfermedad else ["--todas"]
    if "modelo" in acepta and g.modelo and g.modelo != "todos":
        a += ["--modelo", g.modelo]
    if "rapido" in acepta and g.rapido:
        a += ["--rapido"]
    if "skip" in acepta and not g.forzar:  # por defecto reanuda (salta lo hecho)
        a += ["--skip-existing"]
    return a


def correr_etapa(etapa, g, est):
    nombre, script = etapa["nombre"], etapa["script"]
    args = construir_args(etapa["acepta"], g)
    cmd = [sys.executable, script] + args
    logpath = DIR_LOG / f"{nombre}.log"

    print("\n" + "=" * 70)
    print(f">  ETAPA {nombre}   ({' '.join(cmd)})")
    print("=" * 70)
    est["etapas"].setdefault(nombre, {})
    est["etapas"][nombre].update(
        {
            "estado": "en_curso",
            "inicio": datetime.now().isoformat(timespec="seconds"),
            "intentos": est["etapas"][nombre].get("intentos", 0) + 1,
            "log": str(logpath),
        }
    )
    guardar_estado(est)

    t0 = time.time()
    # Forzar UTF-8 en el hijo y tolerar bytes no decodificables (Windows cp1252 -> ±, tildes)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["GRD_COHORTE"] = g.cohorte  # define la cohorte/target en todas las etapas
    with open(logpath, "w", encoding="utf-8") as lg:
        proc = subprocess.Popen(
            cmd,
            cwd=AQUI,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        for line in proc.stdout:
            print(line, end="")
            lg.write(line)
        proc.wait()
    rc = proc.returncode
    dur = time.time() - t0

    if rc == 0:
        est["etapas"][nombre].update(
            {
                "estado": "completado",
                "fin": datetime.now().isoformat(timespec="seconds"),
                "duracion_s": round(dur, 1),
                "error": None,
            }
        )
        guardar_estado(est)
        print(f"[OK] {nombre} completada en {fmt_dur(dur)}")
        return True

    # error
    est["etapas"][nombre].update(
        {
            "estado": "error",
            "fin": datetime.now().isoformat(timespec="seconds"),
            "duracion_s": round(dur, 1),
            "error": f"returncode {rc}",
        }
    )
    guardar_estado(est)
    cola = "".join(logpath.read_text(encoding="utf-8").splitlines(keepends=True)[-15:])
    print("\n" + "!" * 70)
    print(f"[ERROR] en la etapa: {nombre}  (returncode {rc})")
    print(f"   Log completo: {logpath}")
    print(f"   Últimas líneas:\n{cola}")
    print("!" * 70)
    return False


def main():
    ap = argparse.ArgumentParser(
        description="Orquestador del pipeline de modelado (play + reanudar)."
    )
    ap.add_argument(
        "--enfermedad",
        help="corre una sola enfermedad (si se omite y hay --todas, corre las 14)",
    )
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--modelo", default="todos")
    ap.add_argument(
        "--cohorte",
        default="primeras3",
        choices=["primeras3", "principal", "amplia"],
        help="definición de la cohorte/target: primeras3 (pos. 1-3), principal (pos. 1) "
        "o amplia (cualquiera de las 35). Se propaga a todas las etapas.",
    )
    ap.add_argument(
        "--rapido", action="store_true", help="búsqueda corta (prueba end-to-end)"
    )
    ap.add_argument(
        "--sin-shap", action="store_true", dest="sin_shap", help="omite la etapa SHAP"
    )
    ap.add_argument(
        "--sin-split",
        action="store_true",
        dest="sin_split",
        help="omite la etapa 07_split (úsalo si ya lo corriste aparte)",
    )
    ap.add_argument("--desde", help="empezar desde una etapa (nombre exacto)")
    ap.add_argument("--solo", help="correr solo una etapa (nombre exacto)")
    ap.add_argument(
        "--forzar", action="store_true", help="re-correr etapas ya completadas"
    )
    ap.add_argument(
        "--reiniciar",
        action="store_true",
        help="BORRA estado y artefactos previos para re-correr TODO desde cero "
        "(incluido el split; archiva antes con archivar_resultados.py)",
    )
    ap.add_argument(
        "--reiniciar-modelos",
        action="store_true",
        dest="reiniciar_modelos",
        help="como --reiniciar pero CONSERVA el split (07). Útil para re-correr solo el "
        "modelado al cambiar --cohorte, sin rehacer la partición.",
    )
    ap.add_argument("--continuar-con-errores", action="store_true", dest="continuar")
    g = ap.parse_args()
    if not g.todas and not g.enfermedad:
        g.todas = True  # por defecto, todo

    # --reiniciar / --reiniciar-modelos: borra artefactos para re-ejecutar. El segundo
    # CONSERVA el split (07), útil al solo cambiar --cohorte.
    if g.reiniciar or g.reiniciar_modelos:
        conserva_split = g.reiniciar_modelos and not g.reiniciar
        print(
            "REINICIO"
            + (" (conservando el split)" if conserva_split else "")
            + ": borrando estado y artefactos previos…"
        )
        for d in (
            DIR_OUT / "features",
            DIR_OUT / "tuning",
            DIR_OUT / "modelos",
            DIR_OUT / "metricas",
            DIR_OUT / "shap",
        ):
            if d.exists():
                shutil.rmtree(d)
                print(f"  borrado: {d.name}/")
        borrar = [
            RUTA_EST,
            DIR_OUT / "resumen_metricas.csv",
            DIR_OUT / "comparacion_modelos.json",
            DIR_OUT / "shap_resumen_top.csv",
            DIR_OUT / "tiempos_etapas.csv",
        ]
        if not conserva_split:
            borrar.append(RUTA_SPLIT)
        for f in borrar:
            if f.exists():
                f.unlink()
                print(f"  borrado: {f.name}")
        destino = "08_features (07 conservado)" if conserva_split else "07_split"
        print(f"  listo: el pipeline se ejecutará desde {destino}.\n")

    est = cargar_estado()
    est["cohorte"] = g.cohorte  # queda registrado en pipeline_estado.json
    guardar_estado(est)

    # Si el split ya existe (lo corriste aparte), márcalo completado -> se salta solo.
    if RUTA_SPLIT.exists() and not g.forzar:
        e07 = est["etapas"].setdefault("07_split", {})
        if e07.get("estado") != "completado":
            e07.update(
                {
                    "estado": "completado",
                    "nota": "split ya existía (hecho fuera del orquestador)",
                }
            )
            guardar_estado(est)
            print(
                f"07_split: '{RUTA_SPLIT.name}' ya existe -> se marca completado y se salta."
            )

    etapas = [
        e
        for e in ETAPAS
        if not (e.get("opcional") and g.sin_shap)
        and not (e["nombre"] == "07_split" and g.sin_split)
    ]
    nombres = [e["nombre"] for e in etapas]

    # ¿desde dónde arrancar?
    if g.solo:
        if g.solo not in nombres:
            raise SystemExit(f"--solo desconocido. Etapas: {nombres}")
        etapas = [e for e in etapas if e["nombre"] == g.solo]
    elif g.desde:
        if g.desde not in nombres:
            raise SystemExit(f"--desde desconocido. Etapas: {nombres}")
        etapas = etapas[nombres.index(g.desde) :]
    elif not g.forzar:
        # reanudar: primera etapa NO completada
        idx = 0
        for i, e in enumerate(etapas):
            if est["etapas"].get(e["nombre"], {}).get("estado") == "completado":
                idx = i + 1
            else:
                break
        if idx > 0:
            print(
                f"Reanudando: etapas completadas hasta '{etapas[idx-1]['nombre']}'. "
                f"Empiezo en '{etapas[idx]['nombre'] if idx < len(etapas) else '(nada, todo hecho)'}'."
            )
        etapas = etapas[idx:]

    if not etapas:
        print("Todo el pipeline ya está completado. Usa --forzar para re-correr.")
        return

    print(f"Pipeline a ejecutar: {[e['nombre'] for e in etapas]}")
    t0 = time.time()
    for e in etapas:
        ok = correr_etapa(e, g, est)
        if not ok and not g.continuar:
            resumen_tiempos(est)
            print(
                f"\nDetenido en '{e['nombre']}'. Corrige y vuelve a darle play "
                f"(reanuda desde aquí). Estado: {RUTA_EST}"
            )
            sys.exit(1)
    resumen_tiempos(est)
    print(
        f"\n[OK] Pipeline terminado (esta corrida: {fmt_dur(time.time()-t0)}). Estado: {RUTA_EST}"
    )
    print(f"    Resultados: {DIR_OUT}")


if __name__ == "__main__":
    main()
