import streamlit as st
import pandas as pd
from io import BytesIO

# Configuración de página
st.set_page_config(page_title="Cambio de Producto", layout="wide")
st.title("🔧 Plataforma de Cambio de Producto – Laminador")

# Sidebar - Subida de archivos
st.sidebar.header("📁 Subida de Archivos")
file_ddp = st.sidebar.file_uploader("Cargar Consolidado Laminador (DDP)", type=["xlsx"])
file_tiempo = st.sidebar.file_uploader("Cargar Base Tiempo de Cambio", type=["xlsx"])
file_homologacion = st.sidebar.file_uploader("Cargar Mapa Homologación", type=["xlsx"])
file_programa = st.sidebar.file_uploader("Cargar Programa Producción", type=["xlsx"])

# Función para comparar productos
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

# Función para aplicar color a las filas que cambian
def resaltar_filas(row):
    color = 'background-color: #ffcccc' if row["¿Cambia?"] == "✅ Sí" else ''
    return [color] * len(row)

# Función para descargar Excel
def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Resumen')
    output.seek(0)
    return output

# Procesamiento si se suben archivos
if file_ddp and file_homologacion:
    df_ddp = pd.read_excel(file_ddp)
    df_mapa = pd.read_excel(file_homologacion)

    # Unir mapa de homologación
    df_ddp = df_ddp.merge(df_mapa, left_on="Nombre STD", right_on="Producto STD", how="left")

    st.subheader("🔍 Comparador de Productos")

    # Lista de productos únicos
    productos_std = sorted(df_ddp["Producto STD"].dropna().unique())

    # Selectboxes
    col1, col2 = st.columns(2)
    with col1:
        producto_origen = st.selectbox("Selecciona Producto Origen", productos_std, key="origen")
    with col2:
        producto_destino = st.selectbox("Selecciona Producto Destino", productos_std, key="destino")

    # Filtrar productos seleccionados
    datos_origen = df_ddp[df_ddp["Producto STD"] == producto_origen].drop(columns=["Producto Limpio"])
    datos_destino = df_ddp[df_ddp["Producto STD"] == producto_destino].drop(columns=["Producto Limpio"])

    if datos_origen.empty or datos_destino.empty:
        st.warning("No se encontraron datos técnicos para uno de los productos seleccionados.")
    else:
        st.markdown("### 🧮 Detalle Técnico")
        col3, col4 = st.columns(2)
        with col3:
            st.markdown(f"**Producto Origen: {producto_origen}**")
            st.dataframe(datos_origen.reset_index(drop=True))
        with col4:
            st.markdown(f"**Producto Destino: {producto_destino}**")
            st.dataframe(datos_destino.reset_index(drop=True))

        st.markdown("### 📋 Resumen de Diferencias Técnicas")

        columnas_tecnicas = [col for col in datos_origen.columns if col not in ["Producto STD", "Nombre STD"]]
        resumen_diferencias = comparar_productos(datos_origen, datos_destino, columnas_tecnicas)

        st.dataframe(resumen_diferencias.style.apply(resaltar_filas, axis=1))

        # Botón para exportar a Excel
        excel_export = generar_excel(resumen_diferencias)
        st.download_button(
            label="📥 Descargar resumen en Excel",
            data=excel_export,
            file_name=f"Diferencias_{producto_origen}_vs_{producto_destino}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# Mostrar tiempo histórico de cambio
if file_tiempo and file_homologacion:
    df_tiempo = pd.read_excel(file_tiempo)
    df_mapa = pd.read_excel(file_homologacion)

    # Homologar productos origen y destino
    df_tiempo = df_tiempo.merge(df_mapa[['Producto Limpio', 'Producto STD']], left_on="Producto Origen", right_on="Producto Limpio", how="left")
    df_tiempo.rename(columns={"Producto STD": "Origen STD"}, inplace=True)
    df_tiempo = df_tiempo.merge(df_mapa[['Producto Limpio', 'Producto STD']], left_on="Producto Destino", right_on="Producto Limpio", how="left")
    df_tiempo.rename(columns={"Producto STD": "Destino STD"}, inplace=True)

    # Filtrar combinación seleccionada
    filtro = (
        (df_tiempo["Origen STD"] == producto_origen) &
        (df_tiempo["Destino STD"] == producto_destino)
    )

    st.markdown("### ⏱️ Tiempo Histórico de Cambio")
    if df_tiempo[filtro].empty:
        st.info("No se encontraron datos de tiempo histórico para este cambio.")
    else:
        tiempo_prom = df_tiempo[filtro]["Minutos de Cambio"].mean()
        st.success(f"Tiempo promedio histórico entre estos productos: **{round(tiempo_prom, 1)} minutos**")
