# Diccionario de datos — `dm.PersonasDesaparecidas`

DataMart de personas desaparecidas registradas a nivel nacional (MININTER),
periodo 2019–2025. Una fila representa el total de casos de un distrito y mes
determinados, desagregado por sexo, rango de edad y nacionalidad.

- **Base de datos:** `DBPersonasDesaparecidas`
- **Esquema:** `dm`
- **Tabla:** `PersonasDesaparecidas`
- **Grano:** `anio_registro`, `mes_registro`, `ubigeo`, `sexo`, `rango_edad`, `nacionalidad`
- **Script de creación y carga:** `Database/02_personas_desaparecidas_datamart.sql`
- **ETL:** `Pipeline/etl_personas_desaparecidas.py`

## Columnas

| # | Columna | Tipo | Nulo | Descripción | Origen / regla |
|---|---|---|---|---|---|
| 1 | `id_desaparicion` | `INT IDENTITY` | No | Clave sustituta de la fila | Generada en la carga |
| 2 | `anio_registro` | `SMALLINT` | No | Año del hecho | `AÑO` |
| 3 | `mes_registro` | `TINYINT` | No | Mes del hecho (1–12) | `MES` |
| 4 | `fecha_hecho` | `DATE` | No | Primer día del mes del hecho | Derivada de año y mes |
| 5 | `departamento` | `NVARCHAR(60)` | No | Departamento donde ocurrió el hecho | `DPTO_HECHO`, homologado |
| 6 | `provincia` | `NVARCHAR(100)` | No | Provincia donde ocurrió el hecho | `PROV_HECHO` |
| 7 | `distrito` | `NVARCHAR(120)` | No | Distrito donde ocurrió el hecho | `DIST_HECHO` |
| 8 | `ubigeo` | `CHAR(6)` | No | Código ubigeo del distrito | `UBIGEO_HECHO`, normalizado a 6 dígitos |
| 9 | `sexo` | `NCHAR(1)` | Sí | Sexo de la persona desaparecida | `SEXO` (`F`/`M`); vacío → `NULL` |
| 10 | `rango_edad` | `NVARCHAR(30)` | Sí | Rango de edad de la persona desaparecida | `RANGO_EDAD`; vacío → `NULL` |
| 11 | `nacionalidad` | `NVARCHAR(60)` | No | Nacionalidad de la persona desaparecida | `NACIONALIDAD` |
| 12 | `cantidad` | `INT` | No | Número de casos | `CANTIDAD` |
| 13 | `es_anio_parcial` | `BIT` | No | 1 si el año no tiene diciembre; 0 si está completo | Derivada |
| 14 | `archivo_origen` | `NVARCHAR(400)` | No | CSV de procedencia | Nombre del archivo |
| 15 | `fecha_carga` | `DATETIME2(0)` | No | Fecha y hora de carga | `SYSDATETIME()` |

## Tratamiento de codificación (CP1252 → UTF-8)

El CSV original viene en **CP1252 (Windows-1252)**: si se abre como UTF-8, las
tildes y la Ñ aparecen como `?` o `�`. El ETL resuelve esto así:

1. Detecta la codificación real del archivo crudo probando `utf-8-sig`,
   `cp1252` y `latin-1` en ese orden.
2. Genera una copia fiel con BOM en
   `Dataset-Procesado/Personas-Desaparecidas_2019-2025/Personas_Desaparecidas_2019_2025_utf8.csv`
   (`utf-8-sig`), conservando el contenido, las comas y los saltos de línea
   originales.
3. Lee esa copia UTF-8 para todo el procesamiento posterior.
4. Escribe el script SQL en UTF-8 **sin BOM** y lo ejecuta con
   `sqlcmd -f 65001`, con lo que los acentos y la Ñ llegan intactos a
   SQL Server (`N'...'` en todos los literales de texto).

Los caracteres no ASCII conservados son `Á`, `Í`, `Ñ`, `Ó`, `Ú`.

## Reglas de calidad

- `anio_registro` entre 2019 y 2025.
- `mes_registro` entre 1 y 12.
- `cantidad` entero mayor o igual a 0.
- `ubigeo` exactamente 6 dígitos numéricos.
- `departamento`, `provincia`, `distrito` y `nacionalidad` no pueden estar vacíos.
- `sexo` solo admite `F`, `M` o vacío (→ `NULL`).
- `rango_edad` solo admite los seis rangos oficiales o vacío (→ `NULL`).
- El prefijo del ubigeo debe corresponder al departamento:
  - `15` → `LIMA METROPOLITANA` o `REGION LIMA`
  - `07` → `PROV. CONST. DEL CALLAO`
  - Los demás prefijos tienen un único departamento.
- No se permiten duplicados en el grano
  `(anio_registro, mes_registro, ubigeo, sexo, rango_edad, nacionalidad)`.
- `archivo_origen` conserva la trazabilidad hacia el CSV original.

## Homologaciones aplicadas

### Ubigeos

| Ubigeo | Valores encontrados | Valor homologado | Filas |
|---|---|---|---|
| `150121` | `LIMA / PUEBLO LIBRE` (68) y `LIMA / MAGDALENA VIEJA` (2) | `LIMA METROPOLITANA / LIMA / PUEBLO LIBRE` | 70 |
| `160801` | — | `LORETO / PUTUMAYO / PUTUMAYO` | 0 |

> El ubigeo `160801` no aparece en este dataset; se deja la regla por
> consistencia con el DataMart de Denuncias Policiales.

### Nombres de departamento

Los departamentos se homologan al estilo canónico sin tildes usado en el
Dataset 1. Las provincias, distritos y nacionalidades **conservan** sus tildes
y la Ñ.

| Valor en el origen | Valor canónico | Filas |
|---|---|---|
| `JUNÍN` | `JUNIN` | 4,825 |
| `REGIÓN LIMA` | `REGION LIMA` | 2,997 |
| `HUÁNUCO` | `HUANUCO` | 2,753 |
| `ÁNCASH` | `ANCASH` | 2,535 |
| `SAN MARTÍN` | `SAN MARTIN` | 2,084 |
| `CALLAO` | `PROV. CONST. DEL CALLAO` | 1,953 |

Total de filas con departamento homologado: **17,147**.

## Valores vacíos conservados

| Campo | Filas con valor vacío | Carga en SQL Server |
|---|---|---|
| `SEXO` | 83 | `NULL` |
| `RANGO_EDAD` | 1,197 | `NULL` |

## Rangos de edad

- `0-5 AÑOS`
- `6-11 AÑOS`
- `12-17 AÑOS`
- `18-29 AÑOS`
- `30-59 AÑOS`
- `60 A MAS AÑOS`

## Sexo

- `F` — Femenino
- `M` — Masculino
- `NULL` — no informado

## Índices

| Índice | Tipo | Columnas |
|---|---|---|
| `PK_PersonasDesaparecidas` | Clustered, único | `id_desaparicion` |
| `UX_PersonasDesaparecidas_Grano` | Nonclustered, único | `anio_registro, mes_registro, ubigeo, sexo, rango_edad, nacionalidad` |
| `IX_PersonasDesaparecidas_AnioMes` | Nonclustered | `anio_registro, mes_registro` (incluye `cantidad`) |
| `IX_PersonasDesaparecidas_Ubigeo` | Nonclustered | `ubigeo` (incluye `cantidad`) |
| `IX_PersonasDesaparecidas_Nacionalidad` | Nonclustered | `nacionalidad` (incluye `cantidad`) |

## Tabla de control

`etl.ControlCarga` registra cada ejecución del ETL: dataset, archivo, hash
SHA-256 del origen, filas leídas/rechazadas/agrupadas/cargadas, total de casos,
fechas, estado y detalle en JSON (incluida la información de codificación).

## Nota sobre años parciales

A diferencia del DataMart de denuncias, aquí los siete años (2019–2025)
registran los 12 meses, por lo que `es_anio_parcial = 0` en todas las filas.
La regla solo marcaría un año si su último mes cargado fuese anterior a
diciembre.
