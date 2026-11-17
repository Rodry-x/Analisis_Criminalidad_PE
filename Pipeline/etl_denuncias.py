#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ETL del DataMart de Denuncias Policiales (2018-2026).

Lee los 9 CSV de Dataset-Crudo/Denuncias-Policiales_2018-2026, los limpia,
los unifica y genera un script SQL autocontenido para SQL Server.
Opcionalmente ejecuta el script con sqlcmd.

Uso:
    conda run -n ciencia-de-datos python Pipeline/etl_denuncias.py
    conda run -n ciencia-de-datos python Pipeline/etl_denuncias.py --generate-only
    conda run -n ciencia-de-datos python Pipeline/etl_denuncias.py --server localhost --database DBDenunciasPoliciales
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
# Configuración del proyecto
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "Dataset-Crudo" / "Denuncias-Policiales_2018-2026"
DATABASE_DIR = PROJECT_ROOT / "Database"
LOG_DIR = PROJECT_ROOT / "Pipeline" / "logs"
SQL_FILE = DATABASE_DIR / "01_denuncias_policiales_datamart.sql"

DATASET_NAME = "Denuncias Policiales 2018-2026"
DEFAULT_DATABASE = "DBDenunciasPoliciales"
TABLE_NAME = "dm.DenunciasPoliciales"
BATCH_SIZE = 1_000

SOURCE_COLUMNS = [
    "ANIO_REGISTRO",
    "MES_REGISTRO",
    "DPTO_HECHO_NEW",
    "PROV_HECHO",
    "DIST_HECHO",
    "UBIGEO_HECHO",
    "P_MODALIDADES",
    "cantidad",
]

# Orden de columnas del DataMart (sin id_denuncia ni fecha_carga, que son automáticas)
FINAL_COLUMNS = [
    "anio_registro",
    "mes_registro",
    "fecha_hecho",
    "departamento",
    "provincia",
    "distrito",
    "ubigeo",
    "modalidad",
    "cantidad",
    "es_anio_parcial",
    "archivo_origen",
]

# Prefijo de ubigeo -> nombres de departamento válidos.
# El prefijo 15 agrupa Lima Metropolitana y Región Lima; el 07 es la Provincia
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

# Ubigeos con nombres históricos que deben homologarse a la división actual.
UBIGEO_HOMOLOGACION: dict[str, tuple[str, str, str]] = {
    # Putumayo fue distrito de Maynas y luego pasó a ser provincia de Putumayo.
    "160801": ("LORETO", "PUTUMAYO", "PUTUMAYO"),
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ETL del DataMart de Denuncias Policiales 2018-2026."
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
        help="Ruta explícita a sqlcmd.exe. Si se omite, se busca en el PATH.",
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
    log_path = LOG_DIR / f"etl_denuncias_{stamp}.log"

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
    candidates = sorted(
        base.glob(r"*\Tools\Binn\SQLCMD.EXE"),
        reverse=True,
    )
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        "No se encontró sqlcmd.exe. Instala SQL Server Command Line Utilities "
        "o pasa la ruta con --sqlcmd."
    )


def sql_n(value: Any) -> str:
    """Devuelve un literal Unicode de SQL Server escapando comillas simples."""
    return "N'" + str(value).replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# Extracción
# ---------------------------------------------------------------------------
def load_csvs() -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No se encontraron CSV en: {RAW_DIR}")

    logging.info("Leyendo %d archivos CSV desde %s", len(files), RAW_DIR)
    frames: list[pd.DataFrame] = []
    file_stats: list[dict[str, Any]] = []

    for path in files:
        df = pd.read_csv(
            path,
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

        file_stats.append(
            {
                "archivo": path.name,
                "filas": int(len(df)),
                "sha256": sha256_file(path),
            }
        )
        logging.info("  %-36s %9s filas", path.name, f"{len(df):,}")

    combined = pd.concat(frames, ignore_index=True)
    logging.info("Total de filas leídas: %s", f"{len(combined):,}")
    return combined, file_stats


# ---------------------------------------------------------------------------
# Limpieza y transformación
# ---------------------------------------------------------------------------
def clean_data(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame | None]:
    raw_rows = len(df)
    df = df.copy()

    # 1. Normalización de texto
    text_columns = ["DPTO_HECHO_NEW", "PROV_HECHO", "DIST_HECHO", "P_MODALIDADES"]
    for column in text_columns:
        df[column] = (
            df[column]
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
    df["UBIGEO_HECHO"] = (
        df["UBIGEO_HECHO"]
        .astype(str)
        .str.replace(r"\s+", "", regex=True)
        .str.zfill(6)
    )

    # 2. Conversión numérica
    anio = pd.to_numeric(df["ANIO_REGISTRO"], errors="coerce")
    mes = pd.to_numeric(df["MES_REGISTRO"], errors="coerce")
    cantidad = pd.to_numeric(df["cantidad"], errors="coerce")

    # 3. Reglas de calidad
    invalid_anio = anio.isna() | (anio % 1 != 0) | ~anio.between(2018, 2026)
    invalid_mes = mes.isna() | (mes % 1 != 0) | ~mes.between(1, 12)
    invalid_cantidad = cantidad.isna() | (cantidad % 1 != 0) | (cantidad < 0)
    invalid_ubigeo = ~df["UBIGEO_HECHO"].str.fullmatch(r"\d{6}")

    empty_text = pd.Series(False, index=df.index)
    for column in text_columns:
        empty_text = empty_text | df[column].eq("")

    allowed_dpto = df["UBIGEO_HECHO"].str[:2].map(DPTO_POR_UBIGEO)
    invalid_dpto = pd.Series(
        [
            depto not in (allowed if isinstance(allowed, set) else set())
            for depto, allowed in zip(df["DPTO_HECHO_NEW"], allowed_dpto)
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
    )

    motivos = {
        "anio_invalido": int(invalid_anio.sum()),
        "mes_invalido": int(invalid_mes.sum()),
        "cantidad_invalida": int(invalid_cantidad.sum()),
        "ubigeo_invalido": int(invalid_ubigeo.sum()),
        "departamento_ubigeo_incompatible": int(invalid_dpto.sum()),
        "texto_vacio": int(empty_text.sum()),
    }
    rejected_rows = int((~valid).sum())

    rejected: pd.DataFrame | None = None
    if rejected_rows:
        rejected = df.loc[~valid].copy()
        rejected["err_anio"] = invalid_anio[~valid].astype("int8").to_numpy()
        rejected["err_mes"] = invalid_mes[~valid].astype("int8").to_numpy()
        rejected["err_cantidad"] = invalid_cantidad[~valid].astype("int8").to_numpy()
        rejected["err_ubigeo"] = invalid_ubigeo[~valid].astype("int8").to_numpy()
        rejected["err_departamento"] = invalid_dpto[~valid].astype("int8").to_numpy()
        rejected["err_texto_vacio"] = empty_text[~valid].astype("int8").to_numpy()
        logging.warning("Filas rechazadas: %s", f"{rejected_rows:,}")

    # 4. Aplicar filtro y tipos definitivos
    df = df.loc[valid].copy()
    df["ANIO_REGISTRO"] = anio[valid].astype("int16")
    df["MES_REGISTRO"] = mes[valid].astype("int8")
    df["cantidad"] = cantidad[valid].astype("int64")

    # 5. Homologación de ubigeos con nombres históricos
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
            df.loc[mask, "DPTO_HECHO_NEW"] = depto
            df.loc[mask, "PROV_HECHO"] = provincia
            df.loc[mask, "DIST_HECHO"] = distrito
            homologados += count

    # 6. Validar que cada ubigeo tenga un único nombre
    nombres = df.groupby("UBIGEO_HECHO")[
        ["DPTO_HECHO_NEW", "PROV_HECHO", "DIST_HECHO"]
    ].nunique()
    inconsistentes = nombres[(nombres > 1).any(axis=1)]
    if not inconsistentes.empty:
        detalle = ", ".join(inconsistentes.index.tolist()[:10])
        raise ValueError(
            "Hay ubigeos con más de un nombre asociado tras la homologación: "
            f"{detalle}"
        )

    # 7. Agrupar duplicados por grano y sumar cantidad
    grain = ["ANIO_REGISTRO", "MES_REGISTRO", "UBIGEO_HECHO", "P_MODALIDADES"]
    consolidado = (
        df.groupby(grain, as_index=False, sort=False)
        .agg(
            DPTO_HECHO_NEW=("DPTO_HECHO_NEW", "first"),
            PROV_HECHO=("PROV_HECHO", "first"),
            DIST_HECHO=("DIST_HECHO", "first"),
            cantidad=("cantidad", "sum"),
            archivo_origen=(
                "archivo_origen",
                lambda values: ";".join(sorted(set(values))),
            ),
        )
    )
    filas_agrupadas = len(df) - len(consolidado)

    # 8. Renombrar a nombres del DataMart y derivar columnas
    consolidado = consolidado.rename(
        columns={
            "ANIO_REGISTRO": "anio_registro",
            "MES_REGISTRO": "mes_registro",
            "DPTO_HECHO_NEW": "departamento",
            "PROV_HECHO": "provincia",
            "DIST_HECHO": "distrito",
            "UBIGEO_HECHO": "ubigeo",
            "P_MODALIDADES": "modalidad",
        }
    )
    consolidado["fecha_hecho"] = (
        consolidado["anio_registro"].astype(str)
        + "-"
        + consolidado["mes_registro"].astype(str).str.zfill(2)
        + "-01"
    )

    # Un año es parcial si su último mes registrado es menor a diciembre.
    max_mes = consolidado.groupby("anio_registro")["mes_registro"].transform("max")
    consolidado["es_anio_parcial"] = (max_mes < 12).astype("int8")

    consolidado = (
        consolidado.sort_values(
            ["anio_registro", "mes_registro", "ubigeo", "modalidad"]
        )
        .reset_index(drop=True)
        .loc[:, FINAL_COLUMNS]
    )

    # 9. Reconciliación interna
    if consolidado["cantidad"].sum() != df["cantidad"].sum():
        raise ValueError(
            "La suma de cantidad cambió durante la consolidación de duplicados."
        )
    if len(consolidado) != len(df) - filas_agrupadas:
        raise ValueError("El conteo de filas no cuadra tras la consolidación.")

    metrics: dict[str, Any] = {
        "filas_leidas": int(raw_rows),
        "filas_rechazadas": rejected_rows,
        "filas_agrupadas": int(filas_agrupadas),
        "filas_cargadas": int(len(consolidado)),
        "total_denuncias": int(consolidado["cantidad"].sum()),
        "departamentos": int(consolidado["departamento"].nunique()),
        "provincias": int(consolidado["provincia"].nunique()),
        "distritos": int(consolidado["distrito"].nunique()),
        "ubigeos": int(consolidado["ubigeo"].nunique()),
        "modalidades": int(consolidado["modalidad"].nunique()),
        "anio_min": int(consolidado["anio_registro"].min()),
        "anio_max": int(consolidado["anio_registro"].max()),
        "anios_parciales": sorted(
            int(value)
            for value in consolidado.loc[
                consolidado["es_anio_parcial"].eq(1), "anio_registro"
            ].unique()
        ),
        "ubigeos_homologados": int(homologados),
        "motivos_rechazo": motivos,
    }

    logging.info("Filas cargadas: %s", f"{metrics['filas_cargadas']:,}")
    logging.info("Total de denuncias: %s", f"{metrics['total_denuncias']:,}")
    logging.info(
        "Dimensiones: %d deptos, %d provincias, %d distritos, %d modalidades",
        metrics["departamentos"],
        metrics["provincias"],
        metrics["distritos"],
        metrics["modalidades"],
    )
    if metrics["anios_parciales"]:
        logging.warning(
            "Años parciales detectados: %s", metrics["anios_parciales"]
        )

    return consolidado, metrics, rejected


# ---------------------------------------------------------------------------
# Generación del script SQL
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
    total_esperado = metrics["total_denuncias"]
    detalle_json = json.dumps(metrics, ensure_ascii=False)
    fecha_iso = generated_at.strftime("%Y-%m-%dT%H:%M:%S")

    header = f"""/* ============================================================================
   DataMart: {DATASET_NAME}
   ----------------------------------------------------------------------------
   Generado por : Pipeline/etl_denuncias.py
   Fecha        : {generated_at.strftime('%Y-%m-%d %H:%M:%S')}
   Base de datos: {database}
   Tabla destino: {TABLE_NAME}
   Archivos     : {archivos}
   Filas        : {filas_esperadas:,}
   Denuncias    : {total_esperado:,}
   Hash origen  : {metrics.get('hash_origen', '')}

   Limpieza aplicada:
     - Union de los 9 CSV (2018-2026).
     - TRIM y colapso de espacios en textos.
     - UBIGEO_HECHO normalizado a 6 digitos (cero inicial).
     - Ubigeo 160801 homologado a LORETO / PUTUMAYO / PUTUMAYO.
     - Validacion de anio, mes, cantidad, ubigeo y departamento.
     - Agrupacion de duplicados por grano sumando cantidad.
     - fecha_hecho derivada (primer dia del mes).
     - es_anio_parcial = 1 para anos sin diciembre (2026).

   Mapeo de columnas:
     ANIO_REGISTRO  -> anio_registro
     MES_REGISTRO   -> mes_registro
     DPTO_HECHO_NEW -> departamento
     PROV_HECHO     -> provincia
     DIST_HECHO     -> distrito
     UBIGEO_HECHO   -> ubigeo
     P_MODALIDADES  -> modalidad
     cantidad       -> cantidad
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
        total_denuncias   BIGINT NOT NULL,
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
    id_denuncia       INT IDENTITY(1,1) NOT NULL,
    anio_registro     SMALLINT NOT NULL,
    mes_registro      TINYINT NOT NULL,
    fecha_hecho       DATE NOT NULL,
    departamento      NVARCHAR(60) NOT NULL,
    provincia         NVARCHAR(100) NOT NULL,
    distrito          NVARCHAR(120) NOT NULL,
    ubigeo            CHAR(6) NOT NULL,
    modalidad         NVARCHAR(100) NOT NULL,
    cantidad          INT NOT NULL,
    es_anio_parcial   BIT NOT NULL,
    archivo_origen    NVARCHAR(400) NOT NULL,
    fecha_carga       DATETIME2(0) NOT NULL
        CONSTRAINT DF_DenunciasPoliciales_fecha_carga DEFAULT SYSDATETIME(),
    CONSTRAINT PK_DenunciasPoliciales PRIMARY KEY CLUSTERED (id_denuncia),
    CONSTRAINT CK_DenunciasPoliciales_anio
        CHECK (anio_registro BETWEEN 2018 AND 2100),
    CONSTRAINT CK_DenunciasPoliciales_mes
        CHECK (mes_registro BETWEEN 1 AND 12),
    CONSTRAINT CK_DenunciasPoliciales_cantidad
        CHECK (cantidad >= 0),
    CONSTRAINT CK_DenunciasPoliciales_ubigeo
        CHECK (ubigeo LIKE '[0-9][0-9][0-9][0-9][0-9][0-9]')
);
GO

PRINT N'Cargando {filas_esperadas:,} filas en {TABLE_NAME}...';
GO

"""

    insert_prefix = (
        f"INSERT INTO {TABLE_NAME}\n"
        "    (anio_registro, mes_registro, fecha_hecho, departamento, provincia, "
        "distrito, ubigeo, modalidad, cantidad, es_anio_parcial, archivo_origen)\n"
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
                    modalidad,
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
                    f"{sql_n(modalidad)}, "
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

CREATE UNIQUE NONCLUSTERED INDEX UX_DenunciasPoliciales_Grano
    ON {TABLE_NAME} (anio_registro, mes_registro, ubigeo, modalidad)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

CREATE NONCLUSTERED INDEX IX_DenunciasPoliciales_AnioMes
    ON {TABLE_NAME} (anio_registro, mes_registro)
    INCLUDE (cantidad)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

CREATE NONCLUSTERED INDEX IX_DenunciasPoliciales_Ubigeo
    ON {TABLE_NAME} (ubigeo)
    INCLUDE (cantidad)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

CREATE NONCLUSTERED INDEX IX_DenunciasPoliciales_Modalidad
    ON {TABLE_NAME} (modalidad)
    INCLUDE (cantidad)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

PRINT N'Registrando control de carga...';
GO

INSERT INTO etl.ControlCarga
    (dataset, archivos_origen, hash_origen, filas_leidas, filas_rechazadas,
     filas_agrupadas, filas_cargadas, total_denuncias, fecha_inicio, fecha_fin,
     estado, detalle)
VALUES
    ({sql_n(DATASET_NAME)},
     {sql_n(archivos)},
     '{metrics.get('hash_origen', '')}',
     {metrics['filas_leidas']},
     {metrics['filas_rechazadas']},
     {metrics['filas_agrupadas']},
     {metrics['filas_cargadas']},
     {metrics['total_denuncias']},
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
    GROUP BY anio_registro, mes_registro, ubigeo, modalidad
    HAVING COUNT(*) > 1
)
    THROW 51002, N'Validacion fallida: existen duplicados en el grano del DataMart.', 1;

PRINT N'Validacion correcta.';
GO

SELECT
    COUNT(*)                        AS filas_cargadas,
    SUM(cantidad)                   AS total_denuncias,
    COUNT(DISTINCT departamento)    AS departamentos,
    COUNT(DISTINCT provincia)       AS provincias,
    COUNT(DISTINCT distrito)        AS distritos,
    COUNT(DISTINCT ubigeo)          AS ubigeos,
    COUNT(DISTINCT modalidad)       AS modalidades,
    MIN(anio_registro)              AS anio_min,
    MAX(anio_registro)              AS anio_max,
    SUM(CASE WHEN es_anio_parcial = 1 THEN 1 ELSE 0 END) AS filas_anio_parcial
FROM {TABLE_NAME};
GO
"""

    with sql_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(footer)

    size_mb = sql_path.stat().st_size / (1024 * 1024)
    logging.info(
        "Script SQL generado: %s (%.2f MB)", sql_path, size_mb
    )


# ---------------------------------------------------------------------------
# Ejecución en SQL Server
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
            f"sqlcmd terminó con código {process.returncode}. Revisa el log."
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
        rejected_path = LOG_DIR / f"rechazados_denuncias_{stamp}.csv"
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

    metrics_path = LOG_DIR / f"denuncias_metrics_{stamp}.json"
    with metrics_path.open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2)
    logging.info("Métricas guardadas en: %s", metrics_path)

    if args.generate_only:
        logging.info("Modo --generate-only: no se ejecutó el SQL.")
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
        "Tabla %s: %s filas, %s denuncias.",
        TABLE_NAME,
        f"{metrics['filas_cargadas']:,}",
        f"{metrics['total_denuncias']:,}",
    )
    logging.info("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
