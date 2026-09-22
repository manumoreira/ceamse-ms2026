import pandas as pd

def main():
    # Leemos el parquet limpio que ya generó tu pipeline
    df = pd.read_parquet("../data/interim/clean.parquet") 

    # Tu lista de variables simples
    variables_simples = [
        "rubro_trabajo_blanco",
        "rubro_trabajo_informal",
        "rubro_monotributista",
        "cual_programa_social",
        "conoce_organizaciones_sociales",
        "cual_hospital_publico",
        "cual_cesac",
        "cual_clinica_privada",
        "cuadras_a_contenedor_mas_cercano",
        "cuadras_al_centro_transferencia",
        "tipo_otros_camiones"
    ]

    mapeos = []

    for var in variables_simples:
        # Verificamos que la columna exista para evitar errores
        if var in df.columns:
            # Obtenemos los valores únicos descartando nulos
            unicos = df[var].dropna().unique()
            
            for valor in unicos:
                valor_str = str(valor).strip()
                if valor_str:  # Ignoramos si quedó un string vacío
                    mapeos.append({
                        "variable": var,
                        "valor_original": valor_str,
                        "categoria_normalizada": "" # Columna vacía para que llenes vos
                    })
        else:
            print(f"Aviso: La variable '{var}' no se encontró en el dataset.")

    # Convertimos a DataFrame y exportamos
    df_mapeo = pd.DataFrame(mapeos)
    
    # Ordenamos alfabéticamente por variable y luego por valor para facilitar la lectura
    df_mapeo = df_mapeo.sort_values(by=["variable", "valor_original"])
    
    # Guardamos el Excel
    df_mapeo.to_csv("../data/mapeo_simples.csv", index=False)
    print(f"¡Listo! Se extrajeron {len(df_mapeo)} valores únicos. Archivo guardado como 'mapeo_simples.xlsx'")

if __name__ == "__main__":
    main()