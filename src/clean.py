# -*- coding: utf-8 -*-
"""
clean.py — Etapa de limpieza/normalización del pipeline ETL de la encuesta ATSMS26.

Lee el CSV crudo (export de Google Forms) + codebook.yaml, y produce una tabla
"interim" donde cada columna quedó tipada y normalizada.
La lógica de parseo de bajo nivel fue delegada a clean_utils.py.

Uso:
    python clean.py --input ATSMS26.csv --codebook codebook.yaml --outdir data/interim --geo-corrections 

Salidas:
    <outdir>/clean.parquet   - tabla limpia, una fila por encuestado/a (identificador como índice)
    <outdir>/quality_log.csv - cada fila es un problema detectado durante la limpieza
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import pandas as pd
import yaml
import hashlib

from clean_utils import (
    QualityLog, normalize_text, parse_single_choice, parse_multi_choice, 
    parse_free_text, parse_semistructured_cuadras, parse_numeric, 
    parse_date, parse_timestamp, parse_plain_text, parse_semistructured_multichoice
)

def load_codebook(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        cb = yaml.safe_load(f)
    cb["_by_code"] = {c["code"]: c for c in cb["columnas"]}
    cb["_by_index"] = {c["index"]: c for c in cb["columnas"]}
    na_tokens = set(
        t.strip().lower() for t in cb["meta"]["convenciones"]["manejo_de_na"]["na_tokens_sugeridos"]
    )
    na_tokens.discard("") 
    cb["_na_tokens"] = na_tokens
    return cb

def _apply_manual_corrections(df_raw: pd.DataFrame, corrections_path: str | Path) -> pd.DataFrame:
    """Aplica eliminaciones o modificaciones de valores directamente sobre el CSV crudo."""
    path = Path(corrections_path)
    if not path.exists():
        return df_raw
        
    with open(path, "r", encoding="utf-8") as file:
        rules = json.load(file)
        
    # Buscamos la columna de tiempo real del CSV crudo
    time_col = next((c for c in df_raw.columns if normalize_text(c) == normalize_text("Marca temporal")), None)
    if not time_col:
        print("AVISO: No se encontró 'Marca temporal' para aplicar correcciones manuales.")
        return df_raw
        
    df_raw[time_col] = df_raw[time_col].astype(str).str.strip()
    
    temp_time = df_raw[time_col].astype(str).str.strip()

    for rule in rules:
        marca_temporal = str(rule.get("marca_temporal", "")).strip()
        accion = rule.get("accion")
        motivo = rule.get("motivo", "Sin motivo")
        
        if not marca_temporal or not accion:
            continue
            
        mask = temp_time == marca_temporal
        if not mask.any():
            print(f"AVISO: No se encontró la marca temporal '{marca_temporal}' para la corrección manual.")
            continue
            
        if accion == "eliminar":
            df_raw = df_raw[~mask]
            print(f"REGLA MANUAL - Eliminado: {marca_temporal} ({motivo})")
            
        elif accion == "modificar":
            columna = rule.get("columna")
            nuevo_valor = rule.get("nuevo_valor")
            
            if columna in df_raw.columns:
                df_raw.loc[mask, columna] = nuevo_valor
                print(f"REGLA MANUAL - Modificado: {marca_temporal} | {columna} -> '{nuevo_valor}' ({motivo})")
            else:
                print(f"AVISO: La columna '{columna}' no existe en el crudo para modificarla.")
                
    return df_raw

def _apply_geographic_corrections(df_raw: pd.DataFrame, corrections_path: str | Path) -> pd.DataFrame:
    path = Path(corrections_path)
    if not path.exists():
        print(f"AVISO: No se encontró el archivo de correcciones geográficas en {path}.")
        return df_raw
        
    df_geo = pd.read_csv(path, sep=";", dtype=str)
    df_geo = df_geo.dropna(subset=['Segmento_Final', 'Marca_temporal'])

    df_geo['Latitud'] = df_geo['Latitud'].str.replace(',', '.')
    df_geo['Longitud'] = df_geo['Longitud'].str.replace(',', '.')
    df_geo['geo_seccion'] = df_geo['Segmento_Final'].str.split('-').str[0]
    df_geo['geo_circulo'] = df_geo['Segmento_Final'].str.split('-').str[1]
    df_geo['Marca_temporal'] = df_geo['Marca_temporal'].str.strip()
    
    time_col = next((c for c in df_raw.columns if normalize_text(c) == normalize_text("Marca temporal")), None)
    sec_col = next((c for c in df_raw.columns if normalize_text(c) == normalize_text("Sección")), None)
    
    if time_col and sec_col:
        df_raw[time_col] = df_raw[time_col].astype(str).str.strip()
        map_seccion = df_geo.set_index('Marca_temporal')['geo_seccion'].to_dict()
        df_raw[sec_col] = df_raw[time_col].map(map_seccion).fillna(df_raw[sec_col])
        print(f"OK - Secciones geográficas reescritas usando {path.name}")
        
        map_circulo = df_geo.set_index('Marca_temporal')['geo_circulo'].to_dict()
        df_raw["Circulo_Geo"] = df_raw[time_col].map(map_circulo)
        
        map_lat = df_geo.set_index('Marca_temporal')['Latitud'].to_dict()
        map_lon = df_geo.set_index('Marca_temporal')['Longitud'].to_dict()
        df_raw["Latitud"] = df_raw[time_col].map(map_lat)
        df_raw["Longitud"] = df_raw[time_col].map(map_lon)
    else:
        print("AVISO: No se pudieron aplicar correcciones geográficas porque faltan las columnas base en el DF crudo.")
        
    return df_raw

def clean_dataframe(df_raw: pd.DataFrame, codebook: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    log = QualityLog()
    na_tokens = codebook["_na_tokens"]
    
    csv_headers_norm = {normalize_text(c): c for c in df_raw.columns}
    col_mapping = {}
    missing_cols = []
    
    for col in codebook["columnas"]:
        if col.get("injected", False):
            col_mapping[col["code"]] = col["header_original"]
            continue
            
        expected_norm = normalize_text(col["header_original"])
        if expected_norm not in csv_headers_norm:
            missing_cols.append(col["header_original"])
        else:
            col_mapping[col["code"]] = csv_headers_norm[expected_norm]
            
    if missing_cols:
        error_msg = "Faltan columnas esperadas en el CSV o se alteró su nombre original:\n"
        error_msg += "\n".join(f"- {c}" for c in missing_cols)
        raise ValueError(error_msg)

    id_col_real = col_mapping["identificador"]
    
    df_raw[id_col_real] = df_raw[id_col_real].fillna("").astype(str).str.strip()
    
    mask_invalid = df_raw[id_col_real] == ""
    mask_no_numbers = ~df_raw[id_col_real].str.contains(r'\d', regex=True)
    mask_to_replace = mask_invalid | mask_no_numbers
    
    if mask_to_replace.any():
        time_col = col_mapping.get("marca_temporal")
        def generar_id_estable(row):
            # Usamos la marca temporal real si existe en el codebook, sino el backup de texto
            base_string = str(row[time_col]) if time_col and pd.notna(row.get(time_col)) else "".join(str(v) for v in row.values)
            hash_corto = hashlib.md5(base_string.encode('utf-8')).hexdigest()[:8].upper()
            return f"ID_AUTO_{hash_corto}"
            
        df_raw.loc[mask_to_replace, id_col_real] = df_raw[mask_to_replace].apply(generar_id_estable, axis=1)

    mask_dupes = df_raw.duplicated(subset=[id_col_real], keep="first")
    if mask_dupes.any():
        conteo_secuencial = df_raw[mask_dupes].groupby(id_col_real).cumcount() + 1
        df_raw.loc[mask_dupes, id_col_real] = (
            df_raw.loc[mask_dupes, id_col_real] + "_DUP_" + conteo_secuencial.astype(str)
        )

    clean_rows = []
    
    for _, row in df_raw.iterrows():

        ident = normalize_text(row[id_col_real])
        clean_row = {}
        for col in codebook["columnas"]:
            code = col["code"]
            ctype = col["type"]
            real_col_name = col_mapping[code]
            raw_value = row[real_col_name]

            if ctype == "identifier":
                clean_row[code] = normalize_text(raw_value)
            elif ctype == "metadata" and code == "marca_temporal":
                clean_row[code] = parse_timestamp(raw_value, col, log, ident)
            elif ctype == "metadata":
                clean_row[code] = parse_plain_text(raw_value, col, log, ident)
            elif ctype == "date":
                clean_row[code] = parse_date(raw_value, col, log, ident)
            elif ctype == "numeric":
                clean_row[code] = parse_numeric(raw_value, col, log, ident)
            elif ctype == "single_choice":
                clean_row[code] = parse_single_choice(raw_value, col, log, ident)
            elif ctype == "multi_choice":
                clean_row[code] = parse_multi_choice(raw_value, col, log, ident)
            elif ctype in ("open_short", "open_long"):
                clean_row[code] = parse_free_text(raw_value, col, log, ident)
            elif ctype == "open_semistructured":
                hint = col.get("parser_hint", "")
                if hint == "multi_choice_with_other":
                    parsed = parse_semistructured_multichoice(raw_value, col, log, ident)
                    clean_row[f"{code}__opciones"] = parsed["opciones"]
                    clean_row[f"{code}__otros"] = parsed["otros"]
                else:
                    parsed = parse_semistructured_cuadras(raw_value, col, log, ident)
                    clean_row[f"{code}__valor"] = parsed["valor"]
                    clean_row[f"{code}__unidad"] = parsed["unidad"]
                    clean_row[f"{code}__no_sabe"] = parsed["no_sabe"]
                    clean_row[f"{code}__texto_crudo"] = parsed["texto_crudo"]
            else:
                raise ValueError(f"Tipo de columna no soportado: {ctype} ({code})")

            if col.get("required", False):
                if normalize_text(raw_value) == "":
                    if "parent_code" in col:
                        parent_code = col["parent_code"]
                        parent_option = col["parent_option"]
                        parent_val = clean_row.get(parent_code)
                        if isinstance(parent_val, list): parent_letters = parent_val
                        elif isinstance(parent_val, str): parent_letters = parent_val.split("|")
                        else: parent_letters = []
                            
                        if parent_option in parent_letters:
                            log.add(ident, code, "obligatoria_condicional_vacia", "N/A")
                    else:
                        log.add(ident, code, "obligatoria_vacia", "N/A")

            if "parent_code" in col:
                val = clean_row.get(code)
                has_value = True if isinstance(val, list) else pd.notna(val)
                
                if val is not None and has_value:
                    parent_code = col["parent_code"]
                    parent_option = col["parent_option"]
                    
                    if parent_code in clean_row:
                        parent_val = clean_row[parent_code]
                        if isinstance(parent_val, list): parent_letters = parent_val
                        elif isinstance(parent_val, str): parent_letters = parent_val.split("|")
                        else: parent_letters = []
                        
                        if parent_option not in parent_letters:
                            log.add(ident, code, f"texto_condicional_presente_sin_opcion_{parent_option}_en_{parent_code}", str(raw_value))

        clean_rows.append(clean_row)

    df_clean = pd.DataFrame(clean_rows)
    if "identificador" in df_clean.columns:
        df_clean = df_clean.set_index("identificador")
        
    return df_clean, log.to_frame()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV crudo exportado del formulario")
    parser.add_argument("--codebook", required=True, help="codebook.yaml")
    parser.add_argument("--outdir", required=True, help="Carpeta de salida (data/interim)")
    parser.add_argument("--geo-corrections", required=False, help="CSV con coordenadas USIG para corregir las secciones")
    parser.add_argument("--manual-corrections", required=False, help="JSON con reglas de edición manual")
    args = parser.parse_args()
    args = parser.parse_args()

    codebook = load_codebook(args.codebook)
    df_raw = pd.read_csv(args.input, dtype=str, keep_default_na=False)

    # 1. Primero se inyectan los datos espaciales automáticos
    if args.geo_corrections:
        df_raw = _apply_geographic_corrections(df_raw, args.geo_corrections)

    # 2. Segundo se aplican los parches manuales
    if args.manual_corrections:
        df_raw = _apply_manual_corrections(df_raw, args.manual_corrections)
    
    df_clean, df_log = clean_dataframe(df_raw, codebook)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    df_clean.to_parquet(outdir / "clean.parquet")
    df_log.to_csv(outdir / "quality_log.csv", index=False)

    print(f"Filas procesadas: {len(df_clean)}")
    print(f"Columnas en la tabla limpia: {len(df_clean.columns)}")
    print(f"Problemas registrados en el log de calidad: {len(df_log)}")
    print(f"-> {outdir / 'clean.parquet'}")
    print(f"-> {outdir / 'quality_log.csv'}")

if __name__ == "__main__":
    main()