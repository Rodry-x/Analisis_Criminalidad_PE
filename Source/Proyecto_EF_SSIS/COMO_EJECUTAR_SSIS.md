# Cómo abrir y ejecutar el proyecto SSIS `Proyecto_EF_SSIS`

Este documento explica cómo abrir el proyecto en **Visual Studio 2026**, ejecutar los
paquetes ETL y verificar que `DW_ProyectoEF` se cargó correctamente.

---

## 1. Requisitos previos

Antes de abrir Visual Studio, confirma lo siguiente:

| Requisito | Estado esperado |
|---|---|
| SQL Server local (`localhost`) | Servicio **SQL Server (MSSQLSERVER)** iniciado |
| Base de datos `DW_ProyectoEF` | Creada y con el DDL aplicado (`Database/05_datawarehouse_ddl.sql`) |
| DataMarts `DM_Denuncias`, `DM_Desaparecidos`, `DM_Produccion`, `DM_Victimizacion` | Cargados |
| `xp_cmdshell` | Habilitado (lo usa el orquestador) |
| Permisos ACL | `NT SERVICE\MSSQLSERVER` con lectura/ejecución sobre `Source\Proyecto_EF_SSIS` y carpetas padre |
| SQL Server Integration Services | Instalado (viene con SQL Server 2022 en este equipo) |
| Visual Studio 2026 | Con la carga de trabajo **SQL Server Data Tools (SSDT)** / *SQL Server Integration Services* |

Si el orquestador falla con `Acceso denegado`, vuelve a aplicar los permisos:

```powershell
icacls "C:\Users\rodry20x\Documents\Clases-UPN\Ciclo_2026-2\BigDATA\EF_Final\Source" /grant "NT SERVICE\MSSQLSERVER:(OI)(CI)RX" /T
icacls "C:\Users\rodry20x\Documents\Clases-UPN\Ciclo_2026-2\BigDATA\EF_Final\Source\Proyecto_EF_SSIS" /grant "NT SERVICE\MSSQLSERVER:(OI)(CI)RX" /T
```

---

## 2. Abrir el proyecto en Visual Studio 2026

1. Abre **Visual Studio 2026**.
2. `Archivo > Abrir > Proyecto/Solución…`
3. Selecciona:

   ```
   Source\Proyecto_EF_SSIS.slnx
   ```

4. En el **Explorador de soluciones** verás el proyecto `Proyecto_EF_SSIS` con 6 paquetes:

   ```
   Proyecto_EF_SSIS
   ├── 00_Orquestador.dtsx      ← punto de entrada
   ├── 10_Dimensiones.dtsx
   ├── 20_FactDenuncias.dtsx
   ├── 30_FactDesaparecidos.dtsx
   ├── 40_FactProduccion.dtsx
   └── 50_FactVictimizacion.dtsx
   ```

### Si aparece “Referencia a un objeto no establecido” al abrir un paquete

Ese error **no es de carga de datos**. Aparece cuando los metadatos del `.dtproj`
están desincronizados con los `.dtsx` (IDs de paquete heredados, parámetros de
conexión huérfanos o falta de información de diseño).

**Ya corregido en este entorno:**

- El `.dtproj` tiene ahora **6 bloques `SSIS:PackageMetaData`**, uno por paquete,
  con el `ID`, `VersionGUID` y `VersionBuild` reales leídos de cada `.dtsx`.
- La connection manager del proyecto está declarada y alineada con los paquetes.
- Cada `.dtsx` incluye `DTS:DesignTimeProperties` con el layout de sus tareas,
  componentes y restricciones.

Si aún ves el error, cierra VS, elimina la carpeta `.vs` oculta junto a la solución
y vuelve a abrirla:

```powershell
Remove-Item -Recurse -Force "Source\.vs" -ErrorAction SilentlyContinue
```

---

## 3. Ejecutar desde Visual Studio

### Opción A (recomendada): ejecutar solo el orquestador

El paquete `00_Orquestador.dtsx` llama a los otros 5 en el orden correcto:

```
10_Dimensiones
   ↓
20_FactDenuncias
   ↓
30_FactDesaparecidos
   ↓
40_FactProduccion
   ↓
50_FactVictimizacion
```

Pasos:

1. En el **Explorador de soluciones**, haz clic derecho en `00_Orquestador.dtsx`.
2. Selecciona **Set as Startup Item** (Establecer como elemento de inicio).
3. Presiona **F5** o el botón **Iniciar** (▶).
4. En la pestaña de progreso verás cada tarea `Ejecutar SP de carga…` en verde.
5. Espera a que aparezca `DTSER_SUCCESS (0)` / *The package executed successfully*.

> El orquestador usa el procedimiento `etl.sp_EjecutarPaqueteSSIS`, que invoca
> `dtexec` mediante `xp_cmdshell` y **falla explícitamente** si el paquete hijo no
> devuelve `DTSER_SUCCESS`. No uses `no_output`: ocultaba los errores.

### Opción B: ejecutar paquetes individuales

Si quieres recargar una sola tabla:

1. Abre el paquete deseado (por ejemplo `20_FactDenuncias.dtsx`).
2. Presiona **F5**.
3. El Data Flow muestra: origen OLE DB → destino OLE DB.

**Orden obligatorio** si haces una recarga completa manual:

| # | Paquete | Contenido |
|---|---|---|
| 1 | `10_Dimensiones.dtsx` | 12 dimensiones (fecha, tiempo, departamento, provincia, ubigeo, modalidad, sexo, rango de edad, nacionalidad, variable, dependencia, indicador) |
| 2 | `20_FactDenuncias.dtsx` | Hecho de denuncias |
| 3 | `30_FactDesaparecidos.dtsx` | Hecho de desaparecidos |
| 4 | `40_FactProduccion.dtsx` | Hecho de producción policial |
| 5 | `50_FactVictimizacion.dtsx` | Hecho de victimización |

> Las dimensiones deben cargarse primero porque los hechos tienen llaves foráneas
> hacia ellas. Dentro de `10_Dimensiones`, las precedencias respetan
> `departamento → provincia → ubigeo`.

---

## 4. Ejecutar desde línea de comandos (`dtexec`)

Ruta real de `dtexec` en este equipo:

```
C:\Program Files\Microsoft SQL Server\170\DTS\Binn\DTExec.exe
```

Solo validar (no carga datos):

```powershell
$dtexec = 'C:\Program Files\Microsoft SQL Server\170\DTS\Binn\DTExec.exe'
& $dtexec /f "C:\Users\rodry20x\Documents\Clases-UPN\Ciclo_2026-2\BigDATA\EF_Final\Source\Proyecto_EF_SSIS\00_Orquestador.dtsx" /validate
```

Ejecutar el orquestador:

```powershell
& $dtexec /f "C:\Users\rodry20x\Documents\Clases-UPN\Ciclo_2026-2\BigDATA\EF_Final\Source\Proyecto_EF_SSIS\00_Orquestador.dtsx"
```

Resultado esperado al final:

```
DTSER_SUCCESS (0)
```

---

## 5. Verificar la carga

Ejecuta `Database/06_dw_validacion.sql` en SSMS. Debe devolver:

| Tabla | Filas esperadas |
|---|---|
| `dw.fact_denuncias` | 378,187 |
| `dw.fact_desaparecidos` | 77,331 |
| `dw.fact_produccion` | 39,096 |
| `dw.fact_victimizacion` | 1,592 |

Además:

- 0 llaves huérfanas en las 11 relaciones verificadas.
- Las sumas de `cantidad` / `valor` coinciden con los DataMarts de origen.
- `dw.dim_poblacion` queda vacía a propósito (pendiente de datos del INEI).

---

## 6. Notas de diseño

- Los DataMarts se mantienen **planos y limpios**; el modelado dimensional vive
  solo en `DW_ProyectoEF` (constelación de 4 hechos + dimensiones conformadas).
- Regla de Lima aplicada en las vistas `stg`:
  - `1501` → `LIMA METROPOLITANA`
  - `15xx` → `REGION LIMA`
  - `07` → `PROV. CONST. DEL CALLAO`
- Conflicto de nombre de ubigeo entre D1 y D2: gana D1.
- `es_anio_parcial` se guarda en cada tabla de hechos, no en `dim_tiempo`.
- `dim_variable` incluye `unidad_medida`; **no sumar kilos con soles** en el modelo
  final (cada variable se filtra por su unidad).
- `fact_victimizacion` usa `dim_departamento` (no `dim_ubigeo`) porque los alcances
  son `1501` / `1599`.

---

## 7. Siguiente paso

Una vez verificado el SSIS, el flujo continúa con:

1. **SSAS Tabular**: `Source/ModeloProyectoEF/ModeloProyectoEF.smproj` + `Model.bim`.
2. **Power BI**: conectarse al modelo tabular desplegado (o directamente al DW)
   siguiendo `Source/INSTRUCCIONES_POWER_BI.md`.
