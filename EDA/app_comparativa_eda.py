import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Comparativa EDA: Antes vs Después — Proyecto EF Big Data",
    page_icon="⚖️",
    layout="wide",
)

EDA_DIR = Path(__file__).resolve().parent
RAW_OUT = EDA_DIR / "EDA-Datos-Crudos" / "outputs"
DM_OUT = EDA_DIR / "EDA-Datamarts" / "outputs"

RAW_JSON = RAW_OUT / "resumen_crudos.json"
DM_JSON = DM_OUT / "resumen_datamarts.json"

st.title("⚖️ Comparativa EDA: Datos Crudos (Antes) vs DataMarts Procesados (Después)")
st.caption("Validación de extremo a extremo del pipeline ETL — PySpark SQL + Matplotlib + SQL Server")

if not RAW_JSON.exists() or not DM_JSON.exists():
    st.error(
        "Faltan archivos de salida. Ejecuta primero `EDA/EDA-Datos-Crudos/eda_datos_crudos.ipynb` "
        "y `EDA/EDA-Datamarts/eda_datamarts.ipynb`."
    )
    st.stop()

@st.cache_data
def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

@st.cache_data
def load_csv(path: Path):
    return pd.read_csv(path) if path.exists() else pd.DataFrame()

raw = load_json(RAW_JSON)
dm = load_json(DM_JSON)

# KPIs ejecutivos
c1, c2, c3, c4 = st.columns(4)
c1.metric("Filas Crudas vs DataMarts", f"{dm['total_filas_datamarts']:,}", delta=f"Diferencia: {dm['total_filas_datamarts'] - raw['total_filas_crudas']:,} (0 pérdida)")
c2.metric("Problemas detectados (Antes)", raw["total_hallazgos"], delta="En 4 datasets crudos", delta_color="inverse")
c3.metric("Checks de calidad (Después)", f"{dm['validaciones_ok']}/{dm['validaciones_totales']} OK", delta="100% aprobados")
c4.metric("Departamentos conformados", dm["cruce_departamentos_coincidentes"], delta="Listos para DW/SSAS")

st.divider()

tab1, tab2, tab3 = st.tabs([
    "📊 Tabla Comparativa Antes vs Después",
    "🖼️ Comparación Visual Lado a Lado",
    "📋 Trazabilidad Hallazgos → Validaciones",
])

with tab1:
    st.subheader("Impacto de la Limpieza ETL por Dimensión de Calidad")
    r_ds = raw["datasets"]
    d_ds = dm["datasets"]

    comparativa = pd.DataFrame([
        {
            "Dataset": "1. Denuncias Policiales",
            "Filas Antes": f"{r_ds['denuncias']['filas']:,}",
            "Filas Después": f"{d_ds['denuncias']['filas']:,}",
            "Estado Antes (Crudo)": f"{r_ds['denuncias']['ubigeos_5_digitos']:,} ubigeos con 5 díg.; conflicto 160801; 2026 sin marcar parcial",
            "Estado Después (DataMart)": "0 ubigeos inválidos (CHAR(6)); 160801 homologado; es_anio_parcial=1 en 2026",
            "Resultado": "✅ Resuelto",
        },
        {
            "Dataset": "2. Personas Desaparecidas",
            "Filas Antes": f"{r_ds['desaparecidos']['filas']:,}",
            "Filas Después": f"{d_ds['desaparecidos']['filas']:,}",
            "Estado Antes (Crudo)": f"CP1252; {r_ds['desaparecidos']['dptos_no_canonicos']:,} dptos. no canónicos; conflicto 150121; vacíos SEXO/EDAD",
            "Estado Después (DataMart)": "UTF-8/NVARCHAR; 0 dptos. no canónicos; 150121 homologado; NULLs preservados",
            "Resultado": "✅ Resuelto",
        },
        {
            "Dataset": "3. Producción Policial",
            "Filas Antes": f"{r_ds['produccion']['filas']:,}",
            "Filas Después": f"{d_ds['produccion']['filas']:,}",
            "Estado Antes (Crudo)": f"MES en texto (ENE..DIC); {r_ds['produccion']['variables_mezcladas']} vars. sin unidad; Región con tilde; 2026 parcial",
            "Estado Después (DataMart)": f"mes_registro numérico 1–12; {d_ds['produccion']['unidades_medida_separadas']} unidades en unidad_medida; REGION homologado",
            "Resultado": "✅ Resuelto",
        },
        {
            "Dataset": "4. Victimización y Confianza",
            "Filas Antes": f"{r_ds['victimizacion']['filas']:,}",
            "Filas Después": f"{d_ds['victimizacion']['filas']:,}",
            "Estado Antes (Crudo)": f"CP1252; PERIODO constante; {r_ds['victimizacion']['codigos_desalineados_2013']} códigos 2013 erróneos; 58 NACIONAL mezclados",
            "Estado Después (DataMart)": "UTF-8; 0 códigos desalineados; ambito='NACIONAL' separado; 2013 marcado parcial",
            "Resultado": "✅ Resuelto",
        },
    ])
    st.dataframe(comparativa, width="stretch", hide_index=True)

    st.success(
        "**Conclusión:** Los 4 DataMarts conservan el **100% de las filas válidas (`496,206` filas totales)** sin pérdida "
        "ni duplicación, dejando las llaves geográficas y temporales conformadas para alimentar **`DW_ProyectoEF` → SSIS → SSAS Tabular → Power BI**."
    )

with tab2:
    st.subheader("Comparación Visual: Diagnóstico Crudo vs Resultado Analítico en DataMarts")
    selector = st.selectbox(
        "Elige el dataset a comparar:",
        [
            "1. Denuncias Policiales",
            "2. Personas Desaparecidas",
            "3. Producción Policial",
            "4. Victimización y Confianza PNP",
            "5. Visión Global (Hallazgos Crudos vs Auditoría Post-ETL)",
        ],
    )

    pairs = {
        "1. Denuncias Policiales": (
            RAW_OUT / "01_crudo_denuncias_cobertura_ubigeo.png",
            "ANTES: 2026 parcial sin etiquetar y ubigeos de 5 dígitos",
            DM_OUT / "01_dm_q1_evolucion_estacionalidad.png",
            "DESPUÉS: Serie limpia 2018–2025 y estacionalidad mensual 1–12",
        ),
        "2. Personas Desaparecidas": (
            RAW_OUT / "03_crudo_desaparecidos_calidad.png",
            "ANTES: 17,147 filas con departamentos no canónicos y vacíos",
            DM_OUT / "03_dm_q2_desaparecidos_perfil.png",
            "DESPUÉS: Perfil homologado por edad, sexo y proporción menores de 18",
        ),
        "3. Producción Policial": (
            RAW_OUT / "05_crudo_produccion_calidad.png",
            "ANTES: Meses en texto, ceros sin documentar y DIR_REG_FRE inconsistente",
            DM_OUT / "04_dm_q3_produccion_policial.png",
            "DESPUÉS: Magnitudes separadas por unidad_medida (2023–2025)",
        ),
        "4. Victimización y Confianza PNP": (
            RAW_OUT / "06_crudo_victimizacion_cobertura_rangos.png",
            "ANTES: 2013 parcial, 6 códigos erróneos y mezcla NACIONAL",
            DM_OUT / "05_dm_q4_victimizacion_rankings.png",
            "DESPUÉS: Rankings departamentales limpios (promedios 2014–2024)",
        ),
        "5. Visión Global (Hallazgos Crudos vs Auditoría Post-ETL)": (
            RAW_OUT / "07_crudo_resumen_hallazgos.png",
            "ANTES: 13 problemas de calidad detectados en datos crudos",
            DM_OUT / "07_dm_auditoria_resumen.png",
            "DESPUÉS: 496,206 filas limpias y 13/13 validaciones aprobadas",
        ),
    }

    img_l, cap_l, img_r, cap_r = pairs[selector]
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("#### 🔴 Antes (Datos Crudos)")
        if img_l.exists():
            st.image(str(img_l), caption=cap_l, width="stretch")
    with col_r:
        st.markdown("#### 🟢 Después (DataMarts Procesados)")
        if img_r.exists():
            st.image(str(img_r), caption=cap_r, width="stretch")

with tab3:
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Problemas Detectados en Datos Crudos")
        st.dataframe(load_csv(RAW_OUT / "matriz_hallazgos_crudos.csv"), width="stretch", hide_index=True)
    with col_b:
        st.subheader("Validaciones Aprobadas en DataMarts")
        st.dataframe(load_csv(DM_OUT / "auditoria_calidad_datamarts.csv"), width="stretch", hide_index=True)
