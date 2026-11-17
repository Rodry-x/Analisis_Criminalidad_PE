# EF Final — Base de Datos Avanzadas y Big Data

Proyecto de Inteligencia de Negocios y Big Data sobre la criminalidad en el Perú,
usando datasets abiertos del MININTER.

## Estructura del repositorio

```text
Dataset-Crudo/                 Datasets originales y diccionarios de datos
  Denuncias-Policiales_2018-2026/
  Personas-Desaparecidas_2019-2025/
  Produccion-Policial_2023-2026/
  Indicadores-de-Victimizacion-y-confianza-PNP_2013-2024/
 0-Diccionario-de-datos/      Diccionarios oficiales en Excel
Dataset-Procesado/             Copias limpias y convertidas (UTF-8)
Database/                      Scripts SQL y diccionarios de los datamarts
Pipeline/                      Scripts ETL y logs de ejecución
Documentacion/                 Informe y documentación del proyecto
```

## Entorno de ejecución

Todos los ETL se ejecutan con el entorno Conda **`ciencia-de-datos`**:

- Python 3.12.16
- pandas 2.3.3
- SQL Server 2025 Developer en `localhost` (autenticación Windows)

```powershell
conda activate ciencia-de-datos
```

## Dataset 1 — Denuncias Policiales 2018-2026

**Estado:** ETL implementado y cargado en SQL Server.

| Elemento | Valor |
|---|---|
| Archivos de origen | 9 CSV (2018–2026) |
| Filas cargadas | 378,187 |
| Denuncias acumuladas | 7,614,774 |
| Base de datos | `DBDenunciasPoliciales` |
| Tabla | `dm.DenunciasPoliciales` |
| Script SQL | `Database/01_denuncias_policiales_datamart.sql` |
| ETL | `Pipeline/etl_denuncias.py` |

### Ejecución

```powershell
# Opción 1: con el entorno activado
conda activate ciencia-de-datos
python Pipeline/etl_denuncias.py

# Opción 2: sin activar el entorno (usa conda run)
.\Pipeline\run_etl_denuncias.bat

# Solo generar el .sql, sin cargar en SQL Server
python Pipeline/etl_denuncias.py --generate-only
```

Parámetros disponibles:

```text
--server        Instancia de SQL Server (por defecto: localhost)
--database      Nombre de la base (por defecto: DBDenunciasPoliciales)
--sqlcmd        Ruta explícita a sqlcmd.exe
--batch-size    Filas por INSERT masivo (por defecto: 1000)
--generate-only Solo genera el script SQL
```

### Salidas de cada ejecución

- `Database/01_denuncias_policiales_datamart.sql`: script autocontenido con
  DDL, datos, índices, control de carga y validaciones.
- `Pipeline/logs/etl_denuncias_<fecha>.log`: log detallado.
- `Pipeline/logs/denuncias_metrics_<fecha>.json`: métricas del ETL.
- `Pipeline/logs/rechazados_denuncias_<fecha>.csv`: solo si hay filas rechazadas.

### Limpieza aplicada

1. Unión de los 9 CSV.
2. `TRIM` y colapso de espacios en campos de texto.
3. `UBIGEO_HECHO` normalizado a 6 dígitos (recupera el cero inicial de los
   departamentos 01–09).
4. Homologación del ubigeo `160801` a `LORETO / PUTUMAYO / PUTUMAYO`.
5. Validación de año (2018–2026), mes (1–12), cantidad (entero ≥ 0), ubigeo de
   6 dígitos y compatibilidad departamento–ubigeo.
6. Agrupación de duplicados por grano
   `(anio_registro, mes_registro, ubigeo, modalidad)` sumando `cantidad`.
7. Derivación de `fecha_hecho` (primer día del mes).
8. Marca `es_anio_parcial = 1` para años sin diciembre (2026).

### Validación rápida

```sql
USE DBDenunciasPoliciales;

SELECT COUNT(*) AS filas, SUM(cantidad) AS denuncias
FROM dm.DenunciasPoliciales;

SELECT * FROM etl.ControlCarga;
```

Resultado esperado:

```text
filas    denuncias
-------- ---------
378187   7614774
```

## Dataset 2 — Personas Desaparecidas 2019-2025

**Estado:** ETL implementado y cargado en SQL Server.

| Elemento | Valor |
|---|---|
| Archivo de origen | 1 CSV (2019–2025) |
| Codificación original | CP1252 (Windows-1252) |
| Copia UTF-8 | `Dataset-Procesado/Personas-Desaparecidas_2019-2025/Personas_Desaparecidas_2019_2025_utf8.csv` |
| Filas cargadas | 77,331 |
| Casos acumulados | 142,374 |
| Base de datos | `DBPersonasDesaparecidas` |
| Tabla | `dm.PersonasDesaparecidas` |
| Script SQL | `Database/02_personas_desaparecidas_datamart.sql` |
| Diccionario | `Database/02_personas_desaparecidas_diccionario.md` |
| ETL | `Pipeline/etl_personas_desaparecidas.py` |

### Ejecución

```powershell
# Opción 1: sin activar el entorno (usa conda run)
.\Pipeline\run_etl_personas_desaparecidas.bat

# Opción 2: con el entorno activado
conda activate ciencia-de-datos
python Pipeline/etl_personas_desaparecidas.py

# Solo generar el .sql y la copia UTF-8, sin cargar en SQL Server
python Pipeline/etl_personas_desaparecidas.py --generate-only
```

Parámetros disponibles:

```text
--server        Instancia de SQL Server (por defecto: localhost)
--database      Nombre de la base (por defecto: DBPersonasDesaparecidas)
--sqlcmd        Ruta explícita a sqlcmd.exe
--batch-size    Filas por INSERT masivo (por defecto: 1000)
--generate-only Solo genera el script SQL
--reuse-utf8    Reutiliza la copia UTF-8 existente sin reconvertir el crudo
```

### Conversión CP1252 → UTF-8

El CSV original está en **CP1252**, por lo que al abrirlo como UTF-8 las
tildes y la Ñ se ven como `?` o `�` (`A?O`, `PER?`, `JUN?N`). El ETL:

1. Detecta la codificación real probando `utf-8-sig`, `cp1252` y `latin-1`.
2. Genera una copia fiel con BOM (`utf-8-sig`) en `Dataset-Procesado/`,
   conservando el contenido, las comas y los saltos de línea originales.
3. Procesa esa copia UTF-8 y escribe el `.sql` en UTF-8 sin BOM.
4. Ejecuta `sqlcmd -f 65001`, por lo que `PERÚ`, `JUNÍN`, `12-17 AÑOS`,
   `BREÑA` y demás textos llegan correctos a SQL Server.

### Salidas de cada ejecución

- `Dataset-Procesado/Personas-Desaparecidas_2019-2025/Personas_Desaparecidas_2019_2025_utf8.csv`
- `Database/02_personas_desaparecidas_datamart.sql`
- `Pipeline/logs/etl_personas_desaparecidas_<fecha>.log`
- `Pipeline/logs/personas_desaparecidas_metrics_<fecha>.json`
- `Pipeline/logs/rechazados_personas_desaparecidas_<fecha>.csv` (solo si hay rechazos)

### Limpieza aplicada

1. Conversión CP1252 → UTF-8 (`utf-8-sig`).
2. `TRIM` y colapso de espacios en campos de texto.
3. `UBIGEO_HECHO` normalizado a 6 dígitos.
4. Departamentos homologados al estilo canónico sin tildes:
   `ÁNCASH`→`ANCASH`, `HUÁNUCO`→`HUANUCO`, `JUNÍN`→`JUNIN`,
   `SAN MARTÍN`→`SAN MARTIN`, `REGIÓN LIMA`→`REGION LIMA`,
   `CALLAO`→`PROV. CONST. DEL CALLAO`. Provincias, distritos y
   nacionalidades conservan sus tildes y la Ñ.
5. Homologación del ubigeo `150121` a
   `LIMA METROPOLITANA / LIMA / PUEBLO LIBRE` (70 filas).
6. Validación de año (2019–2025), mes (1–12), cantidad (entero ≥ 0), ubigeo de
   6 dígitos, departamento compatible con el ubigeo y campos requeridos.
7. `SEXO` y `RANGO_EDAD` vacíos se cargan como `NULL` (83 y 1,197 filas).
8. Agrupación de duplicados por grano
   `(anio_registro, mes_registro, ubigeo, sexo, rango_edad, nacionalidad)`
   sumando `cantidad`.
9. Derivación de `fecha_hecho` y de `es_anio_parcial`.

### Validación rápida

```sql
USE DBPersonasDesaparecidas;

SELECT COUNT(*) AS filas, SUM(cantidad) AS casos
FROM dm.PersonasDesaparecidas;

SELECT * FROM etl.ControlCarga;
```

Resultado esperado:

```text
filas    casos
-------- ---------
77331    142374
```

## Dataset 3 — Producción Policial 2023-2026

**Estado:** ETL implementado y cargado en SQL Server.

| Elemento | Valor |
|---|---|
| Archivos de origen | 4 CSV (2023–2026) |
| Codificación original | UTF-8 con BOM (sin conversión necesaria) |
| Filas cargadas | 39,096 |
| Base de datos | `DBProduccionPolicial` |
| Tabla | `dm.ProduccionPolicial` |
| Script SQL | `Database/03_produccion_policial_datamart.sql` |
| Diccionario | `Database/03_produccion_policial_diccionario.md` |
| ETL | `Pipeline/etl_produccion_policial.py` |

### Ejecución

```powershell
# Opción 1: sin activar el entorno (usa conda run)
.\Pipeline\run_etl_produccion_policial.bat

# Opción 2: con el entorno activado
conda activate ciencia-de-datos
python Pipeline/etl_produccion_policial.py

# Solo generar el .sql, sin cargar en SQL Server
python Pipeline/etl_produccion_policial.py --generate-only
```

Parámetros disponibles:

```text
--server        Instancia de SQL Server (por defecto: localhost)
--database      Nombre de la base (por defecto: DBProduccionPolicial)
--sqlcmd        Ruta explícita a sqlcmd.exe
--batch-size    Filas por INSERT masivo (por defecto: 1000)
--generate-only Solo genera el script SQL
```

### Mes como número

El origen trae el mes como abreviatura en español (`ENE`, `FEB`, …, `SET`, …,
`DIC`). El ETL lo convierte a **número 1–12** para que los tres DataMarts
tengan la misma clave temporal (`anio_registro`, `mes_registro`) y la unión en
el DataWarehouse sea directa. La equivalencia completa está en el diccionario.

### Salidas de cada ejecución

- `Database/03_produccion_policial_datamart.sql`
- `Pipeline/logs/etl_produccion_policial_<fecha>.log`
- `Pipeline/logs/produccion_policial_metrics_<fecha>.json`
- `Pipeline/logs/rechazados_produccion_policial_<fecha>.csv` (solo si hay rechazos)

### Limpieza aplicada

1. Detección de codificación por archivo (los CSV ya vienen en UTF-8 con BOM).
2. `TRIM`, colapso de espacios y mayúsculas en textos.
3. `MES` convertido de abreviatura a número (1–12).
4. `VALOR` convertido a `DECIMAL(18,6)`, conservando los ceros (que según el
   diccionario significan “sin operativos o resultados reportados”).
5. `unidad_medida` derivada de la variable (`KILOS`, `ENVOLTORIOS`, `SOLES`,
   `PERSONAS`, `UNIDADES`, etc.) para no mezclar magnitudes.
6. Homologación de `DIR_REG_FRE` (`Región` → `REGION`).
7. Validación de año (2023–2026), mes, valor (≥ 0) y textos requeridos.
8. Agrupación de duplicados por grano
   `(anio_registro, mes_registro, dependencia, variable)` sumando `valor`.
9. Derivación de `fecha_hecho` y de `es_anio_parcial` (2026 = 1).

### Validación rápida

```sql
USE DBProduccionPolicial;

SELECT COUNT(*) AS filas, SUM(valor) AS total_valor
FROM dm.ProduccionPolicial;

SELECT anio_registro, COUNT(DISTINCT mes_registro) AS meses, COUNT(*) AS filas
FROM dm.ProduccionPolicial
GROUP BY anio_registro
ORDER BY anio_registro;

SELECT * FROM etl.ControlCarga;
```

Resultado esperado:

```text
filas    total_valor
-------- -----------
39096    2195845317.111756
```

```text
anio_registro meses filas
------------- ----- -----
2023          12    9936
2024          12    9936
2025          12    10584
2026          10    8640
```

### Aviso de interpretación

`VALOR` mezcla unidades (kilos, envoltorios, soles, personas, unidades). Para
cualquier análisis o visualización, **filtrar siempre por `unidad_medida` o por
`variable`**; nunca sumar todo junto.

## Dataset 4 — Victimización y Confianza en la PNP 2013-2024

**Estado:** ETL implementado y cargado en SQL Server.

| Elemento | Valor |
|---|---|
| Archivos de origen | 1 CSV (2013–2024) |
| Codificación original | CP1252 (convertido a UTF-8 con BOM) |
| Filas cargadas | 1,592 |
| Base de datos | `DBVictimizacionConfianzaPNP` |
| Tabla | `dm.VictimizacionConfianzaPNP` |
| Script SQL | `Database/04_victimizacion_datamart.sql` |
| Diccionario | `Database/04_victimizacion_diccionario.md` |
| ETL | `Pipeline/etl_victimizacion.py` |

### Ejecución

```powershell
# Opción 1: sin activar el entorno (usa conda run)
.\Pipeline\run_etl_victimizacion.bat

# Opción 2: con el entorno activado
conda activate ciencia-de-datos
python Pipeline/etl_victimizacion.py

# Solo generar el .sql, sin cargar en SQL Server
python Pipeline/etl_victimizacion.py --generate-only
```

Parámetros disponibles:

```text
--server        Instancia de SQL Server (por defecto: localhost)
--database      Nombre de la base (por defecto: DBVictimizacionConfianzaPNP)
--sqlcmd        Ruta explícita a sqlcmd.exe
--batch-size    Filas por INSERT masivo (por defecto: 1000)
--generate-only Solo genera el script SQL
--reuse-utf8    Reutiliza la copia UTF-8 ya generada
```

### Decisiones sobre columnas del origen

- **`PERIODO` se elimina**: es constante `AÑO` en las 1,592 filas.
- **`VALOR PERIODO` → `anio_registro`**: es la columna que contiene el año.
- **`AMBITO_PROY` → `ambito`**: se conserva porque evita confundir el total
  país con un departamento. En las filas nacionales se guarda
  `departamento = NULL` y `cod_ubicacion = 0`.
- **`DEPARTAMENTO`**: se homologa al estilo canónico sin tildes.
- **`cod_ubicacion`**: se re-deriva del nombre del departamento. Esto corrige
  6 filas de 2013 (victimización por estafa) cuyo código estaba desalineado;
  no se descarta ninguna fila.

El dataset es **anual**, así que no tiene `mes_registro`; se agrega
`fecha_referencia` (01 de enero).

### Grano temporal (anual)

Este dataset no tiene columna de mes: su grano es anual
(`anio_registro`, `indicador`, `cod_ubicacion`). En la unión del DataWarehouse
se usará `NULL AS mes_registro`.

### Salidas de cada ejecución

- `Database/04_victimizacion_datamart.sql`
- `Pipeline/logs/etl_victimizacion_<fecha>.log`
- `Pipeline/logs/victimizacion_metrics_<fecha>.json`
- `Pipeline/logs/rechazados_victimizacion_<fecha>.csv` (solo si hay rechazos)
- `Dataset-Procesado/Indicadores-de-Victimizacion-y-confianza-PNP_2013-2024/Victimizacion_Confianza_PNP_2013_2024_utf8.csv`

### Limpieza aplicada

1. Detección de codificación (CP1252) y copia fiel a UTF-8 con BOM.
2. `TRIM`, colapso de espacios y mayúsculas en textos.
3. Eliminación de `PERIODO` (constante) y renombrado de `VALOR PERIODO`.
4. Homologación de departamentos (`ÁNCASH`, `APURÍMAC`, `HUÁNUCO`, `JUNÍN`,
   `SAN MARTÍN`, `REGIÓN LIMA`).
5. Re-derivación de `cod_ubicacion` desde el departamento (6 filas corregidas).
6. `valor` convertido a `DECIMAL(5,1)` (porcentaje 0–100).
7. Validación de año (2013–2024), indicador, ámbito, `clasif` y `valor`.
8. Derivación de `fecha_referencia` y de `es_anio_parcial`
   (2013 por cobertura incompleta).

### Validación rápida

```sql
USE DBVictimizacionConfianzaPNP;

SELECT COUNT(*) AS filas, SUM(valor) AS suma_valor
FROM dm.VictimizacionConfianzaPNP;

SELECT anio_registro, COUNT(*) AS filas,
       COUNT(DISTINCT indicador) AS indicadores
FROM dm.VictimizacionConfianzaPNP
GROUP BY anio_registro
ORDER BY anio_registro;

SELECT * FROM etl.ControlCarga;
```

Resultado esperado:

```text
filas suma_valor
----- ----------
1592  36287.6
```

```text
anio_registro filas indicadores
------------- ----- -----------
2013          107   4          <- parcial
2014          135   5
...
2024          135   5
```

### Aviso de interpretación

`valor` es un **porcentaje**: no debe sumarse entre indicadores ni entre años.
Para comparar o graficar, filtrar siempre por `indicador` y por `ambito`. El
total nacional ya viene calculado en la fila con `ambito = 'NACIONAL'`; no lo
reconstruyas sumando departamentos.

### Próximos pasos: DataWarehouse

Los cuatro DataMarts están construidos. La siguiente etapa es unirlos en un
DataWarehouse común. Puntos de enlace disponibles:

| Dimensión | Denuncias | Desaparecidas | Producción | Victimización |
|---|---|---|---|---|
| Año | `anio_registro` | `anio_registro` | `anio_registro` | `anio_registro` |
| Mes | `mes_registro` (1–12) | `mes_registro` (1–12) | `mes_registro` (1–12) | *(sin mes: anual)* |
| Departamento | `departamento` | `departamento` | — | `departamento` (`NULL` si nacional) |
| Ubigeo | `ubigeo` | `ubigeo` | — | `cod_ubicacion` (1–25 = prefijo de ubigeo) |

La unión puede hacerse por `anio_registro` (+ `mes_registro` donde exista, o
`NULL` para Victimización) y por departamento canónico.
