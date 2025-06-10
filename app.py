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
    return ddp, mapa, tiempo

df_ddp, df_mapa, df_tiempo = cargar_datos_estaticos()

# Sidebar: Cargar archivo de Programa
st.sidebar.header(":page_facing_up: Subida de Programa")
file_programa = st.sidebar.file_uploader("Subir archivo Programa.xlsx", type=["xlsx"])

# Funciones auxiliares
def comparar_productos(df_origen, df_destino, columnas):
    resumen = []
    for col in columnas:
        val1 = df_origen.iloc[0].get(col, "")
        val2 = df_destino.iloc[0].get(col, "")
        distinto = val1 != val2
        resumen.append({
            "Variable Técnica": col,
            "Producto Origen": val1,
            "Producto Destino": val2,
            "¿Cambia?": "✅ Sí" if distinto else "❌ No"
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

# Sección: Análisis de Secuencia de Cambios
def analizar_secuencia(programa, mapa, ddp, tiempo):
    st.subheader("🔀 Análisis de Secuencia de Cambios")

    # Homologar productos
    programa = programa.merge(mapa, left_on="DESCRIPCIÓN", right_on="Producto Limpio", how="left")
    programa = programa.sort_values(by="INICIO")
    programa["Producto STD"] = programa["Producto STD"].fillna("Sin homologar")

    cambios = []
    for i in range(len(programa) - 1):
        origen = programa.iloc[i]["Producto STD"]
        destino = programa.iloc[i+1]["Producto STD"]
        if origen == destino or "Sin homologar" in [origen, destino]:
            continue

        # Buscar tiempo de cambio
        match = tiempo[(tiempo["Producto Origen STD"] == origen) & (tiempo["Producto Destino STD"] == destino)]
        minutos = match["Minutos de Cambio"].mean() if not match.empty else "Sin datos"

        # Comparar condiciones
        df_origen = ddp[ddp["Nombre STD"] == origen]
        df_destino = ddp[ddp["Nombre STD"] == destino]
        cambios_tecnicos = 0
        if not df_origen.empty and not df_destino.empty:
            columnas_tecnicas = [col for col in df_origen.columns if col not in ["Producto STD", "Nombre STD"]]
            diferencias = comparar_productos(df_origen, df_destino, columnas_tecnicas)
            cambios_tecnicos = diferencias[diferencias["¿Cambia?"] == "✅ Sí"].shape[0]

        cambios.append({
            "Producto Origen": origen,
            "Producto Destino": destino,
            "Minutos Prom. Cambio": minutos,
            "Variables que Cambian": cambios_tecnicos
        })

    df_cambios = pd.DataFrame(cambios)
    st.dataframe(df_cambios)

    # Exportar a Excel
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
