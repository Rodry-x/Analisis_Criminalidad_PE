/* ============================================================================
   DataWarehouse: DW_ProyectoEF
   ----------------------------------------------------------------------------
   Modelo de constelacion (4 tablas de hecho + dimensiones conformadas).

   Capas:
     stg  -> vistas de preparacion. Leen los 4 DataMarts y resuelven las claves.
     dw   -> dimensiones y hechos que carga SSIS.
     etl  -> control de carga.

   Preguntas guia que soporta este modelo:
     1. ¿Donde conviene ubicar mi negocio desde el punto de vista de seguridad?
     2. ¿Como evolucionan las denuncias y que modalidades lideran?
     3. ¿Donde y en que perfil se concentran las desapariciones?
     4. ¿Como evoluciona la confianza en la PNP y que departamentos tienen
        peor percepcion?
     5. ¿Que dependencias/variables concentran la produccion policial?

   Este script crea SOLO la estructura. Los datos los carga SSIS.
   ============================================================================ */

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

IF DB_ID(N'DW_ProyectoEF') IS NULL
BEGIN
    PRINT N'Creando base de datos DW_ProyectoEF...';
    CREATE DATABASE DW_ProyectoEF;
END
ELSE
    PRINT N'La base de datos DW_ProyectoEF ya existe.';
GO

USE DW_ProyectoEF;
GO

IF SCHEMA_ID(N'dw') IS NULL  EXEC(N'CREATE SCHEMA dw');
IF SCHEMA_ID(N'stg') IS NULL EXEC(N'CREATE SCHEMA stg');
IF SCHEMA_ID(N'etl') IS NULL EXEC(N'CREATE SCHEMA etl');
GO

/* ---------------------------------------------------------------------------
   DIMENSIONES
   --------------------------------------------------------------------------- */

/* Se borran primero los hechos y despues las dimensiones por las FOREIGN KEY. */
IF OBJECT_ID(N'dw.fact_denuncias', N'U') IS NOT NULL DROP TABLE dw.fact_denuncias;
IF OBJECT_ID(N'dw.fact_desaparecidos', N'U') IS NOT NULL DROP TABLE dw.fact_desaparecidos;
IF OBJECT_ID(N'dw.fact_produccion', N'U') IS NOT NULL DROP TABLE dw.fact_produccion;
IF OBJECT_ID(N'dw.fact_victimizacion', N'U') IS NOT NULL DROP TABLE dw.fact_victimizacion;
IF OBJECT_ID(N'dw.dim_poblacion', N'U') IS NOT NULL DROP TABLE dw.dim_poblacion;
IF OBJECT_ID(N'dw.dim_ubigeo', N'U') IS NOT NULL DROP TABLE dw.dim_ubigeo;
IF OBJECT_ID(N'dw.dim_provincia', N'U') IS NOT NULL DROP TABLE dw.dim_provincia;
IF OBJECT_ID(N'dw.dim_fecha', N'U') IS NOT NULL DROP TABLE dw.dim_fecha;
IF OBJECT_ID(N'dw.dim_tiempo', N'U') IS NOT NULL DROP TABLE dw.dim_tiempo;
IF OBJECT_ID(N'dw.dim_departamento', N'U') IS NOT NULL DROP TABLE dw.dim_departamento;
IF OBJECT_ID(N'dw.dim_modalidad', N'U') IS NOT NULL DROP TABLE dw.dim_modalidad;
IF OBJECT_ID(N'dw.dim_sexo', N'U') IS NOT NULL DROP TABLE dw.dim_sexo;
IF OBJECT_ID(N'dw.dim_rango_edad', N'U') IS NOT NULL DROP TABLE dw.dim_rango_edad;
IF OBJECT_ID(N'dw.dim_nacionalidad', N'U') IS NOT NULL DROP TABLE dw.dim_nacionalidad;
IF OBJECT_ID(N'dw.dim_variable', N'U') IS NOT NULL DROP TABLE dw.dim_variable;
IF OBJECT_ID(N'dw.dim_dependencia', N'U') IS NOT NULL DROP TABLE dw.dim_dependencia;
IF OBJECT_ID(N'dw.dim_indicador', N'U') IS NOT NULL DROP TABLE dw.dim_indicador;
GO

CREATE TABLE dw.dim_fecha (
    id_fecha         INT NOT NULL,
    fecha            DATE NOT NULL,
    anio             SMALLINT NOT NULL,
    mes              TINYINT NOT NULL,
    dia              TINYINT NOT NULL,
    nombre_mes       NVARCHAR(20) NOT NULL,
    trimestre        TINYINT NOT NULL,
    es_fin_de_semana BIT NOT NULL,
    anio_mes         CHAR(7) NOT NULL,
    CONSTRAINT PK_dim_fecha PRIMARY KEY CLUSTERED (id_fecha)
);
GO

CREATE TABLE dw.dim_tiempo (
    id_tiempo   INT NOT NULL,
    anio        SMALLINT NOT NULL,
    mes         TINYINT NOT NULL,
    nombre_mes  NVARCHAR(20) NOT NULL,
    trimestre   TINYINT NOT NULL,
    periodo     NVARCHAR(10) NOT NULL,
    es_anual    BIT NOT NULL,
    orden       INT NOT NULL,
    CONSTRAINT PK_dim_tiempo PRIMARY KEY CLUSTERED (id_tiempo)
);
GO

CREATE TABLE dw.dim_departamento (
    id_departamento INT NOT NULL,
    codigo          NVARCHAR(6) NOT NULL,
    departamento    NVARCHAR(60) NOT NULL,
    es_nacional     BIT NOT NULL,
    macroregion     NVARCHAR(20) NOT NULL,
    CONSTRAINT PK_dim_departamento PRIMARY KEY CLUSTERED (id_departamento)
);
GO

CREATE TABLE dw.dim_provincia (
    id_provincia    INT NOT NULL,
    provincia       NVARCHAR(100) NOT NULL,
    id_departamento INT NOT NULL,
    CONSTRAINT PK_dim_provincia PRIMARY KEY CLUSTERED (id_provincia),
    CONSTRAINT FK_provincia_departamento FOREIGN KEY (id_departamento)
        REFERENCES dw.dim_departamento (id_departamento)
);
GO

CREATE TABLE dw.dim_ubigeo (
    id_ubigeo       INT NOT NULL,
    ubigeo          CHAR(6) NOT NULL,
    distrito        NVARCHAR(120) NOT NULL,
    provincia       NVARCHAR(100) NOT NULL,
    id_provincia    INT NOT NULL,
    id_departamento INT NOT NULL,
    CONSTRAINT PK_dim_ubigeo PRIMARY KEY CLUSTERED (id_ubigeo),
    CONSTRAINT FK_ubigeo_provincia FOREIGN KEY (id_provincia)
        REFERENCES dw.dim_provincia (id_provincia),
    CONSTRAINT FK_ubigeo_departamento FOREIGN KEY (id_departamento)
        REFERENCES dw.dim_departamento (id_departamento)
);
GO

CREATE TABLE dw.dim_modalidad (
    id_modalidad INT NOT NULL,
    modalidad    NVARCHAR(100) NOT NULL,
    CONSTRAINT PK_dim_modalidad PRIMARY KEY CLUSTERED (id_modalidad)
);
GO

CREATE TABLE dw.dim_sexo (
    id_sexo     INT NOT NULL,
    sexo        NVARCHAR(20) NOT NULL,
    descripcion NVARCHAR(40) NOT NULL,
    CONSTRAINT PK_dim_sexo PRIMARY KEY CLUSTERED (id_sexo)
);
GO

CREATE TABLE dw.dim_rango_edad (
    id_rango_edad INT NOT NULL,
    rango_edad    NVARCHAR(30) NOT NULL,
    CONSTRAINT PK_dim_rango_edad PRIMARY KEY CLUSTERED (id_rango_edad)
);
GO

CREATE TABLE dw.dim_nacionalidad (
    id_nacionalidad INT NOT NULL,
    nacionalidad    NVARCHAR(100) NOT NULL,
    CONSTRAINT PK_dim_nacionalidad PRIMARY KEY CLUSTERED (id_nacionalidad)
);
GO

CREATE TABLE dw.dim_variable (
    id_variable    INT NOT NULL,
    variable       NVARCHAR(100) NOT NULL,
    unidad_medida  NVARCHAR(30) NOT NULL,
    CONSTRAINT PK_dim_variable PRIMARY KEY CLUSTERED (id_variable)
);
GO

CREATE TABLE dw.dim_dependencia (
    id_dependencia INT NOT NULL,
    dependencia    NVARCHAR(200) NOT NULL,
    dir_reg_fre    NVARCHAR(30) NOT NULL,
    CONSTRAINT PK_dim_dependencia PRIMARY KEY CLUSTERED (id_dependencia)
);
GO

CREATE TABLE dw.dim_indicador (
    id_indicador INT NOT NULL,
    indicador    NVARCHAR(200) NOT NULL,
    unidad       NVARCHAR(10) NOT NULL,
    CONSTRAINT PK_dim_indicador PRIMARY KEY CLUSTERED (id_indicador)
);
GO

/* ---------------------------------------------------------------------------
   TABLAS DE HECHO
   --------------------------------------------------------------------------- */

CREATE TABLE dw.fact_denuncias (
    id_fact_denuncia BIGINT IDENTITY(1,1) NOT NULL,
    id_tiempo        INT NOT NULL,
    id_fecha_hecho   INT NOT NULL,
    id_ubigeo        INT NOT NULL,
    id_modalidad     INT NOT NULL,
    cantidad         INT NOT NULL,
    es_anio_parcial  BIT NOT NULL,
    CONSTRAINT PK_fact_denuncias PRIMARY KEY CLUSTERED (id_fact_denuncia),
    CONSTRAINT FK_fd_tiempo FOREIGN KEY (id_tiempo) REFERENCES dw.dim_tiempo (id_tiempo),
    CONSTRAINT FK_fd_fecha FOREIGN KEY (id_fecha_hecho) REFERENCES dw.dim_fecha (id_fecha),
    CONSTRAINT FK_fd_ubigeo FOREIGN KEY (id_ubigeo) REFERENCES dw.dim_ubigeo (id_ubigeo),
    CONSTRAINT FK_fd_modalidad FOREIGN KEY (id_modalidad) REFERENCES dw.dim_modalidad (id_modalidad)
);
GO

CREATE TABLE dw.fact_desaparecidos (
    id_fact_desaparicion BIGINT IDENTITY(1,1) NOT NULL,
    id_tiempo            INT NOT NULL,
    id_fecha_hecho       INT NOT NULL,
    id_ubigeo            INT NOT NULL,
    id_sexo              INT NOT NULL,
    id_rango_edad        INT NOT NULL,
    id_nacionalidad      INT NOT NULL,
    cantidad             INT NOT NULL,
    es_anio_parcial      BIT NOT NULL,
    CONSTRAINT PK_fact_desaparecidos PRIMARY KEY CLUSTERED (id_fact_desaparicion),
    CONSTRAINT FK_fdes_tiempo FOREIGN KEY (id_tiempo) REFERENCES dw.dim_tiempo (id_tiempo),
    CONSTRAINT FK_fdes_fecha FOREIGN KEY (id_fecha_hecho) REFERENCES dw.dim_fecha (id_fecha),
    CONSTRAINT FK_fdes_ubigeo FOREIGN KEY (id_ubigeo) REFERENCES dw.dim_ubigeo (id_ubigeo),
    CONSTRAINT FK_fdes_sexo FOREIGN KEY (id_sexo) REFERENCES dw.dim_sexo (id_sexo),
    CONSTRAINT FK_fdes_rango FOREIGN KEY (id_rango_edad) REFERENCES dw.dim_rango_edad (id_rango_edad),
    CONSTRAINT FK_fdes_nacionalidad FOREIGN KEY (id_nacionalidad) REFERENCES dw.dim_nacionalidad (id_nacionalidad)
);
GO

CREATE TABLE dw.fact_produccion (
    id_fact_produccion BIGINT IDENTITY(1,1) NOT NULL,
    id_tiempo          INT NOT NULL,
    id_fecha_hecho     INT NOT NULL,
    id_variable        INT NOT NULL,
    id_dependencia     INT NOT NULL,
    valor              DECIMAL(18,6) NOT NULL,
    es_anio_parcial    BIT NOT NULL,
    CONSTRAINT PK_fact_produccion PRIMARY KEY CLUSTERED (id_fact_produccion),
    CONSTRAINT FK_fp_tiempo FOREIGN KEY (id_tiempo) REFERENCES dw.dim_tiempo (id_tiempo),
    CONSTRAINT FK_fp_fecha FOREIGN KEY (id_fecha_hecho) REFERENCES dw.dim_fecha (id_fecha),
    CONSTRAINT FK_fp_variable FOREIGN KEY (id_variable) REFERENCES dw.dim_variable (id_variable),
    CONSTRAINT FK_fp_dependencia FOREIGN KEY (id_dependencia) REFERENCES dw.dim_dependencia (id_dependencia)
);
GO

CREATE TABLE dw.fact_victimizacion (
    id_fact_victimizacion BIGINT IDENTITY(1,1) NOT NULL,
    id_tiempo             INT NOT NULL,
    id_departamento       INT NOT NULL,
    id_indicador          INT NOT NULL,
    valor                 DECIMAL(5,1) NOT NULL,
    clasif                SMALLINT NOT NULL,
    es_anio_parcial       BIT NOT NULL,
    CONSTRAINT PK_fact_victimizacion PRIMARY KEY CLUSTERED (id_fact_victimizacion),
    CONSTRAINT FK_fv_tiempo FOREIGN KEY (id_tiempo) REFERENCES dw.dim_tiempo (id_tiempo),
    CONSTRAINT FK_fv_departamento FOREIGN KEY (id_departamento) REFERENCES dw.dim_departamento (id_departamento),
    CONSTRAINT FK_fv_indicador FOREIGN KEY (id_indicador) REFERENCES dw.dim_indicador (id_indicador)
);
GO

/* Tabla opcional para tasas por habitante. Se deja vacia: requiere la
   proyeccion de poblacion del INEI por ubigeo. Las medidas de tasa del modelo
   SSAS quedaran en BLANK hasta que se cargue. */
CREATE TABLE dw.dim_poblacion (
    id_ubigeo INT NOT NULL,
    anio      SMALLINT NOT NULL,
    poblacion INT NOT NULL,
    fuente    NVARCHAR(100) NOT NULL,
    CONSTRAINT PK_dim_poblacion PRIMARY KEY CLUSTERED (id_ubigeo, anio),
    CONSTRAINT FK_poblacion_ubigeo FOREIGN KEY (id_ubigeo) REFERENCES dw.dim_ubigeo (id_ubigeo)
);
GO

IF OBJECT_ID(N'etl.ControlCargaDW', N'U') IS NOT NULL DROP TABLE etl.ControlCargaDW;
GO

CREATE TABLE etl.ControlCargaDW (
    id_carga   INT IDENTITY(1,1) NOT NULL,
    paquete    NVARCHAR(100) NOT NULL,
    tabla      NVARCHAR(100) NOT NULL,
    filas      INT NOT NULL,
    fecha_inicio DATETIME2(0) NOT NULL,
    fecha_fin    DATETIME2(0) NOT NULL,
    estado     NVARCHAR(20) NOT NULL,
    detalle    NVARCHAR(MAX) NULL,
    CONSTRAINT PK_ControlCargaDW PRIMARY KEY CLUSTERED (id_carga)
);
GO

PRINT N'Estructura creada. Generando vistas de preparacion...';
GO

/* ---------------------------------------------------------------------------
   VISTAS stg: fecha y tiempo
   --------------------------------------------------------------------------- */

CREATE OR ALTER VIEW stg.vw_dim_fecha AS
WITH n AS (
    SELECT TOP (6000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS k
    FROM sys.all_objects a CROSS JOIN sys.all_objects b
), fechas AS (
    SELECT DATEADD(DAY, k, CONVERT(DATE, '20130101')) AS fecha
    FROM n
    WHERE k <= DATEDIFF(DAY, CONVERT(DATE, '20130101'), CONVERT(DATE, '20261231'))
)
SELECT
    YEAR(fecha) * 10000 + MONTH(fecha) * 100 + DAY(fecha) AS id_fecha,
    fecha,
    CONVERT(SMALLINT, YEAR(fecha)) AS anio,
    CONVERT(TINYINT, MONTH(fecha)) AS mes,
    CONVERT(TINYINT, DAY(fecha)) AS dia,
    CASE MONTH(fecha)
        WHEN 1 THEN N'ENERO' WHEN 2 THEN N'FEBRERO' WHEN 3 THEN N'MARZO'
        WHEN 4 THEN N'ABRIL' WHEN 5 THEN N'MAYO' WHEN 6 THEN N'JUNIO'
        WHEN 7 THEN N'JULIO' WHEN 8 THEN N'AGOSTO' WHEN 9 THEN N'SETIEMBRE'
        WHEN 10 THEN N'OCTUBRE' WHEN 11 THEN N'NOVIEMBRE' ELSE N'DICIEMBRE'
    END AS nombre_mes,
    CONVERT(TINYINT, DATEPART(QUARTER, fecha)) AS trimestre,
    CONVERT(BIT, CASE WHEN DATEPART(WEEKDAY, fecha) IN (1, 7) THEN 1 ELSE 0 END) AS es_fin_de_semana,
    CONVERT(CHAR(4), YEAR(fecha)) + '-' + RIGHT('0' + CONVERT(CHAR(2), MONTH(fecha)), 2) AS anio_mes
FROM fechas
UNION ALL
SELECT 0, CONVERT(DATE, '19000101'), 1900, 1, 1, N'NO ESPECIFICADO', 0, 0, '1900-01';
GO

CREATE OR ALTER VIEW stg.vw_dim_tiempo AS
WITH n AS (
    SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS k
    FROM sys.all_objects a CROSS JOIN sys.all_objects b
), anios AS (
    SELECT 2013 + k AS anio FROM n WHERE k <= 13
), meses AS (
    SELECT 0 AS mes UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3
    UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7
    UNION ALL SELECT 8 UNION ALL SELECT 9 UNION ALL SELECT 10 UNION ALL SELECT 11
    UNION ALL SELECT 12
)
SELECT
    anio * 100 + meses.mes AS id_tiempo,
    CONVERT(SMALLINT, anio) AS anio,
    CONVERT(TINYINT, meses.mes) AS mes,
    CASE WHEN meses.mes = 0 THEN N'ANUAL' ELSE
        CASE meses.mes
            WHEN 1 THEN N'ENERO' WHEN 2 THEN N'FEBRERO' WHEN 3 THEN N'MARZO'
            WHEN 4 THEN N'ABRIL' WHEN 5 THEN N'MAYO' WHEN 6 THEN N'JUNIO'
            WHEN 7 THEN N'JULIO' WHEN 8 THEN N'AGOSTO' WHEN 9 THEN N'SETIEMBRE'
            WHEN 10 THEN N'OCTUBRE' WHEN 11 THEN N'NOVIEMBRE' ELSE N'DICIEMBRE'
        END
    END AS nombre_mes,
    CONVERT(TINYINT, CASE WHEN meses.mes = 0 THEN 0 ELSE ((meses.mes - 1) / 3) + 1 END) AS trimestre,
    CONVERT(NVARCHAR(10), CASE WHEN meses.mes = 0 THEN N'ANUAL'
        ELSE CONVERT(NVARCHAR(4), anio) + N'-' + RIGHT(N'0' + CONVERT(NVARCHAR(2), meses.mes), 2) END) AS periodo,
    CONVERT(BIT, CASE WHEN meses.mes = 0 THEN 1 ELSE 0 END) AS es_anual,
    anio * 13 + meses.mes AS orden
FROM anios CROSS JOIN meses;
GO

/* ---------------------------------------------------------------------------
   VISTAS stg: geografia
   Regla Lima: 1501 -> LIMA METROPOLITANA, resto de 15xx -> REGION LIMA,
   Callao (07) se mantiene como provincia constitucional.
   --------------------------------------------------------------------------- */

CREATE OR ALTER VIEW stg.vw_dim_departamento AS
SELECT * FROM (VALUES
    (0,   N'0',    N'NACIONAL',                  CONVERT(BIT,1), N'NACIONAL'),
    (1,   N'1',    N'AMAZONAS',                  CONVERT(BIT,0), N'SELVA'),
    (2,   N'2',    N'ANCASH',                    CONVERT(BIT,0), N'SIERRA'),
    (3,   N'3',    N'APURIMAC',                  CONVERT(BIT,0), N'SIERRA'),
    (4,   N'4',    N'AREQUIPA',                  CONVERT(BIT,0), N'COSTA'),
    (5,   N'5',    N'AYACUCHO',                  CONVERT(BIT,0), N'SIERRA'),
    (6,   N'6',    N'CAJAMARCA',                 CONVERT(BIT,0), N'SIERRA'),
    (7,   N'7',    N'PROV. CONST. DEL CALLAO',   CONVERT(BIT,0), N'COSTA'),
    (8,   N'8',    N'CUSCO',                     CONVERT(BIT,0), N'SIERRA'),
    (9,   N'9',    N'HUANCAVELICA',              CONVERT(BIT,0), N'SIERRA'),
    (10,  N'10',   N'HUANUCO',                   CONVERT(BIT,0), N'SIERRA'),
    (11,  N'11',   N'ICA',                       CONVERT(BIT,0), N'COSTA'),
    (12,  N'12',   N'JUNIN',                     CONVERT(BIT,0), N'SIERRA'),
    (13,  N'13',   N'LA LIBERTAD',               CONVERT(BIT,0), N'COSTA'),
    (14,  N'14',   N'LAMBAYEQUE',                CONVERT(BIT,0), N'COSTA'),
    (16,  N'16',   N'LORETO',                    CONVERT(BIT,0), N'SELVA'),
    (17,  N'17',   N'MADRE DE DIOS',             CONVERT(BIT,0), N'SELVA'),
    (18,  N'18',   N'MOQUEGUA',                  CONVERT(BIT,0), N'COSTA'),
    (19,  N'19',   N'PASCO',                     CONVERT(BIT,0), N'SIERRA'),
    (20,  N'20',   N'PIURA',                     CONVERT(BIT,0), N'COSTA'),
    (21,  N'21',   N'PUNO',                      CONVERT(BIT,0), N'SIERRA'),
    (22,  N'22',   N'SAN MARTIN',                CONVERT(BIT,0), N'SELVA'),
    (23,  N'23',   N'TACNA',                     CONVERT(BIT,0), N'COSTA'),
    (24,  N'24',   N'TUMBES',                    CONVERT(BIT,0), N'COSTA'),
    (25,  N'25',   N'UCAYALI',                   CONVERT(BIT,0), N'SELVA'),
    (1501,N'1501', N'LIMA METROPOLITANA',        CONVERT(BIT,0), N'COSTA'),
    (1599,N'1599', N'REGION LIMA',               CONVERT(BIT,0), N'COSTA')
) AS v(id_departamento, codigo, departamento, es_nacional, macroregion);
GO

CREATE OR ALTER VIEW stg.vw_dim_provincia AS
WITH u AS (
    SELECT CONVERT(INT, LEFT(ubigeo, 4)) AS id_provincia, provincia
    FROM DBDenunciasPoliciales.dm.DenunciasPoliciales
    UNION
    SELECT CONVERT(INT, LEFT(ubigeo, 4)), provincia
    FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas
), r AS (
    SELECT id_provincia, provincia,
           ROW_NUMBER() OVER (PARTITION BY id_provincia ORDER BY provincia) AS rn
    FROM u
)
SELECT
    id_provincia,
    provincia,
    CASE
        WHEN id_provincia / 100 = 15 THEN
            CASE WHEN id_provincia = 1501 THEN 1501 ELSE 1599 END
        ELSE id_provincia / 100
    END AS id_departamento
FROM r
WHERE rn = 1
UNION ALL
SELECT 0, N'NO ESPECIFICADO', 0;
GO

CREATE OR ALTER VIEW stg.vw_dim_ubigeo AS
WITH u AS (
    SELECT ubigeo, provincia, distrito, 1 AS prioridad
    FROM DBDenunciasPoliciales.dm.DenunciasPoliciales
    UNION ALL
    SELECT ubigeo, provincia, distrito, 2
    FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas
), r AS (
    SELECT ubigeo, provincia, distrito,
           ROW_NUMBER() OVER (PARTITION BY ubigeo ORDER BY prioridad, distrito) AS rn
    FROM u
)
SELECT
    CONVERT(INT, ubigeo) AS id_ubigeo,
    ubigeo,
    distrito,
    provincia,
    CONVERT(INT, LEFT(ubigeo, 4)) AS id_provincia,
    CASE
        WHEN LEFT(ubigeo, 2) = '15' THEN
            CASE WHEN LEFT(ubigeo, 4) = '1501' THEN 1501 ELSE 1599 END
        ELSE CONVERT(INT, LEFT(ubigeo, 2))
    END AS id_departamento
FROM r
WHERE rn = 1
UNION ALL
SELECT 0, '000000', N'NO ESPECIFICADO', N'NO ESPECIFICADO', 0, 0;
GO

/* ---------------------------------------------------------------------------
   VISTAS stg: dimensiones pequenas
   --------------------------------------------------------------------------- */

CREATE OR ALTER VIEW stg.vw_dim_modalidad AS
SELECT 0 AS id_modalidad, N'NO ESPECIFICADO' AS modalidad
UNION ALL
SELECT ROW_NUMBER() OVER (ORDER BY modalidad), modalidad
FROM (SELECT DISTINCT modalidad FROM DBDenunciasPoliciales.dm.DenunciasPoliciales) x;
GO

CREATE OR ALTER VIEW stg.vw_dim_sexo AS
SELECT * FROM (VALUES
    (0, N'',            N'NO ESPECIFICADO'),
    (1, N'M',           N'MASCULINO'),
    (2, N'F',           N'FEMENINO')
) AS v(id_sexo, sexo, descripcion);
GO

CREATE OR ALTER VIEW stg.vw_dim_rango_edad AS
SELECT 0 AS id_rango_edad, N'NO ESPECIFICADO' AS rango_edad
UNION ALL
SELECT ROW_NUMBER() OVER (ORDER BY rango_edad), rango_edad
FROM (
    SELECT DISTINCT rango_edad
    FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas
    WHERE rango_edad IS NOT NULL AND LTRIM(RTRIM(rango_edad)) <> N''
) x;
GO

CREATE OR ALTER VIEW stg.vw_dim_nacionalidad AS
SELECT 0 AS id_nacionalidad, N'NO ESPECIFICADO' AS nacionalidad
UNION ALL
SELECT ROW_NUMBER() OVER (ORDER BY nacionalidad), nacionalidad
FROM (
    SELECT DISTINCT nacionalidad
    FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas
    WHERE nacionalidad IS NOT NULL AND LTRIM(RTRIM(nacionalidad)) <> N''
) x;
GO

CREATE OR ALTER VIEW stg.vw_dim_variable AS
SELECT 0 AS id_variable, N'NO ESPECIFICADO' AS variable, N'NO ESPECIFICADO' AS unidad_medida
UNION ALL
SELECT ROW_NUMBER() OVER (ORDER BY variable), variable, unidad_medida
FROM (
    SELECT DISTINCT variable, unidad_medida
    FROM DBProduccionPolicial.dm.ProduccionPolicial
) x;
GO

CREATE OR ALTER VIEW stg.vw_dim_dependencia AS
SELECT 0 AS id_dependencia, N'NO ESPECIFICADO' AS dependencia, N'NO ESPECIFICADO' AS dir_reg_fre
UNION ALL
SELECT ROW_NUMBER() OVER (ORDER BY dependencia, dir_reg_fre), dependencia, dir_reg_fre
FROM (
    SELECT DISTINCT dependencia, dir_reg_fre
    FROM DBProduccionPolicial.dm.ProduccionPolicial
) x;
GO

CREATE OR ALTER VIEW stg.vw_dim_indicador AS
SELECT 0 AS id_indicador, N'NO ESPECIFICADO' AS indicador, N'%' AS unidad
UNION ALL
SELECT ROW_NUMBER() OVER (ORDER BY indicador), indicador, N'%'
FROM (
    SELECT DISTINCT indicador
    FROM DBVictimizacionConfianzaPNP.dm.VictimizacionConfianzaPNP
) x;
GO

/* ---------------------------------------------------------------------------
   VISTAS stg: hechos (ya con las claves resueltas)
   --------------------------------------------------------------------------- */

CREATE OR ALTER VIEW stg.vw_fact_denuncias AS
SELECT
    a.anio_registro * 100 + a.mes_registro AS id_tiempo,
    YEAR(a.fecha_hecho) * 10000 + MONTH(a.fecha_hecho) * 100 + DAY(a.fecha_hecho) AS id_fecha_hecho,
    CONVERT(INT, a.ubigeo) AS id_ubigeo,
    ISNULL(m.id_modalidad, 0) AS id_modalidad,
    a.cantidad,
    a.es_anio_parcial
FROM DBDenunciasPoliciales.dm.DenunciasPoliciales a
LEFT JOIN dw.dim_modalidad m ON m.modalidad = a.modalidad;
GO

CREATE OR ALTER VIEW stg.vw_fact_desaparecidos AS
SELECT
    a.anio_registro * 100 + a.mes_registro AS id_tiempo,
    YEAR(a.fecha_hecho) * 10000 + MONTH(a.fecha_hecho) * 100 + DAY(a.fecha_hecho) AS id_fecha_hecho,
    CONVERT(INT, a.ubigeo) AS id_ubigeo,
    ISNULL(s.id_sexo, 0) AS id_sexo,
    ISNULL(e.id_rango_edad, 0) AS id_rango_edad,
    ISNULL(n.id_nacionalidad, 0) AS id_nacionalidad,
    a.cantidad,
    a.es_anio_parcial
FROM DBPersonasDesaparecidas.dm.PersonasDesaparecidas a
LEFT JOIN dw.dim_sexo s ON s.sexo = LTRIM(RTRIM(a.sexo))
LEFT JOIN dw.dim_rango_edad e ON e.rango_edad = a.rango_edad
LEFT JOIN dw.dim_nacionalidad n ON n.nacionalidad = a.nacionalidad;
GO

CREATE OR ALTER VIEW stg.vw_fact_produccion AS
SELECT
    a.anio_registro * 100 + a.mes_registro AS id_tiempo,
    YEAR(a.fecha_hecho) * 10000 + MONTH(a.fecha_hecho) * 100 + DAY(a.fecha_hecho) AS id_fecha_hecho,
    ISNULL(v.id_variable, 0) AS id_variable,
    ISNULL(d.id_dependencia, 0) AS id_dependencia,
    a.valor,
    a.es_anio_parcial
FROM DBProduccionPolicial.dm.ProduccionPolicial a
LEFT JOIN dw.dim_variable v ON v.variable = a.variable AND v.unidad_medida = a.unidad_medida
LEFT JOIN dw.dim_dependencia d ON d.dependencia = a.dependencia AND d.dir_reg_fre = a.dir_reg_fre;
GO

CREATE OR ALTER VIEW stg.vw_fact_victimizacion AS
SELECT
    a.anio_registro * 100 AS id_tiempo,
    a.cod_ubicacion AS id_departamento,
    ISNULL(i.id_indicador, 0) AS id_indicador,
    a.valor,
    a.clasif,
    a.es_anio_parcial
FROM DBVictimizacionConfianzaPNP.dm.VictimizacionConfianzaPNP a
LEFT JOIN dw.dim_indicador i ON i.indicador = a.indicador;
GO

DECLARE @vistas INT = (SELECT COUNT(*) FROM sys.views WHERE schema_id = SCHEMA_ID(N'stg'));
PRINT N'Vistas creadas: ' + CONVERT(NVARCHAR(10), @vistas) + N'.';
GO

/* ---------------------------------------------------------------------------
   PROCEDIMIENTO USADO POR EL ORQUESTADOR SSIS (00_Orquestador.dtsx)

   Ejecuta dtexec mediante xp_cmdshell, captura toda la salida y lanza un error
   si el paquete NO termina con DTSER_SUCCESS. Sin esta comprobacion,
   xp_cmdshell devuelve exito aunque el proceso hijo haya fallado y el
   orquestador SSIS terminaria "verde" sin cargar datos.

   Requisito de entorno: la cuenta de servicio de SQL Server
   (NT SERVICE\MSSQLSERVER) debe tener permisos de lectura sobre la carpeta
   Source\Proyecto_EF_SSIS y de traversal sobre sus carpetas padre.
   --------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE etl.sp_EjecutarPaqueteSSIS
    @RutaPaquete NVARCHAR(4000),
    @RutaDtexec  NVARCHAR(4000) = N'C:\Program Files\Microsoft SQL Server\170\DTS\Binn\DTExec.exe'
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @cmd    NVARCHAR(4000);
    DECLARE @salida TABLE (linea NVARCHAR(4000));

    EXEC sp_configure 'show advanced options', 1; RECONFIGURE;
    EXEC sp_configure 'xp_cmdshell', 1; RECONFIGURE;

    -- Doble comilla inicial/final para que cmd.exe respete los espacios en la ruta.
    SET @cmd = N'""' + @RutaDtexec + N'" /f "' + @RutaPaquete + N'""';

    INSERT INTO @salida (linea)
    EXEC master.dbo.xp_cmdshell @cmd;

    IF NOT EXISTS (SELECT 1 FROM @salida WHERE linea LIKE N'%DTSER_SUCCESS (0)%')
    BEGIN
        DECLARE @detalle NVARCHAR(1000);
        SELECT TOP 1 @detalle = linea
        FROM @salida
        WHERE linea LIKE N'%Error:%'
           OR linea LIKE N'%denegado%'
           OR linea LIKE N'%not recognized%'
           OR linea LIKE N'%no se reconoce%'
           OR linea LIKE N'%failed%'
           OR linea LIKE N'%fallo%'
        ORDER BY linea;

        DECLARE @motivo NVARCHAR(1000) = ISNULL(@detalle, N'la salida de dtexec no contiene DTSER_SUCCESS');

        RAISERROR(N'Fallo al ejecutar el paquete SSIS "%s". Detalle: %s', 16, 1,
                  @RutaPaquete, @motivo);
    END
END
GO

PRINT N'Procedimiento etl.sp_EjecutarPaqueteSSIS creado.';
GO
