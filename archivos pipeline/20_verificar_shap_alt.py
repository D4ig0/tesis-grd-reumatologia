# =============================================================================
# verificar_shap.py — Verificación de las atribuciones SHAP
# Autor: Diego Oliva López | USACH
#
# Comprueba la validez mecánica (aditividad, alineación, formato) de las 
# atribuciones SHAP calculadas sobre el conjunto de test para el mejor modelo.
# =============================================================================
from __future__ import annotations

import argparse
import json
import pickle

import joblib
import numpy as np

import _comun_alt as C


def _desempaqueta(modelo_repr):
    if isinstance(modelo_repr, bytes):
        return pickle.loads(modelo_repr)
    return modelo_repr


def _mejor_modelo(enf):
    metr = list(C.DIR_METR.glob(f"{enf}__*.json"))
    if not metr:
        return None
    mejores = []
    for f in metr:
        d = json.loads(f.read_text(encoding="utf-8"))
        mejores.append((d.get("PR_AUC", 0.0), d["modelo"]))
    return max(mejores)[1]


def verificar(enf, shap_n=2000, usar_guardado=False):
    import shap

    mod = _mejor_modelo(enf)
    if mod is None:
        print(f"[{enf}] sin métricas")
        return
    M = joblib.load(C.DIR_MOD / f"{enf}__{mod}.joblib")
    D = joblib.load(C.DIR_FEAT / f"{enf}.joblib")

    nombres = M["features"]
    X, es_tr = D["X"], D["es_tr"]
    Xte = X[~es_tr]
    muestra = Xte[:shap_n].toarray()
    m0 = _desempaqueta(M["modelos"][0])
    tipo = type(m0).__name__
    es_arbol_prob = tipo.startswith(("RandomForest", "ExtraTrees", "DecisionTree"))

    # (2) alineación
    alineado = (list(D["nombres"]) == list(nombres)) and (
        len(nombres) == muestra.shape[1]
    )

    # SHAP fresco o guardado
    expl = shap.TreeExplainer(m0)
    if usar_guardado:
        sv = np.load(C.DIR_SHAP / f"shap_{enf}_{mod}.npy")
        _ = expl(muestra[:1])
    else:
        sv = expl(muestra).values

    # (3) lista/3D -> clase positiva
    es_3d = sv.ndim == 3
    sv_pos = sv[..., 1] if es_3d else sv

    ev = np.array(expl.expected_value).ravel()
    ev_pos = float(ev[-1])  # clase positiva

    # (1) aditividad: RF en probabilidad, XGBoost/boosting en margen
    if es_arbol_prob:
        pred = m0.predict_proba(muestra)[:, 1]
    else:
        if M.get("modelo") == "xgboost":
            import xgboost as xgb

            booster = m0.get_booster()
            pred = booster.predict(xgb.DMatrix(muestra), output_margin=True)
        elif hasattr(m0, "decision_function"):
            pred = m0.decision_function(muestra).ravel()
        else:
            pred = m0.predict(muestra)

    recon = sv_pos.sum(axis=1) + ev_pos
    maxdiff = float(np.max(np.abs(recon - pred)))
    aditivo = bool(np.allclose(recon, pred, atol=1e-2))

    print(f"[{enf} / {mod}]  modo={M.get('modo')}")
    print(f"   (1) aditividad ....... {aditivo}   (maxdiff={maxdiff:.3g})")
    print(
        f"   (2) alineación ....... {alineado}   (n_nombres={len(nombres)}, n_cols_shap={sv_pos.shape[1]})"
    )
    print(
        f"   (3) forma SHAP ....... {'3D (se tomó clase positiva)' if es_3d else '2D'}"
    )
    print(
        f"   (+) expected_value ... {ev_pos:.4f}  (prob base ~ {1/(1+np.exp(-ev_pos)):.3f} si es margen logit)"
    )
    print(f"   (+) calculado sobre .. TEST (n={muestra.shape[0]} de {Xte.shape[0]})")
    ok = aditivo and alineado
    print(f"   => VEREDICTO: {'SHAP VÁLIDO' if ok else 'REVISAR (ver falla arriba)'}\n")
    return ok


def main():
    ap = argparse.ArgumentParser(
        description="Verificación de atribuciones SHAP (B4/10.2)."
    )
    ap.add_argument("--enfermedad")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--shap-n", type=int, default=2000, dest="shap_n")
    ap.add_argument(
        "--usar-guardado",
        action="store_true",
        dest="usar_guardado",
        help="valida el .npy serializado en vez de recalcular en fresco",
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
    resultados = {}
    for enf in enfs:
        try:
            resultados[enf] = verificar(enf, args.shap_n, args.usar_guardado)
        except Exception as e:
            print(f"[{enf}] ERROR: {e!r}\n")
            resultados[enf] = None
    ok = sum(1 for v in resultados.values() if v)
    print(f"Resumen: {ok}/{len(resultados)} enfermedades con SHAP válido.")


if __name__ == "__main__":
    main()
