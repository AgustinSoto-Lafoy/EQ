import streamlit as st
import pandas as pd
from io import BytesIO

# Configuración de página
st.set_page_config(page_title="Cambio de Producto", layout="wide")
st.title("🔧 Plataforma de Cambio de Producto – Laminador")

# Cargar archivos estáticos desde /data
@st.cache_data
def cargar_datos_estaticos():
    ddp = pd.read_excel("data/Consolidado_Laminador.xlsx")
    mapa = pd.read_excel("data/Mapa_Homologacion_Producto.xlsx")
    tiempo = pd.read_excel("data/BBDD_Tiempo.xlsx")
    desbaste = pd.read_excel("data/Diagrama_Desbaste.xlsx")
    return ddp, mapa, tiempo, desbaste

df_ddp, df_mapa, df_tiempo, df_desbaste = cargar_datos_estaticos()

# Sidebar: Cargar archivo de Programa
st.sidebar.header(":page_facing_up: Subida de Programa")
file_programa = st.sidebar.file_uploader("Subir archivo Programa.xlsx", type=["xlsx"])

# Funciones auxiliares
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

def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Resumen')
    output.seek(0)
    return output

# Comparador manual de productos
st.subheader("🔄 Comparador Manual de Productos")
productos_disponibles = sorted(df_mapa["Producto STD"].dropna().unique())
colA, colB = st.columns(2)
with colA:
    prodA = st.selectbox("Selecciona Producto A", productos_disponibles, key="A")
with colB:
    prodB = st.selectbox("Selecciona Producto B", productos_disponibles, key="B")

# Mostrar diferencia en condiciones DDP
df_A = df_ddp[df_ddp["STD"] == prodA]
df_B = df_ddp[df_ddp["STD"] == prodB]

if not df_A.empty and not df_B.empty:
    columnas_ddp = [col for col in df_A.columns if col not in ["STD", "Producto"]]
    resumen_ddp = comparar_productos(df_A, df_B, columnas_ddp)

    st.markdown("### 🔢 Diferencias en Condiciones Técnicas (DDP)")
    st.dataframe(resumen_ddp.astype(str).style.apply(resaltar_filas, axis=1))

    st.download_button(
        "📄 Descargar Comparación DDP",
        data=generar_excel(resumen_ddp),
        file_name=f"Comparacion_DDP_{prodA}_vs_{prodB}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    if st.toggle("🔍 Ver detalles Desbaste"):
        st.markdown("### 🧠 Comparación Diagrama Desbaste")
        desbA = df_desbaste[df_desbaste["STD"] == prodA]
        desbB = df_desbaste[df_desbaste["STD"] == prodB]
        comunes = set(desbA["Componente limpio"]).intersection(set(desbB["Componente limpio"]))

        comparaciones = []
        for comp in comunes:
            valA = desbA[desbA["Componente limpio"] == comp]["Valor"].values[0]
            valB = desbB[desbB["Componente limpio"] == comp]["Valor"].values[0]
            cambia = valA != valB and not (pd.isna(valA) and pd.isna(valB))
            comparaciones.append({
                "Componente": comp,
                "Valor A": valA,
                "Valor B": valB,
                "¿Cambia?": "✅ Sí" if cambia else "❌ No"
            })

        df_desbaste_cmp = pd.DataFrame(comparaciones)
        st.dataframe(df_desbaste_cmp.astype(str).style.apply(resaltar_filas, axis=1))

        st.download_button(
            "📄 Descargar Comparación Desbaste",
            data=generar_excel(df_desbaste_cmp),
            file_name=f"Comparacion_Desbaste_{prodA}_vs_{prodB}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# Sección: Análisis de Secuencia de Cambios
def analizar_secuencia(programa, mapa, ddp, tiempo):
    st.subheader("🔀 Análisis de Secuencia de Cambios")

    programa = programa.merge(mapa, left_on="DESCRIPCIÓN", right_on="Producto Limpio", how="left")
    programa = programa.sort_values(by="INICIO")
    programa["Producto STD"] = programa["Producto STD"].fillna("Sin homologar")

    cambios = []
    for i in range(len(programa) - 1):
        origen = programa.iloc[i]["Producto STD"]
        destino = programa.iloc[i+1]["Producto STD"]
        if origen == destino or "Sin homologar" in [origen, destino]:
            continue

        match = tiempo[(tiempo["Producto Origen STD"] == origen) & (tiempo["Producto Destino STD"] == destino)]
        minutos = match["Minutos de Cambio"].mean() if not match.empty else "Sin datos"

        df_origen = ddp[ddp["STD"] == origen]
        df_destino = ddp[ddp["STD"] == destino]
        cambios_tecnicos = 0
        if not df_origen.empty and not df_destino.empty:
            columnas_tecnicas = [col for col in df_origen.columns if col not in ["STD", "Producto"]]
            diferencias = comparar_productos(df_origen, df_destino, columnas_tecnicas)
            cambios_tecnicos = diferencias[diferencias["¿Cambia?"] == "✅ Sí"].shape[0]

        cambios.append({
            "Producto Origen": origen,
            "Producto Destino": destino,
            "Minutos Prom. Cambio": minutos,
            "Variables que Cambian": cambios_tecnicos
        })

    df_cambios = pd.DataFrame(cambios)
    st.dataframe(df_cambios.astype(str))

    if not df_cambios.empty:
        st.download_button(
            "📄 Descargar resumen de secuencia",
            data=generar_excel(df_cambios),
            file_name="Resumen_Cambios_Secuencia.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# Ejecutar si hay archivo cargado
if file_programa:
    df_programa = pd.read_excel(file_programa)
    analizar_secuencia(df_programa, df_mapa, df_ddp, df_tiempo)
else:
    st.info("Por favor, sube el archivo Programa.xlsx para iniciar el análisis.")
