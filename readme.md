# Pipeline ETL - Encuesta Territorial ATSMS26

Este repositorio contiene el pipeline de procesamiento, limpieza y modelado de datos de la encuesta territorial ATSMS26. 

El objetivo del proyecto es transformar las respuestas crudas en un modelo de datos estructurado, normalizado y optimizado para alimentar un dashboard analítico en Looker Studio, minimizando el trabajo manual y manteniendo una arquitectura limpia y auditable.

## 🏗 Arquitectura y Filosofía

- **Data-Driven Configuration:** La lógica de tipos de datos, saltos lógicos (skip logic) y opciones de respuesta no está "hardcodeada" en Python, sino centralizada en un archivo de configuración (`codebook.yaml`).
- **Seguridad y Privacidad:** El repositorio está configurado estrictamente para **no rastrear datos**. El archivo `.gitignore` bloquea todos los archivos `.csv`, `.xlsx` y `.parquet`, conservando únicamente la estructura de directorios mediante archivos `.gitkeep`.
- **Trazabilidad:** Los errores de tipeo o valores inesperados no se fuerzan ni se eliminan silenciosamente; se envían a un registro de calidad (`quality_log.csv`) para su posterior auditoría cualitativa.

## 📂 Estructura de Datos

El flujo de información respeta una estructura de directorios estandarizada:

* `data/raw/`: Extracto original crudo de la herramienta de recolección (ej. Google Forms).
* `data/interim/`: Datos intermedios limpios y tipados, guardados en formato eficiente (`clean.parquet`).
* `data/processed/`: Archivos CSV finales, segmentados lógicamente y listos para ser conectados a Looker Studio.

## 🛠 Componentes del Pipeline

1. **`build_codebook.py`**
   Script auxiliar para definir y compilar el modelo de variables, opciones válidas y tipos de datos en un archivo `codebook.yaml`.

2. **`clean.py`**
   Ejecuta la primera etapa del ETL. Lee el archivo crudo, normaliza textos (espacios, unicode), resuelve valores nulos basados en *tokens* definidos, normaliza variables numéricas/fechas y garantiza la integridad de los identificadores únicos.
   *Salida:* `clean.parquet` y `quality_log.csv`.

3. **`transform.py`**
   Ejecuta el modelado final. Lee el archivo interim y separa el dataset en tres dimensiones analíticas:
   - `respuestas_cerradas.csv`: Base principal con identificadores, metadata y variables de opción única numéricas o categóricas.
   - `respuestas_multiples.csv`: Tabla despivotada (*melted*) de las variables de opción múltiple, optimizada para gráficos de barras sin cruces de datos en Looker Studio.
   - `respuestas_abiertas.csv`: Archivo aislado con todos los campos de texto libre para su posterior categorización cualitativa.

4. **`extraer_diccionario.py`**
   Herramienta de extracción rápida que consolida los valores únicos de variables semiestructuradas (ej. hospitales, rubros laborales) en una plantilla Excel, facilitando su normalización manual externa (ej. vía OpenRefine) mediante tablas de mapeo.

## 🚀 Ejecución del Pipeline

Para correr el proceso completo de transformación, ejecutá los scripts en el siguiente orden desde la raíz del proyecto:

```bash
# 1. Limpieza y tipado
python clean.py --input data/raw/ATSMS26.csv --codebook codebook.yaml --outdir data/interim

# 2. Transformación y modelado final
python transform.py --input data/interim/clean.parquet --codebook codebook.yaml --outdir data/processed