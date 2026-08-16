# ==============================================================================
# 07_descriptiva_cohorte.R
# Caracterización descriptiva de la cohorte reumatológica (observación C6)
# Autor: Diego Oliva López | USACH
# Proyecto GRD Chile 2019–2024 — USACH · Diego Oliva López
#
# Entrega COMPLETA (tú seleccionas qué llevar a la tesis). Dos niveles:
#   (A) RESUMEN por enfermedad  -> 1 fila por enfermedad, todo lo esencial junto.
#   (B) DETALLE por enfermedad  -> tablas largas por dimensión (filtrables):
#       edad, región, previsión, tipo de ingreso, tipo de alta, año y
#       comorbilidades por capítulo CIE-10.
#   (+) RESUMEN global de la cohorte.
#
# Cubre el mínimo del profesor (n por enfermedad, edad, sexo, estancia, región,
# año) MÁS severidad y riesgo de mortalidad (APR-DRG), % urgencia, % cirugía,
# peso GRD, tipo de alta/fallecidos, previsión y comorbilidades por capítulo.
# Respeta C2 (posición: primeras-3) y C3 (tramos de Vásquez). Usa los 6 años.
#
# NOTA C4: la variable derivada por enlace de paciente (reingreso_30d) queda
# COMENTADA (decisión pendiente con el profesor). Descomentar para reactivar.
#
# GUARDADO ROBUSTO: cada CSV es independiente y reporta OK / FALLÓ, de modo que
# un fallo en un bloque no impide generar los demás.
#
# USO: ejecutar desde CLAUDE/ (requiere _codigos_cie.R y output/datos_preprocesados.parquet).
#      Genera los CSV en output/descriptiva/  (se imprime la ruta absoluta al final).
# ==============================================================================

suppressPackageStartupMessages({
  library(arrow)
  library(dplyr)
  library(tidyr)
  library(purrr)
  library(readr)
  library(stringr)
})

RUTA_BASE <- "output/datos_preprocesados.parquet"
DIR_OUT <- "output/descriptiva"
if (!dir.exists(DIR_OUT)) dir.create(DIR_OUT, recursive = TRUE)

source("_codigos_cie.R")
ENF <- names(CODIGOS_REUMATICOS)
norm <- function(x) toupper(trimws(as.character(x)))
CODES <- lapply(CODIGOS_REUMATICOS, norm)

# ── Selección robusta de columnas (incluye los capítulos dxcap_ dinámicamente) ─
all_cols <- names(arrow::open_dataset(RUTA_BASE))
dxcap_cols <- grep("^dxcap_", all_cols, value = TRUE)
pedidas <- c(
  paste0("DIAGNOSTICO", 1:3), paste0("reum_", ENF), "enfermedad_principal",
  "edad", "sexo", "region", "duracion_hospitalizacion",
  "IR_29301_PESO", "IR_29301_SEVERIDAD", "IR_29301_MORTALIDAD",
  "n_diagnosticos", "n_procedimientos", "n_enfermedades_reum",
  "flag_intervencion", "flag_pabellon", "TIPO_INGRESO", "TIPOALTA",
  "PREVISION", "reingreso_30d", "anio"
)
cols <- intersect(c(pedidas, dxcap_cols), all_cols)
df <- as.data.frame(arrow::read_parquet(RUTA_BASE, col_select = all_of(cols)))
n_base <- nrow(df)
cat(sprintf("Base: %s episodios | %d columnas leídas\n", format(n_base, big.mark = "."), ncol(df)))

D1 <- norm(df$DIAGNOSTICO1)
D2 <- norm(df$DIAGNOSTICO2)
D3 <- norm(df$DIAGNOSTICO3)
df$tramo <- dplyr::case_when(
  is.na(df$edad) ~ NA_character_, df$edad <= 18 ~ "0-18", df$edad <= 30 ~ "19-30",
  df$edad <= 45 ~ "31-45", df$edad <= 60 ~ "45-60", TRUE ~ ">60"
)

in_prin <- setNames(lapply(ENF, function(g) trimws(as.character(df$enfermedad_principal)) == g), ENF)
in_p3 <- setNames(lapply(ENF, function(g) {
  (D1 %in% CODES[[g]]) | (D2 %in% CODES[[g]]) | (D3 %in% CODES[[g]])
}), ENF)
coh_p3 <- Reduce(`|`, in_p3)

med <- function(x) median(as.numeric(x), na.rm = TRUE)
q1 <- function(x) as.numeric(quantile(as.numeric(x), .25, na.rm = TRUE))
q3 <- function(x) as.numeric(quantile(as.numeric(x), .75, na.rm = TRUE))
pct <- function(lgl) round(mean(lgl, na.rm = TRUE) * 100, 1)
pct_match <- function(x, pat) round(mean(grepl(pat, norm(x)), na.rm = TRUE) * 100, 1)

# ── Guardado robusto: evalúa la tabla dentro de tryCatch y reporta OK/FALLÓ ───
guardar <- function(expr, nombre) {
  tryCatch(
    {
      readr::write_csv(expr, file.path(DIR_OUT, nombre))
      cat("  OK    ->", nombre, "\n")
    },
    error = function(e) cat("  FALLÓ ->", nombre, ":", conditionMessage(e), "\n")
  )
}

# ── (A) RESUMEN por enfermedad (1 fila) ──────────────────────────────────────
guardar(
  purrr::map_dfr(ENF, function(g) {
    s <- df[in_p3[[g]], ]
    tibble::tibble(
      enfermedad = g,
      n_principal = sum(in_prin[[g]], na.rm = TRUE),
      n_primeras3 = sum(in_p3[[g]], na.rm = TRUE),
      n_total = sum(df[[paste0("reum_", g)]], na.rm = TRUE),
      edad_mediana = med(s$edad), edad_q1 = q1(s$edad), edad_q3 = q3(s$edad),
      pct_mujer = pct(s$sexo == 0),
      pct_urgencia = pct_match(s$TIPO_INGRESO, "URG"),
      pct_cirugia = pct(s$flag_intervencion == 1),
      los_mediana = med(s$duracion_hospitalizacion),
      los_q1 = q1(s$duracion_hospitalizacion), los_q3 = q3(s$duracion_hospitalizacion),
      peso_mediana = round(med(s$IR_29301_PESO), 2),
      severidad_mediana = med(s$IR_29301_SEVERIDAD),
      riesgo_mort_mediana = med(s$IR_29301_MORTALIDAD),
      pct_fallecido = pct_match(s$TIPOALTA, "FALLE|MUERT|DEF"),
      # reingreso30_pct = pct(s$reingreso_30d == 1),   # COMENTADO — punto C4 (derivada por enlace; pendiente). Descomentar para reactivar.
      n_proc_mediana = med(s$n_procedimientos),
      n_diag_mediana = med(s$n_diagnosticos),
      n_enf_reum_mediana = med(s$n_enfermedades_reum)
    )
  }) |> arrange(desc(n_primeras3)),
  "desc_resumen_por_enfermedad.csv"
) -> resumen_guardado

# guardar también en objeto para imprimir al final
resumen <- purrr::map_dfr(ENF, function(g) {
  s <- df[in_p3[[g]], ]
  tibble::tibble(
    enfermedad = g, n_primeras3 = sum(in_p3[[g]], na.rm = TRUE),
    edad_mediana = med(s$edad), pct_mujer = pct(s$sexo == 0),
    los_mediana = med(s$duracion_hospitalizacion),
    severidad_mediana = med(s$IR_29301_SEVERIDAD)
  )
}) |> arrange(desc(n_primeras3))

# ── (B) DETALLE por enfermedad — tablas largas ───────────────────────────────
tabla_cat <- function(colname) {
  purrr::map_dfr(ENF, function(g) {
    v <- as.character(df[[colname]][in_p3[[g]]])
    tibble::tibble(cat = v) |>
      dplyr::filter(!is.na(cat) & cat != "") |>
      dplyr::count(cat, name = "n") |>
      dplyr::arrange(dplyr::desc(n)) |>
      dplyr::mutate(enfermedad = g, pct = round(100 * n / sum(n), 1)) |>
      dplyr::select(enfermedad, categoria = cat, n, pct)
  })
}

# edad por tramo
guardar(purrr::map_dfr(ENF, function(g) {
  tr <- factor(df$tramo[in_p3[[g]]], levels = c("0-18", "19-30", "31-45", "45-60", ">60"))
  d <- as.data.frame(table(tr))
  tibble::tibble(
    enfermedad = g, tramo = as.character(d$tr), n = d$Freq,
    pct = round(100 * d$Freq / sum(d$Freq), 1)
  )
}), "desc_detalle_edad_por_enfermedad.csv")

guardar(tabla_cat("region"), "desc_detalle_region_por_enfermedad.csv")
guardar(tabla_cat("PREVISION"), "desc_detalle_prevision_por_enfermedad.csv")
guardar(tabla_cat("TIPO_INGRESO"), "desc_detalle_tipo_ingreso_por_enfermedad.csv")
guardar(tabla_cat("TIPOALTA"), "desc_detalle_tipo_alta_por_enfermedad.csv")

# año por enfermedad (tendencia)
guardar(
  purrr::map_dfr(ENF, function(g) {
    tibble::tibble(anio = df$anio[in_p3[[g]]]) |>
      dplyr::count(anio, name = "n") |>
      dplyr::mutate(enfermedad = g) |>
      dplyr::select(enfermedad, anio, n)
  }),
  "desc_detalle_anio_por_enfermedad.csv"
)

# comorbilidades por capítulo CIE-10 (frecuencia intrahospitalaria) — OE3
if (length(dxcap_cols) > 0) {
  guardar(
    purrr::map_dfr(ENF, function(g) {
      m <- df[in_p3[[g]], dxcap_cols, drop = FALSE]
      tibble::tibble(
        enfermedad = g, capitulo = dxcap_cols,
        pct = round(colMeans(data.matrix(m), na.rm = TRUE) * 100, 1)
      )
    }) |> dplyr::arrange(enfermedad, dplyr::desc(pct)),
    "desc_detalle_comorbilidad_capitulo_por_enfermedad.csv"
  )
}

# ── (+) RESUMEN global de la cohorte (primeras-3) ────────────────────────────
guardar(local({
  s <- df[coh_p3, ]
  tibble::tibble(
    n_base = n_base, n_cohorte_primeras3 = nrow(s),
    pct_cohorte = round(100 * nrow(s) / n_base, 2),
    edad_mediana = med(s$edad), pct_mujer = pct(s$sexo == 0),
    pct_urgencia = pct_match(s$TIPO_INGRESO, "URG"), pct_cirugia = pct(s$flag_intervencion == 1),
    los_mediana = med(s$duracion_hospitalizacion),
    severidad_mediana = med(s$IR_29301_SEVERIDAD),
    pct_fallecido = pct_match(s$TIPOALTA, "FALLE|MUERT|DEF"),
    # reingreso30_pct = pct(s$reingreso_30d == 1),   # COMENTADO — punto C4
    pct_pediatrico = pct(s$tramo == "0-18")
  )
}), "desc_resumen_cohorte.csv")

cat("\nListo. Los CSV están en:\n  ", normalizePath(DIR_OUT), "\n")
print(resumen)
