# Guía paso a paso: modelado tabular `ModeloProyectoEF` + gráficas de Power BI

**Modelo:** `ModeloProyectoEF` (SSAS Tabular)  
**Fuente:** `DW_ProyectoEF.dw` (12 dimensiones + 4 hechos, ya cargados por SSIS)  
**Consumidor final:** Power BI Desktop conectado al modelo SSAS (no a las tablas directamente)

> Nota de nombre: en entregas anteriores aparece como *ModeladoProyectoEF*; el
> nombre oficial del modelo en SSAS y en la documentación es **`ModeloProyectoEF`**.

---

## 1. Requisitos previos

| Requisito | Verificación |
|---|---|
| SSAS instalado y corriendo | Servicio **SQL Server Analysis Services (MSSQLSERVER)** en estado *Running* |
| **SSAS en modo Tabular** | `ServerMode = Tabular` (ver sección 1.1) |
| `DW_ProyectoEF` cargado | Ejecutaste `Database/06_dw_validacion.sql` y viste los 4 conteos correctos |
| Visual Studio 2026 | Con carga de trabajo **SQL Server Data Tools (SSDT)** / SSAS Tabular |
| Permisos | Tu usuario Windows tiene `db_datareader` sobre `DW_ProyectoEF` |
| Cuenta de servicio SSAS | `NT SERVICE\MSSQLServerOLAPService` necesita lectura sobre `DW_ProyectoEF` para procesar |

Comprobar SSAS:

```powershell
Get-Service MSSQLServerOLAPService | Select-Object Name, Status
```

### 1.1 Verificar el modo del servidor (importante en este equipo)

En el momento de escribir esta guía, el servidor local está en modo
**Multidimensional**:

```powershell
$dllDir = 'C:\Program Files\Microsoft SQL Server\170\DTS\Binn'
Add-Type -Path (Join-Path $dllDir 'Microsoft.AnalysisServices.Core.dll')
Add-Type -Path (Join-Path $dllDir 'Microsoft.AnalysisServices.Tabular.dll')
Add-Type -Path (Join-Path $dllDir 'Microsoft.AnalysisServices.dll')
$s = New-Object Microsoft.AnalysisServices.Tabular.Server
$s.Connect('localhost')
$s.ServerMode   # → Multidimensional
$s.Disconnect()
```

Un modelo con `CompatibilityLevel = 1500` **solo se puede desplegar en modo
Tabular**. Si intentas desplegarlo tal cual, SSAS responde:

```
Errors in the metadata manager. Cannot create or load objects in the database
'ModeloProyectoEF' because the server is not running in Tabular mode.
```

**Cómo cambiarlo a Tabular (requiere administrador):**

1. Abre con un editor de texto **como Administrador**:

   ```
   C:\Program Files\Microsoft SQL Server\MSAS17.MSSQLSERVER\OLAP\Config\msmdsrv.ini
   ```

2. Busca la etiqueta `<DeploymentMode>` y cámbiala:

   ```xml
   <DeploymentMode>2</DeploymentMode>   <!-- 0 = Multidimensional, 2 = Tabular -->
   ```

   En SSAS 2022 también puede aparecer como:

   ```xml
   <DeploymentMode>Tabular</DeploymentMode>
   ```

3. Guarda y reinicia el servicio:

   ```powershell
   Restart-Service MSSQLServerOLAPService
   ```

4. Verifica de nuevo `ServerMode` → debe decir `Tabular`.

> El directorio `…\OLAP\Config` está protegido: necesitas una sesión de
> **PowerShell como Administrador**. Si no puedes cambiar el modo, el proyecto
> `Source\ModeloProyectoEF` queda listo y solo falta este paso de infraestructura
> antes de desplegar desde Visual Studio.

---

## 2. Crear el proyecto tabular en Visual Studio 2026

1. Abre Visual Studio 2026.
2. `Archivo > Nuevo > Proyecto…`
3. Busca **Analysis Services Tabular Project** (o *Tabular Model*).
4. Configura:
   - **Name:** `ModeloProyectoEF`
   - **Location:** `…\BigDATA\EF_Final\Source`
   - Marca **Create directory for solution** si quieres agruparlo con la solución SSIS.
5. Aceptar.

Se crea:

```
Source\ModeloProyectoEF\
├── ModeloProyectoEF.smproj
└── Model.bim
```

> La plantilla real de VS 2026 está en:
> `C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\SSAS\ProjectTemplates\Tabular\SemanticModel\`

### 2.1 Configurar el nivel de compatibilidad

1. En el **Explorador de soluciones**, haz clic en `Model.bim`.
2. En la ventana **Properties**, pon:

| Propiedad | Valor |
|---|---|
| Compatibility Level | **1500** (SQL Server 2019+) o **1600** (SQL Server 2022) |
| Default Data Source | `DW_ProyectoEF` |
| Culture | `es-ES` |
| Impersonation Mode | `Impersonate Service Account` |

> Usa `Impersonate Service Account` para que SSAS procese con
> `NT SERVICE\MSSQLServerOLAPService` y no con tu usuario interactivo.

---

## 3. Importar las tablas desde `DW_ProyectoEF`

### Paso 3.1 — Obtener datos

1. En el diseñador de modelos, menú **Model > Get Data** (o icono *Get Data*).
2. Selecciona **SQL Server** → **Connect**.
3. Configura:
   - Server: `localhost`
   - Database: `DW_ProyectoEF`
   - Authentication: **Windows integrated**
4. **Connect** → **Load**.

### Paso 3.2 — Seleccionar tablas

En el navegador, marca **todas las tablas del esquema `dw`**:

**Dimensiones (12):**

```
dim_fecha
dim_tiempo
dim_departamento
dim_provincia
dim_ubigeo
dim_modalidad
dim_sexo
dim_rango_edad
dim_nacionalidad
dim_variable
dim_dependencia
dim_indicador
```

**Hechos (4):**

```
fact_denuncias
fact_desaparecidos
fact_produccion
fact_victimizacion
```

> **No importes `dw.dim_poblacion`** todavía: está vacía a propósito (pendiente
> de proyección del INEI). Si la importas, las medidas de tasa devolverán `BLANK`.
> Puedes importarla igual y dejar las medidas preparadas para cuando se cargue.

Clic en **Load**. VS mostrará las 16 tablas en la vista de diagrama.

---

## 4. Definir relaciones

SSAS normalmente detecta las FK automáticamente. Verifica que queden **exactamente**
estas relaciones (una por cada FOREIGN KEY del DDL):

| Tablahecho/dimensión | Columna | → | Dimensión | Columna |
|---|---|---|---|---|
| `fact_denuncias` | `id_tiempo` | → | `dim_tiempo` | `id_tiempo` |
| `fact_denuncias` | `id_fecha_hecho` | → | `dim_fecha` | `id_fecha` |
| `fact_denuncias` | `id_ubigeo` | → | `dim_ubigeo` | `id_ubigeo` |
| `fact_denuncias` | `id_modalidad` | → | `dim_modalidad` | `id_modalidad` |
| `fact_desaparecidos` | `id_tiempo` | → | `dim_tiempo` | `id_tiempo` |
| `fact_desaparecidos` | `id_fecha_hecho` | → | `dim_fecha` | `id_fecha` |
| `fact_desaparecidos` | `id_ubigeo` | → | `dim_ubigeo` | `id_ubigeo` |
| `fact_desaparecidos` | `id_sexo` | → | `dim_sexo` | `id_sexo` |
| `fact_desaparecidos` | `id_rango_edad` | → | `dim_rango_edad` | `id_rango_edad` |
| `fact_desaparecidos` | `id_nacionalidad` | → | `dim_nacionalidad` | `id_nacionalidad` |
| `fact_produccion` | `id_tiempo` | → | `dim_tiempo` | `id_tiempo` |
| `fact_produccion` | `id_fecha_hecho` | → | `dim_fecha` | `id_fecha` |
| `fact_produccion` | `id_variable` | → | `dim_variable` | `id_variable` |
| `fact_produccion` | `id_dependencia` | → | `dim_dependencia` | `id_dependencia` |
| `fact_victimizacion` | `id_tiempo` | → | `dim_tiempo` | `id_tiempo` |
| `fact_victimizacion` | `id_departamento` | → | `dim_departamento` | `id_departamento` |
| `fact_victimizacion` | `id_indicador` | → | `dim_indicador` | `id_indicador` |

**Relaciones entre dimensiones (importante para la jerarquía geográfica):**

| Desde | → | Hacia |
|---|---|---|
| `dim_ubigeo.id_provincia` | → | `dim_provincia.id_provincia` |
| `dim_ubigeo.id_departamento` | → | `dim_departamento.id_departamento` |
| `dim_provincia.id_departamento` | → | `dim_departamento.id_departamento` |

### Cómo crear/verificar una relación en el diseñador

1. En la **Diagram View**, arrastra la columna clave de la tabla “muchos” (hecho)
   hasta la columna clave de la dimensión “uno”.
2. O usa **Model > New Relationship…** y completa From/To.
3. Todas deben ser **Many-to-One (* : 1)** y **Active**.

---

## 5. Limpieza del modelo (vista de cuadrícula)

En **Grid View**, para cada tabla:

### 5.1 Ocultar columnas de llave y auditoría

Marca como **Hidden = True** (clic derecho → *Hide in client tools*):

- Todos los `id_*` de las tablas de hecho (excepto los que uses en relaciones,
  que SSAS ya oculta automáticamente al crear la relación).
- `id_fact_denuncia`, `id_fact_desaparicion`, `id_fact_produccion`, `id_fact_victimizacion`.
- `clasif` en `fact_victimizacion` → mejor dejarlo visible pero con
  `Summarize By = None` (es un código de clasificación, no una medida aditiva).
- `es_anio_parcial` → déjalo visible como **flag** para filtrar/avisar en el informe.

### 5.2 Configurar columnas de fecha y formato

| Columna | Tabla | Configuración |
|---|---|---|
| `fecha` | `dim_fecha` | Data Type = Date, Format = `dd/mm/yyyy`, `Mark as Date Table = True` |
| `anio` | `dim_tiempo` | Summarize By = **None** (es un año, no se suma) |
| `mes` | `dim_tiempo` | Summarize By = **None**, Sort by column = `orden` |
| `nombre_mes` | `dim_tiempo` | **Sort by column = `mes`** (para que ENERO no salga antes que FEBRERO por orden alfabético) |
| `periodo` | `dim_tiempo` | Summarize By = None |
| `valor` | `fact_produccion` | Formato `#,##0.00` |
| `valor` | `fact_victimizacion` | Formato `0.0"%"` (ya viene en porcentaje) |
| `cantidad` | hechos | Formato `#,##0` |

> **Clave para el modelo:** marcar `dim_fecha` como *Date Table* (menú **Table >
> Mark as Date Table**) usando la columna `fecha`. Esto habilita las funciones
> de inteligencia de tiempo (`TOTALYTD`, `SAMEPERIODLASTYEAR`).

### 5.3 Crear jerarquías

**Jerarquía `Geografía` en `dim_ubigeo`:**

```
departamento → provincia → distrito
```

(arrastra `dim_departamento[departamento]`, `dim_provincia[provincia]`,
`dim_ubigeo[distrito]` dentro de la jerarquía; las relaciones de la sección 4
permiten que los campos de otras tablas aparezcan).

**Jerarquía `Tiempo` en `dim_tiempo`:**

```
anio → trimestre → nombre_mes
```

**Jerarquía `Geografía` en `dim_departamento`** (para `fact_victimizacion`):

```
macroregion → departamento
```

---

## 6. Crear medidas DAX

En **Grid View**, selecciona la tabla de hecho y usa **Model > New Measure**
(o el botón *Σ* de la barra). Escribe estas medidas:

### 6.1 Medidas base

```dax
Total Denuncias = SUM ( fact_denuncias[cantidad] )
```

```dax
Total Desaparecidos = SUM ( fact_desaparecidos[cantidad] )
```

```dax
Total Producción = SUM ( fact_produccion[valor] )
```

```dax
Confianza PNP = AVERAGE ( fact_victimizacion[valor] )
```

> `fact_victimizacion[valor]` es un porcentaje (0–100) con `dim_indicador[unidad] = '%'`.
> Usa **AVERAGE**, no SUM: sumar porcentajes de distintos indicadores no tiene sentido.

### 6.2 Medidas de producción por unidad (evita mezclar kilos con soles)

Primero consulta los valores reales de unidad en SQL:

```sql
SELECT DISTINCT unidad_medida FROM DW_ProyectoEF.dw.dim_variable ORDER BY 1;
```

Luego crea una medida parametrizada por la unidad seleccionada:

```dax
Producción por Unidad =
VAR UnidadSeleccionada = SELECTEDVALUE ( dim_variable[unidad_medida] )
RETURN
    IF (
        NOT ISBLANK ( UnidadSeleccionada ),
        CALCULATE (
            SUM ( fact_produccion[valor] ),
            dim_variable[unidad_medida] = UnidadSeleccionada
        )
    )
```

Esta es la medida que debes usar en el informe (no `Total Producción`), y debes
poner `dim_variable[unidad_medida]` en un **segmentador (slicer)** para elegir
una unidad a la vez.

### 6.3 Medidas de contexto (modalidad líder, año parcial)

```dax
Modalidad Líder =
VAR TablaModalidades =
    ADDCOLUMNS (
        VALUES ( dim_modalidad[modalidad] ),
        "@denuncias", [Total Denuncias]
    )
VAR MaxDenuncias = MAXX ( TablaModalidades, [@denuncias] )
RETURN
    MAXX (
        FILTER ( TablaModalidades, [@denuncias] = MaxDenuncias ),
        dim_modalidad[modalidad]
    )
```

```dax
Es Año Parcial =
SELECTEDVALUE ( dim_tiempo[es_anual], FALSE )
```

```dax
Denuncias Año Anterior =
CALCULATE (
    [Total Denuncias],
    SAMEPERIODLASTYEAR ( dim_fecha[fecha] )
)
```

```dax
Variación Denuncias % =
DIVIDE (
    [Total Denuncias] - [Denuncias Año Anterior],
    [Denuncias Año Anterior]
)
```

### 6.4 Medidas de tasa (preparadas, devuelven BLANK hasta cargar INEI)

```dax
Población = SUM ( dim_poblacion[poblacion] )
```

```dax
Tasa Denuncias x100k =
DIVIDE ( [Total Denuncias] * 100000, [Población] )
```

```dax
Tasa Desaparecidos x100k =
DIVIDE ( [Total Desaparecidos] * 100000, [Población] )
```

> Mientras `dw.dim_poblacion` esté vacía, estas medidas mostrarán `(en blanco)`.
> Eso es **esperado**, no un error.

### 6.5 Organizar medidas en una tabla de medidas

Crea una tabla vacía llamada `_Medidas` (**Model > New Table** no es necesario;
puedes usar **Enter Data** con una sola columna) y mueve todas las medidas ahí.
Así el informe tiene un único lugar para encontrarlas.

---

## 7. Procesar, desplegar y verificar

### 7.1 Procesar en Visual Studio

1. Menú **Model > Process > Process All**.
2. En la ventana *Process Database*, selecciona **Full** y **OK**.
3. Revisa la pestaña **Results**: debe terminar con *Process succeeded*.

> Si falla con *Login failed* o *Access denied*, revisa el permiso de
> `NT SERVICE\MSSQLServerOLAPService` sobre `DW_ProyectoEF`.

### 7.2 Desplegar a SSAS

1. En el Explorador de soluciones, clic derecho en `ModeloProyectoEF` → **Deploy**.
2. Configura:
   - **Server:** `localhost`
   - **Database:** `ModeloProyectoEF`
3. Aceptar. VS despliega y procesa el modelo.
4. Verifica en SSMS:

```sql
-- Conectarse a Analysis Services (localhost), no a Motor de BD
SELECT [Name], [State] FROM $SYSTEM.DBSCHEMA_CATALOGS;
```

Debe aparecer `ModeloProyectoEF` con estado `READY`.

### 7.3 Consulta de prueba (MDX en SSMS)

```sql
SELECT
    [Measures].[Total Denuncias] ON COLUMNS,
    [dim_tiempo].[anio].[anio].ALLMEMBERS ON ROWS
FROM [ModeloProyectoEF]
```

---

## 8. Conectar Power BI Desktop al modelo SSAS

1. Abre **Power BI Desktop**.
2. **Home > Get Data > Analysis Services** (o *SQL Server Analysis Services Database*).
3. Configura:
   - Server: `localhost`
   - Database: `ModeloProyectoEF`
   - Authentication: **Windows** (integrada)
4. **Connect** → **Load**.
5. En el panel **Fields** verás las 16 tablas y las medidas de `_Medidas`.

> Si prefieres conectarte **en DirectQuery** (sin importar datos), marca
> *Connect live*. Para este tamaño (≈ 496k filas) **Import** o **Connect live**
> funcionan igual de bien; usa **Connect live** para que Power BI siempre refleje
> el último procesamiento del modelo.

---

## 9. Qué gráficas usar en Power BI (paso final)

Relación directa con las **5 preguntas guía** del proyecto:

| # | Pregunta guía | Medida / campos | Gráfica recomendada | Por qué |
|---|---|---|---|---|
| 1 | ¿Dónde conviene ubicar mi negocio desde el punto de vista de seguridad? | `Total Denuncias` + `Geografía` (departamento/provincia/distrito) | **Mapa de burbujas** (o mapa coroplético) | Muestra densidad de denuncias por ubicación; permite comparar zonas de alto riesgo de un vistazo. |
| 2 | ¿Cómo evolucionan las denuncias y qué modalidades lideran? | `Total Denuncias` + `dim_tiempo.periodo` + `dim_modalidad.modalidad` | **Gráfico de líneas** (evolución) + **Barras apiladas** (modalidades por año) + Tarjeta con `Modalidad Líder` | La línea muestra tendencia; las barras apiladas muestran composición y cuál modalidad domina cada año. |
| 3 | ¿Dónde y en qué perfil se concentran las desapariciones? | `Total Desaparecidos` + `Geografía` + `sexo`, `rango_edad`, `nacionalidad` | **Mapa de calor** + **Gráfico de barras horizontales** por perfil + **Matriz** departamento × rango de edad | Combina concentración geográfica con perfil demográfico. |
| 4 | ¿Cómo evoluciona la confianza en la PNP y qué departamentos tienen peor percepción? | `Confianza PNP` + `dim_tiempo.anio` + `dim_departamento.departamento` + `dim_indicador.indicador` | **Gráfico de líneas** (confianza en el tiempo) + **Mapa coroplético** (peor percepción) + **Gráfico de embudo/gauge** por indicador | La línea muestra la tendencia nacional; el mapa resalta los departamentos críticos. |
| 5 | ¿Qué dependencias/variables concentran la producción policial? | `Producción por Unidad` + `dim_dependencia.dependencia` + `dim_variable.unidad_medida` | **Barras horizontales** (Top 10 dependencias) + **Matriz** dependencia × variable + **Slicer** de unidad de medida | El slicer evita mezclar unidades; la matriz permite ver qué variable aporta cada dependencia. |

### 9.1 Armar el informe (pasos concretos)

1. **Página 1 — Resumen / Seguridad**
   - Insertar un **Mapa** (burbujas):
     - Location = `dim_ubigeo[distrito]` (o `dim_departamento[departamento]`)
     - Size = `[Total Denuncias]`
   - Insertar 4 **Tarjetas (Cards)**: Total Denuncias, Total Desaparecidos, Confianza PNP, Modalidad Líder.
   - Agregar un **Slicer** de `dim_tiempo[anio]`.

2. **Página 2 — Denuncias**
   - **Line chart**: X = `dim_tiempo[periodo]`, Y = `[Total Denuncias]`.
   - **Stacked bar chart**: X = `dim_tiempo[anio]`, Y = `[Total Denuncias]`, Legend = `dim_modalidad[modalidad]`.
   - Agregar `es_anio_parcial` como slicer para avisar de años incompletos.

3. **Página 3 — Desapariciones**
   - **Mapa** con `Total Desaparecidos`.
   - **Clustered bar chart**: Y = `dim_rango_edad[rango_edad]`, X = `[Total Desaparecidos]`, Legend = `dim_sexo[sexo]`.
   - **Matrix**: Rows = `dim_departamento[departamento]`, Columns = `dim_nacionalidad[nacionalidad]`, Values = `[Total Desaparecidos]`.

4. **Página 4 — Confianza PNP**
   - **Line chart**: X = `dim_tiempo[anio]`, Y = `[Confianza PNP]`, Legend = `dim_indicador[indicador]`.
   - **Mapa coroplético**: Location = `dim_departamento[departamento]`, Color saturation = `[Confianza PNP]`.
   - Ordenar el mapa de menor a mayor para ver primero la **peor percepción**.

5. **Página 5 — Producción policial**
   - **Slicer** de `dim_variable[unidad_medida]` (obligatorio).
   - **Top N bar chart**: Y = `dim_dependencia[dependencia]`, X = `[Producción por Unidad]`, Top N = 10.
   - **Matrix**: Rows = `dim_dependencia[dependencia]`, Columns = `dim_variable[variable]`, Values = `[Producción por Unidad]`.

### 9.2 Buenas prácticas finales

- Usa un **tema de color** único en las 5 páginas.
- Pon **títulos dinámicos** con el año seleccionado:
  `"Denuncias – " & SELECTEDVALUE(dim_tiempo[anio])`.
- Agrega una nota visible: *“Los años con `es_anio_parcial = 1` no son comparables”*.
- No pongas `id_*` en ningún visual: cuando el usuario vea `id_ubigeo`, algo salió mal.
- Si más adelante cargas `dw.dim_poblacion`, cambia las tarjetas para usar
  `[Tasa Denuncias x100k]` en lugar del total absoluto.

---

## 10. Resumen del flujo completo

```
4 DataMarts
   ↓  (vistas stg limpian y resuelven claves)
SSIS (6 paquetes)
   ↓  (OLE DB Source → OLE DB Destination)
DW_ProyectoEF.dw  (constelación: 4 hechos + 12 dimensiones)
   ↓  (Get Data + relaciones + medidas DAX)
ModeloProyectoEF (SSAS Tabular)
   ↓  (Analysis Services / Connect live)
Power BI Desktop → 5 páginas con las gráficas de la sección 9
```

---

## 11. Archivos relacionados

| Archivo | Contenido |
|---|---|
| `Source/GUIA_MODELADO_SSAS_Y_POWER_BI.md` | Este documento. |
| `Source/Proyecto_EF_SSIS/GUIA_PASO_A_PASO_VISUAL_STUDIO.md` | Cómo se construyó el ETL en SSIS. |
| `Source/Proyecto_EF_SSIS/COMO_EJECUTAR_SSIS.md` | Ejecución y permisos del SSIS. |
| `Database/05_datawarehouse_ddl.sql` | DDL, vistas `stg` y SP del orquestador. |
| `Database/06_dw_validacion.sql` | Validación de conteos, FKs y sumas. |
