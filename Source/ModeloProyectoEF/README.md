# ModeloProyectoEF (SSAS Tabular)

Este directorio contiene el proyecto tabular que consume `DW_ProyectoEF.dw`.

| Archivo | Contenido |
|---|---|
| `ModeloProyectoEF.smproj` | Proyecto de Analysis Services para Visual Studio 2026 |
| `Model.bim` | Modelo tabular: 17 tablas, 20 relaciones, 11 medidas DAX y 3 jerarquías |

**Antes de desplegar:** el servidor SSAS local debe estar en modo **Tabular**.
Actualmente está en *Multidimensional*. La guía completa (cambio de modo,
importación de tablas, relaciones, medidas, procesamiento y gráficas de Power BI)
está en:

```
Source/GUIA_MODELADO_SSAS_Y_POWER_BI.md
```
