# =============================================================================
# MÓDULO 06 — ANÁLISIS DE AGRUPACIONES Y TRANSFORMACIONES POR VARIABLE
# Caracterización de Pacientes Reumatológicos — GRD Chile 2019–2024
# Autor: Diego Oliva López | USACH
#
# Objetivo: para CADA variable categórica y numérica, describir en detalle las
# categorías y sus cantidades GLOBAL vs REUMATOLÓGICO, y validar las
# agrupaciones/transformaciones propuestas en el Módulo 05 (antes → después).
#
# Entrada: output/datos_consolidados_etiquetados.parquet  (incluye grupo_paciente)
# Salida : output/analisis_variables/*.csv   (una tabla por variable)
#          output/analisis_variables/_resumen_numericas.csv
#          output/analisis_variables/_lift_categorias.csv  (poder discriminante)
#
# Métricas clave por categoría:
#   n_global, n_reum, n_total, pct_col (% de la columna),
#   pct_reum_en_categoria (= n_reum/n_total), lift (= pct_reum_en_categoria / base_rate)
#   lift > 1  → categoría SOBRE-representada en reumatológicos (señal positiva)
#   lift < 1  → categoría INFRA-representada (señal negativa, p.ej. OBSTETRICA)
# =============================================================================

suppressPackageStartupMessages({
  library(arrow)
  library(dplyr)
  library(stringr)
  library(tidyr)
  library(readr)
})
source("_codigos_cie.R")
CODIGOS_UPPER <- toupper(TODOS_LOS_CODIGOS)

DIR_OUT <- "output"
DIR_AN <- file.path(DIR_OUT, "analisis_variables")
dir.create(DIR_AN, showWarnings = FALSE, recursive = TRUE)
RUTA <- file.path(DIR_OUT, "datos_consolidados_etiquetados.parquet")

cat("Cargando dataset...\n")
df <- arrow::read_parquet(RUTA)
df$.es_reum <- as.integer(df$grupo_paciente == "Reumatológico")
N <- nrow(df)
N_REUM <- sum(df$.es_reum)
BASE_RATE <- N_REUM / N
cat(sprintf(
  "N=%s | Reumatológicos=%s | base rate=%.3f%%\n",
  format(N, big.mark = "."), format(N_REUM, big.mark = "."), BASE_RATE * 100
))

# ── Helpers ──────────────────────────────────────────────────────────────────
normalizar_txt <- function(x) {
  x <- str_squish(str_trim(as.character(x)))
  x <- toupper(x)
  ifelse(x %in% c("", "NULL", "NA", "NAN", "."), NA_character_, x)
}

# Tabla de frecuencias global vs reum para una variable categórica (vector ya listo)
tabla_cat <- function(vec, etiqueta) {
  d <- tibble(cat = vec, reum = df$.es_reum) |>
    mutate(cat = ifelse(is.na(cat), "(NA)", cat)) |>
    group_by(cat) |>
    summarise(
      n_global = n(),
      n_reum = sum(reum),
      .groups = "drop"
    ) |>
    mutate(
      n_no_reum = n_global - n_reum,
      pct_col = round(n_global / N * 100, 3),
      pct_reum_en_categoria = round(n_reum / n_global * 100, 2),
      lift = round((n_reum / n_global) / BASE_RATE, 2)
    ) |>
    arrange(desc(n_global))
  readr::write_csv(d, file.path(DIR_AN, paste0("cat_", etiqueta, ".csv")))
  cat(sprintf(
    "  [cat] %-28s %d categorías → %s\n",
    etiqueta, nrow(d), paste0("cat_", etiqueta, ".csv")
  ))
  d |> mutate(variable = etiqueta)
}

# Resumen numérico por grupo
resumen_num <- function(x, etiqueta) {
  xx <- suppressWarnings(as.numeric(str_replace(as.character(x), ",", ".")))
  tibble(
    variable = etiqueta,
    na_pct = round(mean(is.na(xx)) * 100, 2),
    media_global = round(mean(xx, na.rm = TRUE), 3),
    media_reum = round(mean(xx[df$.es_reum == 1], na.rm = TRUE), 3),
    media_no_reum = round(mean(xx[df$.es_reum == 0], na.rm = TRUE), 3),
    mediana_reum = round(median(xx[df$.es_reum == 1], na.rm = TRUE), 3),
    mediana_no_reum = round(median(xx[df$.es_reum == 0], na.rm = TRUE), 3)
  )
}


# =============================================================================
# 1. VARIABLES CATEGÓRICAS — crudas (top categorías) y agrupadas (validación)
# =============================================================================
cat("\n== CATEGÓRICAS ==\n")
lift_all <- list()

# --- 1a. Categóricas que se analizan CRUDAS (normalizadas) ---
cats_crudas <- c(
  "SEXO", "NACIONALIDAD", "TIPO_INGRESO", "TIPO_ACTIVIDAD", "TIPOALTA",
  "TIPO_PROCEDENCIA", "PREVISION", "ESPECIALIDAD_MEDICA",
  "ESPECIALIDADINTERVENCION", "SERVICIOINGRESO", "SERVICIOALTA", "ETNIA"
)
for (col in intersect(cats_crudas, names(df))) {
  lift_all[[col]] <- tabla_cat(normalizar_txt(df[[col]]), col)
}

# --- 1b. Validación de AGRUPACIONES (antes → después) ---

# region (provincia → 16 regiones)
prov2region <- c(
  ARICA = "ARICA_PARINACOTA", PARINACOTA = "ARICA_PARINACOTA", IQUIQUE = "TARAPACA",
  TAMARUGAL = "TARAPACA", ANTOFAGASTA = "ANTOFAGASTA", `EL LOA` = "ANTOFAGASTA",
  TOCOPILLA = "ANTOFAGASTA", COPIAPO = "ATACAMA", `CHAÑARAL` = "ATACAMA", HUASCO = "ATACAMA",
  ELQUI = "COQUIMBO", LIMARI = "COQUIMBO", CHOAPA = "COQUIMBO", VALPARAISO = "VALPARAISO",
  `ISLA DE PASCUA` = "VALPARAISO", `LOS ANDES` = "VALPARAISO", PETORCA = "VALPARAISO",
  QUILLOTA = "VALPARAISO", `SAN ANTONIO` = "VALPARAISO", `SAN FELIPE` = "VALPARAISO",
  `MARGA MARGA` = "VALPARAISO", SANTIAGO = "METROPOLITANA", CORDILLERA = "METROPOLITANA",
  CHACABUCO = "METROPOLITANA", MAIPO = "METROPOLITANA", MELIPILLA = "METROPOLITANA",
  TALAGANTE = "METROPOLITANA", CACHAPOAL = "OHIGGINS", `CARDENAL CARO` = "OHIGGINS",
  COLCHAGUA = "OHIGGINS", TALCA = "MAULE", CAUQUENES = "MAULE", CURICO = "MAULE", LINARES = "MAULE",
  `DIGUILLÍN` = "NUBLE", ITATA = "NUBLE", PUNILLA = "NUBLE", `ÑUBLE` = "NUBLE",
  CONCEPCION = "BIOBIO", ARAUCO = "BIOBIO", `BIO-BIO` = "BIOBIO", CAUTIN = "ARAUCANIA",
  MALLECO = "ARAUCANIA", VALDIVIA = "LOS_RIOS", RANCO = "LOS_RIOS", LLANQUIHUE = "LOS_LAGOS",
  CHILOE = "LOS_LAGOS", OSORNO = "LOS_LAGOS", PALENA = "LOS_LAGOS", AISEN = "AYSEN",
  COIHAIQUE = "AYSEN", `CAPITAN PRAT` = "AYSEN", `GENERAL CARRERA` = "AYSEN",
  MAGALLANES = "MAGALLANES", `ANTÁRTICA CHILENA` = "MAGALLANES",
  `TIERRA DEL FUEGO` = "MAGALLANES", `ULTIMA ESPERANZA` = "MAGALLANES"
)
if ("PROVINCIA" %in% names(df)) {
  region <- unname(prov2region[normalizar_txt(df$PROVINCIA)])
  lift_all[["region"]] <- tabla_cat(region, "GRUPO_region")
}

# macro-agrupación clínica (idéntica al Módulo 05; folding de tildes)
fold <- function(x) chartr("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun", x)
# Sincronizadas con el Módulo 05 (agrupación por área clínica; REUMATOLOGÍA NO forzada).
macro_especialidad <- function(x) {
  xf <- fold(x)
  dplyr::case_when(
    is.na(x) ~ NA_character_,
    str_detect(xf, "INTENSIV|URGENCIA|EMERGENCIA|CUIDADOS INTENSIVOS|TRATAMIENTO INTERMEDIO|CORONARIO") ~ "INTENSIVO_URGENCIA",
    str_detect(xf, "OBSTETR|GINECOLOG|MATRON|PUERPERIO|EMBARAZO|MATERNO FETAL") ~ "OBSTETRICIA_GINECOLOGIA",
    str_detect(xf, "PEDIATR|NEONATOL|LACTANTE|ADOLESCEN|SEGUNDA INFANCIA|ODONTOPEDIATR") ~ "PEDIATRIA_NEONATOLOGIA",
    str_detect(xf, "ODONT|DENTISTA|MAXILOFACIAL|MAXILO FACIAL|BUCO|PERIODONCIA|ORTODONCIA|ENDODONCIA|REHABILITACION ORAL|IMPLANTOLOG|PATOLOGIA ORAL|TEMPOROMANDIBULAR") ~ "ODONTO_MAXILOFACIAL",
    str_detect(xf, "TRAUMATOL|ORTOPED") ~ "TRAUMATOLOGIA",
    str_detect(xf, "OFTALMOL") ~ "OFTALMOLOGIA",
    str_detect(xf, "PSIQUIATR|NEUROPSIQ|SALUD MENTAL") ~ "SALUD_MENTAL",
    str_detect(xf, "CIRUG|\\bUROLOG|NEUROCIRUG|OTORRINO|VASCULAR|COLOPROCT|ANESTES|\\bTORAX|PLASTICA|CABEZA|CUELLO|PABELLON|QUIRURGIC") ~ "QUIRURGICO",
    str_detect(xf, "MEDICINA INTERNA|MEDICINA GENERAL|MEDICO GENERAL|REUMATOL|CARDIOL|NEUROLOG|NEFROL|GASTRO|RESPIRATORI|BRONCOPULM|HEMATOL|ONCOL|ENDOCRIN|DERMATOL|INMUNOL|INFECTOL|GERIATR|DIABETOL|NUTRICI|REHABILITAC|MEDICINA FISICA") ~ "MEDICINA_ESPECIALIDADES",
    str_detect(xf, "RADIOLOG|IMAGENOL|ANATOMIA PATOL|LABORATORIO|MEDICINA NUCLEAR|MICROBIOL|TRANSFUSIONAL|GENETICA") ~ "DIAGNOSTICO_APOYO",
    TRUE ~ "OTRAS"
  )
}
macro_servicio <- function(x) {
  xf <- fold(x)
  dplyr::case_when(
    is.na(x) ~ NA_character_,
    str_detect(xf, "REUMATOL") ~ "REUMATOLOGIA",
    str_detect(xf, "INTENSIV|INTERMEDIO|\\bUCI\\b|\\bUTI\\b|URGENCIA|EMERGENCIA|CORONARIO|CRITIC|QUEMADO") ~ "INTENSIVO_URGENCIA",
    str_detect(xf, "OBSTETR|GINECOLOG|PUERPERIO|EMBARAZO|MATERNIDAD") ~ "OBSTETRICIA_GINECOLOGIA",
    str_detect(xf, "PEDIATR|NEONATOL|INFANTIL|LACTANTE|SEGUNDA INFANCIA|INCUBADORA|CUNAS|NINOS") ~ "PEDIATRIA_NEONATOLOGIA",
    str_detect(xf, "PSIQUIATR|NEUROPSIQ|SALUD MENTAL") ~ "SALUD_MENTAL",
    str_detect(xf, "TRAUMATOL|ORTOPED") ~ "TRAUMATOLOGIA",
    str_detect(xf, "OFTALMOL") ~ "OFTALMOLOGIA",
    str_detect(xf, "MEDIC") & str_detect(xf, "QUIR") ~ "MEDICO_QUIRURGICO",
    str_detect(xf, "CIRUG|PABELLON|QUIRURGIC|\\bUROLOG|NEUROCIRUG|OTORRINO|VASCULAR|MAXILO|TRANSPLANTE") ~ "QUIRURGICO",
    str_detect(xf, "\\bMEDIC|CARDIOL|NEUROLOG|NEFROL|GASTRO|ONCOL|GERIATR|DIABETES|NUTRICI|HOSPITAL DE DIA MEDICO") ~ "MEDICINA",
    str_detect(xf, "PENSIONADO") ~ "PENSIONADO",
    TRUE ~ "OTRAS"
  )
}
for (col in intersect(c("ESPECIALIDAD_MEDICA", "ESPECIALIDADINTERVENCION"), names(df))) {
  lift_all[[paste0("macro_", col)]] <-
    tabla_cat(macro_especialidad(normalizar_txt(df[[col]])), paste0("GRUPO_macro_", col))
}
if ("SERVICIOINGRESO" %in% names(df)) {
  lift_all[["macro_SERVICIOINGRESO"]] <-
    tabla_cat(macro_servicio(normalizar_txt(df$SERVICIOINGRESO)), "GRUPO_macro_SERVICIOINGRESO")
}

# etnia → binaria originario
pueblos_orig <- c(
  "MAPUCHE", "AYMARA", "RAPA NUI (PASCUENSE)", "DIAGUITA", "KAWÉSQAR",
  "QUECHUA", "YAGÁN (YÁMANA)", "COLLA", "LICAN ANTAI (ATACAMEÑO)"
)
if ("ETNIA" %in% names(df)) {
  e <- normalizar_txt(df$ETNIA)
  et <- dplyr::case_when(
    e %in% pueblos_orig ~ "ORIGINARIO",
    e %in% c("NINGUNO", "NINGUNA", "OTRO") ~ "NO_ORIGINARIO",
    TRUE ~ NA_character_
  )
  lift_all[["etnia_bin"]] <- tabla_cat(et, "GRUPO_etnia_originario")
}

# enfermedades reumatológicas MULTI-HOT (caracterización): un paciente puede
# tener varias → se mide la PREVALENCIA de cada una y la co-ocurrencia.
code2group <- unlist(lapply(names(CODIGOS_REUMATICOS), function(g) {
  setNames(
    rep(g, length(CODIGOS_REUMATICOS[[g]])),
    toupper(str_trim(CODIGOS_REUMATICOS[[g]]))
  )
}))
code2group <- code2group[!duplicated(names(code2group))]
COLS_DIAG <- intersect(paste0("DIAGNOSTICO", 1:35), names(df))
if (length(COLS_DIAG) > 0) {
  map_grupo <- function(x) unname(code2group[toupper(str_trim(as.character(x)))])
  mat_g <- do.call(cbind, lapply(COLS_DIAG, function(c) map_grupo(df[[c]])))
  enf_prev <- lapply(names(CODIGOS_REUMATICOS), function(g) {
    tiene <- rowSums(mat_g == g, na.rm = TRUE) > 0
    tibble(
      enfermedad = g,
      n_pacientes = sum(tiene),
      pct_de_reumatologicos = round(sum(tiene & df$.es_reum == 1) / N_REUM * 100, 2)
    )
  })
  d_enf <- bind_rows(enf_prev) |> arrange(desc(n_pacientes))
  readr::write_csv(d_enf, file.path(DIR_AN, "cat_GRUPO_enfermedades_multihot.csv"))
  # nº de enfermedades reumatológicas distintas por paciente reumatológico
  n_enf <- rowSums(sapply(
    names(CODIGOS_REUMATICOS),
    function(g) rowSums(mat_g == g, na.rm = TRUE) > 0
  ))
  d_co <- tibble(n_enfermedades = n_enf[df$.es_reum == 1]) |>
    count(n_enfermedades, name = "n_pacientes") |>
    mutate(pct = round(n_pacientes / N_REUM * 100, 2))
  readr::write_csv(d_co, file.path(DIR_AN, "cat_GRUPO_n_enfermedades_reum.csv"))
  cat(
    "  [cat] enfermedades multi-hot →", nrow(d_enf),
    "enfermedades | co-ocurrencia en _n_enfermedades_reum.csv\n"
  )
}

# Perfil de PROCEDIMIENTOS por área (CIE-9-MC) — flag "tuvo ≥1 proc del área"
COLS_PROC <- intersect(paste0("PROCEDIMIENTO", 1:30), names(df))
if (length(COLS_PROC) > 0) {
  area_proc <- function(x) {
    n <- floor(suppressWarnings(as.numeric(x)))
    dplyr::case_when(
      is.na(n) ~ NA_character_,
      n >= 1 & n <= 5 ~ "NERVIOSO", n >= 6 & n <= 7 ~ "ENDOCRINO", n >= 8 & n <= 16 ~ "OJO",
      n >= 18 & n <= 20 ~ "OIDO", n >= 21 & n <= 29 ~ "ORL_BUCAL", n >= 30 & n <= 34 ~ "RESPIRATORIO",
      n >= 35 & n <= 39 ~ "CARDIOVASCULAR", n >= 40 & n <= 41 ~ "HEMOLINFATICO",
      n >= 42 & n <= 54 ~ "DIGESTIVO", n >= 55 & n <= 59 ~ "URINARIO", n >= 60 & n <= 71 ~ "GENITAL",
      n >= 72 & n <= 75 ~ "OBSTETRICO", n >= 76 & n <= 84 ~ "MUSCULOESQUELETICO",
      n >= 85 & n <= 86 ~ "PIEL", TRUE ~ "DX_TERAPEUTICO"
    )
  }
  mat_ap <- do.call(cbind, lapply(COLS_PROC, function(c) area_proc(df[[c]])))
  AREAS <- c(
    "NERVIOSO", "ENDOCRINO", "OJO", "OIDO", "ORL_BUCAL", "RESPIRATORIO",
    "CARDIOVASCULAR", "HEMOLINFATICO", "DIGESTIVO", "URINARIO", "GENITAL",
    "OBSTETRICO", "MUSCULOESQUELETICO", "PIEL", "DX_TERAPEUTICO"
  )
  d_ap <- bind_rows(lapply(AREAS, function(a) {
    tiene <- rowSums(mat_ap == a, na.rm = TRUE) > 0
    tibble(
      area = a, n_con_proc = sum(tiene),
      pct_global = round(mean(tiene) * 100, 2),
      pct_reum = round(mean(tiene[df$.es_reum == 1]) * 100, 2),
      pct_no_reum = round(mean(tiene[df$.es_reum == 0]) * 100, 2),
      lift = round(mean(tiene[df$.es_reum == 1]) / mean(tiene), 2)
    )
  })) |> arrange(desc(n_con_proc))
  readr::write_csv(d_ap, file.path(DIR_AN, "cat_GRUPO_area_procedimiento.csv"))
  cat("  [cat] área procedimiento (CIE-9-MC) →", nrow(d_ap), "áreas\n")
}

# Consolidado de lift por categoría (para ver qué categorías discriminan)
lift_tbl <- bind_rows(lift_all) |>
  select(variable, cat, n_global, n_reum, pct_col, pct_reum_en_categoria, lift) |>
  arrange(variable, desc(n_global))
readr::write_csv(lift_tbl, file.path(DIR_AN, "_lift_categorias.csv"))


# =============================================================================
# 2. VARIABLES NUMÉRICAS — estadística por grupo
# =============================================================================
cat("\n== NUMÉRICAS ==\n")

# Derivadas que conviene analizar
# parse robusto: 2023 viene en dd-mm-yyyy → fallback dmy (igual que el Módulo 05)
parse_fecha6 <- function(x) {
  d <- suppressWarnings(lubridate::ymd(x))
  f <- is.na(d) & !is.na(x) & x != ""
  d[f] <- suppressWarnings(lubridate::dmy(x[f]))
  d
}
edad <- as.numeric(difftime(parse_fecha6(df$FECHA_INGRESO),
  parse_fecha6(df$FECHA_NACIMIENTO),
  units = "days"
)) / 365.25
edad[edad < 0 | edad > 120] <- NA
n_diag <- rowSums(!is.na(df[, COLS_DIAG, drop = FALSE]))
COLS_PROC <- intersect(paste0("PROCEDIMIENTO", 1:30), names(df))
n_proc <- rowSums(!is.na(df[, COLS_PROC, drop = FALSE]))
COLS_STR <- intersect(paste0("SERVICIOTRASLADO", 1:9), names(df))
n_tras <- rowSums(!is.na(df[, COLS_STR, drop = FALSE]))

num_list <- list(
  resumen_num(edad, "edad"),
  resumen_num(n_diag, "n_diagnosticos"),
  resumen_num(n_proc, "n_procedimientos"),
  resumen_num(n_tras, "n_traslados"),
  resumen_num(df$IR_29301_PESO, "IR_29301_PESO"),
  resumen_num(df$IR_29301_SEVERIDAD, "IR_29301_SEVERIDAD"),
  resumen_num(df$IR_29301_MORTALIDAD, "IR_29301_MORTALIDAD")
)
num_tbl <- bind_rows(num_list)
readr::write_csv(num_tbl, file.path(DIR_AN, "_resumen_numericas.csv"))
print(num_tbl)

# =============================================================================
# 3. REDUNDANCIA / COLINEALIDAD — sobre el dataset PRE-ENCODING (features modelo)
#    (a) correlación de Pearson entre numéricas  → pares |r| > 0.80
#    (b) VIF (Variance Inflation Factor)          → VIF > 5 (atención), > 10 (grave)
#    (c) V de Cramér entre categóricas            → asociación entre predictores
#    Responde directamente "¿me quedo con esta variable o es redundante?".
# =============================================================================
cat("\n== REDUNDANCIA / COLINEALIDAD ==\n")
RUTA_BASE <- file.path(DIR_OUT, "datos_preprocesados.parquet")
if (!file.exists(RUTA_BASE)) {
  cat("  (Ejecuta 05 primero para generar", RUTA_BASE, ")\n")
} else {
  dfb <- arrow::read_parquet(RUTA_BASE)
  # Excluir caracterización (leakage) y control de los chequeos de features
  excl <- c(
    "grupo_paciente", "es_reum", "anio", "tipo_reum", "enfermedad_principal",
    "n_enfermedades_reum", grep("^reum_", names(dfb), value = TRUE)
  )
  feat <- setdiff(names(dfb), excl)
  num_cols <- feat[sapply(dfb[feat], is.numeric)]
  cat_cols <- feat[sapply(dfb[feat], function(c) is.character(c) || is.factor(c))]

  # Muestra para acelerar (la colinealidad es estructural, no depende de N)
  set.seed(1)
  idx <- sample(seq_len(nrow(dfb)), min(150000, nrow(dfb)))
  dnum <- dfb[idx, num_cols, drop = FALSE]

  # (a) Correlación de Pearson
  M <- suppressWarnings(cor(dnum, use = "pairwise.complete.obs"))
  Mu <- M
  Mu[lower.tri(Mu, diag = TRUE)] <- NA
  pares <- which(abs(Mu) > 0.80, arr.ind = TRUE)
  if (length(pares)) {
    red <- tibble(
      var_1 = rownames(Mu)[pares[, 1]], var_2 = colnames(Mu)[pares[, 2]],
      r = round(Mu[pares], 3)
    ) |> arrange(desc(abs(r)))
    readr::write_csv(red, file.path(DIR_AN, "_redundancia_pares.csv"))
    cat("  (a) Pares |r|>0.80:", nrow(red), "→ _redundancia_pares.csv\n")
    print(head(red, 12))
  } else {
    cat("  (a) Sin pares numéricos con |r|>0.80.\n")
  }

  # (b) VIF: VIF_j = 1/(1 - R²_j), regresando cada numérica sobre las demás
  vif_calc <- function(d) {
    d <- d[, sapply(d, function(c) sd(c, na.rm = TRUE) > 0), drop = FALSE] # quita constantes
    d <- d[stats::complete.cases(d), , drop = FALSE]
    vars <- names(d)
    sapply(vars, function(v) {
      r2 <- summary(stats::lm(stats::reformulate(setdiff(vars, v), v), data = d))$r.squared
      round(1 / (1 - min(r2, 0.999999)), 2)
    })
  }
  vif <- vif_calc(dnum)
  vif_df <- tibble(
    variable = names(vif), VIF = unname(vif),
    alerta = dplyr::case_when(vif > 10 ~ "GRAVE", vif > 5 ~ "ATENCION", TRUE ~ "ok")
  ) |>
    arrange(desc(VIF))
  readr::write_csv(vif_df, file.path(DIR_AN, "_vif_numericas.csv"))
  cat("  (b) VIF numéricas → _vif_numericas.csv (VIF>5 atención, >10 grave)\n")
  print(head(vif_df, 12))

  # (c) V de Cramér entre categóricas (sobre la muestra)
  cramer_v <- function(a, b) {
    t <- table(a, b)
    if (nrow(t) < 2 || ncol(t) < 2) {
      return(NA_real_)
    }
    chi <- suppressWarnings(chisq.test(t, correct = FALSE)$statistic)
    n <- sum(t)
    sqrt((chi / n) / max(1, min(nrow(t), ncol(t)) - 1))
  }
  if (length(cat_cols) >= 2) {
    dcat <- dfb[idx, cat_cols, drop = FALSE]
    cv <- expand.grid |>
      dplyr::filter |>
      dplyr::mutate(V_cramer = mapply(function(a, b) round(cramer_v(dcat[[a]], dcat[[b]]), 3), v1, v2)) |>
      dplyr::arrange(dplyr::desc(V_cramer))
    readr::write_csv(cv, file.path(DIR_AN, "_cramerv_categoricas.csv"))
    cat("  (c) V de Cramér entre categóricas → _cramerv_categoricas.csv\n")
    print(head(cv, 12))
  }
}

# =============================================================================
# 4. EVIDENCIA DE UTILIDAD DE LOS REINGRESOS (desenlace operativo)
# (a) es_reingreso reum vs general (chi² + Odds Ratio)
# (b) dentro de reum, reingreso_30d vs severidad/PESO (Wilcoxon)
# (c) reingreso_30d por enfermedad
# Requiere que 05  ya haya generado datos_preprocesados.parquet.
# =============================================================================
cat("\n== EVIDENCIA REINGRESOS ==\n")
RUTA_BASE2 <- file.path(DIR_OUT, "datos_preprocesados.parquet")
tiene_reingresos <- file.exists(RUTA_BASE2) &&
  all(c("n_hosp_previas", "reingreso_30d") %in%
    names(arrow::read_parquet(RUTA_BASE2, as_data_frame = FALSE)))
if (tiene_reingresos) {
  db <- arrow::read_parquet(RUTA_BASE2)
  db$.reum <- as.integer(db$grupo_paciente == "Reumatológico")
  db$es_reingreso <- as.integer(db$n_hosp_previas > 0) # derivado (es_reingreso se descartó por redundancia)
  # (a) es_reingreso ~ reum
  ct <- table(db$.reum, db$es_reingreso)
  if (all(dim(ct) == c(2, 2))) {
    chi <- suppressWarnings(chisq.test(ct))
    ct <- matrix(as.numeric(ct), nrow = 2) # evita overflow de enteros (conteos en millones)
    or <- (ct[2, 2] * ct[1, 1]) / (ct[2, 1] * ct[1, 2])
    cat(sprintf(
      "(a) es_reingreso: reum=%.1f%% vs general=%.1f%% | chi2 p=%.2e | OR=%.2f\n",
      mean(db$es_reingreso[db$.reum == 1], na.rm = TRUE) * 100,
      mean(db$es_reingreso[db$.reum == 0], na.rm = TRUE) * 100, chi$p.value, or
    ))
  }
  # (b) reingreso_30d vs severidad/PESO dentro de reum
  r <- db[db$.reum == 1, ]
  for (v in intersect(c("IR_29301_SEVERIDAD", "IR_29301_PESO"), names(r))) {
    x <- as.numeric(r[[v]])[r$reingreso_30d == 1]
    y <- as.numeric(r[[v]])[r$reingreso_30d == 0]
    p <- suppressWarnings(wilcox.test(x, y)$p.value)
    cat(sprintf(
      "(b) %s: reingresó=%.2f vs no=%.2f | Wilcoxon p=%.2e\n",
      v, mean(x, na.rm = TRUE), mean(y, na.rm = TRUE), p
    ))
  }
  # (c) reingreso_30d por enfermedad
  enf_cols <- grep("^reum_", names(db), value = TRUE)
  ev <- lapply(enf_cols, function(c) {
    m <- db[[c]] == 1 & db$.reum == 1
    if (sum(m, na.rm = TRUE) < 200) {
      return(NULL)
    }
    data.frame(
      enfermedad = sub("^reum_", "", c), n = sum(m, na.rm = TRUE),
      reingreso_30d_pct = round(mean(db$reingreso_30d[m], na.rm = TRUE) * 100, 1)
    )
  })
  ev <- do.call(rbind, ev)
  ev <- ev[order(-ev$reingreso_30d_pct), ]
  readr::write_csv(ev, file.path(DIR_AN, "_reingreso_por_enfermedad.csv"))
  cat("(c) reingreso_30d por enfermedad → _reingreso_por_enfermedad.csv (rango ",
    min(ev$reingreso_30d_pct), "–", max(ev$reingreso_30d_pct), "%)\n",
    sep = ""
  )
} else {
  cat("  (Vuelve a correr 05 v2 para generar reingreso_30d/es_reingreso y medir su utilidad.)\n")
}

cat("\n✓ Análisis completado. Resultados en:", DIR_AN, "\n")
cat("  · cat_<VARIABLE>.csv        → frecuencias global vs reum por categoría\n")
cat("  · _lift_categorias.csv      → poder discriminante (lift) de cada categoría\n")
cat("  · _resumen_numericas.csv    → estadística de numéricas por grupo\n")
cat("  · cat_GRUPO_*.csv           → validación de las agrupaciones propuestas\n")
cat("  · _redundancia_pares.csv    → pares numéricos |r|>0.80 (colinealidad)\n")
cat("  · _vif_numericas.csv        → VIF por variable (>5 atención, >10 grave)\n")
cat("  · _cramerv_categoricas.csv  → V de Cramér entre predictores categóricos\n")
cat("  · _reingreso_por_enfermedad.csv → tasa de reingreso 30d por enfermedad\n")
