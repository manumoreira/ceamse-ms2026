# -*- coding: utf-8 -*-
"""
transform.py — Etapa de transformación y modelado del pipeline de la encuesta ATSMS26.

Lee el archivo parquet limpio y el codebook, y produce dos CSV finales:
1. respuestas_cerradas.csv: Datos cuantitativos, listos para Google Sheets / Looker Studio.
   Las preguntas de opción múltiple se explotan en variables booleanas (1/0).
2. respuestas_abiertas.csv: Textos libres aislados para análisis cualitativo.

Uso:
    python transform.py --input data/interim/clean.parquet --codebook codebook.yaml --outdir data/processed
"""
import argparse
from pathlib import Path
import pandas as pd
import yaml
import numpy as np

def load_codebook(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def extract_dummies(series: pd.Series, prefix: str, options: list, keep_code: bool = False) -> pd.DataFrame:
    """Convierte una serie de listas/arrays en múltiples columnas 1/0."""
    new_cols = {}
    for opt in options:
        codigo = opt["codigo"]
        texto = opt["texto"]
        
        # Si el flag está activo, usamos el código corto en el nombre de la columna
        label = codigo if keep_code else texto
        col_name = f"{prefix} | {label}" 
        
        def check_presence(val):
            if isinstance(val, (list, tuple, np.ndarray)):
                return 1 if codigo in val else 0
            if pd.isna(val):
                return pd.NA
            return 0
            
        new_cols[col_name] = series.apply(check_presence)
    
    return pd.DataFrame(new_cols)

def transform_data(df_clean: pd.DataFrame, codebook: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    closed_data = {}
    open_data = {}
    melted_rows = []
    
    # El identificador ya es el índice del DataFrame gracias a clean.py
    
    for col in codebook["columnas"]:
        code = col["code"]
        ctype = col["type"]
        
        # Ignorar columnas que no existen en el df (por si agregas futuras al codebook)
        if ctype not in ("open_semistructured", "identifier") and code not in df_clean.columns:
            continue

        if ctype == "identifier":
            continue
            
        elif ctype in ("metadata", "date", "numeric"):
            closed_data[code] = df_clean[code]
            
        elif ctype == "single_choice":
            serie = df_clean[code]
            # Solo mapeamos al texto si NO está activo keep_code
            if "options" in col and not col.get("keep_code", False):
                mapeo = {opt["codigo"]: opt["texto"] for opt in col["options"]}
                closed_data[code] = serie.map(mapeo).fillna(serie)
            else:
                closed_data[code] = serie
                
        elif ctype == "multi_choice":
            keep_code = col.get("keep_code", False)
            df_dummies = extract_dummies(df_clean[code], code, col.get("options", []), keep_code)
            for dummy_col in df_dummies.columns:
                closed_data[dummy_col] = df_dummies[dummy_col]
                
            # Generar las filas despivotadas (melt) para esta pregunta
            for ident, val_list in df_clean[code].items():
                if isinstance(val_list, (list, tuple, np.ndarray)):
                    for val_code in val_list:
                        # Buscamos el texto de esa opción
                        texto = next((opt["texto"] for opt in col.get("options", []) if opt["codigo"] == val_code), val_code)
                        label = val_code if keep_code else texto
                        
                        melted_rows.append({
                            "identificador": ident,
                            "pregunta_codigo": code,
                            "pregunta_texto": col["header_original"],
                            "opcion_texto": label
                        })
                
        elif ctype in ("open_short", "open_long"):
            open_data[code] = df_clean[code]
            
        elif ctype == "open_semistructured":
            hint = col.get("parser_hint", "")
            if hint == "multi_choice_with_other":
                opciones_col = f"{code}__opciones"
                otros_col = f"{code}__otros"
                
                if opciones_col in df_clean.columns:
                    keep_code = col.get("keep_code", False)
                    df_dummies = extract_dummies(df_clean[opciones_col], code, col.get("options", []), keep_code)
                    for dummy_col in df_dummies.columns:
                        closed_data[dummy_col] = df_dummies[dummy_col]
                
                if otros_col in df_clean.columns:
                    open_data[code] = df_clean[otros_col]
            else:
                # Caso Cuadras
                val_col, unit_col, ns_col, raw_col = f"{code}__valor", f"{code}__unidad", f"{code}__no_sabe", f"{code}__texto_crudo"
                if val_col in df_clean.columns:
                    closed_data[val_col] = df_clean[val_col]
                    closed_data[unit_col] = df_clean[unit_col]
                    closed_data[ns_col] = df_clean[ns_col]
                if raw_col in df_clean.columns:
                    open_data[code] = df_clean[raw_col]

    df_closed = pd.DataFrame(closed_data, index=df_clean.index)
    df_open = pd.DataFrame(open_data, index=df_clean.index)
    df_melted = pd.DataFrame(melted_rows)

    # Limpiar filas en el dataset abierto que tengan absolutamente todos sus campos nulos
    df_open = df_open.dropna(how='all')
    
    return df_closed, df_open, df_melted

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Ruta al clean.parquet (data/interim/clean.parquet)")
    parser.add_argument("--codebook", required=True, help="Ruta al codebook.yaml")
    parser.add_argument("--outdir", required=True, help="Carpeta de salida (data/processed)")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    codebook = load_codebook(args.codebook)
    df_clean = pd.read_parquet(args.input)

    df_closed, df_open, df_melted = transform_data(df_clean, codebook)

    # Extrae 'C' seguido de un dígito (ej: 'C1')
    df_closed["distancia_ct_C"] = df_closed["zona_distancia_ct"].str.extract(r'(C\d)') 
    # Extrae 'P' seguido de un dígito (ej: 'P0')
    df_closed["distancia_ct_P"] = df_closed["zona_distancia_ct"].str.extract(r'(P\d)')

    # Filtramos las columnas que NO tienen " | " en su nombre
    columnas_base = [col for col in df_closed.columns if " | " not in col]
    
    # Hacemos el merge solo con esas columnas limpias
    df_melted = df_melted.merge(df_closed[columnas_base], left_on="identificador", right_index=True, how="left")

    # Exportar a CSV listos para consumo (index=True preserva el identificador)
    closed_path = outdir / "respuestas_cerradas.csv"
    open_path = outdir / "respuestas_abiertas.csv"
    multiples_path = outdir / "respuestas_multiples.csv"
    
    df_closed.to_csv(closed_path, index=True)
    df_open.to_csv(open_path, index=True)
    df_melted.to_csv(multiples_path, index=False)

    print(f"Transformación exitosa.")
    print(f"-> {closed_path} ({len(df_closed.columns)} columnas numéricas/categóricas)")
    print(f"-> {open_path} ({len(df_open.columns)} columnas de texto libre)")
    print(f"-> {multiples_path} ({len(df_melted.columns)} columnas de respuesta multiple)")

if __name__ == "__main__":
    main()