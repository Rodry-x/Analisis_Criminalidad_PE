# Guía paso a paso: construir y ejecutar el ETL en Visual Studio 2026

**Proyecto:** `Proyecto_EF_SSIS`  
**Destino:** `DW_ProyectoEF` (esquema `dw`)  
**Orígenes:** 4 DataMarts en SQL Server local (`localhost`)

Esta guía explica **cómo se ve el flujo desde los orígenes, qué hace cada tarea y
cómo se construye/ejecuta en el diseñador de Visual Studio 2026**. El proyecto ya
está creado en `Source/Proyecto_EF_SSIS`, así que puedes abrirlo directamente; la
sección 4 explica cómo recrearlo si quieres aprender haciendo clic.

---

## 1. Panorama general de la arquitectura

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ORÍGENES (4 DataMarts, esquema dm)                                          │
│                                                                              │
│  DBDenunciasPoliciales      → dm.DenunciasPoliciales                         │
│  DBPersonasDesaparecidas    → dm.PersonasDesaparecidas                       │
│  DBProduccionPolicial       → dm.ProduccionPolicial                          │
│  DBVictimizacionConfianzaPNP→ dm.VictimizacionConfianzaPNP                   │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │  (cross-database, mismo localhost)
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  CAPA stg  (dentro de DW_ProyectoEF)                                         │
│  16 vistas CREATE OR ALTER VIEW:                                             │
│    • 12 vw_dim_*  → preparan/Resuelven claves de las dimensiones              │
│    •  4 vw_fact_* → traen los hechos ya con las claves resueltas              │
│  Aquí se aplican las reglas de negocio (Lima, ubigeo, año parcial, etc.).     │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │  OLE DB Source lee la vista
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  SSIS  (Source/Proyecto_EF_SSIS, 6 paquetes .dtsx)                           │
│  Data Flow: OLE DB Source → OLE DB Destination                               │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │  INSERT en modo "table or view - fast load"
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  DESTINO: DW_ProyectoEF.dw                                                   │
│  12 dimensiones + 4 tablas de hecho (modelo de constelación)                 │
│  + etl.ControlCargaDW (auditoría)                                            │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                ▼
                     SSAS Tabular → Power BI
```

**Idea clave:** SSIS **no transforma** los datos con componentes complejos. Toda
la limpieza/resolución de claves ya está en las vistas `stg`. El Data Flow es
simplemente: *leer vista → escribir tabla*. Esto esIntencional y hace el ETL
fácil de auditar.

---

## 2. Los orígenes: qué datos entran

| Base de datos | Tabla de origen | Used por | Registros aprox. |
|---|---|---|---:|
| `DBDenunciasPoliciales` | `dm.DenunciasPoliciales` | D1 + dimensiones de geografía/modalidad | 378,187 |
| `DBPersonasDesaparecidas` | `dm.PersonasDesaparecidas` | D2 + dimensiones de geografía/sexo/edad/nacionalidad | 77,331 |
| `DBProduccionPolicial` | `dm.ProduccionPolicial` | D3 + dimensiones de variable/dependencia | 39,096 |
| `DBVictimizacionConfianzaPNP` | `dm.VictimizacionConfianzaPNP` | D4 + dimensión de indicador | 1,592 |

Los DataMarts se mantienen **planos y limpios**. El modelado dimensional
(llaves, conformación, constelación) existe **solo en `DW_ProyectoEF`**.

### Reglas que ya aplican las vistas `stg`

- **Regla Lima:** `1501 → LIMA METROPOLITANA`, `15xx → REGION LIMA`, `07 → PROV. CONST. DEL CALLAO`.
- **Conflicto de ubigeo D1/D2:** gana el nombre de D1 (`prioridad = 1`).
- **Meses numéricos:** 1–12 (más `0 = ANUAL` en `dim_tiempo`).
- **Año parcial:** se guarda como `es_anio_parcial` en cada hecho (no en `dim_tiempo`).
- **`dim_variable`** incluye `unidad_medida`: no se deben sumar kilos con soles.

---

## 3. Las vistas `stg` (entrada real de cada Data Flow)

### Dimensiones (12)

| Vista `stg` | Origen principal | Tabla destino `dw` |
|---|---|---|
| `vw_dim_fecha` | Generada (calendario 2013–2026) + fila `NO ESPECIFICADO` | `dw.dim_fecha` |
| `vw_dim_tiempo` | Generada (años 2013–2026 × meses 0–12) | `dw.dim_tiempo` |
| `vw_dim_departamento` | Lista conformada (NACIONAL + 24 departamentos + Lima/Callao) | `dw.dim_departamento` |
| `vw_dim_provincia` | D1 ∪ D2 (`LEFT(ubigeo,4)`) | `dw.dim_provincia` |
| `vw_dim_ubigeo` | D1 ∪ D2, gana D1 | `dw.dim_ubigeo` |
| `vw_dim_modalidad` | `DISTINCT modalidad` de D1 | `dw.dim_modalidad` |
| `vw_dim_sexo` | Lista fija (`'', M, F`) | `dw.dim_sexo` |
| `vw_dim_rango_edad` | `DISTINCT rango_edad` de D2 | `dw.dim_rango_edad` |
| `vw_dim_nacionalidad` | `DISTINCT nacionalidad` de D2 | `dw.dim_nacionalidad` |
| `vw_dim_variable` | `DISTINCT variable, unidad_medida` de D3 | `dw.dim_variable` |
| `vw_dim_dependencia` | `DISTINCT dependencia, dir_reg_fre` de D3 | `dw.dim_dependencia` |
| `vw_dim_indicador` | `DISTINCT indicador` de D4 | `dw.dim_indicador` |

### Hechos (4)

| Vista `stg` | Origen | Claves resueltas contra | Tabla destino `dw` |
|---|---|---|---|
| `vw_fact_denuncias` | D1 | `dim_modalidad`, `dim_ubigeo`, `dim_tiempo`, `dim_fecha` | `dw.fact_denuncias` |
| `vw_fact_desaparecidos` | D2 | `dim_sexo`, `dim_rango_edad`, `dim_nacionalidad`, `dim_ubigeo` | `dw.fact_desaparecidos` |
| `vw_fact_produccion` | D3 | `dim_variable`, `dim_dependencia` | `dw.fact_produccion` |
| `vw_fact_victimizacion` | D4 | `dim_indicador`, `dim_departamento` | `dw.fact_victimizacion` |

---

## 4. Construir el proyecto en Visual Studio (paso a paso)

> Si solo quieres **ejecutar** el proyecto ya creado, salta a la sección 6.  
> Esta sección es para entender/recrear cómo se armó.

### Paso 4.1 — Crear el proyecto

1. Abre **Visual Studio 2026**.
2. `Archivo > Nuevo > Proyecto…`
3. Busca la plantilla **Integration Services Project** (viene con SSDT / SQL Server Data Tools).
4. Nombre: `Proyecto_EF_SSIS`.
5. Ubicación: `…\BigDATA\EF_Final\Source`.
6. Aceptar.

Quedarán archivos:

```
Proyecto_EF_SSIS.dtproj
Project.params
Package.dtsx   ← renómbralo a 00_Orquestador.dtsx
```

### Paso 4.2 — Crear el Connection Manager (la conexión al DW)

1. En el diseñador de cualquier paquete, haz clic derecho en el área **Connection Managers** (abajo) → **New OLE DB Connection…**
2. **Configure OLE DB Connection Manager** → **New…**
3. En **Connection Manager**:
   - Provider: **Microsoft OLE DB Driver for SQL Server** (`MSOLEDBSQL`)
   - Server name: `localhost`
   - Authentication: **Windows Authentication**
   - Database: `DW_ProyectoEF`
4. **Test Connection** → debe decir *Test connection succeeded*.
5. Aceptar. Ponle el nombre:

```
localhost.DW_ProyectoEF
```

> Ese mismo connection manager se usa para **leer las vistas `stg` y escribir en `dw`**,
> porque las vistas están dentro de `DW_ProyectoEF` y hacen referencias cross-database
> a los DataMarts (permisos de Windows resueltos por `localhost`).

### Paso 4.3 — Crear un Data Flow (ejemplo: `20_FactDenuncias`)

1. En la pestaña **Control Flow**, arrastra desde la **SSIS Toolbox** un
   **Data Flow Task** al lienzo.
2. Renómbralo: `DFT Fact Denuncias`.
3. Haz doble clic en él → cambias a la pestaña **Data Flow**.
4. Arrastra un **OLE DB Source**:
   - Nombre: `SRC stg vw_fact_denuncias`
   - Doble clic → **OLE DB Source Editor**:
     - Connection manager: `localhost.DW_ProyectoEF`
     - Data access mode: **Table or view**
     - Name of the table or the view: `stg.vw_fact_denuncias`
     - Clic en **Preview** → debe mostrar columnas y filas.
5. Arrastra un **OLE DB Destination**:
   - Nombre: `DST dw fact_denuncias`
   - Doble clic → **OLE DB Destination Editor**:
     - Connection manager: `localhost.DW_ProyectoEF`
     - Data access mode: **Table or view - fast load**
     - Table or view: `[dw].[fact_denuncias]`
     - Clic en **Mappings** → verifica el mapeo automático por nombre:

| Origen (`stg.vw_fact_denuncias`) | Destino (`dw.fact_denuncias`) |
|---|---|
| `id_tiempo` | `id_tiempo` |
| `id_fecha_hecho` | `id_fecha_hecho` |
| `id_ubigeo` | `id_ubigeo` |
| `id_modalidad` | `id_modalidad` |
| `cantidad` | `cantidad` |
| `es_anio_parcial` | `es_anio_parcial` |

6. Une la **flecha azul** desde la salida del Source a la entrada del Destination
   (la flecha se llama `Flujo DFT Fact Denuncias`).
7. El lienzo debe verse así:

```
┌────────────────────────────┐        ┌─────────────────────────────┐
│ SRC stg vw_fact_denuncias  │───────▶│ DST dw fact_denuncias       │
│ (OLE DB Source)            │ Flujo  │ (OLE DB Destination, fast   │
│ Vista de la capa stg       │        │  load, tabla dw.fact_*)     │
└────────────────────────────┘        └─────────────────────────────┘
```

8. Guarda con `Ctrl+S`. El archivo se llama `20_FactDenuncias.dtsx`.

> **Importante:** si haces clic derecho en el Source y eliges *Edit…*, no cambies
> el tipo de acceso. Usar **Table or view** (no *SQL command*) es lo que permite
> que SSIS lea la definición de columnas de la vista y mapee por nombre.

### Paso 4.4 — Repetir para los otros 4 paquetes de carga

| Paquete | Data Flow Task | Source (vista `stg`) | Destination (tabla `dw`) | Columnas mapeadas |
|---|---|---|---|---|
| `10_Dimensiones` | `DFT Dim Fecha` | `vw_dim_fecha` | `dim_fecha` | `id_fecha, fecha, anio, mes, dia, nombre_mes, trimestre, es_fin_de_semana, anio_mes` |
| | `DFT Dim Tiempo` | `vw_dim_tiempo` | `dim_tiempo` | `id_tiempo, anio, mes, nombre_mes, trimestre, periodo, es_anual, orden` |
| | `DFT Dim Departamento` | `vw_dim_departamento` | `dim_departamento` | `id_departamento, codigo, departamento, es_nacional, macroregion` |
| | `DFT Dim Provincia` | `vw_dim_provincia` | `dim_provincia` | `id_provincia, provincia, id_departamento` |
| | `DFT Dim Ubigeo` | `vw_dim_ubigeo` | `dim_ubigeo` | `id_ubigeo, ubigeo, distrito, provincia, id_provincia, id_departamento` |
| | `DFT Dim Modalidad` | `vw_dim_modalidad` | `dim_modalidad` | `id_modalidad, modalidad` |
| | `DFT Dim Sexo` | `vw_dim_sexo` | `dim_sexo` | `id_sexo, sexo, descripcion` |
| | `DFT Dim Rango Edad` | `vw_dim_rango_edad` | `dim_rango_edad` | `id_rango_edad, rango_edad` |
| | `DFT Dim Nacionalidad` | `vw_dim_nacionalidad` | `dim_nacionalidad` | `id_nacionalidad, nacionalidad` |
| | `DFT Dim Variable` | `vw_dim_variable` | `dim_variable` | `id_variable, variable, unidad_medida` |
| | `DFT Dim Dependencia` | `vw_dim_dependencia` | `dim_dependencia` | `id_dependencia, dependencia, dir_reg_fre` |
| | `DFT Dim Indicador` | `vw_dim_indicador` | `dim_indicador` | `id_indicador, indicador, unidad` |
| `30_FactDesaparecidos` | `DFT Fact Desaparecidos` | `vw_fact_desaparecidos` | `fact_desaparecidos` | `id_tiempo, id_fecha_hecho, id_ubigeo, id_sexo, id_rango_edad, id_nacionalidad, cantidad, es_anio_parcial` |
| `40_FactProduccion` | `DFT Fact Produccion` | `vw_fact_produccion` | `fact_produccion` | `id_tiempo, id_fecha_hecho, id_variable, id_dependencia, valor, es_anio_parcial` |
| `50_FactVictimizacion` | `DFT Fact Victimizacion` | `vw_fact_victimizacion` | `fact_victimizacion` | `id_tiempo, id_departamento, id_indicador, valor, clasif, es_anio_parcial` |

#### Precedencias dentro de `10_Dimensiones`

En el **Control Flow** de `10_Dimensiones` debes unir los 12 Data Flow Tasks con
**Precedence Constraint** (flecha verde) en este orden, para respetar llaves foráneas:

```
DFT Dim Fecha
   ↓
DFT Dim Tiempo
   ↓
DFT Dim Departamento
   ↓
DFT Dim Provincia
   ↓
DFT Dim Ubigeo
   ↓
DFT Dim Modalidad
   ↓
DFT Dim Sexo
   ↓
DFT Dim Rango Edad
   ↓
DFT Dim Nacionalidad
   ↓
DFT Dim Variable
   ↓
DFT Dim Dependencia
   ↓
DFT Dim Indicador
```

La restricción es del tipo **Success** (valor por defecto): el siguiente task solo
corre si el anterior terminó bien.

### Paso 4.5 — Crear el orquestador `00_Orquestador.dtsx`

En vez de usar *Execute Package Task* (que en este equipo falló con
`The connection is not specified`), el orquestador usa **5 Execute SQL Task**
que llaman al procedimiento `etl.sp_EjecutarPaqueteSSIS`.

1. Crea un paquete nuevo y renómbralo `00_Orquestador.dtsx`.
2. Arrastra **5 Execute SQL Task** al Control Flow.
3. Nombra cada uno: `Ejecutar SP de carga 1 … 5`.
4. Doble clic en cada uno y configura:

| Propiedad | Valor |
|---|---|
| Connection type | `OLE DB` |
| Connection | `localhost.DW_ProyectoEF` |
| SQLSourceType | `Direct input` |
| SQLStatement | `EXEC etl.sp_EjecutarPaqueteSSIS @RutaPaquete = N'C:\Users\rodry20x\Documents\Clases-UPN\Ciclo_2026-2\BigDATA\EF_Final\Source\Proyecto_EF_SSIS\10_Dimensiones.dtsx';` |

Cambia el nombre del `.dtsx` según el task:

| # | Ruta del paquete hijo |
|---|---|
| 1 | `…\Source\Proyecto_EF_SSIS\10_Dimensiones.dtsx` |
| 2 | `…\Source\Proyecto_EF_SSIS\20_FactDenuncias.dtsx` |
| 3 | `…\Source\Proyecto_EF_SSIS\30_FactDesaparecidos.dtsx` |
| 4 | `…\Source\Proyecto_EF_SSIS\40_FactProduccion.dtsx` |
| 5 | `…\Source\Proyecto_EF_SSIS\50_FactVictimizacion.dtsx` |

5. Une los 5 tasks con flechas verdes (Success) en ese orden.
6. Guarda.

El diseñador debe verse así:

```
┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
│ Ejecutar SP de carga 1│──▶│ Ejecutar SP de carga 2│──▶│ Ejecutar SP de carga 3│
│ 10_Dimensiones        │   │ 20_FactDenuncias      │   │ 30_FactDesaparecidos  │
└───────────────────────┘   └───────────────────────┘   └──────────┬────────────┘
                                                                   │
                                                                   ▼
                                       ┌───────────────────────┐   ┌───────────────────────┐
                                       │ Ejecutar SP de carga 5│◀──│ Ejecutar SP de carga 4│
                                       │ 50_FactVictimizacion  │   │ 40_FactProduccion     │
                                       └───────────────────────┘   └───────────────────────┘
```

### ¿Qué hace `etl.sp_EjecutarPaqueteSSIS`?

Está definido en `Database/05_datawarehouse_ddl.sql` (línea 587). En resumen:

```sql
EXEC sp_configure 'xp_cmdshell', 1; RECONFIGURE;
SET @cmd = '"<dtexec>" /f "<paquete>.dtsx"';
INSERT INTO @salida EXEC master.dbo.xp_cmdshell @cmd;

IF NOT EXISTS (SELECT 1 FROM @salida WHERE linea LIKE '%DTSER_SUCCESS (0)%')
    RAISERROR('Fallo al ejecutar el paquete SSIS...', 16, 1);
```

Es decir: captura **toda** la salida de `dtexec` y falla explícitamente si el
paquete hijo no devuelve `DTSER_SUCCESS (0)`. Por eso no se usa `no_output`:
ocultaría los errores y el orquestador terminaría "verde" sin cargar nada.

---

## 5. Qué ocurre dentro de un Data Flow (vista detallada)

Cuando presionas F5 en `20_FactDenuncias.dtsx`, ocurre esto:

```
1. OLE DB Source
   └─ Abre conexión "localhost.DW_ProyectoEF"
   └─ Ejecuta: SELECT * FROM stg.vw_fact_denuncias
        └─ La vista, a su vez, consulta DBDenunciasPoliciales.dm.DenunciasPoliciales
           y hace LEFT JOIN contra dw.dim_modalidad para resolver id_modalidad.

2. Buffer en memoria (SSIS pipeline)
   └─ No hay transformaciones: solo pasan las 6 columnas mapeadas.

3. OLE DB Destination (fast load)
   └─ Abre la misma conexión
   └─ INSERT BULK-like INTO dw.fact_denuncias
      (id_tiempo, id_fecha_hecho, id_ubigeo, id_modalidad, cantidad, es_anio_parcial)
   └─ Respeta los FOREIGN KEY hacia dim_tiempo, dim_fecha, dim_ubigeo, dim_modalidad.
```

**Por qué funciona el orden:** si `dw.dim_modalidad` estuviera vacía, el
`LEFT JOIN` de la vista devolvería `id_modalidad = 0` (la fila *NO ESPECIFICADO*),
y la FK seguiría siendo válida. Aun así, el orquestador carga primero las
dimensiones para que los ids reales estén disponibles.

---

## 6. Ejecutar desde Visual Studio

### 6.1 Abrir la solución

1. `Archivo > Abrir > Proyecto/Solución…`
2. Selecciona `Source\Proyecto_EF_SSIS.slnx`.
3. Explorador de soluciones:

```
Proyecto_EF_SSIS
├── 00_Orquestador.dtsx      ← elemento de inicio
├── 10_Dimensiones.dtsx
├── 20_FactDenuncias.dtsx
├── 30_FactDesaparecidos.dtsx
├── 40_FactProduccion.dtsx
└── 50_FactVictimizacion.dtsx
```

### 6.2 Ejecutar el orquestador (recomendado)

1. Clic derecho en `00_Orquestador.dtsx` → **Set as Startup Item**.
2. Presiona **F5**.
3. Observa la pestaña de progreso: los 5 tasks se ponen en verde en orden.
4. Resultado esperado:

```
The package executed successfully.
DTSER_SUCCESS (0)
```

### 6.3 Ejecutar un paquete individual

1. Abre, por ejemplo, `20_FactDenuncias.dtsx`.
2. Presiona F5.
3. En la pestaña **Data Flow** verás las filas transferidas junto a cada componente.
4. Opcional: arrastra un **Data Viewer** sobre la flecha azul para ver las filas en vivo.

> Si haces una recarga completa manual, respeta el orden:
> `10 → 20 → 30 → 40 → 50`.

---

## 7. Salida hacia `DW_ProyectoEF`

Después de ejecutar, consulta en SSMS:

```sql
USE DW_ProyectoEF;
GO

SELECT 'fact_denuncias'       AS tabla, COUNT(*) AS filas FROM dw.fact_denuncias
UNION ALL SELECT 'fact_desaparecidos',   COUNT(*) FROM dw.fact_desaparecidos
UNION ALL SELECT 'fact_produccion',      COUNT(*) FROM dw.fact_produccion
UNION ALL SELECT 'fact_victimizacion',   COUNT(*) FROM dw.fact_victimizacion;
```

Resultado esperado:

| Tabla destino | Filas |
|---|---:|
| `dw.fact_denuncias` | 378,187 |
| `dw.fact_desaparecidos` | 77,331 |
| `dw.fact_produccion` | 39,096 |
| `dw.fact_victimizacion` | 1,592 |

También ejecuta `Database/06_dw_validacion.sql`: debe reportar **0 llaves
huérfanas** en las 11 relaciones y sumas idénticas a los DataMarts.

### Modelo resultante (constelación)

```
                    ┌──────────────┐
                    │ dim_tiempo   │
                    └──────┬───────┘
                           │
   ┌──────────┐      ┌─────▼──────────────┐      ┌──────────────┐
   │dim_fecha ├─────▶│ fact_denuncias     │◀─────┤dim_modalidad │
   └──────────┘      └─────┬──────────────┘      └──────────────┘
                           │
                    ┌──────▼───────┐
                    │ dim_ubigeo   │◀── dim_provincia ◀── dim_departamento
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌──────────────────┐
│fact_desapare- │  │fact_produccion│  │fact_victimizacion│
│cidos          │  │               │  │                  │
└───────┬───────┘  └───────┬───────┘  └────────┬─────────┘
        │                  │                   │
   dim_sexo           dim_variable        dim_indicador
   dim_rango_edad     dim_dependencia     dim_departamento
   dim_nacionalidad
```

Nota: `dw.dim_poblacion` existe pero queda **vacía a propósito** (pendiente de
obtener población del INEI para calcular tasas por habitante).

---

## 8. Solución rápida de problemas

| Síntoma | Causa | Acción |
|---|---|---|
| “Referencia a un objeto no establecido” al abrir paquete | Metadatos `.dtproj` desincronizados | Ya corregido. Cierra VS, borra `Source\.vs` y vuelve a abrir. |
| `Acceso denegado` / `0xC0011002` en el orquestador | Falta ACL para `NT SERVICE\MSSQLSERVER` | Ver `COMO_EJECUTAR_SSIS.md`, sección 1. |
| El orquestador termina en verde pero no carga | Se usó `no_output` en `xp_cmdshell` | Usar el SP sin `no_output` (ya corregido). |
| `The connection is not specified` | Execute Package Task | No usarlo; usar Execute SQL Task + SP. |
| Error de FK en la carga | Se ejecutó un hecho antes que las dimensiones | Seguir el orden `10 → 20 → 30 → 40 → 50`. |

---

## 9. Archivos relacionados

| Archivo | Para qué sirve |
|---|---|
| `GUIA_PASO_A_PASO_VISUAL_STUDIO.md` | Este documento (orígenes → flujo → DW). |
| `COMO_EJECUTAR_SSIS.md` | Referencia operativa: permisos, `dtexec`, validación. |
| `Database/05_datawarehouse_ddl.sql` | DDL del DW, vistas `stg` y `sp_EjecutarPaqueteSSIS`. |
| `Database/06_dw_validacion.sql` | Conteos, FKs y sumas de control. |
| `Source/Proyecto_EF_SSIS.slnx` | Solución que se abre en VS 2026. |
