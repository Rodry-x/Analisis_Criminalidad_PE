#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ETL del DataMart de Personas Desaparecidas (2019-2025).

El CSV original esta codificado en CP1252 (Windows-1252), por lo que las
tildes y la letra Ñ se ven como '?' al abrirlo como UTF-8. Este ETL:

  1. Detecta la codificacion real del archivo crudo.
  2. Genera una copia fiel en UTF-8 con BOM (utf-8-sig) dentro de
     Dataset-Procesado/Personas-Desaparecidas_2019-2025/.
  3. Trabaja sobre la copia UTF-8 (pipeline 100% UTF-8 de aqui en adelante).
  4. Limpia, valida y consolida los datos.
  5. Genera un script SQL autocontenido y, opcionalmente, lo ejecuta con
     sqlcmd contra SQL Server.

Uso:
    conda run -n ciencia-de-datos python Pipeline/etl_personas_desaparecidas.py
    conda run -n ciencia-de-datos python Pipeline/etl_personas_desaparecidas.py --generate-only
    conda run -n ciencia-de-datos python Pipeline/etl_personas_desaparecidas.py --server localhost
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
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Configuracion del proyecto
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "Dataset-Crudo" / "Personas-Desaparecidas_2019-2025"
RAW_FILE = RAW_DIR / "Personas_Desaparecidas_2019_2025.csv"
PROCESSED_DIR = PROJECT_ROOT / "Dataset-Procesado" / "Personas-Desaparecidas_2019-2025"
UTF8_FILE = PROCESSED_DIR / "Personas_Desaparecidas_2019_2025_utf8.csv"
DATABASE_DIR = PROJECT_ROOT / "Database"
LOG_DIR = PROJECT_ROOT / "Pipeline" / "logs"
SQL_FILE = DATABASE_DIR / "02_personas_desaparecidas_datamart.sql"

DATASET_NAME = "Personas Desaparecidas 2019-2025"
DEFAULT_DATABASE = "DBPersonasDesaparecidas"
TABLE_NAME = "dm.PersonasDesaparecidas"
BATCH_SIZE = 1_000

SOURCE_COLUMNS = [
    "AÑO",
    "MES",
    "UBIGEO_HECHO",
    "DPTO_HECHO",
    "PROV_HECHO",
    "DIST_HECHO",
    "SEXO",
    "RANGO_EDAD",
    "NACIONALIDAD",
    "CANTIDAD",
]

# Orden de columnas del DataMart (sin id_desaparicion ni fecha_carga)
FINAL_COLUMNS = [
    "anio_registro",
    "mes_registro",
    "fecha_hecho",
    "departamento",
    "provincia",
    "distrito",
    "ubigeo",
    "sexo",
    "rango_edad",
    "nacionalidad",
    "cantidad",
    "es_anio_parcial",
    "archivo_origen",
]

# Variantes de nombres de departamento que se homologan al estilo canonico
# usado en el Dataset 1 (sin tildes). Provincias, distritos y nacionalidades
# conservan sus tildes y la Ñ.
DEPARTAMENTO_CANONICO: dict[str, str] = {
    "ÁNCASH": "ANCASH",
    "HUÁNUCO": "HUANUCO",
    "JUNÍN": "JUNIN",
    "SAN MARTÍN": "SAN MARTIN",
    "REGIÓN LIMA": "REGION LIMA",
    "CALLAO": "PROV. CONST. DEL CALLAO",
}

# Prefijo de ubigeo -> nombres de departamento validos (ya canonizados).
# El prefijo 15 agrupa Lima Metropolitana y Region Lima; el 07 es la Provincia
# Constitucional del Callao.
DPTO_POR_UBIGEO: dict[str, set[str]] = {
    "01": {"AMAZONAS"},
    "02": {"ANCASH"},
    "03": {"APURIMAC"},
    "04": {"AREQUIPA"},
    "05": {"AYACUCHO"},
    "06": {"CAJAMARCA"},
    "07": {"PROV. CONST. DEL CALLAO"},
    "08": {"CUSCO"},
    "09": {"HUANCAVELICA"},
    "10": {"HUANUCO"},
    "11": {"ICA"},
    "12": {"JUNIN"},
    "13": {"LA LIBERTAD"},
    "14": {"LAMBAYEQUE"},
    "15": {"LIMA METROPOLITANA", "REGION LIMA"},
    "16": {"LORETO"},
    "17": {"MADRE DE DIOS"},
    "18": {"MOQUEGUA"},
    "19": {"PASCO"},
    "20": {"PIURA"},
    "21": {"PUNO"},
    "22": {"SAN MARTIN"},
    "23": {"TACNA"},
    "24": {"TUMBES"},
    "25": {"UCAYALI"},
}

# Ubigeos con nombres historicos o inconsistentes que deben homologarse a la
# division politica actual.
UBIGEO_HOMOLOGACION: dict[str, tuple[str, str, str]] = {
    # El ubigeo 150121 corresponde a Pueblo Libre. Algunas filas lo registran
    # como "Magdalena Vieja" (antiguo nombre del distrito).
    "150121": ("LIMA METROPOLITANA", "LIMA", "PUEBLO LIBRE"),
    # Putumayo fue distrito de Maynas y luego paso a ser provincia de Putumayo.
    # En este dataset no hay filas, pero se deja por consistencia con el
    # Dataset 1.
    "160801": ("LORETO", "PUTUMAYO", "PUTUMAYO"),
}

VALID_YEARS = (2019, 2025)

# Codificaciones candidatas, en orden de preferencia.
CANDIDATE_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ETL del DataMart de Personas Desaparecidas 2019-2025."
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
    log_path = LOG_DIR / f"etl_personas_desaparecidas_{stamp}.log"

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
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return "NULL"
    return sql_n(value)


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


def convert_to_utf8(force: bool = True) -> dict[str, Any]:
    """Convierte el CSV crudo a UTF-8 con BOM conservando el contenido exacto."""
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"No existe el archivo crudo: {RAW_FILE}")

    raw_bytes = RAW_FILE.read_bytes()
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
        "archivo_crudo": str(RAW_FILE.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "codificacion_origen": source_encoding,
        "archivo_utf8": str(UTF8_FILE.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "codificacion_destino": "utf-8-sig",
        "convertido_en_esta_corrida": converted,
        "caracteres_no_ascii": latin_chars,
        "sha256_crudo": sha256_file(RAW_FILE),
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
def load_csv() -> tuple[pd.DataFrame, dict[str, Any]]:
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
            f"Esquema inesperado en {RAW_FILE.name}. "
            f"Faltan: {missing}. Sobran: {extra}."
        )

    df = df[SOURCE_COLUMNS].copy()
    df["archivo_origen"] = RAW_FILE.name

    file_stats = {
        "archivo": RAW_FILE.name,
        "filas": int(len(df)),
        "sha256": sha256_file(RAW_FILE),
    }
    logging.info("  %-42s %9s filas", RAW_FILE.name, f"{len(df):,}")
    return df, file_stats


# ---------------------------------------------------------------------------
# Limpieza y transformacion
# ---------------------------------------------------------------------------
def clean_data(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame | None]:
    raw_rows = len(df)
    df = df.copy()

    # 1. Normalizacion de texto (conserva tildes y Ñ).
    text_columns = [
        "DPTO_HECHO",
        "PROV_HECHO",
        "DIST_HECHO",
        "SEXO",
        "RANGO_EDAD",
        "NACIONALIDAD",
    ]
    for column in text_columns:
        df[column] = (
            df[column]
            .astype(str)
            .str.replace("\u00a0", " ", regex=False)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
    df["UBIGEO_HECHO"] = (
        df["UBIGEO_HECHO"].astype(str).str.replace(r"\s+", "", regex=True).str.zfill(6)
    )

    # 2. Conversion numerica
    anio = pd.to_numeric(df["AÑO"], errors="coerce")
    mes = pd.to_numeric(df["MES"], errors="coerce")
    cantidad = pd.to_numeric(df["CANTIDAD"], errors="coerce")

    # 3. Homologacion de nombres de departamento al estilo canonico.
    antes = df["DPTO_HECHO"].copy()
    df["DPTO_HECHO"] = df["DPTO_HECHO"].replace(DEPARTAMENTO_CANONICO)
    departamentos_homologados = int((antes != df["DPTO_HECHO"]).sum())
    if departamentos_homologados:
        detalle = (
            antes[antes != df["DPTO_HECHO"]]
            .value_counts()
            .to_dict()
        )
        logging.info(
            "Departamentos homologados: %s filas %s",
            f"{departamentos_homologados:,}",
            detalle,
        )

    # 4. Reglas de calidad
    invalid_anio = (
        anio.isna() | (anio % 1 != 0) | ~anio.between(*VALID_YEARS)
    )
    invalid_mes = mes.isna() | (mes % 1 != 0) | ~mes.between(1, 12)
    invalid_cantidad = cantidad.isna() | (cantidad % 1 != 0) | (cantidad < 0)
    invalid_ubigeo = ~df["UBIGEO_HECHO"].str.fullmatch(r"\d{6}")

    required_text = ["DPTO_HECHO", "PROV_HECHO", "DIST_HECHO", "NACIONALIDAD"]
    empty_text = pd.Series(False, index=df.index)
    for column in required_text:
        empty_text = empty_text | df[column].eq("")

    # Sexo y rango de edad pueden venir vacios: se cargan como NULL.
    invalid_sexo = ~df["SEXO"].isin(["", "F", "M"])
    invalid_rango = ~(
        df["RANGO_EDAD"].isin(
            ["", "0-5 AÑOS", "6-11 AÑOS", "12-17 AÑOS", "18-29 AÑOS",
             "30-59 AÑOS", "60 A MAS AÑOS"]
        )
    )

    allowed_dpto = df["UBIGEO_HECHO"].str[:2].map(DPTO_POR_UBIGEO)
    invalid_dpto = pd.Series(
        [
            depto not in (allowed if isinstance(allowed, set) else set())
            for depto, allowed in zip(df["DPTO_HECHO"], allowed_dpto)
        ],
        index=df.index,
    )

    valid = ~(
        invalid_anio
        | invalid_mes
        | invalid_cantidad
        | invalid_ubigeo
        | invalid_dpto
        | empty_text
        | invalid_sexo
        | invalid_rango
    )

    motivos = {
        "anio_invalido": int(invalid_anio.sum()),
        "mes_invalido": int(invalid_mes.sum()),
        "cantidad_invalida": int(invalid_cantidad.sum()),
        "ubigeo_invalido": int(invalid_ubigeo.sum()),
        "departamento_ubigeo_incompatible": int(invalid_dpto.sum()),
        "texto_requerido_vacio": int(empty_text.sum()),
        "sexo_invalido": int(invalid_sexo.sum()),
        "rango_edad_invalido": int(invalid_rango.sum()),
    }
    rejected_rows = int((~valid).sum())

    rejected: pd.DataFrame | None = None
    if rejected_rows:
        rejected = df.loc[~valid].copy()
        rejected["err_anio"] = invalid_anio[~valid].astype("int8").to_numpy()
        rejected["err_mes"] = invalid_mes[~valid].astype("int8").to_numpy()
        rejected["err_cantidad"] = (
            invalid_cantidad[~valid].astype("int8").to_numpy()
        )
        rejected["err_ubigeo"] = invalid_ubigeo[~valid].astype("int8").to_numpy()
        rejected["err_departamento"] = (
            invalid_dpto[~valid].astype("int8").to_numpy()
        )
        rejected["err_texto_requerido"] = (
            empty_text[~valid].astype("int8").to_numpy()
        )
        rejected["err_sexo"] = invalid_sexo[~valid].astype("int8").to_numpy()
        rejected["err_rango_edad"] = invalid_rango[~valid].astype("int8").to_numpy()
        logging.warning("Filas rechazadas: %s", f"{rejected_rows:,}")

    # 5. Aplicar filtro y tipos definitivos
    df = df.loc[valid].copy()
    df["AÑO"] = anio[valid].astype("int16")
    df["MES"] = mes[valid].astype("int8")
    df["CANTIDAD"] = cantidad[valid].astype("int64")

    # 6. Homologacion de ubigeos con nombres historicos / inconsistentes
    homologados = 0
    for ubigeo, (depto, provincia, distrito) in UBIGEO_HOMOLOGACION.items():
        mask = df["UBIGEO_HECHO"].eq(ubigeo)
        count = int(mask.sum())
        if count:
            logging.info(
                "Homologando ubigeo %s (%s filas) -> %s / %s / %s",
                ubigeo,
                f"{count:,}",
                depto,
                provincia,
                distrito,
            )
            df.loc[mask, "DPTO_HECHO"] = depto
            df.loc[mask, "PROV_HECHO"] = provincia
            df.loc[mask, "DIST_HECHO"] = distrito
            homologados += count

    # 7. Validar que cada ubigeo tenga un unico nombre
    nombres = df.groupby("UBIGEO_HECHO")[
        ["DPTO_HECHO", "PROV_HECHO", "DIST_HECHO"]
    ].nunique()
    inconsistentes = nombres[(nombres > 1).any(axis=1)]
    if not inconsistentes.empty:
        detalle = ", ".join(inconsistentes.index.tolist()[:10])
        raise ValueError(
            "Hay ubigeos con mas de un nombre asociado tras la homologacion: "
            f"{detalle}"
        )

    # 8. Consolidar duplicados por grano sumando cantidad.
    #    Sexo y rango de edad vacios se conservan como cadena vacia y luego se
    #    escriben como NULL; dropna=False evita que se pierdan grupos nulos.
    grain = [
        "AÑO",
        "MES",
        "UBIGEO_HECHO",
        "SEXO",
        "RANGO_EDAD",
        "NACIONALIDAD",
    ]
    consolidado = (
        df.groupby(grain, as_index=False, sort=False, dropna=False)
        .agg(
            DPTO_HECHO=("DPTO_HECHO", "first"),
            PROV_HECHO=("PROV_HECHO", "first"),
            DIST_HECHO=("DIST_HECHO", "first"),
            CANTIDAD=("CANTIDAD", "sum"),
            archivo_origen=(
                "archivo_origen",
                lambda values: ";".join(sorted(set(values))),
            ),
        )
    )
    filas_agrupadas = len(df) - len(consolidado)

    # 9. Renombrar y derivar columnas del DataMart
    consolidado = consolidado.rename(
        columns={
            "AÑO": "anio_registro",
            "MES": "mes_registro",
            "DPTO_HECHO": "departamento",
            "PROV_HECHO": "provincia",
            "DIST_HECHO": "distrito",
            "UBIGEO_HECHO": "ubigeo",
            "SEXO": "sexo",
            "RANGO_EDAD": "rango_edad",
            "NACIONALIDAD": "nacionalidad",
            "CANTIDAD": "cantidad",
        }
    )
    consolidado["fecha_hecho"] = (
        consolidado["anio_registro"].astype(str)
        + "-"
        + consolidado["mes_registro"].astype(str).str.zfill(2)
        + "-01"
    )

    # Un anio es parcial si su ultimo mes registrado es menor a diciembre.
    max_mes = consolidado.groupby("anio_registro")["mes_registro"].transform("max")
    consolidado["es_anio_parcial"] = (max_mes < 12).astype("int8")

    consolidado = (
        consolidado.sort_values(
            [
                "anio_registro",
                "mes_registro",
                "ubigeo",
                "sexo",
                "rango_edad",
                "nacionalidad",
            ],
            na_position="last",
        )
        .reset_index(drop=True)
        .loc[:, FINAL_COLUMNS]
    )

    # 10. Reconciliacion interna
    if consolidado["cantidad"].sum() != df["CANTIDAD"].sum():
        raise ValueError("La suma de cantidad cambio al consolidar duplicados.")
    if len(consolidado) != len(df) - filas_agrupadas:
        raise ValueError("El conteo de filas no cuadra tras la consolidacion.")

    metrics: dict[str, Any] = {
        "filas_leidas": int(raw_rows),
        "filas_rechazadas": rejected_rows,
        "filas_agrupadas": int(filas_agrupadas),
        "filas_cargadas": int(len(consolidado)),
        "total_casos": int(consolidado["cantidad"].sum()),
        "departamentos": int(consolidado["departamento"].nunique()),
        "provincias": int(consolidado["provincia"].nunique()),
        "distritos": int(consolidado["distrito"].nunique()),
        "ubigeos": int(consolidado["ubigeo"].nunique()),
        "nacionalidades": int(consolidado["nacionalidad"].nunique()),
        "sexos": int(consolidado["sexo"].replace("", pd.NA).nunique()),
        "rangos_edad": int(consolidado["rango_edad"].replace("", pd.NA).nunique()),
        "filas_sexo_null": int(consolidado["sexo"].eq("").sum()),
        "filas_rango_edad_null": int(consolidado["rango_edad"].eq("").sum()),
        "anio_min": int(consolidado["anio_registro"].min()),
        "anio_max": int(consolidado["anio_registro"].max()),
        "anios_parciales": sorted(
            int(value)
            for value in consolidado.loc[
                consolidado["es_anio_parcial"].eq(1), "anio_registro"
            ].unique()
        ),
        "ubigeos_homologados": int(homologados),
        "departamentos_canonizados": departamentos_homologados,
        "motivos_rechazo": motivos,
    }

    logging.info("Filas cargadas: %s", f"{metrics['filas_cargadas']:,}")
    logging.info("Total de casos: %s", f"{metrics['total_casos']:,}")
    logging.info(
        "Dimensiones: %d deptos, %d provincias, %d distritos, %d ubigeos, "
        "%d nacionalidades",
        metrics["departamentos"],
        metrics["provincias"],
        metrics["distritos"],
        metrics["ubigeos"],
        metrics["nacionalidades"],
    )
    logging.info(
        "Valores vacios cargados como NULL: sexo=%s, rango_edad=%s",
        f"{metrics['filas_sexo_null']:,}",
        f"{metrics['filas_rango_edad_null']:,}",
    )
    if metrics["anios_parciales"]:
        logging.warning("Anios parciales detectados: %s", metrics["anios_parciales"])

    return consolidado, metrics, rejected


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
    total_esperado = metrics["total_casos"]
    detalle_json = json.dumps(metrics, ensure_ascii=False)
    fecha_iso = generated_at.strftime("%Y-%m-%dT%H:%M:%S")

    header = f"""/* ============================================================================
   DataMart: {DATASET_NAME}
   ----------------------------------------------------------------------------
   Generado por : Pipeline/etl_personas_desaparecidas.py
   Fecha        : {generated_at.strftime('%Y-%m-%d %H:%M:%S')}
   Base de datos: {database}
   Tabla destino: {TABLE_NAME}
   Archivo      : {archivos}
   Filas        : {filas_esperadas:,}
   Casos        : {total_esperado:,}
   Codificacion origen : {metrics.get('codificacion', {}).get('codificacion_origen', '')}
   Copia UTF-8         : {metrics.get('codificacion', {}).get('archivo_utf8', '')}
   Hash origen  : {metrics.get('hash_origen', '')}

   Limpieza aplicada:
     - Conversion CP1252 -> UTF-8 (utf-8-sig) conservando tildes y N.
     - TRIM y colapso de espacios en textos.
     - UBIGEO_HECHO normalizado a 6 digitos (cero inicial).
     - Departamentos homologados al estilo canonico sin tildes.
     - Ubigeo 150121 homologado a LIMA METROPOLITANA / LIMA / PUEBLO LIBRE.
     - Validacion de anio (2019-2025), mes, cantidad, ubigeo y departamento.
     - SEXO y RANGO_EDAD vacios se cargan como NULL.
     - Agrupacion de duplicados por grano sumando cantidad.
     - fecha_hecho derivada (primer dia del mes).
     - es_anio_parcial = 1 para anios sin diciembre.

   Mapeo de columnas:
     AÑO          -> anio_registro
     MES          -> mes_registro
     UBIGEO_HECHO -> ubigeo
     DPTO_HECHO   -> departamento
     PROV_HECHO   -> provincia
     DIST_HECHO   -> distrito
     SEXO         -> sexo
     RANGO_EDAD   -> rango_edad
     NACIONALIDAD -> nacionalidad
     CANTIDAD     -> cantidad
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
        id_carga          INT IDENTITY(1,1) NOT NULL,
        dataset           NVARCHAR(150) NOT NULL,
        archivo_origen    NVARCHAR(400) NOT NULL,
        hash_origen       CHAR(64) NOT NULL,
        filas_leidas      INT NOT NULL,
        filas_rechazadas  INT NOT NULL,
        filas_agrupadas   INT NOT NULL,
        filas_cargadas    INT NOT NULL,
        total_casos       BIGINT NOT NULL,
        fecha_inicio      DATETIME2(0) NOT NULL,
        fecha_fin         DATETIME2(0) NOT NULL,
        estado            NVARCHAR(20) NOT NULL,
        detalle           NVARCHAR(MAX) NULL,
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
    id_desaparicion   INT IDENTITY(1,1) NOT NULL,
    anio_registro     SMALLINT NOT NULL,
    mes_registro      TINYINT NOT NULL,
    fecha_hecho       DATE NOT NULL,
    departamento      NVARCHAR(60) NOT NULL,
    provincia         NVARCHAR(100) NOT NULL,
    distrito          NVARCHAR(120) NOT NULL,
    ubigeo            CHAR(6) NOT NULL,
    sexo              NCHAR(1) NULL,
    rango_edad        NVARCHAR(30) NULL,
    nacionalidad      NVARCHAR(60) NOT NULL,
    cantidad          INT NOT NULL,
    es_anio_parcial   BIT NOT NULL,
    archivo_origen    NVARCHAR(400) NOT NULL,
    fecha_carga       DATETIME2(0) NOT NULL
        CONSTRAINT DF_PersonasDesaparecidas_fecha_carga DEFAULT SYSDATETIME(),
    CONSTRAINT PK_PersonasDesaparecidas PRIMARY KEY CLUSTERED (id_desaparicion),
    CONSTRAINT CK_PersonasDesaparecidas_anio
        CHECK (anio_registro BETWEEN 2019 AND 2100),
    CONSTRAINT CK_PersonasDesaparecidas_mes
        CHECK (mes_registro BETWEEN 1 AND 12),
    CONSTRAINT CK_PersonasDesaparecidas_cantidad
        CHECK (cantidad >= 0),
    CONSTRAINT CK_PersonasDesaparecidas_ubigeo
        CHECK (ubigeo LIKE '[0-9][0-9][0-9][0-9][0-9][0-9]'),
    CONSTRAINT CK_PersonasDesaparecidas_sexo
        CHECK (sexo IS NULL OR sexo IN (N'F', N'M'))
);
GO

PRINT N'Cargando {filas_esperadas:,} filas en {TABLE_NAME}...';
GO

"""

    insert_prefix = (
        f"INSERT INTO {TABLE_NAME}\n"
        "    (anio_registro, mes_registro, fecha_hecho, departamento, provincia, "
        "distrito, ubigeo, sexo, rango_edad, nacionalidad, cantidad, "
        "es_anio_parcial, archivo_origen)\n"
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
                    mes_registro,
                    fecha_hecho,
                    departamento,
                    provincia,
                    distrito,
                    ubigeo,
                    sexo,
                    rango_edad,
                    nacionalidad,
                    cantidad,
                    es_anio_parcial,
                    archivo_origen,
                ) = row
                values.append(
                    "("
                    f"{int(anio_registro)}, "
                    f"{int(mes_registro)}, "
                    f"'{fecha_hecho}', "
                    f"{sql_n(departamento)}, "
                    f"{sql_n(provincia)}, "
                    f"{sql_n(distrito)}, "
                    f"'{ubigeo}', "
                    f"{sql_n_null(sexo)}, "
                    f"{sql_n_null(rango_edad)}, "
                    f"{sql_n(nacionalidad)}, "
                    f"{int(cantidad)}, "
                    f"{int(es_anio_parcial)}, "
                    f"{sql_n(archivo_origen)}"
                    ")"
                )
            fh.write(insert_prefix)
            fh.write(",\n".join(values))
            fh.write(";\nGO\n\n")

    footer = f"""PRINT N'Creando indices...';
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_PersonasDesaparecidas_Grano
    ON {TABLE_NAME} (anio_registro, mes_registro, ubigeo, sexo, rango_edad,
                     nacionalidad)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

CREATE NONCLUSTERED INDEX IX_PersonasDesaparecidas_AnioMes
    ON {TABLE_NAME} (anio_registro, mes_registro)
    INCLUDE (cantidad)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

CREATE NONCLUSTERED INDEX IX_PersonasDesaparecidas_Ubigeo
    ON {TABLE_NAME} (ubigeo)
    INCLUDE (cantidad)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

CREATE NONCLUSTERED INDEX IX_PersonasDesaparecidas_Nacionalidad
    ON {TABLE_NAME} (nacionalidad)
    INCLUDE (cantidad)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

PRINT N'Registrando control de carga...';
GO

INSERT INTO etl.ControlCarga
    (dataset, archivo_origen, hash_origen, filas_leidas, filas_rechazadas,
     filas_agrupadas, filas_cargadas, total_casos, fecha_inicio, fecha_fin,
     estado, detalle)
VALUES
    ({sql_n(DATASET_NAME)},
     {sql_n(archivos)},
     '{metrics.get('hash_origen', '')}',
     {metrics['filas_leidas']},
     {metrics['filas_rechazadas']},
     {metrics['filas_agrupadas']},
     {metrics['filas_cargadas']},
     {metrics['total_casos']},
     '{fecha_iso}',
     CONVERT(DATETIME2(0), SYSDATETIME()),
     N'EXITOSO',
     {sql_n(detalle_json)});
GO

PRINT N'Validando resultados...';
GO

DECLARE @filas INT = (SELECT COUNT(*) FROM {TABLE_NAME});
DECLARE @total BIGINT = (SELECT SUM(cantidad) FROM {TABLE_NAME});

IF @filas <> {filas_esperadas}
    THROW 51000, N'Validacion fallida: el conteo de filas no coincide con el ETL.', 1;

IF @total <> {total_esperado}
    THROW 51001, N'Validacion fallida: la suma de cantidad no coincide con el ETL.', 1;

IF EXISTS (
    SELECT 1
    FROM {TABLE_NAME}
    GROUP BY anio_registro, mes_registro, ubigeo, sexo, rango_edad,
             nacionalidad
    HAVING COUNT(*) > 1
)
    THROW 51002, N'Validacion fallida: existen duplicados en el grano del DataMart.', 1;

PRINT N'Validacion correcta.';
GO

SELECT
    COUNT(*)                        AS filas_cargadas,
    SUM(cantidad)                   AS total_casos,
    COUNT(DISTINCT departamento)    AS departamentos,
    COUNT(DISTINCT provincia)       AS provincias,
    COUNT(DISTINCT distrito)        AS distritos,
    COUNT(DISTINCT ubigeo)          AS ubigeos,
    COUNT(DISTINCT nacionalidad)    AS nacionalidades,
    SUM(CASE WHEN sexo IS NULL THEN 1 ELSE 0 END)       AS filas_sexo_null,
    SUM(CASE WHEN rango_edad IS NULL THEN 1 ELSE 0 END) AS filas_rango_edad_null,
    MIN(anio_registro)              AS anio_min,
    MAX(anio_registro)              AS anio_max,
    SUM(CASE WHEN es_anio_parcial = 1 THEN 1 ELSE 0 END) AS filas_anio_parcial
FROM {TABLE_NAME};
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
        encoding_info = convert_to_utf8(force=not args.reuse_utf8)
    except Exception:  # noqa: BLE001
        logging.exception("Fallo la conversion a UTF-8.")
        return 1

    raw_df, file_stats = load_csv()
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
        rejected_path = LOG_DIR / f"rechazados_personas_desaparecidas_{stamp}.csv"
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

    metrics_path = LOG_DIR / f"personas_desaparecidas_metrics_{stamp}.json"
    with metrics_path.open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2)
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
        "Tabla %s: %s filas, %s casos.",
        TABLE_NAME,
        f"{metrics['filas_cargadas']:,}",
        f"{metrics['total_casos']:,}",
    )
    logging.info("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
