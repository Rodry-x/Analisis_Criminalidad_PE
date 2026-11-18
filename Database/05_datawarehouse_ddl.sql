/* ============================================================================
   DataWarehouse: DW_ProyectoEF
   ----------------------------------------------------------------------------
   Modelo en constelacion (4 tablas de hecho + 12 dimensiones conformadas).

   Capas:
     dw   -> 12 dimensiones conformadas/especificas y 4 tablas de hechos.
     stg  -> 16 vistas de preparacion (12 dim + 4 fact) sobre los 4 DataMarts.
     etl  -> tabla de auditoria y control de carga (etl.ControlCargaDW).

   DataMarts origen:
     1. DBDenunciasPoliciales.dm.DenunciasPoliciales         (2018-2026)
     2. DBPersonasDesaparecidas.dm.PersonasDesaparecidas     (2019-2025)
     3. DBProduccionPolicial.dm.ProduccionPolicial           (2023-2026)
     4. DBVictimizacionConfianzaPNP.dm.VictimizacionConfianzaPNP (2013-2024)

   Preguntas guia que soporta este modelo:
     Q1. Denuncias (2018-2025): modalidades recurrentes, evolucion anual/mensual
         y estacionalidad, excluyendo 2026 mediante es_anio_parcial = 0.
     Q2. Desaparecidos (2019-2025): perfil por sexo y rango de edad, incluyendo
         bandera es_menor_18 y sentinela 'NO INFORMADO'.
     Q3. Produccion Policial (2023-2025): operativos, detenidos, bandas, drogas
         y dinero incautado separados estrictamente por unidad_medida.
     Q4. Victimizacion y Confianza PNP (2014-2024): percepcion de inseguridad y
         confianza filtrando ambito = 'DEPARTAMENTO' y promediando porcentajes.
     Q5. Cruzada (2019-2025): comparacion por departamento y anio entre
         denuncias, personas desaparecidas y victimizacion/confianza.

   Nota: Este script crea exclusivamente la estructura (0 filas precargadas).
         La carga y validacion se ejecutan en Database/06_dw_validacion.sql
         o mediante el proyecto SSIS Proyecto_EF_SSIS.
   ============================================================================ */

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [master];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF DB_ID(N'DW_ProyectoEF') IS NOT NULL
BEGIN
    PRINT N'Eliminando base de datos DW_ProyectoEF existente para recreacion limpia...';
    ALTER DATABASE [DW_ProyectoEF] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE [DW_ProyectoEF];
END
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

PRINT N'Creando base de datos DW_ProyectoEF...';
CREATE DATABASE [DW_ProyectoEF];
GO

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
   1. ESQUEMAS (stg, dw, etl)
   ============================================================================ */

IF SCHEMA_ID(N'stg') IS NULL
    EXEC(N'CREATE SCHEMA stg');
IF SCHEMA_ID(N'dw') IS NULL
    EXEC(N'CREATE SCHEMA dw');
IF SCHEMA_ID(N'etl') IS NULL
    EXEC(N'CREATE SCHEMA etl');
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* ============================================================================
   2. TABLA DE CONTROL ETL (etl.ControlCargaDW)
   ============================================================================ */

CREATE TABLE etl.ControlCargaDW (
    id_carga_dw      INT IDENTITY(1,1) NOT NULL,
    proceso          NVARCHAR(100)     NOT NULL,
    origen           NVARCHAR(150)     NOT NULL,
    tabla_destino    NVARCHAR(128)     NOT NULL,
    filas_origen     INT               NULL,
    filas_cargadas   INT               NOT NULL,
    claves_huerfanas INT               NOT NULL CONSTRAINT DF_ControlCargaDW_claves_huerfanas DEFAULT (0),
    control_suma     DECIMAL(38,6)     NULL,
    fecha_inicio     DATETIME2(0)      NOT NULL CONSTRAINT DF_ControlCargaDW_fecha_inicio     DEFAULT (SYSDATETIME()),
    fecha_fin        DATETIME2(0)      NULL,
    estado           NVARCHAR(20)      NOT NULL,
    detalle          NVARCHAR(MAX)     NULL,
    CONSTRAINT PK_ControlCargaDW PRIMARY KEY CLUSTERED (id_carga_dw),
    CONSTRAINT CK_ControlCargaDW_estado CHECK (estado IN (N'EN_PROCESO', N'EXITOSO', N'FALLIDO'))
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE NONCLUSTERED INDEX IX_ControlCargaDW_fecha_inicio
    ON etl.ControlCargaDW (fecha_inicio DESC)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* ============================================================================
   3. DIMENSIONES CONFORMADAS Y ESPECIFICAS (12 tablas dw.dim_*)
   ============================================================================ */

-- 3.1 dw.dim_departamento (27 filas: 26 departamentos + sentinela 0 = NACIONAL)
CREATE TABLE dw.dim_departamento (
    id_departamento INT IDENTITY(1,1) NOT NULL,
    cod_ubicacion   INT               NOT NULL,
    departamento    NVARCHAR(60)      NOT NULL,
    ambito          NVARCHAR(15)      NOT NULL,
    es_nacional     BIT               NOT NULL,
    macroregion     NVARCHAR(20)      NOT NULL,
    CONSTRAINT PK_dim_departamento PRIMARY KEY CLUSTERED (id_departamento),
    CONSTRAINT UQ_dim_departamento_cod_ubicacion UNIQUE NONCLUSTERED (cod_ubicacion)
        WITH (FILLFACTOR = 90),
    CONSTRAINT UQ_dim_departamento_departamento UNIQUE NONCLUSTERED (departamento)
        WITH (FILLFACTOR = 90),
    CONSTRAINT CK_dim_departamento_ambito CHECK (ambito IN (N'NACIONAL', N'DEPARTAMENTO')),
    CONSTRAINT CK_dim_departamento_macroregion CHECK (macroregion IN (N'NACIONAL', N'COSTA', N'SIERRA', N'SELVA')),
    CONSTRAINT CK_dim_departamento_coherencia CHECK (
        (ambito = N'NACIONAL' AND es_nacional = 1 AND cod_ubicacion = 0 AND departamento = N'NACIONAL' AND macroregion = N'NACIONAL')
        OR
        (ambito = N'DEPARTAMENTO' AND es_nacional = 0 AND cod_ubicacion > 0 AND departamento <> N'NACIONAL' AND macroregion IN (N'COSTA', N'SIERRA', N'SELVA'))
    )
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 3.2 dw.dim_provincia (196 filas; 1608 -> PUTUMAYO)
CREATE TABLE dw.dim_provincia (
    id_provincia    INT IDENTITY(1,1) NOT NULL,
    id_departamento INT               NOT NULL,
    cod_provincia   CHAR(4)           NOT NULL,
    provincia       NVARCHAR(100)     NOT NULL,
    CONSTRAINT PK_dim_provincia PRIMARY KEY CLUSTERED (id_provincia),
    CONSTRAINT FK_dim_provincia_departamento FOREIGN KEY (id_departamento)
        REFERENCES dw.dim_departamento (id_departamento),
    CONSTRAINT UQ_dim_provincia_cod_provincia UNIQUE NONCLUSTERED (cod_provincia)
        WITH (FILLFACTOR = 90),
    CONSTRAINT CK_dim_provincia_cod CHECK (cod_provincia LIKE '[0-9][0-9][0-9][0-9]')
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE NONCLUSTERED INDEX IX_dim_provincia_departamento
    ON dw.dim_provincia (id_departamento)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 3.3 dw.dim_ubigeo (1,847 filas: union D1 + D2; prioridad D1 en 010201 y 010206)
CREATE TABLE dw.dim_ubigeo (
    id_ubigeo       INT IDENTITY(1,1) NOT NULL,
    id_provincia    INT               NOT NULL,
    id_departamento INT               NOT NULL,
    ubigeo          CHAR(6)           NOT NULL,
    distrito        NVARCHAR(120)     NOT NULL,
    CONSTRAINT PK_dim_ubigeo PRIMARY KEY CLUSTERED (id_ubigeo),
    CONSTRAINT FK_dim_ubigeo_provincia FOREIGN KEY (id_provincia)
        REFERENCES dw.dim_provincia (id_provincia),
    CONSTRAINT FK_dim_ubigeo_departamento FOREIGN KEY (id_departamento)
        REFERENCES dw.dim_departamento (id_departamento),
    CONSTRAINT UQ_dim_ubigeo_ubigeo UNIQUE NONCLUSTERED (ubigeo)
        WITH (FILLFACTOR = 90),
    CONSTRAINT CK_dim_ubigeo_ubigeo CHECK (ubigeo LIKE '[0-9][0-9][0-9][0-9][0-9][0-9]')
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE NONCLUSTERED INDEX IX_dim_ubigeo_provincia
    ON dw.dim_ubigeo (id_provincia)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_dim_ubigeo_departamento
    ON dw.dim_ubigeo (id_departamento)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 3.4 dw.dim_tiempo (182 filas: 2013..2026 x mes 0..12; sin es_anio_parcial)
CREATE TABLE dw.dim_tiempo (
    id_tiempo        INT IDENTITY(1,1) NOT NULL,
    anio             SMALLINT          NOT NULL,
    mes_numero       TINYINT           NOT NULL,
    mes_nombre       NVARCHAR(20)      NOT NULL,
    mes_corto        NVARCHAR(10)      NOT NULL,
    trimestre        TINYINT           NOT NULL,
    trimestre_nombre NVARCHAR(10)      NOT NULL,
    es_anual         BIT               NOT NULL,
    periodo_label    NVARCHAR(15)      NOT NULL,
    CONSTRAINT PK_dim_tiempo PRIMARY KEY CLUSTERED (id_tiempo),
    CONSTRAINT UQ_dim_tiempo_anio_mes UNIQUE NONCLUSTERED (anio, mes_numero)
        WITH (FILLFACTOR = 90),
    CONSTRAINT CK_dim_tiempo_anio CHECK (anio BETWEEN 2013 AND 2100),
    CONSTRAINT CK_dim_tiempo_mes CHECK (mes_numero BETWEEN 0 AND 12),
    CONSTRAINT CK_dim_tiempo_trimestre_coherencia CHECK (
        (mes_numero = 0 AND trimestre = 0 AND es_anual = 1 AND mes_nombre = N'ANUAL' AND mes_corto = N'ANUAL' AND trimestre_nombre = N'ANUAL')
        OR
        (mes_numero BETWEEN 1 AND 12 AND trimestre BETWEEN 1 AND 4 AND es_anual = 0)
    )
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 3.5 dw.dim_fecha (5,113 filas diarias continuas: 2013-01-01 .. 2026-12-31)
CREATE TABLE dw.dim_fecha (
    id_fecha          INT IDENTITY(1,1) NOT NULL,
    fecha             DATE              NOT NULL,
    anio              SMALLINT          NOT NULL,
    mes               TINYINT           NOT NULL,
    dia               TINYINT           NOT NULL,
    mes_nombre        NVARCHAR(20)      NOT NULL,
    trimestre         TINYINT           NOT NULL,
    trimestre_nombre  NVARCHAR(10)      NOT NULL,
    es_primer_dia_mes BIT               NOT NULL,
    CONSTRAINT PK_dim_fecha PRIMARY KEY CLUSTERED (id_fecha),
    CONSTRAINT UQ_dim_fecha_fecha UNIQUE NONCLUSTERED (fecha)
        WITH (FILLFACTOR = 90),
    CONSTRAINT CK_dim_fecha_anio CHECK (anio BETWEEN 2013 AND 2100),
    CONSTRAINT CK_dim_fecha_mes CHECK (mes BETWEEN 1 AND 12),
    CONSTRAINT CK_dim_fecha_dia CHECK (dia BETWEEN 1 AND 31),
    CONSTRAINT CK_dim_fecha_trimestre CHECK (trimestre BETWEEN 1 AND 4)
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 3.6 dw.dim_modalidad (7 filas)
CREATE TABLE dw.dim_modalidad (
    id_modalidad INT IDENTITY(1,1) NOT NULL,
    modalidad    NVARCHAR(100)     NOT NULL,
    CONSTRAINT PK_dim_modalidad PRIMARY KEY CLUSTERED (id_modalidad),
    CONSTRAINT UQ_dim_modalidad_modalidad UNIQUE NONCLUSTERED (modalidad)
        WITH (FILLFACTOR = 90)
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 3.7 dw.dim_sexo (3 filas: F, M, NO INFORMADO)
CREATE TABLE dw.dim_sexo (
    id_sexo          INT IDENTITY(1,1) NOT NULL,
    codigo_sexo      NVARCHAR(15)      NOT NULL,
    sexo_descripcion NVARCHAR(30)      NOT NULL,
    CONSTRAINT PK_dim_sexo PRIMARY KEY CLUSTERED (id_sexo),
    CONSTRAINT UQ_dim_sexo_codigo UNIQUE NONCLUSTERED (codigo_sexo)
        WITH (FILLFACTOR = 90),
    CONSTRAINT CK_dim_sexo_codigo CHECK (codigo_sexo IN (N'F', N'M', N'NO INFORMADO'))
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 3.8 dw.dim_rango_edad (7 filas con es_menor_18 y orden_edad 1..7)
CREATE TABLE dw.dim_rango_edad (
    id_rango_edad INT IDENTITY(1,1) NOT NULL,
    rango_edad    NVARCHAR(30)      NOT NULL,
    es_menor_18   BIT               NOT NULL,
    orden_edad    TINYINT           NOT NULL,
    CONSTRAINT PK_dim_rango_edad PRIMARY KEY CLUSTERED (id_rango_edad),
    CONSTRAINT UQ_dim_rango_edad_rango UNIQUE NONCLUSTERED (rango_edad)
        WITH (FILLFACTOR = 90),
    CONSTRAINT UQ_dim_rango_edad_orden UNIQUE NONCLUSTERED (orden_edad)
        WITH (FILLFACTOR = 90),
    CONSTRAINT CK_dim_rango_edad_orden CHECK (orden_edad BETWEEN 1 AND 7)
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 3.9 dw.dim_nacionalidad (60 filas)
CREATE TABLE dw.dim_nacionalidad (
    id_nacionalidad INT IDENTITY(1,1) NOT NULL,
    nacionalidad    NVARCHAR(60)      NOT NULL,
    CONSTRAINT PK_dim_nacionalidad PRIMARY KEY CLUSTERED (id_nacionalidad),
    CONSTRAINT UQ_dim_nacionalidad_nacionalidad UNIQUE NONCLUSTERED (nacionalidad)
        WITH (FILLFACTOR = 90)
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 3.10 dw.dim_variable (18 filas en 9 unidades de medida)
CREATE TABLE dw.dim_variable (
    id_variable        INT IDENTITY(1,1) NOT NULL,
    variable           NVARCHAR(100)     NOT NULL,
    unidad_medida      NVARCHAR(30)      NOT NULL,
    categoria_variable NVARCHAR(40)      NOT NULL,
    CONSTRAINT PK_dim_variable PRIMARY KEY CLUSTERED (id_variable),
    CONSTRAINT UQ_dim_variable_variable UNIQUE NONCLUSTERED (variable)
        WITH (FILLFACTOR = 90)
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE NONCLUSTERED INDEX IX_dim_variable_unidad
    ON dw.dim_variable (unidad_medida)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 3.11 dw.dim_dependencia (53 filas)
CREATE TABLE dw.dim_dependencia (
    id_dependencia INT IDENTITY(1,1) NOT NULL,
    dependencia    NVARCHAR(60)      NOT NULL,
    dir_reg_fre    NVARCHAR(30)      NOT NULL,
    CONSTRAINT PK_dim_dependencia PRIMARY KEY CLUSTERED (id_dependencia),
    CONSTRAINT UQ_dim_dependencia_dependencia UNIQUE NONCLUSTERED (dependencia)
        WITH (FILLFACTOR = 90)
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE NONCLUSTERED INDEX IX_dim_dependencia_dir_reg_fre
    ON dw.dim_dependencia (dir_reg_fre)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 3.12 dw.dim_indicador (5 filas)
CREATE TABLE dw.dim_indicador (
    id_indicador    INT IDENTITY(1,1) NOT NULL,
    indicador       NVARCHAR(200)     NOT NULL,
    indicador_corto NVARCHAR(60)      NOT NULL,
    CONSTRAINT PK_dim_indicador PRIMARY KEY CLUSTERED (id_indicador),
    CONSTRAINT UQ_dim_indicador_indicador UNIQUE NONCLUSTERED (indicador)
        WITH (FILLFACTOR = 90),
    CONSTRAINT UQ_dim_indicador_indicador_corto UNIQUE NONCLUSTERED (indicador_corto)
        WITH (FILLFACTOR = 90)
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* ============================================================================
   4. TABLAS DE HECHOS (4 tablas dw.fact_*)
   ============================================================================ */

-- 4.1 dw.fact_denuncias (grano: id_tiempo, id_ubigeo, id_modalidad)
CREATE TABLE dw.fact_denuncias (
    id_fact_denuncia BIGINT IDENTITY(1,1) NOT NULL,
    id_tiempo        INT                  NOT NULL,
    id_fecha         INT                  NOT NULL,
    id_ubigeo        INT                  NOT NULL,
    id_modalidad     INT                  NOT NULL,
    cantidad         INT                  NOT NULL,
    es_anio_parcial  BIT                  NOT NULL,
    fecha_carga      DATETIME2(0)         NOT NULL CONSTRAINT DF_fact_denuncias_fecha_carga DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_fact_denuncias PRIMARY KEY CLUSTERED (id_fact_denuncia),
    CONSTRAINT FK_fact_denuncias_tiempo FOREIGN KEY (id_tiempo)
        REFERENCES dw.dim_tiempo (id_tiempo),
    CONSTRAINT FK_fact_denuncias_fecha FOREIGN KEY (id_fecha)
        REFERENCES dw.dim_fecha (id_fecha),
    CONSTRAINT FK_fact_denuncias_ubigeo FOREIGN KEY (id_ubigeo)
        REFERENCES dw.dim_ubigeo (id_ubigeo),
    CONSTRAINT FK_fact_denuncias_modalidad FOREIGN KEY (id_modalidad)
        REFERENCES dw.dim_modalidad (id_modalidad),
    CONSTRAINT CK_fact_denuncias_cantidad CHECK (cantidad >= 0)
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_fact_denuncias_grano
    ON dw.fact_denuncias (id_tiempo, id_ubigeo, id_modalidad)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_denuncias_tiempo
    ON dw.fact_denuncias (id_tiempo)
    INCLUDE (cantidad, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_denuncias_fecha
    ON dw.fact_denuncias (id_fecha)
    INCLUDE (cantidad, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_denuncias_ubigeo
    ON dw.fact_denuncias (id_ubigeo)
    INCLUDE (cantidad, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_denuncias_modalidad
    ON dw.fact_denuncias (id_modalidad)
    INCLUDE (cantidad, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 4.2 dw.fact_desaparecidos (grano: id_tiempo, id_ubigeo, id_sexo, id_rango_edad, id_nacionalidad)
CREATE TABLE dw.fact_desaparecidos (
    id_fact_desaparecido BIGINT IDENTITY(1,1) NOT NULL,
    id_tiempo            INT                  NOT NULL,
    id_fecha             INT                  NOT NULL,
    id_ubigeo            INT                  NOT NULL,
    id_sexo              INT                  NOT NULL,
    id_rango_edad        INT                  NOT NULL,
    id_nacionalidad      INT                  NOT NULL,
    cantidad             INT                  NOT NULL,
    es_anio_parcial      BIT                  NOT NULL,
    fecha_carga          DATETIME2(0)         NOT NULL CONSTRAINT DF_fact_desaparecidos_fecha_carga DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_fact_desaparecidos PRIMARY KEY CLUSTERED (id_fact_desaparecido),
    CONSTRAINT FK_fact_desaparecidos_tiempo FOREIGN KEY (id_tiempo)
        REFERENCES dw.dim_tiempo (id_tiempo),
    CONSTRAINT FK_fact_desaparecidos_fecha FOREIGN KEY (id_fecha)
        REFERENCES dw.dim_fecha (id_fecha),
    CONSTRAINT FK_fact_desaparecidos_ubigeo FOREIGN KEY (id_ubigeo)
        REFERENCES dw.dim_ubigeo (id_ubigeo),
    CONSTRAINT FK_fact_desaparecidos_sexo FOREIGN KEY (id_sexo)
        REFERENCES dw.dim_sexo (id_sexo),
    CONSTRAINT FK_fact_desaparecidos_rango_edad FOREIGN KEY (id_rango_edad)
        REFERENCES dw.dim_rango_edad (id_rango_edad),
    CONSTRAINT FK_fact_desaparecidos_nacionalidad FOREIGN KEY (id_nacionalidad)
        REFERENCES dw.dim_nacionalidad (id_nacionalidad),
    CONSTRAINT CK_fact_desaparecidos_cantidad CHECK (cantidad >= 0)
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_fact_desaparecidos_grano
    ON dw.fact_desaparecidos (id_tiempo, id_ubigeo, id_sexo, id_rango_edad, id_nacionalidad)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_desaparecidos_tiempo
    ON dw.fact_desaparecidos (id_tiempo)
    INCLUDE (cantidad, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_desaparecidos_fecha
    ON dw.fact_desaparecidos (id_fecha)
    INCLUDE (cantidad, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_desaparecidos_ubigeo
    ON dw.fact_desaparecidos (id_ubigeo)
    INCLUDE (cantidad, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_desaparecidos_sexo_edad
    ON dw.fact_desaparecidos (id_sexo, id_rango_edad)
    INCLUDE (cantidad)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_desaparecidos_nacionalidad
    ON dw.fact_desaparecidos (id_nacionalidad)
    INCLUDE (cantidad)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 4.3 dw.fact_produccion (grano: id_tiempo, id_variable, id_dependencia)
CREATE TABLE dw.fact_produccion (
    id_fact_produccion BIGINT IDENTITY(1,1) NOT NULL,
    id_tiempo          INT                  NOT NULL,
    id_fecha           INT                  NOT NULL,
    id_variable        INT                  NOT NULL,
    id_dependencia     INT                  NOT NULL,
    valor              DECIMAL(18,6)        NOT NULL,
    es_anio_parcial    BIT                  NOT NULL,
    fecha_carga        DATETIME2(0)         NOT NULL CONSTRAINT DF_fact_produccion_fecha_carga DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_fact_produccion PRIMARY KEY CLUSTERED (id_fact_produccion),
    CONSTRAINT FK_fact_produccion_tiempo FOREIGN KEY (id_tiempo)
        REFERENCES dw.dim_tiempo (id_tiempo),
    CONSTRAINT FK_fact_produccion_fecha FOREIGN KEY (id_fecha)
        REFERENCES dw.dim_fecha (id_fecha),
    CONSTRAINT FK_fact_produccion_variable FOREIGN KEY (id_variable)
        REFERENCES dw.dim_variable (id_variable),
    CONSTRAINT FK_fact_produccion_dependencia FOREIGN KEY (id_dependencia)
        REFERENCES dw.dim_dependencia (id_dependencia),
    CONSTRAINT CK_fact_produccion_valor CHECK (valor >= 0)
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_fact_produccion_grano
    ON dw.fact_produccion (id_tiempo, id_variable, id_dependencia)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_produccion_tiempo
    ON dw.fact_produccion (id_tiempo)
    INCLUDE (valor, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_produccion_fecha
    ON dw.fact_produccion (id_fecha)
    INCLUDE (valor, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_produccion_variable
    ON dw.fact_produccion (id_variable)
    INCLUDE (valor, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_produccion_dependencia
    ON dw.fact_produccion (id_dependencia)
    INCLUDE (valor, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 4.4 dw.fact_victimizacion (grano: id_tiempo, id_departamento, id_indicador)
CREATE TABLE dw.fact_victimizacion (
    id_fact_victimizacion BIGINT IDENTITY(1,1) NOT NULL,
    id_tiempo             INT                  NOT NULL,
    id_departamento       INT                  NOT NULL,
    id_indicador          INT                  NOT NULL,
    ambito                NVARCHAR(15)         NOT NULL,
    clasif                SMALLINT             NOT NULL,
    valor                 DECIMAL(5,1)         NOT NULL,
    es_anio_parcial       BIT                  NOT NULL,
    fecha_carga           DATETIME2(0)         NOT NULL CONSTRAINT DF_fact_victimizacion_fecha_carga DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_fact_victimizacion PRIMARY KEY CLUSTERED (id_fact_victimizacion),
    CONSTRAINT FK_fact_victimizacion_tiempo FOREIGN KEY (id_tiempo)
        REFERENCES dw.dim_tiempo (id_tiempo),
    CONSTRAINT FK_fact_victimizacion_departamento FOREIGN KEY (id_departamento)
        REFERENCES dw.dim_departamento (id_departamento),
    CONSTRAINT FK_fact_victimizacion_indicador FOREIGN KEY (id_indicador)
        REFERENCES dw.dim_indicador (id_indicador),
    CONSTRAINT CK_fact_victimizacion_ambito CHECK (ambito IN (N'NACIONAL', N'DEPARTAMENTO')),
    CONSTRAINT CK_fact_victimizacion_clasif CHECK (clasif BETWEEN 0 AND 100),
    CONSTRAINT CK_fact_victimizacion_valor CHECK (valor BETWEEN 0 AND 100)
);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_fact_victimizacion_grano
    ON dw.fact_victimizacion (id_tiempo, id_departamento, id_indicador)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_victimizacion_tiempo
    ON dw.fact_victimizacion (id_tiempo)
    INCLUDE (ambito, valor, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_victimizacion_departamento
    ON dw.fact_victimizacion (id_departamento)
    INCLUDE (ambito, valor, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
CREATE NONCLUSTERED INDEX IX_fact_victimizacion_indicador
    ON dw.fact_victimizacion (id_indicador)
    INCLUDE (ambito, valor, es_anio_parcial)
    WITH (FILLFACTOR = 90, SORT_IN_TEMPDB = ON);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* ============================================================================
   5. VISTAS DE STAGING PARA DIMENSIONES (12 vistas stg.vw_dim_*)
   ============================================================================ */

-- 5.1 stg.vw_dim_departamento
CREATE VIEW stg.vw_dim_departamento
AS
WITH dept_origen AS (
    SELECT DISTINCT
        CASE
            WHEN LEFT(ubigeo, 4) = '1501' THEN 1501
            WHEN LEFT(ubigeo, 2) = '15'   THEN 1599
            ELSE CAST(LEFT(ubigeo, 2) AS INT)
        END AS cod_ubicacion,
        departamento
    FROM DBDenunciasPoliciales.dm.DenunciasPoliciales
    UNION
    SELECT DISTINCT
        CASE
            WHEN LEFT(ubigeo, 4) = '1501' THEN 1501
            WHEN LEFT(ubigeo, 2) = '15'   THEN 1599
            ELSE CAST(LEFT(ubigeo, 2) AS INT)
        END AS cod_ubicacion,
        departamento
    FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas
    UNION
    SELECT DISTINCT
        cod_ubicacion,
        departamento
    FROM DBVictimizacionConfianzaPNP.dm.VictimizacionConfianzaPNP
    WHERE ambito = N'DEPARTAMENTO'
)
SELECT
    CAST(0 AS INT) AS cod_ubicacion,
    CAST(N'NACIONAL' AS NVARCHAR(60)) AS departamento,
    CAST(N'NACIONAL' AS NVARCHAR(15)) AS ambito,
    CAST(1 AS BIT) AS es_nacional,
    CAST(N'NACIONAL' AS NVARCHAR(20)) AS macroregion
UNION ALL
SELECT
    CAST(cod_ubicacion AS INT) AS cod_ubicacion,
    CAST(departamento AS NVARCHAR(60)) AS departamento,
    CAST(N'DEPARTAMENTO' AS NVARCHAR(15)) AS ambito,
    CAST(0 AS BIT) AS es_nacional,
    CAST(CASE
        WHEN cod_ubicacion IN (4, 7, 11, 13, 14, 18, 20, 23, 24, 1501, 1599) THEN N'COSTA'
        WHEN cod_ubicacion IN (2, 3, 5, 6, 8, 9, 10, 12, 19, 21) THEN N'SIERRA'
        WHEN cod_ubicacion IN (1, 16, 17, 22, 25) THEN N'SELVA'
        ELSE N'SIERRA'
    END AS NVARCHAR(20)) AS macroregion
FROM dept_origen;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 5.2 stg.vw_dim_provincia (depende de dw.dim_departamento; 1608 -> PUTUMAYO)
CREATE VIEW stg.vw_dim_provincia
AS
WITH fuente AS (
    SELECT DISTINCT
        CAST(LEFT(ubigeo, 4) AS CHAR(4)) AS cod_provincia,
        CASE
            WHEN LEFT(ubigeo, 4) = '1501' THEN 1501
            WHEN LEFT(ubigeo, 2) = '15'   THEN 1599
            ELSE CAST(LEFT(ubigeo, 2) AS INT)
        END AS cod_ubicacion,
        provincia,
        1 AS prioridad
    FROM DBDenunciasPoliciales.dm.DenunciasPoliciales
    UNION ALL
    SELECT DISTINCT
        CAST(LEFT(ubigeo, 4) AS CHAR(4)) AS cod_provincia,
        CASE
            WHEN LEFT(ubigeo, 4) = '1501' THEN 1501
            WHEN LEFT(ubigeo, 2) = '15'   THEN 1599
            ELSE CAST(LEFT(ubigeo, 2) AS INT)
        END AS cod_ubicacion,
        provincia,
        2 AS prioridad
    FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas
),
dedup AS (
    SELECT
        cod_provincia,
        cod_ubicacion,
        provincia,
        ROW_NUMBER() OVER (
            PARTITION BY cod_provincia
            ORDER BY
                prioridad ASC,
                CASE WHEN cod_provincia = '1608' AND provincia = N'PUTUMAYO' THEN 0 ELSE 1 END ASC,
                provincia ASC
        ) AS rn
    FROM fuente
)
SELECT
    CAST(d.id_departamento AS INT) AS id_departamento,
    CAST(p.cod_provincia AS CHAR(4)) AS cod_provincia,
    CAST(p.provincia AS NVARCHAR(100)) AS provincia
FROM dedup AS p
INNER JOIN dw.dim_departamento AS d
    ON d.cod_ubicacion = p.cod_ubicacion
WHERE p.rn = 1;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 5.3 stg.vw_dim_ubigeo (depende de dw.dim_provincia; union D1+D2; D1 gana 010201/010206)
CREATE VIEW stg.vw_dim_ubigeo
AS
WITH fuente AS (
    SELECT DISTINCT
        CAST(ubigeo AS CHAR(6)) AS ubigeo,
        distrito,
        1 AS prioridad
    FROM DBDenunciasPoliciales.dm.DenunciasPoliciales
    UNION ALL
    SELECT DISTINCT
        CAST(ubigeo AS CHAR(6)) AS ubigeo,
        distrito,
        2 AS prioridad
    FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas
),
dedup AS (
    SELECT
        ubigeo,
        distrito,
        ROW_NUMBER() OVER (
            PARTITION BY ubigeo
            ORDER BY prioridad ASC, distrito ASC
        ) AS rn
    FROM fuente
)
SELECT
    CAST(p.id_provincia AS INT) AS id_provincia,
    CAST(p.id_departamento AS INT) AS id_departamento,
    CAST(u.ubigeo AS CHAR(6)) AS ubigeo,
    CAST(u.distrito AS NVARCHAR(120)) AS distrito
FROM dedup AS u
INNER JOIN dw.dim_provincia AS p
    ON p.cod_provincia = LEFT(u.ubigeo, 4)
WHERE u.rn = 1;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 5.4 stg.vw_dim_tiempo (182 filas: 2013..2026 x mes 0..12)
CREATE VIEW stg.vw_dim_tiempo
AS
SELECT
    CAST(a.anio AS SMALLINT) AS anio,
    CAST(m.mes_numero AS TINYINT) AS mes_numero,
    CAST(CASE m.mes_numero
        WHEN 0  THEN N'ANUAL'
        WHEN 1  THEN N'ENERO'
        WHEN 2  THEN N'FEBRERO'
        WHEN 3  THEN N'MARZO'
        WHEN 4  THEN N'ABRIL'
        WHEN 5  THEN N'MAYO'
        WHEN 6  THEN N'JUNIO'
        WHEN 7  THEN N'JULIO'
        WHEN 8  THEN N'AGOSTO'
        WHEN 9  THEN N'SETIEMBRE'
        WHEN 10 THEN N'OCTUBRE'
        WHEN 11 THEN N'NOVIEMBRE'
        WHEN 12 THEN N'DICIEMBRE'
    END AS NVARCHAR(20)) AS mes_nombre,
    CAST(CASE m.mes_numero
        WHEN 0  THEN N'ANUAL'
        WHEN 1  THEN N'ENE'
        WHEN 2  THEN N'FEB'
        WHEN 3  THEN N'MAR'
        WHEN 4  THEN N'ABR'
        WHEN 5  THEN N'MAY'
        WHEN 6  THEN N'JUN'
        WHEN 7  THEN N'JUL'
        WHEN 8  THEN N'AGO'
        WHEN 9  THEN N'SET'
        WHEN 10 THEN N'OCT'
        WHEN 11 THEN N'NOV'
        WHEN 12 THEN N'DIC'
    END AS NVARCHAR(10)) AS mes_corto,
    CAST(CASE WHEN m.mes_numero = 0 THEN 0 ELSE ((m.mes_numero - 1) / 3) + 1 END AS TINYINT) AS trimestre,
    CAST(CASE WHEN m.mes_numero = 0 THEN N'ANUAL' ELSE N'T' + CAST(((m.mes_numero - 1) / 3) + 1 AS NVARCHAR(1)) END AS NVARCHAR(10)) AS trimestre_nombre,
    CAST(CASE WHEN m.mes_numero = 0 THEN 1 ELSE 0 END AS BIT) AS es_anual,
    CAST(
        CAST(a.anio AS NVARCHAR(4))
        + N'-'
        + CASE WHEN m.mes_numero = 0 THEN N'ANUAL' ELSE RIGHT(N'0' + CAST(m.mes_numero AS NVARCHAR(2)), 2) END
        AS NVARCHAR(15)
    ) AS periodo_label
FROM (VALUES
    (2013),(2014),(2015),(2016),(2017),(2018),(2019),
    (2020),(2021),(2022),(2023),(2024),(2025),(2026)
) AS a(anio)
CROSS JOIN (VALUES
    (0),(1),(2),(3),(4),(5),(6),(7),(8),(9),(10),(11),(12)
) AS m(mes_numero);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 5.5 stg.vw_dim_fecha (5,113 filas diarias continuas 2013-01-01..2026-12-31 con tally E1/E2/E4)
CREATE VIEW stg.vw_dim_fecha
AS
WITH
E1(n) AS (
    SELECT 1 UNION ALL SELECT 1 UNION ALL SELECT 1 UNION ALL SELECT 1 UNION ALL SELECT 1
    UNION ALL SELECT 1 UNION ALL SELECT 1 UNION ALL SELECT 1 UNION ALL SELECT 1 UNION ALL SELECT 1
),
E2(n) AS (SELECT 1 FROM E1 AS a CROSS JOIN E1 AS b),
E4(n) AS (SELECT 1 FROM E2 AS a CROSS JOIN E2 AS b),
Nums(n) AS (
    SELECT TOP (DATEDIFF(DAY, '20130101', '20261231') + 1)
           ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1
    FROM E4
),
Fechas AS (
    SELECT DATEADD(DAY, n, CAST('20130101' AS DATE)) AS fecha
    FROM Nums
)
SELECT
    CAST(fecha AS DATE) AS fecha,
    CAST(YEAR(fecha) AS SMALLINT) AS anio,
    CAST(MONTH(fecha) AS TINYINT) AS mes,
    CAST(DAY(fecha) AS TINYINT) AS dia,
    CAST(CASE MONTH(fecha)
        WHEN 1  THEN N'ENERO'
        WHEN 2  THEN N'FEBRERO'
        WHEN 3  THEN N'MARZO'
        WHEN 4  THEN N'ABRIL'
        WHEN 5  THEN N'MAYO'
        WHEN 6  THEN N'JUNIO'
        WHEN 7  THEN N'JULIO'
        WHEN 8  THEN N'AGOSTO'
        WHEN 9  THEN N'SETIEMBRE'
        WHEN 10 THEN N'OCTUBRE'
        WHEN 11 THEN N'NOVIEMBRE'
        WHEN 12 THEN N'DICIEMBRE'
    END AS NVARCHAR(20)) AS mes_nombre,
    CAST(((MONTH(fecha) - 1) / 3) + 1 AS TINYINT) AS trimestre,
    CAST(N'T' + CAST(((MONTH(fecha) - 1) / 3) + 1 AS NVARCHAR(1)) AS NVARCHAR(10)) AS trimestre_nombre,
    CAST(CASE WHEN DAY(fecha) = 1 THEN 1 ELSE 0 END AS BIT) AS es_primer_dia_mes
FROM Fechas;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 5.6 stg.vw_dim_modalidad
CREATE VIEW stg.vw_dim_modalidad
AS
SELECT DISTINCT
    CAST(modalidad AS NVARCHAR(100)) AS modalidad
FROM DBDenunciasPoliciales.dm.DenunciasPoliciales;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 5.7 stg.vw_dim_sexo
CREATE VIEW stg.vw_dim_sexo
AS
SELECT
    CAST(v.codigo_sexo AS NVARCHAR(15)) AS codigo_sexo,
    CAST(v.sexo_descripcion AS NVARCHAR(30)) AS sexo_descripcion
FROM (VALUES
    (N'F',            N'Femenino'),
    (N'M',            N'Masculino'),
    (N'NO INFORMADO', N'No informado')
) AS v(codigo_sexo, sexo_descripcion);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 5.8 stg.vw_dim_rango_edad
CREATE VIEW stg.vw_dim_rango_edad
AS
SELECT
    CAST(v.rango_edad AS NVARCHAR(30)) AS rango_edad,
    CAST(v.es_menor_18 AS BIT) AS es_menor_18,
    CAST(v.orden_edad AS TINYINT) AS orden_edad
FROM (VALUES
    (N'0-5 AÑOS',      1, 1),
    (N'6-11 AÑOS',     1, 2),
    (N'12-17 AÑOS',    1, 3),
    (N'18-29 AÑOS',    0, 4),
    (N'30-59 AÑOS',    0, 5),
    (N'60 A MAS AÑOS', 0, 6),
    (N'NO INFORMADO',  0, 7)
) AS v(rango_edad, es_menor_18, orden_edad);
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 5.9 stg.vw_dim_nacionalidad
CREATE VIEW stg.vw_dim_nacionalidad
AS
SELECT DISTINCT
    CAST(nacionalidad AS NVARCHAR(60)) AS nacionalidad
FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 5.10 stg.vw_dim_variable
CREATE VIEW stg.vw_dim_variable
AS
SELECT DISTINCT
    CAST(variable AS NVARCHAR(100)) AS variable,
    CAST(unidad_medida AS NVARCHAR(30)) AS unidad_medida,
    CAST(CASE
        WHEN variable = N'OPERATIVOS' THEN N'OPERATIVOS'
        WHEN variable IN (N'ARMAS BLANCAS', N'ARMAS DE FUEGO') THEN N'ARMAS INCAUTADAS'
        WHEN variable IN (N'BANDAS CRIMINALES DESARTICULADAS', N'ORGANIZACIONES CRIMINALES DESARTICULADAS') THEN N'ESTRUCTURAS CRIMINALES'
        WHEN variable IN (
            N'CC (ENVOLTORIOS)', N'PBC (ENVOLTORIOS)', N'MARIHUANA (ENVOLTORIO)',
            N'CC (KILOS)', N'MARIHUANA (KILOS)', N'PBC (KILOS)'
        ) THEN N'DROGAS DECOMISADAS'
        WHEN variable IN (N'DINERO INCAUTADO (SOLES)', N'CONTRABANDO (VALORIZACION)') THEN N'INCAUTACION MONETARIA'
        WHEN variable IN (
            N'DETENIDOS DIVERSOS DELITOS (EXTRANJEROS)',
            N'DETENIDOS DIVERSOS DELITOS (PERUANOS)',
            N'DETENIDOS POR REQUISITORIADO',
            N'INTERVENCION EXTRAJEROS (LEY MIGRATORIA)'
        ) THEN N'PERSONAS INTERVENIDAS'
        WHEN variable = N'PAPELETAS INFRACCION RNT' THEN N'TRANSITO'
        ELSE N'OTRAS VARIABLES'
    END AS NVARCHAR(40)) AS categoria_variable
FROM DBProduccionPolicial.dm.ProduccionPolicial;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 5.11 stg.vw_dim_dependencia
CREATE VIEW stg.vw_dim_dependencia
AS
SELECT DISTINCT
    CAST(dependencia AS NVARCHAR(60)) AS dependencia,
    CAST(dir_reg_fre AS NVARCHAR(30)) AS dir_reg_fre
FROM DBProduccionPolicial.dm.ProduccionPolicial;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 5.12 stg.vw_dim_indicador
CREATE VIEW stg.vw_dim_indicador
AS
SELECT DISTINCT
    CAST(indicador AS NVARCHAR(200)) AS indicador,
    CAST(CASE indicador
        WHEN N'PORCENTAJE DE CONFIANZA EN LA PNP'
            THEN N'Confianza en la PNP'
        WHEN N'PORCENTAJE DE PERCEPCIÓN DE INSEGURIDAD AL CAMINAR SOLO(A) DE NOCHE EN SU ZONA O BARRIO'
            THEN N'Percepción de inseguridad'
        WHEN N'PORCENTAJE DE VICTIMIZACIÓN'
            THEN N'Victimización total'
        WHEN N'PORCENTAJE DE VICTIMIZACIÓN POR EL DELITO DE ROBO E INTENTO DE ROBO DE DINERO, CARTERA Y CELULAR'
            THEN N'Victimización por robo'
        WHEN N'PORCENTAJE DE VICTIMIZACIÓN POR ESTAFA'
            THEN N'Victimización por estafa'
        ELSE LEFT(indicador, 60)
    END AS NVARCHAR(60)) AS indicador_corto
FROM DBVictimizacionConfianzaPNP.dm.VictimizacionConfianzaPNP;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* ============================================================================
   6. VISTAS DE STAGING PARA TABLAS DE HECHOS (4 vistas stg.vw_fact_*)
   ============================================================================ */

-- 6.1 stg.vw_fact_denuncias
CREATE VIEW stg.vw_fact_denuncias
AS
SELECT
    CAST(t.id_tiempo AS INT) AS id_tiempo,
    CAST(f.id_fecha AS INT) AS id_fecha,
    CAST(u.id_ubigeo AS INT) AS id_ubigeo,
    CAST(m.id_modalidad AS INT) AS id_modalidad,
    CAST(src.cantidad AS INT) AS cantidad,
    CAST(src.es_anio_parcial AS BIT) AS es_anio_parcial
FROM DBDenunciasPoliciales.dm.DenunciasPoliciales AS src
INNER JOIN dw.dim_tiempo AS t
    ON t.anio = src.anio_registro
   AND t.mes_numero = src.mes_registro
INNER JOIN dw.dim_fecha AS f
    ON f.fecha = src.fecha_hecho
INNER JOIN dw.dim_ubigeo AS u
    ON u.ubigeo = src.ubigeo
INNER JOIN dw.dim_modalidad AS m
    ON m.modalidad = src.modalidad;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 6.2 stg.vw_fact_desaparecidos
CREATE VIEW stg.vw_fact_desaparecidos
AS
SELECT
    CAST(t.id_tiempo AS INT) AS id_tiempo,
    CAST(f.id_fecha AS INT) AS id_fecha,
    CAST(u.id_ubigeo AS INT) AS id_ubigeo,
    CAST(s.id_sexo AS INT) AS id_sexo,
    CAST(re.id_rango_edad AS INT) AS id_rango_edad,
    CAST(n.id_nacionalidad AS INT) AS id_nacionalidad,
    CAST(src.cantidad AS INT) AS cantidad,
    CAST(src.es_anio_parcial AS BIT) AS es_anio_parcial
FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas AS src
INNER JOIN dw.dim_tiempo AS t
    ON t.anio = src.anio_registro
   AND t.mes_numero = src.mes_registro
INNER JOIN dw.dim_fecha AS f
    ON f.fecha = src.fecha_hecho
INNER JOIN dw.dim_ubigeo AS u
    ON u.ubigeo = src.ubigeo
INNER JOIN dw.dim_sexo AS s
    ON s.codigo_sexo = ISNULL(NULLIF(LTRIM(RTRIM(CAST(src.sexo AS NVARCHAR(15)))), N''), N'NO INFORMADO')
INNER JOIN dw.dim_rango_edad AS re
    ON re.rango_edad = ISNULL(NULLIF(LTRIM(RTRIM(src.rango_edad)), N''), N'NO INFORMADO')
INNER JOIN dw.dim_nacionalidad AS n
    ON n.nacionalidad = src.nacionalidad;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 6.3 stg.vw_fact_produccion
CREATE VIEW stg.vw_fact_produccion
AS
SELECT
    CAST(t.id_tiempo AS INT) AS id_tiempo,
    CAST(f.id_fecha AS INT) AS id_fecha,
    CAST(v.id_variable AS INT) AS id_variable,
    CAST(d.id_dependencia AS INT) AS id_dependencia,
    CAST(src.valor AS DECIMAL(18,6)) AS valor,
    CAST(src.es_anio_parcial AS BIT) AS es_anio_parcial
FROM DBProduccionPolicial.dm.ProduccionPolicial AS src
INNER JOIN dw.dim_tiempo AS t
    ON t.anio = src.anio_registro
   AND t.mes_numero = src.mes_registro
INNER JOIN dw.dim_fecha AS f
    ON f.fecha = src.fecha_hecho
INNER JOIN dw.dim_variable AS v
    ON v.variable = src.variable
INNER JOIN dw.dim_dependencia AS d
    ON d.dependencia = src.dependencia;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- 6.4 stg.vw_fact_victimizacion
CREATE VIEW stg.vw_fact_victimizacion
AS
SELECT
    CAST(t.id_tiempo AS INT) AS id_tiempo,
    CAST(dep.id_departamento AS INT) AS id_departamento,
    CAST(ind.id_indicador AS INT) AS id_indicador,
    CAST(src.ambito AS NVARCHAR(15)) AS ambito,
    CAST(src.clasif AS SMALLINT) AS clasif,
    CAST(src.valor AS DECIMAL(5,1)) AS valor,
    CAST(src.es_anio_parcial AS BIT) AS es_anio_parcial
FROM DBVictimizacionConfianzaPNP.dm.VictimizacionConfianzaPNP AS src
INNER JOIN dw.dim_tiempo AS t
    ON t.anio = src.anio_registro
   AND t.mes_numero = 0
INNER JOIN dw.dim_departamento AS dep
    ON dep.cod_ubicacion = src.cod_ubicacion
INNER JOIN dw.dim_indicador AS ind
    ON ind.indicador = src.indicador;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET DATEFORMAT ymd;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

PRINT N'Estructura DW_ProyectoEF creada correctamente (3 esquemas, 1 tabla etl, 12 dimensiones, 4 hechos, 16 vistas stg).';
GO
