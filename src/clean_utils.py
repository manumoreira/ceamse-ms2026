# -*- coding: utf-8 -*-
"""
clean_utils.py — Funciones auxiliares para la normalización de texto y parseo de tipos
en la etapa de limpieza del pipeline ETL ATSMS26.
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

# ---------------------------------------------------------------------------
# Constantes y Expresiones Regulares
# ---------------------------------------------------------------------------
_WRAPPING_QUOTES = ('"', "'", "“”", "«»")
_CHOICE_FRAGMENT_RE = re.compile(r"^([A-Z])\.\s*(.+)$")
_ZONE_LIKE_FRAGMENT_RE = re.compile(r"^([A-Za-z0-9]+)\s*\(")
_CUADRAS_M_RE = re.compile(r"(\d+(?:,\d+)?)\s*m\b")
_CUADRAS_TXT_RE = re.compile(r"(\d+(?:,\d+)?)\s*cuadras?")
_CUADRAS_SOLO_NUM_RE = re.compile(r"^(\d+(?:,\d+)?)$")
_NO_SABE_RE = re.compile(r"no sabe|no se\b", re.IGNORECASE)
_NUM_WORDS = {
    "un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}
_CUADRAS_WORD_RE = re.compile(r"\b(" + "|".join(_NUM_WORDS) + r")\b\s*cuadras?", re.IGNORECASE)
_MEDIA_CUADRA_RE = re.compile(r"\bmedia\s*cuadra\b", re.IGNORECASE)
_Y_MEDIA_RE = re.compile(r"^\s*y\s+media\b", re.IGNORECASE)
_LEADING_NUMBER_RE = re.compile(r"^-?\d+(?:[.,]\d+)?")
_DATE_FORMATS = ("%d/%m/%Y",)
_FECHA_MIN = datetime(2026, 1, 1)
_FECHA_MAX = datetime(2030, 12, 31)

# ---------------------------------------------------------------------------
# Registro de problemas de calidad
# ---------------------------------------------------------------------------
@dataclass
class QualityLog:
    rows: list[dict] = field(default_factory=list)

    def add(self, identificador: str, code: str, issue: str, raw_value: str):
        self.rows.append({
            "identificador": identificador,
            "code": code,
            "issue": issue,
            "raw_value": raw_value,
        })

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=["identificador", "code", "issue", "raw_value"])

# ---------------------------------------------------------------------------
# Utilidades de Texto
# ---------------------------------------------------------------------------
def normalize_text(value: str) -> str:
    if value is None: return ""
    text = unicodedata.normalize("NFC", str(value))
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) >= 2 and text[0] in "\"'" and text[-1] in "\"'" and text[0] == text[-1]:
        text = text[1:-1].strip()
    return text

def is_na_token(text: str, na_tokens: set[str]) -> bool:
    return text.strip().lower().rstrip(".") in na_tokens

def match_option_code(fragment: str, valid_codes: set[str]) -> str | None:
    if fragment in valid_codes: return fragment
    m = _CHOICE_FRAGMENT_RE.match(fragment)
    if m and m.group(1) in valid_codes: return m.group(1)
    m = _ZONE_LIKE_FRAGMENT_RE.match(fragment)
    if m and m.group(1) in valid_codes: return m.group(1)
    return None

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def parse_single_choice(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "": return pd.NA
    valid_codes = {o["codigo"] for o in col.get("options", [])}
    fragments = [f.strip() for f in text.split(",")]
    letters = []
    for frag in fragments:
        code_found = match_option_code(frag, valid_codes)
        if code_found: letters.append(code_found)
        else: log.add(ident, col["code"], "fragmento_no_reconocido_como_opcion", frag)
    if not letters: return pd.NA
    if len(letters) > 1:
        log.add(ident, col["code"], "single_choice_con_mas_de_una_opcion_marcada", text)
        return "|".join(letters)
    return letters[0]

def parse_multi_choice(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "": return pd.NA
    valid_codes = {o["codigo"] for o in col.get("options", [])}
    fragments = [f.strip() for f in text.split(",")]
    letters = []
    for frag in fragments:
        code_found = match_option_code(frag, valid_codes)
        if code_found: letters.append(code_found)
        else: log.add(ident, col["code"], "fragmento_no_reconocido_como_opcion", frag)
    return sorted(set(letters)) if letters else pd.NA

def parse_free_text(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "": return pd.NA
    return text

def parse_semistructured_cuadras(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "": return {"valor": pd.NA, "unidad": pd.NA, "no_sabe": False, "texto_crudo": pd.NA}
    low = text.lower()
    no_sabe = bool(_NO_SABE_RE.search(text))

    m = _CUADRAS_M_RE.search(low)
    if m:
        val_str = m.group(1).replace(",", ".")
        valor = float(val_str) if "." in val_str else int(val_str)
        return {"valor": valor, "unidad": "metros", "no_sabe": no_sabe, "texto_crudo": text}

    m = _CUADRAS_TXT_RE.search(low)
    if m:
        val_str = m.group(1).replace(",", ".")
        valor = float(val_str) if "." in val_str else int(val_str)
        return {"valor": valor, "unidad": "cuadras", "no_sabe": no_sabe, "texto_crudo": text}

    m = _CUADRAS_SOLO_NUM_RE.match(text)
    if m:
        val_str = m.group(1).replace(",", ".")
        valor = float(val_str) if "." in val_str else int(val_str)
        return {"valor": valor, "unidad": "cuadras", "no_sabe": no_sabe, "texto_crudo": text}

    m = _CUADRAS_WORD_RE.search(low)
    if m:
        valor = _NUM_WORDS[m.group(1).lower()]
        resto = low[m.end():m.end() + 12]
        if _Y_MEDIA_RE.search(resto): valor += 0.5
        return {"valor": valor, "unidad": "cuadras", "no_sabe": no_sabe, "texto_crudo": text}

    if _MEDIA_CUADRA_RE.search(low):
        return {"valor": 0.5, "unidad": "cuadras", "no_sabe": no_sabe, "texto_crudo": text}

    log.add(ident, col["code"], "no_se_pudo_extraer_valor_numerico", text)
    return {"valor": pd.NA, "unidad": pd.NA, "no_sabe": no_sabe, "texto_crudo": text}

def parse_numeric(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "": return pd.NA
    try: return int(text)
    except ValueError: pass
    try: return float(text.replace(",", "."))
    except ValueError: pass
    m = _LEADING_NUMBER_RE.match(text)
    if m:
        log.add(ident, col["code"], "numerico_con_texto_adicional", text)
        num_text = m.group(0).replace(",", ".")
        return float(num_text) if "." in num_text else int(num_text)
    log.add(ident, col["code"], "no_es_numerico", text)
    return pd.NA

def parse_date(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "": return pd.NaT
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            if not (_FECHA_MIN <= dt <= _FECHA_MAX):
                log.add(ident, col["code"], "fecha_fuera_de_rango_plausible", text)
            return dt
        except ValueError: continue
    log.add(ident, col["code"], "fecha_no_parseable", text)
    return pd.NaT

def parse_timestamp(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "": return pd.NaT
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try: return datetime.strptime(text, fmt)
        except ValueError: continue
    log.add(ident, col["code"], "timestamp_no_parseable", text)
    return pd.NaT

def parse_plain_text(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    return text if text != "" else pd.NA

def parse_semistructured_multichoice(raw: str, col: dict, log: QualityLog, ident: str):
    text = normalize_text(raw)
    if text == "": return {"opciones": pd.NA, "otros": pd.NA}
    valid_codes = {o["codigo"] for o in col.get("options", [])}
    fragments = [f.strip() for f in text.split(",")]
    letras = []
    otros = []
    for frag in fragments:
        code_found = match_option_code(frag, valid_codes)
        if code_found: letras.append(code_found)
        else: otros.append(frag)
    return {
        "opciones": sorted(set(letras)) if letras else pd.NA,
        "otros": " | ".join(otros) if otros else pd.NA
    }