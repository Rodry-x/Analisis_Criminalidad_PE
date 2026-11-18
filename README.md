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
Source/                        Proyecto SSIS para Visual Studio 2026
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

## DataWarehouse `DW_ProyectoEF`

**Estado:** estructura creada, cargada por SSIS y validada.

Modelo de **constelación**: 4 tablas de hecho y dimensiones conformadas. Los
DataMarts siguen limpios y Planos; todo el modelado dimensional vive en el DW.

| Capa | Contenido |
|---|---|
| `stg` | 16 vistas que leen los 4 DataMarts y resuelven claves y reglas Lima |
| `dw` | 12 dimensiones + 4 hechos (+ `dim_poblacion`, vacía a propósito) |
| `etl` | `ControlCargaDW` |

Scripts:

- `Database/05_datawarehouse_ddl.sql` — crea la base, esquemas, tablas y vistas.
- `Database/06_dw_validacion.sql` — conteos, claves huérfanas, sumas, control
  de carga y muestra de las 5 preguntas guía.

### Hechos y dimensiones

| Hecho | Filas | Dimensiones conformadas |
|---|---:|---|
| `dw.fact_denuncias` | 378,187 | tiempo, fecha, ubigeo, modalidad |
| `dw.fact_desaparecidos` | 77,331 | tiempo, fecha, ubigeo, sexo, rango de edad, nacionalidad |
| `dw.fact_produccion` | 39,096 | tiempo, fecha, variable (con unidad), dependencia |
| `dw.fact_victimizacion` | 1,592 | tiempo, departamento, indicador |

Decisiones del modelo:

- `es_anio_parcial` se guarda **en cada hecho** (el mismo año puede ser parcial
  en un dataset y completo en otro).
- `dim_variable` incluye `unidad_medida`: nunca se suman kilos con soles.
- Regla Lima: `1501 → LIMA METROPOLITANA`, `15xx → REGION LIMA`,
  `07 → PROV. CONST. DEL CALLAO`.
- Conflicto de nombres de ubigeo entre D1 y D2: gana el nombre del Dataset 1.
- `dim_poblacion` está vacía a propósito; las medidas de tasa por habitante
  quedarán en BLANK hasta cargar la proyección del INEI.

## Proyecto SSIS — `Source/Proyecto_EF_SSIS`

**Estado:** 6 paquetes `.dtsx` válidos, ejecutados y validados con `dtexec`.

```text
Source/
  Proyecto_EF_SSIS.slnx                 Solución (abrir en Visual Studio 2026)
  Proyecto_EF_SSIS/
    Proyecto_EF_SSIS.dtproj             Proyecto SSIS (Deployment Model: Project)
    Project.params
    00_Orquestador.dtsx                 5 tareas Execute SQL en cadena (llaman a etl.sp_EjecutarPaqueteSSIS)
    10_Dimensiones.dtsx                 12 Data Flows visibles, encadenados (respeta FKs)
    20_FactDenuncias.dtsx                1 Data Flow
    30_FactDesaparecidos.dtsx            1 Data Flow
    40_FactProduccion.dtsx               1 Data Flow
    50_FactVictimizacion.dtsx            1 Data Flow
```

Cada paquete muestra en el diseñador el flujo visual:

```text
OLE DB Source (vista stg.vw_*)  ──►  OLE DB Destination (tabla dw.*)
connection manager: localhost.DW_ProyectoEF (MSOLEDBSQL, Windows Auth)
```

En `10_Dimensiones.dtsx` los 12 Data Flows están unidos por restricciones de
precedencia en este orden: `fecha → tiempo → departamento → provincia → ubigeo
→ modalidad → sexo → rango_edad → nacionalidad → variable → dependencia →
indicador`. El orden Importa porque `dim_provincia` referencia a
`dim_departamento` y `dim_ubigeo` referencia a ambos; sin las precedencias SSIS
los ejecutaría en paralelo y podría insertar un hijo antes que su padre.

### Cómo abrirlo

1. Abrir `Source/Proyecto_EF_SSIS.slnx` con **Visual Studio 2026**.
2. En el Explorador de soluciones aparece `Proyecto_EF_SSIS` y, dentro,
   los 6 paquetes.
3. Doble clic en cualquier `.dtsx` para ver el Data Flow en el lienzo.

### Cómo ejecutarlo

En orden (el orquestador hace exactamente esto en cadena):

```powershell
$dtexec = 'C:\Program Files\Microsoft SQL Server\170\DTS\Binn\DTExec.exe'
$dir    = 'Source\Proyecto_EF_SSIS'

& $dtexec /f "$dir\10_Dimensiones.dtsx"
& $dtexec /f "$dir\20_FactDenuncias.dtsx"
& $dtexec /f "$dir\30_FactDesaparecidos.dtsx"
& $dtexec /f "$dir\40_FactProduccion.dtsx"
& $dtexec /f "$dir\50_FactVictimizacion.dtsx"

sqlcmd -S localhost -E -C -f 65001 -i Database\06_dw_validacion.sql
```

O ejecutar el orquestador (un solo paquete, carga los 5 en orden):

```powershell
& $dtexec /f "$dir\00_Orquestador.dtsx"
```

El orquestador llama a `etl.sp_EjecutarPaqueteSSIS` (creado por
`Database/05_datawarehouse_ddl.sql`). Ese procedimiento habilita `xp_cmdshell`,
lanza `dtexec`, **captura su salida** y lanza un error si no aparece
`DTSER_SUCCESS`. Así, si un paquete hijo falla, el Execute SQL Task falla y las
precedencias detienen la cadena. Con `xp_cmdshell ... , no_output` el orquestador
había devuelto éxito aunque no cargara nada; eso ya no ocurre.

Requisito de entorno para el orquestador: la cuenta de servicio
`NT SERVICE\MSSQLSERVER` debe poder leer los `.dtsx`. En este equipo se concedió
con:

```powershell
$base = 'C:\Users\rodry20x\Documents\Clases-UPN\Ciclo_2026-2\BigDATA\EF_Final'
icacls "$base\Source\Proyecto_EF_SSIS" /grant 'NT SERVICE\MSSQLSERVER:(OI)(CI)(RX)'
# además de permiso de traversal (RX) en las carpetas padre hasta C:\Users\rodry20x\Documents
```

Si se ejecuta `dtexec` directamente desde PowerShell (como en el bloque anterior),
no se necesita ese permiso porque el proceso corre con el usuario actual.

> Nota: los paquetes usan carga rápida con `INSERT`. Si se vuelven a ejecutar
> sin vaciar primero los hechos, se duplican las filas. Para una recarga
> completa, ejecutar de nuevo `Database/05_datawarehouse_ddl.sql` y luego SSIS.

### Resultado de la validación

```text
D1 Denuncias       378187 = 378187   OK
D2 Desaparecidos    77331 =  77331   OK
D3 Produccion       39096 =  39096   OK
D4 Victimizacion     1592 =   1592   OK
Claves huérfanas: 0 en las 11 relaciones verificadas
Sumas: 7,614,774 / 142,374 / 2,195,845,317.1 / 36,287.6 (idénticas al origen)
```

## Siguiente etapa: SSAS y Power BI

1. Crear `ModeloProyectoEF` (tabular) sobre las tablas `dw.*`.
2. Definir medidas: total de denuncias, tasa por 100 mil habitantes
   (requiere cargar `dw.dim_poblacion`), modalidad líder, confianza PNP.
3. Conectar Power BI Desktop al modelo SSAS (Analysis Services) para que el
   informe consuma el cubo, no las tablas directamente.
