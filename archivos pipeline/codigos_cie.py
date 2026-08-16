# ============================================================================
# codigos_cie.py
# Códigos CIE-10 para clasificación reumatológica — GRD Chile 2019–2024
# Autor: Diego Oliva López | USACH
#
# Convertido desde _codigos_cie.R conservando los comentarios clínicos.
# Lo importa 08_modelado.py para excluir, por enfermedad, los códigos que la
# definen (evita la fuga trivial de que el propio diagnóstico prediga el target).
# ============================================================================

CODIGOS_REUMATICOS = {
    # ==========================================================================
    # ARTRITIS REUMATOIDE (Seropositiva y Seronegativa)
    # ==========================================================================
    # Validado al 100% con el diccionario local. Incluye todas las ramificaciones
    # anatómicas de 5 dígitos para evitar cualquier pérdida de datos.
    "artritis_reumatoide": [
        # --- M05: ARTRITIS REUMATOIDE SEROPOSITIVA ---
        "M05",
        # M05.0: Síndrome de Felty
        "M05.0",
        "M05.00",
        "M05.01",
        "M05.02",
        "M05.03",
        "M05.04",
        "M05.05",
        "M05.06",
        "M05.07",
        "M05.08",
        "M05.09",
        # M05.1: Enfermedad reumatoide del pulmón
        "M05.1",
        "M05.10",
        "M05.11",
        "M05.12",
        "M05.13",
        "M05.14",
        "M05.15",
        "M05.16",
        "M05.17",
        "M05.18",
        "M05.19",
        # M05.2: Vasculitis reumatoide
        "M05.2",
        "M05.20",
        "M05.21",
        "M05.22",
        "M05.23",
        "M05.24",
        "M05.25",
        "M05.26",
        "M05.27",
        "M05.28",
        "M05.29",
        # M05.3: AR con compromiso de otros órganos
        "M05.3",
        "M05.30",
        "M05.31",
        "M05.32",
        "M05.33",
        "M05.34",
        "M05.35",
        "M05.36",
        "M05.37",
        "M05.38",
        "M05.39",
        # M05.8: Otras AR seropositivas
        "M05.8",
        "M05.80",
        "M05.81",
        "M05.82",
        "M05.83",
        "M05.84",
        "M05.85",
        "M05.86",
        "M05.87",
        "M05.88",
        "M05.89",
        # M05.9: AR seropositiva, sin otra especificación
        "M05.9",
        "M05.90",
        "M05.91",
        "M05.92",
        "M05.93",
        "M05.94",
        "M05.95",
        "M05.96",
        "M05.97",
        "M05.98",
        "M05.99",
        # --- M06: OTRAS ARTRITIS REUMATOIDES ---
        "M06",
        # M06.0: Artritis reumatoide seronegativa
        "M06.0",
        "M06.00",
        "M06.01",
        "M06.02",
        "M06.03",
        "M06.04",
        "M06.05",
        "M06.06",
        "M06.07",
        "M06.08",
        "M06.09",
        # M06.1: Enfermedad de Still de comienzo en el adulto
        "M06.1",
        "M06.10",
        "M06.11",
        "M06.12",
        "M06.13",
        "M06.14",
        "M06.15",
        "M06.16",
        "M06.17",
        "M06.18",
        "M06.19",
        # M06.2: Bursitis reumatoide
        "M06.2",
        "M06.20",
        "M06.21",
        "M06.22",
        "M06.23",
        "M06.24",
        "M06.25",
        "M06.26",
        "M06.27",
        "M06.28",
        "M06.29",
        # M06.3: Nódulo reumatoide
        "M06.3",
        "M06.30",
        "M06.31",
        "M06.32",
        "M06.33",
        "M06.34",
        "M06.35",
        "M06.36",
        "M06.37",
        "M06.38",
        "M06.39",
        # M06.4: Poliartropatía inflamatoria
        "M06.4",
        "M06.40",
        "M06.41",
        "M06.42",
        "M06.43",
        "M06.44",
        "M06.45",
        "M06.46",
        "M06.47",
        "M06.48",
        "M06.49",
        # M06.8: Otras AR especificadas
        "M06.8",
        "M06.80",
        "M06.81",
        "M06.82",
        "M06.83",
        "M06.84",
        "M06.85",
        "M06.86",
        "M06.87",
        "M06.88",
        "M06.89",
        # M06.9: Artritis reumatoide, no especificada
        # Nota: la secuencia termina en M06.98 según el diccionario local (M06.99 no existe).
        "M06.9",
        "M06.90",
        "M06.91",
        "M06.92",
        "M06.93",
        "M06.94",
        "M06.95",
        "M06.96",
        "M06.97",
        "M06.98",
    ],
    # ==========================================================================
    # LUPUS ERITEMATOSO SISTÉMICO
    # ==========================================================================
    # Validado al 100% con el diccionario. Sin códigos de 5 dígitos en este bloque.
    "lupus_eritematoso_sistemico": [
        "M32",  # Código raíz estructural
        "M32.0",  # Lupus eritematoso sistémico, inducido por drogas
        "M32.1",  # Lupus eritematoso sistémico con compromiso de órganos o sistemas
        "M32.8",  # Otras formas de lupus eritematoso sistémico
        "M32.9",  # Lupus eritematoso sistémico, sin otra especificación
    ],
    # ==========================================================================
    # ESPONDILITIS ANQUILOSANTE
    # ==========================================================================
    # Validado al 100% con el extracto del diccionario.
    "espondilitis_anquilosante": [
        "M45",  # Código principal de la enfermedad
        "M45.0",  # Espondilitis anquilosante, a designar sitio
        # Bloque de 5 dígitos (2 decimales):
        "M45.00",
        "M45.01",
        "M45.02",
        "M45.03",
        "M45.04",
        "M45.05",
        "M45.06",
        "M45.07",
        "M45.08",
        "M45.09",
        # Bloque alternativo de 4 dígitos (1 decimal):
        "M45.2",  # Región cervical
        "M45.3",  # Región cervicodorsal
        "M45.4",  # Región dorsal
        "M45.5",  # Región dorsolumbar
        "M45.6",  # Región lumbar
        "M45.7",  # Región lumbosacra
        "M45.8",  # Regiones sacra y sacrococcígea
        "M45.9",  # Localizaciones no especificadas
    ],
    # ==========================================================================
    # SÍNDROME DE SJÖGREN (SÍNDROME SECO)
    # ==========================================================================
    # Solo incluye la categoría principal por jerarquía y el único código decimal
    # existente para la enfermedad en el diccionario local.
    "sindrome_de_sjogren": [
        "M35",  # Categoría padre obligatoria
        "M35.0",  # Síndrome seco [Sjögren]
    ],
    # ==========================================================================
    # ARTRITIS / ARTROPATÍA PSORIÁSICA
    # ==========================================================================
    # Captura el espectro psoriásico (M07.0–M07.3) y el código dermatológico L40.5.
    # Descarta el bloque enteropático (.4, .5, .6) por no corresponder a psoriasis.
    "artritis_psoriasica": [
        # --- CÓDIGO CAPÍTULO PIEL ---
        "L40.5",  # Artropatía psoriásica (nexo clave desde dermatología)
        # --- CAPÍTULO MUSCULOESQUELÉTICO (M07) ---
        "M07",  # Código raíz
        # M07.0: Artropatía psoriásica interfalángica distal
        "M07.0",
        "M07.04",
        "M07.07",
        "M07.09",
        # M07.1: Artritis mutilante (secuencia completa de 5 dígitos del diccionario)
        "M07.1",
        "M07.10",
        "M07.11",
        "M07.12",
        "M07.13",
        "M07.14",
        "M07.15",
        "M07.16",
        "M07.17",
        "M07.18",
        "M07.19",
        # M07.2: Espondilitis psoriásica (solo las ramas existentes en el diccionario)
        "M07.2",
        "M07.28",
        "M07.29",
        # M07.3: Otras artropatías psoriásicas (secuencia completa de 5 dígitos)
        "M07.3",
        "M07.30",
        "M07.31",
        "M07.32",
        "M07.33",
        "M07.34",
        "M07.35",
        "M07.36",
        "M07.37",
        "M07.38",
        "M07.39",
    ],
    # ==========================================================================
    # ESCLERODERMIA (ESCLEROSIS SISTÉMICA)
    # ==========================================================================
    "esclerodermia": [
        "M34",  # Categoría principal
        "M34.0",  # Esclerosis sistémica progresiva
        "M34.1",  # Síndrome CR(E)ST
        "M34.2",  # Esclerosis sistémica inducida por drogas o productos químicos
        "M34.8",  # Otras formas de esclerosis sistémica
        "M34.9",  # Esclerosis sistémica, no especificada
    ],
    # ==========================================================================
    # VASCULITIS (sistémicas + cutáneas — se tratan como UNA sola familia)
    # ==========================================================================
    # Antes estaban separadas en vasculitis_sistemicas y vasculitis_cutaneas;
    # se unifican en un único grupo "vasculitis" (misma familia clínica; separarlas
    # fragmentaba casos ya escasos). Total de patologías reumatológicas: 14.
    "vasculitis": [
        # Categorías principales
        "M30",
        "M31",
        # Bloque M30: Poliarteritis nudosa y afecciones relacionadas
        "M30.0",  # Poliarteritis nudosa
        "M30.1",  # Poliarteritis con compromiso pulmonar [Churg-Strauss]
        "M30.2",  # Poliarteritis juvenil
        "M30.3",  # Síndrome mucocutáneo linfonodular [Kawasaki]
        "M30.8",  # Otras afecciones relacionadas con la poliarteritis nudosa
        # Bloque M31: Otras vasculopatías necrotizantes
        "M31.0",  # Angiítis debida a hipersensibilidad
        "M31.1",  # Microangiopatía trombótica
        "M31.2",  # Granuloma letal de la línea media
        "M31.3",  # Granulomatosis de Wegener
        "M31.4",  # Síndrome del cayado de la aorta [Takayasu]
        "M31.5",  # Arteritis de células gigantes con polimialgia reumática
        "M31.6",  # Otras arteritis de células gigantes
        "M31.7",  # Poliangiítis microscópica
        "M31.8",  # Otras vasculopatías necrotizantes especificadas
        "M31.9",  # Vasculopatía necrotizante, no especificada
        # Bloque D69: vasculitis inmunológica
        "D69.0",  # Púrpura alérgica (Vasculitis de Schönlein-Henoch)
        # Bloque L95: vasculitis limitadas a la piel (antes grupo aparte "cutáneas")
        "L95",  # Categoría principal
        "L95.0",  # Vasculitis livedoide
        "L95.1",  # Eritema elevatum diutinum
        "L95.8",  # Otras vasculitis limitadas a la piel
    ],
    # ==========================================================================
    # ARTROSIS / OSTEOARTRITIS
    # ==========================================================================
    "artrosis_osteoartritis": [
        # M15: POLIARTROSIS (Se detiene en 4 dígitos)
        "M15",
        "M15.0",
        "M15.1",
        "M15.2",
        "M15.3",
        "M15.4",
        "M15.8",
        "M15.9",
        # M16: COXARTROSIS [ARTROSIS DE LA CADERA] (Se detiene en 4 dígitos)
        "M16",
        "M16.0",
        "M16.1",
        "M16.2",
        "M16.3",
        "M16.4",
        "M16.5",
        "M16.6",
        "M16.7",
        "M16.9",
        # M17: GONARTROSIS [ARTROSIS DE LA RODILLA] (Se detiene en 4 dígitos)
        "M17",
        "M17.0",
        "M17.1",
        "M17.2",
        "M17.3",
        "M17.4",
        "M17.5",
        "M17.9",
        # M18: ARTROSIS DE LA PRIMERA ARTICULACIÓN CARPOMETACARPIANA (4 dígitos)
        "M18",
        "M18.0",
        "M18.1",
        "M18.2",
        "M18.3",
        "M18.4",
        "M18.5",
        "M18.9",
        # M19: OTRAS ARTROSIS (desglose de 5 dígitos / 2 decimales)
        "M19",
        # M19.0: Primaria
        "M19.0",
        "M19.00",
        "M19.01",
        "M19.02",
        "M19.03",
        "M19.04",
        "M19.05",
        "M19.06",
        "M19.07",
        "M19.08",
        "M19.09",
        # M19.1: Postraumática
        "M19.1",
        "M19.10",
        "M19.11",
        "M19.12",
        "M19.13",
        "M19.14",
        "M19.15",
        "M19.16",
        "M19.17",
        "M19.18",
        "M19.19",
        # M19.2: Otras secundarias
        "M19.2",
        "M19.20",
        "M19.21",
        "M19.22",
        "M19.23",
        "M19.24",
        "M19.25",
        "M19.26",
        "M19.27",
        "M19.28",
        "M19.29",
        # M19.8: Otras especificadas
        "M19.8",
        "M19.80",
        "M19.81",
        "M19.82",
        "M19.83",
        "M19.84",
        "M19.85",
        "M19.86",
        "M19.87",
        "M19.88",
        "M19.89",
        # M19.9: No especificada
        "M19.9",
        "M19.90",
        "M19.91",
        "M19.92",
        "M19.93",
        "M19.94",
        "M19.95",
        "M19.96",
        "M19.97",
        "M19.98",
        "M19.99",
    ],
    # ==========================================================================
    # FIBROMIALGIA
    # ==========================================================================
    "fibromialgia": [
        "M79.7",  # Código base (Fibromialgia)
        "M79.70",  # Fibromialgia, sitios múltiples
        "M79.71",  # Fibromialgia, región del hombro
        "M79.72",  # Fibromialgia, brazo
        "M79.73",  # Fibromialgia, antebrazo
        "M79.74",  # Fibromialgia, mano
        "M79.75",  # Fibromialgia, región pelviana y muslo
        "M79.76",  # Fibromialgia, pierna
        "M79.77",  # Fibromialgia, tobillo y pie
        "M79.78",  # Fibromialgia, otros
        "M79.79",  # Fibromialgia, sitio no especificado
    ],
    # ==========================================================================
    # GOTA
    # ==========================================================================
    "gota": [
        "M10",  # Categoría base
        # M10.0: Gota idiopática
        # (Gota primaria clásica, generalmente por factores genéticos o metabólicos desconocidos)
        "M10.0",
        "M10.00",
        "M10.01",
        "M10.02",
        "M10.03",
        "M10.04",
        "M10.05",
        "M10.06",
        "M10.07",
        "M10.08",
        "M10.09",
        # M10.1: Gota saturnina
        # (Gota secundaria causada por la exposición o intoxicación crónica por plomo)
        "M10.1",
        "M10.10",
        "M10.11",
        "M10.12",
        "M10.13",
        "M10.14",
        "M10.15",
        "M10.16",
        "M10.17",
        "M10.18",
        "M10.19",
        # M10.2: Gota inducida por drogas
        # (Gota secundaria provocada por efectos secundarios de medicamentos, como ciertos diuréticos)
        "M10.2",
        "M10.20",
        "M10.21",
        "M10.22",
        "M10.23",
        "M10.24",
        "M10.25",
        "M10.26",
        "M10.27",
        "M10.28",
        "M10.29",
        # M10.3: Gota debida a alteración de la función renal
        # (Gota secundaria porque los riñones pierden la capacidad de filtrar y excretar el ácido úrico)
        "M10.3",
        "M10.30",
        "M10.31",
        "M10.32",
        "M10.33",
        "M10.34",
        "M10.35",
        "M10.36",
        "M10.37",
        "M10.38",
        "M10.39",
        # M10.4: Otras gotas secundarias
        # (Otras variantes con causas médicas identificables distintas a las anteriores)
        "M10.4",
        "M10.40",
        "M10.41",
        "M10.42",
        "M10.43",
        "M10.44",
        "M10.45",
        "M10.46",
        "M10.47",
        "M10.48",
        "M10.49",
        # M10.9: Gota, no especificada
        # (Casos donde se diagnostica gota pero no se detalla su origen ni su tipo)
        "M10.9",
        "M10.90",
        "M10.91",
        "M10.92",
        "M10.93",
        "M10.94",
        "M10.95",
        "M10.96",
        "M10.97",
        "M10.98",
        "M10.99",
    ],
    # ==========================================================================
    # UVEÍTIS
    # ==========================================================================
    "uveitis": [
        # BLOQUE H20: IRIDOCICLITIS (Uveítis anterior)
        "H20",
        "H20.0",  # Iridociclitis aguda y subaguda
        "H20.1",  # Iridociclitis crónica
        "H20.2",  # Iridociclitis inducida por el cristalino
        "H20.8",  # Otras iridociclitis
        "H20.9",  # Iridociclitis, no especificada
        # BLOQUE H30: INFLAMACIÓN CORIORRETINIANA (Uveítis posterior e intermedia)
        "H30",
        "H30.0",  # Inflamación coriorretiniana focal
        "H30.1",  # Inflamación coriorretiniana diseminada
        "H30.2",  # Ciclitis posterior (Uveítis intermedia)
        "H30.8",  # Otras inflamaciones coriorretinianas
        "H30.9",  # Inflamación coriorretiniana, no especificada
        # CONSTANCIA (M9 · observación del profesor guía, 2026):
        # Se RETIRARON H22, H22.0, H22.1, H22.8, H32, H32.0, H32.8 (uveítis "en
        # enfermedades clasificadas en otra parte" / infecciosas) y H44.1 (endoftalmitis)
        # por captar casos sin vínculo reumático. Se conservan solo los bloques anatómicos
        # H20 y H30. Impacto: -503 episodios (27,5% del grupo en pos. 1-3; ver
        # verificaciones/v08). Sincronizado con _codigos_cie.R.
    ],
    # ==========================================================================
    # MIOSITIS (DERMATOPOLIMIOSITIS Y POLIMIOSITIS)
    # ==========================================================================
    "miositis": [
        # BLOQUE M33: DERMATOPOLIMIOSITIS
        # (Enfermedades sistémicas/autoinmunes del tejido conectivo con afección muscular)
        "M33",
        "M33.0",
        "M33.1",
        "M33.2",
        "M33.9",
        # BLOQUE M60: MIOSITIS
        # (Trastornos propios de los músculos y tejido blando)
        # M60.1: Miositis intersticial
        "M60.1",
        "M60.10",
        "M60.11",
        "M60.12",
        "M60.13",
        "M60.14",
        "M60.15",
        "M60.16",
        "M60.17",
        "M60.18",
        "M60.19",
        # M60.2: RETIRADO (CONSTANCIA · M9, obs. profesor guía, 2026): granuloma por
        # cuerpo extraño en tejido blando — no es reumático. Impacto: -216 episodios
        # (6,0% del grupo en pos. 1-3; ver verificaciones/v08). M60.0 (piomiositis
        # infecciosa) nunca estuvo en la definición. Sincronizado con _codigos_cie.R.
        # M60.8: Otras miositis
        "M60.8",
        "M60.80",
        "M60.81",
        "M60.82",
        "M60.83",
        "M60.84",
        "M60.85",
        "M60.86",
        "M60.87",
        "M60.88",
        "M60.89",
        # M60.9: Miositis, no especificada
        "M60.9",
        "M60.90",
        "M60.91",
        "M60.92",
        "M60.93",
        "M60.94",
        "M60.95",
        "M60.96",
        "M60.97",
        "M60.98",
        "M60.99",
    ],
    # ==========================================================================
    # SÍNDROME DE RAYNAUD
    # ==========================================================================
    "sindrome_de_raynaud": ["I73.0"],  # Síndrome de Raynaud
    # ==========================================================================
    # ARTRITIS IDIOPÁTICA JUVENIL
    # ==========================================================================
    "artritis_idiopatica_juvenil": [
        # BLOQUE M08: ARTRITIS JUVENIL (Patologías primarias)
        "M08",
        # M08.0: Artritis reumatoide juvenil
        "M08.0",
        "M08.00",
        "M08.01",
        "M08.02",
        "M08.03",
        "M08.04",
        "M08.05",
        "M08.06",
        "M08.07",
        "M08.08",
        "M08.09",
        # M08.1: Espondilitis anquilosante juvenil
        "M08.1",
        "M08.10",
        "M08.11",
        "M08.12",
        "M08.13",
        "M08.14",
        "M08.15",
        "M08.16",
        "M08.17",
        "M08.18",
        "M08.19",
        # M08.2: Artritis juvenil de comienzo generalizado
        "M08.2",
        "M08.20",
        "M08.21",
        "M08.22",
        "M08.23",
        "M08.24",
        "M08.25",
        "M08.26",
        "M08.27",
        "M08.28",
        "M08.29",
        # M08.3: Poliartritis juvenil (seronegativa)
        "M08.3",
        "M08.30",
        "M08.31",
        "M08.32",
        "M08.33",
        "M08.34",
        "M08.35",
        "M08.36",
        "M08.37",
        "M08.38",
        "M08.39",
        # M08.4: Artritis juvenil pauciarticular
        "M08.4",
        "M08.40",
        "M08.41",
        "M08.42",
        "M08.43",
        "M08.44",
        "M08.45",
        "M08.46",
        "M08.47",
        "M08.48",
        "M08.49",
        # M08.8: Otras artritis juveniles
        "M08.8",
        "M08.80",
        "M08.81",
        "M08.82",
        "M08.83",
        "M08.84",
        "M08.85",
        "M08.86",
        "M08.87",
        "M08.88",
        "M08.89",
        # M08.9: Artritis juvenil, no especificada
        "M08.9",
        "M08.90",
        "M08.91",
        "M08.92",
        "M08.93",
        "M08.94",
        "M08.95",
        "M08.96",
        "M08.97",
        "M08.98",
        "M08.99",
        # BLOQUE M09: ARTRITIS JUVENIL EN ENFERMEDADES CLASIFICADAS EN OTRA PARTE
        # (Manifestaciones secundarias causadas por otras enfermedades base)
        "M09",
        # M09.0: Artritis juvenil en la psoriasis
        "M09.0",
        "M09.00",
        "M09.01",
        "M09.02",
        "M09.03",
        "M09.04",
        "M09.05",
        "M09.06",
        "M09.07",
        "M09.08",
        "M09.09",
        # M09.1: Artritis juvenil en la enfermedad de Crohn (enteritis regional)
        "M09.1",
        "M09.10",
        "M09.11",
        "M09.12",
        "M09.13",
        "M09.14",
        "M09.15",
        "M09.16",
        "M09.17",
        "M09.18",
        "M09.19",
        # M09.2: Artritis juvenil en la colitis ulcerativa
        "M09.2",
        "M09.20",
        "M09.21",
        "M09.22",
        "M09.23",
        "M09.24",
        "M09.25",
        "M09.26",
        "M09.27",
        "M09.28",
        "M09.29",
        # M09.8: Artritis juvenil en otras enfermedades clasificadas en otra parte
        "M09.8",
        "M09.80",
        "M09.81",
        "M09.82",
        "M09.83",
        "M09.84",
        "M09.85",
        "M09.86",
        "M09.87",
        "M09.88",
        "M09.89",
    ],
}

# Vector plano con todos los códigos únicos
TODOS_LOS_CODIGOS = sorted({c for v in CODIGOS_REUMATICOS.values() for c in v})
