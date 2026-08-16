# =============================================================================
# 07 — MODELADO · PASO 1: PARTICIÓN train/test + VALIDACIÓN CRUZADA
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Qué hace este script (y SOLO esto):
#   1. Carga la etiqueta y el id de paciente desde el pre-encoding.
#   2. Parte train/test 80/20, AL AZAR (no por año), ESTRATIFICADO y POR PACIENTE.
#   3. Verifica que ningún paciente quede en ambos lados y que la proporción de
#      reumatológicos se conserve.
#   4. Define la validación cruzada (StratifiedGroupKFold) DENTRO de train.
#   5. Guarda la partición (split_train_test.parquet) para que TODOS los pasos
#      siguientes usen exactamente la misma división.
#
# Precauciones (ver PRECAUCIONES_modelado.md): aquí NO se binariza, NO se selecciona,
# NO se imputa ni se balancea. Todo eso se hace DESPUÉS, SOLO sobre train.
# =============================================================================

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.model_selection import StratifiedGroupKFold

# ── Rutas ────────────────────────────────────────────────────────────────────
# Este script vive en CLAUDE/modelado/. El preprocesamiento (05) escribió en
# CLAUDE/output/, es decir, en la carpeta hermana. Se ancla a la ubicación del
# script (no al directorio de trabajo) para que funcione desde donde se ejecute.
#   · Si mueves este script a CODIGOS/MODELADO/, cambia DIR_PREP a:
#     AQUI.parent / "PREPROCESAMIENTO" / "CLAUDE" / "output"
AQUI = Path(__file__).resolve().parent
DIR_PREP = AQUI.parent / "output"  # salida del preprocesamiento (05)
RUTA_BASE = DIR_PREP / "datos_preprocesados.parquet"  # pre-encoding (trae id_paciente)
RUTA_SPLIT = DIR_PREP / "split_train_test.parquet"  # salida de este script

# ── Parámetros ───────────────────────────────────────────────────────────────
TEST_FRAC = 0.20  # 20% test  → n_splits = 5 (un fold = test)
N_FOLDS_CV = 5  # folds de validación cruzada DENTRO de train
SEED = 42
COL_LABEL = "grupo_paciente"
COL_GROUP = "id_paciente"
POSITIVO = "Reumatológico"  # clase de interés (contraste principal reum vs general)

# ── 1. Cargar solo lo necesario para partir (liviano) ────────────────────────
tb = pq.read_table(RUTA_BASE, columns=[COL_LABEL, COL_GROUP]).to_pandas()
n = len(tb)
y = (tb[COL_LABEL].astype(str) == POSITIVO).astype(int).values
print(f"Filas: {n:,} | positivos ({POSITIVO}): {y.sum():,} ({y.mean()*100:.2f}%)")

# Grupos = paciente. Los id nulos/marcador NO se pueden agrupar: a cada uno se le
# asigna un grupo único (id negativo) para que jamás compartan lado (evita fuga).
gid = tb[COL_GROUP].astype("string")
es_nulo = gid.isna() | gid.str.strip().str.upper().isin(
    ["", "NA", "NONE", "NULL", "SIN INFORMACIÓN", "SIN INFORMACION", "DESCONOCIDO"]
)
groups = gid.fillna("NA").astype("category").cat.codes.to_numpy().astype(np.int64)
groups[es_nulo.to_numpy()] = -(np.arange(es_nulo.sum()) + 1)  # únicos negativos
print(
    f"Pacientes distintos (grupos): {len(np.unique(groups)):,} | filas con id nulo: {es_nulo.sum():,}"
)

# ── 2. Split train/test: estratificado + por paciente ────────────────────────
# StratifiedGroupKFold con 5 folds → el primer fold es el TEST (~20%), estratificado
# y sin partir pacientes. El resto es train.
sgkf = StratifiedGroupKFold(
    n_splits=int(round(1 / TEST_FRAC)), shuffle=True, random_state=SEED
)
train_idx, test_idx = next(sgkf.split(np.zeros(n), y, groups))
split = np.array(["train"] * n, dtype=object)
split[test_idx] = "test"

# ── 3. Verificaciones (precauciones) ─────────────────────────────────────────
g_train, g_test = set(groups[train_idx]), set(groups[test_idx])
solapan = g_train & g_test
print("\n=== VERIFICACIÓN DEL SPLIT ===")
print(
    f"Train: {len(train_idx):,} filas ({len(train_idx)/n*100:.1f}%) | reum {y[train_idx].mean()*100:.2f}%"
)
print(
    f"Test : {len(test_idx):,} filas ({len(test_idx)/n*100:.1f}%) | reum {y[test_idx].mean()*100:.2f}%"
)
print(f"Pacientes compartidos entre train y test: {len(solapan)}  (debe ser 0)")
assert len(solapan) == 0, "FUGA: hay pacientes en train y test a la vez."

# ── 4. Validación cruzada DENTRO de train (para selección/ajuste sin fuga) ────
cv = StratifiedGroupKFold(n_splits=N_FOLDS_CV, shuffle=True, random_state=SEED)
print(
    f"\nValidación cruzada en train: {N_FOLDS_CV} folds (StratifiedGroupKFold, grupo=paciente)"
)
for k, (tr, va) in enumerate(
    cv.split(np.zeros(len(train_idx)), y[train_idx], groups[train_idx]), 1
):
    print(
        f"  fold {k}: train {len(tr):,} | val {len(va):,} | reum val {y[train_idx][va].mean()*100:.2f}%"
    )

# ── 5. Guardar la partición (misma para todos los pasos siguientes) ──────────
out = pd.DataFrame(
    {
        "row_id": np.arange(n),
        "split": split,
        "id_paciente": tb[COL_GROUP].astype(str).values,
        "grupo": groups,
        "y_reum": y,
    }
)
out.to_parquet(RUTA_SPLIT, index=False)
print(f"\nPartición guardada en: {RUTA_SPLIT}")

# =============================================================================
# PRÓXIMOS PASOS (script 08, en esta misma carpeta modelado/) — TODO sobre TRAIN:
#   a) Binarizar los códigos/categorías CRUDOS (DIAGNOSTICO*, PROCEDIMIENTO*,
#      ESPECIALIDAD_MEDICA, SERVICIOINGRESO, TIPO_PROCEDENCIA):
#      · decidir qué códigos/categorías entran usando SOLO la frecuencia en TRAIN
#        (piso de validez), y aplicar esa MISMA lista a test.
#   b) Selección: chi² de cada candidata vs. objetivo → ordenar por p-value → top-N.
#   c) Balanceo: bootstrapping balanceado (solo train).
#   d) Modelos: regresión logística / random forest / XGBoost → consenso.
#   e) Evaluar en test (una sola vez).
#   El diseño uno-contra-resto por enfermedad se corre repitiendo b) por objetivo.
# =============================================================================
