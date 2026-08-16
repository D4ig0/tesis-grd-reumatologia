# =============================================================================
# estabilidad_atributos.py — Estabilidad de atributos entre modelos (B8, criterio c)
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# El criterio (c) de la hipótesis exige que las variables relevantes sean estables
# e interpretables entre modelos. Este script lo CUANTIFICA por enfermedad:
#   (i)  Índice de Jaccard entre los 20 atributos principales de la regresión
#        logística, el random forest y XGBoost (solapamiento de los top-20).
#   (ii) Correlación de rangos de Spearman entre las importancias de cada par de
#        modelos, sobre el conjunto de atributos comparable.
#
# Umbral declarado a priori: un atributo/orden se considera estable si el Jaccard
# medio entre modelos es >= 0,50 y el Spearman medio es >= 0,60. Por debajo, la
# enfermedad se marca como de perfil inestable y se reporta como tal.
#
# Nota: la corrida canónica entrena un modelo por enfermedad con ponderación de
# clases (sin réplicas de bootstrap), de modo que la estabilidad "entre iteraciones"
# se sustituye por la estabilidad "entre familias de modelos", que es la que sostiene
# el criterio (c) de forma auditable.
#
# Salida: resultados_modelado/estabilidad_atributos.csv
# USO:  python estabilidad_atributos.py [--top 20]
# =============================================================================
from __future__ import annotations

import argparse
import pickle

import _comun_alt as C
import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

MODELOS = ["regresion_logistica", "random_forest", "xgboost"]


def desempaqueta(m):
    return pickle.loads(m) if isinstance(m, bytes) else m


def importancias(enf, modelo):
    art = C.DIR_MOD / f"{enf}__{modelo}.joblib"
    if not art.exists():
        return None
    M = joblib.load(art)
    m = desempaqueta(M["modelos"][0])
    feats = list(M["features"])
    if hasattr(m, "coef_"):
        imp = np.abs(np.ravel(m.coef_))
    elif hasattr(m, "feature_importances_"):
        imp = np.asarray(m.feature_importances_, dtype=float)
    else:
        return None
    n = min(len(feats), len(imp))
    return dict(zip(feats[:n], imp[:n]))


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else np.nan


def main():
    ap = argparse.ArgumentParser(
        description="Estabilidad de atributos entre modelos (B8)."
    )
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    filas = []
    for enf in C.enfermedades_todas():
        imps = {mo: importancias(enf, mo) for mo in MODELOS}
        if any(v is None for v in imps.values()):
            continue
        tops = {
            mo: [f for f, _ in sorted(v.items(), key=lambda t: -t[1])[: args.top]]
            for mo, v in imps.items()
        }
        # Jaccard de los top-N entre pares
        j = {
            "LR-RF": jaccard(tops["regresion_logistica"], tops["random_forest"]),
            "LR-XGB": jaccard(tops["regresion_logistica"], tops["xgboost"]),
            "RF-XGB": jaccard(tops["random_forest"], tops["xgboost"]),
        }

        # Spearman de importancias sobre atributos comunes
        def sp(a, b):
            comunes = sorted(set(imps[a]) & set(imps[b]))
            if len(comunes) < 5:
                return np.nan
            va = [imps[a][f] for f in comunes]
            vb = [imps[b][f] for f in comunes]
            return spearmanr(va, vb).correlation

        s = {
            "LR-RF": sp("regresion_logistica", "random_forest"),
            "LR-XGB": sp("regresion_logistica", "xgboost"),
            "RF-XGB": sp("random_forest", "xgboost"),
        }
        j_mean = np.nanmean(list(j.values()))
        s_mean = np.nanmean(list(s.values()))
        estable = (j_mean >= 0.50) and (s_mean >= 0.60)
        filas.append(
            {
                "enfermedad": enf,
                "jaccard_LR_RF": round(j["LR-RF"], 2),
                "jaccard_LR_XGB": round(j["LR-XGB"], 2),
                "jaccard_RF_XGB": round(j["RF-XGB"], 2),
                "jaccard_medio": round(j_mean, 2),
                "spearman_LR_RF": round(s["LR-RF"], 2),
                "spearman_LR_XGB": round(s["LR-XGB"], 2),
                "spearman_RF_XGB": round(s["RF-XGB"], 2),
                "spearman_medio": round(s_mean, 2),
                "estable": estable,
            }
        )
    out = pd.DataFrame(filas).sort_values("jaccard_medio", ascending=False)
    dest = C.DIR_OUT / "estabilidad_atributos.csv"
    out.to_csv(dest, index=False)
    print(out.to_string(index=False))
    print(f"\nGuardado: {dest}")


if __name__ == "__main__":
    main()
