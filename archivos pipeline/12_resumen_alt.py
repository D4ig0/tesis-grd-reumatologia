# =============================================================================
# 12_resumen.py — ETAPA: consolidación de métricas + comparación de modelos
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Qué hace: junta todas las métricas (10) en una tabla, y por enfermedad compara los
# modelos con Wilcoxon pareado sobre PR-AUC por fold. No entrena nada; solo agrega.
#
# Artefactos: resultados_modelado/resumen_metricas.csv
#             resultados_modelado/comparacion_modelos.json
#
# USO:  python 12_resumen.py
# =============================================================================
from __future__ import annotations

import json

import pandas as pd
from scipy.stats import wilcoxon

import _comun_alt as C


def main():
    filas, folds_por = [], {}
    for f in sorted(C.DIR_METR.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        enf, mod = d["enfermedad"], d["modelo"]
        filas.append(
            {
                "enfermedad": enf,
                "modelo": mod,
                "PR_AUC": d.get("PR_AUC"),
                "PR_AUC_ic95": d.get("PR_AUC_ic95"),
                "AUC_ROC": d.get("AUC_ROC"),
                "AUC_ROC_ic95": d.get("AUC_ROC_ic95"),
                "F1": d.get("F1"),
                "Precision": d.get("Precision"),
                "Recall": d.get("Recall"),
                "brier": d.get("brier"),
                "umbral": d.get("umbral_elegido"),
                "n_test": d.get("n_test"),
                "n_pos_test": d.get("n_pos_test"),
                "cv_PR_AUC_media": d.get("cv_PR_AUC_media"),
                "modo": d.get("modo_entrenamiento"),
            }
        )
        folds_por.setdefault(enf, {})[mod] = d.get("cv_PR_AUC_folds")

    if not filas:
        raise SystemExit(
            "No hay métricas en resultados_modelado/metricas/. Corre 10_entrenar_evaluar."
        )

    df = pd.DataFrame(filas).sort_values(
        ["enfermedad", "PR_AUC"], ascending=[True, False]
    )
    df.to_csv(C.DIR_OUT / "resumen_metricas.csv", index=False)

    # Wilcoxon pareado entre modelos, por enfermedad (sobre PR-AUC por fold)
    comparaciones = {}
    for enf, dmods in folds_por.items():
        nombres = [m for m in dmods if dmods[m]]
        for i in range(len(nombres)):
            for j in range(i + 1, len(nombres)):
                a, b = nombres[i], nombres[j]
                va, vb = dmods[a], dmods[b]
                if va and vb and len(va) == len(vb) and len(va) >= 2:
                    try:
                        stat, p = wilcoxon(va, vb)
                        comparaciones[f"{enf}: {a}_vs_{b}"] = {
                            "wilcoxon_stat": float(stat),
                            "p_value": float(p),
                            "dif_media_PR_AUC": float(
                                pd.Series(va).mean() - pd.Series(vb).mean()
                            ),
                        }
                    except Exception as e:
                        comparaciones[f"{enf}: {a}_vs_{b}"] = {"error": str(e)}
    (C.DIR_OUT / "comparacion_modelos.json").write_text(
        json.dumps(comparaciones, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Resumen: {len(df)} filas -> {C.DIR_OUT/'resumen_metricas.csv'}")
    print(f"Comparación de modelos -> {C.DIR_OUT/'comparacion_modelos.json'}")
    print("\nTop por enfermedad (mejor PR-AUC):")
    print(
        df.groupby("enfermedad")
        .head(1)[["enfermedad", "modelo", "PR_AUC", "AUC_ROC", "F1"]]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
