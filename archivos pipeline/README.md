# Caracterización de pacientes reumatológicos con GRD y aprendizaje automático

Código del trabajo de título *"Caracterización computacional de diagnósticos reumatológicos en
hospitales chilenos mediante atributos GRD y aprendizaje automático"* (USACH, Diego Oliva López;
prof. guía: Manuel Villalobos Cid).

Pipeline reproducible que, a partir de los registros GRD públicos de FONASA (2019–2024), construye una
cohorte reumatológica, entrena modelos supervisados interpretables (regresión logística, random forest,
XGBoost) por enfermedad, los explica con SHAP y cuantifica indicadores de gestión.

## Datos

Los archivos de origen **no se incluyen** (datos públicos de FONASA, pesados). Se descargan del portal
de datos abiertos de FONASA (<https://datosabiertos.fonasa.cl/>) y su integridad se verifica por su
suma **SHA-256** (ver la tabla de procedencia en la tesis). Colocar los seis `GRD_PUBLICO_20XX.txt`
en `datos crudos/`.

## Reproducibilidad

- **Semilla global:** `SEED = 42`.
- **Python:** `pip install -r requirements.txt` (scikit-learn 1.9.0, xgboost 3.4.0, shap 0.52.0, etc.).
  Para las curvas del anexo: `pip install matplotlib`.
- **R:** entorno fijado en `renv.lock` (R 4.5.0); restaurar con `renv::restore()`.

## Orden de ejecución

**Etapa 1 — Preprocesamiento (R)**
`01_txt_to_parquet.R` → `05_preprocesamiento.R`.

**Etapa 2 — EDA y descriptiva (R / Quarto)**
`02_eda_cardinalidad.qmd`, `03_eda_columnas.qmd`, `04_analisis_estadistico.qmd` (documentos Quarto con
código R), `06_analisis_agrupaciones.R`, `07_descriptiva_cohorte.R`.

**Etapa 3 — Modelado (Python)**
Pipeline orquestado por `00_orquestador_alt.py`, que corre en orden:
`07_modelado_split.py` → `08_features.py` → `09_tuning.py` → `10_entrenar_evaluar_alt.py` →
`11_shap_alt.py` → `12_resumen_alt.py` → `13_shap_resumen_alt.py`.
Salidas adicionales: `12_curvas.py` (curvas ROC/PR) y `14_desenlaces.py` (desenlaces).

**Etapa 4 — Análisis complementarios (Python, sobre las salidas del modelado)**
`15_ablacion_artrosis.py` (ablación de códigos de tratamiento), `16_estabilidad_atributos.py` y
`17_estabilidad_iteraciones.py` (estabilidad de atributos), `18_estratificacion.py` (estratificación
por tramo/región/previsión), `19_atributos_prevalencia.py` (corroboración por razón de prevalencias),
`20_verificar_shap_alt.py` (verificación de las matrices SHAP) → `21_persona_anclaje.py` y `22_fig_anclaje.py` 
(comparación con otros trabajos)

Módulos compartidos (importados por los scripts de modelado): `_comun_alt.py`, `codigos_cie.py`.

## Dashboard

El prototipo de dashboard (OE4) se genera con `dashboard_agregados.py` (precalcula los agregados
suprimidos) y se explora con `dashboard/dashboard.html` (página estática; se abre en cualquier
navegador). *Incluir estos archivos junto a este repositorio.*

## Cita

Repositorio: [\[URL\], etiqueta \[vX.Y\]. Datos: registros GRD públicos, FONASA (2019–2024).](https://public.tableau.com/views/PropuestaTableroGRD/PropuestaTableroGRD?%3AshowVizHome=no#1)
