# export_gis.py
import pandas as pd
import argparse

def main():
    parser = argparse.ArgumentParser(description="Exporta un CSV plano optimizado para QGIS/Mapbox")
    parser.add_argument("--input", required=True, help="Ruta al dataset final procesado (parquet o csv)")
    parser.add_argument("--out", required=True, help="Ruta de salida (ej: export_qgis.csv)")
    args = parser.parse_args()

    # Cargar datos
    if args.input.endswith('.parquet'):
        df = pd.read_parquet(args.input)
    else:
        df = pd.read_csv(args.input)

    # 1. Descartar encuestas que no tienen coordenadas
    df_gis = df.dropna(subset=['latitud', 'longitud']).copy()

    # 2. Seleccionar solo las columnas útiles para el mapa
    # (Agregá acá las variables de impacto que quieras visualizar)
    columnas_mapa = [
        'identificador', 'latitud', 'longitud', 
        'seccion', 'modo_captura'
    ]
    # Filtrar solo las columnas que realmente existen en el df
    columnas_existentes = [col for col in columnas_mapa if col in df_gis.columns]
    
    df_export = df_gis[columnas_existentes]

    # 3. Exportar a CSV delimitado por comas (formato estándar para QGIS)
    df_export.to_csv(args.out, index=False, encoding='utf-8')
    print(f"Exportado exitosamente: {args.out} ({len(df_export)} puntos georreferenciados)")

if __name__ == "__main__":
    main()