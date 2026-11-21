import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="EDA DataMarts Procesados — Proyecto EF Big Data",
    page_icon="✅",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "outputs"
JSON_PATH = OUT_DIR / "resumen_datamarts.json"

st.title("✅ EDA de DataMarts Procesados (Post-ETL) — SQL Server + PySpark SQL")
st.caption("Validación post-ETL y análisis Q1–Q5 con PySpark SQL y Matplotlib | Resultados precalculados desde `eda_datamarts.ipynb`")

if not JSON_PATH.exists():
    st.error(
        "No se encontró `outputs/resumen_datamarts.json`. Ejecuta primero el notebook "
        "`EDA/EDA-Datamarts/eda_datamarts.ipynb` para generar los resultados."
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

st.sidebar.header("Navegación EDA DataMarts")
seccion = st.sidebar.radio(
    "Selecciona una vista:",
    [
        "Auditoría de Calidad Post-ETL",
        "Q1: Denuncias Policiales (2018–2025)",
        "Q2: Personas Desaparecidas (2019–2025)",
        "Q3: Producción Policial (2023–2025)",
        "Q4: Victimización y Confianza (2014–2024)",
        "Q5: Cruce Multi-DataMart (2019–2025)",
    ],
)
st.sidebar.divider()
st.sidebar.success(
    f"**SQL Server:** `{data['sql_server']}`\n\n"
    f"**Motor:** {data['motor']}\n\n"
    f"**Validaciones:** {data['validaciones_ok']}/{data['validaciones_totales']} OK"
)

def show_img(filename: str, caption: str = ""):
    p = OUT_DIR / filename
    if p.exists():
        st.image(str(p), caption=caption, width="stretch")
    else:
        st.warning(f"Imagen no encontrada: {filename}")

if seccion == "Auditoría de Calidad Post-ETL":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total filas en DataMarts", f"{data['total_filas_datamarts']:,}")
    c2.metric("Validaciones aprobadas", f"{data['validaciones_ok']} / {data['validaciones_totales']}", delta="100% OK")
    c3.metric("Incidencias residuales", data["validaciones_fallidas"], delta="0 errores")
    c4.metric("Departamentos conformados", data["cruce_departamentos_coincidentes"], delta="D1 = D2 = D4")

    st.success(
        "Las 13 pruebas de integridad ejecutadas con **PySpark SQL** sobre los 4 DataMarts aprobaron sin errores: "
        "0 duplicados por grano, 0 ubigeos inválidos, 26 departamentos canónicos idénticos, meses numéricos 1–12, "
        "`unidad_medida` poblada, `ambito` separado y 0 códigos desalineados."
    )

    show_img("07_dm_auditoria_resumen.png")

    col_a, col_b = st.columns([1.2, 1.8])
    with col_a:
        st.subheader("Resumen por DataMart")
        st.dataframe(load_csv("resumen_general_datamarts.csv"), width="stretch", hide_index=True)
    with col_b:
        st.subheader("Checklist de Auditoría Post-ETL (PySpark SQL)")
        st.dataframe(load_csv("auditoria_calidad_datamarts.csv"), width="stretch", hide_index=True)

elif seccion == "Q1: Denuncias Policiales (2018–2025)":
    d1 = ds["denuncias"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Denuncias (2018–2025 completos)", f"{d1['total_denuncias_2018_2025']:,}")
    c2.metric("Modalidad líder", d1["modalidad_lider"], delta=f"{d1['modalidad_lider_pct']:.2f}%")
    c3.metric("Ubigeos inválidos / Duplicados", "0 / 0", delta="Limpio")

    show_img("01_dm_q1_evolucion_estacionalidad.png")
    show_img("02_dm_q1_modalidades.png")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Serie Anual (Años Completos)")
        st.dataframe(load_csv("q1_denuncias_anual.csv"), width="stretch", hide_index=True)
    with col_b:
        st.subheader("Participación por Modalidad")
        st.dataframe(load_csv("q1_denuncias_modalidad.csv"), width="stretch", hide_index=True)

elif seccion == "Q2: Personas Desaparecidas (2019–2025)":
    d2 = ds["desaparecidos"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Total casos (2019–2025)", f"{d2['total_casos']:,}")
    c2.metric("Menores de 18 años", f"{d2['menores_18']:,}", delta=f"{d2['pct_menores_18']:.2f}% del total")
    c3.metric("Dptos. sin canonizar", d2["dptos_no_canonicos"], delta="100% homologado")

    show_img("03_dm_q2_desaparecidos_perfil.png")

    st.subheader("Distribución por Rango de Edad, Sexo y Grupo Etario")
    df_p = load_csv("q2_desaparecidos_perfil.csv")
    grupo = st.selectbox("Filtrar por grupo etario", ["Todos"] + sorted(df_p["grupo_etario"].unique().tolist()))
    if grupo != "Todos":
        df_p = df_p[df_p["grupo_etario"] == grupo]
    st.dataframe(df_p.sort_values("casos", ascending=False), width="stretch", hide_index=True)

elif seccion == "Q3: Producción Policial (2023–2025)":
    d3 = ds["produccion"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Operativos (2023–2025)", f"{d3['operativos_2023_2025']:,}")
    c2.metric("Detenidos (2023–2025)", f"{d3['detenidos_2023_2025']:,}")
    c3.metric("Droga incautada (kg)", f"{d3['kilos_droga_2023_2025']:,.1f}")
    c4.metric("Dinero incautado (S/)", f"S/ {d3['dinero_incautado_soles_2023_2025']:,.0f}")

    st.info(
        "Cada magnitud se analiza de forma independiente usando la columna `unidad_medida` "
        f"({d3['unidades_medida_separadas']} unidades distintas) y excluyendo `2026` (`es_anio_parcial = 1`)."
    )
    show_img("04_dm_q3_produccion_policial.png")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Totales Anuales por Magnitud (2023–2025)")
        st.dataframe(load_csv("q3_produccion_anual.csv"), width="stretch", hide_index=True)
    with col_b:
        st.subheader("Catálogo de Unidades de Medida")
        st.dataframe(load_csv("q3_produccion_unidades.csv"), width="stretch", hide_index=True)

elif seccion == "Q4: Victimización y Confianza (2014–2024)":
    d4 = ds["victimizacion"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Mayor percepción inseguridad", d4["dpto_mayor_inseguridad"], delta=f"{d4['mayor_inseguridad_pct']:.2f}% prom.")
    c2.metric("Menor confianza en la PNP", d4["dpto_menor_confianza"], delta=f"{d4['menor_confianza_pct']:.2f}% prom.", delta_color="inverse")
    c3.metric("Códigos desalineados", d4["codigos_desalineados"], delta="6 corregidos")

    st.info(
        "Todas las métricas filtran `ambito = 'DEPARTAMENTO'` y `es_anio_parcial = 0` (2014–2024), "
        "calculando **promedios porcentuales** (nunca sumas de porcentajes)."
    )
    show_img("05_dm_q4_victimizacion_rankings.png")

    col_a, col_b = st.columns([1.4, 1.0])
    with col_a:
        st.subheader("Ranking Departamental (Promedios 2014–2024 y Corte 2024)")
        st.dataframe(load_csv("q4_victimizacion_departamentos.csv"), width="stretch", hide_index=True)
    with col_b:
        st.subheader("Referente Nacional (ambito = 'NACIONAL')")
        st.dataframe(load_csv("q4_victimizacion_nacional.csv"), width="stretch", hide_index=True)

else:
    st.subheader("Cruce Multi-DataMart por Departamento (2019–2025)")
    st.caption("Unión exacta en PySpark SQL entre `dm_denuncias`, `dm_desaparecidos` y `dm_victimizacion` mediante nombres canónicos de departamento.")
    show_img("06_dm_q5_cruzado_departamentos.png")

    df_q5 = load_csv("q5_cruzado_departamentos.csv")
    dptos_sel = st.multiselect("Filtrar departamentos:", df_q5["departamento"].tolist(), default=[])
    if dptos_sel:
        df_q5 = df_q5[df_q5["departamento"].isin(dptos_sel)]
    st.dataframe(df_q5, width="stretch", hide_index=True)
