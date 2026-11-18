# Guía Paso a Paso: Construcción Manual del Modelo SSAS Tabular (`Modelo_DW_ProyectoEF`) y Medidas DAX Q1–Q5

Esta guía detalla paso a paso cómo construir manualmente el modelo semántico tabular **`Modelo_DW_ProyectoEF`** en **Visual Studio Community 2026 (`18.11.0`)** con la extensión **Microsoft Analysis Services Projects (`4.0.0`)**, conectado al Data Warehouse **`DW_ProyectoEF`** en **SQL Server 2025 (`localhost`, Autenticación de Windows)**, dejando implementadas todas las relaciones, jerarquías y medidas DAX para responder las **5 preguntas guía (Q1–Q5)** y preparado para su consumo posterior desde **Power BI Desktop**.

> **Alcance de entregables en `SSAS/`**: De acuerdo con la especificación del proyecto (`R3`), esta carpeta contiene exclusivamente documentación y código DAX (`SSAS/GUIA_SSAS_Tabular.md` y `SSAS/Medidas_DAX_ProyectoEF.dax`). No se incluyen binarios ni archivos de proyecto de Visual Studio (`.smproj`, `.bim`, `.slnx`).

---

## 1. Prerrequisitos y Configuración del Entorno SSAS (Hallazgo Local Verificado)

### 1.1 Estado verificado del entorno local
Antes de crear el proyecto tabular, ten en cuenta la configuración real detectada en este equipo (`RODRYPC`):

| Componente | Estado verificado | Impacto en el modelado |
|---|---|---|
| **SQL Server (Motor relacional)** | SQL Server 2025 RTM (`17.0.1000.7`) en `localhost`, `DW_ProyectoEF` creada y poblada | Origen listo (`12` dimensiones `dw.dim_*` + `4` hechos `dw.fact_*`) |
| **Servicio SSAS (`MSSQLServerOLAPService`)** | `SQL Server Analysis Services (MSSQLSERVER)`, versión `17.0.25.218`, puerto TCP `2383` activo, **`ServerMode = Multidimensional`** (`<DeploymentMode>0</DeploymentMode>`, `SupportedCompatibilityLevels = 1050, 1100`) | **No acepta proyectos Tabular `1600`/`1700`** mientras permanezca en modo Multidimensional |
| **Visual Studio Community 2026** | Versión `18.11.0` (`18.11.12306.390`) + extensión **Microsoft Analysis Services Projects `4.0.0`** | Incluye el motor tabular embebido **`LocalServer\msmdsrv.exe`** (`2025.0170.0039.18`) |
| **Niveles de compatibilidad soportados en VS 2026** | `1200`, `1400`, `1500`, **`1600` (SQL Server 2022)**, **`1700` (SQL Server 2025)** | Se recomienda **`1700`** (o **`1600`**) |

Debido a que `MSSQLServerOLAPService` en `localhost` corre actualmente en modo **Multidimensional**, tienes **dos opciones** según estés en fase de diseño o listo para desplegar al servidor local:

### 1.2 Opción A — Desarrollo en Visual Studio con Área de Trabajo Integrada (Recomendada durante el modelado)
Esta opción permite crear el modelo, configurar relaciones, jerarquías y validar medidas DAX sin modificar el servicio de Windows ni requerir permisos de administrador:

1. Al crear el proyecto en Visual Studio 2026, en la ventana **Diseñador de modelos tabulares**, selecciona **Área de trabajo integrada** (*Integrated Workspace*).
2. Visual Studio levantará automáticamente la instancia local embebida `LocalServer\msmdsrv.exe` (`2025.0170.0039.18`) en memoria.
3. **Advertencia**: **NO** selecciones *"Servidor de área de trabajo"* apuntando a `localhost` mientras `MSSQLServerOLAPService` siga en modo Multidimensional (`1050/1100`), ya que Visual Studio arrojará un error de incompatibilidad de modo/nivel de compatibilidad.

### 1.3 Opción B — Despliegue en el servicio SSAS de `localhost` (Cambio a modo Tabular)
Si necesitas desplegar `Modelo_DW_ProyectoEF` en la instancia `localhost` (por ejemplo, para conectarlo desde Power BI Desktop mediante *Live Connection* o consultar desde SSMS 22):

1. Abre **Bloc de notas** (o tu editor de texto) **como Administrador**.
2. Haz una copia de respaldo y abre el archivo de configuración del servicio:
   ```text
   C:\Program Files\Microsoft SQL Server\MSAS17.MSSQLSERVER\OLAP\Config\msmdsrv.ini
   ```
3. Busca la etiqueta `<DeploymentMode>` dentro de `<ConfigurationSettings>` y cambia su valor de `0` (Multidimensional) a **`2`** (Tabular):
   ```xml
   <DeploymentMode>2</DeploymentMode>
   ```
4. Guarda el archivo y reinicia el servicio **`MSSQLServerOLAPService`** desde `services.msc` (*SQL Server Analysis Services (MSSQLSERVER)* -> *Reiniciar*) o desde PowerShell ejecutado como Administrador:
   ```powershell
   Restart-Service -Name MSSQLServerOLAPService
   ```
5. Verifica la conexión desde **SQL Server Management Studio 22 (`22.10.1`)** conectándote a **Analysis Services** -> `localhost`: el ícono del servidor cambiará al ícono tabular y las propiedades mostrarán `ServerMode = Tabular` con soporte para niveles `1600` y `1700`.

> **Advertencia crítica sobre el cambio de modo**: Una instancia de SSAS solo puede ejecutar un modo a la vez. Mientras `<DeploymentMode>2</DeploymentMode>` esté activo, **cualquier base de datos Multidimensional existente en `localhost` no se cargará** (quedará inaccesible hasta restaurar `<DeploymentMode>0</DeploymentMode>` y reiniciar `MSSQLServerOLAPService`).

---

## 2. Creación del Proyecto, Origen de Datos e Importación (`DW_ProyectoEF`)

### 2.1 Crear el proyecto tabular en Visual Studio 2026
1. Abre **Visual Studio Community 2026 (`18.11.0`)**.
2. Selecciona **Crear un proyecto** (*Create a new project*).
3. Busca la plantilla **Proyecto tabular de Analysis Services** (*Analysis Services Tabular Project*) y haz clic en **Siguiente**.
4. Configura:
   - **Nombre del proyecto**: `Modelo_DW_ProyectoEF`
   - **Ubicación**: la carpeta local donde decidas trabajar el proyecto en tu entorno de desarrollo (fuera del alcance de entrega de código fuente en `SSAS/`).
5. En el cuadro **Diseñador de modelos tabulares**:
   - Selecciona **Área de trabajo integrada** (*Integrated Workspace*, Opción A) o `localhost` solo si ya aplicaste la Opción B.
   - **Nivel de compatibilidad**: selecciona **`SQL Server 2025 / Azure Analysis Services (1700)`** (alineado con SQL Server 2025 RTM local) o **`SQL Server 2022 / Azure Analysis Services (1600)`** si requieres compatibilidad con servidores 2022.
   - Haz clic en **Aceptar**.

### 2.2 Configurar la conexión a `DW_ProyectoEF` (`localhost`)
1. En el **Explorador de modelos tabulares** (*Tabular Model Explorer*), haz clic derecho en **Orígenes de datos** (*Data Sources*) -> **Importar desde el origen de datos** (*Import From Data Source*).
2. Elige **Base de datos** -> **Base de datos SQL Server** (*SQL Server database*) -> **Conectar**.
3. Ingresa los parámetros de conexión:
   - **Servidor**: `localhost` (o `.`)
   - **Base de datos**: `DW_ProyectoEF`
4. En **Credenciales / Modo de suplantación** (*Impersonation*):
   - Selecciona **Windows** (*Use my current credentials* en Power Query / Área de trabajo integrada).
   - Para el despliegue en `localhost` (Propiedades del Data Source en *Tabular Model Explorer* -> *Impersonation Mode*): configura **`ImpersonateServiceAccount`** (o **`ImpersonateAccount`** con credenciales de Windows autorizadas), asegurándote de que la cuenta del servicio SSAS (`NT Service\MSSQLServerOLAPService` o tu cuenta Windows configurada) tenga permiso `db_datareader` sobre `DW_ProyectoEF`.

### 2.3 Importar exclusivamente las 16 tablas `dw.*` (`107` columnas)
En el **Navegador** de tablas de `DW_ProyectoEF`:

1. Marca **ÚNICAMENTE** las **12 dimensiones `dw.dim_*`** y las **4 tablas de hechos `dw.fact_*`** (`16` tablas en total, `107` columnas):
   - **Dimensiones (`12`)**: `dw.dim_departamento`, `dw.dim_provincia`, `dw.dim_ubigeo`, `dw.dim_tiempo`, `dw.dim_fecha`, `dw.dim_modalidad`, `dw.dim_sexo`, `dw.dim_rango_edad`, `dw.dim_nacionalidad`, `dw.dim_variable`, `dw.dim_dependencia`, `dw.dim_indicador`.
   - **Hechos (`4`)**: `dw.fact_denuncias`, `dw.fact_desaparecidos`, `dw.fact_produccion`, `dw.fact_victimizacion`.
2. **NO importes** ninguna vista del esquema **`stg`** (`stg.vw_*`) ni la tabla de auditoría **`etl.ControlCargaDW`**.
3. Haz clic en **Transformar datos** (*Transform Data*) solo si deseas verificar que el nombre de cada tabla en el modelo quede limpio sin el prefijo `dw ` (es decir: `dim_departamento`, `dim_provincia`, `dim_ubigeo`, `dim_tiempo`, `dim_fecha`, `dim_modalidad`, `dim_sexo`, `dim_rango_edad`, `dim_nacionalidad`, `dim_variable`, `dim_dependencia`, `dim_indicador`, `fact_denuncias`, `fact_desaparecidos`, `fact_produccion`, `fact_victimizacion`), de modo que coincida exactamente con los nombres usados en el script DAX.
4. Haz clic en **Cargar** (*Load* / *Import*).

---

## 3. Configuración de Columnas: Visibilidad, Tipos, Formatos y `Sort By Column`

### 3.1 Reglas críticas de tipos de datos y formatos
Antes de ocultar claves y configurar órdenes, verifica estas cuatro reglas críticas en la cuadrícula de diseño del modelo:

1. **Precisión de 6 decimales en `fact_produccion[valor]` (`DECIMAL(18,6)`)**:
   - Debe quedar como **`Decimal Number` (`Double`)** con formato `#,##0.00` (o `#,##0.######` cuando se analicen kilos de droga).
   - **NUNCA** cambies su tipo a `Fixed Decimal Number` (`Currency`), porque ese tipo trunca/redondea a 4 decimales y alteraría cifras reales como `518,794.548573` kg o `2,195,845,317.111756`.
2. **Escala `0..100` en `fact_victimizacion[valor]` (`DECIMAL(5,1)`)**:
   - Debe quedar como **`Decimal Number` (`Double`)** con formato `0.0`.
   - Esta columna almacena puntos porcentuales en escala `0..100` (por ejemplo, `58.1` representa `58.1%`, NO `0.581`).
   - **NUNCA** apliques el formato estándar `0.0%` o `0.00%` directamente sobre `fact_victimizacion[valor]` ni sobre `AVERAGE(fact_victimizacion[valor])`, porque SSAS/Power BI multiplicaría el valor por `100` (mostrando `5810.0%`). En las medidas Q4 se usa formato literal `0.00"%"` (o `0.0"%"`) para mantener la escala numérica `0..100` consistente con SQL Server.
3. **Preservación de ceros a la izquierda en códigos geográficos**:
   - `dim_provincia[cod_provincia]` (`CHAR(4)`) y `dim_ubigeo[ubigeo]` (`CHAR(6)`) deben permanecer como **`Text` (`String`)** para preservar valores como `0101`, `010101` o `070101`.
4. **Columnas `BIT` como `True/False` (`Boolean`)**:
   - `es_anio_parcial`, `es_anual`, `es_menor_18`, `es_nacional` y `es_primer_dia_mes` se importan como `True/False` (`Boolean`), permitiendo evaluaciones limpias en DAX como `= FALSE ()` o `= TRUE ()`.

### 3.2 Inventario completo de columnas, tipos, formatos y visibilidad (`16` tablas, `107` columnas)

Marca **`Hide from Client Tools = True`** (*Ocultar de las herramientas cliente*) en las **36 columnas surrogate `id_*`** (`15` PK/FK en dimensiones + `21` PK/FK en hechos) y, de forma recomendada, en las **4 columnas técnicas `fecha_carga`**:

| Tabla | Columna | Tipo SQL | Tipo SSAS Tabular | Formato | Ocultar | Notas / Sort By |
|---|---|---|---|---|---|---|
| `dim_departamento` | `id_departamento` | `INT` | Whole Number | `0` | **Sí** | PK surrogate |
| `dim_departamento` | `cod_ubicacion` | `INT` | Whole Number | `0` | No | `0` = `NACIONAL`, `1..25`, `1501`, `1599` |
| `dim_departamento` | `departamento` | `NVARCHAR(60)` | Text | General | No | `27` valores únicos |
| `dim_departamento` | `ambito` | `NVARCHAR(15)` | Text | General | No | `'NACIONAL'` / `'DEPARTAMENTO'` |
| `dim_departamento` | `es_nacional` | `BIT` | True/False | `TRUE/FALSE` | No | `TRUE` solo en `NACIONAL` |
| `dim_departamento` | `macroregion` | `NVARCHAR(20)` | Text | General | No | `'NACIONAL'`, `'COSTA'`, `'SIERRA'`, `'SELVA'` |
| `dim_provincia` | `id_provincia` | `INT` | Whole Number | `0` | **Sí** | PK surrogate |
| `dim_provincia` | `id_departamento` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_departamento` |
| `dim_provincia` | `cod_provincia` | `CHAR(4)` | Text | General | No | Mantener `Text` (`0101`..`2504`) |
| `dim_provincia` | `provincia` | `NVARCHAR(100)` | Text | General | No | `196` provincias únicas |
| `dim_ubigeo` | `id_ubigeo` | `INT` | Whole Number | `0` | **Sí** | PK surrogate |
| `dim_ubigeo` | `id_provincia` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_provincia` |
| `dim_ubigeo` | `id_departamento` | `INT` | Whole Number | `0` | **Sí** | **NO relacionar en SSAS** |
| `dim_ubigeo` | `ubigeo` | `CHAR(6)` | Text | General | No | Mantener visible para desambiguar |
| `dim_ubigeo` | `distrito` | `NVARCHAR(120)` | Text | General | No | Nivel hoja de `Jerarquia_Geografica` |
| `dim_tiempo` | `id_tiempo` | `INT` | Whole Number | `0` | **Sí** | PK surrogate |
| `dim_tiempo` | `anio` | `SMALLINT` | Whole Number | `0` | No | `2013..2026` (sin comas) |
| `dim_tiempo` | `mes_numero` | `TINYINT` | Whole Number | `0` | No | `0` (`ANUAL`) y `1..12` |
| `dim_tiempo` | `mes_nombre` | `NVARCHAR(20)` | Text | General | No | **Sort By `mes_numero`** |
| `dim_tiempo` | `mes_corto` | `NVARCHAR(10)` | Text | General | No | **Sort By `mes_numero`** |
| `dim_tiempo` | `trimestre` | `TINYINT` | Whole Number | `0` | No | `0` (`ANUAL`) y `1..4` |
| `dim_tiempo` | `trimestre_nombre` | `NVARCHAR(10)` | Text | General | No | **Sort By `trimestre`** |
| `dim_tiempo` | `es_anual` | `BIT` | True/False | `TRUE/FALSE` | No | `TRUE` cuando `mes_numero = 0` |
| `dim_tiempo` | `periodo_label` | `NVARCHAR(15)` | Text | General | No | `YYYY-MM` o `YYYY-ANUAL` |
| `dim_fecha` | `id_fecha` | `INT` | Whole Number | `0` | **Sí** | PK surrogate |
| `dim_fecha` | `fecha` | `DATE` | Date | `yyyy-MM-dd` | No | `2013-01-01..2026-12-31` |
| `dim_fecha` | `anio` | `SMALLINT` | Whole Number | `0` | No | `2013..2026` |
| `dim_fecha` | `mes` | `TINYINT` | Whole Number | `0` | No | `1..12` |
| `dim_fecha` | `dia` | `TINYINT` | Whole Number | `0` | No | `1..31` |
| `dim_fecha` | `mes_nombre` | `NVARCHAR(20)` | Text | General | No | **Sort By `mes`** |
| `dim_fecha` | `trimestre` | `TINYINT` | Whole Number | `0` | No | `1..4` |
| `dim_fecha` | `trimestre_nombre` | `NVARCHAR(10)` | Text | General | No | **Sort By `trimestre`** |
| `dim_fecha` | `es_primer_dia_mes` | `BIT` | True/False | `TRUE/FALSE` | No | Día 1 de cada mes |
| `dim_modalidad` | `id_modalidad` | `INT` | Whole Number | `0` | **Sí** | PK surrogate |
| `dim_modalidad` | `modalidad` | `NVARCHAR(100)` | Text | General | No | `7` modalidades |
| `dim_sexo` | `id_sexo` | `INT` | Whole Number | `0` | **Sí** | PK surrogate |
| `dim_sexo` | `codigo_sexo` | `NVARCHAR(15)` | Text | General | No | `'F'`, `'M'`, `'NO INFORMADO'` |
| `dim_sexo` | `sexo_descripcion` | `NVARCHAR(30)` | Text | General | No | `'Femenino'`, `'Masculino'`, `'No informado'` |
| `dim_rango_edad` | `id_rango_edad` | `INT` | Whole Number | `0` | **Sí** | PK surrogate |
| `dim_rango_edad` | `rango_edad` | `NVARCHAR(30)` | Text | General | No | **Sort By `orden_edad`** |
| `dim_rango_edad` | `es_menor_18` | `BIT` | True/False | `TRUE/FALSE` | No | `TRUE` en `0-5`, `6-11`, `12-17` |
| `dim_rango_edad` | `orden_edad` | `TINYINT` | Whole Number | `0` | No | `1..7` |
| `dim_nacionalidad` | `id_nacionalidad` | `INT` | Whole Number | `0` | **Sí** | PK surrogate |
| `dim_nacionalidad` | `nacionalidad` | `NVARCHAR(60)` | Text | General | No | `60` valores (sentinela `'NO INDICA'`) |
| `dim_variable` | `id_variable` | `INT` | Whole Number | `0` | **Sí** | PK surrogate |
| `dim_variable` | `variable` | `NVARCHAR(100)` | Text | General | No | `18` variables |
| `dim_variable` | `unidad_medida` | `NVARCHAR(30)` | Text | General | No | `9` unidades |
| `dim_variable` | `categoria_variable` | `NVARCHAR(40)` | Text | General | No | `6` categorías |
| `dim_dependencia` | `id_dependencia` | `INT` | Whole Number | `0` | **Sí** | PK surrogate |
| `dim_dependencia` | `dependencia` | `NVARCHAR(60)` | Text | General | No | `53` dependencias |
| `dim_dependencia` | `dir_reg_fre` | `NVARCHAR(30)` | Text | General | No | `6` direcciones/regiones |
| `dim_indicador` | `id_indicador` | `INT` | Whole Number | `0` | **Sí** | PK surrogate |
| `dim_indicador` | `indicador` | `NVARCHAR(200)` | Text | General | No | `5` textos oficiales completos |
| `dim_indicador` | `indicador_corto` | `NVARCHAR(60)` | Text | General | No | `5` nombres cortos |
| `fact_denuncias` | `id_fact_denuncia` | `BIGINT` | Whole Number | `0` | **Sí** | PK surrogate |
| `fact_denuncias` | `id_tiempo` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_tiempo` |
| `fact_denuncias` | `id_fecha` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_fecha` |
| `fact_denuncias` | `id_ubigeo` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_ubigeo` |
| `fact_denuncias` | `id_modalidad` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_modalidad` |
| `fact_denuncias` | `cantidad` | `INT` | Whole Number | `#,##0` | No (o Sí si solo se exponen medidas) | Base de `[Total Denuncias]` |
| `fact_denuncias` | `es_anio_parcial` | `BIT` | True/False | `TRUE/FALSE` | No | `TRUE` en `2026` |
| `fact_denuncias` | `fecha_carga` | `DATETIME2(0)` | Date/Time | `yyyy-MM-dd HH:mm:ss` | **Sí** (rec.) | Auditoría ETL |
| `fact_desaparecidos` | `id_fact_desaparecido` | `BIGINT` | Whole Number | `0` | **Sí** | PK surrogate |
| `fact_desaparecidos` | `id_tiempo` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_tiempo` |
| `fact_desaparecidos` | `id_fecha` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_fecha` |
| `fact_desaparecidos` | `id_ubigeo` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_ubigeo` |
| `fact_desaparecidos` | `id_sexo` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_sexo` |
| `fact_desaparecidos` | `id_rango_edad` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_rango_edad` |
| `fact_desaparecidos` | `id_nacionalidad` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_nacionalidad` |
| `fact_desaparecidos` | `cantidad` | `INT` | Whole Number | `#,##0` | No (o Sí si solo medidas) | Base de `[Total Desaparecidos]` |
| `fact_desaparecidos` | `es_anio_parcial` | `BIT` | True/False | `TRUE/FALSE` | No | `0` filas parciales |
| `fact_desaparecidos` | `fecha_carga` | `DATETIME2(0)` | Date/Time | `yyyy-MM-dd HH:mm:ss` | **Sí** (rec.) | Auditoría ETL |
| `fact_produccion` | `id_fact_produccion` | `BIGINT` | Whole Number | `0` | **Sí** | PK surrogate |
| `fact_produccion` | `id_tiempo` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_tiempo` |
| `fact_produccion` | `id_fecha` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_fecha` |
| `fact_produccion` | `id_variable` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_variable` |
| `fact_produccion` | `id_dependencia` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_dependencia` |
| `fact_produccion` | `valor` | `DECIMAL(18,6)` | **Decimal Number (Double)** | `#,##0.00` | No (o Sí) | **NUNCA Fixed Decimal / Currency** |
| `fact_produccion` | `es_anio_parcial` | `BIT` | True/False | `TRUE/FALSE` | No | `TRUE` en `2026` |
| `fact_produccion` | `fecha_carga` | `DATETIME2(0)` | Date/Time | `yyyy-MM-dd HH:mm:ss` | **Sí** (rec.) | Auditoría ETL |
| `fact_victimizacion` | `id_fact_victimizacion` | `BIGINT` | Whole Number | `0` | **Sí** | PK surrogate |
| `fact_victimizacion` | `id_tiempo` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_tiempo` (`mes_numero = 0`) |
| `fact_victimizacion` | `id_departamento` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_departamento` |
| `fact_victimizacion` | `id_indicador` | `INT` | Whole Number | `0` | **Sí** | FK -> `dim_indicador` |
| `fact_victimizacion` | `ambito` | `NVARCHAR(15)` | Text | General | No | `'NACIONAL'` / `'DEPARTAMENTO'` |
| `fact_victimizacion` | `clasif` | `SMALLINT` | Whole Number | `0` | No | `0` (`NACIONAL`), `1..26` |
| `fact_victimizacion` | `valor` | `DECIMAL(5,1)` | **Decimal Number (Double)** | `0.0` | No (o Sí) | Escala `0..100`; **NO usar `0.0%`** |
| `fact_victimizacion` | `es_anio_parcial` | `BIT` | True/False | `TRUE/FALSE` | No | `TRUE` en `2013` |
| `fact_victimizacion` | `fecha_carga` | `DATETIME2(0)` | Date/Time | `yyyy-MM-dd HH:mm:ss` | **Sí** (rec.) | Auditoría ETL |

### 3.3 Configurar `Sort By Column` (Ordenar por columna)
En la vista de datos de cada tabla, selecciona la columna de etiqueta, abre el menú **Columna** (*Column*) -> **Ordenar por columna** (*Sort By Column*) y configura los **6 pares** verificados (todos con relación 1:1 sin errores):

1. `dim_tiempo[mes_nombre]` -> ordenar por **`dim_tiempo[mes_numero]`** (`ANUAL = 0`, `ENERO = 1` .. `SETIEMBRE = 9` .. `DICIEMBRE = 12`).
2. `dim_tiempo[mes_corto]` -> ordenar por **`dim_tiempo[mes_numero]`** (`ANUAL = 0`, `ENE = 1` .. `SET = 9` .. `DIC = 12`).
3. `dim_tiempo[trimestre_nombre]` -> ordenar por **`dim_tiempo[trimestre]`** (`ANUAL = 0`, `T1 = 1` .. `T4 = 4`).
4. `dim_rango_edad[rango_edad]` -> ordenar por **`dim_rango_edad[orden_edad]`** (`0-5 AÑOS = 1`, `6-11 AÑOS = 2`, `12-17 AÑOS = 3`, `18-29 AÑOS = 4`, `30-59 AÑOS = 5`, `60 A MAS AÑOS = 6`, `NO INFORMADO = 7`).
5. `dim_fecha[mes_nombre]` -> ordenar por **`dim_fecha[mes]`** (`1..12`).
6. `dim_fecha[trimestre_nombre]` -> ordenar por **`dim_fecha[trimestre]`** (`1..4`).

> **Nota sobre `dim_fecha` como tabla de fechas**: Puedes marcar `dim_fecha` como tabla de fechas (*Mark as Date Table* sobre `dim_fecha[fecha]`). No obstante, las medidas de Q1–Q5 utilizan **`dim_tiempo`** porque `fact_victimizacion` es de grano anual (`mes_numero = 0`) y solo enlaza con `dim_tiempo`.

---

## 4. Relaciones en Constelación sin Ambigüedades (`19` Relaciones Activas)

Cambia a la **Vista de diagrama** (*Diagram View*) en Visual Studio 2026. Verifica o crea manualmente las **19 relaciones activas**, todas con cardinalidad **Varios a uno (`*:1` / Many-to-One)** y dirección de filtro **Única (`Single`)** desde la tabla de dimensión hacia la tabla de hechos (o padre -> hijo en el copo de nieve):

| # | Tabla origen (Lado `Many *`) | Columna origen | Tabla destino (Lado `One 1`) | Columna destino | Cardinalidad | Dirección | Estado |
|---:|---|---|---|---|---|---|---|
| 1 | `fact_denuncias` | `id_tiempo` | `dim_tiempo` | `id_tiempo` | Many-to-One (`*:1`) | Single | Activa |
| 2 | `fact_denuncias` | `id_fecha` | `dim_fecha` | `id_fecha` | Many-to-One (`*:1`) | Single | Activa |
| 3 | `fact_denuncias` | `id_ubigeo` | `dim_ubigeo` | `id_ubigeo` | Many-to-One (`*:1`) | Single | Activa |
| 4 | `fact_denuncias` | `id_modalidad` | `dim_modalidad` | `id_modalidad` | Many-to-One (`*:1`) | Single | Activa |
| 5 | `fact_desaparecidos` | `id_tiempo` | `dim_tiempo` | `id_tiempo` | Many-to-One (`*:1`) | Single | Activa |
| 6 | `fact_desaparecidos` | `id_fecha` | `dim_fecha` | `id_fecha` | Many-to-One (`*:1`) | Single | Activa |
| 7 | `fact_desaparecidos` | `id_ubigeo` | `dim_ubigeo` | `id_ubigeo` | Many-to-One (`*:1`) | Single | Activa |
| 8 | `fact_desaparecidos` | `id_sexo` | `dim_sexo` | `id_sexo` | Many-to-One (`*:1`) | Single | Activa |
| 9 | `fact_desaparecidos` | `id_rango_edad` | `dim_rango_edad` | `id_rango_edad` | Many-to-One (`*:1`) | Single | Activa |
| 10 | `fact_desaparecidos` | `id_nacionalidad` | `dim_nacionalidad` | `id_nacionalidad` | Many-to-One (`*:1`) | Single | Activa |
| 11 | `fact_produccion` | `id_tiempo` | `dim_tiempo` | `id_tiempo` | Many-to-One (`*:1`) | Single | Activa |
| 12 | `fact_produccion` | `id_fecha` | `dim_fecha` | `id_fecha` | Many-to-One (`*:1`) | Single | Activa |
| 13 | `fact_produccion` | `id_variable` | `dim_variable` | `id_variable` | Many-to-One (`*:1`) | Single | Activa |
| 14 | `fact_produccion` | `id_dependencia` | `dim_dependencia` | `id_dependencia` | Many-to-One (`*:1`) | Single | Activa |
| 15 | `fact_victimizacion` | `id_tiempo` | `dim_tiempo` | `id_tiempo` | Many-to-One (`*:1`) | Single | Activa |
| 16 | `fact_victimizacion` | `id_departamento` | `dim_departamento` | `id_departamento` | Many-to-One (`*:1`) | Single | Activa |
| 17 | `fact_victimizacion` | `id_indicador` | `dim_indicador` | `id_indicador` | Many-to-One (`*:1`) | Single | Activa |
| 18 | `dim_ubigeo` | `id_provincia` | `dim_provincia` | `id_provincia` | Many-to-One (`*:1`) | Single | Activa |
| 19 | `dim_provincia` | `id_departamento` | `dim_departamento` | `id_departamento` | Many-to-One (`*:1`) | Single | Activa |

### Reglas críticas de desambiguación (PROHIBICIONES)
1. **NO crear ni activar `dim_ubigeo[id_departamento] -> dim_departamento[id_departamento]`**:
   - En SQL Server existe la restricción `FK_dim_ubigeo_departamento` (la FK #20), por lo que Visual Studio podría detectarla automáticamente durante la importación.
   - Si aparece en el diagrama, **elimínala** (o déjala **inactiva** con *Active = False*).
   - **Motivo**: como `dim_ubigeo -> dim_provincia -> dim_departamento` ya está activa, activar también el atajo directo crea dos caminos simultáneos hacia `dim_departamento` (ambigüedad que SSAS Tabular rechaza). En `DW_ProyectoEF` se verificó `0` discrepancias entre `dim_ubigeo[id_departamento]` y `dim_provincia[id_departamento]` en los `1,847` ubigeos, por lo que la propagación vía `dim_provincia` es 100% exacta para Q5.
2. **NO relacionar `dim_fecha` con `dim_tiempo`**:
   - `dim_fecha` tiene grano diario (`5,113` filas, `2013-01-01`..`2026-12-31`) y `dim_tiempo` tiene grano mensual + anual (`182` filas, incluyendo `mes_numero = 0` `'ANUAL'` usado por `fact_victimizacion`).
   - **Motivo**: unirlas produciría una relación varios a varios o rutas de filtro ambiguas (`fact_* -> dim_fecha -> dim_tiempo` vs `fact_* -> dim_tiempo`). Ambas tablas deben permanecer como dimensiones conformadas independientes.

---

## 5. Construcción de las 4 Jerarquías del Modelo

En SSAS Tabular, todos los niveles de una jerarquía deben residir en la **misma tabla**. En la Vista de diagrama, crea estas 4 jerarquías:

### 5.1 `Jerarquia_Geografica` (en `dim_ubigeo`)
Como `departamento` y `provincia` viven en tablas padre del copo de nieve, primero crea en `dim_ubigeo` (Vista de datos -> columna vacía a la derecha) las columnas calculadas usando `RELATED`:

```dax
departamento_geo = RELATED ( dim_departamento[departamento] )
```
```dax
provincia_geo = RELATED ( dim_provincia[provincia] )
```
*(Opcional)* Si deseas incluir el nivel de macrorregión como nivel superior adicional o atributo auxiliar:
```dax
macroregion_geo = RELATED ( dim_departamento[macroregion] )
```
*(Recomendación: oculta las columnas auxiliares `departamento_geo`, `provincia_geo` y `macroregion_geo` de las herramientas cliente una vez añadidas a la jerarquía para no duplicar campos en Power BI.)*

Luego, en Vista de diagrama sobre `dim_ubigeo`, crea la jerarquía **`Jerarquia_Geografica`** con los niveles en este orden:
1. `departamento_geo` *(o `macroregion_geo` -> `departamento_geo` si incluyes macrorregión)*
2. `provincia_geo`
3. `distrito`

> **Nota obligatoria de desambiguación en `distrito`**: En Perú existen `102` nombres de distrito repetidos entre provincias (p. ej., `SANTA ROSA` ×10) y **4 pares con nombre de distrito duplicado dentro de la misma provincia** (`080912` / `080915 KUMPIRUSHIATO`, `080911` / `080914 MEGANTONI` en La Convención; `100607` / `100608 CASTILLO GRANDE` en Leoncio Prado; `150121` / `150144 PUEBLO LIBRE` en Lima). Por ello, **mantén visible `dim_ubigeo[ubigeo]`** en la tabla para desambiguar a nivel distrital cuando sea necesario (o utiliza opcionalmente una columna calculada `distrito_ubigeo = dim_ubigeo[distrito] & " (" & dim_ubigeo[ubigeo] & ")"` como hoja alternativa).

### 5.2 `Jerarquia_Tiempo` (en `dim_tiempo`)
Crea la jerarquía **`Jerarquia_Tiempo`** en `dim_tiempo` con los niveles:
1. `anio`
2. `trimestre_nombre`
3. `mes_nombre`

> **Nota sobre la fila `ANUAL`**: `dim_tiempo` incluye una fila con `mes_numero = 0` (`mes_nombre = "ANUAL"`, `trimestre_nombre = "ANUAL"`, `es_anual = TRUE()`), utilizada exclusivamente por `fact_victimizacion`. Las tablas mensuales (`fact_denuncias`, `fact_desaparecidos`, `fact_produccion`) solo enlazan a `mes_numero` `1..12`.

### 5.3 `Jerarquia_Produccion` (en `dim_dependencia`)
Crea la jerarquía **`Jerarquia_Produccion`** en `dim_dependencia` con los niveles (`0` violaciones 1:N):
1. `dir_reg_fre` (`6` valores: `REGION`, `DIRNIC`, `DIRNOS`, `FRENTE`, `RP ICA`, `RP TUMBES`)
2. `dependencia` (`53` dependencias policiales)

### 5.4 `Jerarquia_Variable` (en `dim_variable`)
Crea la jerarquía **`Jerarquia_Variable`** en `dim_variable` con los niveles:
1. `unidad_medida`
2. `categoria_variable`
3. `variable`

> **Nota importante de cardinalidad M:N**: Entre `unidad_medida` y `categoria_variable` existe una relación **varios a varios (M:N)**: `DROGAS DECOMISADAS` aparece bajo `ENVOLTORIO`, `ENVOLTORIOS` y `KILOS`; `INCAUTACION MONETARIA` aparece bajo `SOLES` y `SOLES (VALORIZACION)`; y `UNIDADES` agrupa tanto `ARMAS INCAUTADAS` como `ESTRUCTURAS CRIMINALES`. SSAS Tabular permite construir la jerarquía sin errores, y **`unidad_medida` debe ir obligatoriamente como raíz** para evitar sumar unidades incompatibles en Q3.

---

## 6. Medidas DAX Completas por Pregunta Guía (Q1–Q5)

Todas las medidas siguientes están consolidadas en `SSAS/Medidas_DAX_ProyectoEF.dax`. Para crearlas manualmente en Visual Studio:
1. En **Vista de datos**, selecciona la **tabla destino** indicada y haz clic en cualquier celda de la **cuadrícula de medidas** (parte inferior de la tabla).
2. Pega la definición exacta `Nombre Medida := ...` en la barra de fórmulas y presiona **Enter**.
3. En la ventana **Propiedades**, asigna **Carpeta para mostrar** (*Display Folder*) y **Formato** (*Format String*).

> **Advertencia sobre literales exactos en `DW_ProyectoEF`**:
> - Mes 9 es **`"SETIEMBRE"`** (`"SET"`), no `"SEPTIEMBRE"`.
> - Sentinela en `dim_sexo` y `dim_rango_edad` es **`"NO INFORMADO"`**, pero en `dim_nacionalidad` es **`"NO INDICA"`** (`3` casos).
> - En `dim_variable`: **`"INTERVENCION EXTRAJEROS (LEY MIGRATORIA)"`** viene sin `'N'` en `EXTRAJEROS` desde el DataMart origen; `"CONTRABANDO (VALORIZACION)"` no lleva tilde.
> - En `dim_indicador`: lleva tildes (`"PORCENTAJE DE PERCEPCIÓN..."`, `"PORCENTAJE DE VICTIMIZACIÓN..."`).
> - En `dim_departamento`: **`"ANCASH"`**, **`"APURIMAC"`**, **`"HUANUCO"`**, **`"JUNIN"`**, **`"SAN MARTIN"`** y **`"REGION LIMA"`** van **sin tildes**; el Callao es **`"PROV. CONST. DEL CALLAO"`**.

---

### 6.1 Q1 — Denuncias Policiales (`2018–2025`, Tabla destino: `fact_denuncias`, Carpeta: `Q1 - Denuncias`)

Reglas aplicadas:
- Excluir `2026` mediante `fact_denuncias[es_anio_parcial] = FALSE ()` (`6,866,606` denuncias en `2018–2025`; `748,168` excluidas en `2026`).
- **Por qué no usar `DATEADD(dim_fecha[fecha], -1, YEAR)` en YoY**: `dim_fecha` no está relacionada con `dim_tiempo`; al filtrar `dim_tiempo[anio]` o `dim_tiempo[mes_nombre]`, `DATEADD` sobre `dim_fecha` deja intacto el filtro de `dim_tiempo` y devuelve el mismo año.
- **Por qué no usar `FILTER(ALL(dim_tiempo), dim_tiempo[anio] = MAX(...) - 1)`**: `ALL(dim_tiempo)` borra el mes/trimestre actual (devolviendo todo el año anterior cuando se cruza por mes), y sin validar `NOT ISBLANK([Total Denuncias])` mostraría `-100.00%` en `2026`. El patrón con `SELECTEDVALUE + VALUES + TREATAS` resuelve ambos problemas.

```dax
// Formato: #,##0
Total Denuncias :=
CALCULATE (
    SUM ( fact_denuncias[cantidad] ),
    fact_denuncias[es_anio_parcial] = FALSE ()
)
```

```dax
// Formato: #,##0
Ranking Modalidad :=
IF (
    ISINSCOPE ( dim_modalidad[modalidad] ) && NOT ISBLANK ( [Total Denuncias] ),
    RANKX (
        ALL ( dim_modalidad ),
        [Total Denuncias],
        ,
        DESC,
        SKIP
    )
)
```

```dax
// Formato: 0.00%
% Participacion Modalidad :=
DIVIDE (
    [Total Denuncias],
    CALCULATE (
        [Total Denuncias],
        ALL ( dim_modalidad )
    )
)
```

```dax
// Formato: #,##0
Denuncias Anio Anterior :=
VAR AnioActual =
    SELECTEDVALUE ( dim_tiempo[anio] )
VAR MesesActuales =
    VALUES ( dim_tiempo[mes_numero] )
VAR ValorActual =
    [Total Denuncias]
RETURN
    IF (
        NOT ISBLANK ( AnioActual ) && NOT ISBLANK ( ValorActual ),
        CALCULATE (
            [Total Denuncias],
            ALL ( dim_tiempo ),
            dim_tiempo[anio] = AnioActual - 1,
            TREATAS ( MesesActuales, dim_tiempo[mes_numero] )
        )
    )
```

```dax
// Formato: +0.00%;-0.00%;0.00%
Variacion YoY Denuncias % :=
VAR Actual =
    [Total Denuncias]
VAR Anterior =
    [Denuncias Anio Anterior]
RETURN
    IF (
        NOT ISBLANK ( Actual ) && NOT ISBLANK ( Anterior ),
        DIVIDE ( Actual - Anterior, Anterior )
    )
```

```dax
// Formato: #,##0.00
Promedio Mensual Denuncias :=
CALCULATE (
    AVERAGEX (
        VALUES ( dim_tiempo[periodo_label] ),
        [Total Denuncias]
    ),
    KEEPFILTERS ( dim_tiempo[es_anual] = FALSE () )
)
```

```dax
// Formato: 0.00%
% Estacionalidad Mensual :=
DIVIDE (
    CALCULATE (
        [Total Denuncias],
        KEEPFILTERS ( dim_tiempo[es_anual] = FALSE () )
    ),
    CALCULATE (
        [Total Denuncias],
        REMOVEFILTERS (
            dim_tiempo[mes_numero],
            dim_tiempo[mes_nombre],
            dim_tiempo[mes_corto],
            dim_tiempo[trimestre],
            dim_tiempo[trimestre_nombre],
            dim_tiempo[periodo_label]
        ),
        KEEPFILTERS ( dim_tiempo[es_anual] = FALSE () )
    )
)
```

*(Nota sobre `[Promedio Mensual Denuncias]`: al iterar `VALUES(dim_tiempo[periodo_label])` sobre `es_anual = FALSE()`, funciona de forma exacta a nivel de mes —promediando ese mes entre los 8 años completos, p. ej. `OCTUBRE = 74,922.50`—, a nivel de trimestre, a nivel de año y en el Total general de 96 meses = `71,527.15`.)*

---

### 6.2 Q2 — Personas Desaparecidas (`2019–2025`, Tabla destino: `fact_desaparecidos`, Carpeta: `Q2 - Desaparecidos`)

Reglas aplicadas:
- `fact_desaparecidos` cubre `2019–2025` (`142,374` casos, `0` filas parciales).
- Menores de 18 años (`dim_rango_edad[es_menor_18] = TRUE()`): agrupa exactamente **`'0-5 AÑOS'`** (`1,366`), **`'6-11 AÑOS'`** (`5,293`) y **`'12-17 AÑOS'`** (`74,603`) -> **`81,262` casos (`57.08%`)**.
- Valores no informados: `dim_sexo[codigo_sexo] = "NO INFORMADO"` (`90`), `dim_rango_edad[rango_edad] = "NO INFORMADO"` (`1,357`), unión sin intersección = `1,447`. Adicionalmente, `dim_nacionalidad[nacionalidad] = "NO INDICA"` aporta `3` casos disjuntos.

```dax
// Formato: #,##0
Total Desaparecidos :=
CALCULATE (
    SUM ( fact_desaparecidos[cantidad] ),
    fact_desaparecidos[es_anio_parcial] = FALSE ()
)
```

```dax
// Formato: #,##0
Total Desaparecidos Menores 18 :=
CALCULATE (
    [Total Desaparecidos],
    KEEPFILTERS ( dim_rango_edad[es_menor_18] = TRUE () )
)
```

```dax
// Formato: 0.00%
% Desaparecidos Menores 18 :=
DIVIDE (
    [Total Desaparecidos Menores 18],
    [Total Desaparecidos]
)
```

```dax
// Formato: #,##0
Desaparecidos Sexo No Informado :=
CALCULATE (
    [Total Desaparecidos],
    KEEPFILTERS ( dim_sexo[codigo_sexo] = "NO INFORMADO" )
)
```

```dax
// Formato: #,##0
Desaparecidos Edad No Informada :=
CALCULATE (
    [Total Desaparecidos],
    KEEPFILTERS ( dim_rango_edad[rango_edad] = "NO INFORMADO" )
)
```

```dax
// Formato: #,##0
Desaparecidos No Informado :=
CALCULATE (
    [Total Desaparecidos],
    FILTER (
        fact_desaparecidos,
        RELATED ( dim_sexo[codigo_sexo] ) = "NO INFORMADO"
            || RELATED ( dim_rango_edad[rango_edad] ) = "NO INFORMADO"
    )
)
```

```dax
// Formato: 0.00%
% Participacion Perfil Desaparecidos :=
DIVIDE (
    [Total Desaparecidos],
    CALCULATE (
        [Total Desaparecidos],
        ALL ( dim_sexo ),
        ALL ( dim_rango_edad )
    )
)
```

---

### 6.3 Q3 — Producción Policial (`2023–2025`, Tabla destino: `fact_produccion`, Carpeta: `Q3 - Produccion Policial`)

Reglas aplicadas:
- Excluir `2026` mediante `fact_produccion[es_anio_parcial] = FALSE ()`.
- **Prohibición crítica**: nunca crear una suma sin filtro de `unidad_medida` / `variable`.
- **Advertencia sobre `"UNIDADES"`**: la unidad `"UNIDADES"` incluye tanto armas (`ARMAS BLANCAS`, `ARMAS DE FUEGO`) como estructuras criminales (`BANDAS CRIMINALES DESARTICULADAS`, `ORGANIZACIONES CRIMINALES DESARTICULADAS`). Al explorar `[Valor Produccion Unitario]` con `unidad_medida = "UNIDADES"`, segmenta siempre también por `dim_variable[variable]` o `dim_variable[categoria_variable]`. Asimismo, `"ENVOLTORIO"` (marihuana) y `"ENVOLTORIOS"` (CC/PBC) son unidades distintas en origen, al igual que `"SOLES"` (dinero incautado) y `"SOLES (VALORIZACION)"` (contrabando).

```dax
// Formato: #,##0
Operativos Policiales :=
CALCULATE (
    SUM ( fact_produccion[valor] ),
    fact_produccion[es_anio_parcial] = FALSE (),
    KEEPFILTERS ( dim_variable[variable] = "OPERATIVOS" )
)
```

```dax
// Formato: #,##0
Total Detenidos :=
CALCULATE (
    SUM ( fact_produccion[valor] ),
    fact_produccion[es_anio_parcial] = FALSE (),
    KEEPFILTERS (
        dim_variable[variable] IN {
            "DETENIDOS DIVERSOS DELITOS (EXTRANJEROS)",
            "DETENIDOS DIVERSOS DELITOS (PERUANOS)",
            "DETENIDOS POR REQUISITORIADO"
        }
    )
)
```

```dax
// Formato: #,##0
Intervenciones Extranjeros :=
CALCULATE (
    SUM ( fact_produccion[valor] ),
    fact_produccion[es_anio_parcial] = FALSE (),
    KEEPFILTERS ( dim_variable[variable] = "INTERVENCION EXTRAJEROS (LEY MIGRATORIA)" )
)
```

```dax
// Formato: #,##0
Bandas Desarticuladas :=
CALCULATE (
    SUM ( fact_produccion[valor] ),
    fact_produccion[es_anio_parcial] = FALSE (),
    KEEPFILTERS ( dim_variable[variable] = "BANDAS CRIMINALES DESARTICULADAS" )
)
```

```dax
// Formato: #,##0
Organizaciones Criminales Desarticuladas :=
CALCULATE (
    SUM ( fact_produccion[valor] ),
    fact_produccion[es_anio_parcial] = FALSE (),
    KEEPFILTERS ( dim_variable[variable] = "ORGANIZACIONES CRIMINALES DESARTICULADAS" )
)
```

```dax
// Formato: #,##0.######
Kilos de Droga Incautada :=
CALCULATE (
    SUM ( fact_produccion[valor] ),
    fact_produccion[es_anio_parcial] = FALSE (),
    KEEPFILTERS ( dim_variable[unidad_medida] = "KILOS" )
)
```

```dax
// Formato: "S/ "#,##0.00
Dinero Incautado Soles :=
CALCULATE (
    SUM ( fact_produccion[valor] ),
    fact_produccion[es_anio_parcial] = FALSE (),
    KEEPFILTERS ( dim_variable[variable] = "DINERO INCAUTADO (SOLES)" )
)
```

```dax
// Formato: "S/ "#,##0.00
Contrabando Valorizacion Soles :=
CALCULATE (
    SUM ( fact_produccion[valor] ),
    fact_produccion[es_anio_parcial] = FALSE (),
    KEEPFILTERS ( dim_variable[variable] = "CONTRABANDO (VALORIZACION)" )
)
```

```dax
// Formato: #,##0.00
Valor Produccion Unitario :=
IF (
    HASONEVALUE ( dim_variable[unidad_medida] ),
    CALCULATE (
        SUM ( fact_produccion[valor] ),
        fact_produccion[es_anio_parcial] = FALSE ()
    ),
    BLANK ()
)
```

---

### 6.4 Q4 — Victimización y Confianza en la PNP (`2014–2024`, Tabla destino: `fact_victimizacion`, Carpeta: `Q4 - Victimizacion y Confianza`)

Reglas aplicadas:
- Excluir `2013` mediante `KEEPFILTERS ( fact_victimizacion[es_anio_parcial] = FALSE () )`.
- Filtrar únicamente registros departamentales usando `KEEPFILTERS ( dim_departamento[ambito] = "DEPARTAMENTO" )` y `KEEPFILTERS ( dim_departamento[es_nacional] = FALSE () )` (usar `KEEPFILTERS` asegura que la fila `NACIONAL` devuelva `BLANK()` en lugar de sobreescribir el contexto).
- **NUNCA sumar porcentajes**: utilizar `AVERAGE ( fact_victimizacion[valor] )`.
- **Escala `0..100` vs formato `%`**: como `valor` está en escala `0..100`, usa el formato **`0.00"%"`** (o `0.0"%"`), **NUNCA `0.00%`** (que multiplicaría `49.58` por `100` mostrando `4958.36%`).
- **Trampa `NACIONAL` en `RANKX` ascendente**: `dim_departamento` tiene `27` filas (`26` departamentos + `NACIONAL`). Como `[Confianza PNP Promedio %]` es `BLANK()` en `NACIONAL`, un `RANKX ( ALL ( dim_departamento ), ..., ASC )` colocaría a `NACIONAL` en el **puesto #1** y desplazaría a todos los departamentos a `2..27`. Filtrar la tabla de `RANKX` a `dim_departamento[ambito] = "DEPARTAMENTO" && dim_departamento[es_nacional] = FALSE ()` elimina el defecto por completo.

```dax
// Formato: 0.00"%"
Percepcion Inseguridad Promedio % :=
CALCULATE (
    AVERAGE ( fact_victimizacion[valor] ),
    KEEPFILTERS ( fact_victimizacion[es_anio_parcial] = FALSE () ),
    KEEPFILTERS ( dim_departamento[ambito] = "DEPARTAMENTO" ),
    KEEPFILTERS ( dim_departamento[es_nacional] = FALSE () ),
    dim_indicador[indicador] = "PORCENTAJE DE PERCEPCIÓN DE INSEGURIDAD AL CAMINAR SOLO(A) DE NOCHE EN SU ZONA O BARRIO"
)
```

```dax
// Formato: 0.00"%"
Confianza PNP Promedio % :=
CALCULATE (
    AVERAGE ( fact_victimizacion[valor] ),
    KEEPFILTERS ( fact_victimizacion[es_anio_parcial] = FALSE () ),
    KEEPFILTERS ( dim_departamento[ambito] = "DEPARTAMENTO" ),
    KEEPFILTERS ( dim_departamento[es_nacional] = FALSE () ),
    dim_indicador[indicador] = "PORCENTAJE DE CONFIANZA EN LA PNP"
)
```

```dax
// Formato: 0.00"%"
Victimizacion General Promedio % :=
CALCULATE (
    AVERAGE ( fact_victimizacion[valor] ),
    KEEPFILTERS ( fact_victimizacion[es_anio_parcial] = FALSE () ),
    KEEPFILTERS ( dim_departamento[ambito] = "DEPARTAMENTO" ),
    KEEPFILTERS ( dim_departamento[es_nacional] = FALSE () ),
    dim_indicador[indicador] = "PORCENTAJE DE VICTIMIZACIÓN"
)
```

```dax
// Formato: 0.00"%"
Victimizacion Robo Promedio % :=
CALCULATE (
    AVERAGE ( fact_victimizacion[valor] ),
    KEEPFILTERS ( fact_victimizacion[es_anio_parcial] = FALSE () ),
    KEEPFILTERS ( dim_departamento[ambito] = "DEPARTAMENTO" ),
    KEEPFILTERS ( dim_departamento[es_nacional] = FALSE () ),
    dim_indicador[indicador] = "PORCENTAJE DE VICTIMIZACIÓN POR EL DELITO DE ROBO E INTENTO DE ROBO DE DINERO, CARTERA Y CELULAR"
)
```

```dax
// Formato: 0.00"%"
Victimizacion Estafa Promedio % :=
CALCULATE (
    AVERAGE ( fact_victimizacion[valor] ),
    KEEPFILTERS ( fact_victimizacion[es_anio_parcial] = FALSE () ),
    KEEPFILTERS ( dim_departamento[ambito] = "DEPARTAMENTO" ),
    KEEPFILTERS ( dim_departamento[es_nacional] = FALSE () ),
    dim_indicador[indicador] = "PORCENTAJE DE VICTIMIZACIÓN POR ESTAFA"
)
```

```dax
// Formato: 0.00"%"
Indicador % Promedio :=
IF (
    HASONEVALUE ( dim_indicador[indicador] ),
    CALCULATE (
        AVERAGE ( fact_victimizacion[valor] ),
        KEEPFILTERS ( fact_victimizacion[es_anio_parcial] = FALSE () ),
        KEEPFILTERS ( dim_departamento[ambito] = "DEPARTAMENTO" ),
        KEEPFILTERS ( dim_departamento[es_nacional] = FALSE () )
    ),
    BLANK ()
)
```

```dax
// Formato: #,##0
Ranking Inseguridad Dept :=
IF (
    ISINSCOPE ( dim_departamento[departamento] )
        && NOT ISBLANK ( [Percepcion Inseguridad Promedio %] ),
    RANKX (
        FILTER (
            ALL ( dim_departamento ),
            dim_departamento[ambito] = "DEPARTAMENTO"
                && dim_departamento[es_nacional] = FALSE ()
        ),
        [Percepcion Inseguridad Promedio %],
        ,
        DESC,
        SKIP
    )
)
```

```dax
// Formato: #,##0
Ranking Menor Confianza Dept :=
IF (
    ISINSCOPE ( dim_departamento[departamento] )
        && NOT ISBLANK ( [Confianza PNP Promedio %] ),
    RANKX (
        FILTER (
            ALL ( dim_departamento ),
            dim_departamento[ambito] = "DEPARTAMENTO"
                && dim_departamento[es_nacional] = FALSE ()
        ),
        [Confianza PNP Promedio %],
        ,
        ASC,
        SKIP
    )
)
```

```dax
// Formato: 0.00"%"
Valor Nacional Referencia % :=
IF (
    HASONEVALUE ( dim_indicador[indicador] ),
    CALCULATE (
        AVERAGE ( fact_victimizacion[valor] ),
        REMOVEFILTERS ( dim_departamento ),
        dim_departamento[ambito] = "NACIONAL",
        dim_departamento[es_nacional] = TRUE (),
        KEEPFILTERS ( fact_victimizacion[es_anio_parcial] = FALSE () )
    ),
    BLANK ()
)
```

---

### 6.5 Q5 — Análisis Cruzado por Departamento y Año (`2019–2025`, Tabla destino: `fact_denuncias`, Carpeta: `Q5 - Analisis Cruzado`)

Reglas aplicadas:
- **Alineación temporal `2019–2025`**: `fact_denuncias` empieza en `2018` (`771,473`) mientras `fact_desaparecidos` empieza en `2019`. Si se dividiera `[Total Denuncias]` (`6,866,606`) entre `[Total Desaparecidos]` (`142,374`), el ratio subiría artificialmente un `+12.66%` (`48.23` vs `42.81`). Por eso `[Total Denuncias (2019-2025)]` acota explícitamente `dim_tiempo[anio] >= 2019 && dim_tiempo[anio] <= 2025` con `KEEPFILTERS` (`6,095,133`).
- **Propagación geográfica unívoca**: al segmentar por `dim_departamento[departamento]` y `dim_tiempo[anio]`, la relación única `dim_ubigeo -> dim_provincia -> dim_departamento` filtra `fact_denuncias` y `fact_desaparecidos`, mientras `fact_victimizacion` se filtra directamente por `dim_departamento`.
- **Comportamiento en `2025`**: `fact_victimizacion` solo llega hasta `2024` (`0` filas en `2025`). Por lo tanto, en matrices comparativas `2019–2025`, `[Percepcion Inseguridad Promedio %]` y `[Confianza PNP Promedio %]` devuelven **`BLANK()` en `2025`** — **NUNCA** debes envolverlas en `+ 0` ni `COALESCE(..., 0)` porque falsificaría un 0% de inseguridad o confianza.
- **Medidas reutilizadas en Q5** (ya definidas en Q2 y Q4, sin duplicar nombres en el modelo): `[Total Desaparecidos]`, `[Percepcion Inseguridad Promedio %]` y `[Confianza PNP Promedio %]`.

```dax
// Formato: #,##0
Total Denuncias (2019-2025) :=
CALCULATE (
    SUM ( fact_denuncias[cantidad] ),
    KEEPFILTERS ( fact_denuncias[es_anio_parcial] = FALSE () ),
    KEEPFILTERS ( dim_tiempo[anio] >= 2019 && dim_tiempo[anio] <= 2025 )
)
```

```dax
// Formato: #,##0.00
Denuncias vs Desaparecidos Ratio :=
DIVIDE (
    [Total Denuncias (2019-2025)],
    [Total Desaparecidos]
)
```

---

## 7. Tabla de Referencia de Verificación (Baselines Esperados en SQL Server)

Una vez creadas todas las relaciones y medidas en Visual Studio, compara tus resultados (en *Analizar en Excel* o mediante una consulta `EVALUATE` en SSMS 22) contra los valores exactos consultados en `DW_ProyectoEF`:

### 7.1 Baselines Globales Q1–Q5

| Pregunta | Medida / Segmento | Resultado esperado | Detalle de validación |
|---|---|---:|---|
| **Q1** | `[Total Denuncias]` (`2018–2025`) | **`6,866,606`** | Excluye `2026` parcial (`748,168`); bruto = `7,614,774` |
| **Q1** | Evolución YoY (`2019` .. `2025`) | `2023`: `1,042,205` (`+18.91%`) | `2018`: `771,473` (`BLANK`), `2019`: `852,706` (`+10.53%`), `2020`: `646,083` (`-24.23%`), `2021`: `754,041` (`+16.71%`), `2022`: `876,489` (`+16.24%`), `2024`: `1,017,082` (`-2.41%`), `2025`: `906,527` (`-10.87%`) |
| **Q1** | Spot-check YoY mensual (`OCTUBRE`) | `2024-10`: `82,730` (`-10.35%`) | `2023-10`: `92,280`; `2025-10`: `76,217` (`-7.87%`) |
| **Q1** | Top 3 Modalidades (`2018–2025`) | `#1 Otros` (`36.16%`) | `#1 Otros` (`2,483,096`), `#2 Violencia contra la mujer e integrantes` (`2,023,213` / `29.46%`), `#3 Hurto` (`1,367,670` / `19.92%`), `#4 Robo` (`685,218` / `9.98%`) |
| **Q1** | Estacionalidad (`2018–2025`) | Pico #1 `OCTUBRE` (`599,380`) | Promedio `OCTUBRE` = `74,922.50`; #2 `MARZO` (`599,128` / `74,891.00`); mínimo `JUNIO` (`537,108` / `67,138.50`) |
| **Q2** | `[Total Desaparecidos]` (`2019–2025`) | **`142,374`** | `0` filas parciales (`2019 = 26,331`, ..., `2025 = 20,947`) |
| **Q2** | `[Total Desaparecidos Menores 18]` | **`81,262`** (`57.08%`) | `0-5 AÑOS` (`1,366`) + `6-11 AÑOS` (`5,293`) + `12-17 AÑOS` (`74,603`) |
| **Q2** | Perfil predominante (`sexo × edad`) | **`F` + `12-17 AÑOS` (`58,891`)** | `41.36%` del total nacional; `#2 M + 12-17 AÑOS` (`15,703`) |
| **Q2** | Sentinela `NO INFORMADO` / `NO INDICA` | `90` sexo / `1,357` edad / `1,447` unión | `dim_nacionalidad[nacionalidad] = "NO INDICA"` = `3` |
| **Q3** | `[Operativos Policiales]` (`2023–2025`) | **`3,503,958`** | `REGION`: `2,834,924`; `FRENTE`: `320,575`; `DIRNOS`: `200,754`; `DIRNIC`: `94,843` |
| **Q3** | `[Total Detenidos]` (`2023–2025`) | **`1,061,639`** | Suma de 3 variables `DETENIDOS*` (`49,619 + 791,965 + 220,055`) |
| **Q3** | `[Intervenciones Extranjeros]` | **`192,712`** | Variable `"INTERVENCION EXTRAJEROS (LEY MIGRATORIA)"` |
| **Q3** | `[Bandas Desarticuladas]` / `[Org. Crim.]` | **`38,152`** / **`651`** | Ambas en `unidad_medida = "UNIDADES"` (sin mezclar con armas: `18,203 + 21,114`) |
| **Q3** | `[Kilos de Droga Incautada]` | **`518,794.548573` kg** | `CC`: `144,053.603590`; `MARIHUANA`: `236,224.022553`; `PBC`: `138,516.922430` |
| **Q3** | `[Dinero Incautado Soles]` | **`S/ 53,874,929.712`** | Unidad `"SOLES"` |
| **Q3** | `[Contrabando Valorizacion Soles]` | **`S/ 1,631,816,149.014`** | Unidad `"SOLES (VALORIZACION)"` |
| **Q4** | Promedio 26 Deptos (`2014–2024`) | Inseg: **`49.58%`** / Conf: **`19.39%`** | Victimización Gral: `23.43%`, Robo: `14.02%`, Estafa: `4.68%` (excluye `2013` y `NACIONAL`) |
| **Q4** | `[Valor Nacional Referencia %]` (`2014–2024`) | Inseg: **`54.54%`** / Conf: **`20.19%`** | En `2024`: Inseguridad `56.60%`, Confianza PNP `17.60%` |
| **Q4** | Top 3 Mayor Inseguridad (`2014–2024`) | `#1 PUNO` (`66.60%`) | `#2 MADRE DE DIOS` (`66.21%`), `#3 LIMA METROPOLITANA` (`59.86%`), `#4 TACNA` (`58.91%`), `#5 CALLAO` (`58.69%`) |
| **Q4** | Top 3 Menor Confianza PNP (`2014–2024`) | `#1 PUNO` (`6.69%`) | `#2 MADRE DE DIOS` (`10.05%`), `#3 AYACUCHO` (`11.94%`), `#4 APURIMAC` (`14.82%`), `#5 HUANUCO` (`15.42%`) |
| **Q5** | `[Total Denuncias (2019-2025)]` | **`6,095,133`** | Acotado `2019–2025` (excluye `2018` = `771,473` y `2026`) |
| **Q5** | `[Denuncias vs Desaparecidos Ratio]` | **`42.81`** (`6,095,133 / 142,374`) | Ejemplo `LIMA METROPOLITANA`: `2,121,986` den / `46,848` des = `45.30` |
| **Q5** | Año `2025` en Victimización/Confianza | **`BLANK()`** | `den_2025 = 906,527`, `des_2025 = 20,947`, `fact_victimizacion` sin filas en `2025` |

---

## 8. Procesamiento, Validación y Preparación para Power BI Desktop (Etapa Posterior)

### 8.1 Procesar y probar el modelo en Visual Studio
1. En Visual Studio, selecciona **Extensiones** -> **Modelo** -> **Procesar** -> **Procesar todo** (*Process All*) para verificar que las `16` tablas cargan exactamente las filas de `DW_ProyectoEF` sin errores de clave única ni de relación.
2. Haz clic en **Analizar en Excel** (*Analyze in Excel*) en la barra de herramientas del diseñador tabular para abrir una Tabla Dinámica conectada en vivo al Área de Trabajo Integrada y validar las cifras de la **Sección 7**.
3. Si aplicaste la Opción B (`<DeploymentMode>2</DeploymentMode>` en `localhost`), haz clic derecho en el proyecto `Modelo_DW_ProyectoEF` -> **Implementar** (*Deploy*) para publicar el cubo tabular en `localhost`, y prueba consultas `EVALUATE` desde **SSMS 22** (*Nueva consulta DAX* sobre `localhost` -> `Modelo_DW_ProyectoEF`).

### 8.2 Consumo posterior desde Power BI Desktop
Cuando se construyan los tableros en **Power BI Desktop** en la etapa siguiente, el modelo quedará listo para consumirse siguiendo estas pautas:

1. **Modo de conexión recomendado (`Live Connection` / Conexión en vivo)**:
   - En Power BI Desktop: **Obtener datos** -> **Analysis Services (SQL Server Analysis Services database)**.
   - **Servidor**: `localhost` | **Base de datos**: `Modelo_DW_ProyectoEF` | Modo: **Conectar en directo** (*Connect Live*).
   - Ventaja: Power BI reutiliza directamente la memoria VertiPaq del servidor SSAS, todas las `34` medidas DAX, formatos, carpetas `Q1`..`Q5` y las `4` jerarquías sin duplicar datos ni reescribir fórmulas.
   - *(Alternativa si se requiere modelado híbrido con fuentes externas: usar **Import** o **DirectQuery** sobre SSAS, recordando no re-agregar las medidas de porcentaje Q4).*
2. **Uso correcto de jerarquías y carpetas en los visuales**:
   - **Q1 (Denuncias)**: utiliza `Jerarquia_Tiempo` (`anio` -> `trimestre_nombre` -> `mes_nombre`) con `[Total Denuncias]`, `[Variacion YoY Denuncias %]`, `[Promedio Mensual Denuncias]` y `[% Estacionalidad Mensual]`; y `dim_modalidad[modalidad]` con `[Ranking Modalidad]` y `[% Participacion Modalidad]`.
   - **Q2 (Desaparecidos)**: matriz con `dim_sexo[codigo_sexo]` en columnas y `dim_rango_edad[rango_edad]` (ordenada por `orden_edad`) en filas, usando `[Total Desaparecidos]`, `[% Participacion Perfil Desaparecidos]` y tarjetas KPI con `[Total Desaparecidos Menores 18]` y `[% Desaparecidos Menores 18]`.
   - **Q3 (Producción)**: utiliza `Jerarquia_Produccion` (`dir_reg_fre` -> `dependencia`) en filas y `dim_tiempo[anio]` junto a las medidas específicas (`[Operativos Policiales]`, `[Total Detenidos]`, `[Bandas Desarticuladas]`, `[Kilos de Droga Incautada]`, `[Dinero Incautado Soles]`, `[Contrabando Valorizacion Soles]`), o bien `Jerarquia_Variable` empezando siempre en `unidad_medida` con `[Valor Produccion Unitario]`.
   - **Q4 (Victimización y Confianza)**: utiliza `dim_departamento[departamento]` (sin incluir `NACIONAL` en el eje gracias a `KEEPFILTERS`, pero mostrando `[Valor Nacional Referencia %]` como línea constante o columna paralela) junto a `[Percepcion Inseguridad Promedio %]`, `[Confianza PNP Promedio %]`, `[Ranking Inseguridad Dept]` y `[Ranking Menor Confianza Dept]`.
   - **Q5 (Análisis Cruzado)**: tabla o gráfico combinado por `dim_departamento[departamento]` y `dim_tiempo[anio]` (`2019–2025`) mostrando `[Total Denuncias (2019-2025)]`, `[Total Desaparecidos]`, `[Denuncias vs Desaparecidos Ratio]`, `[Percepcion Inseguridad Promedio %]` y `[Confianza PNP Promedio %]` (manteniendo `2025` en blanco para victimización/confianza).
