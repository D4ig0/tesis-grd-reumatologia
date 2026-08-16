# =============================================================================
# MÓDULO 05 — PREPROCESAMIENTO GRD CHILE 2019–2024  
# Caracterización de Pacientes Reumatológicos
# Autor: Diego Oliva López | USACH
# Fecha  : 2026-06-24
#
# Entrada: output/datos_consolidados_etiquetados.parquet  (generado por 02)
# Salida : output/datos_preprocesados.parquet      (pre-encoding, para Módulo 06)
#          output/datos_preprocesados_ohe.parquet   (post-encoding, para modelos)
#          output/log_preprocesamiento.txt
#
paquetes <- c(
  "arrow", "dplyr", "tidyr", "lubridate", "stringr",
  "forcats", "purrr", "readr", "data.table"
)
faltantes <- paquetes[!sapply(paquetes, requireNamespace, quietly = TRUE)]
if (length(faltantes) > 0) {
  install.packages(faltantes, repos = "https://cloud.r-project.org")
}
invisible(lapply(paquetes, library, character.only = TRUE))

source("_codigos_cie.R") # define: CODIGOS_REUMATICOS, TODOS_LOS_CODIGOS
CODIGOS_UPPER <- toupper(TODOS_LOS_CODIGOS)

# ── 1. CONSTANTES ────────────────────────────────────────────────────────────
DIR_OUT <- "output"
RUTA_ENTRADA <- file.path(DIR_OUT, "datos_consolidados_etiquetados.parquet")
RUTA_SALIDA_BASE <- file.path(DIR_OUT, "datos_preprocesados.parquet")
RUTA_SALIDA_OHE <- file.path(DIR_OUT, "datos_preprocesados_ohe.parquet")
RUTA_LOG <- file.path(DIR_OUT, "log_preprocesamiento.txt")

if (!file.exists(RUTA_ENTRADA)) {
  stop("No se encontró '", RUTA_ENTRADA, "'. Ejecuta primero el Módulo 02.")
}

log_lines <- character(0)
log_add <- function(...) {
  msg <- paste0("[", format(Sys.time(), "%H:%M:%S"), "] ", paste0(...))
  message(msg)
  log_lines <<- c(log_lines, msg)
}

log_add("========== INICIO PREPROCESAMIENTO v2 ==========")
df <- arrow::read_parquet(RUTA_ENTRADA)
n_filas_orig <- nrow(df)
n_cols_orig <- ncol(df)
log_add(
  "Dataset cargado: ", format(n_filas_orig, big.mark = "."),
  " filas × ", n_cols_orig, " columnas"
)


# =============================================================================
# ETAPA 0 — NORMALIZACIÓN UNIVERSAL DE STRINGS  
# Sin esto, la cardinalidad observada está inflada por duplicados sucios
# ("OTRO" vs "OTRO ") y el OHE genera columnas redundantes.
# =============================================================================
log_add("----- ETAPA 0: Normalización universal de texto -----")

normalizar_txt <- function(x) {
  x <- as.character(x)
  x <- stringr::str_trim(x) # quita espacios extremos
  x <- stringr::str_squish(x) # colapsa espacios internos
  x <- toupper(x) # unifica mayúsculas (mantiene tildes)
  x <- dplyr::if_else(x %in% c("", "NULL", "NA", "NaN", "."), NA_character_, x)
  x
}

# OJO: las fechas se normalizan pero NO se mandan a NA aquí; se parsean en Etapa 2.
cols_char <- names(df)[sapply(df, is.character)]
cols_fecha <- intersect(c(
  "FECHA_NACIMIENTO", "FECHA_INGRESO",
  "FECHAALTA", "FECHAINTERV1"
), names(df))
cols_norm <- setdiff(cols_char, cols_fecha)
df <- df |>
  dplyr::mutate(dplyr::across(dplyr::all_of(cols_norm), normalizar_txt))
# Fechas: solo trim, sin upper ni NA (se manejan en parseo)
df <- df |>
  dplyr::mutate(dplyr::across(
    dplyr::all_of(cols_fecha),
    ~ stringr::str_trim(as.character(.))
  ))
log_add(
  "Normalizadas ", length(cols_norm), " columnas de texto. ",
  "ETNIA 'OTRO'/'OTRO ' y NINGUNO/NINGUNA quedan fusionadas."
)


# =============================================================================
# ETAPA 1 — LIMPIEZA DE REGISTROS + ELIMINACIÓN ESTRUCTURAL
# =============================================================================
log_add("----- ETAPA 1: Limpieza de registros y eliminaciones -----")

# ── 1-LIMPIEZA: registros duplicados + filas vacías ──────────────────────────
# Saneamiento inicial estándar, ANTES de eliminar identificadores (para poder
# deduplicar por episodio real). Se ejecuta tras la normalización (Etapa 0), de
# modo que variantes sucias ("OTRO " vs "OTRO") ya no impiden detectar duplicados.
n_ini <- nrow(df)

# (a) Registros duplicados: mismo episodio del MISMO paciente identificado por
#     ID_PACIENTE + fecha ingreso + fecha alta + diagnóstico principal (+ hospital).
#     ⚠ La clave DEBE incluir el identificador de paciente: sin él, pacientes
#     distintos con mismo hospital+fechas+diagnóstico se colapsarían como falsos
#     duplicados (probado: sin ID marcaría 10,7% vs 0,1% real). Solo se deduplica
#     entre filas con ID válido; las de ID nulo se conservan (no comparables).
key_cols <- intersect(c(
  "ID_PACIENTE", "FECHA_INGRESO", "FECHAALTA",
  "DIAGNOSTICO1", "COD_HOSPITAL"
), names(df))
if ("ID_PACIENTE" %in% key_cols && length(key_cols) >= 3) {
  id_txt <- toupper(stringr::str_trim(as.character(df$ID_PACIENTE)))
  id_ok <- !is.na(df$ID_PACIENTE) &
    !(id_txt %in% c("", "NA", "NONE", "NULL", "SIN INFORMACIÓN", "DESCONOCIDO"))
  dup <- logical(nrow(df))
  dup[id_ok] <- duplicated(df[id_ok, key_cols, drop = FALSE])
  df <- df[!dup, , drop = FALSE]
  log_add(
    "1-LIMPIEZA duplicados: ", format(sum(dup), big.mark = "."),
    " registros duplicados eliminados (clave: ", paste(key_cols, collapse = "+"), ")"
  )
} else {
  log_add("1-LIMPIEZA duplicados: OMITIDO (sin ID_PACIENTE, evita falsos positivos)")
}

# (b) Filas completamente vacías (todos los campos NA tras la normalización).
vacias <- rowSums(!is.na(df)) == 0
if (any(vacias)) {
  df <- df[!vacias, , drop = FALSE]
  log_add("1-LIMPIEZA filas vacías: ", format(sum(vacias), big.mark = "."), " eliminadas")
}
log_add(
  "1-LIMPIEZA total: ", format(n_ini, big.mark = "."), " → ",
  format(nrow(df), big.mark = "."), " filas (",
  format(n_ini - nrow(df), big.mark = "."), " eliminadas)"
)

# NOTA — inconsistencias de rango/fecha (edad, duración, alta<ingreso): se manejan
# a nivel de VALOR (→ NA) en la Etapa 2, conservando la fila (sus otros campos
# pueden ser válidos). Para ELIMINAR la fila con alta<ingreso, poner el flag
# DROP_FECHA_INCONSISTENTE <- TRUE (ver Etapa 2).

elim <- function(df, cols, etiqueta) {
  c2 <- intersect(cols, names(df))
  df <- df |> dplyr::select(-dplyr::all_of(c2))
  log_add("  ", etiqueta, " (", length(c2), " cols)")
  df
}
# ID_PACIENTE NO se elimina aquí: se usa en Etapa 2 para derivar reingresos
# (enlazando hospitalizaciones del mismo paciente) y se elimina después.
df <- elim(
  df, c(
    "CIP_ENCRIPTADO", "ID_BENEFICIARIO",
    "MEDICOINTERV1_ENCRIPTADO", "MEDICOALTA_ENCRIPTADO"
  ),
  "1A Identificadores (ID_PACIENTE se conserva para reingresos)"
)
df <- elim(df, c(
  paste0("CONDICIONDEALTANEONATO", 1:4), paste0("PESORN", 1:4),
  paste0("SEXORN", 1:4), paste0("RN", 1:4, "ESTADO")
), "1B Neonatal")
# 1C-bis Derivar n_traslados ANTES de eliminar (nº de servicios de traslado no nulos).
# Proxy de complejidad del episodio: 17.2% tuvo >=1 traslado (distribución 0-9).
COLS_STRAS <- intersect(paste0("SERVICIOTRASLADO", 1:9), names(df))
if (length(COLS_STRAS) > 0) {
  df$n_traslados <- rowSums(!is.na(df[, COLS_STRAS, drop = FALSE]), na.rm = TRUE)
  log_add(
    "1C-bis n_traslados derivada: ", round(mean(df$n_traslados > 0) * 100, 1),
    "% con >=1 traslado"
  )
}


df <- elim(df, paste0("FECHATRASLADO", 1:9), "1C Fechas traslado")
df <- elim(df, paste0("SERVICIOTRASLADO", 1:9), "1D Servicios traslado")
# FECHAPROCEDIMIENTO1: ~100% NA y los pocos valores son corruptos (RUTs tipo
# "7001546-3", no fechas). Inservible → eliminar.
df <- elim(df, "FECHAPROCEDIMIENTO1", "1E FechaProc1 (100% NA + corrupta)")
df <- elim(df, "HOSPPROCEDENCIA", "1F HospProcedencia (88% NA)")
# PROVINCIA NO se elimina aquí: se deriva `region` en Etapa 2 (mapeo a 16 regiones).
df <- elim(
  df, c("SERVICIO_SALUD", "COMUNA", "COD_HOSPITAL"),
  "1G Geográficas triviales (V<0.10)"
)
# NOTA: IR_29301_PESO NO se elimina. Su "99.91% NA" en v1 era un artefacto de
# parseo: usa coma decimal ("0,4384") y as.numeric() la convertía toda en NA.
# Se recupera en Etapa 2 (5.808.446 de 5.808.536 valores válidos; V=0.39, Mediano).
log_add("ETAPA 1 completada. Columnas: ", ncol(df))


# =============================================================================
# ETAPA 2 — FEATURE ENGINEERING  (derivar ANTES de borrar fuentes)
# =============================================================================
log_add("----- ETAPA 2: Feature engineering -----")

# Parseo robusto de fechas: 2023 viene en dd-mm-yyyy; resto en yyyy-mm-dd.
# Estrategia: intentar ymd; donde falle, intentar dmy. Recupera ~18% de NA.
parse_fecha <- function(x) {
  d <- suppressWarnings(lubridate::ymd(x))
  falla <- is.na(d) & !is.na(x) & x != ""
  d[falla] <- suppressWarnings(lubridate::dmy(x[falla]))
  d
}

# 2A edad
df <- df |>
  dplyr::mutate(
    .fn  = parse_fecha(FECHA_NACIMIENTO),
    .fi  = parse_fecha(FECHA_INGRESO),
    edad = as.numeric(difftime(.fi, .fn, units = "days")) / 365.25,
    edad = dplyr::if_else(edad < 0 | edad > 120, NA_real_, edad)
  ) |>
  dplyr::select(-.fn, -.fi)
log_add("2A edad: NA = ", round(mean(is.na(df$edad)) * 100, 1), "% (antes ~18%)")

# 2B duracion_hospitalizacion
DROP_FECHA_INCONSISTENTE <- FALSE # TRUE = eliminar filas con alta<ingreso (como el antecedente)
df <- df |>
  dplyr::mutate(
    .fi = parse_fecha(FECHA_INGRESO),
    .fa = parse_fecha(FECHAALTA),
    duracion_hospitalizacion = as.numeric(difftime(.fa, .fi, units = "days"))
  )
# Cuantificar inconsistencias ANTES de mandarlas a NA (para el informe de limpieza)
n_neg <- sum(df$duracion_hospitalizacion < 0, na.rm = TRUE) # alta < ingreso
n_rang <- sum(df$duracion_hospitalizacion > 730, na.rm = TRUE) # estadía > 2 años
log_add(
  "2B inconsistencias fechas: alta<ingreso = ", format(n_neg, big.mark = "."),
  " | duración>730d = ", format(n_rang, big.mark = ".")
)
if (DROP_FECHA_INCONSISTENTE) {
  malas <- !is.na(df$duracion_hospitalizacion) & df$duracion_hospitalizacion < 0
  df <- df[!malas, , drop = FALSE]
  log_add("2B filas con alta<ingreso ELIMINADAS: ", format(sum(malas), big.mark = "."))
}
df <- df |>
  dplyr::mutate(
    duracion_hospitalizacion = dplyr::if_else(
      duracion_hospitalizacion < 0 | duracion_hospitalizacion > 730,
      NA_real_, duracion_hospitalizacion
    )
  ) |>
  dplyr::select(-.fi, -.fa)
log_add("2B duracion: NA = ", round(mean(is.na(df$duracion_hospitalizacion)) * 100, 1), "%")

# ── 2B-ter REINGRESOS (derivar ANTES de eliminar ID_PACIENTE y fechas) ────────
# Enlaza hospitalizaciones del mismo paciente (ID_PACIENTE) ordenadas por fecha.
# Costo: ~ordenamiento + agrupado (segundos). Marcadores de ID → NA (no enlazables).
#   n_hosp_previas       : nº de hospitalizaciones previas del paciente (0 = primera)
#   es_reingreso         : 1 si tuvo al menos una hospitalización previa
#   reingreso_30d        : 1 si ingresó ≤30 días tras el alta anterior (readmisión clásica)
#   dias_desde_ult_hosp  : días entre el alta previa y este ingreso (NA si es la 1ª)
# NOTA DE ROL: reingreso_30d/es_reingreso son DESENLACES (outcomes). Se conservan en
# el dataset; en el análisis de reingreso pasan a 'y' (no a X). Ver DICCIONARIO/ AUDITORIA.
if ("ID_PACIENTE" %in% names(df)) {
  id_clean <- toupper(stringr::str_trim(as.character(df$ID_PACIENTE)))
  id_clean[id_clean %in% c("SIN INFORMACIÓN", "DESCONOCIDO", "NULL", "NONE", "", "NA")] <- NA
  hlp <- data.table::data.table(
    .row = seq_len(nrow(df)),
    id   = id_clean,
    ing  = parse_fecha(df$FECHA_INGRESO),
    alta = parse_fecha(df$FECHAALTA)
  )
  data.table::setorder(hlp, id, ing, na.last = TRUE)
  hlp[, n_prev := seq_len(.N) - 1L, by = id]
  hlp[, prev_alta := data.table::shift(alta), by = id]
  hlp[, dias := as.integer(ing - prev_alta)]
  hlp[, re30 := as.integer(!is.na(dias) & dias >= 0 & dias <= 30)]
  hlp[is.na(id), c("n_prev", "re30") := NA]
  data.table::setorder(hlp, .row) # restaurar orden original
  # NOTA: es_reingreso se descarta por redundancia — equivale a (n_hosp_previas > 0).
  df$n_hosp_previas <- hlp$n_prev
  df$reingreso_30d <- hlp$re30
  df$dias_desde_ult_hosp <- hlp$dias
  rm(hlp)
  invisible(gc())
  log_add(
    "2B-ter Reingresos: reingreso_30d ",
    round(mean(df$reingreso_30d == 1, na.rm = TRUE) * 100, 1),
    "% | n_hosp_previas media ", round(mean(df$n_hosp_previas, na.rm = TRUE), 2)
  )

  # ── Censura de bordes del reingreso  ────────────────
  # JUSTIFICACIÓN: el identificador se re-cifra en la fuente entre 2020 y 2021
  # (verificado en verificaciones/v01-v07), por lo que el enlace por paciente solo es
  # válido DENTRO de cada bloque ({2019,2020} y {2021-2024}). En los bordes de cada
  # bloque no hay 30 días de ventana observables dentro del mismo bloque, de modo que
  # un reingreso_30d = 0 ahí sería "por construcción" y no ausencia real (censura a la
  # derecha por fin de bloque; a la izquierda por inicio de bloque). Se CENSURA (NA) el
  # indicador en los 30 días iniciales y finales de cada bloque y se declara el período
  # de calentamiento en el escrito. reingreso_30d SÍ se conserva (evento de ventana
  # corta, válido dentro de bloque); n_hosp_previas y dias_desde_ult_hosp se descartan
  # del modelo (ver COLS_EXCLUIR_MODELO): son acumuladas y se reinician en el corte.
  if (all(c("anio", "FECHA_INGRESO") %in% names(df))) {
    .ing <- parse_fecha(df$FECHA_INGRESO)
    .blk <- ifelse(suppressWarnings(as.integer(df$anio)) <= 2020L, "A", "B")
    n_cens <- 0L
    for (b in c("A", "B")) {
      idx <- which(.blk == b & !is.na(.ing))
      if (length(idx)) {
        dmin <- min(.ing[idx])
        dmax <- max(.ing[idx])
        cens <- idx[.ing[idx] < (dmin + 30) | .ing[idx] > (dmax - 30)]
        if (length(cens)) {
          df$reingreso_30d[cens] <- NA_integer_
          n_cens <- n_cens + length(cens)
        }
      }
    }
    log_add(
      "2B-ter Censura de bordes reingreso: ", n_cens,
      " episodios -> NA (30 días iniciales/finales de cada bloque; obs. profesor C4)"
    )
  }
}
# ID_PACIENTE se CONSERVA como clave de grupo para el split por paciente en el
# modelado (StratifiedGroupKFold). NO es feature: va como control, fuera de la matriz.
if ("ID_PACIENTE" %in% names(df)) df$id_paciente <- as.character(df$ID_PACIENTE)
df <- df |> dplyr::select(-dplyr::any_of("ID_PACIENTE"))

df <- df |> dplyr::select(-dplyr::any_of(
  c("FECHA_NACIMIENTO", "FECHA_INGRESO", "FECHAALTA", "FECHAINTERV1")
))

# 2B-bis IR_29301_PESO → numérico con coma decimal ("0,4384" → 0.4384)
# Recupera la variable de mayor señal (V=0.39). Solo ~90 NA reales.
if ("IR_29301_PESO" %in% names(df)) {
  df$IR_29301_PESO <- suppressWarnings(
    as.numeric(stringr::str_replace(df$IR_29301_PESO, ",", "."))
  )
  log_add(
    "2B-bis IR_29301_PESO → numérico (coma→punto). NA reales: ",
    sum(is.na(df$IR_29301_PESO))
  )
}

# 2C n_diagnosticos (conteo de comorbilidad — feature legítima, NO usa códigos reum)
COLS_DIAG <- intersect(paste0("DIAGNOSTICO", 1:35), names(df))
df$n_diagnosticos <- rowSums(!is.na(df[, COLS_DIAG, drop = FALSE]), na.rm = TRUE)
log_add("2C n_diagnosticos: media = ", round(mean(df$n_diagnosticos), 2))

# 2D tipo_reum — SOLO para caracterización (Módulo 06). EXCLUIDA del modelo.
# ⚠ LEAKAGE: tipo_reum reconstruye la etiqueta (SIN_REUM ⟺ no reumatológico).
#   Se conserva en el dataset pre-encoding pero NUNCA entra al OHE / a X.
es_reum_code <- function(x) {
  toupper(stringr::str_trim(as.character(x))) %in% CODIGOS_UPPER &
    !is.na(x) & x != ""
}
diag1_reum <- es_reum_code(df[["DIAGNOSTICO1"]])
COLS_DIAG_SEC <- setdiff(COLS_DIAG, "DIAGNOSTICO1")
diag_sec_reum <- rowSums(sapply(COLS_DIAG_SEC, function(c) es_reum_code(df[[c]])),
  na.rm = TRUE
) > 0
df$tipo_reum <- dplyr::case_when(
  diag1_reum ~ "DIAG_PRINCIPAL",
  diag_sec_reum ~ "DIAG_SECUNDARIO",
  TRUE ~ "SIN_REUM"
)
log_add(
  "2D tipo_reum (solo caracterización, EXCLUIDA del modelo): ",
  paste(capture.output(table(df$tipo_reum)), collapse = " | ")
)

# 2D-bis enfermedades reumatológicas MULTI-HOT — un paciente puede tener VARIAS.
# Se crea una binaria por cada una de las 15 enfermedades (reum_<grupo>) marcando
# 1 si CUALQUIER diagnóstico del episodio pertenece a ese grupo → NO se pierde
# ninguna enfermedad concurrente. Más:
#   · enfermedad_principal  = grupo del DIAGNOSTICO1 (diagnóstico principal)
#   · n_enfermedades_reum   = nº de enfermedades reumatológicas distintas
# Todo deriva de los códigos de la etiqueta → CARACTERIZACIÓN, EXCLUIR-MODELO.
code2group <- unlist(lapply(names(CODIGOS_REUMATICOS), function(g) {
  setNames(
    rep(g, length(CODIGOS_REUMATICOS[[g]])),
    toupper(stringr::str_trim(CODIGOS_REUMATICOS[[g]]))
  )
}))
code2group <- code2group[!duplicated(names(code2group))]
map_grupo <- function(x) unname(code2group[toupper(stringr::str_trim(as.character(x)))])
grupos_diag <- lapply(COLS_DIAG, function(c) map_grupo(df[[c]])) # 35 vectores
mat_grupos <- do.call(cbind, grupos_diag) # n × 35

COLS_ENF_REUM <- character(0)
for (g in names(CODIGOS_REUMATICOS)) {
  nm <- paste0("reum_", g)
  df[[nm]] <- as.integer(rowSums(mat_grupos == g, na.rm = TRUE) > 0)
  COLS_ENF_REUM <- c(COLS_ENF_REUM, nm)
}
df$n_enfermedades_reum <- rowSums(df[, COLS_ENF_REUM, drop = FALSE])
df$enfermedad_principal <- map_grupo(df[["DIAGNOSTICO1"]]) # grupo del dx principal
log_add(
  "2D-bis multi-hot enfermedades reum: ", length(COLS_ENF_REUM),
  " binarias. Máx enfermedades en un episodio: ", max(df$n_enfermedades_reum),
  " | con >1 enfermedad: ", sum(df$n_enfermedades_reum > 1)
)

# 
# =============================================================================
# 2D-ter DIAGNÓSTICOS: perfil por capítulo (descriptivo) — SIN binarizar por código
# ── CAMBIO (evitar fuga de datos): la binarización de comorbilidades por código
#    (comorb_<CODIGO>) SE ELIMINA de aquí. Elegir "cuáles códigos" por su frecuencia
#    en TODO el dataset usa información del test → sería fuga. Esa binarización y su
#    selección chi² top-N se hacen en el MODELADO, sobre TRAIN, a partir de las
#    columnas DIAGNOSTICO1-35 CRUDAS (que ahora se CONSERVAN, ver abajo).
#    Aquí solo se deja dxcap_<capitulo>: es un mapeo POR FILA (el capítulo de un
#    código es fijo, no se "aprende" del dataset) y es puramente DESCRIPTIVO (OE3).
# =============================================================================

# --- perfil grueso por capítulo CIE-10 (presencia, DESCRIPTIVO — no del modelo) ---
cap_diag <- function(x) {
  L <- toupper(substr(stringr::str_trim(as.character(x)), 1, 1))
  dplyr::case_when(
    is.na(L) | L == "" ~ NA_character_,
    L %in% c("A", "B") ~ "INFECCIOSO",
    L %in% c("C", "D") ~ "NEO_HEMATO",
    L == "E" ~ "ENDOCRINO_METABOLICO",
    L == "F" ~ "SALUD_MENTAL",
    L == "G" ~ "NERVIOSO",
    L %in% c("H") ~ "OJO_OIDO",
    L == "I" ~ "CARDIOVASCULAR",
    L == "J" ~ "RESPIRATORIO",
    L == "K" ~ "DIGESTIVO",
    L == "L" ~ "PIEL",
    L == "M" ~ "MUSCULOESQUELETICO",
    L == "N" ~ "GENITOURINARIO",
    L == "O" ~ "OBSTETRICO",
    L == "P" ~ "PERINATAL",
    L == "Q" ~ "CONGENITO",
    L == "R" ~ "SINTOMAS_HALLAZGOS",
    L %in% c("S", "T") ~ "TRAUMA_ENVENENAMIENTO",
    L %in% c("V", "W", "X", "Y") ~ "CAUSAS_EXTERNAS",
    L == "Z" ~ "FACTORES_SALUD",
    TRUE ~ "OTROS_DX"
  )
}
mat_cap <- do.call(cbind, lapply(COLS_DIAG, function(c) cap_diag(df[[c]])))
CAPS_DX <- c(
  "INFECCIOSO", "NEO_HEMATO", "ENDOCRINO_METABOLICO", "SALUD_MENTAL", "NERVIOSO",
  "OJO_OIDO", "CARDIOVASCULAR", "RESPIRATORIO", "DIGESTIVO", "PIEL",
  "MUSCULOESQUELETICO", "GENITOURINARIO", "OBSTETRICO", "PERINATAL", "CONGENITO",
  "SINTOMAS_HALLAZGOS", "TRAUMA_ENVENENAMIENTO", "CAUSAS_EXTERNAS", "FACTORES_SALUD"
)
for (a in CAPS_DX) df[[paste0("dxcap_", a)]] <- as.integer(rowSums(mat_cap == a, na.rm = TRUE) > 0)
rm(mat_cap)
invisible(gc())
log_add("2D-ter Perfil por capítulo CIE-10 (descriptivo): ", length(CAPS_DX), " presencias (dxcap_*)")

# Los DIAGNOSTICO1-35 CRUDOS se CONSERVAN (antes se eliminaban): el modelado los
# binariza por código y selecciona por chi² top-N, todo sobre TRAIN (sin fuga).

# 2E n_procedimientos + perfil por ÁREA anatómica (CIE-9-MC)
# Los códigos son CIE-9-MC (ej. "76.1"); la parte entera define el capítulo/área.
# Se cuenta cuántos procedimientos de cada área tuvo el episodio → conserva el
# perfil procedimental completo sin explotar a miles de columnas OHE.
# Son features LEGÍTIMAS del modelo (no derivan de la etiqueta).
COLS_PROC <- intersect(paste0("PROCEDIMIENTO", 1:30), names(df))
df$n_procedimientos <- rowSums(!is.na(df[, COLS_PROC, drop = FALSE]), na.rm = TRUE)

# cap_proc(): SECCIONES OFICIALES CIE-9-MC (Vol. 3). Los dos primeros dígitos del
# código determinan la sección → agrupación por TAXONOMÍA EXTERNA OFICIAL, no por un
# criterio del investigador. Es el equivalente en procedimientos a dxcap_ (capítulos
# CIE-10 de la OMS). Los rangos NO se subdividen ni se reagrupan: se respetan tal cual
# los define la clasificación (única forma de que la agrupación sea defendible).
cap_proc <- function(x) {
  n <- floor(suppressWarnings(as.numeric(x)))
  dplyr::case_when(
    is.na(n) ~ NA_character_,
    n == 0 ~ "PROC_NEC", # 00  Procedimientos NEC
    n >= 1 & n <= 5 ~ "SISTEMA_NERVIOSO", # 01-05
    n >= 6 & n <= 7 ~ "SISTEMA_ENDOCRINO", # 06-07
    n >= 8 & n <= 16 ~ "OJO", # 08-16
    n == 17 ~ "OTROS_DIAG_TERAPEUTICOS", # 17
    n >= 18 & n <= 20 ~ "OIDO", # 18-20
    n >= 21 & n <= 29 ~ "NARIZ_BOCA_FARINGE", # 21-29 (incl. dental)
    n >= 30 & n <= 34 ~ "SISTEMA_RESPIRATORIO", # 30-34
    n >= 35 & n <= 39 ~ "SISTEMA_CARDIOVASCULAR", # 35-39
    n >= 40 & n <= 41 ~ "SISTEMA_HEMOLINFATICO", # 40-41
    n >= 42 & n <= 54 ~ "SISTEMA_DIGESTIVO", # 42-54
    n >= 55 & n <= 59 ~ "SISTEMA_URINARIO", # 55-59
    n >= 60 & n <= 64 ~ "GENITAL_MASCULINO", # 60-64
    n >= 65 & n <= 71 ~ "GENITAL_FEMENINO", # 65-71
    n >= 72 & n <= 75 ~ "OBSTETRICOS", # 72-75
    n >= 76 & n <= 84 ~ "SISTEMA_MUSCULOESQUELETICO", # 76-84
    n >= 85 & n <= 86 ~ "TEGUMENTARIO", # 85-86
    n >= 87 & n <= 99 ~ "DIAG_TERAPEUTICOS_MISC", # 87-99
    TRUE ~ NA_character_
  )
}
mat_cap <- do.call(cbind, lapply(COLS_PROC, function(c) cap_proc(df[[c]])))
CAPS_PROC <- c(
  "PROC_NEC", "SISTEMA_NERVIOSO", "SISTEMA_ENDOCRINO", "OJO",
  "OTROS_DIAG_TERAPEUTICOS", "OIDO", "NARIZ_BOCA_FARINGE",
  "SISTEMA_RESPIRATORIO", "SISTEMA_CARDIOVASCULAR", "SISTEMA_HEMOLINFATICO",
  "SISTEMA_DIGESTIVO", "SISTEMA_URINARIO", "GENITAL_MASCULINO",
  "GENITAL_FEMENINO", "OBSTETRICOS", "SISTEMA_MUSCULOESQUELETICO",
  "TEGUMENTARIO", "DIAG_TERAPEUTICOS_MISC"
)
# PRESENCIA (multi-hot) por sección oficial: mapeo POR FILA (la sección de un código
# es fija) → DESCRIPTIVO (OE3), no del modelo. No se "aprende" nada del dataset.
for (a in CAPS_PROC) df[[paste0("proccap_", a)]] <- as.integer(rowSums(mat_cap == a, na.rm = TRUE) > 0)
rm(mat_cap)
invisible(gc())

# --- PROCEDIMIENTOS INDIVIDUALES: SE BINARIZAN EN EL MODELADO (sobre TRAIN) ---
# ── CAMBIO (evitar fuga): la binarización por código (proccod_<CODIGO>) y su
#    selección chi² top-N SE ELIMINAN de aquí. Elegir "cuáles códigos" por frecuencia
#    en todo el dataset usa información del test → fuga. Se hace en el MODELADO, sobre
#    TRAIN, a partir de las columnas PROCEDIMIENTO1-30 CRUDAS (que ahora se CONSERVAN).
log_add(
  "2E procedimientos: n_procedimientos (media ", round(mean(df$n_procedimientos), 2),
  ") + ", length(CAPS_PROC), " secciones CIE-9-MC descriptivas (proccap_*). ",
  "Códigos crudos conservados para binarizar en el modelado (sobre train)."
)

# 2F flag_pabellon (la señal está en el hecho, no en la magnitud: r=0.010)
if ("USOSPABELLON" %in% names(df)) {
  usos <- suppressWarnings(as.numeric(df$USOSPABELLON))
  df$flag_pabellon <- as.integer(!is.na(usos) & usos > 0)
  df <- df |> dplyr::select(-USOSPABELLON)
  log_add("2F flag_pabellon: ", round(mean(df$flag_pabellon) * 100, 1), "% con pabellón")
}

# 2G flag_intervencion + ELIMINAR ESPECIALIDADINTERVENCION
# El 44.8% NA de ESPECIALIDADINTERVENCION es informativo (= sin cirugía) → se
# resume en flag_intervencion (1 = hubo cirugía). Además, verificado en Módulo 06,
# ESPECIALIDADINTERVENCION tiene V de Cramér = 0,83 con ESPECIALIDAD_MEDICA (cuando
# hay cirugía, la especialidad que opera suele ser la misma que la de cabecera):
# es redundante. Se conserva ESPECIALIDAD_MEDICA + flag_intervencion, y se ELIMINA
# ESPECIALIDADINTERVENCION (evita ~10 columnas OHE casi duplicadas y su 55% de NA).
if ("ESPECIALIDADINTERVENCION" %in% names(df)) {
  df$flag_intervencion <- as.integer(!is.na(df$ESPECIALIDADINTERVENCION))
  df <- df |> dplyr::select(-ESPECIALIDADINTERVENCION)
  log_add(
    "2G flag_intervencion: ", round(mean(df$flag_intervencion) * 100, 1),
    "% con intervención. ESPECIALIDADINTERVENCION eliminada (V=0,83 con ESPECIALIDAD_MEDICA)"
  )
}

# 2H flag_cambio_servicio (captura el 15.5% de info no redundante entre
#    SERVICIOINGRESO y SERVICIOALTA, evitando un OHE completo de SERVICIOALTA)
if (all(c("SERVICIOINGRESO", "SERVICIOALTA") %in% names(df))) {
  df$flag_cambio_servicio <- as.integer(
    !is.na(df$SERVICIOINGRESO) & !is.na(df$SERVICIOALTA) &
      df$SERVICIOINGRESO != df$SERVICIOALTA
  )
  df <- df |> dplyr::select(-SERVICIOALTA) # se reemplaza por el flag
  log_add(
    "2H flag_cambio_servicio: ", round(mean(df$flag_cambio_servicio) * 100, 1),
    "% cambió de servicio. SERVICIOALTA eliminada (84.5% redundante)."
  )
}
log_add("ETAPA 2 completada. Columnas: ", ncol(df))


# =============================================================================
# ETAPA 3 + 4 — DECISIÓN POR CARDINALIDAD Y AGRUPACIÓN
# =============================================================================
log_add("----- ETAPA 3/4: Agrupaciones por cardinalidad -----")

# ── Binarias (cardinalidad real = 2) ─────────────────────────────────────────
df$sexo <- dplyr::case_when(
  df$SEXO == "HOMBRE" ~ 1L, df$SEXO == "MUJER" ~ 0L, TRUE ~ NA_integer_
)
df$nacionalidad_chilena <- dplyr::case_when(
  is.na(df$NACIONALIDAD) ~ NA_integer_,
  df$NACIONALIDAD %in% c("CHILENA", "CHILE", "CHL", "C") ~ 1L,
  TRUE ~ 0L
)
df <- df |> dplyr::select(-dplyr::any_of(c("SEXO", "NACIONALIDAD")))
log_add("3-bin sexo (1=Hombre, 0=Mujer) + nacionalidad_chilena creadas")

# =============================================================================
# CATEGÓRICAS DE ALTA CARDINALIDAD (ESPECIALIDAD_MEDICA, SERVICIOINGRESO,
# TIPO_PROCEDENCIA): SE BINARIZAN EN EL MODELADO (sobre TRAIN)
# ── CAMBIO (evitar fuga): antes se construían aquí dummies top-20 por frecuencia
#    (espmed_/serving_/proced_). Elegir "cuáles categorías" por su frecuencia en TODO
#    el dataset usa información del test → fuga. Esa binarización + selección chi²
#    top-N se hace en el MODELADO, sobre TRAIN, a partir de las columnas CRUDAS
#    ESPECIALIDAD_MEDICA / SERVICIOINGRESO / TIPO_PROCEDENCIA (que se CONSERVAN).
#    Las macro-áreas clínicas (*_macro) se mantienen como capa DESCRIPTIVA.
# =============================================================================
log_add(
  "3-alta-card: ESPECIALIDAD_MEDICA/SERVICIOINGRESO/TIPO_PROCEDENCIA quedan CRUDAS ",
  "(binarización + selección en el modelado, sobre train)"
)

# ── PROVINCIA → region (16 regiones) ─────────────────────────────────────────
# Mapeo de las 57 provincias a las 16 regiones de Chile. Reduce 57→16 cats y
# da un descriptor geográfico interpretable para caracterización regional.
prov2region <- c(
  ARICA = "ARICA_PARINACOTA", PARINACOTA = "ARICA_PARINACOTA",
  IQUIQUE = "TARAPACA", TAMARUGAL = "TARAPACA",
  ANTOFAGASTA = "ANTOFAGASTA", `EL LOA` = "ANTOFAGASTA", TOCOPILLA = "ANTOFAGASTA",
  COPIAPO = "ATACAMA", `CHAÑARAL` = "ATACAMA", HUASCO = "ATACAMA",
  ELQUI = "COQUIMBO", LIMARI = "COQUIMBO", CHOAPA = "COQUIMBO",
  VALPARAISO = "VALPARAISO", `ISLA DE PASCUA` = "VALPARAISO", `LOS ANDES` = "VALPARAISO",
  PETORCA = "VALPARAISO", QUILLOTA = "VALPARAISO", `SAN ANTONIO` = "VALPARAISO",
  `SAN FELIPE` = "VALPARAISO", `MARGA MARGA` = "VALPARAISO",
  SANTIAGO = "METROPOLITANA", CORDILLERA = "METROPOLITANA", CHACABUCO = "METROPOLITANA",
  MAIPO = "METROPOLITANA", MELIPILLA = "METROPOLITANA", TALAGANTE = "METROPOLITANA",
  CACHAPOAL = "OHIGGINS", `CARDENAL CARO` = "OHIGGINS", COLCHAGUA = "OHIGGINS",
  TALCA = "MAULE", CAUQUENES = "MAULE", CURICO = "MAULE", LINARES = "MAULE",
  `DIGUILLÍN` = "NUBLE", ITATA = "NUBLE", PUNILLA = "NUBLE", `ÑUBLE` = "NUBLE",
  CONCEPCION = "BIOBIO", ARAUCO = "BIOBIO", `BIO-BIO` = "BIOBIO",
  CAUTIN = "ARAUCANIA", MALLECO = "ARAUCANIA",
  VALDIVIA = "LOS_RIOS", RANCO = "LOS_RIOS",
  LLANQUIHUE = "LOS_LAGOS", CHILOE = "LOS_LAGOS", OSORNO = "LOS_LAGOS", PALENA = "LOS_LAGOS",
  AISEN = "AYSEN", COIHAIQUE = "AYSEN", `CAPITAN PRAT` = "AYSEN", `GENERAL CARRERA` = "AYSEN",
  MAGALLANES = "MAGALLANES", `ANTÁRTICA CHILENA` = "MAGALLANES",
  `TIERRA DEL FUEGO` = "MAGALLANES", `ULTIMA ESPERANZA` = "MAGALLANES"
)
if ("PROVINCIA" %in% names(df)) {
  df$region <- unname(prov2region[df$PROVINCIA]) # DESCONOCIDO y NA → NA
  df <- df |> dplyr::select(-PROVINCIA)
  log_add("3-PROVINCIA → region: ", length(unique(na.omit(df$region))), " regiones")
}

# ── ETNIA → binaria etnia_originario (1 = pertenece a pueblo originario) ──────
# Pueblos originarios reconocidos (Ley 19.253). NINGUNO/OTRO = no originario.
# DESCONOCIDO/NO RESPONDE → NA. Para caracterización detallada por pueblo,
# usar la columna ETNIA cruda desde el dataset pre-Etapa0 si se necesita.
pueblos_orig <- c(
  "MAPUCHE", "AYMARA", "RAPA NUI (PASCUENSE)", "DIAGUITA", "KAWÉSQAR",
  "QUECHUA", "YAGÁN (YÁMANA)", "COLLA", "LICAN ANTAI (ATACAMEÑO)"
)
if ("ETNIA" %in% names(df)) {
  df$etnia_originario <- dplyr::case_when(
    df$ETNIA %in% pueblos_orig ~ 1L,
    df$ETNIA %in% c("NINGUNO", "NINGUNA", "OTRO") ~ 0L,
    TRUE ~ NA_integer_
  ) # DESCONOCIDO/NO RESPONDE
  df <- df |> dplyr::select(-ETNIA)
  log_add(
    "3-ETNIA → binaria etnia_originario: ",
    round(mean(df$etnia_originario, na.rm = TRUE) * 100, 2), "% originario"
  )
}

# ── TIPO_INGRESO / TIPO_ACTIVIDAD → residuales de calidad a NA ────────────────
if ("TIPO_INGRESO" %in% names(df)) {
  df$TIPO_INGRESO <- dplyr::if_else(
    df$TIPO_INGRESO %in% c("URGENCIA", "PROGRAMADA", "OBSTETRICA"),
    df$TIPO_INGRESO, NA_character_
  )
}
# RELABEL 1:1 (NO se fusionan niveles): solo se normalizan nombres a etiquetas
# limpias y la basura de calidad (<0,05%) va a NA. Cada nivel real → su propia
# categoría OHE; la selección la hace el chi² al modelar.
if ("TIPO_ACTIVIDAD" %in% names(df)) {
  df$TIPO_ACTIVIDAD <- dplyr::case_when(
    df$TIPO_ACTIVIDAD == "HOSPITALIZACIÓN" ~ "HOSPITALIZACION",
    df$TIPO_ACTIVIDAD == "CIRUGÍA MAYOR AMBULATORIA (CMA)" ~ "CMA",
    df$TIPO_ACTIVIDAD == "HOSPITALIZACIÓN EN URGENCIA" ~ "HOSP_URGENCIA",
    df$TIPO_ACTIVIDAD == "HOSPITALIZACIÓN DIURNA" ~ "HOSP_DIURNA",
    TRUE ~ NA_character_
  ) # DESCONOCIDO / NO IDENTIFICADO
}

# ── TIPOALTA → relabel 1:1 (sin fusionar dispositivos de egreso) ─────────────
# Se normalizan nombres; solo se unen sub-etiquetas administrativas del MISMO
# destino (dos "otro hospital", dos "inst. privada") como limpieza, no como
# agrupación semántica. Basura de calidad (<0,05%) → NA.
if ("TIPOALTA" %in% names(df)) {
  df$TIPOALTA <- dplyr::case_when(
    df$TIPOALTA == "DOMICILIO" ~ "DOMICILIO",
    df$TIPOALTA == "FALLECIDO" ~ "FALLECIDO",
    df$TIPOALTA == "HOSPITALIZACIÓN DOMICILIARIA" ~ "HOSP_DOMICILIARIA",
    df$TIPOALTA == "ALTA VOLUNTARIA" ~ "ALTA_VOLUNTARIA",
    df$TIPOALTA == "FUGA DEL PACIENTE" ~ "FUGA",
    stringr::str_detect(df$TIPOALTA, "DERIVACI.N OTRO HOSPITAL") ~ "DERIV_HOSPITAL_PUBLICO",
    stringr::str_detect(df$TIPOALTA, "DERIVACI.N INST. PRIVADA") ~ "DERIV_PRIVADA",
    stringr::str_detect(df$TIPOALTA, "DERIVACI.N A OTROS CENTROS") ~ "DERIV_OTROS_CENTROS",
    TRUE ~ NA_character_
  ) # NO IDENTIFICADA / DESCONOCIDO
}

# ── TIPO_PROCEDENCIA → 5 macro-grupos (capa DESCRIPTIVA *_macro) ─────────────
# Ya NO reemplaza la variable: el modelo usa las dummies proced_* del bloque
# 3-topN. Esta agrupación se conserva sólo para tablas descriptivas.
if ("TIPO_PROCEDENCIA" %in% names(df)) {
  df$TIPO_PROCEDENCIA_macro <- dplyr::case_when(
    stringr::str_detect(df$TIPO_PROCEDENCIA, "EMERGENCIA") ~ "EMERGENCIA",
    stringr::str_detect(df$TIPO_PROCEDENCIA, "ESPECIALIDADES") ~ "ESPECIALIDADES",
    stringr::str_detect(df$TIPO_PROCEDENCIA, "HOSPITALES") ~ "HOSPITAL_RED",
    stringr::str_detect(df$TIPO_PROCEDENCIA, "APS") ~ "APS",
    df$TIPO_PROCEDENCIA %in% c("DESCONOCIDO", "NO IDENTIFICADO") ~ NA_character_,
    TRUE ~ "PRIVADO_OTRAS"
  )
}

# ── PREVISION → tramos FONASA MAI A/B/C/D SEPARADOS (proxy NSE, V=0.106) ──────
# Criterio OFICIAL: los tramos A/B/C/D son la clasificación socioeconómica de FONASA
# (definición legal, no del investigador) y cubren el 96% de los datos. Libre elección
# (FLE) es otra modalidad oficial. El resto (ISAPRE, particular, FFAA) se agrupa como
# "NO_FONASA": es un residual definido por exclusión (todo lo que no es FONASA público),
# no una fusión semántica arbitraria.
# OJO: los valores reales son "FONASA INSTITUCIONAL - (MAI) A", no "FONASA MAI A".
if ("PREVISION" %in% names(df)) {
  df$PREVISION <- dplyr::case_when(
    stringr::str_detect(df$PREVISION, "\\(MAI\\) A") ~ "FONASA_MAI_A",
    stringr::str_detect(df$PREVISION, "\\(MAI\\) B") ~ "FONASA_MAI_B",
    stringr::str_detect(df$PREVISION, "\\(MAI\\) C") ~ "FONASA_MAI_C",
    stringr::str_detect(df$PREVISION, "\\(MAI\\) D") ~ "FONASA_MAI_D",
    stringr::str_detect(df$PREVISION, "LIBRE ELECC") ~ "FONASA_FLE",
    df$PREVISION %in% c("ISAPRE", "PARTICULAR") |
      stringr::str_detect(df$PREVISION, "DIPRECA|CAPREDENA|FFAA|SISA") ~ "NO_FONASA",
    TRUE ~ NA_character_
  ) # NO IDENTIFICADA / NO CONSIGNADO / DESCONOCIDO
}

# ── Macro-agrupación clínica para alta cardinalidad (NO top-N ciego) ──────────
# Fuerza REUMATOLOGIA aunque sea rara. Orden de las reglas importa.
# fold(): quita tildes para que el matching sea insensible a acentos
# (ej. "ÁREA MÉDICA" debe caer en MEDICO). Se aplica solo para detectar,
# la categoría resultante es el código limpio sin tildes.
fold <- function(x) chartr("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun", x)

# Especialidades médicas (ESPECIALIDAD_MEDICA). Agrupación por MACRO-ÁREA CLÍNICA.
# El ORDEN importa (regla más específica primero) para evitar colisiones de substring
# (ej. INTENSIVA antes que MEDICINA; \bUROLOG con límite de palabra para no capturar
# neUROLOGia; ODONTO/MAXILOFACIAL antes que TRAUMATOLOGIA por "traumatología buco maxilofacial").
# Con esto OTRAS < 0,1% (solo Medicina Familiar/Desconocido). Ver JUSTIFICACIONES.md.
macro_especialidad <- function(x) {
  xf <- fold(x)
  dplyr::case_when(
    is.na(x) ~ NA_character_,
    # REUMATOLOGÍA ya NO se fuerza como grupo propio: cae en MEDICINA_ESPECIALIDADES
    # (su área clínica natural). Motivo: como feature del clasificador reum-vs-general
    # era casi circular (lift 15). El "% atendido por reumatología" se reporta como
    # estadística descriptiva (acceso), no como predictora. Ver JUSTIFICACIONES.md.
    stringr::str_detect(xf, "INTENSIV|URGENCIA|EMERGENCIA|CUIDADOS INTENSIVOS|TRATAMIENTO INTERMEDIO|CORONARIO") ~ "INTENSIVO_URGENCIA",
    stringr::str_detect(xf, "OBSTETR|GINECOLOG|MATRON|PUERPERIO|EMBARAZO|MATERNO FETAL") ~ "OBSTETRICIA_GINECOLOGIA",
    stringr::str_detect(xf, "PEDIATR|NEONATOL|LACTANTE|ADOLESCEN|SEGUNDA INFANCIA|ODONTOPEDIATR") ~ "PEDIATRIA_NEONATOLOGIA",
    stringr::str_detect(xf, "ODONT|DENTISTA|MAXILOFACIAL|MAXILO FACIAL|BUCO|PERIODONCIA|ORTODONCIA|ENDODONCIA|REHABILITACION ORAL|IMPLANTOLOG|PATOLOGIA ORAL|TEMPOROMANDIBULAR") ~ "ODONTO_MAXILOFACIAL",
    stringr::str_detect(xf, "TRAUMATOL|ORTOPED") ~ "TRAUMATOLOGIA",
    stringr::str_detect(xf, "OFTALMOL") ~ "OFTALMOLOGIA",
    stringr::str_detect(xf, "PSIQUIATR|NEUROPSIQ|SALUD MENTAL") ~ "SALUD_MENTAL",
    stringr::str_detect(xf, "CIRUG|\\bUROLOG|NEUROCIRUG|OTORRINO|VASCULAR|COLOPROCT|ANESTES|\\bTORAX|PLASTICA|CABEZA|CUELLO|PABELLON|QUIRURGIC") ~ "QUIRURGICO",
    stringr::str_detect(xf, "MEDICINA INTERNA|MEDICINA GENERAL|MEDICO GENERAL|REUMATOL|CARDIOL|NEUROLOG|NEFROL|GASTRO|RESPIRATORI|BRONCOPULM|HEMATOL|ONCOL|ENDOCRIN|DERMATOL|INMUNOL|INFECTOL|GERIATR|DIABETOL|NUTRICI|REHABILITAC|MEDICINA FISICA") ~ "MEDICINA_ESPECIALIDADES",
    stringr::str_detect(xf, "RADIOLOG|IMAGENOL|ANATOMIA PATOL|LABORATORIO|MEDICINA NUCLEAR|MICROBIOL|TRANSFUSIONAL|GENETICA") ~ "DIAGNOSTICO_APOYO",
    TRUE ~ "OTRAS"
  )
}

# Servicios clínicos (SERVICIOINGRESO) — vocabulario distinto (unidades/salas).
# Mismo criterio de macro-área clínica; orden por especificidad. OTRAS ~0,5% (Desconocido).
macro_servicio <- function(x) {
  xf <- fold(x)
  dplyr::case_when(
    is.na(x) ~ NA_character_,
    stringr::str_detect(xf, "INTENSIV|INTERMEDIO|\\bUCI\\b|\\bUTI\\b|URGENCIA|EMERGENCIA|CORONARIO|CRITIC|QUEMADO") ~ "INTENSIVO_URGENCIA",
    stringr::str_detect(xf, "OBSTETR|GINECOLOG|PUERPERIO|EMBARAZO|MATERNIDAD") ~ "OBSTETRICIA_GINECOLOGIA",
    stringr::str_detect(xf, "PEDIATR|NEONATOL|INFANTIL|LACTANTE|SEGUNDA INFANCIA|INCUBADORA|CUNAS|NINOS") ~ "PEDIATRIA_NEONATOLOGIA",
    stringr::str_detect(xf, "PSIQUIATR|NEUROPSIQ|SALUD MENTAL") ~ "SALUD_MENTAL",
    stringr::str_detect(xf, "TRAUMATOL|ORTOPED") ~ "TRAUMATOLOGIA",
    stringr::str_detect(xf, "OFTALMOL") ~ "OFTALMOLOGIA",
    stringr::str_detect(xf, "MEDIC") & stringr::str_detect(xf, "QUIR") ~ "MEDICO_QUIRURGICO",
    stringr::str_detect(xf, "CIRUG|PABELLON|QUIRURGIC|\\bUROLOG|NEUROCIRUG|OTORRINO|VASCULAR|MAXILO|TRANSPLANTE") ~ "QUIRURGICO",
    stringr::str_detect(xf, "\\bMEDIC|CARDIOL|NEUROLOG|NEFROL|GASTRO|ONCOL|GERIATR|DIABETES|NUTRICI|HOSPITAL DE DIA MEDICO") ~ "MEDICINA",
    stringr::str_detect(xf, "PENSIONADO") ~ "PENSIONADO",
    TRUE ~ "OTRAS"
  )
}

# Las macro-áreas pasan a columnas *_macro (capa DESCRIPTIVA). NO entran al
# modelo: serían redundantes con las dummies espmed_*/serving_* (una determina
# a la otra). Se conservan para las tablas de caracterización clínica.
for (col in intersect(c("ESPECIALIDAD_MEDICA"), names(df))) { # ESPECIALIDADINTERVENCION ya eliminada (2G)
  n0 <- length(unique(na.omit(df[[col]])))
  df[[paste0(col, "_macro")]] <- macro_especialidad(df[[col]])
  log_add(
    "3-clínica ", col, "_macro (descriptiva): ", n0, " → ",
    length(unique(na.omit(df[[paste0(col, "_macro")]]))), " macro-grupos"
  )
}
if ("SERVICIOINGRESO" %in% names(df)) {
  n0 <- length(unique(na.omit(df$SERVICIOINGRESO)))
  df$SERVICIOINGRESO_macro <- macro_servicio(df$SERVICIOINGRESO)
  log_add(
    "3-clínica SERVICIOINGRESO_macro (descriptiva): ", n0, " → ",
    length(unique(na.omit(df$SERVICIOINGRESO_macro))), " macro-grupos"
  )
}
# ── IR_29301_COD_GRD → ELIMINAR ──────────────────────────────────────────────
# Verificado: PESO y SEVERIDAD se determinan 100% desde el COD_GRD (colinealidad
# perfecta), y es un CÓDIGO categórico de 1.064 valores (no una cantidad). Su
# información ya está en IR_29301_PESO (continua, con sentido) + IR_29301_SEVERIDAD.
df <- df |> dplyr::select(-dplyr::any_of("IR_29301_COD_GRD"))
log_add("3-IR_29301_COD_GRD eliminado (100% colineal con PESO+SEVERIDAD)")

# ── IR_29301_SEVERIDAD / MORTALIDAD → numéricas ("DESCONOCIDO" → NA) ──────────
for (col in intersect(c("IR_29301_SEVERIDAD", "IR_29301_MORTALIDAD"), names(df))) {
  df[[col]] <- suppressWarnings(as.numeric(df[[col]]))
}
log_add("3-IR SEVERIDAD/MORTALIDAD → numéricas")

log_add("ETAPA 3/4 completada. Columnas: ", ncol(df))


# =============================================================================
# EXPORTAR DATASET PRE-ENCODING  (incluye tipo_reum para caracterización 06)
# =============================================================================
arrow::write_parquet(df, RUTA_SALIDA_BASE)
log_add(
  "Pre-encoding exportado: ", RUTA_SALIDA_BASE,
  " (", format(nrow(df), big.mark = "."), " × ", ncol(df), ")"
)


# =============================================================================
# ETAPA 5 — ENCODING (OHE)
# =============================================================================
log_add("----- ETAPA 5: One-Hot Encoding -----")
DROP_FIRST <- FALSE # TRUE para modelos lineales (evita multicolinealidad)

ohe_col <- function(df, col, drop_first = FALSE) {
  vals <- sort(unique(df[[col]][!is.na(df[[col]])]))
  if (drop_first && length(vals) > 1) vals <- vals[-1]
  for (v in vals) {
    nm <- paste0(col, "__", stringr::str_replace_all(v, "[^A-Za-z0-9]", "_"))
    df[[nm]] <- as.integer(!is.na(df[[col]]) & df[[col]] == v)
  }
  df[[col]] <- NULL
  df
}

# Variables a OHE (nominales de baja-media cardinalidad ya agrupadas).
# tipo_reum NO está aquí (leakage). SEXO/NACIONALIDAD ya son binarias.
# OHE solo de las nominales de BAJA cardinalidad y dominio fijo (estructural, no se
# "aprende" nada por frecuencia). ESPECIALIDADINTERVENCION eliminada (redundante, V=0,83).
COLS_OHE <- intersect(c(
  "TIPO_INGRESO", "TIPO_ACTIVIDAD", "TIPOALTA",
  "PREVISION", "region"
), names(df))

# Columnas que NO entran a la matriz OHE del modelo, PERO SÍ quedan en el parquet
# pre-encoding (datos_preprocesados.parquet) para el modelado y la descripción:
#  · etiqueta / control (grupo_paciente, es_reum, anio)
#  · fuga: tipo_reum, reum_*, enfermedad_principal, n_enfermedades_reum
#  · CRUDOS de ALTA CARDINALIDAD (DIAGNOSTICO1-35, PROCEDIMIENTO1-30, ESPECIALIDAD_MEDICA,
#    SERVICIOINGRESO, TIPO_PROCEDENCIA): su binarización + selección chi² top-N se hace
#    en el MODELADO, sobre TRAIN (evitar fuga). Aquí van CRUDOS.
#  · descriptivas: dxcap_ (capítulos CIE-10), proccap_ (secciones CIE-9), *_macro.
COLS_EXCLUIR_MODELO <- intersect(c(
  "grupo_paciente", "es_reum", "anio", "id_paciente",
  "tipo_reum", "enfermedad_principal", "n_enfermedades_reum",
  # C4 : variables acumuladas sesgadas por el re-cifrado del id entre
  # 2020 y 2021 -> se REINICIAN en el corte (un paciente de 2021 aparece con 0 previas
  # aunque las tuviera en 2019-2020) + censura a la izquierda. Se DESCARTAN del modelo
  # (se conservan en el parquet pre-encoding solo para transparencia/descriptiva).
  "n_hosp_previas", "dias_desde_ult_hosp",
  "ESPECIALIDAD_MEDICA", "SERVICIOINGRESO", "TIPO_PROCEDENCIA",
  "ESPECIALIDAD_MEDICA_macro", "SERVICIOINGRESO_macro", "TIPO_PROCEDENCIA_macro",
  paste0("DIAGNOSTICO", 1:35), # crudos → binarizar en modelado/train
  paste0("PROCEDIMIENTO", 1:30), # crudos → binarizar en modelado/train
  grep("^reum_", names(df), value = TRUE),
  grep("^dxcap_", names(df), value = TRUE), # capítulos CIE-10 → descriptivo
  grep("^proccap_", names(df), value = TRUE) # secciones CIE-9  → descriptivo
), names(df))

df_ohe <- df |> dplyr::select(-dplyr::all_of(COLS_EXCLUIR_MODELO))
for (col in COLS_OHE) df_ohe <- ohe_col(df_ohe, col, drop_first = DROP_FIRST)

# Reincorporar etiqueta, año e id_paciente como columnas de control (no como features X;
# id_paciente = clave de grupo para el split por paciente en el modelado)
for (c in intersect(c("grupo_paciente", "es_reum", "anio", "id_paciente"), names(df))) {
  df_ohe[[c]] <- df[[c]]
}

log_add(
  "OHE aplicado a ", length(COLS_OHE), " variables: ",
  paste(COLS_OHE, collapse = ", ")
)
log_add(
  "Excluidas del modelo (leakage/control): ",
  paste(COLS_EXCLUIR_MODELO, collapse = ", ")
)

arrow::write_parquet(df_ohe, RUTA_SALIDA_OHE)
log_add(
  "OHE exportado: ", RUTA_SALIDA_OHE,
  " (", format(nrow(df_ohe), big.mark = "."), " × ", ncol(df_ohe), ")"
)

# =============================================================================
# CUANTIFICACIÓN DE DIMENSIONALIDAD — ¿cuántas columnas quedan para el modelo?
# Desglose por variable OHE + numéricas/binarias passthrough + total.
# Sirve para decidir si conviene seguir eliminando/agrupando.
# =============================================================================
log_add("----- DIMENSIONALIDAD FINAL -----")
cols_control <- intersect(c("grupo_paciente", "es_reum", "anio", "id_paciente"), names(df_ohe))
cols_modelo <- setdiff(names(df_ohe), cols_control)
dim_ohe <- sapply(COLS_OHE, function(v) sum(startsWith(names(df_ohe), paste0(v, "__"))))
n_passthrough <- length(cols_modelo) - sum(dim_ohe)
for (v in names(dim_ohe)) log_add(sprintf("  OHE %-26s %2d cols", v, dim_ohe[v]))
log_add(sprintf("  %-30s %2d cols", "Numéricas/binarias passthrough", n_passthrough))
log_add(sprintf(
  "  >>> TOTAL MATRIZ DEL MODELO: %d columnas (+%d control)",
  length(cols_modelo), length(cols_control)
))
dim_df <- data.frame(
  grupo = c(names(dim_ohe), "PASSTHROUGH_num_bin", "TOTAL_MODELO"),
  n_columnas = c(unname(dim_ohe), n_passthrough, length(cols_modelo))
)
readr::write_csv(dim_df, file.path(DIR_OUT, "dimensionalidad_ohe.csv"))
log_add("Reporte de dimensionalidad: ", file.path(DIR_OUT, "dimensionalidad_ohe.csv"))


# =============================================================================
# VERIFICACIÓN ANTI-LEAKAGE
# Ninguna feature debe reconstruir la etiqueta.
# =============================================================================
log_add("----- VERIFICACIÓN -----")
if ("grupo_paciente" %in% names(df_ohe)) {
  y <- as.integer(df_ohe$grupo_paciente == "Reumatológico")
  feats <- setdiff(names(df_ohe), c("grupo_paciente", "es_reum", "anio", "id_paciente"))
  # Chequeo: ¿alguna columna binaria coincide ~perfecto con y?
  sospechosas <- character(0)
  for (f in feats) {
    v <- df_ohe[[f]]
    if (length(unique(na.omit(v))) <= 2 && all(na.omit(v) %in% c(0, 1))) {
      conc <- mean(v == y, na.rm = TRUE)
      if (conc > 0.99 || conc < 0.01) sospechosas <- c(sospechosas, f)
    }
  }
  if (length(sospechosas) > 0) {
    log_add("⚠ POSIBLE LEAKAGE en: ", paste(sospechosas, collapse = ", "))
  } else {
    log_add("✓ Sin features que reconstruyan la etiqueta (>99% concordancia)")
  }
}


# =============================================================================
# SELECCIÓN DE CARACTERÍSTICAS — SE HACE EN EL MODELADO, NO AQUÍ
# (corrección explícita del profesor guía: evitar FUGA DE DATOS)
#
# El preprocesamiento entrega la MATRIZ COMPLETA de candidatas (todas las dummies
# de presencia comorb_/proccod_/espmed_/serving_/proced_ + numéricas + taxonomías).
# La selección chi² NO se aplica sobre la base completa: hacerlo usa información
# del conjunto de prueba y produce fuga de datos — es exactamente el error que el
# profesor corrigió del trabajo de referencia (allí se filtró y DESPUÉS se partió
# train/test; el orden correcto es el inverso).
#
# PROCEDIMIENTO CORRECTO (en la fase de modelado, en Python):
#   1) Partir train / test (estratificado por paciente).
#   2) SÓLO sobre train: chi² de cada candidata contra el objetivo.
#   3) Ordenar por p-value —equivale a ordenar por el estadístico chi² de mayor a
#      menor, que no sufre el underflow del p con N grande— y quedarse con las
#      TOP-N (N según cuántas variables se quiera manejar, p. ej. 100).
#   4) Entrenar los modelos con esas top-N (ensamblado/consenso); evaluar en test.
#   Para uno-vs-resto, la selección se repite por enfermedad (cada objetivo, su
#   propia selección sobre su propio train).
# Ver JUSTIFICACIONES.md §4.6 y el pipeline (Etapa 6 y sección de decisiones).
# =============================================================================


# =============================================================================
# RESUMEN FINAL
# =============================================================================
log_add("========== RESUMEN ==========")
log_add("Columnas originales : ", n_cols_orig)
log_add("Columnas pre-encoding: ", ncol(df))
log_add("Columnas post-OHE    : ", ncol(df_ohe))
log_add("Matriz OHE del modelo (df_ohe) = features SEGURAS (no aprenden por frecuencia):")
log_add("   edad, duracion_hospitalizacion, n_diagnosticos, n_procedimientos, n_traslados,")
log_add("   n_hosp_previas, sexo, nacionalidad_chilena, etnia_originario, flags (pabellon/")
log_add("   intervencion/cambio_servicio), IR_29301_PESO/SEVERIDAD/MORTALIDAD,")
log_add("   OHE de TIPO_INGRESO/TIPO_ACTIVIDAD/TIPOALTA/PREVISION/region.")
log_add("CRUDAS en el pre-encoding (binarizar+seleccionar en MODELADO, sobre train):")
log_add("   DIAGNOSTICO1-35, PROCEDIMIENTO1-30, ESPECIALIDAD_MEDICA, SERVICIOINGRESO, TIPO_PROCEDENCIA")
log_add("Descriptivas (NO modelo): dxcap_<cap> (19 CIE-10) + proccap_<sec> (18 CIE-9) + *_macro")
log_add("Desenlaces: reingreso_30d, n_hosp_previas, dias_desde_ult_hosp, duracion, IR_29301_PESO/SEVERIDAD")
log_add("Caracterización (EXCLUIDAS, leakage): tipo_reum, reum_<enfermedad> (14 multi-hot),")
log_add("   enfermedad_principal, n_enfermedades_reum")
log_add("Selección de características: NO se hace aquí; va en el modelado (split → chi² top-N sobre train). Evita fuga.")
log_add("Decisiones clave: leakage excluido | PESO recuperado (coma decimal) | fechas 2023 |")
log_add("   binarización+selección de alta cardinalidad DIFERIDA a modelado/train | reingresos derivados")

readr::write_lines(log_lines, RUTA_LOG)
message("Log guardado en: ", RUTA_LOG)
message("Preprocesamiento v2 completado.")
