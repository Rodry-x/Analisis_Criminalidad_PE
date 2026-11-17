# Diccionario de datos — `dm.VictimizacionConfianzaPNP`

DataMart de indicadores de victimización, percepción de inseguridad y
confianza en la PNP a nivel nacional y departamental (INEI, ENAPRES),
periodo 2013–2024. Una fila representa el valor de un indicador para un
determinado ámbito (nacional o un departamento) en un año.

- **Base de datos:** `DBVictimizacionConfianzaPNP`
- **Esquema:** `dm`
- **Tabla:** `VictimizacionConfianzaPNP`
- **Grano:** `anio_registro`, `indicador`, `cod_ubicacion`
- **Script de creación y carga:** `Database/04_victimizacion_datamart.sql`
- **ETL:** `Pipeline/etl_victimizacion.py`

> El dataset es **anual**: no existe columna de mes. Por eso el DataMart no
> tiene `mes_registro`; en la unión del DataWarehouse se proyectará
> `NULL AS mes_registro` para los años de este dataset.

## Columnas

| # | Columna | Tipo | Nulo | Descripción | Origen / regla |
|---|---|---|---|---|---|
| 1 | `id_indicador` | `INT IDENTITY` | No | Clave sustituta de la fila | Generada en la carga |
| 2 | `anio_registro` | `SMALLINT` | No | Año del indicador | `VALOR PERIODO` (renombrada) |
| 3 | `fecha_referencia` | `DATE` | No | Fecha de referencia (01 de enero) | Derivada de `anio_registro` |
| 4 | `ambito` | `NVARCHAR(15)` | No | `NACIONAL` o `DEPARTAMENTO` | `AMBITO_PROY` |
| 5 | `cod_ubicacion` | `INT` | No | Código de ubicación del alcance | Re-derivado de `DEPARTAMENTO` |
| 6 | `departamento` | `NVARCHAR(60)` | **Sí** | Departamento canónico; `NULL` si es nacional | `DEPARTAMENTO`, homologado |
| 7 | `indicador` | `NVARCHAR(200)` | No | Nombre del indicador | `INDICADOR` |
| 8 | `clasif` | `SMALLINT` | No | Ranking del indicador en el año (0 = nacional) | `CLASIF` |
| 9 | `valor` | `DECIMAL(5,1)` | No | Valor porcentual (0–100) | `VALOR` |
| 10 | `es_anio_parcial` | `BIT` | No | 1 si el año tiene cobertura incompleta | Derivada (2013 = 1) |
| 11 | `archivo_origen` | `NVARCHAR(200)` | No | CSV de procedencia | Nombre del archivo |
| 12 | `fecha_carga` | `DATETIME2(0)` | No | Fecha y hora de carga | `SYSDATETIME()` |

## Decisiones de diseño sobre columnas del origen

### `PERIODO` (eliminada)

`PERIODO` contiene el literal `AÑO` en **las 1,592 filas**. No aporta
información, así que el ETL la valida y la elimina. Si en una futura versión
del dataset `PERIODO` deja de ser constante, el ETL falla de forma explícita
para no perder información.

### `VALOR PERIODO` → `anio_registro`

Es la columna que realmente contiene el año (2013–2024). Se renombra a
`anio_registro` para que coincida con los DataMarts 1, 2 y 3.

### `AMBITO_PROY` → `ambito` y `DEPARTAMENTO` normalizada

`AMBITO_PROY` solo toma dos valores y es derivable de `DEPARTAMENTO`:

| `AMBITO_PROY` | `DEPARTAMENTO` en el origen | `ambito` | `departamento` | `cod_ubicacion` |
|---|---|---|---|---|
| `NACIONAL` | `NACIONAL` | `NACIONAL` | `NULL` | `0` |
| `DEPARTAMENTO` | Nombre del departamento | `DEPARTAMENTO` | Nombre canónico | Código del departamento |

Se conserva `ambito` porque `DEPARTAMENTO = 'NACIONAL'` **no es un
departamento**: si se dejara así, cualquier suma o filtro por departamento
mezclaría el total país con los 26 departamentos y duplicaría los valores.
Con `departamento = NULL` en las filas nacionales, la dimensión geográfica
queda limpia y el agregado país sigue disponible por `ambito = 'NACIONAL'`.

## Mapeo `cod_ubicacion` ↔ departamento

| Código | Departamento | Filas |
|---|---|---|
| `0` | *(nacional)* | 58 |
| `1` | AMAZONAS | 59 |
| `2` | ANCASH | 59 |
| `3` | APURIMAC | 59 |
| `4` | AREQUIPA | 59 |
| `5` | AYACUCHO | 59 |
| `6` | CAJAMARCA | 59 |
| `7` | PROV. CONST. DEL CALLAO | 59 |
| `8` | CUSCO | 59 |
| `9` | HUANCAVELICA | 59 |
| `10` | HUANUCO | 59 |
| `11` | ICA | 59 |
| `12` | JUNIN | 59 |
| `13` | LA LIBERTAD | 59 |
| `14` | LAMBAYEQUE | 59 |
| `16` | LORETO | 59 |
| `17` | MADRE DE DIOS | 59 |
| `18` | MOQUEGUA | 59 |
| `19` | PASCO | 59 |
| `20` | PIURA | 59 |
| `21` | PUNO | 59 |
| `22` | SAN MARTIN | 59 |
| `23` | TACNA | 59 |
| `24` | TUMBES | 59 |
| `25` | UCAYALI | 59 |
| `1501` | LIMA METROPOLITANA | 59 |
| `1599` | REGION LIMA | 59 |

- El código `15` (Lima como departamento completo) **no se usa**, porque Lima
  se desagrega en `1501` (Lima Metropolitana) y `1599` (Región Lima).
- Los códigos `1`–`25` siguen el orden de ubigeo del INEI, por lo que
  `cod_ubicacion` de 1–25 coincide con los dos primeros dígitos del `ubigeo`
  de los DataMarts 1 y 2. Para unir con ellos:
  `CAST(cod_ubicacion AS CHAR(2)) = LEFT(ubigeo, 2)` (solo para `1`–`25`).

## Corrección de `COD_UBICACION` (6 filas)

En el origen, **6 filas de 2013 del indicador `PORCENTAJE DE VICTIMIZACIÓN
POR ESTAFA`** tienen el código de ubicación desalineado respecto al nombre
del departamento (el código `7`, Callao, falta y los códigos `15`–`20`
apuntan al departamento equivocado).

| Año | Departamento | Código origen | Código corregido |
|---|---|---|---|
| 2013 | PROV. CONST. DEL CALLAO | 20 | **7** |
| 2013 | LORETO | 15 | **16** |
| 2013 | MADRE DE DIOS | 16 | **17** |
| 2013 | MOQUEGUA | 17 | **18** |
| 2013 | PASCO | 18 | **19** |
| 2013 | PIURA | 19 | **20** |

**Por qué se corrige en lugar de rechazar:** en esas 6 filas el nombre del
departamento es coherente con `VALOR` y con `CLASIF` (el ranking se
corresponde exactamente con el valor), y los 26 departamentos aparecen
exactamente una vez. El campo desalineado es el código, no el nombre. El ETL
re-deriva `cod_ubicacion` desde `DEPARTAMENTO` en **todas** las filas y deja
constancia de las correcciones en el log y en `etl.ControlCarga`
(`filas_codigo_corregido = 6`).

## Departamentos homologados

Se aplica el estilo canónico de los otros DataMarts (mayúsculas, sin tildes):

| Origen | Canónico |
|---|---|
| `ÁNCASH` | `ANCASH` |
| `APURÍMAC` | `APURIMAC` |
| `HUÁNUCO` | `HUANUCO` |
| `JUNÍN` | `JUNIN` |
| `SAN MARTÍN` | `SAN MARTIN` |
| `REGIÓN LIMA` | `REGION LIMA` |

Total homologado: 354 filas (59 por cada uno de los 6 nombres).

## Indicadores

| Indicador | Filas | Rango de `valor` |
|---|---|---|
| `PORCENTAJE DE CONFIANZA EN LA PNP` | 297 | 4.4 – 39.7 |
| `PORCENTAJE DE PERCEPCIÓN DE INSEGURIDAD AL CAMINAR SOLO(A) DE NOCHE EN SU ZONA O BARRIO` | 324 | 12.5 – 76.7 |
| `PORCENTAJE DE VICTIMIZACIÓN` | 323 | 8.4 – 46.3 |
| `PORCENTAJE DE VICTIMIZACIÓN POR EL DELITO DE ROBO E INTENTO DE ROBO DE DINERO, CARTERA Y CELULAR` | 324 | 2.5 – 29.6 |
| `PORCENTAJE DE VICTIMIZACIÓN POR ESTAFA` | 324 | 0.2 – 17.9 |

`valor` es siempre un **porcentaje** (0–100) con **un decimal** en el origen.
Los indicadores conservan sus tildes y su nombre oficial completo.

## `CLASIF` (ranking)

`CLASIF` es el puesto del alcance dentro del indicador y año: `0` es el total
nacional y `1` es el valor más alto entre los 26 departamentos.

- **No forma parte de la clave**: hay empates (por ejemplo, dos departamentos
  con el mismo valor comparten el mismo `CLASIF`), por lo que no es único.
- Se conserva como dato descriptivo, no como identificador.

## Cobertura y año parcial

Cada año completo tiene **5 indicadores × 27 alcances = 135 filas**.

| Año | Filas | Indicadores | Estado |
|---|---|---|---|
| 2013 | 107 | 4 | **Parcial** |
| 2014–2024 | 135 | 5 | Completo |

En 2013:

- No existe ninguna fila de `PORCENTAJE DE CONFIANZA EN LA PNP`.
- Falta la fila nacional (`cod_ubicacion = 0`) de `PORCENTAJE DE VICTIMIZACIÓN`.

Por eso todas las filas de 2013 tienen `es_anio_parcial = 1`. El cálculo es
por **cobertura** (indicadores × alcances), no por meses, porque el dataset no
tiene granularidad mensual.

## Reglas de calidad

- `anio_registro` entre 2013 y 2024.
- `indicador` no vacío.
- `ambito` en `NACIONAL` / `DEPARTAMENTO`.
- Coherencia: `NACIONAL` ⇔ `cod_ubicacion = 0` ⇔ `departamento IS NULL`.
- `clasif` entero entre 0 y 26 (se admite hasta 100 por holgura).
- `valor` decimal finito entre 0 y 100.
- Sin duplicados en el grano `(anio_registro, indicador, cod_ubicacion)`.
- `archivo_origen` conserva la trazabilidad hacia el CSV original.

## Índices

| Índice | Tipo | Columnas |
|---|---|---|
| `PK_VictimizacionConfianzaPNP` | Clustered, único | `id_indicador` |
| `UX_VictimizacionConfianzaPNP_Grano` | Nonclustered, único | `anio_registro, indicador, cod_ubicacion` |
| `IX_VictimizacionConfianzaPNP_Anio` | Nonclustered | `anio_registro` (incluye `valor`) |
| `IX_VictimizacionConfianzaPNP_Indicador` | Nonclustered | `indicador` (incluye `valor`) |
| `IX_VictimizacionConfianzaPNP_Ubicacion` | Nonclustered | `cod_ubicacion` (incluye `valor`) |

## Tabla de control

`etl.ControlCarga` registra cada ejecución del ETL: dataset, archivo, hash
SHA-256 del origen, filas leídas/rechazadas/agrupadas/cargadas, filas con
código corregido, filas de año parcial, total de indicadores, fechas, estado y
detalle en JSON.

## Nota de interpretación

`valor` es un porcentaje: **no debe sumarse entre indicadores ni entre años**.
Para comparar, promediar o graficar, filtrar siempre por `indicador` y por
`ambito`. El total nacional ya está calculado en la fila con
`ambito = 'NACIONAL'`; no lo reconstruyas sumando departamentos.
