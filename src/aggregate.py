# -*- coding: utf-8 -*-
"""
aggregate.py — Genera un dataset en formato largo (Tidy Data) con las frecuencias 
y porcentajes de las preguntas cerradas y de opción múltiple.
Ideal para ser ingestado como única fuente de datos en Google Sheets o Looker Studio.

Uso:
    python aggregate.py --input data/processed/respuestas_cerradas.csv --codebook codebook.yaml --outdir data/processed
"""
import argparse
from pathlib import Path
import pandas as pd
import yaml

def load_codebook(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def aggregate_data(df: pd.DataFrame, codebook: dict) -> pd.DataFrame:
    resultados = []
    
    for col in codebook["columnas"]:
        code = col["code"]
        ctype = col["type"]
        texto_pregunta = col["header_original"]
        opciones = col.get("options", [])
        
        # 1. PREGUNTAS DE OPCIÓN ÚNICA
        if ctype == "single_choice":
            if code not in df.columns: continue
            
            # Frecuencias absolutas (ignorando nulos para el % de respuestas válidas)
            counts = df[code].value_counts(dropna=True)
            total_validos = counts.sum()
            
            opciones_dict = {opt["codigo"]: opt["texto"] for opt in opciones}
            
            for opt_code, count in counts.items():
                texto_opt = opciones_dict.get(opt_code, str(opt_code))
                porcentaje = (count / total_validos) * 100 if total_validos > 0 else 0
                
                resultados.append({
                    "pregunta_codigo": code,
                    "pregunta_texto": texto_pregunta,
                    "tipo_pregunta": ctype,
                    "opcion_codigo": opt_code,
                    "opcion_texto": texto_opt,
                    "casos": int(count),
                    "porcentaje_sobre_validos": round(porcentaje, 1)
                })
                
        # 2. PREGUNTAS DE OPCIÓN MÚLTIPLE (y semi-estructuradas con opciones)
        elif ctype == "multi_choice" or (ctype == "open_semistructured" and col.get("parser_hint") == "multi_choice_with_other"):
            dummy_cols = [f"{code}__{opt['codigo']}" for opt in opciones if f"{code}__{opt['codigo']}" in df.columns]
            if not dummy_cols: continue
            
            # El denominador son los encuestados que respondieron AL MENOS una opción
            valid_mask = df[dummy_cols].sum(axis=1) > 0
            total_validos = valid_mask.sum()
            
            for opt in opciones:
                opt_code = opt["codigo"]
                col_dummy = f"{code}__{opt_code}"
                
                if col_dummy in df.columns:
                    count = df[col_dummy].sum()
                    porcentaje = (count / total_validos) * 100 if total_validos > 0 else 0
                    
                    resultados.append({
                        "pregunta_codigo": code,
                        "pregunta_texto": texto_pregunta,
                        "tipo_pregunta": ctype,
                        "opcion_codigo": opt_code,
                        "opcion_texto": opt["texto"],
                        "casos": int(count),
                        # En multi_choice la suma de porcentajes será > 100%, lo cual es correcto
                        "porcentaje_sobre_validos": round(porcentaje, 1) 
                    })

    return pd.DataFrame(resultados)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Ruta a respuestas_cerradas.csv")
    parser.add_argument("--codebook", required=True, help="Ruta al codebook.yaml")
    parser.add_argument("--outdir", required=True, help="Carpeta de salida")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    codebook = load_codebook(args.codebook)
    # Leemos el CSV de cerradas asegurando que el identificador sea el índice
    df_closed = pd.read_csv(args.input, index_col="identificador")

    df_agg = aggregate_data(df_closed, codebook)

    out_path = outdir / "resumen_agregado.csv"
    df_agg.to_csv(out_path, index=False)

    print(f"Agregación exitosa. Creado: {out_path} ({len(df_agg)} filas de resumen)")

if __name__ == "__main__":
    main()