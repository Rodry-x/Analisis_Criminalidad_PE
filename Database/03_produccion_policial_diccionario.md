# Diccionario de datos — `dm.ProduccionPolicial`

DataMart de producción policial (operativos y resultados) a nivel nacional
(MININTER), periodo 2023–2026. Una fila representa el valor de una variable de
producción para una dependencia policial en un mes determinado.

- **Base de datos:** `DBProduccionPolicial`
- **Esquema:** `dm`
- **Tabla:** `ProduccionPolicial`
- **Grano:** `anio_registro`, `mes_registro`, `dependencia`, `variable`
- **Script de creación y carga:** `Database/03_produccion_policial_datamart.sql`
- **ETL:** `Pipeline/etl_produccion_policial.py`

## Columnas

| # | Columna | Tipo | Nulo | Descripción | Origen / regla |
|---|---|---|---|---|---|
| 1 | `id_produccion` | `INT IDENTITY` | No | Clave sustituta de la fila | Generada en la carga |
| 2 | `anio_registro` | `SMALLINT` | No | Año de referencia | `AÑO` |
| 3 | `mes_registro` | `TINYINT` | No | Mes de referencia (**1–12**) | `MES`, convertido de abreviatura |
| 4 | `fecha_hecho` | `DATE` | No | Primer día del mes | Derivada de año y mes |
| 5 | `variable` | `NVARCHAR(100)` | No | Variable de análisis (operativos y resultados) | `VARIABLE` |
| 6 | `unidad_medida` | `NVARCHAR(30)` | No | Unidad de `valor` | Derivada de `variable` |
| 7 | `dependencia` | `NVARCHAR(60)` | No | Dependencia policial | `DEPENDENCIAS` |
| 8 | `dir_reg_fre` | `NVARCHAR(30)` | No | Tipo/ámbito de la dependencia | `DIR_REG_FRE`, homologado |
| 9 | `valor` | `DECIMAL(18,6)` | No | Valor reportado (puede ser 0) | `VALOR` |
| 10 | `es_anio_parcial` | `BIT` | No | 1 si el año no tiene diciembre | Derivada (2026 = 1) |
| 11 | `archivo_origen` | `NVARCHAR(80)` | No | CSV de procedencia | Nombre del archivo |
| 12 | `fecha_carga` | `DATETIME2(0)` | No | Fecha y hora de carga | `SYSDATETIME()` |

## Conversión del mes a número

El origen trae el mes como abreviatura en español. Para que este DataMart sea
concordante con `dm.DenunciasPoliciales` y `dm.PersonasDesaparecidas` (y la
unión posterior en el DataWarehouse sea directa), el ETL lo convierte a número:

| Abreviatura | Mes | Número |
|---|---|---|
| `ENE` | Enero | 1 |
| `FEB` | Febrero | 2 |
| `MAR` | Marzo | 3 |
| `ABR` | Abril | 4 |
| `MAY` | Mayo | 5 |
| `JUN` | Junio | 6 |
| `JUL` | Julio | 7 |
| `AGO` | Agosto | 8 |
| `SET` | Setiembre | 9 |
| `OCT` | Octubre | 10 |
| `NOV` | Noviembre | 11 |
| `DIC` | Diciembre | 12 |

> `SET` es la abreviatura usada por el MININTER para setiembre. El ETL también
> acepta `SEP`. Además admite nombres completos y meses numéricos `1`–`12`.

## Unidad de medida

`VALOR` mezcla conteos, kilos, envoltorios y soles en una sola columna. Por eso
se agregó `unidad_medida`, que se deriva del nombre de la variable y es
indispensable para no sumar magnitudes incompatibles:

| Variable | Unidad |
|---|---|
| `ARMAS BLANCAS` | `UNIDADES` |
| `ARMAS DE FUEGO` | `UNIDADES` |
| `BANDAS CRIMINALES DESARTICULADAS` | `UNIDADES` |
| `ORGANIZACIONES CRIMINALES DESARTICULADAS` | `UNIDADES` |
| `CC (ENVOLTORIOS)` | `ENVOLTORIOS` |
| `PBC (ENVOLTORIOS)` | `ENVOLTORIOS` |
| `MARIHUANA (ENVOLTORIO)` | `ENVOLTORIO` |
| `CC (KILOS)` | `KILOS` |
| `MARIHUANA (KILOS)` | `KILOS` |
| `PBC (KILOS)` | `KILOS` |
| `DINERO INCAUTADO (SOLES)` | `SOLES` |
| `CONTRABANDO (VALORIZACION)` | `SOLES (VALORIZACION)` |
| `DETENIDOS DIVERSOS DELITOS (EXTRANJEROS)` | `PERSONAS` |
| `DETENIDOS DIVERSOS DELITOS (PERUANOS)` | `PERSONAS` |
| `DETENIDOS POR REQUISITORIADO` | `PERSONAS` |
| `INTERVENCION EXTRAJEROS (LEY MIGRATORIA)` | `PERSONAS` |
| `OPERATIVOS` | `OPERATIVOS` |
| `PAPELETAS INFRACCION RNT` | `PAPELETAS` |

`INTERVENCION EXTRAJEROS` conserva la grafía del origen (debería decir
`EXTRANJEROS`) para no alterar el nombre oficial de la variable.

## Valores cero

El diccionario oficial indica que `VALOR = 0` significa que **no se reportaron
operativos ni resultados** para esa variable, dependencia y mes. Por eso las
**15,458 filas con valor 0 se conservan**; no son datos faltantes.

## Tipo de dependencia (`dir_reg_fre`)

| Valor | Dependencias | Filas |
|---|---|---|
| `REGION` | 25 | 19,836 |
| `DIRNIC` | 12 | 9,504 |
| `DIRNOS` | 8 | 5,760 |
| `FRENTE` | 6 | 3,204 |
| `RP ICA` | 1 | 396 |
| `RP TUMBES` | 1 | 396 |

- `Región` del origen se homologa a `REGION` (mayúsculas, sin tilde).
- Cada `dependencia` tiene un único `dir_reg_fre`.
- En 2025 y 2026 aparecen `RP ICA` y `RP TUMBES` como valor de `dir_reg_fre`
  (el origen repite el nombre de la dependencia en lugar del tipo). Se
  mantienen tal cual y se documentan como inconsistencia del origen.

## Cambio estructural 2025–2026

En 2023–2024 existen las dependencias `FP APURIMAC`, `FP CAJAMARCA`,
`FP ICA`, `FP PUERTO INCA` y `FP TUMBES` (Frentes Policiales). A partir de
2025 esas filas pasan a registrarse como `RP APURIMAC`, `RP CAJAMARCA`,
`RP ICA` y `RP TUMBES` (Regiones Policiales). **No se homologaron** porque son
unidades orgánicas distintas: cualquier serie temporal por dependencia debe
considerar este corte estructural.

## Reglas de calidad

- `anio_registro` entre 2023 y 2026.
- `mes_registro` entre 1 y 12 (tras convertir la abreviatura).
- `valor` decimal finito mayor o igual a 0, con hasta 6 decimales.
- `variable`, `dependencia` y `dir_reg_fre` no pueden estar vacías.
- No se permiten duplicados en el grano
  `(anio_registro, mes_registro, dependencia, variable)`.
- `archivo_origen` conserva la trazabilidad hacia el CSV original.

## Índices

| Índice | Tipo | Columnas |
|---|---|---|
| `PK_ProduccionPolicial` | Clustered, único | `id_produccion` |
| `UX_ProduccionPolicial_Grano` | Nonclustered, único | `anio_registro, mes_registro, dependencia, variable` |
| `IX_ProduccionPolicial_AnioMes` | Nonclustered | `anio_registro, mes_registro` (incluye `valor`) |
| `IX_ProduccionPolicial_Dependencia` | Nonclustered | `dependencia` (incluye `valor`) |
| `IX_ProduccionPolicial_Variable` | Nonclustered | `variable` (incluye `valor`) |

## Tabla de control

`etl.ControlCarga` registra cada ejecución del ETL: dataset, archivos, hash
SHA-256 del origen, filas leídas/rechazadas/agrupadas/cargadas, filas con
valor 0, suma total de `valor`, fechas, estado y detalle en JSON.

> La columna `total_valor` es solo una referencia de control: al mezclar
> unidades (kilos, soles, personas, unidades) **no debe interpretarse como un
> total consolidado**. Para analizar, filtrar siempre por `unidad_medida` o
> por `variable`.

## Nota sobre 2026

El archivo de 2026 solo contiene enero–octubre (10 meses). Todas sus filas
tienen `es_anio_parcial = 1` y no deben compararse directamente con años
completos.
