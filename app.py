import streamlit as st
import pandas as pd
import io

# =====================================
# CONFIGURACIÓN INICIAL
# =====================================

st.set_page_config(page_title="Cambio de Producto", layout="wide")

# =====================================
# FUNCIONES DE CARGA DE DATOS
# =====================================

@st.cache_data
def cargar_datos():
    """Carga los archivos base de datos necesarios para la aplicación."""
    try:
        ddp = pd.read_excel("data/Consolidado_Laminador.xlsx")
        tiempo = pd.read_excel("data/BBDD_Tiempo.xlsx")
        desbaste = pd.read_excel("data/Diagrama_Desbaste.xlsx")
        return ddp, tiempo, desbaste
    except Exception as e:
        st.error(f"❌ Error al cargar archivos base: {e}")
        return None, None, None

def cargar_programa_usuario():
    """Maneja la carga del archivo de programa del usuario."""
    if "df_prog" not in st.session_state:
        archivo_programa = st.file_uploader(
            "📤 Sube el archivo de programa (xlsx)", 
            type=["xlsx"], 
            key="carga_global"
        )
        if archivo_programa is not None:
            try:
                df_prog = pd.read_excel(archivo_programa, sheet_name="TablaCombinada")
                st.session_state.df_prog = df_prog.dropna(subset=["Nombre STD"]).reset_index(drop=True)
                st.success("✅ Archivo cargado exitosamente")
            except Exception as e:
                st.error(f"❌ Error al cargar archivo: {e}")

# =====================================
# FUNCIONES DE COMPARACIÓN
# =====================================

def comparar_productos(df_a, df_b, columnas):
    """Compara dos productos y retorna las diferencias."""
    resumen = []
    posiciones = sorted(set(df_a["STD"]).union(df_b["STD"]))
    
    for pos in posiciones:
        fila_a = df_a[df_a["STD"] == pos]
        fila_b = df_b[df_b["STD"] == pos]
        
        for col in columnas:
            val_a = fila_a[col].values[0] if not fila_a.empty else None
            val_b = fila_b[col].values[0] if not fila_b.empty else None
            
            # Saltar valores vacíos o nulos
            if (val_a is None or pd.isna(val_a)) and (val_b is None or pd.isna(val_b)):
                continue
                
            cambia = val_a != val_b
            resumen.append({
                "Posicion": pos, 
                "Componente": col, 
                "Valor A": val_a, 
                "Valor B": val_b, 
                "¿Cambia?": "✅ Sí" if cambia else "❌ No"
            })
    
    return pd.DataFrame(resumen)

def comparar_desbaste(df_desbaste, familia_a, familia_b):
    """Compara diagrama de desbaste entre dos familias."""
    resumen_desbaste = []
    
    # Filtrar por familias
    desb_a = df_desbaste[df_desbaste["Familia"] == familia_a] if familia_a != "(Todos)" else df_desbaste
    desb_b = df_desbaste[df_desbaste["Familia"] == familia_b] if familia_b != "(Todos)" else df_desbaste
    
    # Obtener todos los pares únicos de SubSTD y Componente
    pares = sorted(
        set(zip(desb_a["SubSTD"], desb_a["Componente limpio"])) | 
        set(zip(desb_b["SubSTD"], desb_b["Componente limpio"])), 
        key=lambda x: int(x[0][1]) if x[0].startswith("D") and x[0][1:].isdigit() else 99
    )
    
    for substd, comp in pares:
        val1 = desb_a[(desb_a["SubSTD"] == substd) & (desb_a["Componente limpio"] == comp)]["Valor"].values
        val2 = desb_b[(desb_b["SubSTD"] == substd) & (desb_b["Componente limpio"] == comp)]["Valor"].values
        
        val1 = val1[0] if len(val1) > 0 else None
        val2 = val2[0] if len(val2) > 0 else None
        
        # Saltar valores vacíos
        if (val1 is None or pd.isna(val1)) and (val2 is None or pd.isna(val2)):
            continue
            
        cambia = val1 != val2
        resumen_desbaste.append({
            "Posición": substd,
            "Componente": comp,
            "Valor A": val1,
            "Valor B": val2,
            "¿Cambia?": "✅ Sí" if cambia else "❌ No"
        })
    
    return pd.DataFrame(resumen_desbaste)

def obtener_tiempo_cambio(df_tiempo, producto_origen, producto_destino):
    """Obtiene el tiempo de cambio entre dos productos."""
    tiempo_exacto = df_tiempo[
        (df_tiempo["Nombre STD Origen"] == producto_origen) & 
        (df_tiempo["Nombre STD Destino"] == producto_destino)
    ]["Minutos Cambio"].values
    
    return tiempo_exacto[0] if len(tiempo_exacto) > 0 else None

def agrupar_cambios_consecutivos(df):
    """Agrupa cambios consecutivos del mismo tipo."""
    columnas_clave = ["Producto Origen", "Producto Destino", "Familia"]
    df["Grupo"] = (df[columnas_clave] != df[columnas_clave].shift()).any(axis=1).cumsum()

    df_agrupado = df.groupby("Grupo").agg({
        "Secuencia": "first",
        "Familia": "first",
        "Producto Origen": "first",
        "Producto Destino": "first",
        "Tiempo estimado": "first",
        "Cambios Código Canal": "first"
    }).reset_index(drop=True)

    return df_agrupado

# =====================================
# FUNCIONES DE ESTILO
# =====================================

def resaltar_cambios(row):
    """Aplica estilo a las filas que tienen cambios."""
    base_color = "#ffacac" if st.get_option("theme.base") == "Light" else "#FF6E6E"
    return [f'background-color: {base_color}' if row["¿Cambia?"] == "✅ Sí" else '' for _ in row]

def mostrar_info_familia(producto, df_ddp, label):
    """Muestra información de la familia del producto cuando se selecciona 'Todos'."""
    if producto:
        familia_real = df_ddp[df_ddp["Producto"] == producto]["Familia"].dropna().unique()
        if len(familia_real) > 0:
            st.markdown(
                f"<span style='font-size: 14px;'>{label} pertenece a la familia: <b>{familia_real[0]}</b></span>", 
                unsafe_allow_html=True
            )

# =====================================
# INTERFAZ PRINCIPAL
# =====================================

def main():
    """Función principal de la aplicación."""
    
    # Cargar datos base
    df_ddp, df_tiempo, df_desbaste = cargar_datos()
    if df_ddp is None:
        st.stop()
    
    # Carga global del programa
    cargar_programa_usuario()
    
    # Crear pestañas
    tabs = st.tabs(["🆚 Comparador de Productos", "📋 Secuencia de Programa", "🏭 Maestranza"])
    
    # =====================================
    # PESTAÑA 1: COMPARADOR MANUAL
    # =====================================
    
    with tabs[0]:
        st.title("🔧 Plataforma de Cambio de Producto – Laminador")
        st.subheader("🔄 Comparador Manual de Productos")
        
        # Selección de familias
        familias = ["(Todos)"] + sorted(df_ddp["Familia"].dropna().unique())
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            familia_a = st.selectbox("Selecciona Familia A", familias, key="famA")
        with col_f2:
            familia_b = st.selectbox("Selecciona Familia B", familias, key="famB")
        
        # Filtrar productos por familia
        df_fam_a = df_ddp if familia_a == "(Todos)" else df_ddp[df_ddp["Familia"] == familia_a]
        df_fam_b = df_ddp if familia_b == "(Todos)" else df_ddp[df_ddp["Familia"] == familia_b]
        
        productos_a = sorted(df_fam_a["Producto"].dropna().unique())
        productos_b = sorted(df_fam_b["Producto"].dropna().unique())
        
        # Selección de productos
        col_a, col_b = st.columns(2)
        
        with col_a:
            producto_a = st.selectbox("Selecciona Producto A", productos_a, key="A", index=0)
            if familia_a == "(Todos)":
                mostrar_info_familia(producto_a, df_ddp, "Producto A")
        
        with col_b:
            producto_b = st.selectbox("Selecciona Producto B", productos_b, key="B", index=0)
            if familia_b == "(Todos)":
                mostrar_info_familia(producto_b, df_ddp, "Producto B")
        
        # Análisis de productos seleccionados
        if producto_a and producto_b:
            mostrar_comparacion_productos(
                df_ddp, df_tiempo, df_desbaste, 
                producto_a, producto_b, familia_a, familia_b
            )
    
    # =====================================
    # PESTAÑA 2: SECUENCIA DE PROGRAMA
    # =====================================
    
    with tabs[1]:
        st.title("📋 Secuencia de Programa")
        
        if "df_prog" in st.session_state:
            mostrar_secuencia_programa(df_ddp, df_tiempo)
        else:
            st.warning("Por favor carga primero el archivo de programa en la parte superior.")
    
    # =====================================
    # PESTAÑA 3: MAESTRANZA
    # =====================================
    
    with tabs[2]:
        st.title("🏭 Resumen Técnico para Maestranza")
        
        if "df_prog" in st.session_state:
            mostrar_resumen_maestranza(df_ddp)
        else:
            st.warning("Por favor carga primero el archivo de programa en la parte superior.")

def mostrar_comparacion_productos(df_ddp, df_tiempo, df_desbaste, producto_a, producto_b, familia_a, familia_b):
    """Muestra la comparación detallada entre dos productos."""
    
    df_a = df_ddp[df_ddp["Producto"] == producto_a]
    df_b = df_ddp[df_ddp["Producto"] == producto_b]
    
    if df_a.empty or df_b.empty:
        st.warning("No se encontraron datos para uno o ambos productos.")
        return
    
    # Mostrar tiempo de cambio
    tiempo = obtener_tiempo_cambio(df_tiempo, producto_a, producto_b)
    if tiempo:
        st.success(f"⏱️ Tiempo estimado de cambio: {tiempo} minutos")
    else:
        st.warning("No se encontró tiempo de cambio registrado entre estos productos.")
    
    # Comparación técnica (DDP)
    columnas_ddp = [col for col in df_a.columns if col not in ["STD", "Producto", "Familia"]]
    resumen_ddp = comparar_productos(df_a, df_b, columnas_ddp)
    
    st.markdown("### 🔢 Diferencias Técnicas por cambio producto")
    mostrar_solo_cambios_ddp = st.checkbox("Mostrar solo componentes que cambian (DDP)", value=False)
    
    if mostrar_solo_cambios_ddp:
        resumen_ddp = resumen_ddp[resumen_ddp["¿Cambia?"] == "✅ Sí"]
    
    st.dataframe(resumen_ddp.style.apply(resaltar_cambios, axis=1))
    
    # Comparación desbaste
    df_desbaste_cmp = comparar_desbaste(df_desbaste, familia_a, familia_b)
    
    st.markdown("### 🧠 Diagrama Desbaste")
    mostrar_solo_cambios_desbaste = st.checkbox("Mostrar solo componentes que cambian (Desbaste)", value=False)
    
    if mostrar_solo_cambios_desbaste:
        df_desbaste_cmp = df_desbaste_cmp[df_desbaste_cmp["¿Cambia?"] == "✅ Sí"]
    
    st.dataframe(df_desbaste_cmp.astype(str).style.apply(resaltar_cambios, axis=1))
    
    # Resumen de cambios
    st.markdown("### 📊 Resumen de cambios")
    resumen_contador = resumen_ddp[resumen_ddp["¿Cambia?"] == "✅ Sí"]
    conteo_por_componente = resumen_contador["Componente"].value_counts().reset_index()
    conteo_por_componente.columns = ["Componente", "Cantidad de Cambios"]
    st.dataframe(conteo_por_componente)

def mostrar_secuencia_programa(df_ddp, df_tiempo):
    """Muestra el análisis de la secuencia del programa."""
    
    df_prog = st.session_state.df_prog
    resumen = []
    
    # Analizar cada cambio en la secuencia
    for i in range(len(df_prog) - 1):
        origen = df_prog.loc[i, "Nombre STD"]
        destino = df_prog.loc[i + 1, "Nombre STD"]
        
        # Obtener tiempo de cambio
        tiempo = obtener_tiempo_cambio(df_tiempo, origen, destino)
        
        # Calcular cambios en código canal
        df_a = df_ddp[df_ddp["Producto"] == origen]
        df_b = df_ddp[df_ddp["Producto"] == destino]
        
        cambios_codigo_canal = 0
        if not df_a.empty and not df_b.empty:
            merged = df_a.merge(df_b, on="STD", suffixes=("_A", "_B"))
            if "Código Canal_A" in merged.columns and "Código Canal_B" in merged.columns:
                cambios_codigo_canal = merged.apply(
                    lambda row: row["Código Canal_A"] != row["Código Canal_B"], axis=1
                ).sum()
        
        # Obtener familias
        familia_origen = df_a['Familia'].values[0] if not df_a.empty else "N/A"
        familia_destino = df_b['Familia'].values[0] if not df_b.empty else "N/A"
        
        resumen.append({
            "Secuencia": i + 1,
            "Familia": f"{familia_origen}-{familia_destino}",
            "Producto Origen": origen,
            "Producto Destino": destino,
            "Tiempo estimado": tiempo,
            "Cambios Código Canal": cambios_codigo_canal
        })
    
    # Agrupar cambios consecutivos
    df_resumen = agrupar_cambios_consecutivos(pd.DataFrame(resumen))
    
    # Mostrar cambios
    st.markdown("### Cambios en secuencia")
    for idx, fila in df_resumen.iterrows():
        tiempo_mostrar = "-" if pd.isna(fila['Tiempo estimado']) else f"{int(fila['Tiempo estimado'])} min"
        titulo = f"🔹 #{fila['Secuencia']} | {fila['Producto Origen']} → {fila['Producto Destino']} | ⏱️ {tiempo_mostrar} | 🔧 {fila['Cambios Código Canal']} cambios canal"
        
        with st.expander(titulo):
            df_a_cmp = df_ddp[df_ddp["Producto"] == fila['Producto Origen']]
            df_b_cmp = df_ddp[df_ddp["Producto"] == fila['Producto Destino']]
            
            if not df_a_cmp.empty and not df_b_cmp.empty:
                columnas_cmp = [col for col in df_a_cmp.columns if col not in ["STD", "Producto", "Familia"]]
                resumen_cmp = comparar_productos(df_a_cmp, df_b_cmp, columnas_cmp)
                resumen_cmp = resumen_cmp[resumen_cmp["¿Cambia?"] == "✅ Sí"]
                st.dataframe(resumen_cmp)

def mostrar_resumen_maestranza(df_ddp):
    """Muestra el resumen técnico para maestranza."""

    df_prog = st.session_state.df_prog.copy()

    # Detectar bloques consecutivos del mismo producto
    df_prog["Grupo"] = (df_prog["Nombre STD"] != df_prog["Nombre STD"].shift()).cumsum()

    # Sumar toneladas programadas por bloque consecutivo
    df_programa = (
        df_prog
        .groupby(["Grupo", "Nombre STD"], as_index=False)
        .agg({"PROGR": "sum"})
        .rename(columns={"PROGR": "Toneladas Programadas"})
    )
    df_programa["Toneladas Programadas"] = df_programa["Toneladas Programadas"].astype(int)

    # Obtener códigos de canal por producto
    codigos_por_producto = (
        df_ddp.groupby("Producto")["Código Canal"]
        .unique()
        .apply(lambda x: ", ".join(sorted([str(c) for c in x if pd.notna(c)])))
        .reset_index()
        .rename(columns={"Producto": "Nombre STD", "Código Canal": "Códigos Canal"})
    )

    # Unir programa con información técnica
    df_resumen = df_programa.merge(codigos_por_producto, on="Nombre STD", how="left")
    df_resumen = df_resumen[["Nombre STD", "Toneladas Programadas", "Códigos Canal"]]

    st.dataframe(df_resumen, use_container_width=True)

    # Tabla adicional: Frecuencia real de cada código de canal según el programa
    st.markdown("### 🔁 Frecuencia de Códigos de Canal en el Programa")
    df_resumen["Códigos Canal Lista"] = df_resumen["Códigos Canal"].apply(
        lambda x: x.split(", ") if isinstance(x, str) else []
    )
    codigos_expandidos = df_resumen.explode("Códigos Canal Lista")
    frecuencia_en_programa = (
        codigos_expandidos["Códigos Canal Lista"]
        .value_counts()
        .reset_index()
        .rename(columns={"index": "Código Canal", "Códigos Canal Lista": "Frecuencia en Programa"})
    )
    st.dataframe(frecuencia_en_programa, use_container_width=True)

    # Botón de descarga (solo de la tabla principal)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_resumen.to_excel(writer, index=False, sheet_name="Resumen Maestranza")
    buffer.seek(0)

    st.download_button(
        label="📥 Descargar Excel",
        data=buffer,
        file_name="Resumen_Maestranza.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =====================================
# EJECUCIÓN PRINCIPAL
# =====================================

if __name__ == "__main__":
    main()