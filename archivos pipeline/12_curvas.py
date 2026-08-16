# =============================================================================
# 12_curvas.py — Curvas ROC y PR + matrices de confusión para el anexo (M15 / §11)
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Qué hace: para cada enfermedad toma su MEJOR modelo (mayor PR-AUC), recalcula las
# probabilidades en el conjunto de TEST y genera:
#   - figuras/curvas_roc.png       (ROC de las enfermedades útiles, superpuestas)
#   - figuras/curvas_pr.png        (PR de las enfermedades útiles, superpuestas)
#   - figuras/confusion_<enf>.png  (matriz de confusión por enfermedad, umbral guardado)
# No reentrena nada: reutiliza features (08) y modelos (10) ya guardados.
#
# USO:  python 12_curvas.py                 # solo las 5 con desempeño útil
#       python 12_curvas.py --todas         # las 14
# =============================================================================
from __future__ import annotations

import argparse
import json

import joblib
import matplotlib
import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import _comun_alt as C

# Las cinco con desempeño útil (mayor PR-AUC); se priorizan por espacio.
UTILES = [
    "artrosis_osteoartritis",
    "lupus_eritematoso_sistemico",
    "vasculitis",
    "fibromialgia",
    "gota",
]
NOMBRE = {
    "artrosis_osteoartritis": "Artrosis / osteoartritis",
    "lupus_eritematoso_sistemico": "Lupus",
    "vasculitis": "Vasculitis",
    "fibromialgia": "Fibromialgia",
    "gota": "Gota",
    "artritis_idiopatica_juvenil": "AIJ",
    "uveitis": "Uveítis",
    "miositis": "Miositis",
    "artritis_reumatoide": "Artritis reumatoide",
    "sindrome_de_sjogren": "Sjögren",
    "artritis_psoriasica": "A. psoriásica",
    "esclerodermia": "Esclerodermia",
    "sindrome_de_raynaud": "Raynaud",
    "espondilitis_anquilosante": "Espondilitis",
}
USACH = ["#EA7600", "#00A499", "#C8102E", "#498BCA", "#8C4799", "#EAAA00", "#333F48"]
FIG = C.DIR_MOD.parent / "figuras"
FIG.mkdir(parents=True, exist_ok=True)


def mejor_modelo(enf):
    """Modelo con mayor PR-AUC en test para la enfermedad, según los JSON de métricas."""
    mejor, prmax = None, -1.0
    for f in C.DIR_METR.glob(f"{enf}__*.json"):
        m = json.loads(f.read_text(encoding="utf-8"))
        if float(m.get("PR_AUC", 0)) > prmax:
            prmax, mejor = float(m["PR_AUC"]), (
                f.stem.split("__")[1],
                float(m.get("umbral_elegido", 0.5)),
            )
    return mejor


def datos_test(enf, modelo):
    D = joblib.load(C.DIR_FEAT / f"{enf}.joblib")
    M = joblib.load(C.DIR_MOD / f"{enf}__{modelo}.joblib")
    yte = D["y"][~D["es_tr"]]
    p_te = C.proba_ensamble(M["modelos"], D["X"][~D["es_tr"]])
    return yte, p_te, float(M.get("umbral", 0.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--todas", action="store_true")
    args = ap.parse_args()
    enfs = list(NOMBRE) if args.todas else UTILES

    datos = {}
    for enf in enfs:
        mm = mejor_modelo(enf)
        if not mm:
            print(f"  [{enf}] sin métricas; omitida")
            continue
        modelo, _ = mm
        datos[enf] = (modelo, *datos_test(enf, modelo))

    # --- ROC superpuestas ---
    plt.figure(figsize=(6.4, 5.2))
    for i, (enf, (modelo, yte, p_te, thr)) in enumerate(datos.items()):
        fpr, tpr, _ = roc_curve(yte, p_te)
        plt.plot(
            fpr,
            tpr,
            color=USACH[i % len(USACH)],
            lw=1.8,
            label=f"{NOMBRE[enf]} (AUC={roc_auc_score(yte, p_te):.3f})",
        )
    plt.plot([0, 1], [0, 1], "--", color="#b0b7c3", lw=1)
    plt.xlabel("Tasa de falsos positivos")
    plt.ylabel("Tasa de verdaderos positivos")
    plt.title("Curvas ROC")
    plt.legend(fontsize=8, loc="lower right")
    plt.tight_layout()
    plt.savefig(FIG / "curvas_roc.png", dpi=200)
    plt.close()

    # --- PR superpuestas ---
    plt.figure(figsize=(6.4, 5.2))
    for i, (enf, (modelo, yte, p_te, thr)) in enumerate(datos.items()):
        prec, rec, _ = precision_recall_curve(yte, p_te)
        plt.plot(
            rec,
            prec,
            color=USACH[i % len(USACH)],
            lw=1.8,
            label=f"{NOMBRE[enf]} (PR-AUC={average_precision_score(yte, p_te):.3f})",
        )
    plt.xlabel("Exhaustividad (recall)")
    plt.ylabel("Precisión")
    plt.title("Curvas de precisión-exhaustividad")
    plt.legend(fontsize=8, loc="upper right")
    plt.tight_layout()
    plt.savefig(FIG / "curvas_pr.png", dpi=200)
    plt.close()

    # --- Matrices de confusión ---
    n = len(datos)
    cols = min(3, n)
    filas = int(np.ceil(n / cols))
    fig, axes = plt.subplots(filas, cols, figsize=(3.2 * cols, 3.0 * filas))
    axes = np.atleast_1d(axes).ravel()
    for ax, (enf, (modelo, yte, p_te, thr)) in zip(axes, datos.items()):
        cm = confusion_matrix(yte, (p_te >= thr).astype(int))
        ax.imshow(cm, cmap="Oranges")
        for (r, c), v in np.ndenumerate(cm):
            ax.text(
                c,
                r,
                f"{v:,}".replace(",", "."),
                ha="center",
                va="center",
                color="white" if v > cm.max() / 2 else "#333F48",
                fontsize=9,
            )
        ax.set_title(f"{NOMBRE[enf]} (umbral {thr:.2f})", fontsize=9)
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["No", "Sí"])
        ax.set_yticklabels(["No", "Sí"])
        ax.set_xlabel("Predicho")
        ax.set_ylabel("Real")
    for ax in axes[n:]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(FIG / "confusion_matrices.png", dpi=200)
    plt.close(fig)

    print(f"Guardado en: {FIG}")
    print("  curvas_roc.png | curvas_pr.png | confusion_matrices.png")


if __name__ == "__main__":
    main()
