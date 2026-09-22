# -*- coding: utf-8 -*-
"""
Genera codebook.yaml a partir de ATSMS26.csv (encuesta ATSMS26 - CEAMSE / Centro de Transferencia).
Ejecutar una sola vez para generar la base del codebook; después se edita a mano
a medida que aparecen nuevas opciones o preguntas en futuras descargas del formulario.
"""
import yaml

def oc(codigo, texto):
    return {"codigo": codigo, "texto": texto}

# ---------------------------------------------------------------------------
# Metadatos generales
# ---------------------------------------------------------------------------
meta = {
    "encuesta": "ATSMS26",
    "descripcion": "Encuesta socioambiental sobre el Centro de Transferencia (CEAMSE) y su entorno barrial",
    "fuente": "Google Forms (export CSV)",
    "version_codebook": "0.2.0",
    "convenciones": {
        "tipos_de_pregunta": {
            "metadata": "Datos administrativos de la respuesta (no son preguntas de la encuesta).",
            "identifier": "Clave estable de la fila, no cambia entre descargas.",
            "numeric": "Valor numérico. Debe poder castear a int/float tras limpieza.",
            "date": "Fecha. Validar rango plausible.",
            "single_choice": "Opción única, formato 'LETRA. TEXTO'.",
            "multi_choice": "Opción múltiple ('Marque una o más'), respuestas concatenadas.",
            "open_short": "Pregunta abierta de respuesta corta (un solo renglón en el formulario).",
            "open_long": "Pregunta abierta de respuesta larga (párrafo/comentarios en el formulario).",
            "open_semistructured": "Texto libre que mezcla un dato estructurado con lenguaje natural. Requiere un parser dedicado."
        },
        "manejo_de_na": {
            "single_choice_y_multi_choice": "Vacío -> NA. 'NO SABE / NO CONTESTA' NO es NA.",
            "open_short_y_open_long": "Vacío -> NA. Los tokens como 'no sabe' se dejan intactos para codificación cualitativa.",
            "na_tokens_sugeridos": ["", "no sabe", "no sabe.", "ns/nc", "n/a", "no contesta", "no", "ninguna", "ninguno", "no aplica", "-"],
            "advertencia": "Esta lista es un punto de partida, no una regla automática ciega."
        },
        "notas_de_calidad_detectadas": [
            "Columna 'fecha_encuesta': valor '15/7/1997' es un error de tipeo evidente (probablemente 2026). Validar rango de fechas plausible antes de aceptar.",
            "Columna 'encuestador': nombres inconsistentes para la misma persona (ej. 'Lucía Veiras' vs 'lucia', 'Guadalupe' vs 'Guadalupe Pino'). Requiere tabla de normalización manual encuestador -> nombre canónico.",
            "Columna 'cuadras_al_centro_transferencia': mezcla números limpios ('4'), con unidad ('50m'), con calificadores ('no sabe, pero a 12 cuadras') y basura ('kjhoino').",
            "Algunas preguntas de opción única (ej. situacion_laboral) tienen al menos un caso con más de una letra marcada. Se procesan combinadas."
        ]
    }
}

# ---------------------------------------------------------------------------
# Columnas
# ---------------------------------------------------------------------------
columnas = []

def add(idx, code, header, tipo, **kw):
    entry = {"index": idx, "code": code, "header_original": header, "type": tipo}
    entry.update(kw)
    columnas.append(entry)

add(0, "marca_temporal", "Marca temporal", "metadata",
    descripcion="Timestamp de envío del formulario (distinto de la fecha real de la encuesta).")

add(1, "fecha_encuesta", "Fecha de realización de esta encuesta", "date",
    descripcion="Fecha en que se hizo la encuesta en el territorio.",
    formato_detectado="d/m/YYYY sin ceros a la izquierda",
    notas="Ver anomalía '15/7/1997' en notas_de_calidad_detectadas.")

add(2, "encuestador", "Nombre de la Encuestadora", "metadata",
    descripcion="Nombre de quien releva la encuesta.",
    notas="Normalizar variantes del mismo nombre antes de usar para analizar por encuestador.")

add(3, "domicilio", "Domicilio donde se realiza la encuesta (Calle / Altura o N° de puerta / Entre qué calles / Pasillo / Tira / Manzana)", "open_short",
    descripcion="Dirección en formato libre, mezcla calle+altura, entrecalles, tiras/manzanas de villa.")

add(4, "zona_distancia_ct", "Distancia del CT", "single_choice",
    keep_code=True,
    descripcion="Zona de distancia al Centro de Transferencia y si está dentro o fuera del recorrido de camiones. Generada por el instrumento de muestreo, no la responde el encuestado.",
    options=[
        oc("C1P0", "entre 0 y 300 m del CT y FUERA del recorrido de camiones"),
        oc("C1P1", "entre 0 y 300 m del CT y DENTRO del recorrido de camiones"),
        oc("C2P0", "entre 301 y 600 m del CT y FUERA del recorrido de camiones"),
        oc("C2P1", "entre 301 y 600 m del CT y DENTRO del recorrido de camiones"),
        oc("C3P0", "entre 601 y 900 m del CT y FUERA del recorrido de camiones"),
        oc("C3P1", "entre 601 y 900 m del CT y DENTRO del recorrido de camiones"),
        oc("C4P0", "entre 901 y 1200 m del CT y FUERA del recorrido de camiones"),
        oc("C4P1", "entre 901 y 1200 m del CT y DENTRO del recorrido de camiones"),
        oc("C5P0", "entre 1201 y 1500 m del CT y FUERA del recorrido de camiones"),
        oc("C5P1", "entre 1201 y 1500 m del CT y DENTRO del recorrido de camiones"),
    ])

add(5, "edad", "01. EDAD", "numeric")

add(6, "genero", "02. GÉNERO", "single_choice",
    options=[oc("A", "FEMENINO"), oc("B", "MASCULINO"), oc("C", "OTRO")])

add(7, "estudia_actualmente", "03. ¿ESTUDIA ACTUALMENTE?", "single_choice",
    options=[oc("A", "SI"), oc("B", "NO")])

add(8, "max_nivel_estudios", "04. ¿CUÁL ES SU MÁXIMO NIVEL DE ESTUDIOS ALCANZADO?", "single_choice",
    options=[oc("A", "PRIMARIO"), oc("B", "SECUNDARIO INCOMPLETO"), oc("C", "SECUNDARIO COMPLETO"),
              oc("D", "TERCIARIO O UNIVERSITARIO INCOMPLETO"), oc("E", "TERCIARIO O UNIVERSITARIO COMPLETO")])

add(9, "situacion_laboral", "05. ¿EN QUÉ SITUACIÓN LABORAL SE ENCUENTRA ACTUALMENTE?", "multi_choice",
    options=[oc("A", "TRABAJO EN BLANCO"), oc("B", "TRABAJO INFORMAL"), oc("C", "MONOTRIBUTISTA"), oc("D", "DESOCUPADO")])

add(10, "rubro_trabajo_blanco", "05 / A. ¿En qué rubro -Trabajo en Blanco-?", "open_short",
    parent_code="situacion_laboral", parent_option="A")
add(11, "rubro_trabajo_informal", "05 / B. ¿En qué rubro -Trabajo Informal-?", "open_short",
    parent_code="situacion_laboral", parent_option="B")
add(12, "rubro_monotributista", "05 / C. ¿En qué rubro -Monotributista-?", "open_short",
    parent_code="situacion_laboral", parent_option="C")

add(13, "beneficiario_programa_social", "06. Actualmente ¿es beneficiario de algún programa social proveniente del Gobierno Nacional?", "single_choice",
    options=[oc("A", "NO"), oc("B", "SI")])
add(14, "cual_programa_social", "06 / B. ¿De cuál programa social es beneficiario?", "open_short",
    parent_code="beneficiario_programa_social", parent_option="B")

add(15, "conoce_organizaciones_sociales", "07. ¿Conoce alguna de estas organizaciones sociales que se encuentra en el barrio? (Marque una o más respuestas)", "open_semistructured",
    options=[oc("A", "COMEDOR COMUNITARIO"), oc("B", "CENTRO CULTURAL"), oc("C", "ASAMBLEA BARRIAL"),
              oc("D", "BACHILLERATO POPULAR"), oc("E", "ORGANIZACIÓN SIN FINES DE LUCRO (ONG)"),
              oc("F", "NO SABE / NO CONTESTA")],
    parser_hint="multi_choice_with_other",
    notas="Maneja tanto las opciones cerradas como el campo 'Otros' de Google Forms.")

add(16, "participa_organizaciones", "08. ¿Participa en alguna de estas organizaciones?", "single_choice",
    options=[oc("A", "SI"), oc("B", "NO")])

add(17, "motivos_sanitarios_frecuentes", "09. ¿Cuáles son los motivos sanitarios de consulta más frecuentes? (Marque una o más respuestas)", "multi_choice",
    options=[oc("A", "ALERGIAS EN LA PIEL"), oc("B", "PROBLEMAS RESPIRATORIOS"), oc("C", "VISTA IRRITADA"),
              oc("D", "DIARREA RECURRENTE"), oc("E", "RABIA"), oc("F", "LEPTOSPIROSIS"), oc("G", "TÉTANOS"),
              oc("H", "TOS"), oc("I", "NINGUNO DE LOS ANTERIORES"), oc("J", "OTRO (especifique)")])
add(18, "otro_motivo_sanitario", "09 / J. Especifique otro motivo sanitario de consulta frecuente", "open_short",
    parent_code="motivos_sanitarios_frecuentes", parent_option="J")

add(19, "lugar_consulta_medica", "10. Ante la necesidad de una consulta médica asiste a ... (Marque una o más respuestas)", "multi_choice",
    options=[oc("A", "HOSPITAL PÚBLICO"), oc("B", "CENTRO COMUNITARIO DE SALUD (CESAC)"),
              oc("C", "CLÍNICA MÉDICA / HOSPITAL / SANATORIO PRIVADO"), oc("D", "OTRO")])
add(20, "cual_hospital_publico", "10 / A. ¿A cuál Hospital Público asiste?", "open_short",
    parent_code="lugar_consulta_medica", parent_option="A")
add(21, "cual_cesac", "10 / B. ¿A cuál CESAC asiste?", "open_short",
    parent_code="lugar_consulta_medica", parent_option="B")
add(22, "cual_clinica_privada", "10 / C. ¿A cuál Clinica / Hospital / Sanatorio privado asiste?", "open_short",
    parent_code="lugar_consulta_medica", parent_option="C")

add(23, "calidad_aire", "11. ¿Cómo evalúa la calidad del aire en su barrio?", "single_choice",
    options=[oc("A", "BUENO"), oc("B", "REGULAR"), oc("C", "MALO"), oc("D", "NO SABE / NO CONTESTA")])

add(24, "fuentes_contaminacion_aire", "12. En su opinión ¿cuáles son las principales fuentes de contaminación del aire en su barrio? (Marque una o más respuestas)", "multi_choice",
    options=[oc("A", "TRÁNSITO VEHICULAR"), oc("B", "ACTIVIDAD INDUSTRIAL"), oc("C", "OBRAS EN CONSTRUCCIÓN"),
              oc("D", "CENTRO DE TRANSFERENCIA DEL CEAMSE"), oc("E", "FALTA DE ESPACIOS VERDES"),
              oc("F", "NO SABE / NO CONTESTA"), oc("G", "OTRO (especifique)")])
add(25, "otra_fuente_contaminacion_aire", "12 / G. ¿Qué otra fuente de contaminación principal considera que hay en su barrio?", "open_short",
    parent_code="fuentes_contaminacion_aire", parent_option="G")

add(26, "evento_extraordinario_aire", "13. ¿Recuerda algún evento extraordinario que haya afectado la calidad del aire en su barrio?", "single_choice",
    options=[oc("A", "NO"), oc("B", "SI ¿cuál?")])
add(27, "detalle_evento_extraordinario_aire", "13 / B. El /los EVENTO/S EXTRAORDINARIO/S que afectó/aron la calidad del aire en el barrio fue / fueron: ", "open_short",
    parent_code="evento_extraordinario_aire", parent_option="B")

add(28, "conoce_zonas_inundables", "14. ¿Conoce lugares del barrio dónde se estanque el agua o se inunde cuando llueve?", "single_choice",
    options=[oc("A", "NO"), oc("B", "SI ¿dónde?")])
add(29, "donde_inunda", "14/ B. ¿Dónde se inunda o estanca el agua cuando llueve?", "open_short",
    parent_code="conoce_zonas_inundables", parent_option="B")

add(30, "cambia_olor_zanjas_lluvia", "15. En los días de lluvia ¿cambia el olor de las zanjas y pozos ciegos?", "single_choice",
    options=[oc("A", "NO"), oc("B", "SI (describa)")])
add(31, "como_es_olor_zanjas_lluvia", "15 / B. El olor de las zanjas y pozos ciegos en los días de lluvia, es:", "open_long",
    parent_code="cambia_olor_zanjas_lluvia", parent_option="B")

add(32, "institucion_emergencia_inundacion", "16. Ante una emergencia vinculada a las inundaciones ¿a qué institución recurriría?  (Marque una o más respuestas)", "multi_choice",
    options=[oc("A", "BOMBEROS"), oc("B", "SAME - EMERGENCIAS"), oc("C", "INSTITUTO DE VIVIENDA DE LA CIUDAD (IVC)"),
              oc("D", "DEFENSA CIVIL - EMERGENCIAS"), oc("E", "NO SABE / NO CONTESTA"), oc("F", "OTRO (especifique)")])
add(33, "otra_institucion_emergencia_inundacion", "16 / F. ¿A qué OTRA institución recurriría en caso de una emergencia por inundaciones?", "open_short",
    parent_code="institucion_emergencia_inundacion", parent_option="F")

add(34, "fuentes_contaminacion_sonora", "17. En su opinión ¿cuáles son las principales fuentes de contaminación sonora en el barrio?  (Marque una o más respuestas)", "multi_choice",
    options=[oc("A", "OBRAS EN CONSTRUCCIÓN"), oc("B", "ACTIVIDAD INDUSTRIAL"), oc("C", "CAMIONES RECOLECTORES DE RESIDUOS"),
              oc("D", "CENTRO DE TRANSFERENCIA DEL CEAMSE"), oc("E", "TRANSPORTE PÚBLICO"), oc("F", "OTRO (especifique)")])
add(35, "otra_fuente_contaminacion_sonora", "17 / F. ¿Qué OTRA/s fuente/s de contaminación sonora considera que hay en en barrio?", "open_short",
    parent_code="fuentes_contaminacion_sonora", parent_option="F")

add(36, "momento_mayor_ruido_percibido", "18. ¿En qué momento del día se perciben con mayor intensidad los ruidos?  (Marque una o más respuestas)", "multi_choice",
    options=[oc("A", "A LA MAÑANA"), oc("B", "A LA TARDE"), oc("C", "A LA NOCHE"), oc("D", "NO SABE / NO CONTESTA")])

add(37, "fuentes_congestion_transito", "19. En su opinión ¿cuáles son las principales fuentes de congestión del tránsito en el barrio?  (Marque una o más respuestas)", "multi_choice",
    options=[oc("A", "TRANSPORTE PÚBLICO"), oc("B", "VEHÍCULOS PARTICULARES"), oc("C", "CAMIONES PESADOS"), oc("D", "OTRO (especifique)")])
add(38, "otra_fuente_congestion_transito", "19 / D. ¿Qué OTRA/s fuente/s de congestión del tránsito se presenta/n en el barrio?", "open_short",
    parent_code="fuentes_congestion_transito", parent_option="D")

add(39, "horarios_mayor_circulacion_vial", "20. ¿Cuáles son los horarios de mayor circulación vial en su barrio?", "multi_choice",
    options=[oc("A", "A LA MAÑANA"), oc("B", "A LA TARDE"), oc("C", "A LA NOCHE"), oc("D", "NO SABE / NO CONTESTA")])

add(40, "frecuencia_accidentes_transito", "21. En su opinión ¿con qué frecuencia ocurren accidentes de tránsito en el barrio?", "single_choice",
    options=[oc("A", "POCO FRECUENTE"), oc("B", "FRECUENTE"), oc("C", "MUY FRECUENTE")])
add(41, "comentarios_accidentes_transito", "21 / Comentarios sobre la frecuencia de los accidentes de tránsito en el barrio", "open_long",
    notas="Ligada temáticamente a frecuencia_accidentes_transito.")

add(42, "donde_deposita_residuos_domicilio", "22. ¿En dónde deposita los residuos que genera en su domicilio?", "open_short",
    notas="Sin opciones predefinidas en el formulario.")

add(43, "hay_contenedores_en_cuadra", "23. En la cuadra de su vivienda o lugar dónde desarrolla su actividad ¿hay contenedores de residuos?", "single_choice",
    options=[oc("A", "SI"), oc("B", "NO (indicar dónde hay)")])
add(44, "cuadras_a_contenedor_mas_cercano", "23 / B. Si NO hay contenedores de residuos en la cuadra de su casa o del lugar donde desarrolla su actividad ¿a cuántas cuadras de éstos se encuentra el contenedor más cercano?", "open_semistructured",
    parent_code="hay_contenedores_en_cuadra", parent_option="B",
    parser_hint="Extraer número de cuadras si está presente.")

add(45, "dificultades_sistema_contenedores", "24. ¿Cuál de estos aspectos considera una dificultad en el sistema de contenedores?  (Marque una o más respuestas)", "multi_choice",
    options=[oc("A", "GENERAN MAL OLOR"), oc("B", "HAY POCOS CONTENEDORES"), oc("C", "SE DESBORDAN DE RESIDUOS"),
              oc("D", "ENTORPECEN LA CIRCULACIÓN DE PEATONES"), oc("E", "OTROS (especifique)")])
add(46, "otro_aspecto_dificultad_contenedores", "24 / E. ¿Que aspecto no listado considera una dificultad en el sistema de contenedores?", "open_short",
    parent_code="dificultades_sistema_contenedores", parent_option="E")

add(47, "frecuencia_camion_recolector", "25. ¿Con qué frecuencia pasa el camión recolector de residuos?", "single_choice",
    options=[oc("A", "MÁS DE UNA VEZ A LA SEMANA"), oc("B", "UNA VEZ A LA SEMANA"), oc("C", "MENOS DE UNA VEZ A LA SEMANA"),
              oc("D", "NO PASA EL SERVICIO DE RECOLECCIÓN DE RESIDUOS")])

add(48, "conoce_cooperativa_cartoneros", "26. ¿Conoce alguna cooperativa de cartoneros que trabaje en el barrio?", "single_choice",
    options=[oc("A", "SI"), oc("B", "NO")])

add(49, "tareas_cooperativa_cartoneros", "27. ¿Qué tipos de tareas realizan?", "single_choice",
    options=[oc("A", "RECOLECCIÓN DE RESIDUOS RECICLABLES"), oc("B", "LIMPIEZA DE CALLES"), oc("C", "OTRO (especifique)")])
add(50, "otro_tipo_tarea_cooperativa", "27 / C. ¿Qué OTRO tipo de tareas realiza la cooperativa de cartoneros que trabaja en el barrio?", "open_short",
    parent_code="tareas_cooperativa_cartoneros", parent_option="C")

add(51, "realiza_separacion_residuos", "28. ¿Usted realiza algún tipo de separación de residuos?", "single_choice",
    options=[oc("A", "NO"), oc("B", "SI (especifique)")])
add(52, "tipo_separacion_residuos", "28 / B. ¿Qué tipo de separación de residuos realiza?", "open_short",
    parent_code="realiza_separacion_residuos", parent_option="B")

add(53, "donde_deposita_reciclables", "29. ¿Dónde deposita los residuos reciclables?", "multi_choice",
    options=[oc("A", "CONTENEDORES VERDES UBICADOS EN LAS CALLES"), oc("B", "SE LOS ENTREGA A COOPERATIVAS DE CARTONEROS"),
              oc("C", 'LOS LLEVA HASTA "PUNTOS VERDES"'), oc("D", "OTRO (especifique)")])
add(54, "otro_sitio_reciclables", "29 / D. ¿En qué OTRO sitio deposita usted los residuos reciclables?", "open_short",
    parent_code="donde_deposita_reciclables", parent_option="D")

add(55, "evaluacion_barrido_limpieza", "30. ¿Cómo evaluaría el servicio de barrido y limpieza de calles de su cuadra?", "single_choice",
    options=[oc("A", "INSUFICIENTE"), oc("B", "SUFICIENTE"), oc("C", "MUY BUENO"),
              oc("D", "NO PASA EL BARRENDERO POR MI CUADRA")])

add(56, "reclamo_manejo_residuos", "31. ¿Alguna vez realizó algún reclamo vinculado al manejo de residuos?", "single_choice",
    options=[oc("A", "NO"), oc("B", "SI (especifique motivo y a qué institución)")])
add(57, "motivo_reclamo_residuos", "31 / B. ¿Cuál fue el motivo del reclamo y en qué institución lo hizo?", "open_long",
    parent_code="reclamo_manejo_residuos", parent_option="B")

add(58, "pelea_vecino_basura", "32. ¿Ha tenido alguna pelea con algún vecino por motivo de la basura?", "single_choice",
    options=[oc("A", "NO"), oc("B", "SI (especifique)")])
add(59, "motivo_pelea_vecino_basura", "32 / B. ¿Por que motivo se peleó con algún vecino en relación con el tema de la basura?", "open_long",
    parent_code="pelea_vecino_basura", parent_option="B")

add(60, "conoce_centro_transferencia", "33. ¿Conoce el Centro de Transferencia operado por CEAMSE ubicado en su barrio?", "single_choice",
    options=[oc("A", "SI"), oc("B", "NO")])

add(61, "cuadras_al_centro_transferencia", "34. ¿A cuántas cuadras del Centro de Transferencia vive o desarrolla su actividad?", "open_semistructured",
    parser_hint="Mezcla números limpios, con unidad, calificadores y basura.")

add(62, "conoce_actividades_centro_transferencia", "35. ¿Conoce las actividades que se realizan en el Centro de Transferencia?", "single_choice",
    options=[oc("A", "NO"), oc("B", "SI (especifique)")])
add(63, "actividades_conocidas_centro_transferencia", "35 / B. ¿Qué actividades del Centro de Transferencia conoce usted?", "open_long",
    parent_code="conoce_actividades_centro_transferencia", parent_option="B")

add(64, "momento_transito_camiones_ceamse", "36. ¿En qué momento del día hay mayor tránsito de camiones del CEAMSE?", "multi_choice",
    options=[oc("A", "A LA MAÑANA"), oc("B", "A LA TARDE"), oc("C", "A LA NOCHE"), oc("D", "NO SABE / NO CONTESTA")])

add(65, "hay_otro_tipo_camiones", "37. ¿Hay otro tipo de camiones que transitan por la zona?", "single_choice",
    options=[oc("A", "NO"), oc("B", "SI (especifique)")])
add(66, "tipo_otros_camiones", "37 / B. ¿Qué otro tipo de camiones -que no sean de CEAMSE- transitan por la zona?", "open_short",
    parent_code="hay_otro_tipo_camiones", parent_option="B")

add(67, "afectacion_transito_camiones_ceamse", "38. ¿Qué tanto le afecta el tránsito de camiones de CEAMSE?", "single_choice",
    options=[oc("A", "INDIFERENTE"), oc("B", "MOLESTIA LEVE"), oc("C", "MOLESTIA GRAVE"), oc("D", "MOLESTIA MUY GRAVE")])
add(68, "comentario_molestias_transito_camiones", "38 / ¿Tiene algo para comentar sobre las molestias que produce el tránsito de camiones de CEAMSE?", "open_long",
    notas="Ligada temáticamente a afectacion_transito_camiones_ceamse.")

add(69, "sintio_olores_centro_transferencia", "39. ¿Sintió alguna vez olores provenientes del Centro de Transferencia?", "single_choice",
    options=[oc("A", "SI"), oc("B", "NO")])
add(70, "momento_mayor_olores_percibidos", "40. ¿Hay algún momento del día en que se perciban con más intensidad estos olores?", "multi_choice",
    options=[oc("A", "A LA MAÑANA"), oc("B", "A LA TARDE"), oc("C", "A LA NOCHE"), oc("D", "INDIFERENTE")])
add(71, "afectacion_olores_centro_transferencia", "41. ¿Cómo le afectan los olores provenientes del Centro de Transferencia?", "single_choice",
    options=[oc("A", "INDIFERENTE"), oc("B", "MOLESTIA LEVE"), oc("C", "MOLESTIA GRAVE"), oc("D", "MOLESTIA INTOLERABLE")])
add(72, "especifique_afectacion_olores", "41 / Especifique mejor cómo se produce esta afectación", "open_long",
    notas="Ligada temáticamente a afectacion_olores_centro_transferencia.")

add(73, "sintio_ruidos_centro_transferencia", "42. ¿Alguna vez sintió ruidos del Centro de Transferencia?", "single_choice",
    options=[oc("A", "SI"), oc("B", "NO")])
add(74, "momento_mayor_ruidos_centro_percibidos", "43. ¿En que momento del día se sienten con más intensidad estos ruidos?", "multi_choice",
    options=[oc("A", "A LA MAÑANA"), oc("B", "A LA TARDE"), oc("C", "A LA NOCHE"), oc("D", "INDIFERENTE")])
add(75, "afectacion_ruidos_centro_transferencia", "44. ¿Cómo le resultan estos ruidos?", "single_choice",
    options=[oc("A", "INDIFERENTES"), oc("B", "MOLESTIA LEVE"), oc("C", "MOLESTIA GRAVE"), oc("D", "MOLESTIA INTOLERABLE")])
add(76, "indique_afectacion_ruidos", "44 / Indique más específicamente como lo afectan estos ruidos", "open_long",
    notas="Ligada temáticamente a afectacion_ruidos_centro_transferencia.")

add(77, "sintio_vibraciones", "45. ¿Alguna vez sintió vibraciones en su casa o lugar donde desarrolla su actividad?", "single_choice",
    options=[oc("A", "SI"), oc("B", "NO")])
add(78, "origen_vibraciones", "46. ¿De dónde piensa que provienen estas vibraciones?", "multi_choice",
    options=[oc("A", "DE ACTIVIDADES DENTRO DEL CENTRO DE TRANSFERENCIA"), oc("B", "DE LA CIRCULACIÓN DE CAMIONES"),
              oc("C", "NO SABE / NO CONTESTA"), oc("D", "OTRAS POSIBILIDADES (especifique)")])
add(79, "otras_fuentes_vibraciones", "46 / ¿De que otras fuentes o POSIBILIDADES -diferentes de las listadas- piensa que provienen las vibraciones que usted siente en su casa o lugar donde desarrolla su actividad?", "open_short",
    parent_code="origen_vibraciones", parent_option="D")
add(80, "momento_mayor_vibraciones_percibidas", "47. ¿Hay algún momento del día en que se siente más la intensidad de las vibraciones?", "multi_choice",
    options=[oc("A", "A LA MAÑANA"), oc("B", "A LA TARDE"), oc("C", "A LA NOCHE"), oc("D", "INDIFERENTE")])
add(81, "afectacion_vibraciones", "48. ¿Cómo le afectan las vibraciones?", "single_choice",
    options=[oc("A", "INDIFERENTE"), oc("B", "MOLESTIA LEVE"), oc("C", "MOLESTIA GRAVE"), oc("D", "MOLESTIA INTOLERABLE")])
add(82, "actividades_afectadas_por_vibraciones", "48 / ¿En qué actividades o circunstancias le afectan concretamente las vibraciones?", "open_long",
    notas="Ligada temáticamente a afectacion_vibraciones.")

add(83, "beneficios_centro_transferencia", "49. En su opinión ¿cuáles pueden ser los beneficios del Centro de Transferencia en el barrio?", "multi_choice",
    options=[oc("A", "MEJOR ILUMINACIÓN"), oc("B", "MAYOR SEGURIDAD"), oc("C", "MAYOR HIGIENE"),
              oc("D", "NO SABE / NO CONTESTA"), oc("E", "OTRO (especifique)")])
add(84, "otro_beneficio_centro_transferencia", "49 / E. ¿Qué OTRO beneficio considera que implica tener el Centro de Transferencia en el barrio?", "open_short",
    parent_code="beneficios_centro_transferencia", parent_option="E")

add(85, "consulto_ceamse", "50. ¿Usted ha consultado alguna vez a CEAMSE para informarse sobre las actividades del Centro de Transferencia?", "single_choice",
    options=[oc("A", "NO"), oc("B", "SI (especifique)")])
add(86, "motivo_consulta_ceamse", "50 / B. ¿Por qué motivo ha consultado a CEAMSE sobre las actividades del Centro de Transferencia?", "open_long",
    parent_code="consulto_ceamse", parent_option="B")

add(87, "identificador", "Identificador", "identifier",
    descripcion="Clave estable por encuestado/a, usar como PK en todas las tablas derivadas.")

add(88, "CT", "CENTRO DE TRANSFERENCIA", "single_choice",
    descripcion="Centro de Transferencia de referencia",
    options=[
        oc("FLORES", "FLORES"),
        oc("POMPEYA - ZAVALETA", "POMPEYA - ZAVALETA"), 
        oc("COLEGIALES", "COLEGIALES")
    ])

add(89, "seccion", "Sección", "single_choice",
    descripcion="Sección",
    options=[
        oc("S1", "S1"),
        oc("S2", "S2"),
        oc("S3", "S3"),
        oc("S4", "S4"),
        oc("S5", "S5"),
    ])

codebook = {"meta": meta, "columnas": columnas}

with open("codebook.yaml", "w", encoding="utf-8") as f:
    yaml.dump(codebook, f, allow_unicode=True, sort_keys=False, width=100)

print("OK -", len(columnas), "columnas escritas")