# Guía Paso a Paso: Construcción del Dashboard Dinámico en Power BI Desktop (`DW_ProyectoEF` / `Modelo_DW_ProyectoEF`)

Esta guía detalla paso a paso cómo conectar **Power BI Desktop** en vivo (*Connect Live*) al cubo tabular **`Modelo_DW_ProyectoEF`** en **SQL Server Analysis Services (SSAS)** y construir un reporte dinámico de **5 páginas** para responder las **5 preguntas guía (Q1–Q5)** sin duplicar datos ni romper las reglas de agregación.

> **Referencia de medidas DAX**: todas las medidas citadas en esta guía provienen de `SSAS/Medidas_DAX_ProyectoEF.dax` y las columnas de las 12 dimensiones provienen de `Database/05_datawarehouse_ddl.sql`.

---

## 1. Conexión en Vivo (Connect Live) desde Power BI Desktop a SSAS

1. Abre **Power BI Desktop**.
2. En la pestaña **Inicio**, haz clic en **Obtener datos** → **Más...** → **Base de datos** → **Base de datos de SQL Server Analysis Services** → **Conectar**.
3. Configura la conexión:
   - **Servidor**: `localhost` *(o el nombre de tu instancia SSAS Tabular)*.
   - **Base de datos**: `Modelo_DW_ProyectoEF` *(opcional en este paso; se puede elegir en el navegador)*.
   - **Modo de conectividad**: selecciona **Conectar en directo** (*Connect live*).
   > **Importante**: no uses *Importar*, porque el modo *Connect Live* respeta las relaciones de constelación, las jerarquías y las medidas DAX del cubo SSAS (como promedios de porcentajes y separación por `unidad_medida`).
4. Haz clic en **Aceptar**, selecciona **`Modelo_DW_ProyectoEF`** en el Navegador y pulsa **Aceptar**.
5. En el panel **Campos / Datos** de la derecha verás las 12 tablas `dim_*` y las 4 tablas `fact_*` con sus medidas agrupadas.

---

## 2. Reglas Generales del Reporte (Antes de Crear Visuales)

1. **Años parciales**:
   - `2026` es parcial (enero–octubre) en Denuncias y Producción Policial (`es_anio_parcial = TRUE`).
   - `2013` es parcial en Victimización y Confianza PNP (sin confianza PNP).
   - Para comparaciones históricas limpias, usa las medidas ya filtradas o aplica el filtro `dim_tiempo[anio]` en el rango completo de cada página.
2. **Ámbito en Victimización (`dim_departamento[ambito]`)**:
   - En las páginas 4 y 5, aplica siempre un **filtro de página** `dim_departamento[ambito] = "DEPARTAMENTO"` para no mezclar la fila `NACIONAL` con los 26 departamentos.
3. **Navegación entre páginas**:
   - Crea 5 pestañas en la parte inferior: `1. Denuncias`, `2. Desaparecidos`, `3. Producción Policial`, `4. Victimización y Confianza`, `5. Análisis Cruzado`.
   - Opcional: agrega un **Navegador de páginas** (**Insertar** → **Botones** → **Navegador** → **Navegador de páginas**) en la cabecera de cada hoja para moverte con un clic.

---

## 3. Diseño Paso a Paso de las 5 Páginas (Q1–Q5)

### Página 1: `1. Denuncias` (Pregunta Q1 — 2018–2025)
> *¿Cuáles son las modalidades delictivas más recurrentes y cómo evolucionaron por año y mes (estacionalidad)?*

1. **Filtros de página**:
   - Arrastra `dim_tiempo[anio]` al panel *Filtros de esta página* → selecciona `2018` a `2025` *(excluye 2026 parcial para comparativas anuales)*.
2. **Segmentadores (Slicers) superiores**:
   - `dim_tiempo[anio]` (lista o entre).
   - `dim_departamento[macroregion]` y `dim_departamento[departamento]`.
   - `dim_modalidad[modalidad]`.
3. **Tarjetas (KPIs) en la fila superior**:
   - Tarjeta 1: `Total Denuncias`
   - Tarjeta 2: `Promedio Mensual Denuncias`
   - Tarjeta 3: `Variacion YoY Denuncias %`
4. **Visual 1 — Modalidades más recurrentes (Gráfico de barras horizontales apiladas/agrupadas)**:
   - **Eje Y**: `dim_modalidad[modalidad]`
   - **Eje X**: `Total Denuncias`
   - **Información sobre herramientas (Tooltips)**: `% Participacion Modalidad`, `Ranking Modalidad`
   - Ordenar por `Total Denuncias` descendente.
5. **Visual 2 — Evolución y estacionalidad mensual (Gráfico de líneas)**:
   - **Eje X**: `dim_tiempo[mes_corto]` *(ordenado por `dim_tiempo[mes_numero]`)*
   - **Leyenda**: `dim_tiempo[anio]`
   - **Eje Y**: `Total Denuncias`
   - **Tooltips**: `% Estacionalidad Mensual`, `Denuncias Anio Anterior`
6. **Visual 3 — Desglose territorial con Drill-Down (Matriz)**:
   - **Filas**: `dim_departamento[departamento]` → `dim_provincia[provincia]` → `dim_ubigeo[distrito]`
   - **Valores**: `Total Denuncias`, `% Participacion Modalidad`

---

### Página 2: `2. Desaparecidos` (Pregunta Q2 — 2019–2025)
> *¿Qué perfil predomina por sexo y rango de edad, y cuántos casos son menores de 18 años?*

1. **Filtros de página**:
   - `dim_tiempo[anio]` entre `2019` y `2025`.
2. **Segmentadores (Slicers)**:
   - `dim_tiempo[anio]`
   - `dim_departamento[departamento]`
   - `dim_nacionalidad[nacionalidad]`
3. **Tarjetas (KPIs)**:
   - Tarjeta 1: `Total Desaparecidos`
   - Tarjeta 2: `Total Desaparecidos Menores 18`
   - Tarjeta 3: `% Desaparecidos Menores 18`
   - Tarjeta 4: `Desaparecidos No Informado` *(transparencia de registros con sexo o edad no informados)*
4. **Visual 1 — Perfil por Rango de Edad y Sexo (Gráfico de columnas agrupadas)**:
   - **Eje X**: `dim_rango_edad[rango_edad]` *(verificando orden por `dim_rango_edad[orden_edad]`)*
   - **Leyenda**: `dim_sexo[sexo_descripcion]`
   - **Eje Y**: `Total Desaparecidos`
   - **Tooltips**: `% Participacion Perfil Desaparecidos`
5. **Visual 2 — Proporción Menores de 18 años (Gráfico de anillos / Donut)**:
   - **Leyenda**: `dim_rango_edad[es_menor_18]`
   - **Valores**: `Total Desaparecidos`
6. **Visual 3 — Evolución anual por sexo (Gráfico de líneas o columnas apiladas)**:
   - **Eje X**: `dim_tiempo[anio]`
   - **Leyenda**: `dim_sexo[sexo_descripcion]`
   - **Eje Y**: `Total Desaparecidos`

---

### Página 3: `3. Producción Policial` (Pregunta Q3 — 2023–2025)
> *¿Cuántos operativos, detenidos, bandas desarticuladas, kilos de droga y soles incautados se registraron por año y tipo de dependencia (`dir_reg_fre`)?*

> **Regla crítica**: nunca grafiques `KILOS` junto a `SOLES` o `PERSONAS` en el mismo eje numérico. Usa tarjetas y gráficos separados por unidad de medida.

1. **Filtros de página**:
   - `dim_tiempo[anio]` entre `2023` y `2025` *(excluye 2026 parcial para comparativas anuales)*.
2. **Segmentadores (Slicers)**:
   - `dim_tiempo[anio]`
   - `dim_dependencia[dir_reg_fre]`
   - `dim_dependencia[dependencia]`
3. **Tarjetas (KPIs — una por magnitud)**:
   - `Operativos Policiales`
   - `Total Detenidos`
   - `Intervenciones Extranjeros`
   - `Bandas Desarticuladas`
   - `Organizaciones Criminales Desarticuladas`
   - `Kilos de Droga Incautada`
   - `Dinero Incautado Soles`
   - `Contrabando Valorizacion Soles`
4. **Visual 1 — Kilos de Droga Incautada por Año y Tipo de Dependencia (Columnas agrupadas)**:
   - **Eje X**: `dim_tiempo[anio]`
   - **Leyenda**: `dim_dependencia[dir_reg_fre]`
   - **Eje Y**: `Kilos de Droga Incautada`
5. **Visual 2 — Dinero Incautado en Soles por Año (Columnas agrupadas)**:
   - **Eje X**: `dim_tiempo[anio]`
   - **Leyenda**: `dim_dependencia[dir_reg_fre]`
   - **Eje Y**: `Dinero Incautado Soles`
6. **Visual 3 — Detalle completo por Variable y Unidad (Matriz)**:
   - **Filas**: `dim_variable[unidad_medida]` → `dim_variable[variable]`
   - **Columnas**: `dim_tiempo[anio]`
   - **Valores**: `Valor Produccion Unitario` *(respetando la unidad de cada fila sin sumar magnitudes incompatibles)*

---

### Página 4: `4. Victimización y Confianza` (Pregunta Q4 — 2014–2024)
> *¿Qué departamentos tienen más percepción de inseguridad y menos confianza en la PNP?*

1. **Filtros de página (obligatorio)**:
   - `dim_departamento[ambito]` = **`DEPARTAMENTO`**
   - `dim_tiempo[anio]` entre `2014` y `2024` *(excluye 2013 parcial)*
2. **Segmentadores (Slicers)**:
   - `dim_tiempo[anio]` *(recomendado seleccionar `2024` para corte del último año, o dejar multi-año para ver promedio histórico)*
   - `dim_departamento[macroregion]`
3. **Tarjetas (KPIs)**:
   - `Percepcion Inseguridad Promedio %`
   - `Confianza PNP Promedio %`
   - `Victimizacion General Promedio %`
   - `Valor Nacional Referencia %` *(muestra el referente país sin mezclar filas)*
4. **Visual 1 — Departamentos con mayor percepción de inseguridad (Barras horizontales)**:
   - **Eje Y**: `dim_departamento[departamento]`
   - **Eje X**: `Percepcion Inseguridad Promedio %`
   - **Tooltips**: `Ranking Inseguridad Dept`
   - Ordenar descendente por `Percepcion Inseguridad Promedio %`.
5. **Visual 2 — Departamentos con menor confianza en la PNP (Barras horizontales)**:
   - **Eje Y**: `dim_departamento[departamento]`
   - **Eje X**: `Confianza PNP Promedio %`
   - **Tooltips**: `Ranking Menor Confianza Dept`
   - Ordenar **ascendente** por `Confianza PNP Promedio %` *(los más bajos arriba)*.
6. **Visual 3 — Dispersión Inseguridad vs Confianza (Gráfico de dispersión / Scatter)**:
   - **Valores**: `dim_departamento[departamento]`
   - **Eje X**: `Percepcion Inseguridad Promedio %`
   - **Eje Y**: `Confianza PNP Promedio %`
   - **Leyenda**: `dim_departamento[macroregion]`

---

### Página 5: `5. Análisis Cruzado` (Pregunta Q5 — 2019–2025)
> *¿Cómo se comparan denuncias policiales, personas desaparecidas y percepción/confianza por departamento y año?*

1. **Filtros de página (obligatorio)**:
   - `dim_departamento[ambito]` = **`DEPARTAMENTO`**
   - `dim_tiempo[anio]` entre `2019` y `2025`
2. **Segmentadores (Slicers)**:
   - `dim_tiempo[anio]`
   - `dim_departamento[macroregion]`
   - `dim_departamento[departamento]`
3. **Tarjetas (KPIs)**:
   - `Total Denuncias (2019-2025)`
   - `Total Desaparecidos`
   - `Denuncias vs Desaparecidos Ratio`
   - `Percepcion Inseguridad Promedio %`
   - `Confianza PNP Promedio %`
4. **Visual 1 — Denuncias vs Personas Desaparecidas por Departamento (Gráfico combinado de columnas y líneas)**:
   - **Eje X**: `dim_departamento[departamento]`
   - **Eje Y de columna**: `Total Denuncias (2019-2025)`
   - **Eje Y de línea**: `Total Desaparecidos`
   - Ordenar descendente por `Total Denuncias (2019-2025)`.
5. **Visual 2 — Evolución anual cruzada (Gráfico combinado de columnas y líneas)**:
   - **Eje X**: `dim_tiempo[anio]`
   - **Eje Y de columna**: `Total Denuncias (2019-2025)`
   - **Eje Y de línea**: `Total Desaparecidos`
6. **Visual 3 — Tabla comparativa integral por Departamento**:
   - **Filas**: `dim_departamento[departamento]`
   - **Valores**:
     - `Total Denuncias (2019-2025)`
     - `Total Desaparecidos`
     - `Denuncias vs Desaparecidos Ratio`
     - `Percepcion Inseguridad Promedio %`
     - `Confianza PNP Promedio %`

---

## 4. Validación Rápida en Power BI Desktop

Antes de guardar tu archivo `.pbix`:
1. Verifica que **ninguna tarjeta de Victimización** muestre valores mayores a `100%` (si ves `5810%`, revisa que la medida en SSAS tenga formato `0.00"%"` y no `0.00%`).
2. Verifica que en **Página 3 (Producción)** el gráfico de **Kilos de Droga** y el de **Dinero Incautado** estén separados y coincidan con los totales de `Database/06_dw_validacion.sql`.
3. Verifica que en **Página 4 y 5**, al quitar o poner filtros de año, la fila `NACIONAL` no aparezca en las barras de departamentos.
4. Guarda el proyecto como `PowerBI/Dashboard_ProyectoEF.pbix`.
