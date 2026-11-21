# Módulo EDA — PySpark SQL + Matplotlib + Streamlit

Este módulo complementa el proyecto `EF_Final` con dos Análisis Exploratorios de Datos (EDA) ejecutados en **PySpark SQL** (entorno Conda `ciencia-de-datos`) con gráficas en **Matplotlib** y **3 aplicaciones Streamlit** listas para presentar en vivo de forma instantánea.

## Estructura

```text
EDA/
  EDA-Datos-Crudos/
    eda_datos_crudos.ipynb        # EDA Pre-ETL sobre los 4 conjuntos de CSVs crudos (PySpark SQL)
    app_eda_crudos.py             # App Streamlit del EDA de datos crudos
    run_streamlit_crudos.bat      # Lanzador 1-clic
    outputs/                      # Métricas JSON/CSV y gráficas PNG exportadas por el notebook
  EDA-Datamarts/
    eda_datamarts.ipynb           # EDA Post-ETL leyendo los 4 DataMarts desde SQL Server (PySpark SQL)
    app_eda_datamarts.py          # App Streamlit del EDA de DataMarts procesados
    run_streamlit_datamarts.bat   # Lanzador 1-clic
    outputs/                      # Métricas JSON/CSV y gráficas PNG exportadas por el notebook
  app_comparativa_eda.py          # App Streamlit ejecutiva: Antes vs Después
  run_streamlit_comparativa.bat   # Lanzador 1-clic
```

## Cómo ejecutar las presentaciones en Streamlit

Puedes hacer doble clic en cualquiera de los `.bat` o ejecutar en PowerShell:

```powershell
conda activate ciencia-de-datos

# 1. Presentación EDA Datos Crudos (Pre-ETL)
streamlit run EDA/EDA-Datos-Crudos/app_eda_crudos.py

# 2. Presentación EDA DataMarts Procesados (Post-ETL)
streamlit run EDA/EDA-Datamarts/app_eda_datamarts.py

# 3. Presentación Comparativa Antes vs Después
streamlit run EDA/app_comparativa_eda.py
```

## Cómo re-ejecutar los notebooks

Ambos notebooks ya están ejecutados con sus salidas, gráficas y archivos en `outputs/`. Si vuelves a correr los ETL y quieres refrescar los resultados:

```powershell
conda activate ciencia-de-datos
jupyter nbconvert --to notebook --execute --inplace EDA/EDA-Datos-Crudos/eda_datos_crudos.ipynb
jupyter nbconvert --to notebook --execute --inplace EDA/EDA-Datamarts/eda_datamarts.ipynb
```

> **Nota de conexión SQL Server (`eda_datamarts.ipynb`):** Por defecto se conecta a `(localdb)\MSSQLLocalDB` con Autenticación de Windows. Para usar `localhost`, define `$env:SQL_SERVER = "localhost"` o cambia la variable `SQL_SERVER` en la primera celda del notebook.
