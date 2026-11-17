#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ETL del DataMart de Produccion Policial (2023-2026).

Lee los 4 CSV de Dataset-Crudo/Produccion-Policial_2023-2026, valida y
homologa los datos y genera un script SQL autocontenido para SQL Server.
Opcionalmente ejecuta el script con sqlcmd.

Particularidad de este dataset: el mes viene como abreviatura en espanol
(ENE, FEB, MAR, ..., SET, OCT, NOV, DIC). El ETL lo convierte a numero (1-12)
para que el DataMart sea concordante con los de Denuncias y Personas
Desaparecidas y la union posterior en el DataWarehouse sea directa.

Uso:
    conda run -n ciencia-de-datos python Pipeline/etl_produccion_policial.py
    conda run -n ciencia-de-datos python Pipeline/etl_produccion_policial.py --generate-only
    conda run -n ciencia-de-datos python Pipeline/etl_produccion_policial.py --server localhost
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
RAW_DIR = PROJECT_ROOT / "Dataset-Crudo" / "Produccion-Policial_2023-2026"
PROCESSED_DIR = PROJECT_ROOT / "Dataset-Procesado" / "Produccion-Policial_2023-2026"
DATABASE_DIR = PROJECT_ROOT / "Database"
LOG_DIR = PROJECT_ROOT / "Pipeline" / "logs"
SQL_FILE = DATABASE_DIR / "03_produccion_policial_datamart.sql"

DATASET_NAME = "Produccion Policial 2023-2026"
DEFAULT_DATABASE = "DBProduccionPolicial"
TABLE_NAME = "dm.ProduccionPolicial"
BATCH_SIZE = 1_000

SOURCE_COLUMNS = ["AÑO", "MES", "VARIABLE", "DEPENDENCIAS", "DIR_REG_FRE", "VALOR"]

# Orden de columnas del DataMart (sin id_produccion ni fecha_carga)
FINAL_COLUMNS = [
    "anio_registro",
    "mes_registro",
    "fecha_hecho",
    "variable",
    "unidad_medida",
    "dependencia",
    "dir_reg_fre",
    "valor",
    "es_anio_parcial",
    "archivo_origen",
]

# Mes en espanol -> numero. Se aceptan la abreviatura oficial del dataset
# (SET = setiembre) y variantes habituales (SEP).
MESES: dict[str, int] = {
    "ENE": 1, "ENERO": 1,
    "FEB": 2, "FEBRERO": 2,
    "MAR": 3, "MARZO": 3,
    "ABR": 4, "ABRIL": 4,
    "MAY": 5, "MAYO": 5,
    "JUN": 6, "JUNIO": 6,
    "JUL": 7, "JULIO": 7,
    "AGO": 8, "AGOSTO": 8,
    "SET": 9, "SEP": 9, "SETIEMBRE": 9, "SEPTIEMBRE": 9,
    "OCT": 10, "OCTUBRE": 10,
    "NOV": 11, "NOVIEMBRE": 11,
    "DIC": 12, "DICIEMBRE": 12,
}

# Homologacion de DIR_REG_FRE: se pasa a mayusculas y se quita la tilde de
# "Region" para mantener el estilo canonico de los otros datamarts.
DIR_REG_FRE_CANONICO: dict[str, str] = {
    "REGIÓN": "REGION",
}

# Unidad de medida de cada variable. Es necesaria porque VALOR mezcla conteos,
# kilos, envoltorios y soles; sumarlos sin separar la unidad no tiene sentido.
UNIDAD_POR_VARIABLE: dict[str, str] = {
    "ARMAS BLANCAS": "UNIDADES",
    "ARMAS DE FUEGO": "UNIDADES",
    "BANDAS CRIMINALES DESARTICULADAS": "UNIDADES",
    "CC (ENVOLTORIOS)": "ENVOLTORIOS",
    "CC (KILOS)": "KILOS",
    "CONTRABANDO (VALORIZACION)": "SOLES (VALORIZACION)",
    "DETENIDOS DIVERSOS DELITOS (EXTRANJEROS)": "PERSONAS",
    "DETENIDOS DIVERSOS DELITOS (PERUANOS)": "PERSONAS",
    "DETENIDOS POR REQUISITORIADO": "PERSONAS",
    "DINERO INCAUTADO (SOLES)": "SOLES",
    "INTERVENCION EXTRAJEROS (LEY MIGRATORIA)": "PERSONAS",
    "MARIHUANA (ENVOLTORIO)": "ENVOLTORIO",
    "MARIHUANA (KILOS)": "KILOS",
    "OPERATIVOS": "OPERATIVOS",
    "ORGANIZACIONES CRIMINALES DESARTICULADAS": "UNIDADES",
    "PAPELETAS INFRACCION RNT": "PAPELETAS",
    "PBC (ENVOLTORIOS)": "ENVOLTORIOS",
    "PBC (KILOS)": "KILOS",
}

VALID_YEARS = (2023, 2026)

CANDIDATE_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ETL del DataMart de Produccion Policial 2023-2026."
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
    return parser.parse_args()


def configure_logging() -> tuple[Path, str]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"etl_produccion_policial_{stamp}.log"

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


def detect_encoding(data: bytes) -> str:
    for encoding in CANDIDATE_ENCODINGS:
        try:
            data.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo decodificar el archivo como UTF-8, CP1252 ni latin-1.")


def ensure_utf8(path: Path) -> tuple[Path, dict[str, Any]]:
    """Devuelve una ruta legible como UTF-8, convirtiendo solo si hace falta."""
    data = path.read_bytes()
    encoding = detect_encoding(data)

    info = {
        "archivo": path.name,
        "codificacion": encoding,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "convertido": False,
        "archivo_utf8": None,
    }

    if encoding in ("utf-8-sig", "utf-8"):
        logging.info("  %-32s ya esta en UTF-8 (%s)", path.name, encoding)
        return path, info

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSED_DIR / f"{path.stem}_utf8.csv"
    dest.write_bytes(data.decode(encoding).encode("utf-8-sig"))
    info["convertido"] = True
    info["archivo_utf8"] = str(dest.relative_to(PROJECT_ROOT)).replace("\\", "/")
    logging.info(
        "  %-32s convertido de %s a UTF-8 -> %s", path.name, encoding, dest.name
    )
    return dest, info


def map_month(value: str) -> int | None:
    text = value.strip().upper()
    if text == "":
        return None
    if text.isdigit():
        number = int(text)
        return number if 1 <= number <= 12 else None
    return MESES.get(text)


def parse_decimal(value: str) -> Decimal | None:
    """Convierte VALOR a Decimal conservando hasta 6 decimales."""
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


# ---------------------------------------------------------------------------
# Extraccion
# ---------------------------------------------------------------------------
def load_csvs() -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No se encontraron CSV en: {RAW_DIR}")

    logging.info("Leyendo %d archivos CSV desde %s", len(files), RAW_DIR)
    frames: list[pd.DataFrame] = []
    file_stats: list[dict[str, Any]] = []

    for path in files:
        source, info = ensure_utf8(path)
        df = pd.read_csv(
            source,
            dtype=str,
            keep_default_na=False,
            encoding="utf-8-sig",
        )
        df.columns = [col.strip() for col in df.columns]

        missing = [col for col in SOURCE_COLUMNS if col not in df.columns]
        extra = [col for col in df.columns if col not in SOURCE_COLUMNS]
        if missing or extra:
            raise ValueError(
                f"Esquema inesperado en {path.name}. "
                f"Faltan: {missing}. Sobran: {extra}."
            )

        df = df[SOURCE_COLUMNS].copy()
        df["archivo_origen"] = path.name
        frames.append(df)

        info["filas"] = int(len(df))
        file_stats.append(info)
        logging.info("  %-32s %9s filas", path.name, f"{len(df):,}")

    combined = pd.concat(frames, ignore_index=True)
    logging.info("Total de filas leidas: %s", f"{len(combined):,}")
    return combined, file_stats


# ---------------------------------------------------------------------------
# Limpieza y transformacion
# ---------------------------------------------------------------------------
def clean_data(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame | None]:
    raw_rows = len(df)
    df = df.copy()

    # 1. Normalizacion de texto
    for column in ["VARIABLE", "DEPENDENCIAS", "DIR_REG_FRE"]:
        df[column] = (
            df[column]
            .astype(str)
            .str.replace("\u00a0", " ", regex=False)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
            .str.upper()
        )
    df["DIR_REG_FRE"] = df["DIR_REG_FRE"].replace(DIR_REG_FRE_CANONICO)

    # 2. Conversion del mes (ENE, FEB, ... -> 1..12)
    mes_crudo = df["MES"].copy()
    df["MES_NUM"] = df["MES"].map(map_month)
    meses_desconocidos = sorted(
        df.loc[df["MES_NUM"].isna(), "MES"].unique().tolist()
    )
    if meses_desconocidos:
        logging.warning("Meses no reconocidos: %s", meses_desconocidos)

    logging.info(
        "Meses convertidos a numero: %s",
        ", ".join(
            f"{name}={num}"
            for name, num in sorted(MESES.items(), key=lambda kv: (kv[1], kv[0]))
            if name in set(mes_crudo.str.strip().str.upper())
        ),
    )

    # 3. Conversion numerica
    anio = pd.to_numeric(df["AÑO"], errors="coerce")
    valor = df["VALOR"].map(parse_decimal)

    # 4. Reglas de calidad
    invalid_anio = anio.isna() | (anio % 1 != 0) | ~anio.between(*VALID_YEARS)
    invalid_mes = df["MES_NUM"].isna() | ~df["MES_NUM"].between(1, 12)
    invalid_valor = valor.isna() | (valor < 0)

    empty_text = pd.Series(False, index=df.index)
    for column in ["VARIABLE", "DEPENDENCIAS", "DIR_REG_FRE"]:
        empty_text = empty_text | df[column].eq("")

    variables_desconocidas = sorted(
        set(df["VARIABLE"].unique()) - set(UNIDAD_POR_VARIABLE)
    )
    if variables_desconocidas:
        raise ValueError(
            "Hay variables sin unidad de medida definida: "
            f"{variables_desconocidas}. Agregalas a UNIDAD_POR_VARIABLE."
        )

    valid = ~(
        invalid_anio | invalid_mes | invalid_valor | empty_text
    )

    motivos = {
        "anio_invalido": int(invalid_anio.sum()),
        "mes_invalido": int(invalid_mes.sum()),
        "valor_invalido": int(invalid_valor.sum()),
        "texto_vacio": int(empty_text.sum()),
    }
    rejected_rows = int((~valid).sum())

    rejected: pd.DataFrame | None = None
    if rejected_rows:
        rejected = df.loc[~valid].copy()
        rejected["err_anio"] = invalid_anio[~valid].astype("int8").to_numpy()
        rejected["err_mes"] = invalid_mes[~valid].astype("int8").to_numpy()
        rejected["err_valor"] = invalid_valor[~valid].astype("int8").to_numpy()
        rejected["err_texto_vacio"] = (
            empty_text[~valid].astype("int8").to_numpy()
        )
        logging.warning("Filas rechazadas: %s", f"{rejected_rows:,}")

    # 5. Aplicar filtro y tipos definitivos
    df = df.loc[valid].copy()
    df["AÑO"] = anio[valid].astype("int16")
    df["MES_NUM"] = df["MES_NUM"].astype("int8")
    df["VALOR_DEC"] = valor[valid]

    # 6. Consolidar duplicados por grano sumando valor
    grain = ["AÑO", "MES_NUM", "DEPENDENCIAS", "VARIABLE"]
    consolidado = (
        df.groupby(grain, as_index=False, sort=False, dropna=False)
        .agg(
            DIR_REG_FRE=("DIR_REG_FRE", "first"),
            VALOR=("VALOR_DEC", "sum"),
            archivo_origen=(
                "archivo_origen",
                lambda values: ";".join(sorted(set(values))),
            ),
        )
    )
    filas_agrupadas = len(df) - len(consolidado)

    # 7. Renombrar y derivar columnas del DataMart
    consolidado = consolidado.rename(
        columns={
            "AÑO": "anio_registro",
            "MES_NUM": "mes_registro",
            "DEPENDENCIAS": "dependencia",
            "VARIABLE": "variable",
            "DIR_REG_FRE": "dir_reg_fre",
            "VALOR": "valor",
        }
    )
    consolidado["unidad_medida"] = consolidado["variable"].map(UNIDAD_POR_VARIABLE)
    consolidado["fecha_hecho"] = (
        consolidado["anio_registro"].astype(str)
        + "-"
        + consolidado["mes_registro"].astype(str).str.zfill(2)
        + "-01"
    )

    max_mes = consolidado.groupby("anio_registro")["mes_registro"].transform("max")
    consolidado["es_anio_parcial"] = (max_mes < 12).astype("int8")

    consolidado = (
        consolidado.sort_values(
            ["anio_registro", "mes_registro", "dependencia", "variable"]
        )
        .reset_index(drop=True)
        .loc[:, FINAL_COLUMNS]
    )

    # 8. Reconciliacion interna
    if consolidado["valor"].sum() != df["VALOR_DEC"].sum():
        raise ValueError("La suma de valor cambio al consolidar duplicados.")
    if len(consolidado) != len(df) - filas_agrupadas:
        raise ValueError("El conteo de filas no cuadra tras la consolidacion.")

    metrics: dict[str, Any] = {
        "filas_leidas": int(raw_rows),
        "filas_rechazadas": rejected_rows,
        "filas_agrupadas": int(filas_agrupadas),
        "filas_cargadas": int(len(consolidado)),
        "filas_valor_cero": int((consolidado["valor"] == 0).sum()),
        "total_valor": float(consolidado["valor"].sum()),
        "variables": int(consolidado["variable"].nunique()),
        "unidades_medida": int(consolidado["unidad_medida"].nunique()),
        "dependencias": int(consolidado["dependencia"].nunique()),
        "dir_reg_fre": int(consolidado["dir_reg_fre"].nunique()),
        "anio_min": int(consolidado["anio_registro"].min()),
        "anio_max": int(consolidado["anio_registro"].max()),
        "anios_parciales": sorted(
            int(value)
            for value in consolidado.loc[
                consolidado["es_anio_parcial"].eq(1), "anio_registro"
            ].unique()
        ),
        "meses_convertidos": {
            name: num
            for name, num in sorted(MESES.items(), key=lambda kv: (kv[1], kv[0]))
            if name in set(mes_crudo.str.strip().str.upper())
        },
        "motivos_rechazo": motivos,
    }

    logging.info("Filas cargadas: %s", f"{metrics['filas_cargadas']:,}")
    logging.info(
        "Dimensiones: %d variables, %d dependencias, %d dir_reg_fre",
        metrics["variables"],
        metrics["dependencias"],
        metrics["dir_reg_fre"],
    )
    logging.info(
        "Filas con valor 0 (conservadas): %s",
        f"{metrics['filas_valor_cero']:,}",
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
    file_stats: list[dict[str, Any]],
    sql_path: Path,
    database: str,
    generated_at: datetime,
    batch_size: int,
) -> None:
    sql_path.parent.mkdir(parents=True, exist_ok=True)

    archivos = ", ".join(item["archivo"] for item in file_stats)
    filas_esperadas = metrics["filas_cargadas"]
    total_valor = f"{df['valor'].sum():.6f}"
    detalle_json = json.dumps(metrics, ensure_ascii=False)
    fecha_iso = generated_at.strftime("%Y-%m-%dT%H:%M:%S")

    header = f"""/* ============================================================================
   DataMart: {DATASET_NAME}
   ----------------------------------------------------------------------------
   Generado por : Pipeline/etl_produccion_policial.py
   Fecha        : {generated_at.strftime('%Y-%m-%d %H:%M:%S')}
   Base de datos: {database}
   Tabla destino: {TABLE_NAME}
   Archivos     : {archivos}
   Filas        : {filas_esperadas:,}
   Suma VALOR   : {total_valor}
   Hash origen  : {metrics.get('hash_origen', '')}

   Limpieza aplicada:
     - Union de los 4 CSV (2023-2026).
     - Deteccion de codificacion; sin conversion si ya es UTF-8.
     - TRIM y colapso de espacios; textos en mayusculas.
     - MES convertido de abreviatura (ENE..DIC) a numero (1..12).
     - VALOR convertido a DECIMAL(18,6), conservando ceros.
     - unidad_medida derivada de la variable.
     - DIR_REG_FRE homologado (REGIÓN -> REGION).
     - Validacion de anio (2023-2026), mes, valor y textos requeridos.
     - Agrupacion de duplicados por grano sumando valor.
     - fecha_hecho derivada (primer dia del mes).
     - es_anio_parcial = 1 para anios sin diciembre (2026).

   Mapeo de columnas:
     AÑO          -> anio_registro
     MES          -> mes_registro (1-12)
     VARIABLE     -> variable
     DEPENDENCIAS -> dependencia
     DIR_REG_FRE  -> dir_reg_fre
     VALOR        -> valor
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
        archivos_origen   NVARCHAR(MAX) NOT NULL,
        hash_origen       CHAR(64) NOT NULL,
        filas_leidas      INT NOT NULL,
        filas_rechazadas  INT NOT NULL,
        filas_agrupadas   INT NOT NULL,
        filas_cargadas    INT NOT NULL,
        filas_valor_cero  INT NOT NULL,
        total_valor       DECIMAL(38,6) NOT NULL,
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
    id_produccion     INT IDENTITY(1,1) NOT NULL,
    anio_registro     SMALLINT NOT NULL,
    mes_registro      TINYINT NOT NULL,
    fecha_hecho       DATE NOT NULL,
    variable          NVARCHAR(100) NOT NULL,
    unidad_medida     NVARCHAR(30) NOT NULL,
    dependencia       NVARCHAR(60) NOT NULL,
    dir_reg_fre       NVARCHAR(30) NOT NULL,
    valor             DECIMAL(18,6) NOT NULL,
    es_anio_parcial   BIT NOT NULL,
    archivo_origen    NVARCHAR(80) NOT NULL,
    fecha_carga       DATETIME2(0) NOT NULL
        CONSTRAINT DF_ProduccionPolicial_fecha_carga DEFAULT SYSDATETIME(),
    CONSTRAINT PK_ProduccionPolicial PRIMARY KEY CLUSTERED (id_produccion),
    CONSTRAINT CK_ProduccionPolicial_anio
        CHECK (anio_registro BETWEEN 2023 AND 2100),
    CONSTRAINT CK_ProduccionPolicial_mes
        CHECK (mes_registro BETWEEN 1 AND 12),
    CONSTRAINT CK_ProduccionPolicial_valor
        CHECK (valor >= 0)
);
GO

PRINT N'Cargando {filas_esperadas:,} filas en {TABLE_NAME}...';
GO

"""

    insert_prefix = (
        f"INSERT INTO {TABLE_NAME}\n"
        "    (anio_registro, mes_registro, fecha_hecho, variable, unidad_medida, "
        "dependencia, dir_reg_fre, valor, es_anio_parcial, archivo_origen)\n"
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
                    variable,
                    unidad_medida,
                    dependencia,
                    dir_reg_fre,
                    valor,
                    es_anio_parcial,
                    archivo_origen,
                ) = row
                values.append(
                    "("
                    f"{int(anio_registro)}, "
                    f"{int(mes_registro)}, "
                    f"'{fecha_hecho}', "
                    f"{sql_n(variable)}, "
                    f"{sql_n(unidad_medida)}, "
                    f"{sql_n(dependencia)}, "
                    f"{sql_n(dir_reg_fre)}, "
                    f"{valor:.6f}, "
                    f"{int(es_anio_parcial)}, "
                    f"{sql_n(archivo_origen)}"
                    ")"
                )
            fh.write(insert_prefix)
            fh.write(",\n".join(values))
            fh.write(";\nGO\n\n")

    footer = f"""PRINT N'Creando indices...';
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_ProduccionPolicial_Grano
    ON {TABLE_NAME} (anio_registro, mes_registro, dependencia, variable)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

CREATE NONCLUSTERED INDEX IX_ProduccionPolicial_AnioMes
    ON {TABLE_NAME} (anio_registro, mes_registro)
    INCLUDE (valor)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

CREATE NONCLUSTERED INDEX IX_ProduccionPolicial_Dependencia
    ON {TABLE_NAME} (dependencia)
    INCLUDE (valor)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

CREATE NONCLUSTERED INDEX IX_ProduccionPolicial_Variable
    ON {TABLE_NAME} (variable)
    INCLUDE (valor)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

PRINT N'Registrando control de carga...';
GO

INSERT INTO etl.ControlCarga
    (dataset, archivos_origen, hash_origen, filas_leidas, filas_rechazadas,
     filas_agrupadas, filas_cargadas, filas_valor_cero, total_valor,
     fecha_inicio, fecha_fin, estado, detalle)
VALUES
    ({sql_n(DATASET_NAME)},
     {sql_n(archivos)},
     '{metrics.get('hash_origen', '')}',
     {metrics['filas_leidas']},
     {metrics['filas_rechazadas']},
     {metrics['filas_agrupadas']},
     {metrics['filas_cargadas']},
     {metrics['filas_valor_cero']},
     {total_valor},
     '{fecha_iso}',
     CONVERT(DATETIME2(0), SYSDATETIME()),
     N'EXITOSO',
     {sql_n(detalle_json)});
GO

PRINT N'Validando resultados...';
GO

DECLARE @filas INT = (SELECT COUNT(*) FROM {TABLE_NAME});
DECLARE @total DECIMAL(38,6) = (SELECT SUM(valor) FROM {TABLE_NAME});

IF @filas <> {filas_esperadas}
    THROW 51000, N'Validacion fallida: el conteo de filas no coincide con el ETL.', 1;

IF ABS(@total - {total_valor}) > 0.000001
    THROW 51001, N'Validacion fallida: la suma de valor no coincide con el ETL.', 1;

IF EXISTS (
    SELECT 1
    FROM {TABLE_NAME}
    GROUP BY anio_registro, mes_registro, dependencia, variable
    HAVING COUNT(*) > 1
)
    THROW 51002, N'Validacion fallida: existen duplicados en el grano del DataMart.', 1;

PRINT N'Validacion correcta.';
GO

SELECT
    COUNT(*)                        AS filas_cargadas,
    SUM(valor)                      AS total_valor,
    COUNT(DISTINCT variable)        AS variables,
    COUNT(DISTINCT unidad_medida)   AS unidades_medida,
    COUNT(DISTINCT dependencia)     AS dependencias,
    COUNT(DISTINCT dir_reg_fre)     AS dir_reg_fre,
    SUM(CASE WHEN valor = 0 THEN 1 ELSE 0 END)           AS filas_valor_cero,
    MIN(anio_registro)              AS anio_min,
    MAX(anio_registro)              AS anio_max,
    SUM(CASE WHEN es_anio_parcial = 1 THEN 1 ELSE 0 END) AS filas_anio_parcial
FROM {TABLE_NAME};
GO

SELECT
    anio_registro,
    COUNT(DISTINCT mes_registro) AS meses,
    COUNT(*)                     AS filas
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

    raw_df, file_stats = load_csvs()
    datamart_df, metrics, rejected = clean_data(raw_df)

    metrics["dataset"] = DATASET_NAME
    metrics["archivos"] = file_stats
    metrics["hash_origen"] = hashlib.sha256(
        "".join(item["sha256"] for item in file_stats).encode("utf-8")
    ).hexdigest()
    metrics["fecha_generacion"] = generated_at.strftime("%Y-%m-%d %H:%M:%S")
    metrics["script_sql"] = str(SQL_FILE.relative_to(PROJECT_ROOT)).replace("\\", "/")
    metrics["base_datos"] = args.database
    metrics["tabla"] = TABLE_NAME

    if rejected is not None and not rejected.empty:
        rejected_path = LOG_DIR / f"rechazados_produccion_policial_{stamp}.csv"
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

    metrics_path = LOG_DIR / f"produccion_policial_metrics_{stamp}.json"
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
