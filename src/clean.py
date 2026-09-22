# -*- coding: utf-8 -*-
"""
clean.py — Etapa de limpieza/normalización del pipeline ETL de la encuesta ATSMS26.

Lee el CSV crudo (export de Google Forms) + codebook.yaml, y produce una tabla
"interim" donde cada columna quedó tipada y normalizada según lo que dice el
codebook, sin todavía separar en dataset estructurado / respuestas abiertas
(eso es responsabilidad de transform.py, el siguiente paso del pipeline).

No inventa respuestas ni corrige texto libre "a mano": normaliza forma
(espacios, unicode, comillas envolventes) y detecta NA sólo con la lista de
tokens del codebook. Todo lo que no se puede interpretar con confianza queda
registrado en el log de calidad para revisión humana, no se descarta en silencio.

Uso:
    python clean.py --input ATSMS26.csv --codebook codebook.yaml --outdir data/interim

Salidas:
    <outdir>/clean.parquet   - tabla limpia, una fila por encuestado/a (identificador como índice)
    <outdir>/quality_log.csv - cada fila es un problema detectado durante la limpieza
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------

_WRAPPING_QUOTES = ('"', "'", "“”", "«»")


def normalize_text(value: str) -> str:
    """Unicode NFC, recorta espacios, colapsa espacios internos múltiples,
    y saca comillas que envuelven toda la celda (típico de exports de Forms
    cuando alguien pegó una frase completa entre comillas)."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) >= 2 and text[0] in "\"'" and text[-1] in "\"'" and text[0] == text[-1]:
        text = text[1:-1].strip()
    return text


def is_na_token(text: str, na_tokens: set[str]) -> bool:
    return text.strip().lower().rstrip(".") in na_tokens


# ---------------------------------------------------------------------------
# Registro de problemas de calidad (no se corrigen solos, se dejan documentados)
# ---------------------------------------------------------------------------

@dataclass
class QualityLog:
    rows: list[dict] = field(default_factory=list)

    def add(self, identificador: str, code: str, issue: str, raw_value: str):
        self.rows.append(
            {
                "identificador": identificador,
                "code": code,
                "issue": issue,
                "raw_value": raw_value,
            }
        )

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=["identificador", "code", "issue", "raw_value"])


# ---------------------------------------------------------------------------
# Codebook
# ---------------------------------------------------------------------------

def load_codebook(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        cb = yaml.safe_load(f)
    cb["_by_code"] = {c["code"]: c for c in cb["columnas"]}
    cb["_by_index"] = {c["index"]: c for c in cb["columnas"]}
    na_tokens = set(
        t.strip().lower() for t in cb["meta"]["convenciones"]["manejo_de_na"]["na_tokens_sugeridos"]
    )
    na_tokens.discard("")  # el vacío se maneja aparte, no como token de texto
    cb["_na_tokens"] = na_tokens
    return cb


# ---------------------------------------------------------------------------
# Parsers por tipo de columna
# ---------------------------------------------------------------------------

_CHOICE_FRAGMENT_RE = re.compile(r"^([A-Z])\.\s*(.+)$")
_ZONE_LIKE_FRAGMENT_RE = re.compile(r"^([A-Za-z0-9]+)\s*\(")


def match_option_code(fragment: str, valid_codes: set[str]) -> str | None:
    """Reconoce formatos de opción vistos en la encuesta y hace match directo."""
    # NUEVO: Si el fragmento coincide exactamente con un código válido (ej: "FLORES"), pasa.
    if fragment in valid_codes:
        return fragment
        
    m = _CHOICE_FRAGMENT_RE.match(fragment)
    if m and m.group(1) in valid_codes:
        return m.group(1)
        
    m = _ZONE_LIKE_FRAGMENT_RE.match(fragment)
    if m and m.group(1) in valid_codes:
        return m.group(1)
        
    return None


def parse_single_choice(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "":
        return pd.NA
    valid_codes = {o["codigo"] for o in col.get("options", [])}
    fragments = [f.strip() for f in text.split(",")]
    letters = []
    for frag in fragments:
        code_found = match_option_code(frag, valid_codes)
        if code_found:
            letters.append(code_found)
        else:
            log.add(ident, col["code"], "fragmento_no_reconocido_como_opcion", frag)
    if not letters:
        return pd.NA
    if len(letters) > 1:
        log.add(ident, col["code"], "single_choice_con_mas_de_una_opcion_marcada", text)
        # Se preserva toda la información (no se descarta ninguna letra), pero como
        # string "A|B" en vez de lista: así la columna mantiene un tipo homogéneo
        # (compatible con parquet/csv) y el caso queda igual señalado en el log.
        return "|".join(letters)
    return letters[0]


def parse_multi_choice(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "":
        return pd.NA
    valid_codes = {o["codigo"] for o in col.get("options", [])}
    fragments = [f.strip() for f in text.split(",")]
    letters = []
    for frag in fragments:
        code_found = match_option_code(frag, valid_codes)
        if code_found:
            letters.append(code_found)
        else:
            log.add(ident, col["code"], "fragmento_no_reconocido_como_opcion", frag)
    return sorted(set(letters)) if letters else pd.NA


def parse_free_text(raw: str, col: dict, log: QualityLog, ident: str):
    """Para respuestas abiertas (cortas o largas): normaliza el texto, 
    pero los tokens NA se dejan intactos para codificación cualitativa posterior."""
    text = normalize_text(raw)
    if text == "":
        return pd.NA
    return text


_CUADRAS_M_RE = re.compile(r"(\d+)\s*m\b")
_CUADRAS_TXT_RE = re.compile(r"(\d+)\s*cuadras?")
_CUADRAS_SOLO_NUM_RE = re.compile(r"^(\d+)$")
_NO_SABE_RE = re.compile(r"no sabe|no se\b", re.IGNORECASE)

_NUM_WORDS = {
    "un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}
_CUADRAS_WORD_RE = re.compile(
    r"\b(" + "|".join(_NUM_WORDS) + r")\b\s*cuadras?", re.IGNORECASE
)
_MEDIA_CUADRA_RE = re.compile(r"\bmedia\s*cuadra\b", re.IGNORECASE)
_Y_MEDIA_RE = re.compile(r"^\s*y\s+media\b", re.IGNORECASE)


def parse_semistructured_cuadras(raw: str, col: dict, log: QualityLog, ident: str):
    """Extrae un valor numérico de cuadras/metros de un texto libre, sin perder
    el texto original. Reconoce dígitos ('4 cuadras'), números en palabras
    ('una cuadra', 'dos cuadras') y 'media cuadra' (incluido como sufijo:
    'una cuadra y media' -> 1.5). No es exhaustivo por diseño: casos ambiguos
    como 'Vive enfrente' o 'dijo 3 pero son 5' quedan sin valor numérico y
    van al log de calidad para revisión humana en vez de adivinar."""
    text = normalize_text(raw)
    if text == "":
        return {"valor": pd.NA, "unidad": pd.NA, "no_sabe": False, "texto_crudo": pd.NA}

    low = text.lower()
    no_sabe = bool(_NO_SABE_RE.search(text))

    m = _CUADRAS_M_RE.search(low)
    if m:
        return {"valor": int(m.group(1)), "unidad": "metros", "no_sabe": no_sabe, "texto_crudo": text}

    m = _CUADRAS_TXT_RE.search(low)
    if m:
        return {"valor": int(m.group(1)), "unidad": "cuadras", "no_sabe": no_sabe, "texto_crudo": text}

    m = _CUADRAS_SOLO_NUM_RE.match(text)
    if m:
        return {"valor": int(m.group(1)), "unidad": "cuadras", "no_sabe": no_sabe, "texto_crudo": text}

    m = _CUADRAS_WORD_RE.search(low)
    if m:
        valor = _NUM_WORDS[m.group(1).lower()]
        resto = low[m.end():m.end() + 12]
        if _Y_MEDIA_RE.search(resto):
            valor += 0.5
        return {"valor": valor, "unidad": "cuadras", "no_sabe": no_sabe, "texto_crudo": text}

    if _MEDIA_CUADRA_RE.search(low):
        return {"valor": 0.5, "unidad": "cuadras", "no_sabe": no_sabe, "texto_crudo": text}

    log.add(ident, col["code"], "no_se_pudo_extraer_valor_numerico", text)
    return {"valor": pd.NA, "unidad": pd.NA, "no_sabe": no_sabe, "texto_crudo": text}


_LEADING_NUMBER_RE = re.compile(r"^-?\d+(?:[.,]\d+)?")


def parse_numeric(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "":
        return pd.NA
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text.replace(",", "."))
    except ValueError:
        pass
    # Tolera texto pegado al número (ej. '42 años', '50m'): extrae el número líder
    # pero deja constancia de que la celda no era numérica pura.
    m = _LEADING_NUMBER_RE.match(text)
    if m:
        log.add(ident, col["code"], "numerico_con_texto_adicional", text)
        num_text = m.group(0).replace(",", ".")
        return float(num_text) if "." in num_text else int(num_text)
    log.add(ident, col["code"], "no_es_numerico", text)
    return pd.NA


_DATE_FORMATS = ("%d/%m/%Y",)
# La encuesta se realiza desde 2026 en adelante: cualquier fecha fuera de este
# rango es casi con certeza un error de tipeo, se marca pero no se descarta el registro.
_FECHA_MIN = datetime(2026, 1, 1)
_FECHA_MAX = datetime(2030, 12, 31)


def parse_date(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "":
        return pd.NaT
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            if not (_FECHA_MIN <= dt <= _FECHA_MAX):
                log.add(ident, col["code"], "fecha_fuera_de_rango_plausible", text)
            return dt
        except ValueError:
            continue
    log.add(ident, col["code"], "fecha_no_parseable", text)
    return pd.NaT


def parse_timestamp(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "":
        return pd.NaT
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    log.add(ident, col["code"], "timestamp_no_parseable", text)
    return pd.NaT


def parse_plain_text(raw: str, col: dict, log: QualityLog, ident: str):
    """Para metadata / identifier: normaliza forma pero no aplica heurísticas de NA
    (un domicilio o un nombre de encuestadora vacío es NA por vacío, no por texto)."""
    text = normalize_text(raw)
    return text if text != "" else pd.NA

def parse_semistructured_multichoice(raw: str, col: dict, log: QualityLog, ident: str):
    """Separa las opciones con letra del texto libre que Forms concatena con comas."""
    text = normalize_text(raw)
    if text == "":
        return {"opciones": pd.NA, "otros": pd.NA}
    
    valid_codes = {o["codigo"] for o in col.get("options", [])}
    fragments = [f.strip() for f in text.split(",")]
    
    letras = []
    otros = []
    for frag in fragments:
        code_found = match_option_code(frag, valid_codes)
        if code_found:
            letras.append(code_found)
        else:
            # Si no es una letra válida, asume que es el texto libre de 'Otros'
            otros.append(frag)
            
    return {
        "opciones": sorted(set(letras)) if letras else pd.NA,
        "otros": " | ".join(otros) if otros else pd.NA
    }

# ---------------------------------------------------------------------------
# Limpieza de una fila / de la tabla completa
# ---------------------------------------------------------------------------

def _check_header_alignment(df_raw: pd.DataFrame, codebook: dict) -> None:
    """El matching real es por posición (columna 'index'), no por el texto del
    header: los exports de Google Forms son sensibles a espacios/mayúsculas y
    calzar por nombre exacto es frágil. Este chequeo es sólo una alerta para
    detectar si el formulario cambió el ORDEN de las preguntas entre descargas,
    que sí rompería el pipeline."""
    for col in codebook["columnas"]:
        idx = col["index"]
        if idx >= len(df_raw.columns):
            print(f"AVISO: falta la columna en posición {idx} ({col['code']}) en el CSV de entrada.")
            continue
        real_header = normalize_text(df_raw.columns[idx])
        declared_header = normalize_text(col["header_original"])
        if real_header != declared_header:
            print(
                f"AVISO: el header en la posición {idx} no coincide con el codebook.\n"
                f"       esperado: {declared_header!r}\n"
                f"       real:     {real_header!r}\n"
                f"       (se sigue procesando por posición; revisar si el formulario cambió esa pregunta)"
            )


def clean_dataframe(df_raw: pd.DataFrame, codebook: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    log = QualityLog()
    na_tokens = codebook["_na_tokens"]
    
    # MAPEO AGRESIVO POR NOMBRE
    csv_headers_norm = {normalize_text(c): c for c in df_raw.columns}
    col_mapping = {}
    missing_cols = []
    
    for col in codebook["columnas"]:
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

    clean_rows = []
    for _, row in df_raw.iterrows():
        ident = normalize_text(row[id_col_real])
        clean_row = {}
        for col in codebook["columnas"]:
            code = col["code"]
            ctype = col["type"]
            real_col_name = col_mapping[code]
            raw_value = row[real_col_name]

            # Parseo según el tipo
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
                # Procesamos todas las abiertas (cortas o largas) igual
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

            # VALIDACIÓN DE SKIP LOGIC (Condicional)
            # 1. Invertimos la condición: solo evaluamos si la columna tiene parent_code
            if "parent_code" in col:
                val = clean_row.get(code)
                
                # 2. Check seguro de nulos que no explota si recibe una lista
                has_value = True if isinstance(val, list) else pd.notna(val)
                
                if val is not None and has_value:
                    parent_code = col["parent_code"]
                    parent_option = col["parent_option"]
                    
                    if parent_code in clean_row:
                        parent_val = clean_row[parent_code]
                        if isinstance(parent_val, list):
                            parent_letters = parent_val
                        elif isinstance(parent_val, str):
                            parent_letters = parent_val.split("|")
                        else:
                            parent_letters = []
                        
                        if parent_option not in parent_letters:
                            log.add(
                                ident,
                                code,
                                f"texto_condicional_presente_sin_opcion_{parent_option}_en_{parent_code}",
                                str(raw_value),
                            )

        clean_rows.append(clean_row)

    df_clean = pd.DataFrame(clean_rows).set_index("identificador")
    return df_clean, log.to_frame()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV crudo exportado del formulario")
    parser.add_argument("--codebook", required=True, help="codebook.yaml")
    parser.add_argument("--outdir", required=True, help="Carpeta de salida (data/interim)")
    args = parser.parse_args()

    codebook = load_codebook(args.codebook)
    df_raw = pd.read_csv(args.input, dtype=str, keep_default_na=False)

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
