import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Cambio de Producto", layout="wide")
st.title("🔧 Plataforma de Cambio de Producto – Laminador")

@st.cache_data
def cargar_datos_estaticos():
    ddp = pd.read_excel("data/Consolidado_Laminador.xlsx")
    tiempo = pd.read_excel("data/BBDD_Tiempo.xlsx")
    desbaste = pd.read_excel("data/Diagrama_Desbaste.xlsx")

    for col in ["Producto Origen STD", "Producto Destino STD"]:
        tiempo[col] = tiempo[col].astype(str).str.strip().str.upper()
    ddp["Producto"] = ddp["Producto"].astype(str).str.strip().str.upper()

    return ddp, tiempo, desbaste

df_ddp, df_tiempo, df_desbaste = cargar_datos_estaticos()

st.sidebar.header(":page_facing_up: Subida de Programa")
file_programa = st.sidebar.file_uploader("Subir archivo Programa.xlsx", type=["xlsx"])

def comparar_productos_por_posicion(dfA, dfB, columnas):
    resumen = []
    posiciones = sorted(set(dfA["STD"]).union(set(dfB["STD"])), key=lambda x: (
        0 if x == "DU" else
        int(x[1]) if x.startswith("M") else
        10 + int(x[1]) if x.startswith("A") else
        99
    ))
    for pos in posiciones:
        filaA = dfA[dfA["STD"] == pos]
        filaB = dfB[dfB["STD"] == pos]
        for col in columnas:
            valA = filaA[col].values[0] if not filaA.empty and col in filaA else None
            valB = filaB[col].values[0] if not filaB.empty and col in filaB else None
            valA = None if pd.isna(valA) or valA == "None" else valA
            valB = None if pd.isna(valB) or valB == "None" else valB
            if valA is None and valB is None:
                cambia = False
            else:
                cambia = valA != valB
            resumen.append({
                "Posición": pos,
                "Componente": col,
                "Valor A": valA,
                "Valor B": valB,
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

productosA = sorted(df_famA["Producto"].dropna().unique())
productosB = sorted(df_famB["Producto"].dropna().unique())

colA, colB = st.columns(2)
with colA:
    productoA = st.selectbox("Selecciona Producto A", productosA, key="A")
with colB:
    productoB = st.selectbox("Selecciona Producto B", productosB, key="B")

# Obtener STD desde nombre del producto seleccionado
df_A = df_famA[df_famA["Producto"] == productoA]
df_B = df_famB[df_famB["Producto"] == productoB]

if not df_A.empty and not df_B.empty:
    columnas_ddp = [col for col in df_A.columns if col not in ["STD", "Producto", "Familia"]]
    resumen_ddp = comparar_productos_por_posicion(df_A, df_B, columnas_ddp)

    st.markdown("### 🔢 Diferencias Técnicas por Posición del Laminador (DDP)")
    st.dataframe(resumen_ddp.astype(str).style.apply(resaltar_filas, axis=1))

    resumen_desbaste = []
    desbA = df_desbaste[df_desbaste["Familia"] == familiaA]
    desbB = df_desbaste[df_desbaste["Familia"] == familiaB]
    pares = sorted(set(zip(desbA["SubSTD"], desbA["Componente limpio"])) | set(zip(desbB["SubSTD"], desbB["Componente limpio"])), key=lambda x: int(x[0][1]) if x[0].startswith("D") and x[0][1:].isdigit() else 99)
    for substd, comp in pares:
        val1 = desbA[(desbA["SubSTD"] == substd) & (desbA["Componente limpio"] == comp)]["Valor"].values
        val2 = desbB[(desbB["SubSTD"] == substd) & (desbB["Componente limpio"] == comp)]["Valor"].values
        val1 = val1[0] if len(val1) > 0 else None
        val2 = val2[0] if len(val2) > 0 else None
        cambia = val1 != val2 and not (pd.isna(val1) and pd.isna(val2))
        resumen_desbaste.append({
            "Posición": substd,
            "Componente": comp,
            "Valor A": val1,
            "Valor B": val2,
            "¿Cambia?": "✅ Sí" if cambia else "❌ No"
        })
    df_desbaste_cmp = pd.DataFrame(resumen_desbaste)
    st.markdown("### 🧠 Comparación Diagrama Desbaste (todas las posiciones)")
    st.dataframe(df_desbaste_cmp.astype(str).style.apply(resaltar_filas, axis=1))