# Guía Paso a Paso de Construcción Manual en SSIS: `Proyecto_EF_SSIS`

Esta guía describe con precisión exacta cómo construir manualmente el proyecto ETL **`Proyecto_EF_SSIS`** en **Visual Studio Community 2026** + **SQL Server Integration Services Projects 2022+** para poblar de forma idempotente el Data Warehouse **`DW_ProyectoEF`** en **SQL Server 2025 RTM** (`localhost`, Autenticación de Windows) consumiendo las **16 vistas de staging (`stg.vw_*`)** definidas en `Database/05_datawarehouse_ddl.sql`.

> **Nota de alcance:** La carpeta `SSIS/` contiene exclusivamente esta guía manual paso a paso (sin archivos `.dtsx`, `.dtproj`, `.slnx` ni `.ispac`). El proyecto `Proyecto_EF_SSIS` debe crearse y compilarse en el directorio de soluciones elegido en Visual Studio siguiendo estas instrucciones.

---

## Tabla de Contenido

1. [Entorno Verificado, Creación del Proyecto `"Proyecto_EF_SSIS"` y Gestor de Conexión `CM_DW_ProyectoEF`](#1-entorno-verificado-creación-del-proyecto-proyecto_ef_ssis-y-gestor-de-conexión-cm_dw_proyectoef)
2. [Limpieza Previa Idempotente (`Execute SQL Task`) y Explicación de `Msg 4712`](#2-limpieza-previa-idempotente-execute-sql-task-y-explicación-de-msg-4712)
3. [Arquitectura de Paquetes (6 `.dtsx`) y Precedencia FK](#3-arquitectura-de-paquetes-6-dtsx-y-precedencia-fk)
4. [Los 16 Data Flows Limpios (`OLE DB Source` -> `OLE DB Destination`) y Mapeos Exactos Columna por Columna](#4-los-16-data-flows-limpios-ole-db-source---ole-db-destination-y-mapeos-exactos-columna-por-columna)
5. [Paquete Orquestador (`00_Orquestador.dtsx`) y Tarea `SQL - Auditoria y Validacion Post-Carga`](#5-paquete-orquestador-00_orquestadordtsx-y-tarea-sql---auditoria-y-validacion-post-carga)
6. [Compilación (`.ispac`), Ejecución (Visual Studio y `DTExec.exe`) y Verificación Post-Carga](#6-compilación-ispac-ejecución-visual-studio-y-dtexecexe-y-verificación-post-carga)

---

## 1. Entorno Verificado, Creación del Proyecto `"Proyecto_EF_SSIS"` y Gestor de Conexión `CM_DW_ProyectoEF`

### 1.1 Entorno Local Verificado

| Componente | Versión / Estado Verificado | Detalle Técnico |
|---|---|---|
| **IDE** | Visual Studio Community 2026 (`18.11.0+12306.390`) | `C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\devenv.exe` |
| **Extensión SSIS** | `SQL Server Integration Services Projects 2022+` (`17.0.1016.0`) | Manifest `Version="2.2"`, ensamblados `2025.0170.1016.00` |
| **Motor SQL Server** | SQL Server 2025 RTM (`17.0.1000.7`, X64) | Instancia local predeterminada `localhost` (`RodryPC`), Enterprise Developer Edition |
| **Autenticación y Base** | Windows Authentication / `DW_ProyectoEF` | Intercalación uniforme `Modern_Spanish_CI_AS` (codepage `1252`), `compatibility_level = 170` |
| **Servicios Windows** | `MSSQLSERVER`, `MsDtsServer170`, `SSISTELEMETRY170` | En ejecución (`Running`). No existe catálogo `SSISDB` (`DB_ID('SSISDB') IS NULL`) |

### 1.2 Creación del Proyecto `"Proyecto_EF_SSIS"`

1. Abrir **Visual Studio Community 2026** -> **Create a new project**.
2. Buscar y seleccionar la plantilla **`Integration Services Project`** (no elegir el asistente `Integration Services Project Wizard`). Hacer clic en **Next**.
3. Configurar los datos del proyecto:
   - **Project name:** `Proyecto_EF_SSIS`
   - **Location:** carpeta de trabajo de soluciones SSIS (fuera de `EF_Final\SSIS/` si deseas conservar `EF_Final\SSIS/` únicamente con documentación).
   - Clic en **Create**.
4. Verificar el **Modelo de Despliegue**:
   - El proyecto se crea por defecto en **Project Deployment Model** (el cual compila a un archivo `.ispac` en `bin\Development\Proyecto_EF_SSIS.ispac` y habilita *Project Connection Managers* y *Project Reference* en `Execute Package Task`). No cambiar a *Package Deployment Model*.
5. Configurar **`TargetServerVersion`** a **SQL Server 2025**:
   - En **Solution Explorer**, clic derecho sobre el proyecto **`Proyecto_EF_SSIS`** -> **Properties**.
   - Ir a **Configuration Properties** -> **General** -> **`TargetServerVersion`**.
   - Seleccionar **`SQL Server 2025`** (valor interno `SQLServer2025`, alineado al motor `17.0.1000.7`).
   - Hacer clic en **Apply** y **OK**. *(Hacer esto antes de diseñar los paquetes evita conversiones de formato posteriores.)*
6. **Nota obligatoria sobre Runtime de 64 bits (`Run64BitRuntime`) en Visual Studio 2026:**
   - En **Configuration Properties** -> **Debugging**, la propiedad `Run64BitRuntime` refleja la arquitectura de depuración del IDE.
   - Según la especificación oficial de la extensión SSIS (`Run64BitRuntimeDesc`: *"From Visual Studio 2022, only 64-bit SSIS runtime is supported."*), **Visual Studio 2026 ejecuta exclusivamente en runtime SSIS de 64 bits** (`DtsDebugHost.exe` en `170\Binn`). No intentes forzar depuración de 32 bits dentro de Visual Studio; si en algún escenario externo necesitases ejecutar en 32 bits, debes usar explícitamente `C:\Program Files (x86)\Microsoft SQL Server\170\DTS\Binn\DTExec.exe`.

### 1.3 Creación del Project Connection Manager `(project) CM_DW_ProyectoEF`

Al crear el gestor de conexión a nivel de proyecto, aparecerá automáticamente en el panel **Connection Managers** de los 6 paquetes como **`(project) CM_DW_ProyectoEF`**, garantizando una única definición centralizada.

1. En **Solution Explorer**, expandir `Proyecto_EF_SSIS`.
2. Clic derecho sobre la carpeta **`Connection Managers`** -> **`New Connection Manager...`**.
3. En la ventana *Add SSIS Connection Manager*, seleccionar **`OLEDB`** y hacer clic en **Add...**.
4. En *Configure OLE DB Connection Manager*, hacer clic en **New...**.
5. Configurar el proveedor OLE DB correcto para SQL Server 2025 en `localhost`:

   - **Opción recomendada — `Microsoft OLE DB Driver 19 for SQL Server` (`MSOLEDBSQL19`):**
     1. En **Provider**, seleccionar **`Microsoft OLE DB Driver 19 for SQL Server`** (`MSOLEDBSQL19`, instalado en versión `2019.0194.0001.00`).
     2. En **Server name**, escribir **`localhost`** (o `.`).
     3. En *Log on to the server*, seleccionar **`Use Windows NT Integrated Security`** (`Integrated Security=SSPI`).
     4. En *Connect to a database* -> **Select or enter a database name**, elegir **`DW_ProyectoEF`**.
     5. **Configuración TLS obligatoria para `localhost` en `MSOLEDBSQL19`:**
        - Por defecto, `MSOLEDBSQL19` impone **`Use Encryption for Data = Mandatory`** y **`Trust Server Certificate = False`**. Contra una instancia local con certificado autofirmado, hacer clic en `Test Connection` sin ajustar esta propiedad falla con el error real:
          > `SSL Provider: La cadena de certificación fue emitida por una entidad en la que no se confía.`
        - Para corregirlo, en el mismo cuadro **Connection Manager**, ir a la pestaña **`All`** (izquierda) y configurar una de estas dos propiedades válidas:
          - **Recomendado (mantiene cifrado):** **`Trust Server Certificate`** = **`True`** *(resultado verificado en `sys.dm_exec_connections`: conecta con `encrypt_option = TRUE`)*.
          - **Alternativa:** **`Use Encryption for Data`** = **`Optional`** *(conecta con `encrypt_option = FALSE`)*.

   - **Opción alternativa verificada — `Microsoft OLE DB Driver for SQL Server` (`MSOLEDBSQL` v18):**
     - Si seleccionas **`Microsoft OLE DB Driver for SQL Server`** (`MSOLEDBSQL`, versión `2018.0187.0005.00`), conecta directamente a `localhost` / `DW_ProyectoEF` con Windows Authentication sin requerir propiedades TLS adicionales.

   - **Advertencias críticas contra proveedores obsoletos o ausentes en este equipo:**
     - **NO usar `SQLNCLI11` / `SQLNCLI10` (SQL Server Native Client):** no están instalados ni registrados en el equipo; seleccionarlos o importarlos provoca error de proveedor no registrado.
     - **NO usar `SQLOLEDB` (Microsoft OLE DB Provider for SQL Server legado):** falla en vivo al conectar contra `localhost` en este entorno con el error:
       > `[DBNETLIB][ConnectionOpen (Connect()).]No existe el servidor SQL Server o se ha denegado el acceso al mismo.`

6. Hacer clic en **`Test Connection`** -> confirmar el mensaje **`Test connection succeeded.`**, luego clic en **OK** -> **OK**.
7. En **Solution Explorer** -> **`Connection Managers`**, hacer clic derecho sobre la nueva conexión -> **Rename** -> nombrarla exactamente **`CM_DW_ProyectoEF`**. *(En la ventana Properties, verificar que `Name` = `CM_DW_ProyectoEF` y `RetainSameConnection` = `False`.)*

---

## 2. Limpieza Previa Idempotente (`Execute SQL Task`) y Explicación de `Msg 4712`

Antes de ejecutar las cargas de dimensiones y hechos, el paquete orquestador **`00_Orquestador.dtsx`** ejecuta la tarea **`SQL - Limpieza Previa DW`** para garantizar **idempotencia total** (cero duplicados y claves sustitutas `IDENTITY` contiguas desde `1` en cada ejecución).

### 2.1 Propiedades de la Tarea `SQL - Limpieza Previa DW` (`Execute SQL Task`)

| Propiedad (`Execute SQL Task Editor`) | Valor Exacto | Motivo Técnico |
|---|---|---|
| **Name** | `SQL - Limpieza Previa DW` | Nombre descriptivo en `Control Flow` |
| **ConnectionType** | `OLE DB` | Usa el Project Connection Manager |
| **Connection** | `CM_DW_ProyectoEF` | Apunta a `DW_ProyectoEF` en `localhost` |
| **SQLSourceType** | `Direct input` | Código T-SQL incrustado directamente |
| **BypassPrepare** | **`True`** | **Obligatorio:** evita que `sp_prepare` intente preparar lotes multi-sentencia con `TRUNCATE`, `DELETE` y `DBCC CHECKIDENT` |
| **ResultSet** | `None` | No devuelve conjuntos de filas |

### 2.2 Código T-SQL Exacto de `SQL - Limpieza Previa DW`

Copiar y pegar exactamente el siguiente bloque T-SQL (alineado con `Database/06_dw_validacion.sql`, líneas `89–132`) en la propiedad **`SQLStatement`**:

```sql
SET NOCOUNT ON;
SET XACT_ABORT ON;

-- 1. Limpieza segura para FKs: TRUNCATE solo en hechos, DELETE en orden inverso en dims
TRUNCATE TABLE dw.fact_denuncias;
TRUNCATE TABLE dw.fact_desaparecidos;
TRUNCATE TABLE dw.fact_produccion;
TRUNCATE TABLE dw.fact_victimizacion;

DELETE FROM dw.dim_ubigeo;
DELETE FROM dw.dim_provincia;
DELETE FROM dw.dim_departamento;
DELETE FROM dw.dim_tiempo;
DELETE FROM dw.dim_fecha;
DELETE FROM dw.dim_modalidad;
DELETE FROM dw.dim_sexo;
DELETE FROM dw.dim_rango_edad;
DELETE FROM dw.dim_nacionalidad;
DELETE FROM dw.dim_variable;
DELETE FROM dw.dim_dependencia;
DELETE FROM dw.dim_indicador;

-- 2. Reseed controlado (solo si la tabla ya tuvo inserciones previas)
IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID(N'dw.dim_departamento') AND last_value IS NOT NULL)
    DBCC CHECKIDENT ('dw.dim_departamento', RESEED, 0) WITH NO_INFOMSGS;
IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID(N'dw.dim_provincia') AND last_value IS NOT NULL)
    DBCC CHECKIDENT ('dw.dim_provincia', RESEED, 0) WITH NO_INFOMSGS;
IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID(N'dw.dim_ubigeo') AND last_value IS NOT NULL)
    DBCC CHECKIDENT ('dw.dim_ubigeo', RESEED, 0) WITH NO_INFOMSGS;
IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID(N'dw.dim_tiempo') AND last_value IS NOT NULL)
    DBCC CHECKIDENT ('dw.dim_tiempo', RESEED, 0) WITH NO_INFOMSGS;
IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID(N'dw.dim_fecha') AND last_value IS NOT NULL)
    DBCC CHECKIDENT ('dw.dim_fecha', RESEED, 0) WITH NO_INFOMSGS;
IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID(N'dw.dim_modalidad') AND last_value IS NOT NULL)
    DBCC CHECKIDENT ('dw.dim_modalidad', RESEED, 0) WITH NO_INFOMSGS;
IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID(N'dw.dim_sexo') AND last_value IS NOT NULL)
    DBCC CHECKIDENT ('dw.dim_sexo', RESEED, 0) WITH NO_INFOMSGS;
IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID(N'dw.dim_rango_edad') AND last_value IS NOT NULL)
    DBCC CHECKIDENT ('dw.dim_rango_edad', RESEED, 0) WITH NO_INFOMSGS;
IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID(N'dw.dim_nacionalidad') AND last_value IS NOT NULL)
    DBCC CHECKIDENT ('dw.dim_nacionalidad', RESEED, 0) WITH NO_INFOMSGS;
IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID(N'dw.dim_variable') AND last_value IS NOT NULL)
    DBCC CHECKIDENT ('dw.dim_variable', RESEED, 0) WITH NO_INFOMSGS;
IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID(N'dw.dim_dependencia') AND last_value IS NOT NULL)
    DBCC CHECKIDENT ('dw.dim_dependencia', RESEED, 0) WITH NO_INFOMSGS;
IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID(N'dw.dim_indicador') AND last_value IS NOT NULL)
    DBCC CHECKIDENT ('dw.dim_indicador', RESEED, 0) WITH NO_INFOMSGS;
```

### 2.3 ¿Por qué falla `TRUNCATE TABLE` sobre cualquier `dw.dim_*` (`Msg 4712`) y por qué se protege `RESEED`?

1. **Explicación de `Msg 4712` en `DW_ProyectoEF`:**
   - `TRUNCATE TABLE` es una operación DDL de desasignación de páginas que no evalúa fila por fila las restricciones `FOREIGN KEY`. Por ello, SQL Server verifica los metadatos de `sys.foreign_keys` **antes de ejecutar** y rechaza `TRUNCATE TABLE` sobre **cualquier tabla referenciada por al menos una FK**, **incluso cuando las tablas hijas (`dw.fact_*`) tienen `0` filas**.
   - El error exacto del motor (`sys.messages`, `message_id = 4712`, Severidad 16) es:
     - **Inglés (`1033`):** `Cannot truncate table '%.*ls' because it is being referenced by a FOREIGN KEY constraint.`
     - **Español (`3082`):** `No se puede truncar la tabla '%1!'. Una restricción FOREIGN KEY hace referencia a ella.`
   - En `DW_ProyectoEF`, existen **20 restricciones `FOREIGN KEY`** (`NO_ACTION`) distribuidas así:

   | Tabla | Tipo | FKs Entrantes | FKs Salientes | ¿Permite `TRUNCATE TABLE`? | Acción de Limpieza |
   |---|---|---:|---:|---|---|
   | `dw.fact_denuncias` | FACT | **0** | 4 | **SÍ** (reinicia `IDENTITY` a `1`) | `TRUNCATE TABLE` |
   | `dw.fact_desaparecidos` | FACT | **0** | 6 | **SÍ** (reinicia `IDENTITY` a `1`) | `TRUNCATE TABLE` |
   | `dw.fact_produccion` | FACT | **0** | 4 | **SÍ** (reinicia `IDENTITY` a `1`) | `TRUNCATE TABLE` |
   | `dw.fact_victimizacion` | FACT | **0** | 3 | **SÍ** (reinicia `IDENTITY` a `1`) | `TRUNCATE TABLE` |
   | `dw.dim_tiempo` | DIM | **4** | 0 | **NO** (`Msg 4712`) | `DELETE` + `RESEED` |
   | `dw.dim_departamento` | DIM | **3** | 0 | **NO** (`Msg 4712`) | `DELETE` (3.º en cadena geo) + `RESEED` |
   | `dw.dim_fecha` | DIM | **3** | 0 | **NO** (`Msg 4712`) | `DELETE` + `RESEED` |
   | `dw.dim_ubigeo` | DIM | **2** | 2 | **NO** (`Msg 4712`) | `DELETE` (1.º en cadena geo) + `RESEED` |
   | `dw.dim_provincia` | DIM | **1** | 1 | **NO** (`Msg 4712`) | `DELETE` (2.º en cadena geo) + `RESEED` |
   | `dw.dim_modalidad` | DIM | **1** | 0 | **NO** (`Msg 4712`) | `DELETE` + `RESEED` |
   | `dw.dim_sexo` | DIM | **1** | 0 | **NO** (`Msg 4712`) | `DELETE` + `RESEED` |
   | `dw.dim_rango_edad` | DIM | **1** | 0 | **NO** (`Msg 4712`) | `DELETE` + `RESEED` |
   | `dw.dim_nacionalidad` | DIM | **1** | 0 | **NO** (`Msg 4712`) | `DELETE` + `RESEED` |
   | `dw.dim_variable` | DIM | **1** | 0 | **NO** (`Msg 4712`) | `DELETE` + `RESEED` |
   | `dw.dim_dependencia` | DIM | **1** | 0 | **NO** (`Msg 4712`) | `DELETE` + `RESEED` |
   | `dw.dim_indicador` | DIM | **1** | 0 | **NO** (`Msg 4712`) | `DELETE` + `RESEED` |

   - Además, dentro de las dimensiones existe jerarquía geográfica (`dim_ubigeo` -> `dim_provincia` y `dim_departamento`; `dim_provincia` -> `dim_departamento`), por lo que tras truncar las 4 `dw.fact_*`, el `DELETE` debe ejecutarse estrictamente en orden inverso: **`dw.dim_ubigeo` -> `dw.dim_provincia` -> `dw.dim_departamento`** (y luego las 9 dimensiones independientes).

2. **Por qué es obligatoria la guarda `AND last_value IS NOT NULL` en `DBCC CHECKIDENT`:**
   - `DELETE FROM` no reinicia el contador `IDENTITY`, por lo que en recargas se necesita `DBCC CHECKIDENT(..., RESEED, 0)` para que la siguiente fila vuelva a obtener `id = 1`.
   - Sin embargo, en una tabla recién creada que **nunca ha recibido inserciones** (`sys.identity_columns.last_value IS NULL`), ejecutar `DBCC CHECKIDENT(..., RESEED, 0)` establece el valor actual en `0` y provoca un **bug `off-by-one`**: el primer `INSERT` recibe **`id = 0`** en lugar de `id = 1`.
   - Al verificar `last_value IS NOT NULL`, en una tabla virgen no se ejecuta el `RESEED` (la primera fila nace con `id = 1`), mientras que en cualquier recarga posterior a `DELETE` (`last_value` ya no es `NULL`), el `RESEED, 0` reinicia correctamente la secuencia para generar `id = 1, 2, 3...`.

> **Nota sobre recarga solo de hechos (Pass 2):** Cuando las dimensiones no cambian y únicamente se desea recargar hechos (equivalente al Pass 2 de `Database/06_dw_validacion.sql`), basta ejecutar `TRUNCATE TABLE` sobre las 4 `dw.fact_*`. En el orquestador estándar de esta guía se realiza limpieza completa para garantizar idempotencia absoluta tanto de dimensiones como de hechos.

---

## 3. Arquitectura de Paquetes (6 `.dtsx`) y Precedencia FK

En **Solution Explorer** -> **`SSIS Packages`**, renombra el paquete inicial `Package.dtsx` a `00_Orquestador.dtsx` y crea los 5 paquetes adicionales (clic derecho en `SSIS Packages` -> **New SSIS Package** -> **Rename**):

| # | Paquete (`.dtsx`) | Rol en la Arquitectura | Contenido |
|---|---|---|---|
| 1 | `00_Orquestador.dtsx` | **Paquete maestro (Startup Object)** | Limpieza previa (`Execute SQL Task`) -> `10_Dimensiones` -> 4 `Execute Package Task` en paralelo -> Auditoría y validación post-carga (`Execute SQL Task`) |
| 2 | `10_Dimensiones.dtsx` | **Carga de las 12 dimensiones** | 12 *Data Flow Tasks* (`stg.vw_dim_*` -> `dw.dim_*`) respetando precedencia geográfica FK |
| 3 | `20_FactDenuncias.dtsx` | **Carga `dw.fact_denuncias`** | 1 *Data Flow Task*: `stg.vw_fact_denuncias` -> `dw.fact_denuncias` (`378,187` filas) |
| 4 | `30_FactDesaparecidos.dtsx` | **Carga `dw.fact_desaparecidos`** | 1 *Data Flow Task*: `stg.vw_fact_desaparecidos` -> `dw.fact_desaparecidos` (`77,331` filas) |
| 5 | `40_FactProduccion.dtsx` | **Carga `dw.fact_produccion`** | 1 *Data Flow Task*: `stg.vw_fact_produccion` -> `dw.fact_produccion` (`39,096` filas) |
| 6 | `50_FactVictimizacion.dtsx` | **Carga `dw.fact_victimizacion`** | 1 *Data Flow Task*: `stg.vw_fact_victimizacion` -> `dw.fact_victimizacion` (`1,592` filas) |

### 3.1 Precedencia Obligatoria en `10_Dimensiones.dtsx`

Dentro del **Control Flow** de `10_Dimensiones.dtsx`, agrega 12 **Data Flow Tasks** y configura obligatoriamente las restricciones de precedencia verdes (**`Success`**):

```text
[DFT_Dim_Departamento] ──(Success)──> [DFT_Dim_Provincia] ──(Success)──> [DFT_Dim_Ubigeo]

(En paralelo con la cadena anterior, sin dependencias entre sí):
  [DFT_Dim_Tiempo]
  [DFT_Dim_Fecha]
  [DFT_Dim_Modalidad]
  [DFT_Dim_Sexo]
  [DFT_Dim_RangoEdad]
  [DFT_Dim_Nacionalidad]
  [DFT_Dim_Variable]
  [DFT_Dim_Dependencia]
  [DFT_Dim_Indicador]
```

**Fundamento técnico en las vistas SQL de `Database/05_datawarehouse_ddl.sql`:**
- `stg.vw_dim_provincia` (líneas `818–819`) ejecuta `INNER JOIN dw.dim_departamento AS d ON d.cod_ubicacion = p.cod_ubicacion` para resolver la clave sustituta `id_departamento` (y resuelve el conflicto `1608 -> PUTUMAYO`). Si `dw.dim_departamento` no se ha cargado antes, la vista devuelve `0` filas.
- `stg.vw_dim_ubigeo` (líneas `862–863`) ejecuta `INNER JOIN dw.dim_provincia AS p ON p.cod_provincia = LEFT(u.ubigeo, 4)` para obtener tanto `id_provincia` como `id_departamento` (uniendo D1 + D2 con prioridad D1 para `010201`/`010206` e incluyendo `150144`). Si `dw.dim_provincia` no se ha cargado antes, la vista devuelve `0` filas.
- Las **9 dimensiones restantes** no consultan ninguna tabla `dw.*` en sus vistas `stg.vw_dim_*` y no tienen FKs salientes, por lo que pueden ejecutarse **en paralelo** con `MaxConcurrentExecutables = -1` (valor por defecto de SSIS).

### 3.2 Ejecución en Paralelo de los 4 Paquetes de Hechos (`20`–`50`)

- Las 4 vistas `stg.vw_fact_*` resuelven todas sus claves sustitutas (`id_tiempo`, `id_fecha`, `id_ubigeo`, `id_departamento`, `id_modalidad`, `id_sexo`, `id_rango_edad`, `id_nacionalidad`, `id_variable`, `id_dependencia`, `id_indicador`) mediante `INNER JOIN` contra las **12 tablas `dw.dim_*`**.
- Por ello, en `00_Orquestador.dtsx`, los 4 paquetes `20_FactDenuncias.dtsx`, `30_FactDesaparecidos.dtsx`, `40_FactProduccion.dtsx` y `50_FactVictimizacion.dtsx` se ejecutan **en paralelo** únicamente después de que **`EPT - 10_Dimensiones`** termine con estado **`Success`**.

---

## 4. Los 16 Data Flows Limpios (`OLE DB Source` -> `OLE DB Destination`) y Mapeos Exactos Columna por Columna

### 4.1 Configuración Estándar de Componentes en Todos los Data Flows

Cada uno de los 16 Data Flows consta únicamente de **dos componentes** conectados con la flecha azul de salida de datos: **`OLE DB Source`** -> **`OLE DB Destination`**.

#### Configuración estándar de `OLE DB Source`
1. **OLE DB connection manager:** `(project) CM_DW_ProyectoEF`
2. **Data access mode:** `Table or view`
3. **Name of the table or the view:** `[stg].[vw_<nombre>]` (según la tabla del Data Flow)
4. Pestaña **Columns:** verificar que todas las columnas disponibles de la vista estén marcadas (por defecto aparecen todas seleccionadas en el orden exacto de destino).

#### Configuración estándar de `OLE DB Destination`
1. **OLE DB connection manager:** `(project) CM_DW_ProyectoEF`
2. **Data access mode:** **`Table or view - fast load`**
3. **Name of the table or the view:** `[dw].[<nombre>]`
4. Casillas y parámetros de *Fast Load*:
   - **`Keep identity`:** **DESMARCADO** *(SQL Server genera el `IDENTITY(1,1)` automáticamente desde `1`)*.
   - **`Keep nulls`:** **DESMARCADO** *(nota técnica: en `INFORMATION_SCHEMA.COLUMNS`, las 69 columnas de `stg.vw_*` reportan `IS_NULLABLE = YES` porque SQL Server infiere nulabilidad potencial en expresiones `CAST`/`CASE`/`UNION`/`VALUES`/joins; sin embargo, las vistas garantizan **0 valores `NULL` reales** gracias a sentinelas `'NO INFORMADO'`/`'NACIONAL'`, y las tablas destino `dw.*` son `NOT NULL`. Mantener `Keep nulls` desmarcado permite aplicar valores `DEFAULT` en columnas no mapeadas como `fecha_carga` sin afectar a las 69 columnas sin nulos)*.
   - **`Table lock`:** **MARCADO** *(bloqueo `TABLOCK` optimizado para carga masiva en tablas recién limpiadas)*.
   - **`Check constraints`:** **MARCADO** *(asegura validación inmediata de las restricciones `CK_*` y `FK_*` durante el *fast load*)*.
   - **`Rows per batch`:** dejar vacío (o `50000` en hechos grandes).
   - **`Maximum insert commit size`:** **`2147483647`** *(valor por defecto; **ADVERTENCIA:** NO cambiar a `0` porque Microsoft documenta que `0` combinado con concurrencia sobre la misma tabla puede colgar/bloquear el paquete indeterminadamente)*.
5. Pestaña **Mappings:**
   - Las **69 columnas** de origen se mapean **1 a 1** por nombre exacto (`src_ordinal + 1 = dst_ordinal`).
   - Todas las columnas destino **`id_*` con `IDENTITY(1,1)`** (`16` columnas) y **`fecha_carga`** (`4` columnas con `DEFAULT (SYSDATETIME())`) deben permanecer explícitamente en **`<ignore>`** (`20` columnas en `<ignore>` en total).

### 4.2 Compatibilidad Total SQL Server <-> SSIS (Sin `Data Conversion` ni `Derived Column`)

Las 5 bases de datos en `localhost` (`DW_ProyectoEF` y los 4 DataMarts) comparten la intercalación **`Modern_Spanish_CI_AS`** (página de códigos **`1252`**), y las 16 vistas `stg.vw_*` proyectan exactamente los mismos tipos, longitudes, precisiones y escalas que las 16 tablas `dw.*` (`0` discrepancias verificadas en `sys.columns`):

| Tipo SQL Server (`stg.vw_*` y `dw.*`) | Tipo SSIS (`Data Flow`) | Uso en `DW_ProyectoEF` | ¿Requiere conversión? |
|---|---|---|---|
| `INT` | `DT_I4` (four-byte signed integer) | Claves sustitutas FK, `cod_ubicacion`, `cantidad` | No (`1:1`) |
| `SMALLINT` | `DT_I2` (two-byte signed integer) | `anio`, `clasif` | No (`1:1`) |
| `TINYINT` | `DT_UI1` (one-byte unsigned integer) | `mes_numero`, `mes`, `dia`, `trimestre`, `orden_edad` | No (`1:1`) |
| `BIT` | `DT_BOOL` (Boolean) | `es_nacional`, `es_anual`, `es_primer_dia_mes`, `es_menor_18`, `es_anio_parcial` | No (`1:1`) |
| `DATE` | `DT_DBDATE` (database date) | `fecha` en `dw.dim_fecha` | No (`1:1`) |
| `DECIMAL(18,6)` / `DECIMAL(5,1)` | `DT_NUMERIC` (`18,6` / `5,1`) | `valor` en `fact_produccion` y `fact_victimizacion` | No (`1:1`) |
| `CHAR(4)` / `CHAR(6)` | `DT_STR` (CP `1252`, long. `4`/`6`) | `cod_provincia`, `ubigeo` | No (`1:1`) |
| `NVARCHAR(n)` | `DT_WSTR` (Unicode, long. `n`) | Textos descriptivos (`10`..`200` caracteres) | No (`1:1`) |

**Totales verificados:** **16** Data Flows = **69** columnas mapeadas + **16** PK `IDENTITY(1,1)` en `<ignore>` + **4** `fecha_carga` en `<ignore>` = **89** columnas destino totales.

---

### 4.3 Tablas de Mapeo Exactas — Paquete `10_Dimensiones.dtsx` (12 Data Flows)

#### 1. `DFT_Dim_Departamento`: `[stg].[vw_dim_departamento]` -> `[dw].[dim_departamento]`
- **Orden:** 1.º en cadena geográfica (antes de `DFT_Dim_Provincia`).
- **Filas esperadas:** **`27`** (`26` departamentos/regiones + `1` sentinela `cod_ubicacion = 0`, `NACIONAL`).
- **Restricciones destino:** `PK_dim_departamento (id_departamento)`, `UQ_dim_departamento_cod_ubicacion`, `UQ_dim_departamento_departamento`, `CK_dim_departamento_ambito`, `CK_dim_departamento_macroregion`, `CK_dim_departamento_coherencia`.

| Ord. Orig. | Columna Origen (`stg.vw_dim_departamento`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.dim_departamento`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_departamento` | `INT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `cod_ubicacion` | `DT_I4` | 2 | `cod_ubicacion` | `INT` | `NOT NULL` | `UQ` -> `cod_ubicacion` |
| 2 | `departamento` | `DT_WSTR(60)` | 3 | `departamento` | `NVARCHAR(60)` | `NOT NULL` | `UQ` -> `departamento` |
| 3 | `ambito` | `DT_WSTR(15)` | 4 | `ambito` | `NVARCHAR(15)` | `NOT NULL` | `CK` -> `ambito` |
| 4 | `es_nacional` | `DT_BOOL` | 5 | `es_nacional` | `BIT` | `NOT NULL` | `CK` -> `es_nacional` |
| 5 | `macroregion` | `DT_WSTR(20)` | 6 | `macroregion` | `NVARCHAR(20)` | `NOT NULL` | `CK` -> `macroregion` |

#### 2. `DFT_Dim_Provincia`: `[stg].[vw_dim_provincia]` -> `[dw].[dim_provincia]`
- **Orden:** 2.º en cadena geográfica (después de `DFT_Dim_Departamento` y antes de `DFT_Dim_Ubigeo`).
- **Filas esperadas:** **`196`** (resuelve `1608` -> `PUTUMAYO`).
- **Restricciones destino:** `PK_dim_provincia (id_provincia)`, `FK_dim_provincia_departamento`, `UQ_dim_provincia_cod_provincia`, `CK_dim_provincia_cod ([0-9][0-9][0-9][0-9])`.

| Ord. Orig. | Columna Origen (`stg.vw_dim_provincia`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.dim_provincia`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_provincia` | `INT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `id_departamento` | `DT_I4` | 2 | `id_departamento` | `INT` | `NOT NULL` | `FK (dim_departamento)` -> `id_departamento` |
| 2 | `cod_provincia` | `DT_STR(4, 1252)` | 3 | `cod_provincia` | `CHAR(4)` | `NOT NULL` | `UQ`, `CK` -> `cod_provincia` |
| 3 | `provincia` | `DT_WSTR(100)` | 4 | `provincia` | `NVARCHAR(100)` | `NOT NULL` | `provincia -> provincia` |

#### 3. `DFT_Dim_Ubigeo`: `[stg].[vw_dim_ubigeo]` -> `[dw].[dim_ubigeo]`
- **Orden:** 3.º en cadena geográfica (después de `DFT_Dim_Provincia`).
- **Filas esperadas:** **`1,847`** (prioridad D1 para `010201`=`BAGUA` y `010206`=`LA PECA`; incluye `150144`).
- **Restricciones destino:** `PK_dim_ubigeo (id_ubigeo)`, `FK_dim_ubigeo_provincia`, `FK_dim_ubigeo_departamento`, `UQ_dim_ubigeo_ubigeo`, `CK_dim_ubigeo_ubigeo ([0-9][0-9][0-9][0-9][0-9][0-9])`.

| Ord. Orig. | Columna Origen (`stg.vw_dim_ubigeo`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.dim_ubigeo`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_ubigeo` | `INT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `id_provincia` | `DT_I4` | 2 | `id_provincia` | `INT` | `NOT NULL` | `FK (dim_provincia)` -> `id_provincia` |
| 2 | `id_departamento` | `DT_I4` | 3 | `id_departamento` | `INT` | `NOT NULL` | `FK (dim_departamento)` -> `id_departamento` |
| 3 | `ubigeo` | `DT_STR(6, 1252)` | 4 | `ubigeo` | `CHAR(6)` | `NOT NULL` | `UQ`, `CK` -> `ubigeo` |
| 4 | `distrito` | `DT_WSTR(120)` | 5 | `distrito` | `NVARCHAR(120)` | `NOT NULL` | `distrito -> distrito` |

#### 4. `DFT_Dim_Tiempo`: `[stg].[vw_dim_tiempo]` -> `[dw].[dim_tiempo]`
- **Orden:** Paralelo (independiente).
- **Filas esperadas:** **`182`** (`2013..2026` x `mes_numero 0..12`, incluyendo fila anual `mes_numero = 0`).
- **Restricciones destino:** `PK_dim_tiempo (id_tiempo)`, `UQ_dim_tiempo_anio_mes`, `CK_dim_tiempo_anio (2013..2100)`, `CK_dim_tiempo_mes (0..12)`, `CK_dim_tiempo_trimestre_coherencia`.

| Ord. Orig. | Columna Origen (`stg.vw_dim_tiempo`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.dim_tiempo`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_tiempo` | `INT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `anio` | `DT_I2` | 2 | `anio` | `SMALLINT` | `NOT NULL` | `UQ`, `CK` -> `anio` |
| 2 | `mes_numero` | `DT_UI1` | 3 | `mes_numero` | `TINYINT` | `NOT NULL` | `UQ`, `CK` -> `mes_numero` |
| 3 | `mes_nombre` | `DT_WSTR(20)` | 4 | `mes_nombre` | `NVARCHAR(20)` | `NOT NULL` | `mes_nombre -> mes_nombre` |
| 4 | `mes_corto` | `DT_WSTR(10)` | 5 | `mes_corto` | `NVARCHAR(10)` | `NOT NULL` | `mes_corto -> mes_corto` |
| 5 | `trimestre` | `DT_UI1` | 6 | `trimestre` | `TINYINT` | `NOT NULL` | `CK` -> `trimestre` |
| 6 | `trimestre_nombre` | `DT_WSTR(10)` | 7 | `trimestre_nombre` | `NVARCHAR(10)` | `NOT NULL` | `trimestre_nombre -> trimestre_nombre` |
| 7 | `es_anual` | `DT_BOOL` | 8 | `es_anual` | `BIT` | `NOT NULL` | `CK` -> `es_anual` |
| 8 | `periodo_label` | `DT_WSTR(15)` | 9 | `periodo_label` | `NVARCHAR(15)` | `NOT NULL` | `periodo_label -> periodo_label` |

#### 5. `DFT_Dim_Fecha`: `[stg].[vw_dim_fecha]` -> `[dw].[dim_fecha]`
- **Orden:** Paralelo (independiente).
- **Filas esperadas:** **`5,113`** (`2013-01-01` .. `2026-12-31` contiguo).
- **Restricciones destino:** `PK_dim_fecha (id_fecha)`, `UQ_dim_fecha_fecha`, `CK_dim_fecha_anio`, `CK_dim_fecha_mes (1..12)`, `CK_dim_fecha_dia (1..31)`, `CK_dim_fecha_trimestre (1..4)`.

| Ord. Orig. | Columna Origen (`stg.vw_dim_fecha`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.dim_fecha`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_fecha` | `INT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `fecha` | `DT_DBDATE` | 2 | `fecha` | `DATE` | `NOT NULL` | `UQ` -> `fecha` |
| 2 | `anio` | `DT_I2` | 3 | `anio` | `SMALLINT` | `NOT NULL` | `CK` -> `anio` |
| 3 | `mes` | `DT_UI1` | 4 | `mes` | `TINYINT` | `NOT NULL` | `CK` -> `mes` |
| 4 | `dia` | `DT_UI1` | 5 | `dia` | `TINYINT` | `NOT NULL` | `CK` -> `dia` |
| 5 | `mes_nombre` | `DT_WSTR(20)` | 6 | `mes_nombre` | `NVARCHAR(20)` | `NOT NULL` | `mes_nombre -> mes_nombre` |
| 6 | `trimestre` | `DT_UI1` | 7 | `trimestre` | `TINYINT` | `NOT NULL` | `CK` -> `trimestre` |
| 7 | `trimestre_nombre` | `DT_WSTR(10)` | 8 | `trimestre_nombre` | `NVARCHAR(10)` | `NOT NULL` | `trimestre_nombre -> trimestre_nombre` |
| 8 | `es_primer_dia_mes` | `DT_BOOL` | 9 | `es_primer_dia_mes` | `BIT` | `NOT NULL` | `es_primer_dia_mes -> es_primer_dia_mes` |

#### 6. `DFT_Dim_Modalidad`: `[stg].[vw_dim_modalidad]` -> `[dw].[dim_modalidad]`
- **Orden:** Paralelo (independiente). | **Filas esperadas:** **`7`** | **Restricciones:** `PK_dim_modalidad`, `UQ_dim_modalidad_modalidad`.

| Ord. Orig. | Columna Origen (`stg.vw_dim_modalidad`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.dim_modalidad`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_modalidad` | `INT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `modalidad` | `DT_WSTR(100)` | 2 | `modalidad` | `NVARCHAR(100)` | `NOT NULL` | `UQ` -> `modalidad` |

#### 7. `DFT_Dim_Sexo`: `[stg].[vw_dim_sexo]` -> `[dw].[dim_sexo]`
- **Orden:** Paralelo (independiente). | **Filas esperadas:** **`3`** (`F`, `M`, `NO INFORMADO`) | **Restricciones:** `PK_dim_sexo`, `UQ_dim_sexo_codigo`, `CK_dim_sexo_codigo`.

| Ord. Orig. | Columna Origen (`stg.vw_dim_sexo`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.dim_sexo`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_sexo` | `INT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `codigo_sexo` | `DT_WSTR(15)` | 2 | `codigo_sexo` | `NVARCHAR(15)` | `NOT NULL` | `UQ`, `CK` -> `codigo_sexo` |
| 2 | `sexo_descripcion` | `DT_WSTR(30)` | 3 | `sexo_descripcion` | `NVARCHAR(30)` | `NOT NULL` | `sexo_descripcion -> sexo_descripcion` |

#### 8. `DFT_Dim_RangoEdad`: `[stg].[vw_dim_rango_edad]` -> `[dw].[dim_rango_edad]`
- **Orden:** Paralelo (independiente). | **Filas esperadas:** **`7`** (`0-5 AÑOS` .. `NO INFORMADO`) | **Restricciones:** `PK_dim_rango_edad`, `UQ_dim_rango_edad_rango`, `UQ_dim_rango_edad_orden`, `CK_dim_rango_edad_orden (1..7)`.

| Ord. Orig. | Columna Origen (`stg.vw_dim_rango_edad`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.dim_rango_edad`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_rango_edad` | `INT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `rango_edad` | `DT_WSTR(30)` | 2 | `rango_edad` | `NVARCHAR(30)` | `NOT NULL` | `UQ` -> `rango_edad` |
| 2 | `es_menor_18` | `DT_BOOL` | 3 | `es_menor_18` | `BIT` | `NOT NULL` | `es_menor_18 -> es_menor_18` |
| 3 | `orden_edad` | `DT_UI1` | 4 | `orden_edad` | `TINYINT` | `NOT NULL` | `UQ`, `CK` -> `orden_edad` |

#### 9. `DFT_Dim_Nacionalidad`: `[stg].[vw_dim_nacionalidad]` -> `[dw].[dim_nacionalidad]`
- **Orden:** Paralelo (independiente). | **Filas esperadas:** **`60`** | **Restricciones:** `PK_dim_nacionalidad`, `UQ_dim_nacionalidad_nacionalidad`.

| Ord. Orig. | Columna Origen (`stg.vw_dim_nacionalidad`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.dim_nacionalidad`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_nacionalidad` | `INT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `nacionalidad` | `DT_WSTR(60)` | 2 | `nacionalidad` | `NVARCHAR(60)` | `NOT NULL` | `UQ` -> `nacionalidad` |

#### 10. `DFT_Dim_Variable`: `[stg].[vw_dim_variable]` -> `[dw].[dim_variable]`
- **Orden:** Paralelo (independiente). | **Filas esperadas:** **`18`** (`9` `unidad_medida` distintas) | **Restricciones:** `PK_dim_variable`, `UQ_dim_variable_variable`, `IX_dim_variable_unidad`.

| Ord. Orig. | Columna Origen (`stg.vw_dim_variable`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.dim_variable`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_variable` | `INT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `variable` | `DT_WSTR(100)` | 2 | `variable` | `NVARCHAR(100)` | `NOT NULL` | `UQ` -> `variable` |
| 2 | `unidad_medida` | `DT_WSTR(30)` | 3 | `unidad_medida` | `NVARCHAR(30)` | `NOT NULL` | `unidad_medida -> unidad_medida` |
| 3 | `categoria_variable` | `DT_WSTR(40)` | 4 | `categoria_variable` | `NVARCHAR(40)` | `NOT NULL` | `categoria_variable -> categoria_variable` |

#### 11. `DFT_Dim_Dependencia`: `[stg].[vw_dim_dependencia]` -> `[dw].[dim_dependencia]`
- **Orden:** Paralelo (independiente). | **Filas esperadas:** **`53`** (`6` `dir_reg_fre` distintas) | **Restricciones:** `PK_dim_dependencia`, `UQ_dim_dependencia_dependencia`, `IX_dim_dependencia_dir_reg_fre`.

| Ord. Orig. | Columna Origen (`stg.vw_dim_dependencia`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.dim_dependencia`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_dependencia` | `INT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `dependencia` | `DT_WSTR(60)` | 2 | `dependencia` | `NVARCHAR(60)` | `NOT NULL` | `UQ` -> `dependencia` |
| 2 | `dir_reg_fre` | `DT_WSTR(30)` | 3 | `dir_reg_fre` | `NVARCHAR(30)` | `NOT NULL` | `dir_reg_fre -> dir_reg_fre` |

#### 12. `DFT_Dim_Indicador`: `[stg].[vw_dim_indicador]` -> `[dw].[dim_indicador]`
- **Orden:** Paralelo (independiente). | **Filas esperadas:** **`5`** | **Restricciones:** `PK_dim_indicador`, `UQ_dim_indicador_indicador`, `UQ_dim_indicador_indicador_corto`.

| Ord. Orig. | Columna Origen (`stg.vw_dim_indicador`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.dim_indicador`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_indicador` | `INT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `indicador` | `DT_WSTR(200)` | 2 | `indicador` | `NVARCHAR(200)` | `NOT NULL` | `UQ` -> `indicador` |
| 2 | `indicador_corto` | `DT_WSTR(60)` | 3 | `indicador_corto` | `NVARCHAR(60)` | `NOT NULL` | `UQ` -> `indicador_corto` |

---

### 4.4 Tablas de Mapeo Exactas — Paquetes de Hechos `20` a `50` (4 Data Flows)

#### 13. Paquete `20_FactDenuncias.dtsx` — `DFT_Fact_Denuncias`: `[stg].[vw_fact_denuncias]` -> `[dw].[fact_denuncias]`
- **Filas esperadas:** **`378,187`** (`SUM(cantidad) = 7,614,774`; `37,683` filas de 2026 con `es_anio_parcial = 1`).
- **Restricciones:** `PK_fact_denuncias`, `FK_fact_denuncias_tiempo`, `FK_fact_denuncias_fecha`, `FK_fact_denuncias_ubigeo`, `FK_fact_denuncias_modalidad`, `CK_fact_denuncias_cantidad (cantidad >= 0)`, `UX_fact_denuncias_grano (id_tiempo, id_ubigeo, id_modalidad)`, `DF_fact_denuncias_fecha_carga`.

| Ord. Orig. | Columna Origen (`stg.vw_fact_denuncias`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.fact_denuncias`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_fact_denuncia` | `BIGINT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `id_tiempo` | `DT_I4` | 2 | `id_tiempo` | `INT` | `NOT NULL` | `FK (dim_tiempo)`, `UX` -> `id_tiempo` |
| 2 | `id_fecha` | `DT_I4` | 3 | `id_fecha` | `INT` | `NOT NULL` | `FK (dim_fecha)` -> `id_fecha` |
| 3 | `id_ubigeo` | `DT_I4` | 4 | `id_ubigeo` | `INT` | `NOT NULL` | `FK (dim_ubigeo)`, `UX` -> `id_ubigeo` |
| 4 | `id_modalidad` | `DT_I4` | 5 | `id_modalidad` | `INT` | `NOT NULL` | `FK (dim_modalidad)`, `UX` -> `id_modalidad` |
| 5 | `cantidad` | `DT_I4` | 6 | `cantidad` | `INT` | `NOT NULL` | `CK (>= 0)` -> `cantidad` |
| 6 | `es_anio_parcial` | `DT_BOOL` | 7 | `es_anio_parcial` | `BIT` | `NOT NULL` | `es_anio_parcial -> es_anio_parcial` |
| — | *(no existe en vista)* | — | 8 | `fecha_carga` | `DATETIME2(0)` | `NOT NULL` | `DEFAULT (SYSDATETIME())` -> **`<ignore>`** |

#### 14. Paquete `30_FactDesaparecidos.dtsx` — `DFT_Fact_Desaparecidos`: `[stg].[vw_fact_desaparecidos]` -> `[dw].[fact_desaparecidos]`
- **Filas esperadas:** **`77,331`** (`SUM(cantidad) = 142,374`; `0` filas con `es_anio_parcial = 1`; `37,611` filas / `81,262` casos `es_menor_18 = 1`).
- **Restricciones:** `PK_fact_desaparecidos`, `FK_fact_desaparecidos_tiempo`, `FK_fact_desaparecidos_fecha`, `FK_fact_desaparecidos_ubigeo`, `FK_fact_desaparecidos_sexo`, `FK_fact_desaparecidos_rango_edad`, `FK_fact_desaparecidos_nacionalidad`, `CK_fact_desaparecidos_cantidad (cantidad >= 0)`, `UX_fact_desaparecidos_grano (id_tiempo, id_ubigeo, id_sexo, id_rango_edad, id_nacionalidad)`, `DF_fact_desaparecidos_fecha_carga`.

| Ord. Orig. | Columna Origen (`stg.vw_fact_desaparecidos`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.fact_desaparecidos`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_fact_desaparecido` | `BIGINT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `id_tiempo` | `DT_I4` | 2 | `id_tiempo` | `INT` | `NOT NULL` | `FK (dim_tiempo)`, `UX` -> `id_tiempo` |
| 2 | `id_fecha` | `DT_I4` | 3 | `id_fecha` | `INT` | `NOT NULL` | `FK (dim_fecha)` -> `id_fecha` |
| 3 | `id_ubigeo` | `DT_I4` | 4 | `id_ubigeo` | `INT` | `NOT NULL` | `FK (dim_ubigeo)`, `UX` -> `id_ubigeo` |
| 4 | `id_sexo` | `DT_I4` | 5 | `id_sexo` | `INT` | `NOT NULL` | `FK (dim_sexo)`, `UX` -> `id_sexo` |
| 5 | `id_rango_edad` | `DT_I4` | 6 | `id_rango_edad` | `INT` | `NOT NULL` | `FK (dim_rango_edad)`, `UX` -> `id_rango_edad` |
| 6 | `id_nacionalidad` | `DT_I4` | 7 | `id_nacionalidad` | `INT` | `NOT NULL` | `FK (dim_nacionalidad)`, `UX` -> `id_nacionalidad` |
| 7 | `cantidad` | `DT_I4` | 8 | `cantidad` | `INT` | `NOT NULL` | `CK (>= 0)` -> `cantidad` |
| 8 | `es_anio_parcial` | `DT_BOOL` | 9 | `es_anio_parcial` | `BIT` | `NOT NULL` | `es_anio_parcial -> es_anio_parcial` |
| — | *(no existe en vista)* | — | 10 | `fecha_carga` | `DATETIME2(0)` | `NOT NULL` | `DEFAULT (SYSDATETIME())` -> **`<ignore>`** |

#### 15. Paquete `40_FactProduccion.dtsx` — `DFT_Fact_Produccion`: `[stg].[vw_fact_produccion]` -> `[dw].[fact_produccion]`
- **Filas esperadas:** **`39,096`** (`15,458` con `valor = 0`; `SUM(valor) = 2,195,845,317.111756`; `8,640` filas de 2026 con `es_anio_parcial = 1`).
- **Restricciones:** `PK_fact_produccion`, `FK_fact_produccion_tiempo`, `FK_fact_produccion_fecha`, `FK_fact_produccion_variable`, `FK_fact_produccion_dependencia`, `CK_fact_produccion_valor (valor >= 0)`, `UX_fact_produccion_grano (id_tiempo, id_variable, id_dependencia)`, `DF_fact_produccion_fecha_carga`.

| Ord. Orig. | Columna Origen (`stg.vw_fact_produccion`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.fact_produccion`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_fact_produccion` | `BIGINT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `id_tiempo` | `DT_I4` | 2 | `id_tiempo` | `INT` | `NOT NULL` | `FK (dim_tiempo)`, `UX` -> `id_tiempo` |
| 2 | `id_fecha` | `DT_I4` | 3 | `id_fecha` | `INT` | `NOT NULL` | `FK (dim_fecha)` -> `id_fecha` |
| 3 | `id_variable` | `DT_I4` | 4 | `id_variable` | `INT` | `NOT NULL` | `FK (dim_variable)`, `UX` -> `id_variable` |
| 4 | `id_dependencia` | `DT_I4` | 5 | `id_dependencia` | `INT` | `NOT NULL` | `FK (dim_dependencia)`, `UX` -> `id_dependencia` |
| 5 | `valor` | `DT_NUMERIC(18,6)` | 6 | `valor` | `DECIMAL(18,6)` | `NOT NULL` | `CK (>= 0)` -> `valor` |
| 6 | `es_anio_parcial` | `DT_BOOL` | 7 | `es_anio_parcial` | `BIT` | `NOT NULL` | `es_anio_parcial -> es_anio_parcial` |
| — | *(no existe en vista)* | — | 8 | `fecha_carga` | `DATETIME2(0)` | `NOT NULL` | `DEFAULT (SYSDATETIME())` -> **`<ignore>`** |

#### 16. Paquete `50_FactVictimizacion.dtsx` — `DFT_Fact_Victimizacion`: `[stg].[vw_fact_victimizacion]` -> `[dw].[fact_victimizacion]`
- **Filas esperadas:** **`1,592`** (`SUM(valor) = 36,287.6`; `58` filas `NACIONAL`; `107` filas de 2013 con `es_anio_parcial = 1`; `1,430` filas `DEPARTAMENTO` 2014–2024).
- **Restricciones:** `PK_fact_victimizacion`, `FK_fact_victimizacion_tiempo`, `FK_fact_victimizacion_departamento`, `FK_fact_victimizacion_indicador`, `CK_fact_victimizacion_ambito ('NACIONAL','DEPARTAMENTO')`, `CK_fact_victimizacion_clasif (0..100)`, `CK_fact_victimizacion_valor (0..100)`, `UX_fact_victimizacion_grano (id_tiempo, id_departamento, id_indicador)`, `DF_fact_victimizacion_fecha_carga`.

| Ord. Orig. | Columna Origen (`stg.vw_fact_victimizacion`) | Tipo SSIS | Ord. Dest. | Columna Destino (`dw.fact_victimizacion`) | Tipo SQL Exacto | Nulab. Dest. | Restricciones / Mapeo SSIS |
|---:|---|---|---:|---|---|---|---|
| — | *(no existe en vista)* | — | 1 | `id_fact_victimizacion` | `BIGINT` | `NOT NULL` | `PK`, `IDENTITY(1,1)` -> **`<ignore>`** |
| 1 | `id_tiempo` | `DT_I4` | 2 | `id_tiempo` | `INT` | `NOT NULL` | `FK (dim_tiempo)`, `UX` -> `id_tiempo` |
| 2 | `id_departamento` | `DT_I4` | 3 | `id_departamento` | `INT` | `NOT NULL` | `FK (dim_departamento)`, `UX` -> `id_departamento` |
| 3 | `id_indicador` | `DT_I4` | 4 | `id_indicador` | `INT` | `NOT NULL` | `FK (dim_indicador)`, `UX` -> `id_indicador` |
| 4 | `ambito` | `DT_WSTR(15)` | 5 | `ambito` | `NVARCHAR(15)` | `NOT NULL` | `CK` -> `ambito` |
| 5 | `clasif` | `DT_I2` | 6 | `clasif` | `SMALLINT` | `NOT NULL` | `CK (0..100)` -> `clasif` |
| 6 | `valor` | `DT_NUMERIC(5,1)` | 7 | `valor` | `DECIMAL(5,1)` | `NOT NULL` | `CK (0..100)` -> `valor` |
| 7 | `es_anio_parcial` | `DT_BOOL` | 8 | `es_anio_parcial` | `BIT` | `NOT NULL` | `es_anio_parcial -> es_anio_parcial` |
| — | *(no existe en vista)* | — | 9 | `fecha_carga` | `DATETIME2(0)` | `NOT NULL` | `DEFAULT (SYSDATETIME())` -> **`<ignore>`** |

---

## 5. Paquete Orquestador (`00_Orquestador.dtsx`) y Tarea `SQL - Auditoria y Validacion Post-Carga`

### 5.1 Flujo de Control (`Control Flow`) de `00_Orquestador.dtsx`

Configurar la propiedad del paquete `00_Orquestador.dtsx` **`MaxConcurrentExecutables = -1`** (valor por defecto: permite hasta `procesadores lógicos + 2` tareas concurrentes, habilitando el paralelismo de los 4 paquetes de hechos).

Disponer las **7 tareas** en el *Control Flow* conectadas exclusivamente con restricciones de precedencia verdes (**`Value = Success`**, `Logical AND`):

```text
                [SQL - Limpieza Previa DW]  (Execute SQL Task)
                            │
                        (Success)
                            ▼
                 [EPT - 10_Dimensiones]     (Execute Package Task)
           ┌───────────┬────┴────┬───────────────┐
       (Success)   (Success) (Success)       (Success)
           ▼           ▼         ▼               ▼
  [EPT - 20_     [EPT - 30_   [EPT - 40_     [EPT - 50_
  FactDenuncias] FactDesapar] FactProducc]   FactVictimiz]
           │           │         │               │
       (Success)   (Success) (Success)       (Success)
           └───────────┴────┬────┴───────────────┘
                            ▼
          [SQL - Auditoria y Validacion Post-Carga]  (Execute SQL Task)
```

### 5.2 Configuración Exacta de los 5 `Execute Package Task`

En cada uno de los 5 `Execute Package Task`, abrir **Edit...** -> pestaña **Package** y establecer exactamente:

| Nombre de Tarea en `00_Orquestador.dtsx` | `ReferenceType` | `PackageNameFromProjectReference` | `ExecuteOutOfProcess` |
|---|---|---|---|
| `EPT - 10_Dimensiones` | `Project Reference` | `10_Dimensiones.dtsx` | `False` |
| `EPT - 20_FactDenuncias` | `Project Reference` | `20_FactDenuncias.dtsx` | `False` |
| `EPT - 30_FactDesaparecidos` | `Project Reference` | `30_FactDesaparecidos.dtsx` | `False` |
| `EPT - 40_FactProduccion` | `Project Reference` | `40_FactProduccion.dtsx` | `False` |
| `EPT - 50_FactVictimizacion` | `Project Reference` | `50_FactVictimizacion.dtsx` | `False` |

> **Nota:** `ReferenceType = Project Reference` (`UseProjectReference = True`) es válido únicamente en **Project Deployment Model** y exige haber compilado el `.ispac` antes de ejecutar `00_Orquestador.dtsx`.

### 5.3 Configuración y SQL Completo de `SQL - Auditoria y Validacion Post-Carga`

| Propiedad (`Execute SQL Task Editor`) | Valor Exacto |
|---|---|
| **Name** | `SQL - Auditoria y Validacion Post-Carga` |
| **ConnectionType** | `OLE DB` |
| **Connection** | `CM_DW_ProyectoEF` |
| **SQLSourceType** | `Direct input` |
| **BypassPrepare** | **`True`** |
| **ResultSet** | `None` |

Copiar y pegar el siguiente bloque T-SQL completo en **`SQLStatement`**. Registra el lote en `etl.ControlCargaDW` (`EN_PROCESO` -> `EXITOSO` o `FALLIDO` tras `ROLLBACK` en `CATCH`, manteniendo trazabilidad ante fallos) y ejecuta exactamente las validaciones de `Database/06_dw_validacion.sql` (`THROW 51000..51017`):

```sql
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;

DECLARE @id_carga INT;
DECLARE @detalle  NVARCHAR(MAX);

INSERT INTO etl.ControlCargaDW (
    proceso, origen, tabla_destino, filas_origen, filas_cargadas, claves_huerfanas, control_suma, estado, detalle
)
VALUES (
    N'SSIS_00_Orquestador',
    N'stg.vw_* (D1-D4)',
    N'DW_ProyectoEF (12 dim + 4 fact)',
    NULL,
    0,
    0,
    NULL,
    N'EN_PROCESO',
    N'Inicio de auditoria y validacion post-carga desde Proyecto_EF_SSIS.'
);
SET @id_carga = CAST(SCOPE_IDENTITY() AS INT);

BEGIN TRY
    -- 1. Conteos exactos de las 12 dimensiones (THROW 51000)
    DECLARE @cnt_dim_depto INT = (SELECT COUNT(*) FROM dw.dim_departamento);
    DECLARE @cnt_dim_prov  INT = (SELECT COUNT(*) FROM dw.dim_provincia);
    DECLARE @cnt_dim_ubig  INT = (SELECT COUNT(*) FROM dw.dim_ubigeo);
    DECLARE @cnt_dim_tiem  INT = (SELECT COUNT(*) FROM dw.dim_tiempo);
    DECLARE @cnt_dim_fech  INT = (SELECT COUNT(*) FROM dw.dim_fecha);
    DECLARE @cnt_dim_mod   INT = (SELECT COUNT(*) FROM dw.dim_modalidad);
    DECLARE @cnt_dim_sexo  INT = (SELECT COUNT(*) FROM dw.dim_sexo);
    DECLARE @cnt_dim_edad  INT = (SELECT COUNT(*) FROM dw.dim_rango_edad);
    DECLARE @cnt_dim_nac   INT = (SELECT COUNT(*) FROM dw.dim_nacionalidad);
    DECLARE @cnt_dim_var   INT = (SELECT COUNT(*) FROM dw.dim_variable);
    DECLARE @cnt_dim_dep   INT = (SELECT COUNT(*) FROM dw.dim_dependencia);
    DECLARE @cnt_dim_ind   INT = (SELECT COUNT(*) FROM dw.dim_indicador);

    IF @cnt_dim_depto <> 27   THROW 51000, N'Validacion fallida: dw.dim_departamento debe tener 27 filas.', 1;
    IF @cnt_dim_prov  <> 196  THROW 51000, N'Validacion fallida: dw.dim_provincia debe tener 196 filas.', 1;
    IF @cnt_dim_ubig  <> 1847 THROW 51000, N'Validacion fallida: dw.dim_ubigeo debe tener 1847 filas.', 1;
    IF @cnt_dim_tiem  <> 182  THROW 51000, N'Validacion fallida: dw.dim_tiempo debe tener 182 filas.', 1;
    IF @cnt_dim_fech  <> 5113 THROW 51000, N'Validacion fallida: dw.dim_fecha debe tener 5113 filas.', 1;
    IF @cnt_dim_mod   <> 7    THROW 51000, N'Validacion fallida: dw.dim_modalidad debe tener 7 filas.', 1;
    IF @cnt_dim_sexo  <> 3    THROW 51000, N'Validacion fallida: dw.dim_sexo debe tener 3 filas.', 1;
    IF @cnt_dim_edad  <> 7    THROW 51000, N'Validacion fallida: dw.dim_rango_edad debe tener 7 filas.', 1;
    IF @cnt_dim_nac   <> 60   THROW 51000, N'Validacion fallida: dw.dim_nacionalidad debe tener 60 filas.', 1;
    IF @cnt_dim_var   <> 18   THROW 51000, N'Validacion fallida: dw.dim_variable debe tener 18 filas.', 1;
    IF @cnt_dim_dep   <> 53   THROW 51000, N'Validacion fallida: dw.dim_dependencia debe tener 53 filas.', 1;
    IF @cnt_dim_ind   <> 5    THROW 51000, N'Validacion fallida: dw.dim_indicador debe tener 5 filas.', 1;

    -- 2. Reglas deterministicas de resolucion geografica (THROW 51001)
    IF NOT EXISTS (SELECT 1 FROM dw.dim_provincia WHERE cod_provincia = '1608' AND provincia = N'PUTUMAYO')
        THROW 51001, N'Validacion fallida: cod_provincia 1608 debe resolverse como PUTUMAYO.', 1;
    IF NOT EXISTS (SELECT 1 FROM dw.dim_ubigeo WHERE ubigeo = '010201' AND distrito = N'BAGUA')
        THROW 51001, N'Validacion fallida: ubigeo 010201 debe resolverse como BAGUA (prioridad D1).', 1;
    IF NOT EXISTS (SELECT 1 FROM dw.dim_ubigeo WHERE ubigeo = '010206' AND distrito = N'LA PECA')
        THROW 51001, N'Validacion fallida: ubigeo 010206 debe resolverse como LA PECA (prioridad D1).', 1;
    IF NOT EXISTS (SELECT 1 FROM dw.dim_ubigeo WHERE ubigeo = '150144')
        THROW 51001, N'Validacion fallida: ubigeo 150144 (solo D2) debe existir en dw.dim_ubigeo.', 1;

    -- 3. Cero claves huerfanas en las 20 relaciones FK: 3 dims + 17 hechos (THROW 51002)
    DECLARE @huerfanas INT = 0;

    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.dim_provincia AS p LEFT JOIN dw.dim_departamento AS d ON d.id_departamento = p.id_departamento WHERE d.id_departamento IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.dim_ubigeo AS u LEFT JOIN dw.dim_provincia AS p ON p.id_provincia = u.id_provincia WHERE p.id_provincia IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.dim_ubigeo AS u LEFT JOIN dw.dim_departamento AS d ON d.id_departamento = u.id_departamento WHERE d.id_departamento IS NULL;

    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_denuncias AS f LEFT JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo WHERE t.id_tiempo IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_denuncias AS f LEFT JOIN dw.dim_fecha AS fe ON fe.id_fecha = f.id_fecha WHERE fe.id_fecha IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_denuncias AS f LEFT JOIN dw.dim_ubigeo AS u ON u.id_ubigeo = f.id_ubigeo WHERE u.id_ubigeo IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_denuncias AS f LEFT JOIN dw.dim_modalidad AS m ON m.id_modalidad = f.id_modalidad WHERE m.id_modalidad IS NULL;

    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_desaparecidos AS f LEFT JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo WHERE t.id_tiempo IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_desaparecidos AS f LEFT JOIN dw.dim_fecha AS fe ON fe.id_fecha = f.id_fecha WHERE fe.id_fecha IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_desaparecidos AS f LEFT JOIN dw.dim_ubigeo AS u ON u.id_ubigeo = f.id_ubigeo WHERE u.id_ubigeo IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_desaparecidos AS f LEFT JOIN dw.dim_sexo AS s ON s.id_sexo = f.id_sexo WHERE s.id_sexo IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_desaparecidos AS f LEFT JOIN dw.dim_rango_edad AS r ON r.id_rango_edad = f.id_rango_edad WHERE r.id_rango_edad IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_desaparecidos AS f LEFT JOIN dw.dim_nacionalidad AS n ON n.id_nacionalidad = f.id_nacionalidad WHERE n.id_nacionalidad IS NULL;

    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_produccion AS f LEFT JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo WHERE t.id_tiempo IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_produccion AS f LEFT JOIN dw.dim_fecha AS fe ON fe.id_fecha = f.id_fecha WHERE fe.id_fecha IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_produccion AS f LEFT JOIN dw.dim_variable AS v ON v.id_variable = f.id_variable WHERE v.id_variable IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_produccion AS f LEFT JOIN dw.dim_dependencia AS dep ON dep.id_dependencia = f.id_dependencia WHERE dep.id_dependencia IS NULL;

    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_victimizacion AS f LEFT JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo WHERE t.id_tiempo IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_victimizacion AS f LEFT JOIN dw.dim_departamento AS d ON d.id_departamento = f.id_departamento WHERE d.id_departamento IS NULL;
    SELECT @huerfanas = @huerfanas + COUNT(*) FROM dw.fact_victimizacion AS f LEFT JOIN dw.dim_indicador AS i ON i.id_indicador = f.id_indicador WHERE i.id_indicador IS NULL;

    IF @huerfanas <> 0
        THROW 51002, N'Validacion fallida: existen claves huerfanas en el modelo dimensional.', 1;

    -- 4. Cero duplicados por grano en las 4 tablas de hechos (THROW 51003)
    DECLARE @dup_den INT = (SELECT COUNT(*) FROM (SELECT 1 AS x FROM dw.fact_denuncias GROUP BY id_tiempo, id_ubigeo, id_modalidad HAVING COUNT(*) > 1) AS d);
    DECLARE @dup_des INT = (SELECT COUNT(*) FROM (SELECT 1 AS x FROM dw.fact_desaparecidos GROUP BY id_tiempo, id_ubigeo, id_sexo, id_rango_edad, id_nacionalidad HAVING COUNT(*) > 1) AS d);
    DECLARE @dup_pro INT = (SELECT COUNT(*) FROM (SELECT 1 AS x FROM dw.fact_produccion GROUP BY id_tiempo, id_variable, id_dependencia HAVING COUNT(*) > 1) AS d);
    DECLARE @dup_vic INT = (SELECT COUNT(*) FROM (SELECT 1 AS x FROM dw.fact_victimizacion GROUP BY id_tiempo, id_departamento, id_indicador HAVING COUNT(*) > 1) AS d);

    IF (@dup_den + @dup_des + @dup_pro + @dup_vic) <> 0
        THROW 51003, N'Validacion fallida: se detectaron duplicados de grano en tablas de hechos.', 1;

    -- 5. Reconciliacion exacta contra DataMarts origen D1-D4 (THROW 51004..51007)
    DECLARE @src_cnt_d1 INT, @src_sum_d1 BIGINT;
    DECLARE @src_cnt_d2 INT, @src_sum_d2 BIGINT;
    DECLARE @src_cnt_d3 INT, @src_sum_d3 DECIMAL(38,6);
    DECLARE @src_cnt_d4 INT, @src_sum_d4 DECIMAL(38,6);

    SELECT @src_cnt_d1 = COUNT(*), @src_sum_d1 = SUM(CAST(cantidad AS BIGINT))
    FROM DBDenunciasPoliciales.dm.DenunciasPoliciales;

    SELECT @src_cnt_d2 = COUNT(*), @src_sum_d2 = SUM(CAST(cantidad AS BIGINT))
    FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas;

    SELECT @src_cnt_d3 = COUNT(*), @src_sum_d3 = SUM(CAST(valor AS DECIMAL(38,6)))
    FROM DBProduccionPolicial.dm.ProduccionPolicial;

    SELECT @src_cnt_d4 = COUNT(*), @src_sum_d4 = SUM(CAST(valor AS DECIMAL(38,6)))
    FROM DBVictimizacionConfianzaPNP.dm.VictimizacionConfianzaPNP;

    DECLARE @dw_cnt_d1 INT, @dw_sum_d1 BIGINT, @dw_par_d1 INT;
    DECLARE @dw_cnt_d2 INT, @dw_sum_d2 BIGINT, @dw_par_d2 INT;
    DECLARE @dw_cnt_d3 INT, @dw_sum_d3 DECIMAL(38,6), @dw_par_d3 INT, @dw_ceros_d3 INT;
    DECLARE @dw_cnt_d4 INT, @dw_sum_d4 DECIMAL(38,6), @dw_par_d4 INT, @dw_nac_d4 INT;

    SELECT @dw_cnt_d1 = COUNT(*), @dw_sum_d1 = SUM(CAST(cantidad AS BIGINT)), @dw_par_d1 = SUM(CASE WHEN es_anio_parcial = 1 THEN 1 ELSE 0 END)
    FROM dw.fact_denuncias;

    SELECT @dw_cnt_d2 = COUNT(*), @dw_sum_d2 = SUM(CAST(cantidad AS BIGINT)), @dw_par_d2 = SUM(CASE WHEN es_anio_parcial = 1 THEN 1 ELSE 0 END)
    FROM dw.fact_desaparecidos;

    SELECT @dw_cnt_d3 = COUNT(*), @dw_sum_d3 = SUM(CAST(valor AS DECIMAL(38,6))), @dw_par_d3 = SUM(CASE WHEN es_anio_parcial = 1 THEN 1 ELSE 0 END), @dw_ceros_d3 = SUM(CASE WHEN valor = 0 THEN 1 ELSE 0 END)
    FROM dw.fact_produccion;

    SELECT @dw_cnt_d4 = COUNT(*), @dw_sum_d4 = SUM(CAST(valor AS DECIMAL(38,6))), @dw_par_d4 = SUM(CASE WHEN es_anio_parcial = 1 THEN 1 ELSE 0 END), @dw_nac_d4 = SUM(CASE WHEN ambito = N'NACIONAL' THEN 1 ELSE 0 END)
    FROM dw.fact_victimizacion;

    IF @dw_cnt_d1 <> 378187 OR @dw_cnt_d1 <> @src_cnt_d1 OR @dw_sum_d1 <> 7614774 OR @dw_sum_d1 <> @src_sum_d1 OR @dw_par_d1 <> 37683
        THROW 51004, N'Validacion fallida: reconciliacion de dw.fact_denuncias vs DBDenunciasPoliciales.', 1;

    IF @dw_cnt_d2 <> 77331 OR @dw_cnt_d2 <> @src_cnt_d2 OR @dw_sum_d2 <> 142374 OR @dw_sum_d2 <> @src_sum_d2 OR @dw_par_d2 <> 0
        THROW 51005, N'Validacion fallida: reconciliacion de dw.fact_desaparecidos vs DBPersonasDesaparecidas.', 1;

    IF @dw_cnt_d3 <> 39096 OR @dw_cnt_d3 <> @src_cnt_d3 OR @dw_sum_d3 <> 2195845317.111756 OR @dw_sum_d3 <> @src_sum_d3 OR @dw_ceros_d3 <> 15458 OR @dw_par_d3 <> 8640
        THROW 51006, N'Validacion fallida: reconciliacion de dw.fact_produccion vs DBProduccionPolicial.', 1;

    IF @dw_cnt_d4 <> 1592 OR @dw_cnt_d4 <> @src_cnt_d4 OR @dw_sum_d4 <> 36287.6 OR @dw_sum_d4 <> @src_sum_d4 OR @dw_par_d4 <> 107 OR @dw_nac_d4 <> 58
        THROW 51007, N'Validacion fallida: reconciliacion de dw.fact_victimizacion vs DBVictimizacionConfianzaPNP.', 1;

    -- 6. Aserciones analiticas de las 5 preguntas guia Q1-Q5 (THROW 51008..51017)
    DECLARE @q1_2018_2025 BIGINT = (
        SELECT SUM(CAST(f.cantidad AS BIGINT))
        FROM dw.fact_denuncias AS f
        INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
        WHERE f.es_anio_parcial = 0 AND t.anio BETWEEN 2018 AND 2025
    );
    DECLARE @q1_2026_parcial BIGINT = (
        SELECT SUM(CAST(f.cantidad AS BIGINT))
        FROM dw.fact_denuncias AS f
        WHERE f.es_anio_parcial = 1
    );
    IF @q1_2018_2025 <> 6866606 OR @q1_2026_parcial <> 748168
        THROW 51008, N'Validacion Q1 fallida: denuncias 2018-2025 deben sumar 6,866,606 y 2026 parcial 748,168.', 1;

    DECLARE @q2_u18_rows INT, @q2_u18_sum BIGINT;
    SELECT @q2_u18_rows = COUNT(*), @q2_u18_sum = SUM(CAST(f.cantidad AS BIGINT))
    FROM dw.fact_desaparecidos AS f
    INNER JOIN dw.dim_rango_edad AS re ON re.id_rango_edad = f.id_rango_edad
    WHERE re.es_menor_18 = 1;

    DECLARE @q2_sexo_ni_rows INT, @q2_sexo_ni_sum BIGINT;
    SELECT @q2_sexo_ni_rows = COUNT(*), @q2_sexo_ni_sum = SUM(CAST(f.cantidad AS BIGINT))
    FROM dw.fact_desaparecidos AS f
    INNER JOIN dw.dim_sexo AS s ON s.id_sexo = f.id_sexo
    WHERE s.codigo_sexo = N'NO INFORMADO';

    DECLARE @q2_edad_ni_rows INT, @q2_edad_ni_sum BIGINT;
    SELECT @q2_edad_ni_rows = COUNT(*), @q2_edad_ni_sum = SUM(CAST(f.cantidad AS BIGINT))
    FROM dw.fact_desaparecidos AS f
    INNER JOIN dw.dim_rango_edad AS re ON re.id_rango_edad = f.id_rango_edad
    WHERE re.rango_edad = N'NO INFORMADO';

    IF @q2_u18_rows <> 37611 OR @q2_u18_sum <> 81262
        THROW 51009, N'Validacion Q2 fallida: menores de 18 deben sumar 81,262 casos en 37,611 filas.', 1;
    IF @q2_sexo_ni_rows <> 83 OR @q2_sexo_ni_sum <> 90
        THROW 51010, N'Validacion Q2 fallida: sexo NO INFORMADO debe tener 83 filas y 90 casos.', 1;
    IF @q2_edad_ni_rows <> 1197 OR @q2_edad_ni_sum <> 1357
        THROW 51011, N'Validacion Q2 fallida: rango_edad NO INFORMADO debe tener 1,197 filas y 1,357 casos.', 1;

    DECLARE @q3_kilos      DECIMAL(38,6) = (SELECT SUM(f.valor) FROM dw.fact_produccion AS f INNER JOIN dw.dim_variable AS v ON v.id_variable = f.id_variable WHERE f.es_anio_parcial = 0 AND v.unidad_medida = N'KILOS');
    DECLARE @q3_soles      DECIMAL(38,6) = (SELECT SUM(f.valor) FROM dw.fact_produccion AS f INNER JOIN dw.dim_variable AS v ON v.id_variable = f.id_variable WHERE f.es_anio_parcial = 0 AND v.unidad_medida = N'SOLES');
    DECLARE @q3_soles_val  DECIMAL(38,6) = (SELECT SUM(f.valor) FROM dw.fact_produccion AS f INNER JOIN dw.dim_variable AS v ON v.id_variable = f.id_variable WHERE f.es_anio_parcial = 0 AND v.unidad_medida = N'SOLES (VALORIZACION)');
    DECLARE @q3_operativos DECIMAL(38,6) = (SELECT SUM(f.valor) FROM dw.fact_produccion AS f INNER JOIN dw.dim_variable AS v ON v.id_variable = f.id_variable WHERE f.es_anio_parcial = 0 AND v.unidad_medida = N'OPERATIVOS');
    DECLARE @q3_env_sing   DECIMAL(38,6) = (SELECT SUM(f.valor) FROM dw.fact_produccion AS f INNER JOIN dw.dim_variable AS v ON v.id_variable = f.id_variable WHERE f.es_anio_parcial = 0 AND v.unidad_medida = N'ENVOLTORIO');
    DECLARE @q3_env_plur   DECIMAL(38,6) = (SELECT SUM(f.valor) FROM dw.fact_produccion AS f INNER JOIN dw.dim_variable AS v ON v.id_variable = f.id_variable WHERE f.es_anio_parcial = 0 AND v.unidad_medida = N'ENVOLTORIOS');
    DECLARE @q3_personas   DECIMAL(38,6) = (SELECT SUM(f.valor) FROM dw.fact_produccion AS f INNER JOIN dw.dim_variable AS v ON v.id_variable = f.id_variable WHERE f.es_anio_parcial = 0 AND v.unidad_medida = N'PERSONAS');
    DECLARE @q3_unidades   DECIMAL(38,6) = (SELECT SUM(f.valor) FROM dw.fact_produccion AS f INNER JOIN dw.dim_variable AS v ON v.id_variable = f.id_variable WHERE f.es_anio_parcial = 0 AND v.unidad_medida = N'UNIDADES');
    DECLARE @q3_papeletas  DECIMAL(38,6) = (SELECT SUM(f.valor) FROM dw.fact_produccion AS f INNER JOIN dw.dim_variable AS v ON v.id_variable = f.id_variable WHERE f.es_anio_parcial = 0 AND v.unidad_medida = N'PAPELETAS');

    IF @q3_kilos <> 518794.548573
        THROW 51012, N'Validacion Q3 fallida: KILOS 2023-2025 debe ser 518794.548573.', 1;
    IF @q3_soles <> 53874929.712000 OR @q3_soles_val <> 1631816149.014000
        THROW 51013, N'Validacion Q3 fallida: SOLES (53874929.712000) y SOLES (VALORIZACION) (1631816149.014000) deben mantenerse separados.', 1;
    IF @q3_operativos <> 3503958.000000
        THROW 51014, N'Validacion Q3 fallida: OPERATIVOS 2023-2025 debe ser 3503958.000000.', 1;
    IF @q3_env_sing <> 444589.000000 OR @q3_env_plur <> 6623509.000000 OR @q3_personas <> 1254351.000000 OR @q3_unidades <> 78120.000000 OR @q3_papeletas <> 3289357.000000
        THROW 51015, N'Validacion Q3 fallida: ENVOLTORIO, ENVOLTORIOS, PERSONAS, UNIDADES y PAPELETAS deben reconciliar exactamente por separado.', 1;

    DECLARE @q4_rows INT = (
        SELECT COUNT(*)
        FROM dw.fact_victimizacion AS f
        INNER JOIN dw.dim_departamento AS d ON d.id_departamento = f.id_departamento
        WHERE f.es_anio_parcial = 0 AND d.ambito = N'DEPARTAMENTO'
    );
    DECLARE @q4_invalid INT = (
        SELECT COUNT(*)
        FROM dw.fact_victimizacion AS f
        INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
        INNER JOIN dw.dim_departamento AS d ON d.id_departamento = f.id_departamento
        WHERE f.es_anio_parcial = 0 AND d.ambito = N'DEPARTAMENTO'
          AND (t.anio = 2013 OR f.ambito = N'NACIONAL' OR d.es_nacional = 1)
    );
    IF @q4_rows <> 1430 OR @q4_invalid <> 0
        THROW 51016, N'Validacion Q4 fallida: debe haber exactamente 1,430 filas departamentales completas (2014-2024) sin filas nacionales ni de 2013.', 1;

    DECLARE @q5_dept_cnt INT = (SELECT COUNT(DISTINCT d.id_departamento) FROM dw.dim_departamento AS d WHERE d.ambito = N'DEPARTAMENTO');
    DECLARE @q5_vic_2025 INT = (SELECT COUNT(*) FROM dw.fact_victimizacion AS f INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo WHERE t.anio = 2025);
    IF @q5_dept_cnt <> 26 OR @q5_vic_2025 <> 0
        THROW 51017, N'Validacion Q5 fallida: deben existir 26 departamentos y 0 filas de victimizacion en 2025.', 1;

    -- 7. Registro de auditoria por hecho y cierre EXITOSO en etl.ControlCargaDW
    INSERT INTO etl.ControlCargaDW (proceso, origen, tabla_destino, filas_origen, filas_cargadas, claves_huerfanas, control_suma, fecha_fin, estado, detalle)
    VALUES
        (N'SSIS_20_FactDenuncias',     N'stg.vw_fact_denuncias',     N'dw.fact_denuncias',     @src_cnt_d1, @dw_cnt_d1, 0, CAST(@dw_sum_d1 AS DECIMAL(38,6)), SYSDATETIME(), N'EXITOSO', N'Carga SSIS reconciliada D1 (378,187 filas; 7,614,774 denuncias; 37,683 parciales 2026).'),
        (N'SSIS_30_FactDesaparecidos', N'stg.vw_fact_desaparecidos', N'dw.fact_desaparecidos', @src_cnt_d2, @dw_cnt_d2, 0, CAST(@dw_sum_d2 AS DECIMAL(38,6)), SYSDATETIME(), N'EXITOSO', N'Carga SSIS reconciliada D2 (77,331 filas; 142,374 casos; 0 parciales).'),
        (N'SSIS_40_FactProduccion',    N'stg.vw_fact_produccion',    N'dw.fact_produccion',    @src_cnt_d3, @dw_cnt_d3, 0, @dw_sum_d3,                      SYSDATETIME(), N'EXITOSO', N'Carga SSIS reconciliada D3 (39,096 filas incl. 15,458 ceros; 8,640 parciales 2026).'),
        (N'SSIS_50_FactVictimizacion', N'stg.vw_fact_victimizacion', N'dw.fact_victimizacion', @src_cnt_d4, @dw_cnt_d4, 0, @dw_sum_d4,                      SYSDATETIME(), N'EXITOSO', N'Carga SSIS reconciliada D4 (1,592 filas incl. 58 NACIONAL y 107 parciales 2013).');

    SET @detalle = CONCAT(
        N'Orquestador SSIS EXITOSO. Dims=12 (27/196/1847/182/5113/7/3/7/60/18/53/5). ',
        N'Facts: denuncias=', @dw_cnt_d1, N' (', @dw_sum_d1, N'), ',
        N'desaparecidos=', @dw_cnt_d2, N' (', @dw_sum_d2, N'), ',
        N'produccion=', @dw_cnt_d3, N' (', @dw_sum_d3, N'), ',
        N'victimizacion=', @dw_cnt_d4, N' (', @dw_sum_d4, N'). Huerfanas=0.'
    );

    UPDATE etl.ControlCargaDW
    SET filas_origen     = @src_cnt_d1 + @src_cnt_d2 + @src_cnt_d3 + @src_cnt_d4,
        filas_cargadas   = @dw_cnt_d1 + @dw_cnt_d2 + @dw_cnt_d3 + @dw_cnt_d4,
        claves_huerfanas = 0,
        fecha_fin        = SYSDATETIME(),
        estado           = N'EXITOSO',
        detalle          = @detalle
    WHERE id_carga_dw = @id_carga;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0
        ROLLBACK TRANSACTION;

    UPDATE etl.ControlCargaDW
    SET fecha_fin = SYSDATETIME(),
        estado    = N'FALLIDO',
        detalle   = LEFT(ERROR_MESSAGE(), 4000)
    WHERE id_carga_dw = @id_carga;

    THROW;
END CATCH;
```

---

## 6. Compilación (`.ispac`), Ejecución (Visual Studio y `DTExec.exe`) y Verificación Post-Carga

### 6.1 Compilación Obligatoria (`.ispac`) Antes de Ejecutar

En **Project Deployment Model**, cada `Execute Package Task` configurado con `ReferenceType = Project Reference` lee los paquetes hijos desde el archivo compilado **`.ispac`**. Si ejecutas `00_Orquestador.dtsx` sin haber compilado antes el proyecto, Visual Studio detendrá la ejecución con el error:
> `ProjectDeploymentFileNotFound: A project deployment file (.ispac extension) is required in order to execute containers or packages. Build the project and try again.`

**Pasos de compilación:**
1. Guardar todos los paquetes (`Ctrl+Shift+S`).
2. En el menú superior, ir a **`Build`** -> **`Build Proyecto_EF_SSIS`** (o clic derecho sobre el proyecto en *Solution Explorer* -> **Build**).
3. Confirmar en la ventana *Output*: `Build: 1 succeeded, 0 failed` y verificar que se generó `...\bin\Development\Proyecto_EF_SSIS.ispac`. *(Repetir el Build cada vez que modifiques cualquiera de los paquetes `10`–`50` antes de correr `00_Orquestador.dtsx`.)*

### 6.2 Ejecución en Visual Studio 2026

1. En **Solution Explorer**, hacer clic derecho sobre **`00_Orquestador.dtsx`** -> **`Set as StartUp Object`**.
2. Presionar **`F5`** (o clic derecho sobre `00_Orquestador.dtsx` -> **`Execute Package`**).
3. Observar en la pestaña **Execution Results / Progress** que:
   - `SQL - Limpieza Previa DW` finaliza en verde.
   - `EPT - 10_Dimensiones` carga las 12 dimensiones en el orden FK correcto.
   - Los 4 `EPT - 20..50` se ejecutan **simultáneamente** en verde.
   - `SQL - Auditoria y Validacion Post-Carga` finaliza en verde.
4. Detener la depuración (`Shift+F5`).

### 6.3 Ejecución por Línea de Comandos (`DTExec.exe` v170)

Para ejecutar fuera de Visual Studio en este equipo (sin necesidad de catálogo `SSISDB`), utilizar el ejecutable **`DTExec.exe` de SQL Server 2025 (64-bit, `17.0.1000.7`)** pasando el proyecto compilado `.ispac` y el paquete maestro:

```powershell
& "C:\Program Files\Microsoft SQL Server\170\DTS\Binn\DTExec.exe" /Proj "<ruta_de_tu_solucion>\Proyecto_EF_SSIS\bin\Development\Proyecto_EF_SSIS.ispac" /Pack "00_Orquestador.dtsx"
```

*(Alternativamente está disponible el binario de la extensión VS 2026 `17.0.1016.0` en `C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\SSIS\170\Binn\DTExec.exe`.)*

> **Advertencias críticas para `DTExec.exe`:**
> 1. **NO usar `/File "...\00_Orquestador.dtsx"`:** ejecutar un `.dtsx` suelto con `/File` falla porque no carga los Project Connection Managers (`(project) CM_DW_ProyectoEF`) ni resuelve las referencias de proyecto (`ReferenceType = Project Reference`) del `.ispac`. Usar siempre **`/Proj "...\Proyecto_EF_SSIS.ispac" /Pack "00_Orquestador.dtsx"`**.
> 2. **NO usar el `DTExec.exe` legado v130 (`C:\Program Files\Microsoft SQL Server\130\DTS\Binn\DTExec.exe`, SQL Server 2016):** falla por incompatibilidad de versión de formato contra paquetes compilados para `TargetServerVersion = SQL Server 2025` (v170).

### 6.4 Verificación Post-Carga en SQL Server (`DW_ProyectoEF`)

Ejecutar en SSMS o `sqlcmd` para confirmar la auditoría y los totales exactos tras la corrida de SSIS:

```sql
USE [DW_ProyectoEF];
GO

-- 1. Auditoria reciente en etl.ControlCargaDW
SELECT TOP (10)
    id_carga_dw, proceso, tabla_destino, filas_origen, filas_cargadas,
    claves_huerfanas, control_suma, fecha_inicio, fecha_fin, estado, detalle
FROM etl.ControlCargaDW
ORDER BY id_carga_dw DESC;

-- 2. Verificacion de conteos exactos y sumas de control
SELECT N'dw.dim_departamento' AS objeto, COUNT(*) AS filas, NULL AS suma_control FROM dw.dim_departamento
UNION ALL SELECT N'dw.dim_provincia',    COUNT(*), NULL FROM dw.dim_provincia
UNION ALL SELECT N'dw.dim_ubigeo',       COUNT(*), NULL FROM dw.dim_ubigeo
UNION ALL SELECT N'dw.dim_tiempo',       COUNT(*), NULL FROM dw.dim_tiempo
UNION ALL SELECT N'dw.dim_fecha',        COUNT(*), NULL FROM dw.dim_fecha
UNION ALL SELECT N'dw.dim_modalidad',    COUNT(*), NULL FROM dw.dim_modalidad
UNION ALL SELECT N'dw.dim_sexo',         COUNT(*), NULL FROM dw.dim_sexo
UNION ALL SELECT N'dw.dim_rango_edad',   COUNT(*), NULL FROM dw.dim_rango_edad
UNION ALL SELECT N'dw.dim_nacionalidad', COUNT(*), NULL FROM dw.dim_nacionalidad
UNION ALL SELECT N'dw.dim_variable',     COUNT(*), NULL FROM dw.dim_variable
UNION ALL SELECT N'dw.dim_dependencia',  COUNT(*), NULL FROM dw.dim_dependencia
UNION ALL SELECT N'dw.dim_indicador',    COUNT(*), NULL FROM dw.dim_indicador
UNION ALL SELECT N'dw.fact_denuncias',     COUNT(*), CAST(SUM(CAST(cantidad AS BIGINT)) AS DECIMAL(38,6)) FROM dw.fact_denuncias
UNION ALL SELECT N'dw.fact_desaparecidos', COUNT(*), CAST(SUM(CAST(cantidad AS BIGINT)) AS DECIMAL(38,6)) FROM dw.fact_desaparecidos
UNION ALL SELECT N'dw.fact_produccion',    COUNT(*), SUM(CAST(valor AS DECIMAL(38,6)))                    FROM dw.fact_produccion
UNION ALL SELECT N'dw.fact_victimizacion', COUNT(*), SUM(CAST(valor AS DECIMAL(38,6)))                    FROM dw.fact_victimizacion;
```

#### Resultados Esperados de Control

| Objeto | Filas Esperadas | Suma de Control Esperada |
|---|---:|---:|
| `dw.dim_departamento` | `27` | — |
| `dw.dim_provincia` | `196` | — |
| `dw.dim_ubigeo` | `1,847` | — |
| `dw.dim_tiempo` | `182` | — |
| `dw.dim_fecha` | `5,113` | — |
| `dw.dim_modalidad` | `7` | — |
| `dw.dim_sexo` | `3` | — |
| `dw.dim_rango_edad` | `7` | — |
| `dw.dim_nacionalidad` | `60` | — |
| `dw.dim_variable` | `18` | — |
| `dw.dim_dependencia` | `53` | — |
| `dw.dim_indicador` | `5` | — |
| **Subtotal Dimensiones (12)** | **`7,315`** | — |
| `dw.fact_denuncias` | `378,187` | `7614774.000000` (`SUM(cantidad)`) |
| `dw.fact_desaparecidos` | `77,331` | `142374.000000` (`SUM(cantidad)`) |
| `dw.fact_produccion` | `39,096` | `2195845317.111756` (`SUM(valor)`) |
| `dw.fact_victimizacion` | `1,592` | `36287.600000` (`SUM(valor)`) |
| **Subtotal Hechos (4)** | **`496,206`** | — |

Opcionalmente, para ejecutar la prueba integral de reconciliación, consultas Q1–Q5 e idempotencia (Pass 2) desde consola:

```powershell
sqlcmd -S localhost -E -C -b -f 65001 -r 1 -i Database\06_dw_validacion.sql
```
