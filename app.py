import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Cambio de Producto", layout="wide")
st.title("🔧 Plataforma de Cambio de Producto – Laminador")

@st.cache_data
def cargar_datos_estaticos():
    ddp = pd.read_excel("data/Consolidado_Laminador.xlsx")
    mapa = pd.read_excel("data/Mapa_Homologacion_Producto.xlsx")
    tiempo = pd.read_excel("data/BBDD_Tiempo.xlsx")
    desbaste = pd.read_excel("data/Diagrama_Desbaste.xlsx")
    return ddp, mapa, tiempo, desbaste

df_ddp, df_mapa, df_tiempo, df_desbaste = cargar_datos_estaticos()

st.sidebar.header(":page_facing_up: Subida de Programa")
file_programa = st.sidebar.file_uploader("Subir archivo Programa.xlsx", type=["xlsx"])

def comparar_productos(df_origen, df_destino, columnas):
    resumen = []
    for col in columnas:
        val1 = df_origen.iloc[0].get(col, "")
        val2 = df_destino.iloc[0].get(col, "")
        val1 = None if pd.isna(val1) or val1 == "None" else val1
        val2 = None if pd.isna(val2) or val2 == "None" else val2
        if val1 is None and val2 is None:
            cambia = False
        else:
            cambia = val1 != val2
        resumen.append({
            "Variable Técnica": col,
            "Producto A": val1,
            "Producto B": val2,
            "¿Cambia?": "✅ Sí" if cambia else "❌ No"
        })
    return pd.DataFrame(resumen)

def resaltar_filas(row):
    color = 'background-color: #ffcccc' if row["¿Cambia?"] == "✅ Sí" else ''
    return [color] * len(row)

st.subheader("🔄 Comparador Manual de Productos")
familias = sorted(df_ddp["Familia"].dropna().unique())
colf1, colf2 = st.columns(2)
with colf1:
    familiaA = st.selectbox("Selecciona Familia A", familias, key="famA")
with colf2:
    familiaB = st.selectbox("Selecciona Familia B", familias, key="famB")

df_famA = df_ddp[df_ddp["Familia"] == familiaA]
df_famB = df_ddp[df_ddp["Familia"] == familiaB]
productosA = sorted(df_famA["STD"].dropna().unique())
productosB = sorted(df_famB["STD"].dropna().unique())

colA, colB = st.columns(2)
with colA:
    prodA = st.selectbox("Selecciona Producto A", productosA, key="A")
with colB:
    prodB = st.selectbox("Selecciona Producto B", productosB, key="B")

df_A = df_ddp[df_ddp["STD"] == prodA]
df_B = df_ddp[df_ddp["STD"] == prodB]

if not df_A.empty and not df_B.empty:
    columnas_ddp = [col for col in df_A.columns if col not in ["STD", "Producto"]]
    resumen_ddp = comparar_productos(df_A, df_B, columnas_ddp)

    st.markdown("### 🔢 Diferencias en Condiciones Técnicas (DDP)")
    st.dataframe(resumen_ddp.astype(str).style.apply(resaltar_filas, axis=1))

    resumen_desbaste = []
    desbA = df_desbaste[df_desbaste["Familia"] == familiaA]
    desbB = df_desbaste[df_desbaste["Familia"] == familiaB]
    comunes = set(desbA["Componente limpio"]).intersection(set(desbB["Componente limpio"]))
    for comp in comunes:
        valA = desbA[desbA["Componente limpio"] == comp]["Valor"].values[0]
        valB = desbB[desbB["Componente limpio"] == comp]["Valor"].values[0]
        cambia = valA != valB and not (pd.isna(valA) and pd.isna(valB))
        resumen_desbaste.append({
            "Componente": comp,
            "Valor A": valA,
            "Valor B": valB,
            "¿Cambia?": "✅ Sí" if cambia else "❌ No"
        })
    df_desbaste_cmp = pd.DataFrame(resumen_desbaste)
    st.markdown("### 🧠 Comparación Diagrama Desbaste (por Familia)")
    st.dataframe(df_desbaste_cmp.astype(str).style.apply(resaltar_filas, axis=1))

    tiempo_exacto = df_tiempo[
        (df_tiempo["Producto Origen STD"] == prodA) &
        (df_tiempo["Producto Destino STD"] == prodB)
    ]["Minutos de Cambio"].values
    tiempo_str = f"{tiempo_exacto[0]}" if len(tiempo_exacto) > 0 else "Sin datos"
    st.success(f"Tiempo estimado de cambio: {tiempo_str} minutos")
