# =============================================================================
# _comun.py — funciones y configuración compartidas por el pipeline de modelado
# Caracterización de pacientes reumatológicos con GRD y ML
# Autor: Diego Oliva López | USACH
#
# Este módulo NO se ejecuta solo: lo importan 08_features, 09_tuning,
# 10_entrenar_evaluar, 11_shap y 12_resumen. Concentra la lógica (vocab, chi²,
# balanceo, tuning, métricas) para que cada etapa sea delgada y sin duplicación.
#
# REGLA DE ORO (anti-fuga): lo que APRENDE de los datos (vocab, chi², OHE,
# hiperparámetros, umbral) se ajusta SOLO en train. El test se toca una vez, al final.
# Seed fijo (SEED) => reproducibilidad.
# =============================================================================

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import sparse
from scipy.stats import loguniform, randint, uniform
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import chi2
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    RandomizedSearchCV,
    StratifiedGroupKFold,
    cross_val_predict,
    cross_validate,
)

warnings.filterwarnings("ignore")

# XGBoost y SHAP son opcionales.
try:
    from xgboost import XGBClassifier

    HAY_XGB = True
except Exception:
    HAY_XGB = False
try:
    import shap  # noqa: F401

    HAY_SHAP = True
except Exception:
    HAY_SHAP = False

# ── Rutas y carpetas de artefactos ───────────────────────────────────────────
AQUI = Path(__file__).resolve().parent
DIR_PREP = AQUI.parent / "output"
RUTA_BASE = DIR_PREP / "datos_preprocesados.parquet"
RUTA_SPLIT = DIR_PREP / "split_train_test.parquet"

DIR_OUT = AQUI / "resultados_modelado_alt"  # raíz de resultados ALT
DIR_FEAT = (
    AQUI / "resultados_modelado" / "features"
)  # se reutilizan las features originales
DIR_TUN = (
    AQUI / "resultados_modelado" / "tuning"
)  # se reutilizan los hiperparámetros originales
DIR_MOD = DIR_OUT / "modelos"  # 10_entrenar_evaluar
DIR_METR = DIR_OUT / "metricas"  # 10_entrenar_evaluar
DIR_SHAP = DIR_OUT / "shap"  # 11_shap
DIR_LOG = DIR_OUT / "logs"  # logs por etapa
RUTA_ESTADO = DIR_OUT / "pipeline_estado.json"
for _d in (DIR_OUT, DIR_FEAT, DIR_TUN, DIR_MOD, DIR_METR, DIR_SHAP, DIR_LOG):
    _d.mkdir(parents=True, exist_ok=True)

SEED = 42
LABEL = "grupo_paciente"
POSITIVO = "Reumatológico"

# C2 — definición de la cohorte y de los targets. Se lee de la variable de entorno
# GRD_COHORTE (la fija el orquestador con --cohorte); por defecto "primeras3". Opciones:
#   "principal": enfermedad reumática en el diagnóstico principal (posición 1, "por" estricto).
#   "primeras3": enfermedad reumática en las 3 primeras posiciones (cohorte de estudio, "por").
#   "amplia":    enfermedad presente en cualquiera de las 35 posiciones ("con").
COHORTE = os.environ.get("GRD_COHORTE", "primeras3").strip().lower()

# ── Roles de columnas (DICCIONARIO_datos_modelado.md) ─────────────────────────
# C4: n_hosp_previas y dias_desde_ult_hosp NO son features (sesgadas por el re-cifrado
# del id entre 2020 y 2021). reingreso_30d es desenlace, con censura de bordes en 05.
FEAT_NUM = [
    "edad",
    "n_diagnosticos",
    "n_procedimientos",
    "n_traslados",
    "IR_29301_PESO",
    "IR_29301_SEVERIDAD",
    "IR_29301_MORTALIDAD",
]
FEAT_BIN = [
    "sexo",
    "nacionalidad_chilena",
    "etnia_originario",
    "flag_pabellon",
    "flag_intervencion",
    "flag_cambio_servicio",
]
FEAT_CAT = ["TIPO_INGRESO", "TIPO_ACTIVIDAD", "TIPOALTA", "PREVISION", "region"]
COLS_DIAG = [f"DIAGNOSTICO{i}" for i in range(1, 36)]
COLS_PROC = [f"PROCEDIMIENTO{i}" for i in range(1, 31)]
COLS_CAT_ALTA = ["ESPECIALIDAD_MEDICA", "SERVICIOINGRESO", "TIPO_PROCEDENCIA"]
REUM_COLS = [
    "reum_artritis_reumatoide",
    "reum_lupus_eritematoso_sistemico",
    "reum_espondilitis_anquilosante",
    "reum_sindrome_de_sjogren",
    "reum_artritis_psoriasica",
    "reum_esclerodermia",
    "reum_vasculitis",
    "reum_artrosis_osteoartritis",
    "reum_fibromialgia",
    "reum_gota",
    "reum_uveitis",
    "reum_miositis",
    "reum_sindrome_de_raynaud",
    "reum_artritis_idiopatica_juvenil",
]

MODELOS_VALIDOS = ["regresion_logistica", "random_forest"] + (
    ["xgboost"] if HAY_XGB else []
)

# Códigos CIE (con comentarios) para la exclusión anti-fuga.
sys.path.insert(0, str(AQUI))
try:
    from codigos_cie import CODIGOS_REUMATICOS
except Exception:
    CODIGOS_REUMATICOS = {}


def enfermedades_todas():
    return [c.replace("reum_", "") for c in REUM_COLS]


def norm_code_series(s: pd.Series) -> pd.Series:
    return s.astype("string").str.upper().str.replace(".", "", regex=False).str.strip()


def norm_set(codes) -> set:
    return {c.upper().replace(".", "").strip() for c in codes}


# ── Carga de la cohorte + split (una sola vez, en 08_features) ────────────────
def cargar_cohorte():
    if not RUTA_SPLIT.exists():
        raise SystemExit(
            f"Falta {RUTA_SPLIT.name}: corre primero 07_modelado_split.py."
        )
    split = pd.read_parquet(RUTA_SPLIT)
    pac2split = (
        split.drop_duplicates("id_paciente").set_index("id_paciente")["split"].to_dict()
    )
    cols = (
        ["id_paciente", LABEL]
        + FEAT_NUM
        + FEAT_BIN
        + FEAT_CAT
        + COLS_DIAG
        + COLS_PROC
        + COLS_CAT_ALTA
        + REUM_COLS
    )
    cols = [c for c in cols if c in pq.ParquetFile(RUTA_BASE).schema_arrow.names]
    base = pq.read_table(
        RUTA_BASE, columns=cols, filters=[(LABEL, "=", POSITIVO)]
    ).to_pandas()
    base["split"] = base["id_paciente"].astype(str).map(pac2split)
    base = base[base["split"].isin(["train", "test"])].copy()

    # C2: si la cohorte es "primeras3", se REDEFINEN cohorte y targets sobre las
    # posiciones diagnósticas 1-3 (a partir de DIAGNOSTICO1-3 y CODIGOS_REUMATICOS).
    # Se sobrescriben las columnas reum_<enf> (any-position) con la versión primeras-3,
    # de modo que target, comorbilidades reum y cohorte quedan todas en primeras-3.
    if COHORTE in ("primeras3", "principal"):
        n_pos = 3 if COHORTE == "primeras3" else 1
        cols_p = [
            f"DIAGNOSTICO{i}"
            for i in range(1, n_pos + 1)
            if f"DIAGNOSTICO{i}" in base.columns
        ]
        d = [norm_code_series(base[c]) for c in cols_p]
        en = pd.Series(False, index=base.index)
        for enf in enfermedades_todas():
            cs = norm_set(CODIGOS_REUMATICOS.get(enf, []))
            pres = pd.Series(False, index=base.index)
            for di in d:
                pres = pres | di.isin(cs)
            base[f"reum_{enf}"] = pres.astype(
                "int8"
            )  # sobrescribe any-position -> posiciones 1..n_pos
            en = en | pres
        base = base[en].copy()  # cohorte = enfermedad reumática en pos. 1..n_pos
    # COHORTE == "amplia": se mantiene la definición por cualquier posición (sin cambios)
    return base


# ── Construcción de features (aprende en train, aplica a ambos) ───────────────
def _presencia(df, cols, vocab):
    idx = {c: j for j, c in enumerate(vocab)}
    fil, col = [], []
    for c in cols:
        m = norm_code_series(df[c]).map(idx)
        ok = m.notna().values
        fil.append(np.nonzero(ok)[0])
        col.append(m.values[ok].astype(int))
    if fil and sum(len(f) for f in fil):
        fi = np.concatenate(fil)
        co = np.concatenate(col)
        M = sparse.csr_matrix(
            (np.ones(len(fi), np.int8), (fi, co)), shape=(len(df), len(vocab))
        )
        M.data[:] = 1
        return M
    return sparse.csr_matrix((len(df), len(vocab)), dtype=np.int8)


def _vocab_frecuente(df_tr, cols, piso, excluir=None):
    excluir = excluir or set()
    conteo = {}
    for c in cols:
        vc = norm_code_series(df_tr[c]).dropna()
        for code, n in vc[vc != ""].value_counts().items():
            if code not in excluir:
                conteo[code] = conteo.get(code, 0) + int(n)
    return sorted([c for c, n in conteo.items() if n >= piso])


def construir_features(base, enfermedad, piso_frec, drop_sev=False):
    target = f"reum_{enfermedad}"
    df = base
    y = df[target].astype(int).values
    es_tr = (df["split"] == "train").values
    df_tr = df[es_tr]

    feat_num = [
        c
        for c in FEAT_NUM
        if not (drop_sev and c in ("IR_29301_SEVERIDAD", "IR_29301_MORTALIDAD"))
    ]
    Xnum = df[feat_num].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    Xbin = df[FEAT_BIN].apply(pd.to_numeric, errors="coerce").fillna(0).values
    ohe, ohe_names = [], []
    for c in FEAT_CAT:
        cats = pd.Index(df_tr[c].astype("string").dropna().unique())
        d = pd.get_dummies(df[c].astype("string"), prefix=c).reindex(
            columns=[f"{c}_{v}" for v in cats], fill_value=0
        )
        ohe.append(d.values.astype(np.int8))
        ohe_names += list(d.columns)
    Xseg = sparse.csr_matrix(np.hstack([Xnum, Xbin] + ohe))
    nombres_seg = feat_num + FEAT_BIN + ohe_names

    excluir = norm_set(CODIGOS_REUMATICOS.get(enfermedad, []))
    voc_d = _vocab_frecuente(df_tr, COLS_DIAG, piso_frec, excluir)
    voc_p = _vocab_frecuente(df_tr, COLS_PROC, piso_frec)
    Md = _presencia(df, COLS_DIAG, voc_d)
    Mp = _presencia(df, COLS_PROC, voc_p)
    cat_M, cat_names = [], []
    for c in COLS_CAT_ALTA:
        vc = df_tr[c].astype("string").value_counts()
        cats = vc[vc >= piso_frec].index
        d = pd.get_dummies(df[c].astype("string"), prefix=c).reindex(
            columns=[f"{c}_{v}" for v in cats], fill_value=0
        )
        cat_M.append(sparse.csr_matrix(d.values.astype(np.int8)))
        cat_names += list(d.columns)
    otras = [c for c in REUM_COLS if c != target]
    Mr = sparse.csr_matrix(df[otras].fillna(0).astype(np.int8).values)

    Xalta = sparse.hstack([Md, Mp] + cat_M + [Mr], format="csr")
    nombres_alta = np.array(
        voc_d + [f"proc_{p}" for p in voc_p] + cat_names + otras, dtype=object
    )
    grupos = df["id_paciente"].astype("category").cat.codes.values
    return dict(
        Xseg=Xseg,
        nombres_seg=nombres_seg,
        Xalta=Xalta,
        nombres_alta=nombres_alta,
        y=y,
        es_tr=es_tr,
        grupos=grupos,
        target=target,
    )


def top_n_chi2(Xalta, y, es_tr, nombres_alta, top_n):
    chi, pval = chi2(Xalta[es_tr], y[es_tr])
    chi = np.nan_to_num(chi, nan=0.0)
    orden = np.argsort(chi)[::-1][:top_n]
    ranking = pd.DataFrame(
        {"feature": nombres_alta[orden], "chi2": chi[orden], "p_value": pval[orden]}
    )
    return orden, ranking


# ── Modelos, balanceo, tuning ────────────────────────────────────────────────
def espacios(spw):
    esp = {
        "regresion_logistica": (
            LogisticRegression(
                solver="liblinear",
                class_weight="balanced",
                max_iter=2000,
                random_state=SEED,
            ),
            {"C": loguniform(1e-3, 1e2), "penalty": ["l1", "l2"]},
        ),
        "random_forest": (
            RandomForestClassifier(
                class_weight="balanced_subsample", n_jobs=-1, random_state=SEED
            ),
            {
                "n_estimators": randint(150, 400),
                "max_depth": [None, 10, 20, 30],
                "max_features": ["sqrt", "log2"],
                "min_samples_leaf": randint(1, 20),
            },
        ),
    }
    if HAY_XGB:
        esp["xgboost"] = (
            XGBClassifier(
                tree_method="hist",
                eval_metric="logloss",
                n_jobs=-1,
                random_state=SEED,
                scale_pos_weight=spw,
            ),
            {
                "n_estimators": randint(200, 500),
                "max_depth": randint(3, 8),
                "learning_rate": loguniform(1e-2, 3e-1),
                "subsample": uniform(0.6, 0.4),
                "colsample_bytree": uniform(0.6, 0.4),
            },
        )
    return esp


def balancear_train(Xtr, ytr, gtr, cap_pos, ratio, seed=SEED, boot_pos=False):
    r = np.random.default_rng(seed)
    pos = np.where(ytr == 1)[0]
    neg = np.where(ytr == 0)[0]
    n_pos = min(len(pos), cap_pos)
    n_neg = min(len(neg), int(ratio * n_pos))
    ip = r.choice(pos, size=n_pos, replace=boot_pos)
    ineg = r.choice(neg, size=n_neg, replace=(len(neg) < n_neg))
    idx = np.concatenate([ip, ineg])
    r.shuffle(idx)
    return Xtr[idx], ytr[idx], gtr[idx]


def tunear(est, params, Xtr, ytr, gtr, n_iter, cv_folds, scoring="average_precision"):
    n_pos = int(ytr.sum())
    folds = max(2, min(cv_folds, n_pos))
    cv = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=SEED)
    rs = RandomizedSearchCV(
        est,
        params,
        n_iter=n_iter,
        scoring=scoring,
        cv=cv,
        n_jobs=-1,
        random_state=SEED,
        refit=True,
        error_score=0.0,
    )
    rs.fit(Xtr, ytr, groups=gtr)
    return rs.best_estimator_, rs.best_params_, float(rs.best_score_)


def cv_por_fold(est, X, y, g, cv_folds):
    folds = max(2, min(cv_folds, int(y.sum())))
    cv = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=SEED)
    res = cross_validate(
        est,
        X,
        y,
        groups=g,
        cv=cv,
        scoring=["average_precision", "roc_auc"],
        n_jobs=-1,
        error_score=0.0,
    )
    return res["test_average_precision"], res["test_roc_auc"]


def umbral_por_validacion(est, X, y, g, cv_folds):
    folds = max(2, min(cv_folds, int(y.sum())))
    cv = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=SEED)
    p = cross_val_predict(
        est, X, y, groups=g, cv=cv, method="predict_proba", n_jobs=-1
    )[:, 1]
    ths = np.linspace(0.05, 0.95, 19)
    f1s = [f1_score(y, (p >= t).astype(int), zero_division=0) for t in ths]
    return float(ths[int(np.argmax(f1s))])


def entrenar_final(best_est, Xtr, ytr, gtr, n_pos, umbral_estable, cap, ratio, k_boot):
    import pickle

    from sklearn.base import clone

    # NUEVA LÓGICA (ALT): No se balancea, se entrena directamente sobre Xtr y ytr
    # asumiendo que best_est (ej. XGBoost) ya viene con scale_pos_weight = prevalencia_real
    m = clone(best_est).fit(Xtr, ytr)
    return [pickle.dumps(m)], "completo_con_pesos"


def proba_ensamble(modelos, X):
    import pickle

    probs = []
    for m_bytes in modelos:
        m = pickle.loads(m_bytes)
        probs.append(m.predict_proba(X)[:, 1])
        del m  # Libera RAM después de predecir
    return np.mean(probs, axis=0)


def evaluar(y, p, umbral=0.5):
    yhat = (p >= umbral).astype(int)
    return {
        "AUC_ROC": float(roc_auc_score(y, p)),
        "PR_AUC": float(average_precision_score(y, p)),
        "Precision": float(precision_score(y, yhat, zero_division=0)),
        "Recall": float(recall_score(y, yhat, zero_division=0)),
        "F1": float(f1_score(y, yhat, zero_division=0)),
        "matriz_confusion": confusion_matrix(y, yhat).tolist(),
        "n_test": int(len(y)),
        "n_pos_test": int(y.sum()),
    }


def ic_bootstrap(y, p, fn, n=500, seed=SEED):
    r = np.random.default_rng(seed)
    vals = []
    idx = np.arange(len(y))
    for _ in range(n):
        s = r.choice(idx, size=len(idx), replace=True)
        if 0 < y[s].sum() < len(s):
            vals.append(fn(y[s], p[s]))
    if not vals:
        return [None, None]
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return [float(lo), float(hi)]
