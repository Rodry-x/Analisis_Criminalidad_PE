#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ETL del DataMart de Victimizacion y Confianza en la PNP (2013-2024).

El CSV original esta codificado en CP1252 (Windows-1252), por lo que las
tildes y la letra N se ven como '?' al abrirlo como UTF-8. Este ETL:

  1. Detecta la codificacion real del archivo crudo.
  2. Genera una copia fiel en UTF-8 con BOM (utf-8-sig) dentro de
     Dataset-Procesado/Indicadores-de-Victimizacion-y-confianza-PNP_2013-2024/.
  3. Trabaja sobre la copia UTF-8 (pipeline 100% UTF-8 de aqui en adelante).
  4. Limpia, valida y consolida los datos.
  5. Genera un script SQL autocontenido y, opcionalmente, lo ejecuta con
     sqlcmd contra SQL Server.

Notas de diseno del dataset:
  - PERIODO es constante ('AÑO') en todas las filas -> se elimina.
  - 'VALOR PERIODO' contiene el anio -> se renombra a anio_registro.
  - AMBITO_PROY es redundante con DEPARTAMENTO; se conserva como 'ambito'
    porque evita confundir el agregado nacional con un departamento.
  - DEPARTAMENTO = 'NACIONAL' no es un departamento real: en esas filas se
    guarda departamento = NULL y cod_ubicacion = 0.
  - El dataset no tiene mes: el grano es anual.

Uso:
    conda run -n ciencia-de-datos python Pipeline/etl_victimizacion.py
    conda run -n ciencia-de-datos python Pipeline/etl_victimizacion.py --generate-only
    conda run -n ciencia-de-datos python Pipeline/etl_victimizacion.py --server localhost
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import subprocess
import sys
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Configuracion del proyecto
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "Dataset-Crudo" / "Indicadores-de-Victimizacion-y-confianza-PNP_2013-2024"
PROCESSED_DIR = (
    PROJECT_ROOT
    / "Dataset-Procesado"
    / "Indicadores-de-Victimizacion-y-confianza-PNP_2013-2024"
)
UTF8_FILE = PROCESSED_DIR / "Victimizacion_Confianza_PNP_2013_2024_utf8.csv"
DATABASE_DIR = PROJECT_ROOT / "Database"
LOG_DIR = PROJECT_ROOT / "Pipeline" / "logs"
SQL_FILE = DATABASE_DIR / "04_victimizacion_datamart.sql"

DATASET_NAME = "Victimizacion y Confianza PNP 2013-2024"
DEFAULT_DATABASE = "DBVictimizacionConfianzaPNP"
TABLE_NAME = "dm.VictimizacionConfianzaPNP"
BATCH_SIZE = 1_000

SOURCE_COLUMNS = [
    "VALOR",
    "INDICADOR",
    "CLASIF",
    "PERIODO",
    "VALOR PERIODO",
    "COD_UBICACION",
    "AMBITO_PROY",
    "DEPARTAMENTO",
]

# Orden de columnas del DataMart (sin id_indicador ni fecha_carga)
FINAL_COLUMNS = [
    "anio_registro",
    "fecha_referencia",
    "ambito",
    "cod_ubicacion",
    "departamento",
    "indicador",
    "clasif",
    "valor",
    "es_anio_parcial",
    "archivo_origen",
]

# Variantes de nombres de departamento que se homologan al estilo canonico
# usado en los Dataset 1-3 (mayusculas sin tildes).
DEPARTAMENTO_CANONICO: dict[str, str] = {
    "ÁNCASH": "ANCASH",
    "APURÍMAC": "APURIMAC",
    "HUÁNUCO": "HUANUCO",
    "JUNÍN": "JUNIN",
    "SAN MARTÍN": "SAN MARTIN",
    "REGIÓN LIMA": "REGION LIMA",
}

# Departamento canonico -> codigo de ubicacion del dataset.
# Lima se divide en LIMA METROPOLITANA (1501) y REGION LIMA (1599); por eso el
# codigo 15 (Lima como departamento completo) nunca se usa.
DEPARTAMENTO_CODIGO: dict[str, int] = {
    "AMAZONAS": 1,
    "ANCASH": 2,
    "APURIMAC": 3,
    "AREQUIPA": 4,
    "AYACUCHO": 5,
    "CAJAMARCA": 6,
    "PROV. CONST. DEL CALLAO": 7,
    "CUSCO": 8,
    "HUANCAVELICA": 9,
    "HUANUCO": 10,
    "ICA": 11,
    "JUNIN": 12,
    "LA LIBERTAD": 13,
    "LAMBAYEQUE": 14,
    # 15 = LIMA (departamento completo): no aplica en este dataset.
    "LORETO": 16,
    "MADRE DE DIOS": 17,
    "MOQUEGUA": 18,
    "PASCO": 19,
    "PIURA": 20,
    "PUNO": 21,
    "SAN MARTIN": 22,
    "TACNA": 23,
    "TUMBES": 24,
    "UCAYALI": 25,
    "LIMA METROPOLITANA": 1501,
    "REGION LIMA": 1599,
}

NACIONAL = "NACIONAL"
COD_NACIONAL = 0
AMBITOS_VALIDOS = {"NACIONAL", "DEPARTAMENTO"}

INDICADORES_ESPERADOS = {
    "PORCENTAJE DE CONFIANZA EN LA PNP",
    "PORCENTAJE DE PERCEPCIÓN DE INSEGURIDAD AL CAMINAR SOLO(A) DE NOCHE EN SU ZONA O BARRIO",
    "PORCENTAJE DE VICTIMIZACIÓN",
    "PORCENTAJE DE VICTIMIZACIÓN POR EL DELITO DE ROBO E INTENTO DE ROBO DE DINERO, CARTERA Y CELULAR",
    "PORCENTAJE DE VICTIMIZACIÓN POR ESTAFA",
}

VALID_YEARS = (2013, 2024)

# Codificaciones candidatas, en orden de preferencia.
CANDIDATE_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ETL del DataMart de Victimizacion y Confianza PNP 2013-2024."
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Solo genera el archivo .sql, sin ejecutarlo en SQL Server.",
    )
    parser.add_argument(
        "--server",
        default="localhost",
        help="Instancia de SQL Server (por defecto: localhost).",
    )
    parser.add_argument(
        "--database",
        default=DEFAULT_DATABASE,
        help=f"Nombre de la base de datos (por defecto: {DEFAULT_DATABASE}).",
    )
    parser.add_argument(
        "--sqlcmd",
        default=None,
        help="Ruta explicita a sqlcmd.exe. Si se omite, se busca en el PATH.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Filas por INSERT masivo (por defecto: {BATCH_SIZE}).",
    )
    parser.add_argument(
        "--reuse-utf8",
        action="store_true",
        help="Reutiliza la copia UTF-8 existente en Dataset-Procesado "
        "(no vuelve a convertir el archivo crudo).",
    )
    return parser.parse_args()


def configure_logging() -> tuple[Path, str]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"etl_victimizacion_{stamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    return log_path, stamp


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_sqlcmd(explicit: str | None = None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise FileNotFoundError(f"No existe sqlcmd en: {path}")
        return path

    found = shutil.which("sqlcmd")
    if found:
        return Path(found)

    base = Path(r"C:\Program Files\Microsoft SQL Server\Client SDK\ODBC")
    candidates = sorted(base.glob(r"*\Tools\Binn\SQLCMD.EXE"), reverse=True)
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        "No se encontro sqlcmd.exe. Instala SQL Server Command Line Utilities "
        "o pasa la ruta con --sqlcmd."
    )


def sql_n(value: Any) -> str:
    """Devuelve un literal Unicode de SQL Server escapando comillas simples."""
    return "N'" + str(value).replace("'", "''") + "'"


def sql_n_null(value: Any) -> str:
    """Literal Unicode o NULL cuando el valor es vacio."""
    if value is None:
        return "NULL"
    if not isinstance(value, str) and pd.isna(value):
        return "NULL"
    if isinstance(value, str) and value.strip() == "":
        return "NULL"
    return sql_n(value)


def find_raw_file() -> Path:
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No se encontro ningun CSV en: {RAW_DIR}")
    if len(files) > 1:
        raise ValueError(
            f"Se esperaba un unico CSV en {RAW_DIR}, se encontraron {len(files)}."
        )
    return files[0]


# ---------------------------------------------------------------------------
# Conversion de codificacion
# ---------------------------------------------------------------------------
def detect_encoding(data: bytes) -> str:
    for encoding in CANDIDATE_ENCODINGS:
        try:
            data.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(
        "desconocida", data, 0, 1, "No se pudo decodificar el archivo CSV."
    )


def convert_to_utf8(raw_file: Path, force: bool = True) -> dict[str, Any]:
    """Convierte el CSV crudo a UTF-8 con BOM conservando el contenido exacto."""
    if not raw_file.exists():
        raise FileNotFoundError(f"No existe el archivo crudo: {raw_file}")

    raw_bytes = raw_file.read_bytes()
    source_encoding = detect_encoding(raw_bytes)
    text = raw_bytes.decode(source_encoding)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    converted = False
    if force or not UTF8_FILE.exists():
        # utf-8-sig agrega BOM para que Excel detecte UTF-8 sin ambiguedad.
        UTF8_FILE.write_bytes(text.encode("utf-8-sig"))
        converted = True

    utf8_bytes = UTF8_FILE.read_bytes()
    if not utf8_bytes.startswith(b"\xef\xbb\xbf"):
        raise ValueError("La copia UTF-8 no tiene BOM; se esperaba utf-8-sig.")

    latin_chars = sorted({ch for ch in text if ord(ch) > 127})
    info = {
        "archivo_crudo": str(raw_file.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "codificacion_origen": source_encoding,
        "archivo_utf8": str(UTF8_FILE.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "codificacion_destino": "utf-8-sig",
        "convertido_en_esta_corrida": converted,
        "caracteres_no_ascii": latin_chars,
        "sha256_crudo": sha256_file(raw_file),
        "sha256_utf8": sha256_file(UTF8_FILE),
        "bytes_crudo": len(raw_bytes),
        "bytes_utf8": len(utf8_bytes),
    }

    logging.info("Codificacion detectada del archivo crudo: %s", source_encoding)
    if converted:
        logging.info("Copia UTF-8 generada: %s", UTF8_FILE)
    else:
        logging.info("Se reutiliza la copia UTF-8 existente: %s", UTF8_FILE)
    logging.info(
        "Caracteres no ASCII conservados: %s", "".join(latin_chars) or "(ninguno)"
    )
    return info


# ---------------------------------------------------------------------------
# Extraccion
# ---------------------------------------------------------------------------
def load_csv(raw_file: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    logging.info("Leyendo copia UTF-8: %s", UTF8_FILE)
    df = pd.read_csv(
        UTF8_FILE,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    df.columns = [col.strip() for col in df.columns]

    missing = [col for col in SOURCE_COLUMNS if col not in df.columns]
    extra = [col for col in df.columns if col not in SOURCE_COLUMNS]
    if missing or extra:
        raise ValueError(
            f"Esquema inesperado en {raw_file.name}. "
            f"Faltan: {missing}. Sobran: {extra}."
        )

    df = df[SOURCE_COLUMNS].copy()
    df["archivo_origen"] = raw_file.name

    file_stats = {
        "archivo": raw_file.name,
        "filas": int(len(df)),
        "sha256": sha256_file(raw_file),
    }
    logging.info("  %-42s %9s filas", raw_file.name, f"{len(df):,}")
    return df, file_stats


# ---------------------------------------------------------------------------
# Limpieza y transformacion
# ---------------------------------------------------------------------------
def parse_decimal(value: str) -> Decimal | None:
    """Convierte VALOR a Decimal conservando el decimal del origen."""
    text = value.strip().replace(" ", "")
    if text == "":
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    return number


def clean_data(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame | None]:
    raw_rows = len(df)
    df = df.copy()

    # 1. Normalizacion de texto (conserva tildes y N).
    text_columns = ["INDICADOR", "PERIODO", "AMBITO_PROY", "DEPARTAMENTO"]
    for column in text_columns:
        df[column] = (
            df[column]
            .astype(str)
            .str.replace("\u00a0", " ", regex=False)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
            .str.upper()
        )

    # 2. PERIODO debe ser constante: si no lo es, no se puede eliminar.
    periodos = sorted(df["PERIODO"].unique().tolist())
    if periodos != ["AÑO"]:
        raise ValueError(
            "PERIODO ya no es constante en el origen: "
            f"{periodos}. Revisar el diseno antes de eliminar la columna."
        )
    logging.info("PERIODO es constante ('AÑO') en %s filas: se elimina.", f"{raw_rows:,}")

    # 3. Canonicalizacion del departamento.
    antes = df["DEPARTAMENTO"].copy()
    df["DEPARTAMENTO"] = df["DEPARTAMENTO"].replace(DEPARTAMENTO_CANONICO)
    departamentos_canonizados = int((antes != df["DEPARTAMENTO"]).sum())
    if departamentos_canonizados:
        detalle = antes[antes != df["DEPARTAMENTO"]].value_counts().to_dict()
        logging.info(
            "Departamentos homologados: %s filas %s",
            f"{departamentos_canonizados:,}",
            detalle,
        )

    # 4. Conversion numerica
    anio = pd.to_numeric(df["VALOR PERIODO"], errors="coerce")
    clasif = pd.to_numeric(df["CLASIF"], errors="coerce")
    cod_src = pd.to_numeric(df["COD_UBICACION"], errors="coerce")
    valor = df["VALOR"].map(parse_decimal)

    # 5. Derivar cod_ubicacion desde el nombre del departamento.
    #    El nombre es el campo confiable: en el origen hay 6 filas de 2013
    #    (victimizacion por estafa) cuyo COD_UBICACION esta desalineado.
    dep = df["DEPARTAMENTO"]
    cod_derivado = dep.map(DEPARTAMENTO_CODIGO)
    es_nacional = dep.eq(NACIONAL)
    cod_derivado = cod_derivado.where(~es_nacional, COD_NACIONAL)

    sin_mapeo = ~es_nacional & cod_derivado.isna()
    if sin_mapeo.any():
        desconocidos = sorted(dep[sin_mapeo].unique().tolist())
        raise ValueError(
            "Hay departamentos sin codigo de ubicacion definido: "
            f"{desconocidos}. Agregalos a DEPARTAMENTO_CODIGO."
        )

    corregidas = (~es_nacional) & cod_src.notna() & (cod_src.astype("Int64") != cod_derivado.astype("Int64"))
    filas_codigo_corregido = int(corregidas.sum())
    codigos_corregidos: list[dict[str, Any]] = []
    if filas_codigo_corregido:
        detalle_corregido = df.loc[corregidas, ["VALOR PERIODO", "INDICADOR", "COD_UBICACION", "DEPARTAMENTO"]]
        for row in detalle_corregido.itertuples(index=False):
            codigos_corregidos.append(
                {
                    "anio_registro": int(row[0]),
                    "indicador": row[1],
                    "cod_origen": int(row[2]),
                    "cod_derivado": int(DEPARTAMENTO_CODIGO[row[3]]),
                    "departamento": row[3],
                }
            )
            logging.warning(
                "Codigo corregido: %s | %s | cod %s -> %s | %s",
                row[0],
                row[1][:45],
                row[2],
                DEPARTAMENTO_CODIGO[row[3]],
                row[3],
            )

    # 6. Reglas de calidad
    invalid_anio = anio.isna() | (anio % 1 != 0) | ~anio.between(*VALID_YEARS)
    invalid_clasif = clasif.isna() | (clasif % 1 != 0) | ~clasif.between(0, 100)
    invalid_valor = valor.isna() | (valor < 0) | (valor > 100)
    invalid_ambito = ~df["AMBITO_PROY"].isin(AMBITOS_VALIDOS)
    invalid_cod = cod_src.isna() | (cod_src % 1 != 0) | (cod_src < 0)

    # Coherencia ambito <-> departamento
    ambito_nacional = df["AMBITO_PROY"].eq(NACIONAL)
    incoherente = (ambito_nacional & ~es_nacional) | (~ambito_nacional & es_nacional)

    empty_text = (
        df["INDICADOR"].eq("")
        | df["AMBITO_PROY"].eq("")
        | (df["DEPARTAMENTO"].eq("") & ~ambito_nacional)
    )

    indicadores_desconocidos = sorted(
        set(df["INDICADOR"].unique()) - INDICADORES_ESPERADOS
    )
    if indicadores_desconocidos:
        logging.warning(
            "Indicadores fuera del catalogo esperado: %s", indicadores_desconocidos
        )

    valid = ~(
        invalid_anio
        | invalid_clasif
        | invalid_valor
        | invalid_ambito
        | invalid_cod
        | incoherente
        | empty_text
    )

    motivos = {
        "anio_invalido": int(invalid_anio.sum()),
        "clasif_invalido": int(invalid_clasif.sum()),
        "valor_invalido": int(invalid_valor.sum()),
        "ambito_invalido": int(invalid_ambito.sum()),
        "cod_ubicacion_invalido": int(invalid_cod.sum()),
        "ambito_departamento_incoherente": int(incoherente.sum()),
        "texto_requerido_vacio": int(empty_text.sum()),
    }
    rejected_rows = int((~valid).sum())

    rejected: pd.DataFrame | None = None
    if rejected_rows:
        rejected = df.loc[~valid].copy()
        rejected["err_anio"] = invalid_anio[~valid].astype("int8").to_numpy()
        rejected["err_clasif"] = invalid_clasif[~valid].astype("int8").to_numpy()
        rejected["err_valor"] = invalid_valor[~valid].astype("int8").to_numpy()
        rejected["err_ambito"] = invalid_ambito[~valid].astype("int8").to_numpy()
        rejected["err_cod_ubicacion"] = invalid_cod[~valid].astype("int8").to_numpy()
        rejected["err_incoherente"] = incoherente[~valid].astype("int8").to_numpy()
        rejected["err_texto_vacio"] = empty_text[~valid].astype("int8").to_numpy()
        logging.warning("Filas rechazadas: %s", f"{rejected_rows:,}")

    # 7. Aplicar filtro y tipos definitivos
    df = df.loc[valid].copy()
    df["anio_registro"] = anio[valid].astype("int16")
    df["clasif"] = clasif[valid].astype("int16")
    df["cod_ubicacion"] = cod_derivado[valid].astype("int64")
    df["valor"] = valor[valid]

    # 8. Columnas derivadas del DataMart
    nacional = df["AMBITO_PROY"].eq(NACIONAL)
    df["ambito"] = df["AMBITO_PROY"]
    df["departamento"] = df["DEPARTAMENTO"].where(~nacional, None)
    df["indicador"] = df["INDICADOR"]
    df["fecha_referencia"] = df["anio_registro"].astype(str) + "-01-01"

    # 9. Cobertura -> anio parcial
    #    Un anio esta completo si tiene todas las combinaciones
    #    indicador x alcance del dataset (5 x 27 = 135 filas).
    alcances_total = int(df["cod_ubicacion"].nunique())
    indicadores_total = int(df["indicador"].nunique())
    esperado_por_anio = alcances_total * indicadores_total
    filas_por_anio = df.groupby("anio_registro").size()
    anios_parciales = sorted(
        int(anio_) for anio_, filas in filas_por_anio.items() if filas < esperado_por_anio
    )
    df["es_anio_parcial"] = (
        df["anio_registro"].isin(anios_parciales).astype("int8")
    )

    # 10. Duplicados de grano: no deberia haber ninguno.
    grain = ["anio_registro", "indicador", "cod_ubicacion"]
    duplicados = int(df.duplicated(subset=grain).sum())
    if duplicados:
        detalle = (
            df[df.duplicated(subset=grain, keep=False)]
            .sort_values(grain)
            .loc[:, grain + ["valor"]]
            .head(20)
        )
        raise ValueError(
            "Existen duplicados en el grano (anio_registro, indicador, "
            f"cod_ubicacion): {duplicados}. Ejemplo:\n{detalle.to_string(index=False)}"
        )

    df = (
        df.sort_values(["anio_registro", "cod_ubicacion", "indicador"])
        .reset_index(drop=True)
        .loc[:, FINAL_COLUMNS]
    )

    # 11. Reconciliacion interna
    if df["valor"].sum() != pd.Series(valor[valid].tolist()).sum():
        raise ValueError("La suma de valor cambio durante la transformacion.")
    if len(df) != raw_rows - rejected_rows:
        raise ValueError("El conteo de filas no cuadra tras la limpieza.")

    metrics: dict[str, Any] = {
        "filas_leidas": int(raw_rows),
        "filas_rechazadas": rejected_rows,
        "filas_agrupadas": 0,
        "filas_cargadas": int(len(df)),
        "total_indicadores": indicadores_total,
        "alcances": alcances_total,
        "esperado_por_anio": int(esperado_por_anio),
        "filas_codigo_corregido": filas_codigo_corregido,
        "codigos_corregidos": codigos_corregidos,
        "departamentos": int(df["departamento"].nunique()),
        "ambitos": int(df["ambito"].nunique()),
        "filas_nacionales": int(df["ambito"].eq(NACIONAL).sum()),
        "anio_min": int(df["anio_registro"].min()),
        "anio_max": int(df["anio_registro"].max()),
        "anios_parciales": anios_parciales,
        "filas_anio_parcial": int(df["es_anio_parcial"].sum()),
        "suma_valor": float(df["valor"].sum()),
        "departamentos_canonizados": departamentos_canonizados,
        "motivos_rechazo": motivos,
    }

    logging.info("Filas cargadas: %s", f"{metrics['filas_cargadas']:,}")
    logging.info(
        "Dimensiones: %d indicadores, %d alcances, %d departamentos, %d nacionales",
        metrics["total_indicadores"],
        metrics["alcances"],
        metrics["departamentos"],
        metrics["filas_nacionales"],
    )
    logging.info(
        "Cobertura esperada por anio: %s filas", f"{esperado_por_anio:,}"
    )
    if anios_parciales:
        logging.warning("Anios parciales detectados: %s", anios_parciales)
    if filas_codigo_corregido:
        logging.warning(
            "Codigos de ubicacion corregidos desde el departamento: %s",
            f"{filas_codigo_corregido:,}",
        )

    return df, metrics, rejected


# ---------------------------------------------------------------------------
# Generacion del script SQL
# ---------------------------------------------------------------------------
def write_sql(
    df: pd.DataFrame,
    metrics: dict[str, Any],
    file_stats: dict[str, Any],
    sql_path: Path,
    database: str,
    generated_at: datetime,
    batch_size: int,
) -> None:
    sql_path.parent.mkdir(parents=True, exist_ok=True)

    archivos = file_stats["archivo"]
    filas_esperadas = metrics["filas_cargadas"]
    total_valor = f"{df['valor'].sum():.1f}"
    detalle_json = json.dumps(metrics, ensure_ascii=False)
    fecha_iso = generated_at.strftime("%Y-%m-%dT%H:%M:%S")

    header = f"""/* ============================================================================
   DataMart: {DATASET_NAME}
   ----------------------------------------------------------------------------
   Generado por : Pipeline/etl_victimizacion.py
   Fecha        : {generated_at.strftime('%Y-%m-%d %H:%M:%S')}
   Base de datos: {database}
   Tabla destino: {TABLE_NAME}
   Archivo      : {archivos}
   Filas        : {filas_esperadas:,}
   Suma VALOR   : {total_valor}
   Codificacion origen : {metrics.get('codificacion', {}).get('codificacion_origen', '')}
   Copia UTF-8         : {metrics.get('codificacion', {}).get('archivo_utf8', '')}
   Hash origen  : {metrics.get('hash_origen', '')}

   Limpieza aplicada:
     - Conversion CP1252 -> UTF-8 (utf-8-sig) conservando tildes.
     - TRIM y colapso de espacios; textos en mayusculas.
     - PERIODO eliminada (constante 'AÑO' en el 100% de las filas).
     - VALOR PERIODO renombrada a anio_registro.
     - Departamentos homologados al estilo canonico sin tildes.
     - cod_ubicacion re-derivado del departamento (corrige 6 filas de 2013).
     - ambito = NACIONAL / DEPARTAMENTO; departamento = NULL si es nacional.
     - VALOR convertido a DECIMAL(5,1) (porcentaje 0-100).
     - Validacion de anio (2013-2024), indicador, ambito, clasif y valor.
     - fecha_referencia derivada (01 de enero del anio).
     - es_anio_parcial = 1 para anios con cobertura incompleta (2013).

   Mapeo de columnas:
     VALOR         -> valor
     INDICADOR     -> indicador
     CLASIF        -> clasif
     PERIODO       -> (eliminada)
     VALOR PERIODO -> anio_registro
     COD_UBICACION -> cod_ubicacion (re-derivado del departamento)
     AMBITO_PROY   -> ambito
     DEPARTAMENTO  -> departamento (NULL para NACIONAL)
   ============================================================================ */

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
GO

USE [master];
GO

IF DB_ID(N'{database}') IS NULL
BEGIN
    PRINT N'Creando base de datos {database}...';
    CREATE DATABASE [{database}];
END
ELSE
BEGIN
    PRINT N'La base de datos {database} ya existe.';
END
GO

USE [{database}];
GO

IF SCHEMA_ID(N'dm') IS NULL
    EXEC(N'CREATE SCHEMA dm');
IF SCHEMA_ID(N'etl') IS NULL
    EXEC(N'CREATE SCHEMA etl');
GO

IF OBJECT_ID(N'etl.ControlCarga', N'U') IS NULL
BEGIN
    CREATE TABLE etl.ControlCarga (
        id_carga                INT IDENTITY(1,1) NOT NULL,
        dataset                 NVARCHAR(150) NOT NULL,
        archivo_origen          NVARCHAR(400) NOT NULL,
        hash_origen             CHAR(64) NOT NULL,
        filas_leidas            INT NOT NULL,
        filas_rechazadas        INT NOT NULL,
        filas_agrupadas         INT NOT NULL,
        filas_cargadas          INT NOT NULL,
        filas_codigo_corregido  INT NOT NULL,
        filas_anio_parcial      INT NOT NULL,
        total_indicadores       INT NOT NULL,
        fecha_inicio            DATETIME2(0) NOT NULL,
        fecha_fin               DATETIME2(0) NOT NULL,
        estado                  NVARCHAR(20) NOT NULL,
        detalle                 NVARCHAR(MAX) NULL,
        CONSTRAINT PK_ControlCarga PRIMARY KEY CLUSTERED (id_carga)
    );
END
GO

IF OBJECT_ID(N'{TABLE_NAME}', N'U') IS NOT NULL
BEGIN
    PRINT N'Eliminando tabla {TABLE_NAME} para recargar...';
    DROP TABLE {TABLE_NAME};
END
GO

CREATE TABLE {TABLE_NAME} (
    id_indicador      INT IDENTITY(1,1) NOT NULL,
    anio_registro     SMALLINT NOT NULL,
    fecha_referencia  DATE NOT NULL,
    ambito            NVARCHAR(15) NOT NULL,
    cod_ubicacion     INT NOT NULL,
    departamento      NVARCHAR(60) NULL,
    indicador         NVARCHAR(200) NOT NULL,
    clasif            SMALLINT NOT NULL,
    valor             DECIMAL(5,1) NOT NULL,
    es_anio_parcial   BIT NOT NULL,
    archivo_origen    NVARCHAR(200) NOT NULL,
    fecha_carga       DATETIME2(0) NOT NULL
        CONSTRAINT DF_VictimizacionConfianzaPNP_fecha_carga DEFAULT SYSDATETIME(),
    CONSTRAINT PK_VictimizacionConfianzaPNP PRIMARY KEY CLUSTERED (id_indicador),
    CONSTRAINT CK_VictimizacionConfianzaPNP_anio
        CHECK (anio_registro BETWEEN 2013 AND 2100),
    CONSTRAINT CK_VictimizacionConfianzaPNP_valor
        CHECK (valor BETWEEN 0 AND 100),
    CONSTRAINT CK_VictimizacionConfianzaPNP_clasif
        CHECK (clasif BETWEEN 0 AND 100),
    CONSTRAINT CK_VictimizacionConfianzaPNP_ambito
        CHECK (ambito IN (N'NACIONAL', N'DEPARTAMENTO')),
    CONSTRAINT CK_VictimizacionConfianzaPNP_ubicacion
        CHECK (
            (ambito = N'NACIONAL' AND cod_ubicacion = 0 AND departamento IS NULL)
            OR
            (ambito = N'DEPARTAMENTO' AND cod_ubicacion <> 0 AND departamento IS NOT NULL)
        )
);
GO

PRINT N'Cargando {filas_esperadas:,} filas en {TABLE_NAME}...';
GO

"""

    insert_prefix = (
        f"INSERT INTO {TABLE_NAME}\n"
        "    (anio_registro, fecha_referencia, ambito, cod_ubicacion, "
        "departamento, indicador, clasif, valor, es_anio_parcial, archivo_origen)\n"
        "VALUES\n"
    )

    with sql_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(header)

        total = len(df)
        for start in range(0, total, batch_size):
            batch = df.iloc[start : start + batch_size]
            values: list[str] = []
            for row in batch.itertuples(index=False, name=None):
                (
                    anio_registro,
                    fecha_referencia,
                    ambito,
                    cod_ubicacion,
                    departamento,
                    indicador,
                    clasif,
                    valor,
                    es_anio_parcial,
                    archivo_origen,
                ) = row
                values.append(
                    "("
                    f"{int(anio_registro)}, "
                    f"'{fecha_referencia}', "
                    f"{sql_n(ambito)}, "
                    f"{int(cod_ubicacion)}, "
                    f"{sql_n_null(departamento)}, "
                    f"{sql_n(indicador)}, "
                    f"{int(clasif)}, "
                    f"{valor:.1f}, "
                    f"{int(es_anio_parcial)}, "
                    f"{sql_n(archivo_origen)}"
                    ")"
                )
            fh.write(insert_prefix)
            fh.write(",\n".join(values))
            fh.write(";\nGO\n\n")

    footer = f"""PRINT N'Creando indices...';
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_VictimizacionConfianzaPNP_Grano
    ON {TABLE_NAME} (anio_registro, indicador, cod_ubicacion)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

CREATE NONCLUSTERED INDEX IX_VictimizacionConfianzaPNP_Anio
    ON {TABLE_NAME} (anio_registro)
    INCLUDE (valor)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

CREATE NONCLUSTERED INDEX IX_VictimizacionConfianzaPNP_Indicador
    ON {TABLE_NAME} (indicador)
    INCLUDE (valor)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

CREATE NONCLUSTERED INDEX IX_VictimizacionConfianzaPNP_Ubicacion
    ON {TABLE_NAME} (cod_ubicacion)
    INCLUDE (valor)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

PRINT N'Registrando control de carga...';
GO

INSERT INTO etl.ControlCarga
    (dataset, archivo_origen, hash_origen, filas_leidas, filas_rechazadas,
     filas_agrupadas, filas_cargadas, filas_codigo_corregido,
     filas_anio_parcial, total_indicadores, fecha_inicio, fecha_fin,
     estado, detalle)
VALUES
    ({sql_n(DATASET_NAME)},
     {sql_n(archivos)},
     '{metrics.get('hash_origen', '')}',
     {metrics['filas_leidas']},
     {metrics['filas_rechazadas']},
     {metrics['filas_agrupadas']},
     {metrics['filas_cargadas']},
     {metrics['filas_codigo_corregido']},
     {metrics['filas_anio_parcial']},
     {metrics['total_indicadores']},
     '{fecha_iso}',
     CONVERT(DATETIME2(0), SYSDATETIME()),
     N'EXITOSO',
     {sql_n(detalle_json)});
GO

PRINT N'Validando resultados...';
GO

DECLARE @filas INT = (SELECT COUNT(*) FROM {TABLE_NAME});
DECLARE @total DECIMAL(18,1) = (SELECT SUM(valor) FROM {TABLE_NAME});

IF @filas <> {filas_esperadas}
    THROW 51000, N'Validacion fallida: el conteo de filas no coincide con el ETL.', 1;

IF ABS(@total - {total_valor}) > 0.05
    THROW 51001, N'Validacion fallida: la suma de valor no coincide con el ETL.', 1;

IF EXISTS (
    SELECT 1
    FROM {TABLE_NAME}
    GROUP BY anio_registro, indicador, cod_ubicacion
    HAVING COUNT(*) > 1
)
    THROW 51002, N'Validacion fallida: existen duplicados en el grano del DataMart.', 1;

IF EXISTS (
    SELECT 1
    FROM {TABLE_NAME}
    WHERE (ambito = N'NACIONAL' AND departamento IS NOT NULL)
       OR (ambito = N'DEPARTAMENTO' AND departamento IS NULL)
)
    THROW 51003, N'Validacion fallida: ambito y departamento son incoherentes.', 1;

PRINT N'Validacion correcta.';
GO

SELECT
    COUNT(*)                        AS filas_cargadas,
    SUM(valor)                      AS suma_valor,
    COUNT(DISTINCT indicador)       AS indicadores,
    COUNT(DISTINCT cod_ubicacion)   AS alcances,
    COUNT(DISTINCT departamento)    AS departamentos,
    SUM(CASE WHEN ambito = N'NACIONAL' THEN 1 ELSE 0 END)  AS filas_nacionales,
    MIN(anio_registro)              AS anio_min,
    MAX(anio_registro)              AS anio_max,
    SUM(CASE WHEN es_anio_parcial = 1 THEN 1 ELSE 0 END)   AS filas_anio_parcial
FROM {TABLE_NAME};
GO

SELECT
    anio_registro,
    COUNT(*)                     AS filas,
    COUNT(DISTINCT indicador)    AS indicadores,
    COUNT(DISTINCT cod_ubicacion) AS alcances
FROM {TABLE_NAME}
GROUP BY anio_registro
ORDER BY anio_registro;
GO
"""

    with sql_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(footer)

    size_mb = sql_path.stat().st_size / (1024 * 1024)
    logging.info("Script SQL generado: %s (%.2f MB)", sql_path, size_mb)


# ---------------------------------------------------------------------------
# Ejecucion en SQL Server
# ---------------------------------------------------------------------------
def run_sql(
    sqlcmd: Path,
    sql_path: Path,
    server: str,
    database: str,
) -> None:
    cmd = [
        str(sqlcmd),
        "-S",
        server,
        "-E",
        "-C",
        "-b",
        "-f",
        "65001",
        "-r",
        "1",
        "-i",
        str(sql_path),
    ]
    logging.info("Ejecutando SQL en %s (base %s)...", server, database)
    logging.debug("Comando: %s", " ".join(cmd))

    started = time.perf_counter()
    process = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=3600,
    )
    elapsed = time.perf_counter() - started

    if process.stdout:
        for line in process.stdout.splitlines():
            if line.strip():
                logging.info("sqlcmd | %s", line.rstrip())

    if process.returncode != 0:
        if process.stderr:
            for line in process.stderr.splitlines():
                if line.strip():
                    logging.error("sqlcmd | %s", line.rstrip())
        raise RuntimeError(
            f"sqlcmd termino con codigo {process.returncode}. Revisa el log."
        )

    logging.info("Carga completada en %.2f segundos.", elapsed)


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------
def main() -> int:
    args = parse_args()
    log_path, stamp = configure_logging()

    logging.info("=" * 78)
    logging.info("ETL %s", DATASET_NAME)
    logging.info("Entorno: %s", sys.executable)
    logging.info("Log: %s", log_path)
    logging.info("=" * 78)

    if not RAW_DIR.exists():
        logging.error("No existe la carpeta de datos crudos: %s", RAW_DIR)
        return 1

    generated_at = datetime.now()

    try:
        raw_file = find_raw_file()
        encoding_info = convert_to_utf8(raw_file, force=not args.reuse_utf8)
    except Exception:  # noqa: BLE001
        logging.exception("Fallo la conversion a UTF-8.")
        return 1

    raw_df, file_stats = load_csv(raw_file)
    datamart_df, metrics, rejected = clean_data(raw_df)

    metrics["dataset"] = DATASET_NAME
    metrics["archivo"] = file_stats
    metrics["codificacion"] = encoding_info
    metrics["hash_origen"] = hashlib.sha256(
        file_stats["sha256"].encode("utf-8")
    ).hexdigest()
    metrics["fecha_generacion"] = generated_at.strftime("%Y-%m-%d %H:%M:%S")
    metrics["script_sql"] = str(SQL_FILE.relative_to(PROJECT_ROOT)).replace("\\", "/")
    metrics["base_datos"] = args.database
    metrics["tabla"] = TABLE_NAME

    if rejected is not None and not rejected.empty:
        rejected_path = LOG_DIR / f"rechazados_victimizacion_{stamp}.csv"
        rejected.to_csv(rejected_path, index=False, encoding="utf-8-sig")
        metrics["archivo_rechazados"] = str(
            rejected_path.relative_to(PROJECT_ROOT)
        ).replace("\\", "/")
        logging.warning("Filas rechazadas guardadas en: %s", rejected_path)

    write_sql(
        datamart_df,
        metrics,
        file_stats,
        SQL_FILE,
        args.database,
        generated_at,
        args.batch_size,
    )

    metrics_path = LOG_DIR / f"victimizacion_metrics_{stamp}.json"
    with metrics_path.open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2, default=str)
    logging.info("Metricas guardadas en: %s", metrics_path)

    if args.generate_only:
        logging.info("Modo --generate-only: no se ejecuto el SQL.")
        return 0

    try:
        sqlcmd = find_sqlcmd(args.sqlcmd)
        run_sql(sqlcmd, SQL_FILE, args.server, args.database)
    except Exception as exc:  # noqa: BLE001 - se reporta y se corta el proceso
        logging.exception("Error durante la carga: %s", exc)
        return 1

    logging.info("=" * 78)
    logging.info("ETL finalizado correctamente.")
    logging.info(
        "Tabla %s: %s filas cargadas.",
        TABLE_NAME,
        f"{metrics['filas_cargadas']:,}",
    )
    logging.info("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
