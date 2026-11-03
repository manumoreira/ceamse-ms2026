#!/bin/zsh

echo "Iniciando limpieza de datos..."
python src/clean.py \
    --input data/raw/ATSMS26.csv \
    --codebook src/codebook.yaml \
    --outdir data/interim \
    --geo-corrections data/raw/correcciones_geo.csv \
    --manual-corrections data/raw/correcciones_manuales.json

echo "Limpieza finalizada."