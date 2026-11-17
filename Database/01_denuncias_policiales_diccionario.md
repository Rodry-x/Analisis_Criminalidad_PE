# Diccionario de datos — `dm.DenunciasPoliciales`

DataMart de denuncias policiales registradas a nivel nacional (MININTER),
periodo 2018–2026. Una fila representa el total de denuncias de una modalidad
delictiva en un distrito y mes determinados.

- **Base de datos:** `DBDenunciasPoliciales`
- **Esquema:** `dm`
- **Tabla:** `DenunciasPoliciales`
- **Grano:** `anio_registro`, `mes_registro`, `ubigeo`, `modalidad`
- **Script de creación y carga:** `Database/01_denuncias_policiales_datamart.sql`

## Columnas

| # | Columna | Tipo | Nulo | Descripción | Origen / regla |
|---|---|---|---|---|---|
| 1 | `id_denuncia` | `INT IDENTITY` | No | Clave sustituta de la fila | Generada en la carga |
| 2 | `anio_registro` | `SMALLINT` | No | Año del hecho | `ANIO_REGISTRO` |
| 3 | `mes_registro` | `TINYINT` | No | Mes del hecho (1–12) | `MES_REGISTRO` |
| 4 | `fecha_hecho` | `DATE` | No | Primer día del mes del hecho | Derivada de año y mes |
| 5 | `departamento` | `NVARCHAR(60)` | No | Departamento donde ocurrió el hecho | `DPTO_HECHO_NEW` |
| 6 | `provincia` | `NVARCHAR(100)` | No | Provincia donde ocurrió el hecho | `PROV_HECHO` |
| 7 | `distrito` | `NVARCHAR(120)` | No | Distrito donde ocurrió el hecho | `DIST_HECHO` |
| 8 | `ubigeo` | `CHAR(6)` | No | Código ubigeo del distrito | `UBIGEO_HECHO`, normalizado a 6 dígitos |
| 9 | `modalidad` | `NVARCHAR(100)` | No | Modalidad delictiva | `P_MODALIDADES` |
| 10 | `cantidad` | `INT` | No | Número de denuncias | `cantidad` |
| 11 | `es_anio_parcial` | `BIT` | No | 1 si el año no tiene diciembre; 0 si está completo | Derivada (2026 = 1) |
| 12 | `archivo_origen` | `NVARCHAR(400)` | No | CSV de procedencia | Nombre del archivo |
| 13 | `fecha_carga` | `DATETIME2(0)` | No | Fecha y hora de carga | `SYSDATETIME()` |

## Reglas de calidad

- `anio_registro` entre 2018 y 2026.
- `mes_registro` entre 1 y 12.
- `cantidad` entero mayor o igual a 0.
- `ubigeo` exactamente 6 dígitos numéricos.
- El prefijo del ubigeo debe corresponder al departamento:
  - `15` → `LIMA METROPOLITANA` o `REGION LIMA`
  - `07` → `PROV. CONST. DEL CALLAO`
  - Los demás prefijos tienen un único departamento.
- No se permiten duplicados en el grano
  `(anio_registro, mes_registro, ubigeo, modalidad)`.
- `archivo_origen` conserva la trazabilidad hacia el CSV original.

## Homologaciones aplicadas

| Ubigeo | Valores encontrados | Valor homologado |
|---|---|---|
| `160801` | `LORETO / MAYNAS / PUTUMAYO` y `LORETO / PUTUMAYO / PUTUMAYO` | `LORETO / PUTUMAYO / PUTUMAYO` |

## Modalidades disponibles

- `Otros`
- `Violencia contra la mujer e integrantes`
- `Hurto`
- `Robo`
- `Estafa`
- `Extorsión`
- `Secuestro`

## Índices

| Índice | Tipo | Columnas |
|---|---|---|
| `PK_DenunciasPoliciales` | Clustered, único | `id_denuncia` |
| `UX_DenunciasPoliciales_Grano` | Nonclustered, único | `anio_registro, mes_registro, ubigeo, modalidad` |
| `IX_DenunciasPoliciales_AnioMes` | Nonclustered | `anio_registro, mes_registro` (incluye `cantidad`) |
| `IX_DenunciasPoliciales_Ubigeo` | Nonclustered | `ubigeo` (incluye `cantidad`) |
| `IX_DenunciasPoliciales_Modalidad` | Nonclustered | `modalidad` (incluye `cantidad`) |

## Tabla de control

`etl.ControlCarga` registra cada ejecución del ETL: dataset, archivos, hash
SHA-256 del origen, filas leídas/rechazadas/agrupadas/cargadas, total de
denuncias, fechas, estado y detalle en JSON.

## Nota sobre 2026

El archivo de 2026 solo contiene enero–octubre. Por eso todas sus filas tienen
`es_anio_parcial = 1` y no deben compararse directamente con años completos.
