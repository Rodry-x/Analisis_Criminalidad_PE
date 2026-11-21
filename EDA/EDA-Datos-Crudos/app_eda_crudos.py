import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="EDA Datos Crudos — Proyecto EF Big Data",
    page_icon="🔍",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "outputs"
JSON_PATH = OUT_DIR / "resumen_crudos.json"

st.title("🔍 EDA de Datos Crudos (Pre-ETL) — MININTER Perú")
st.caption("Procesado con PySpark SQL y visualizado con Matplotlib | Resultados precalculados desde `eda_datos_crudos.ipynb`")

if not JSON_PATH.exists():
    st.error(
        "No se encontró `outputs/resumen_crudos.json`. Ejecuta primero el notebook "
        "`EDA/EDA-Datos-Crudos/eda_datos_crudos.ipynb` para generar los resultados."
    )
    st.stop()

@st.cache_data
def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

@st.cache_data
def load_csv(name: str):
    p = OUT_DIR / name
    return pd.read_csv(p) if p.exists() else pd.DataFrame()

data = load_json(JSON_PATH)
ds = data["datasets"]

# Sidebar
st.sidebar.header("Navegación EDA Crudo")
seccion = st.sidebar.radio(
    "Selecciona una vista:",
    [
        "Resumen Ejecutivo y Codificación",
        "1. Denuncias Policiales (2018–2026)",
        "2. Personas Desaparecidas (2019–2025)",
        "3. Producción Policial (2023–2026)",
        "4. Victimización y Confianza (2013–2024)",
        "Matriz de Hallazgos → Reglas ETL",
    ],
)
st.sidebar.divider()
st.sidebar.info(f"**Motor:** {data['motor']}\n\n**Archivos CSV:** {data['total_archivos_csv']}\n\n**Total filas crudas:** {data['total_filas_crudas']:,}")

def show_img(filename: str, caption: str = ""):
    p = OUT_DIR / filename
    if p.exists():
        st.image(str(p), caption=caption, width="stretch")
    else:
        st.warning(f"Imagen no encontrada: {filename}")

if seccion == "Resumen Ejecutivo y Codificación":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Archivos CSV crudos", data["total_archivos_csv"])
    c2.metric("Total filas crudas", f"{data['total_filas_crudas']:,}")
    c3.metric("Archivos en CP1252", data["archivos_cp1252"], delta="Requieren UTF-8", delta_color="inverse")
    c4.metric("Problemas detectados", data["total_hallazgos"], delta="Justifican el ETL", delta_color="inverse")

    st.subheader("Resumen General de los 4 Datasets Crudos (PySpark SQL)")
    st.dataframe(load_csv("resumen_general_crudos.csv"), width="stretch", hide_index=True)

    st.subheader("Mapa de Problemas de Calidad por Dataset y Severidad")
    show_img("07_crudo_resumen_hallazgos.png")

    st.subheader("Auditoría de Archivos CSV y Codificación Detectada")
    df_arch = load_csv("archivos_codificacion_crudos.csv")
    st.dataframe(df_arch, width="stretch", hide_index=True)

elif seccion == "1. Denuncias Policiales (2018–2026)":
    d1 = ds["denuncias"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filas crudas", f"{d1['filas']:,}")
    c2.metric("Denuncias acumuladas", f"{d1['total_denuncias']:,}")
    c3.metric("Ubigeos sin cero inicial (<6 díg.)", f"{d1['ubigeos_5_digitos']:,}", delta="Normalizar a CHAR(6)", delta_color="inverse")
    c4.metric("Año 2026 (parcial)", f"{d1['meses_2026']} meses", delta="Sin Nov–Dic", delta_color="inverse")

    st.warning(
        "**Hallazgos clave:** Los departamentos con prefijo `01`–`09` perdieron el cero inicial en `UBIGEO_HECHO` "
        "(quedando en 5 dígitos), el ubigeo `160801` aparece bajo dos provincias (`MAYNAS` y `PUTUMAYO`), "
        "y `2026` solo contiene enero–octubre."
    )
    show_img("01_crudo_denuncias_cobertura_ubigeo.png")
    show_img("02_crudo_denuncias_modalidades.png")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Cobertura Anual Cruda")
        st.dataframe(load_csv("d1_crudo_anual.csv"), width="stretch", hide_index=True)
    with col_b:
        st.subheader("Conflicto en Ubigeo 160801")
        st.dataframe(load_csv("d1_crudo_conflicto_ubigeo.csv"), width="stretch", hide_index=True)

elif seccion == "2. Personas Desaparecidas (2019–2025)":
    d2 = ds["desaparecidos"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filas crudas", f"{d2['filas']:,}")
    c2.metric("Casos acumulados", f"{d2['total_casos']:,}")
    c3.metric("Dptos. no canónicos", f"{d2['dptos_no_canonicos']:,}", delta="Tildes / CALLAO", delta_color="inverse")
    c4.metric("Vacíos SEXO / EDAD", f"{d2['sexo_vacio']} / {d2['rango_edad_vacio']:,}", delta="Preservar como NULL", delta_color="off")

    st.warning(
        "**Hallazgos clave:** El archivo viene en codificación **CP1252** (rompe `Á, Í, Ñ, Ó, Ú` si se abre como UTF-8), "
        "17,147 filas tienen nombres de departamento con tildes o `CALLAO`, existen vacíos en `SEXO` (83) y `RANGO_EDAD` (1,197), "
        "y el ubigeo `150121` mezcla `PUEBLO LIBRE` con `MAGDALENA VIEJA`."
    )
    show_img("03_crudo_desaparecidos_calidad.png")
    show_img("04_crudo_desaparecidos_perfil.png")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Departamentos por Homologar")
        st.dataframe(load_csv("d2_crudo_dptos_no_canonicos.csv"), width="stretch", hide_index=True)
    with col_b:
        st.subheader("Conflicto en Ubigeo 150121")
        st.dataframe(load_csv("d2_crudo_conflicto_150121.csv"), width="stretch", hide_index=True)

elif seccion == "3. Producción Policial (2023–2026)":
    d3 = ds["produccion"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filas crudas", f"{d3['filas']:,}")
    c2.metric("Filas con VALOR = 0", f"{d3['filas_valor_cero']:,}", delta="Válidas (sin reporte)", delta_color="off")
    c3.metric("Variables mezcladas", d3["variables_mezcladas"], delta="Sin unidad_medida", delta_color="inverse")
    c4.metric("Año 2026 (parcial)", f"{d3['meses_2026']} meses", delta="Meses en texto ENE..OCT", delta_color="inverse")

    st.warning(
        "**Hallazgos clave:** `MES` viene como abreviatura (`ENE`..`SET`..`DIC`), `VALOR` mezcla kilos, soles, "
        "envoltorios, personas y operativos sin columna `unidad_medida`, y `DIR_REG_FRE` trae `Región` con tilde "
        "más las inconsistencias `RP ICA` y `RP TUMBES`."
    )
    show_img("05_crudo_produccion_calidad.png")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Cobertura y Ceros por Año")
        st.dataframe(load_csv("d3_crudo_anual.csv"), width="stretch", hide_index=True)
    with col_b:
        st.subheader("Valores Crudos de DIR_REG_FRE")
        st.dataframe(load_csv("d3_crudo_dir_reg_fre.csv"), width="stretch", hide_index=True)

    st.subheader("Las 18 Variables Mezcladas en VALOR (Crudo)")
    st.dataframe(load_csv("d3_crudo_variables.csv"), width="stretch", hide_index=True)

elif seccion == "4. Victimización y Confianza (2013–2024)":
    d4 = ds["victimizacion"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filas crudas", f"{d4['filas']:,}")
    c2.metric("Códigos desalineados (2013)", d4["codigos_desalineados_2013"], delta="Corregir desde dpto.", delta_color="inverse")
    c3.metric("Filas NACIONAL en dpto.", d4["filas_nacionales_en_dpto"], delta="Separar por ambito", delta_color="inverse")
    c4.metric("Cobertura 2013 (parcial)", f"{d4['filas_2013']} / 135", delta="Sin confianza PNP", delta_color="inverse")

    st.warning(
        "**Hallazgos clave:** Codificación **CP1252**, columna `PERIODO` constante (`AÑO`), grano anual sin mes, "
        "año 2013 incompleto (`107` filas), 58 filas nacionales mezcladas en `DEPARTAMENTO`, 354 filas con tildes "
        "y **6 filas de 2013 con `COD_UBICACION` desalineado** (detectadas con PySpark SQL)."
    )
    show_img("06_crudo_victimizacion_cobertura_rangos.png")

    st.subheader("6 Filas con COD_UBICACION Desalineado en 2013 (Detectadas por PySpark SQL)")
    st.dataframe(load_csv("d4_crudo_codigos_desalineados.csv"), width="stretch", hide_index=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Cobertura por Año")
        st.dataframe(load_csv("d4_crudo_anual.csv"), width="stretch", hide_index=True)
    with col_b:
        st.subheader("Rango Porcentual por Indicador (No Sumables)")
        st.dataframe(load_csv("d4_crudo_indicadores.csv"), width="stretch", hide_index=True)

else:
    st.subheader("Matriz Completa de Hallazgos de Calidad y Reglas de Limpieza ETL")
    df_h = load_csv("matriz_hallazgos_crudos.csv")
    col1, col2 = st.columns(2)
    ds_opts = ["Todos"] + sorted(df_h["dataset"].unique().tolist())
    sev_opts = ["Todas", "Alta", "Media", "Baja"]
    f_ds = col1.selectbox("Filtrar por Dataset", ds_opts)
    f_sev = col2.selectbox("Filtrar por Severidad", sev_opts)

    df_view = df_h.copy()
    if f_ds != "Todos":
        df_view = df_view[df_view["dataset"] == f_ds]
    if f_sev != "Todas":
        df_view = df_view[df_view["severidad"] == f_sev]

    st.dataframe(df_view, width="stretch", hide_index=True)
    show_img("07_crudo_resumen_hallazgos.png")
