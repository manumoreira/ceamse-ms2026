INPUT_CSV = data/raw/ATSMS26.csv
CODEBOOK = src/codebook.yaml
INTERIM_DIR = data/interim
PROCESSED_DIR = data/processed
GEO_CORR = data/raw/correcciones_geo.csv
MANUAL_CORR = data/raw/correcciones_manuales.json

.PHONY: all run_clean run_transform reset

all: run_clean run_transform

run_clean:
	@echo "Iniciando limpieza de datos..."
	python src/clean.py --input $(INPUT_CSV) --codebook $(CODEBOOK) --outdir $(INTERIM_DIR) --geo-corrections $(GEO_CORR) --manual-corrections $(MANUAL_CORR)
	@echo "Limpieza finalizada."

run_transform:
	@echo "Iniciando transformación de datos..."
	python src/transform.py --input $(INTERIM_DIR)/clean.parquet --codebook $(CODEBOOK) --outdir $(PROCESSED_DIR)
	@echo "Transformación finalizada."

reset:
	@echo "Borrando archivos procesados e intermedios..."
	rm -f $(INTERIM_DIR)/*.parquet
	rm -f $(PROCESSED_DIR)/*.csv
	@echo "Entorno limpio."