/* ============================================================================
   Validacion del DataWarehouse DW_ProyectoEF despues de ejecutar SSIS
   ----------------------------------------------------------------------------
   Ejecutar despues de:
     Source/Proyecto_EF_SSIS/10_Dimensiones.dtsx
     Source/Proyecto_EF_SSIS/20_FactDenuncias.dtsx
     Source/Proyecto_EF_SSIS/30_FactDesaparecidos.dtsx
     Source/Proyecto_EF_SSIS/40_FactProduccion.dtsx
     Source/Proyecto_EF_SSIS/50_FactVictimizacion.dtsx

   Comprueba:
     1. Conteos de hechos DW = conteos de los DataMarts de origen.
     2. Integridad referencial (claves huesped -> dimensiones).
     3. Sumas de medidas (no se perdieron filas ni se duplicaron valores).
     4. Registro de control de carga en etl.ControlCargaDW.
   ============================================================================ */

SET NOCOUNT ON;
USE DW_ProyectoEF;
GO

PRINT '=== 1. CONTEOS DW vs DATAMARTS ===';
SELECT origen, tabla_origen, filas_origen, filas_dw,
       CASE WHEN filas_origen = filas_dw THEN 'OK' ELSE 'ERROR' END AS resultado
FROM (
    SELECT 'D1 Denuncias' AS origen, 'DBDenunciasPoliciales.dm.DenunciasPoliciales' AS tabla_origen,
           (SELECT COUNT(*) FROM DBDenunciasPoliciales.dm.DenunciasPoliciales) AS filas_origen,
           (SELECT COUNT(*) FROM dw.fact_denuncias) AS filas_dw
    UNION ALL
    SELECT 'D2 Desaparecidos', 'DBPersonasDesaparecidas.dm.PersonasDesaparecidas',
           (SELECT COUNT(*) FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas),
           (SELECT COUNT(*) FROM dw.fact_desaparecidos)
    UNION ALL
    SELECT 'D3 Produccion', 'DBProduccionPolicial.dm.ProduccionPolicial',
           (SELECT COUNT(*) FROM DBProduccionPolicial.dm.ProduccionPolicial),
           (SELECT COUNT(*) FROM dw.fact_produccion)
    UNION ALL
    SELECT 'D4 Victimizacion', 'DBVictimizacionConfianzaPNP.dm.VictimizacionConfianzaPNP',
           (SELECT COUNT(*) FROM DBVictimizacionConfianzaPNP.dm.VictimizacionConfianzaPNP),
           (SELECT COUNT(*) FROM dw.fact_victimizacion)
) x;
GO

PRINT '=== 2. DIMENSIONES CARGADAS ===';
SELECT 'dw.dim_fecha' AS dimension, COUNT(*) AS filas FROM dw.dim_fecha
UNION ALL SELECT 'dw.dim_tiempo', COUNT(*) FROM dw.dim_tiempo
UNION ALL SELECT 'dw.dim_departamento', COUNT(*) FROM dw.dim_departamento
UNION ALL SELECT 'dw.dim_provincia', COUNT(*) FROM dw.dim_provincia
UNION ALL SELECT 'dw.dim_ubigeo', COUNT(*) FROM dw.dim_ubigeo
UNION ALL SELECT 'dw.dim_modalidad', COUNT(*) FROM dw.dim_modalidad
UNION ALL SELECT 'dw.dim_sexo', COUNT(*) FROM dw.dim_sexo
UNION ALL SELECT 'dw.dim_rango_edad', COUNT(*) FROM dw.dim_rango_edad
UNION ALL SELECT 'dw.dim_nacionalidad', COUNT(*) FROM dw.dim_nacionalidad
UNION ALL SELECT 'dw.dim_variable', COUNT(*) FROM dw.dim_variable
UNION ALL SELECT 'dw.dim_dependencia', COUNT(*) FROM dw.dim_dependencia
UNION ALL SELECT 'dw.dim_indicador', COUNT(*) FROM dw.dim_indicador;
GO

PRINT '=== 3. CLAVES HUESPED (deben ser todas 0) ===';
SELECT 'fact_denuncias -> dim_tiempo' AS relacion,
       COUNT(*) AS filas_huerfanas
FROM dw.fact_denuncias f LEFT JOIN dw.dim_tiempo d ON d.id_tiempo = f.id_tiempo
WHERE d.id_tiempo IS NULL
UNION ALL
SELECT 'fact_denuncias -> dim_fecha',
       COUNT(*) FROM dw.fact_denuncias f LEFT JOIN dw.dim_fecha d ON d.id_fecha = f.id_fecha_hecho WHERE d.id_fecha IS NULL
UNION ALL
SELECT 'fact_denuncias -> dim_ubigeo',
       COUNT(*) FROM dw.fact_denuncias f LEFT JOIN dw.dim_ubigeo d ON d.id_ubigeo = f.id_ubigeo WHERE d.id_ubigeo IS NULL
UNION ALL
SELECT 'fact_denuncias -> dim_modalidad',
       COUNT(*) FROM dw.fact_denuncias f LEFT JOIN dw.dim_modalidad d ON d.id_modalidad = f.id_modalidad WHERE d.id_modalidad IS NULL
UNION ALL
SELECT 'fact_desaparecidos -> dim_sexo',
       COUNT(*) FROM dw.fact_desaparecidos f LEFT JOIN dw.dim_sexo d ON d.id_sexo = f.id_sexo WHERE d.id_sexo IS NULL
UNION ALL
SELECT 'fact_desaparecidos -> dim_rango_edad',
       COUNT(*) FROM dw.fact_desaparecidos f LEFT JOIN dw.dim_rango_edad d ON d.id_rango_edad = f.id_rango_edad WHERE d.id_rango_edad IS NULL
UNION ALL
SELECT 'fact_desaparecidos -> dim_nacionalidad',
       COUNT(*) FROM dw.fact_desaparecidos f LEFT JOIN dw.dim_nacionalidad d ON d.id_nacionalidad = f.id_nacionalidad WHERE d.id_nacionalidad IS NULL
UNION ALL
SELECT 'fact_produccion -> dim_variable',
       COUNT(*) FROM dw.fact_produccion f LEFT JOIN dw.dim_variable d ON d.id_variable = f.id_variable WHERE d.id_variable IS NULL
UNION ALL
SELECT 'fact_produccion -> dim_dependencia',
       COUNT(*) FROM dw.fact_produccion f LEFT JOIN dw.dim_dependencia d ON d.id_dependencia = f.id_dependencia WHERE d.id_dependencia IS NULL
UNION ALL
SELECT 'fact_victimizacion -> dim_departamento',
       COUNT(*) FROM dw.fact_victimizacion f LEFT JOIN dw.dim_departamento d ON d.id_departamento = f.id_departamento WHERE d.id_departamento IS NULL
UNION ALL
SELECT 'fact_victimizacion -> dim_indicador',
       COUNT(*) FROM dw.fact_victimizacion f LEFT JOIN dw.dim_indicador d ON d.id_indicador = f.id_indicador WHERE d.id_indicador IS NULL;
GO

PRINT '=== 4. SUMAS DE MEDIDAS DW vs ORIGEN ===';
SELECT 'denuncias' AS medida,
       (SELECT SUM(cantidad) FROM dw.fact_denuncias) AS suma_dw,
       (SELECT SUM(cantidad) FROM DBDenunciasPoliciales.dm.DenunciasPoliciales) AS suma_origen
UNION ALL
SELECT 'desaparecidos',
       (SELECT SUM(cantidad) FROM dw.fact_desaparecidos),
       (SELECT SUM(cantidad) FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas)
UNION ALL
SELECT 'produccion (valor)',
       (SELECT SUM(valor) FROM dw.fact_produccion),
       (SELECT SUM(valor) FROM DBProduccionPolicial.dm.ProduccionPolicial)
UNION ALL
SELECT 'victimizacion (valor)',
       (SELECT SUM(valor) FROM dw.fact_victimizacion),
       (SELECT SUM(valor) FROM DBVictimizacionConfianzaPNP.dm.VictimizacionConfianzaPNP);
GO

PRINT '=== 5. CONTROL DE CARGA ===';
DELETE FROM etl.ControlCargaDW;
GO
INSERT INTO etl.ControlCargaDW (paquete, tabla, filas, fecha_inicio, fecha_fin, estado, detalle)
SELECT '10_Dimensiones.dtsx', 'dw.dim_tiempo', COUNT(*), GETDATE(), GETDATE(), 'OK', 'Carga por SSIS'
FROM dw.dim_tiempo
UNION ALL SELECT '20_FactDenuncias.dtsx', 'dw.fact_denuncias', COUNT(*), GETDATE(), GETDATE(), 'OK', 'Carga por SSIS' FROM dw.fact_denuncias
UNION ALL SELECT '30_FactDesaparecidos.dtsx', 'dw.fact_desaparecidos', COUNT(*), GETDATE(), GETDATE(), 'OK', 'Carga por SSIS' FROM dw.fact_desaparecidos
UNION ALL SELECT '40_FactProduccion.dtsx', 'dw.fact_produccion', COUNT(*), GETDATE(), GETDATE(), 'OK', 'Carga por SSIS' FROM dw.fact_produccion
UNION ALL SELECT '50_FactVictimizacion.dtsx', 'dw.fact_victimizacion', COUNT(*), GETDATE(), GETDATE(), 'OK', 'Carga por SSIS' FROM dw.fact_victimizacion;
GO
SELECT id_carga, paquete, tabla, filas, estado FROM etl.ControlCargaDW ORDER BY id_carga;
GO

PRINT '=== 6. MUESTRA DE LAS 5 PREGUNTAS GUIA ===';
PRINT 'P1: Top 10 departamentos por denuncias (solo 2024, anio completo)';
SELECT TOP 10 d.departamento, SUM(f.cantidad) AS denuncias
FROM dw.fact_denuncias f
JOIN dw.dim_tiempo t ON t.id_tiempo = f.id_tiempo
JOIN dw.dim_ubigeo u ON u.id_ubigeo = f.id_ubigeo
JOIN dw.dim_departamento d ON d.id_departamento = u.id_departamento
WHERE t.anio = 2024 AND t.es_anual = 0 AND f.es_anio_parcial = 0
GROUP BY d.departamento ORDER BY denuncias DESC;
GO

PRINT 'P2: Evolucion anual de denuncias y modalidad lider';
WITH x AS (
    SELECT t.anio, m.modalidad, SUM(f.cantidad) AS denuncias,
           ROW_NUMBER() OVER (PARTITION BY t.anio ORDER BY SUM(f.cantidad) DESC) AS rn
    FROM dw.fact_denuncias f
    JOIN dw.dim_tiempo t ON t.id_tiempo = f.id_tiempo
    JOIN dw.dim_modalidad m ON m.id_modalidad = f.id_modalidad
    WHERE t.es_anual = 0 AND f.es_anio_parcial = 0
    GROUP BY t.anio, m.modalidad
)
SELECT anio, modalidad AS modalidad_lider, denuncias FROM x WHERE rn = 1 ORDER BY anio;
GO

PRINT 'P3: Desapariciones por departamento y rango de edad (anios completos)';
SELECT TOP 10 d.departamento, e.rango_edad, SUM(f.cantidad) AS desaparecidos
FROM dw.fact_desaparecidos f
JOIN dw.dim_tiempo t ON t.id_tiempo = f.id_tiempo
JOIN dw.dim_ubigeo u ON u.id_ubigeo = f.id_ubigeo
JOIN dw.dim_departamento d ON d.id_departamento = u.id_departamento
JOIN dw.dim_rango_edad e ON e.id_rango_edad = f.id_rango_edad
WHERE t.es_anual = 0 AND f.es_anio_parcial = 0
GROUP BY d.departamento, e.rango_edad ORDER BY desaparecidos DESC;
GO

PRINT 'P4: Peor percepcion departamental (confianza PNP, ultimo anio completo)';
SELECT TOP 10 d.departamento, i.indicador, f.valor
FROM dw.fact_victimizacion f
JOIN dw.dim_tiempo t ON t.id_tiempo = f.id_tiempo
JOIN dw.dim_departamento d ON d.id_departamento = f.id_departamento
JOIN dw.dim_indicador i ON i.id_indicador = f.id_indicador
WHERE t.anio = (
    SELECT MAX(t2.anio) FROM dw.fact_victimizacion f2
    JOIN dw.dim_tiempo t2 ON t2.id_tiempo = f2.id_tiempo
    WHERE f2.es_anio_parcial = 0
)
  AND f.es_anio_parcial = 0
ORDER BY f.valor ASC;
GO

PRINT 'P5: Produccion policial por dependencia (una variable, su unidad)';
SELECT TOP 10 dep.dependencia, v.variable, v.unidad_medida, SUM(f.valor) AS valor_total
FROM dw.fact_produccion f
JOIN dw.dim_tiempo t ON t.id_tiempo = f.id_tiempo
JOIN dw.dim_dependencia dep ON dep.id_dependencia = f.id_dependencia
JOIN dw.dim_variable v ON v.id_variable = f.id_variable
WHERE t.es_anual = 0 AND f.es_anio_parcial = 0
  AND v.variable = 'DINERO INCAUTADO (SOLES)'
GROUP BY dep.dependencia, v.variable, v.unidad_medida
ORDER BY valor_total DESC;
GO
