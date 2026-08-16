# ==============================================================================
# MÓDULO 1: CONVERSIÓN TXT → PARQUET
# Autor: Diego Oliva López | USACH
# Descripción: Lee cada archivo TXT y lo convierte a Parquet columnar usando arrow.
# ==============================================================================

suppressPackageStartupMessages({
  library(arrow) # write_parquet
  library(readr) # lectura principal (robusto con encodings)
  library(dplyr)
  library(stringr)
})

# ==============================================================================
# SECCIÓN A: CONFIGURACIÓN — ajustar estas rutas antes de ejecutar
# ==============================================================================

# Carpeta donde están los TXT originales de FONASA
DIR_RAW <- "datos crudos"

# Carpeta de salida para los Parquet. Se crea si no existe.
DIR_PARQ <- "parquet"

# Tabla de archivos por año:
#   anio        → etiqueta de año
#   archivo_txt → nombre del archivo dentro de DIR_RAW
#   col_id      → columna de identificador de paciente en ese año
#
# NOTA: 2023 usa el mismo col_id que 2019–2022 según el diccionario FONASA.
# Si FONASA corrige o publica una versión 2023 con diferente esquema, actualizar.
ARCHIVOS_GRD <- tibble::tribble(
  ~anio, ~archivo_txt, ~col_id,
  2019L, "GRD_PUBLICO_2019.txt", "CIP_ENCRIPTADO",
  2020L, "GRD_PUBLICO_2020.txt", "CIP_ENCRIPTADO",
  2021L, "GRD_PUBLICO_2021.txt", "CIP_ENCRIPTADO",
  2022L, "GRD_PUBLICO_2022.txt", "CIP_ENCRIPTADO",
  2023L, "GRD_PUBLICO_2023.txt", "CIP_ENCRIPTADO",
  2024L, "GRD_PUBLICO_2024.txt", "ID_BENEFICIARIO"
)

# Lista de encodings para el fallback de detección
ENCODINGS_A_PROBAR <- c(
  "UTF-8", "UTF-8-BOM",
  "UTF-16LE", "UTF-16BE", "UTF-16",
  "UTF-32LE", "UTF-32BE", "UTF-32",
  "Windows-1252", "Windows-1250", "Windows-1251",
  "ISO-8859-1", "ISO-8859-15", "ISO-8859-2",
  "CP850", "CP437",
  "macintosh"
)

# ==============================================================================
# SECCIÓN B: FUNCIONES AUXILIARES
# ==============================================================================

# ── B1: Detecta el encoding del archivo analizando sus bytes ──────────────────
detectar_encoding <- function(ruta, n_bytes = 1e6, umbral_confianza = 0.70) {
  cat("  Analizando bytes para identificar encoding...\n")

  # ── Paso 1: análisis estadístico de bytes ────────────────────────────────────
  candidatos <- tryCatch(
    readr::guess_encoding(ruta, n_max = n_bytes),
    error = function(e) {
      cat(sprintf(
        "  [WARN] guess_encoding falló (%s). Usando lista de respaldo.\n",
        e$message
      ))
      NULL
    }
  )

  if (!is.null(candidatos) && nrow(candidatos) > 0) {
    # Mostrar todos los candidatos con su confianza (útil para auditoría)
    cat("  Candidatos detectados por análisis de bytes:\n")
    for (i in seq_len(nrow(candidatos))) {
      cat(sprintf(
        "    %d. %-20s  confianza: %.0f%%\n",
        i, candidatos$encoding[i], candidatos$confidence[i] * 100
      ))
    }

    # Intentar cada candidato en orden de confianza
    for (i in seq_len(nrow(candidatos))) {
      enc <- candidatos$encoding[i]
      conf <- candidatos$confidence[i]

      valido <- tryCatch(
        {
          df_test <- readr::read_delim(
            ruta,
            delim = "|",
            col_types = readr::cols(.default = "c"),
            locale = readr::locale(encoding = enc),
            n_max = 5000,
            progress = FALSE, show_col_types = FALSE
          )
          nrow(df_test) > 0
        },
        error = function(e) FALSE
      )

      if (valido) {
        cat(sprintf(
          "  -> Encoding seleccionado: %s (confianza: %.0f%%)\n",
          enc, conf * 100
        ))
        if (conf < umbral_confianza) {
          cat(sprintf(
            "  [AVISO] Confianza %.0f%% < umbral %.0f%%. ",
            conf * 100, umbral_confianza * 100
          ))
          cat("Verificar manualmente que acentos y ñ se ven bien en el Parquet.\n")
        }
        return(enc)
      }
    }

    cat("  [WARN] Ningún candidato del análisis pasó la validación. Usando lista de respaldo.\n")
  }

  # ── Paso 2: fuerza bruta con encodings comunes para FONASA (fallback) ────────
  cat("  Probando lista de respaldo...\n")
  for (enc in ENCODINGS_A_PROBAR) {
    df_prueba <- tryCatch(
      readr::read_delim(
        ruta,
        delim = "|",
        col_types = readr::cols(.default = "c"),
        locale = readr::locale(encoding = enc),
        n_max = 50000,
        progress = FALSE, show_col_types = FALSE
      ),
      error = function(e) NULL
    )
    if (!is.null(df_prueba) && nrow(df_prueba) > 0) {
      cat(sprintf("  -> Encoding confirmado por respaldo: %s\n", enc))
      return(enc)
    }
  }

  stop("No se pudo determinar el encoding del archivo: ", ruta)
}

# ── B2: Lee el TXT completo con readr usando el encoding detectado ─────────────
leer_txt_grd <- function(ruta, encoding_detectado) {
  cat(sprintf("  -> Leyendo con readr (encoding: %s)...\n", encoding_detectado))

  readr::read_delim(
    ruta,
    delim = "|",
    col_types = readr::cols(.default = "c"),
    locale = readr::locale(encoding = encoding_detectado),
    progress = TRUE, show_col_types = FALSE
  )
}

# ── B3: Sanitización UTF-8 defensiva ──────────────────────────────────────────
sanitizar_utf8 <- function(df) {
  cols_char <- names(df)[sapply(df, is.character)]
  if (length(cols_char) == 0L) {
    return(df)
  }
  df |> dplyr::mutate(
    dplyr::across(
      dplyr::all_of(cols_char),
      ~ iconv(.x, from = "UTF-8", to = "UTF-8", sub = "?")
    )
  )
}

# ── B4: Normaliza nombres de columnas ─────────────────────────────────────────
normalizar_columnas <- function(df, col_id, anio) {
  # Normalizar nombres a mayúsculas para evitar inconsistencias entre años
  colnames(df) <- toupper(colnames(df))
  col_id <- toupper(col_id)

  # Renombrar ID fuente → nombre canónico
  if (col_id %in% colnames(df)) {
    df <- dplyr::rename(df, ID_PACIENTE = dplyr::all_of(col_id))
  } else {
    stop(sprintf("La columna ID '%s' no existe en el archivo del año %d.", col_id, anio))
  }

  # Forzar todo a character (ya viene así de readr, pero es una garantía explícita)
  df <- dplyr::mutate(df, dplyr::across(dplyr::everything(), as.character))

  df
}

# ── B5: Escribe el Parquet con compresión SNAPPY ──────────────────────────────
escribir_parquet <- function(df, ruta_salida) {
  arrow::write_parquet(
    df,
    sink        = ruta_salida,
    compression = "snappy", # SNAPPY: muy rápido en lectura, tamaño razonable
    version     = "2.6" # compatible con R, Python (pandas/polars), DuckDB
  )
  cat(sprintf(
    "  -> Guardado: %s (%.1f MB)\n",
    basename(ruta_salida),
    file.size(ruta_salida) / 1e6
  ))
}

# ==============================================================================
# SECCIÓN C: PIPELINE PRINCIPAL
# ==============================================================================

convertir_todos_a_parquet <- function() {
  # Crear directorio de salida si no existe
  if (!dir.exists(DIR_PARQ)) {
    dir.create(DIR_PARQ, recursive = TRUE)
    cat(sprintf("[INFO] Directorio creado: %s\n", DIR_PARQ))
  }

  cat(paste0("\n", strrep("=", 70), "\n"))
  cat("  CONVERSIÓN TXT → PARQUET  |  GRD Chile 2019–2024\n")
  cat(paste0(strrep("=", 70), "\n\n"))

  resumen <- vector("list", nrow(ARCHIVOS_GRD))

  for (i in seq_len(nrow(ARCHIVOS_GRD))) {
    anio <- ARCHIVOS_GRD$anio[i]
    archivo <- ARCHIVOS_GRD$archivo_txt[i]
    col_id <- ARCHIVOS_GRD$col_id[i]
    ruta_txt <- file.path(DIR_RAW, archivo)
    ruta_pqt <- file.path(DIR_PARQ, sprintf("GRD_%d.parquet", anio))

    cat(sprintf("[%d/%d] Procesando año %d\n", i, nrow(ARCHIVOS_GRD), anio))
    cat(sprintf("  Fuente : %s\n", ruta_txt))

    # ── Verificar existencia ──────────────────────────────────────────────────
    if (!file.exists(ruta_txt)) {
      cat(sprintf("  [OMITIDO] Archivo no encontrado: %s\n\n", ruta_txt))
      resumen[[i]] <- tibble::tibble(
        anio = anio, estado = "no_encontrado",
        n_filas = NA_integer_, n_cols = NA_integer_,
        mb_parquet = NA_real_
      )
      next
    }

    # ── Si ya existe el Parquet, saltear (modo incremental) ───────────────────
    if (file.exists(ruta_pqt)) {
      cat(sprintf("  [EXISTENTE] Ya existe %s. Saltando.\n", basename(ruta_pqt)))
      cat("  Para forzar reconversión, elimina el .parquet y vuelve a ejecutar.\n\n")
      resumen[[i]] <- tibble::tibble(
        anio = anio, estado = "ya_existe",
        n_filas = NA_integer_, n_cols = NA_integer_,
        mb_parquet = file.size(ruta_pqt) / 1e6
      )
      next
    }

    # ── Detectar encoding ─────────────────────────────────────────────────────
    cat("  Detectando encoding...\n")
    enc_ok <- tryCatch(
      detectar_encoding(ruta_txt),
      error = function(e) {
        cat(sprintf("  [ERROR] %s\n\n", e$message))
        NULL
      }
    )
    if (is.null(enc_ok)) {
      resumen[[i]] <- tibble::tibble(
        anio = anio, estado = "error_encoding",
        n_filas = NA_integer_, n_cols = NA_integer_,
        mb_parquet = NA_real_
      )
      next
    }
    cat(sprintf("  Encoding detectado: %s\n", enc_ok))

    # ── Leer TXT ──────────────────────────────────────────────────────────────
    t0 <- proc.time()
    df <- tryCatch(
      leer_txt_grd(ruta_txt, enc_ok),
      error = function(e) {
        cat(sprintf("  [ERROR] Lectura fallida: %s\n\n", e$message))
        NULL
      }
    )
    if (is.null(df)) {
      resumen[[i]] <- tibble::tibble(
        anio = anio, estado = "error_lectura",
        n_filas = NA_integer_, n_cols = NA_integer_,
        mb_parquet = NA_real_
      )
      next
    }
    t_lect <- (proc.time() - t0)[["elapsed"]]
    cat(sprintf(
      "  Leídas %s filas x %d columnas en %.1f s\n",
      format(nrow(df), big.mark = ","), ncol(df), t_lect
    ))

    # ── Normalizar columnas ───────────────────────────────────────────────────
    df <- tryCatch(
      normalizar_columnas(df, col_id, anio),
      error = function(e) {
        cat(sprintf("  [ERROR] Normalización: %s\n\n", e$message))
        NULL
      }
    )
    if (is.null(df)) {
      resumen[[i]] <- tibble::tibble(
        anio = anio, estado = "error_normalizacion",
        n_filas = NA_integer_, n_cols = NA_integer_,
        mb_parquet = NA_real_
      )
      next
    }

    # ── Sanitizar UTF-8 ───────────────────────────────────────────────────────
    cat("  Sanitizando UTF-8...\n")
    df <- sanitizar_utf8(df)

    # ── Escribir Parquet ──────────────────────────────────────────────────────
    t0 <- proc.time()
    tryCatch(
      escribir_parquet(df, ruta_pqt),
      error = function(e) {
        cat(sprintf("  [ERROR] Escritura Parquet: %s\n\n", e$message))
        return(NULL)
      }
    )
    t_escr <- (proc.time() - t0)[["elapsed"]]
    cat(sprintf("  Escrito en %.1f s\n\n", t_escr))

    resumen[[i]] <- tibble::tibble(
      anio       = anio,
      estado     = "ok",
      n_filas    = nrow(df),
      n_cols     = ncol(df),
      mb_parquet = file.size(ruta_pqt) / 1e6
    )

    rm(df)
    gc(verbose = FALSE)
  }

  # ── Tabla resumen final ────────────────────────────────────────────────────
  resumen_df <- dplyr::bind_rows(resumen)
  cat(paste0(strrep("-", 70), "\n"))
  cat("  RESUMEN FINAL\n")
  cat(paste0(strrep("-", 70), "\n"))
  print(resumen_df)
  cat(paste0(strrep("=", 70), "\n\n"))

  invisible(resumen_df)
}

# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================
# Este script se ejecuta automáticamente al hacer source("01_txt_to_parquet.R").
# Si solo necesitas cargar las funciones sin ejecutar (e.g., para testear),
# define SOLO_CARGAR_FUNCIONES <- TRUE antes de hacer source().

if (!exists("SOLO_CARGAR_FUNCIONES") || !isTRUE(SOLO_CARGAR_FUNCIONES)) {
  convertir_todos_a_parquet()
}


