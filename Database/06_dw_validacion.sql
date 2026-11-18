/* ============================================================================
   Validacion, Carga e Idempotencia: DW_ProyectoEF
   ----------------------------------------------------------------------------
   Proposito:
     1. Pass 1 (Carga completa limpia):
        - TRUNCATE de las 4 tablas de hechos (dw.fact_*).
        - DELETE en orden inverso de FK de las 12 dimensiones (dw.dim_*) +
          DBCC CHECKIDENT(..., RESEED, 0) con guarda last_value IS NOT NULL.
        - Carga de las 12 dimensiones en orden FK desde stg.vw_dim_*.
        - Carga de las 4 tablas de hechos desde stg.vw_fact_*.
     2. Validacion integral (fail-fast con THROW 51000..51020):
        - Conteos exactos de las 12 dimensiones y resolucion determinista
          de conflictos geograficos (1608 -> PUTUMAYO, 010201 -> BAGUA,
          010206 -> LA PECA, 150144 incluido).
        - Cero claves huerfanas en las 20 relaciones FK (17 de hechos + 3 dim).
        - Cero filas duplicadas por grano en las 4 tablas de hechos.
        - Reconciliacion exacta de filas y sumas frente a los 4 DataMarts
          origen (DBDenunciasPoliciales, DBPersonasDesaparecidas,
          DBProduccionPolicial, DBVictimizacionConfianzaPNP).
     3. Validacion analitica Q1-Q5:
        - Q1: Denuncias 2018-2025 (es_anio_parcial = 0) = 6,866,606.
        - Q2: Desaparecidos 2019-2025, menores de 18 = 81,262 casos (37,611 filas)
              y sentinela NO INFORMADO (83 sexo / 1,197 rango_edad).
        - Q3: Produccion Policial 2023-2025 separada por unidad_medida.
        - Q4: Victimizacion y Confianza PNP 2014-2024 (es_anio_parcial = 0,
              ambito = 'DEPARTAMENTO', 1,430 filas, promedio AVG(valor)).
        - Q5: Comparacion cruzada 2019-2025 en los 26 departamentos.
     4. Pass 2 (Prueba de idempotencia):
        - TRUNCATE de las 4 tablas de hechos, recarga desde stg.vw_fact_* y
          verificacion de paridad exacta con Pass 1 (cero duplicados).
     5. Auditoria en etl.ControlCargaDW fuera de transacciones anuladas.

   Ejecucion recomendada:
     sqlcmd -S localhost -E -C -b -f 65001 -r 1 -i Database\06_dw_validacion.sql
   ============================================================================ */

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DW_ProyectoEF];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* ============================================================================
   PASS 1: CARGA COMPLETA LIMPIA Y RECONCILIACION CONTRA ORIGEN
   ============================================================================ */

PRINT N'=== PASS 1: Carga completa limpia de DW_ProyectoEF ===';

IF OBJECT_ID(N'tempdb..#Pass1Baseline') IS NOT NULL
    DROP TABLE #Pass1Baseline;

CREATE TABLE #Pass1Baseline (
    tabla_destino NVARCHAR(128) NOT NULL PRIMARY KEY,
    filas         INT           NOT NULL,
    control_suma  DECIMAL(38,6) NOT NULL
);

DECLARE @id_carga_pass1 INT;
DECLARE @detalle_pass1  NVARCHAR(MAX);

INSERT INTO etl.ControlCargaDW (
    proceso, origen, tabla_destino, filas_origen, filas_cargadas, claves_huerfanas, control_suma, estado, detalle
)
VALUES (
    N'06_dw_validacion_pass1_carga_completa',
    N'stg.vw_* (D1-D4)',
    N'DW_ProyectoEF (12 dim + 4 fact)',
    NULL,
    0,
    0,
    NULL,
    N'EN_PROCESO',
    N'Inicio de carga limpia completa y validacion de integridad referencial.'
);
SET @id_carga_pass1 = CAST(SCOPE_IDENTITY() AS INT);

BEGIN TRY
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

    -- 3. Carga de las 12 dimensiones en orden FK
    INSERT INTO dw.dim_departamento (cod_ubicacion, departamento, ambito, es_nacional, macroregion)
    SELECT cod_ubicacion, departamento, ambito, es_nacional, macroregion
    FROM stg.vw_dim_departamento
    ORDER BY cod_ubicacion;

    INSERT INTO dw.dim_provincia (id_departamento, cod_provincia, provincia)
    SELECT id_departamento, cod_provincia, provincia
    FROM stg.vw_dim_provincia
    ORDER BY cod_provincia;

    INSERT INTO dw.dim_ubigeo (id_provincia, id_departamento, ubigeo, distrito)
    SELECT id_provincia, id_departamento, ubigeo, distrito
    FROM stg.vw_dim_ubigeo
    ORDER BY ubigeo;

    INSERT INTO dw.dim_tiempo (anio, mes_numero, mes_nombre, mes_corto, trimestre, trimestre_nombre, es_anual, periodo_label)
    SELECT anio, mes_numero, mes_nombre, mes_corto, trimestre, trimestre_nombre, es_anual, periodo_label
    FROM stg.vw_dim_tiempo
    ORDER BY anio, mes_numero;

    INSERT INTO dw.dim_fecha (fecha, anio, mes, dia, mes_nombre, trimestre, trimestre_nombre, es_primer_dia_mes)
    SELECT fecha, anio, mes, dia, mes_nombre, trimestre, trimestre_nombre, es_primer_dia_mes
    FROM stg.vw_dim_fecha
    ORDER BY fecha;

    INSERT INTO dw.dim_modalidad (modalidad)
    SELECT modalidad
    FROM stg.vw_dim_modalidad
    ORDER BY modalidad;

    INSERT INTO dw.dim_sexo (codigo_sexo, sexo_descripcion)
    SELECT codigo_sexo, sexo_descripcion
    FROM stg.vw_dim_sexo
    ORDER BY codigo_sexo;

    INSERT INTO dw.dim_rango_edad (rango_edad, es_menor_18, orden_edad)
    SELECT rango_edad, es_menor_18, orden_edad
    FROM stg.vw_dim_rango_edad
    ORDER BY orden_edad;

    INSERT INTO dw.dim_nacionalidad (nacionalidad)
    SELECT nacionalidad
    FROM stg.vw_dim_nacionalidad
    ORDER BY nacionalidad;

    INSERT INTO dw.dim_variable (variable, unidad_medida, categoria_variable)
    SELECT variable, unidad_medida, categoria_variable
    FROM stg.vw_dim_variable
    ORDER BY unidad_medida, variable;

    INSERT INTO dw.dim_dependencia (dependencia, dir_reg_fre)
    SELECT dependencia, dir_reg_fre
    FROM stg.vw_dim_dependencia
    ORDER BY dir_reg_fre, dependencia;

    INSERT INTO dw.dim_indicador (indicador, indicador_corto)
    SELECT indicador, indicador_corto
    FROM stg.vw_dim_indicador
    ORDER BY indicador;

    -- 4. Validacion de conteos exactos de las 12 dimensiones y resolucion geografica
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

    IF @cnt_dim_depto <> 27  THROW 51000, N'Validacion fallida: dw.dim_departamento debe tener 27 filas.', 1;
    IF @cnt_dim_prov  <> 196 THROW 51000, N'Validacion fallida: dw.dim_provincia debe tener 196 filas.', 1;
    IF @cnt_dim_ubig  <> 1847 THROW 51000, N'Validacion fallida: dw.dim_ubigeo debe tener 1847 filas.', 1;
    IF @cnt_dim_tiem  <> 182 THROW 51000, N'Validacion fallida: dw.dim_tiempo debe tener 182 filas.', 1;
    IF @cnt_dim_fech  <> 5113 THROW 51000, N'Validacion fallida: dw.dim_fecha debe tener 5113 filas.', 1;
    IF @cnt_dim_mod   <> 7   THROW 51000, N'Validacion fallida: dw.dim_modalidad debe tener 7 filas.', 1;
    IF @cnt_dim_sexo  <> 3   THROW 51000, N'Validacion fallida: dw.dim_sexo debe tener 3 filas.', 1;
    IF @cnt_dim_edad  <> 7   THROW 51000, N'Validacion fallida: dw.dim_rango_edad debe tener 7 filas.', 1;
    IF @cnt_dim_nac   <> 60  THROW 51000, N'Validacion fallida: dw.dim_nacionalidad debe tener 60 filas.', 1;
    IF @cnt_dim_var   <> 18  THROW 51000, N'Validacion fallida: dw.dim_variable debe tener 18 filas.', 1;
    IF @cnt_dim_dep   <> 53  THROW 51000, N'Validacion fallida: dw.dim_dependencia debe tener 53 filas.', 1;
    IF @cnt_dim_ind   <> 5   THROW 51000, N'Validacion fallida: dw.dim_indicador debe tener 5 filas.', 1;

    IF NOT EXISTS (SELECT 1 FROM dw.dim_provincia WHERE cod_provincia = '1608' AND provincia = N'PUTUMAYO')
        THROW 51001, N'Validacion fallida: cod_provincia 1608 debe resolverse como PUTUMAYO.', 1;
    IF NOT EXISTS (SELECT 1 FROM dw.dim_ubigeo WHERE ubigeo = '010201' AND distrito = N'BAGUA')
        THROW 51001, N'Validacion fallida: ubigeo 010201 debe resolverse como BAGUA (prioridad D1).', 1;
    IF NOT EXISTS (SELECT 1 FROM dw.dim_ubigeo WHERE ubigeo = '010206' AND distrito = N'LA PECA')
        THROW 51001, N'Validacion fallida: ubigeo 010206 debe resolverse como LA PECA (prioridad D1).', 1;
    IF NOT EXISTS (SELECT 1 FROM dw.dim_ubigeo WHERE ubigeo = '150144')
        THROW 51001, N'Validacion fallida: ubigeo 150144 (solo D2) debe existir en dw.dim_ubigeo.', 1;

    -- 5. Carga de las 4 tablas de hechos
    INSERT INTO dw.fact_denuncias (id_tiempo, id_fecha, id_ubigeo, id_modalidad, cantidad, es_anio_parcial)
    SELECT id_tiempo, id_fecha, id_ubigeo, id_modalidad, cantidad, es_anio_parcial
    FROM stg.vw_fact_denuncias;

    INSERT INTO dw.fact_desaparecidos (id_tiempo, id_fecha, id_ubigeo, id_sexo, id_rango_edad, id_nacionalidad, cantidad, es_anio_parcial)
    SELECT id_tiempo, id_fecha, id_ubigeo, id_sexo, id_rango_edad, id_nacionalidad, cantidad, es_anio_parcial
    FROM stg.vw_fact_desaparecidos;

    INSERT INTO dw.fact_produccion (id_tiempo, id_fecha, id_variable, id_dependencia, valor, es_anio_parcial)
    SELECT id_tiempo, id_fecha, id_variable, id_dependencia, valor, es_anio_parcial
    FROM stg.vw_fact_produccion;

    INSERT INTO dw.fact_victimizacion (id_tiempo, id_departamento, id_indicador, ambito, clasif, valor, es_anio_parcial)
    SELECT id_tiempo, id_departamento, id_indicador, ambito, clasif, valor, es_anio_parcial
    FROM stg.vw_fact_victimizacion;

    -- 6. Validacion de cero claves huerfanas en las 20 relaciones FK (17 hechos + 3 dim)
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

    -- 7. Validacion de cero duplicados por grano en las 4 tablas de hechos
    DECLARE @dup_den INT = (SELECT COUNT(*) FROM (SELECT 1 AS x FROM dw.fact_denuncias GROUP BY id_tiempo, id_ubigeo, id_modalidad HAVING COUNT(*) > 1) AS d);
    DECLARE @dup_des INT = (SELECT COUNT(*) FROM (SELECT 1 AS x FROM dw.fact_desaparecidos GROUP BY id_tiempo, id_ubigeo, id_sexo, id_rango_edad, id_nacionalidad HAVING COUNT(*) > 1) AS d);
    DECLARE @dup_pro INT = (SELECT COUNT(*) FROM (SELECT 1 AS x FROM dw.fact_produccion GROUP BY id_tiempo, id_variable, id_dependencia HAVING COUNT(*) > 1) AS d);
    DECLARE @dup_vic INT = (SELECT COUNT(*) FROM (SELECT 1 AS x FROM dw.fact_victimizacion GROUP BY id_tiempo, id_departamento, id_indicador HAVING COUNT(*) > 1) AS d);

    IF (@dup_den + @dup_des + @dup_pro + @dup_vic) <> 0
        THROW 51003, N'Validacion fallida: se detectaron duplicados de grano en tablas de hechos.', 1;

    -- 8. Reconciliacion exacta contra DataMarts origen y totales esperados
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

    SELECT
        @dw_cnt_d1 = COUNT(*),
        @dw_sum_d1 = SUM(CAST(cantidad AS BIGINT)),
        @dw_par_d1 = SUM(CASE WHEN es_anio_parcial = 1 THEN 1 ELSE 0 END)
    FROM dw.fact_denuncias;

    SELECT
        @dw_cnt_d2 = COUNT(*),
        @dw_sum_d2 = SUM(CAST(cantidad AS BIGINT)),
        @dw_par_d2 = SUM(CASE WHEN es_anio_parcial = 1 THEN 1 ELSE 0 END)
    FROM dw.fact_desaparecidos;

    SELECT
        @dw_cnt_d3 = COUNT(*),
        @dw_sum_d3 = SUM(CAST(valor AS DECIMAL(38,6))),
        @dw_par_d3 = SUM(CASE WHEN es_anio_parcial = 1 THEN 1 ELSE 0 END),
        @dw_ceros_d3 = SUM(CASE WHEN valor = 0 THEN 1 ELSE 0 END)
    FROM dw.fact_produccion;

    SELECT
        @dw_cnt_d4 = COUNT(*),
        @dw_sum_d4 = SUM(CAST(valor AS DECIMAL(38,6))),
        @dw_par_d4 = SUM(CASE WHEN es_anio_parcial = 1 THEN 1 ELSE 0 END),
        @dw_nac_d4 = SUM(CASE WHEN ambito = N'NACIONAL' THEN 1 ELSE 0 END)
    FROM dw.fact_victimizacion;

    IF @dw_cnt_d1 <> 378187 OR @dw_cnt_d1 <> @src_cnt_d1 OR @dw_sum_d1 <> 7614774 OR @dw_sum_d1 <> @src_sum_d1 OR @dw_par_d1 <> 37683
        THROW 51004, N'Validacion fallida: reconciliacion de dw.fact_denuncias vs DBDenunciasPoliciales.', 1;

    IF @dw_cnt_d2 <> 77331 OR @dw_cnt_d2 <> @src_cnt_d2 OR @dw_sum_d2 <> 142374 OR @dw_sum_d2 <> @src_sum_d2 OR @dw_par_d2 <> 0
        THROW 51005, N'Validacion fallida: reconciliacion de dw.fact_desaparecidos vs DBPersonasDesaparecidas.', 1;

    IF @dw_cnt_d3 <> 39096 OR @dw_cnt_d3 <> @src_cnt_d3 OR @dw_sum_d3 <> 2195845317.111756 OR @dw_sum_d3 <> @src_sum_d3 OR @dw_ceros_d3 <> 15458 OR @dw_par_d3 <> 8640
        THROW 51006, N'Validacion fallida: reconciliacion de dw.fact_produccion vs DBProduccionPolicial.', 1;

    IF @dw_cnt_d4 <> 1592 OR @dw_cnt_d4 <> @src_cnt_d4 OR @dw_sum_d4 <> 36287.6 OR @dw_sum_d4 <> @src_sum_d4 OR @dw_par_d4 <> 107 OR @dw_nac_d4 <> 58
        THROW 51007, N'Validacion fallida: reconciliacion de dw.fact_victimizacion vs DBVictimizacionConfianzaPNP.', 1;

    -- Guardar linea base para prueba de idempotencia Pass 2
    INSERT INTO #Pass1Baseline (tabla_destino, filas, control_suma)
    VALUES
        (N'dw.fact_denuncias',     @dw_cnt_d1, CAST(@dw_sum_d1 AS DECIMAL(38,6))),
        (N'dw.fact_desaparecidos', @dw_cnt_d2, CAST(@dw_sum_d2 AS DECIMAL(38,6))),
        (N'dw.fact_produccion',    @dw_cnt_d3, @dw_sum_d3),
        (N'dw.fact_victimizacion', @dw_cnt_d4, @dw_sum_d4);

    -- Registrar detalle por hecho en etl.ControlCargaDW
    INSERT INTO etl.ControlCargaDW (proceso, origen, tabla_destino, filas_origen, filas_cargadas, claves_huerfanas, control_suma, fecha_fin, estado, detalle)
    VALUES
        (N'06_dw_validacion_pass1_hecho', N'stg.vw_fact_denuncias',     N'dw.fact_denuncias',     @src_cnt_d1, @dw_cnt_d1, 0, CAST(@dw_sum_d1 AS DECIMAL(38,6)), SYSDATETIME(), N'EXITOSO', N'Reconciliacion exacta D1 (378,187 filas; 7,614,774 denuncias; 37,683 filas 2026 parciales).'),
        (N'06_dw_validacion_pass1_hecho', N'stg.vw_fact_desaparecidos', N'dw.fact_desaparecidos', @src_cnt_d2, @dw_cnt_d2, 0, CAST(@dw_sum_d2 AS DECIMAL(38,6)), SYSDATETIME(), N'EXITOSO', N'Reconciliacion exacta D2 (77,331 filas; 142,374 casos; 0 parciales).'),
        (N'06_dw_validacion_pass1_hecho', N'stg.vw_fact_produccion',    N'dw.fact_produccion',    @src_cnt_d3, @dw_cnt_d3, 0, @dw_sum_d3,                      SYSDATETIME(), N'EXITOSO', N'Reconciliacion exacta D3 (39,096 filas incl. 15,458 ceros; 8,640 filas 2026 parciales).'),
        (N'06_dw_validacion_pass1_hecho', N'stg.vw_fact_victimizacion', N'dw.fact_victimizacion', @src_cnt_d4, @dw_cnt_d4, 0, @dw_sum_d4,                      SYSDATETIME(), N'EXITOSO', N'Reconciliacion exacta D4 (1,592 filas incl. 58 NACIONAL y 107 de 2013 parciales).');

    SET @detalle_pass1 = CONCAT(
        N'Pass 1 exitoso. Dims=12 (27/196/1847/182/5113/7/3/7/60/18/53/5). ',
        N'Facts: denuncias=', @dw_cnt_d1, N' (', @dw_sum_d1, N'), ',
        N'desaparecidos=', @dw_cnt_d2, N' (', @dw_sum_d2, N'), ',
        N'produccion=', @dw_cnt_d3, N' (', @dw_sum_d3, N'), ',
        N'victimizacion=', @dw_cnt_d4, N' (', @dw_sum_d4, N'). Huerfanas=0.'
    );

    UPDATE etl.ControlCargaDW
    SET filas_origen   = @src_cnt_d1 + @src_cnt_d2 + @src_cnt_d3 + @src_cnt_d4,
        filas_cargadas = @dw_cnt_d1 + @dw_cnt_d2 + @dw_cnt_d3 + @dw_cnt_d4,
        claves_huerfanas = 0,
        fecha_fin      = SYSDATETIME(),
        estado         = N'EXITOSO',
        detalle        = @detalle_pass1
    WHERE id_carga_dw = @id_carga_pass1;

    PRINT N'Pass 1 completado y reconciliado correctamente (0 huerfanas, 0 duplicados).';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0
        ROLLBACK TRANSACTION;

    UPDATE etl.ControlCargaDW
    SET fecha_fin = SYSDATETIME(),
        estado    = N'FALLIDO',
        detalle   = LEFT(ERROR_MESSAGE(), 4000)
    WHERE id_carga_dw = @id_carga_pass1;

    THROW;
END CATCH;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* ============================================================================
   VALIDACION ANALITICA DE LAS 5 PREGUNTAS GUIA (Q1 - Q5)
   ============================================================================ */

PRINT N'=== Validacion de reglas analiticas Q1-Q5 ===';

-- Q1: Denuncias 2018-2025 (excluir 2026 con es_anio_parcial = 0)
DECLARE @q1_2018_2025 BIGINT = (
    SELECT SUM(CAST(f.cantidad AS BIGINT))
    FROM dw.fact_denuncias AS f
    INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
    WHERE f.es_anio_parcial = 0
      AND t.anio BETWEEN 2018 AND 2025
);
DECLARE @q1_2026_parcial BIGINT = (
    SELECT SUM(CAST(f.cantidad AS BIGINT))
    FROM dw.fact_denuncias AS f
    WHERE f.es_anio_parcial = 1
);

IF @q1_2018_2025 <> 6866606 OR @q1_2026_parcial <> 748168
    THROW 51008, N'Validacion Q1 fallida: denuncias 2018-2025 deben sumar 6,866,606 y 2026 parcial 748,168.', 1;

SELECT
    N'Q1_Denuncias_Modalidad_2018_2025' AS consulta,
    m.modalidad,
    SUM(CAST(f.cantidad AS BIGINT)) AS total_denuncias
FROM dw.fact_denuncias AS f
INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
INNER JOIN dw.dim_modalidad AS m ON m.id_modalidad = f.id_modalidad
WHERE f.es_anio_parcial = 0
  AND t.anio BETWEEN 2018 AND 2025
GROUP BY m.modalidad
ORDER BY total_denuncias DESC;

SELECT
    N'Q1_Denuncias_Anual_2018_2025' AS consulta,
    t.anio,
    SUM(CAST(f.cantidad AS BIGINT)) AS total_denuncias
FROM dw.fact_denuncias AS f
INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
WHERE f.es_anio_parcial = 0
  AND t.anio BETWEEN 2018 AND 2025
GROUP BY t.anio
ORDER BY t.anio;

SELECT
    N'Q1_Denuncias_Mensual_Estacionalidad_2018_2025' AS consulta,
    t.mes_numero,
    t.mes_nombre,
    SUM(CAST(f.cantidad AS BIGINT)) AS total_denuncias,
    CAST(SUM(CAST(f.cantidad AS DECIMAL(18,2))) / NULLIF(COUNT(DISTINCT t.anio), 0) AS DECIMAL(18,2)) AS promedio_mensual_anual
FROM dw.fact_denuncias AS f
INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
WHERE f.es_anio_parcial = 0
  AND t.anio BETWEEN 2018 AND 2025
GROUP BY t.mes_numero, t.mes_nombre
ORDER BY t.mes_numero;

-- Q2: Desaparecidos 2019-2025 (es_menor_18 = 1 y sentinela NO INFORMADO)
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

SELECT
    N'Q2_Desaparecidos_Perfil_2019_2025' AS consulta,
    s.codigo_sexo,
    s.sexo_descripcion,
    re.rango_edad,
    re.es_menor_18,
    re.orden_edad,
    SUM(CAST(f.cantidad AS BIGINT)) AS total_casos
FROM dw.fact_desaparecidos AS f
INNER JOIN dw.dim_sexo AS s ON s.id_sexo = f.id_sexo
INNER JOIN dw.dim_rango_edad AS re ON re.id_rango_edad = f.id_rango_edad
GROUP BY s.codigo_sexo, s.sexo_descripcion, re.rango_edad, re.es_menor_18, re.orden_edad
ORDER BY total_casos DESC, re.orden_edad;

-- Q3: Produccion Policial 2023-2025 (separada por unidad_medida sin mezclar magnitudes)
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

SELECT
    N'Q3_Produccion_2023_2025_Por_Unidad' AS consulta,
    t.anio,
    v.unidad_medida,
    v.variable,
    dep.dir_reg_fre,
    SUM(f.valor) AS total_valor
FROM dw.fact_produccion AS f
INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
INNER JOIN dw.dim_variable AS v ON v.id_variable = f.id_variable
INNER JOIN dw.dim_dependencia AS dep ON dep.id_dependencia = f.id_dependencia
WHERE f.es_anio_parcial = 0
  AND t.anio BETWEEN 2023 AND 2025
GROUP BY t.anio, v.unidad_medida, v.variable, dep.dir_reg_fre
ORDER BY t.anio, v.unidad_medida, v.variable, dep.dir_reg_fre;

-- Q4: Victimizacion y Confianza PNP 2014-2024 (es_anio_parcial = 0 y ambito = 'DEPARTAMENTO', usando AVG)
DECLARE @q4_rows INT = (
    SELECT COUNT(*)
    FROM dw.fact_victimizacion AS f
    INNER JOIN dw.dim_departamento AS d ON d.id_departamento = f.id_departamento
    WHERE f.es_anio_parcial = 0
      AND d.ambito = N'DEPARTAMENTO'
);
DECLARE @q4_invalid INT = (
    SELECT COUNT(*)
    FROM dw.fact_victimizacion AS f
    INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
    INNER JOIN dw.dim_departamento AS d ON d.id_departamento = f.id_departamento
    WHERE f.es_anio_parcial = 0
      AND d.ambito = N'DEPARTAMENTO'
      AND (t.anio = 2013 OR f.ambito = N'NACIONAL' OR d.es_nacional = 1)
);

IF @q4_rows <> 1430 OR @q4_invalid <> 0
    THROW 51016, N'Validacion Q4 fallida: debe haber exactamente 1,430 filas departamentales completas (2014-2024) sin filas nacionales ni de 2013.', 1;

SELECT
    N'Q4_Percepcion_Inseguridad_2014_2024' AS consulta,
    d.departamento,
    CAST(AVG(f.valor) AS DECIMAL(5,2)) AS promedio_porcentaje
FROM dw.fact_victimizacion AS f
INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
INNER JOIN dw.dim_departamento AS d ON d.id_departamento = f.id_departamento
INNER JOIN dw.dim_indicador AS i ON i.id_indicador = f.id_indicador
WHERE f.es_anio_parcial = 0
  AND d.ambito = N'DEPARTAMENTO'
  AND t.anio BETWEEN 2014 AND 2024
  AND i.indicador = N'PORCENTAJE DE PERCEPCIÓN DE INSEGURIDAD AL CAMINAR SOLO(A) DE NOCHE EN SU ZONA O BARRIO'
GROUP BY d.departamento
ORDER BY promedio_porcentaje DESC;

SELECT
    N'Q4_Confianza_PNP_2014_2024' AS consulta,
    d.departamento,
    CAST(AVG(f.valor) AS DECIMAL(5,2)) AS promedio_porcentaje
FROM dw.fact_victimizacion AS f
INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
INNER JOIN dw.dim_departamento AS d ON d.id_departamento = f.id_departamento
INNER JOIN dw.dim_indicador AS i ON i.id_indicador = f.id_indicador
WHERE f.es_anio_parcial = 0
  AND d.ambito = N'DEPARTAMENTO'
  AND t.anio BETWEEN 2014 AND 2024
  AND i.indicador = N'PORCENTAJE DE CONFIANZA EN LA PNP'
GROUP BY d.departamento
ORDER BY promedio_porcentaje ASC;

-- Q5: Cruzada 2019-2025 por departamento y anio
DECLARE @q5_dept_cnt INT = (
    SELECT COUNT(DISTINCT d.id_departamento)
    FROM dw.dim_departamento AS d
    WHERE d.ambito = N'DEPARTAMENTO'
);
DECLARE @q5_vic_2025 INT = (
    SELECT COUNT(*)
    FROM dw.fact_victimizacion AS f
    INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
    WHERE t.anio = 2025
);

IF @q5_dept_cnt <> 26 OR @q5_vic_2025 <> 0
    THROW 51017, N'Validacion Q5 fallida: deben existir 26 departamentos y 0 filas de victimizacion en 2025.', 1;

WITH den AS (
    SELECT d.id_departamento, t.anio, SUM(CAST(f.cantidad AS BIGINT)) AS total_denuncias
    FROM dw.fact_denuncias AS f
    INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
    INNER JOIN dw.dim_ubigeo AS u ON u.id_ubigeo = f.id_ubigeo
    INNER JOIN dw.dim_departamento AS d ON d.id_departamento = u.id_departamento
    WHERE f.es_anio_parcial = 0 AND t.anio BETWEEN 2019 AND 2025
    GROUP BY d.id_departamento, t.anio
),
des AS (
    SELECT d.id_departamento, t.anio, SUM(CAST(f.cantidad AS BIGINT)) AS total_desaparecidos
    FROM dw.fact_desaparecidos AS f
    INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
    INNER JOIN dw.dim_ubigeo AS u ON u.id_ubigeo = f.id_ubigeo
    INNER JOIN dw.dim_departamento AS d ON d.id_departamento = u.id_departamento
    WHERE f.es_anio_parcial = 0 AND t.anio BETWEEN 2019 AND 2025
    GROUP BY d.id_departamento, t.anio
),
vic AS (
    SELECT
        f.id_departamento,
        t.anio,
        MAX(CASE WHEN i.indicador = N'PORCENTAJE DE PERCEPCIÓN DE INSEGURIDAD AL CAMINAR SOLO(A) DE NOCHE EN SU ZONA O BARRIO' THEN f.valor END) AS pct_inseguridad,
        MAX(CASE WHEN i.indicador = N'PORCENTAJE DE CONFIANZA EN LA PNP' THEN f.valor END) AS pct_confianza_pnp
    FROM dw.fact_victimizacion AS f
    INNER JOIN dw.dim_tiempo AS t ON t.id_tiempo = f.id_tiempo
    INNER JOIN dw.dim_indicador AS i ON i.id_indicador = f.id_indicador
    WHERE f.es_anio_parcial = 0
      AND f.ambito = N'DEPARTAMENTO'
      AND t.anio BETWEEN 2019 AND 2025
    GROUP BY f.id_departamento, t.anio
),
anios AS (
    SELECT DISTINCT anio
    FROM dw.dim_tiempo
    WHERE anio BETWEEN 2019 AND 2025
)
SELECT
    N'Q5_Cruzada_2019_2025' AS consulta,
    d.departamento,
    a.anio,
    ISNULL(den.total_denuncias, 0) AS total_denuncias,
    ISNULL(des.total_desaparecidos, 0) AS total_desaparecidos,
    vic.pct_inseguridad,
    vic.pct_confianza_pnp
FROM dw.dim_departamento AS d
CROSS JOIN anios AS a
LEFT JOIN den ON den.id_departamento = d.id_departamento AND den.anio = a.anio
LEFT JOIN des ON des.id_departamento = d.id_departamento AND des.anio = a.anio
LEFT JOIN vic ON vic.id_departamento = d.id_departamento AND vic.anio = a.anio
WHERE d.ambito = N'DEPARTAMENTO'
ORDER BY d.departamento, a.anio;

PRINT N'Validacion Q1-Q5 completada correctamente.';
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* ============================================================================
   PASS 2: PRUEBA DE IDEMPOTENCIA (TRUNCATE HECHOS + RECARGA SIN DUPLICADOS)
   ============================================================================ */

PRINT N'=== PASS 2: Prueba de idempotencia (TRUNCATE hechos + recarga) ===';

DECLARE @id_carga_pass2 INT;

INSERT INTO etl.ControlCargaDW (
    proceso, origen, tabla_destino, filas_origen, filas_cargadas, claves_huerfanas, control_suma, estado, detalle
)
VALUES (
    N'06_dw_validacion_pass2_idempotencia',
    N'stg.vw_fact_*',
    N'DW_ProyectoEF (4 fact tables)',
    NULL,
    0,
    0,
    NULL,
    N'EN_PROCESO',
    N'Inicio de prueba de idempotencia mediante TRUNCATE de tablas de hechos y recarga.'
);
SET @id_carga_pass2 = CAST(SCOPE_IDENTITY() AS INT);

BEGIN TRY
    TRUNCATE TABLE dw.fact_denuncias;
    TRUNCATE TABLE dw.fact_desaparecidos;
    TRUNCATE TABLE dw.fact_produccion;
    TRUNCATE TABLE dw.fact_victimizacion;

    INSERT INTO dw.fact_denuncias (id_tiempo, id_fecha, id_ubigeo, id_modalidad, cantidad, es_anio_parcial)
    SELECT id_tiempo, id_fecha, id_ubigeo, id_modalidad, cantidad, es_anio_parcial
    FROM stg.vw_fact_denuncias;

    INSERT INTO dw.fact_desaparecidos (id_tiempo, id_fecha, id_ubigeo, id_sexo, id_rango_edad, id_nacionalidad, cantidad, es_anio_parcial)
    SELECT id_tiempo, id_fecha, id_ubigeo, id_sexo, id_rango_edad, id_nacionalidad, cantidad, es_anio_parcial
    FROM stg.vw_fact_desaparecidos;

    INSERT INTO dw.fact_produccion (id_tiempo, id_fecha, id_variable, id_dependencia, valor, es_anio_parcial)
    SELECT id_tiempo, id_fecha, id_variable, id_dependencia, valor, es_anio_parcial
    FROM stg.vw_fact_produccion;

    INSERT INTO dw.fact_victimizacion (id_tiempo, id_departamento, id_indicador, ambito, clasif, valor, es_anio_parcial)
    SELECT id_tiempo, id_departamento, id_indicador, ambito, clasif, valor, es_anio_parcial
    FROM stg.vw_fact_victimizacion;

    -- Comparar contra Pass 1
    DECLARE @p2_cnt_d1 INT, @p2_sum_d1 DECIMAL(38,6);
    DECLARE @p2_cnt_d2 INT, @p2_sum_d2 DECIMAL(38,6);
    DECLARE @p2_cnt_d3 INT, @p2_sum_d3 DECIMAL(38,6);
    DECLARE @p2_cnt_d4 INT, @p2_sum_d4 DECIMAL(38,6);

    SELECT @p2_cnt_d1 = COUNT(*), @p2_sum_d1 = SUM(CAST(cantidad AS DECIMAL(38,6))) FROM dw.fact_denuncias;
    SELECT @p2_cnt_d2 = COUNT(*), @p2_sum_d2 = SUM(CAST(cantidad AS DECIMAL(38,6))) FROM dw.fact_desaparecidos;
    SELECT @p2_cnt_d3 = COUNT(*), @p2_sum_d3 = SUM(CAST(valor AS DECIMAL(38,6)))    FROM dw.fact_produccion;
    SELECT @p2_cnt_d4 = COUNT(*), @p2_sum_d4 = SUM(CAST(valor AS DECIMAL(38,6)))    FROM dw.fact_victimizacion;

    IF EXISTS (
        SELECT 1
        FROM #Pass1Baseline AS b
        INNER JOIN (
            SELECT N'dw.fact_denuncias'     AS tabla_destino, @p2_cnt_d1 AS filas, @p2_sum_d1 AS control_suma
            UNION ALL
            SELECT N'dw.fact_desaparecidos' AS tabla_destino, @p2_cnt_d2 AS filas, @p2_sum_d2 AS control_suma
            UNION ALL
            SELECT N'dw.fact_produccion'    AS tabla_destino, @p2_cnt_d3 AS filas, @p2_sum_d3 AS control_suma
            UNION ALL
            SELECT N'dw.fact_victimizacion' AS tabla_destino, @p2_cnt_d4 AS filas, @p2_sum_d4 AS control_suma
        ) AS p2 ON p2.tabla_destino = b.tabla_destino
        WHERE b.filas <> p2.filas OR b.control_suma <> p2.control_suma
    )
        THROW 51018, N'Validacion Pass 2 fallida: conteos o sumas difieren respecto a Pass 1 tras TRUNCATE y recarga.', 1;

    -- Verificar cero duplicados tras recarga Pass 2
    DECLARE @p2_dup INT = 0;
    SELECT @p2_dup = @p2_dup + COUNT(*) FROM (SELECT 1 AS x FROM dw.fact_denuncias     GROUP BY id_tiempo, id_ubigeo, id_modalidad HAVING COUNT(*) > 1) AS x;
    SELECT @p2_dup = @p2_dup + COUNT(*) FROM (SELECT 1 AS x FROM dw.fact_desaparecidos GROUP BY id_tiempo, id_ubigeo, id_sexo, id_rango_edad, id_nacionalidad HAVING COUNT(*) > 1) AS x;
    SELECT @p2_dup = @p2_dup + COUNT(*) FROM (SELECT 1 AS x FROM dw.fact_produccion    GROUP BY id_tiempo, id_variable, id_dependencia HAVING COUNT(*) > 1) AS x;
    SELECT @p2_dup = @p2_dup + COUNT(*) FROM (SELECT 1 AS x FROM dw.fact_victimizacion GROUP BY id_tiempo, id_departamento, id_indicador HAVING COUNT(*) > 1) AS x;

    IF @p2_dup <> 0
        THROW 51019, N'Validacion Pass 2 fallida: se detectaron duplicados de grano tras la recarga.', 1;

    -- Verificar 0 huerfanas tras recarga Pass 2
    DECLARE @p2_huerfanas INT = 0;
    SELECT @p2_huerfanas = @p2_huerfanas + COUNT(*) FROM dw.fact_denuncias AS f LEFT JOIN dw.dim_ubigeo AS u ON u.id_ubigeo = f.id_ubigeo WHERE u.id_ubigeo IS NULL;
    SELECT @p2_huerfanas = @p2_huerfanas + COUNT(*) FROM dw.fact_desaparecidos AS f LEFT JOIN dw.dim_ubigeo AS u ON u.id_ubigeo = f.id_ubigeo WHERE u.id_ubigeo IS NULL;
    SELECT @p2_huerfanas = @p2_huerfanas + COUNT(*) FROM dw.fact_produccion AS f LEFT JOIN dw.dim_variable AS v ON v.id_variable = f.id_variable WHERE v.id_variable IS NULL;
    SELECT @p2_huerfanas = @p2_huerfanas + COUNT(*) FROM dw.fact_victimizacion AS f LEFT JOIN dw.dim_departamento AS d ON d.id_departamento = f.id_departamento WHERE d.id_departamento IS NULL;

    IF @p2_huerfanas <> 0
        THROW 51020, N'Validacion Pass 2 fallida: claves huerfanas tras recarga de hechos.', 1;

    UPDATE etl.ControlCargaDW
    SET filas_origen     = @p2_cnt_d1 + @p2_cnt_d2 + @p2_cnt_d3 + @p2_cnt_d4,
        filas_cargadas   = @p2_cnt_d1 + @p2_cnt_d2 + @p2_cnt_d3 + @p2_cnt_d4,
        claves_huerfanas = 0,
        fecha_fin        = SYSDATETIME(),
        estado           = N'EXITOSO',
        detalle          = N'Pass 2 idempotente EXITOSO: TRUNCATE de 4 hechos y recarga con paridad exacta vs Pass 1 (0 duplicados, 0 huerfanas).'
    WHERE id_carga_dw = @id_carga_pass2;

    DROP TABLE #Pass1Baseline;
    PRINT N'Pass 2 completado: idempotencia verificada al 100%.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0
        ROLLBACK TRANSACTION;

    UPDATE etl.ControlCargaDW
    SET fecha_fin = SYSDATETIME(),
        estado    = N'FALLIDO',
        detalle   = LEFT(ERROR_MESSAGE(), 4000)
    WHERE id_carga_dw = @id_carga_pass2;

    THROW;
END CATCH;

SELECT
    id_carga_dw,
    proceso,
    origen,
    tabla_destino,
    filas_origen,
    filas_cargadas,
    claves_huerfanas,
    control_suma,
    fecha_inicio,
    fecha_fin,
    estado,
    detalle
FROM etl.ControlCargaDW
ORDER BY id_carga_dw;

PRINT N'Validacion integral DW_ProyectoEF finalizada con exito.';
GO
