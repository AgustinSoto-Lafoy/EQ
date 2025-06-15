import streamlit as st
import pandas as pd
import io
import numpy as np
from datetime import datetime
import logging

# =====================================
# CONFIGURACIÓN INICIAL
# =====================================

st.set_page_config(
    page_title="Cambio de Producto - Laminador", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =====================================
# FUNCIONES DE CARGA DE DATOS
# =====================================

@st.cache_data(ttl=3600)  # Cache por 1 hora
def cargar_datos():
    """Carga los archivos base de datos necesarios para la aplicación."""
    archivos = {
        "ddp": "data/Consolidado_Laminador.xlsx",
        "tiempo": "data/BBDD_Tiempo.xlsx", 
        "desbaste": "data/Diagrama_Desbaste.xlsx"
    }
    
    datos = {}
    errores = []
    
    for key, archivo in archivos.items():
        try:
            # Optimizar lectura con tipos específicos si es posible
            df = pd.read_excel(archivo)
            # Optimizar tipos de datos
            df = optimizar_tipos_datos(df)
            datos[key] = df
            logger.info(f"Archivo {archivo} cargado exitosamente")
        except Exception as e:
            errores.append(f"Error cargando {archivo}: {str(e)}")
            logger.error(f"Error cargando {archivo}: {str(e)}")
    
    if errores:
        st.error("❌ Errores al cargar archivos base:\n" + "\n".join(errores))
        return None, None, None
    
    return datos.get("ddp"), datos.get("tiempo"), datos.get("desbaste")

def optimizar_tipos_datos(df):
    """Optimiza los tipos de datos del DataFrame para mejor rendimiento."""
    for col in df.columns:
        if df[col].dtype == 'object':
            # Convertir strings a category si tienen pocos valores únicos
            if df[col].nunique() / len(df) < 0.5:
                df[col] = df[col].astype('category')
        elif df[col].dtype in ['int64', 'float64']:
            # Downcast a tipos más pequeños
            if df[col].dtype == 'int64':
                df[col] = pd.to_numeric(df[col], downcast='integer')
            else:
                df[col] = pd.to_numeric(df[col], downcast='float')
    
    return df

def cargar_programa_usuario():
    """Maneja la carga del archivo de programa del usuario."""
    if "df_prog" not in st.session_state:
        with st.container():
            st.markdown("### 📤 Cargar Programa")
            archivo_programa = st.file_uploader(
                "Sube el archivo de programa (xlsx)", 
                type=["xlsx"], 
                key="carga_global",
                help="Archivo debe contener la hoja 'TablaCombinada' con columna 'Nombre STD'"
            )
            
            if archivo_programa is not None:
                with st.spinner("Cargando archivo..."):
                    try:
                        df_prog = pd.read_excel(archivo_programa, sheet_name="TablaCombinada")
                        
                        # Validaciones
                        if "Nombre STD" not in df_prog.columns:
                            st.error("❌ El archivo debe contener la columna 'Nombre STD'")
                            return
                        
                        df_prog_clean = df_prog.dropna(subset=["Nombre STD"]).reset_index(drop=True)
                        
                        if df_prog_clean.empty:
                            st.error("❌ No se encontraron datos válidos en el archivo")
                            return
                        
                        # Optimizar tipos de datos
                        df_prog_clean = optimizar_tipos_datos(df_prog_clean)
                        
                        st.session_state.df_prog = df_prog_clean
                        st.success(f"✅ Archivo cargado exitosamente ({len(df_prog_clean)} registros)")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error al cargar archivo: {e}")
                        logger.error(f"Error cargando programa: {str(e)}")

# =====================================
# FUNCIONES DE COMPARACIÓN OPTIMIZADAS
# =====================================

@st.cache_data
def comparar_productos(df_a, df_b, columnas):
    """Compara dos productos y retorna las diferencias - OPTIMIZADA."""
    if df_a.empty or df_b.empty:
        return pd.DataFrame()
    
    # Usar merge para comparación más eficiente
    df_a_clean = df_a[["STD"] + columnas].copy()
    df_b_clean = df_b[["STD"] + columnas].copy()
    
    # Merge en lugar de loops
    merged = df_a_clean.merge(df_b_clean, on="STD", how="outer", suffixes=("_A", "_B"))
    
    resumen = []
    for _, row in merged.iterrows():
        for col in columnas:
            val_a = row.get(f"{col}_A")
            val_b = row.get(f"{col}_B")
            
            # Saltar valores vacíos o nulos
            if pd.isna(val_a) and pd.isna(val_b):
                continue
            
            # Comparación más robusta
            cambia = not pd.isna(val_a) and not pd.isna(val_b) and val_a != val_b
            cambia = cambia or (pd.isna(val_a) != pd.isna(val_b))
            
            resumen.append({
                "Posicion": row["STD"],
                "Componente": col,
                "Valor A": val_a if not pd.isna(val_a) else "-",
                "Valor B": val_b if not pd.isna(val_b) else "-",
                "¿Cambia?": "✅ Sí" if cambia else "❌ No"
            })
    
    return pd.DataFrame(resumen)

@st.cache_data
def comparar_desbaste(df_desbaste, familia_a, familia_b):
    """Compara diagrama de desbaste entre dos familias - OPTIMIZADA."""
    # Filtrar por familias de forma más eficiente
    mask_a = df_desbaste["Familia"] == familia_a if familia_a != "(Todos)" else True
    mask_b = df_desbaste["Familia"] == familia_b if familia_b != "(Todos)" else True
    
    desb_a = df_desbaste[mask_a] if isinstance(mask_a, pd.Series) else df_desbaste
    desb_b = df_desbaste[mask_b] if isinstance(mask_b, pd.Series) else df_desbaste
    
    # Crear pivot para comparación más eficiente
    pivot_a = desb_a.pivot_table(
        index=["SubSTD", "Componente limpio"], 
        values="Valor", 
        aggfunc='first'
    )
    pivot_b = desb_b.pivot_table(
        index=["SubSTD", "Componente limpio"], 
        values="Valor", 
        aggfunc='first'
    )
    
    # Combinar y comparar
    combined = pd.concat([pivot_a, pivot_b], axis=1, keys=['A', 'B'])
    combined = combined.fillna("-")
    
    resumen_desbaste = []
    for (substd, comp), row in combined.iterrows():
        val_a = row.get(('A', 'Valor'), "-")
        val_b = row.get(('B', 'Valor'), "-")
        
        if val_a == "-" and val_b == "-":
            continue
            
        cambia = val_a != val_b
        resumen_desbaste.append({
            "Posición": substd,
            "Componente": comp,
            "Valor A": val_a,
            "Valor B": val_b,
            "¿Cambia?": "✅ Sí" if cambia else "❌ No"
        })
    
    # Ordenar por posición
    df_result = pd.DataFrame(resumen_desbaste)
    if not df_result.empty:
        df_result['sort_key'] = df_result['Posición'].apply(
            lambda x: int(x[1:]) if isinstance(x, str) and x.startswith("D") and x[1:].isdigit() else 999
        )
        df_result = df_result.sort_values('sort_key').drop('sort_key', axis=1)
    
    return df_result

@st.cache_data
def obtener_tiempo_cambio(df_tiempo, producto_origen, producto_destino):
    """Obtiene el tiempo de cambio entre dos productos - OPTIMIZADA."""
    mask = (df_tiempo["Nombre STD Origen"] == producto_origen) & \
           (df_tiempo["Nombre STD Destino"] == producto_destino)
    
    resultado = df_tiempo.loc[mask, "Minutos Cambio"]
    return resultado.iloc[0] if not resultado.empty else None

def agrupar_cambios_consecutivos(df):
    """Agrupa cambios consecutivos del mismo tipo - OPTIMIZADA."""
    if df.empty:
        return df
    
    columnas_clave = ["Producto Origen", "Producto Destino", "Familia"]
    
    # Crear grupos de forma más eficiente
    cambios = df[columnas_clave].ne(df[columnas_clave].shift()).any(axis=1)
    df = df.copy()
    df["Grupo"] = cambios.cumsum()

    # Agrupar manteniendo las columnas necesarias
    df_agrupado = df.groupby("Grupo", as_index=False).agg({
        "Secuencia": "first",
        "Familia": "first", 
        "Producto Origen": "first",
        "Producto Destino": "first",
        "Tiempo estimado": "first",
        "Cambios Código Canal": "first"
    })

    return df_agrupado.drop("Grupo", axis=1)

# =====================================
# FUNCIONES DE ESTILO Y UI
# =====================================

def resaltar_cambios(row):
    """Aplica estilo a las filas que tienen cambios."""
    color_cambio = "#ffebee"  # Color más suave
    color_sin_cambio = "#f1f8e9"  # Verde muy claro para no cambios
    
    if row["¿Cambia?"] == "✅ Sí":
        return [f'background-color: {color_cambio}; font-weight: bold'] * len(row)
    else:
        return [f'background-color: {color_sin_cambio}'] * len(row)

def mostrar_info_familia(producto, df_ddp, label):
    """Muestra información de la familia del producto."""
    if producto:
        familia = df_ddp[df_ddp["Producto"] == producto]["Familia"].dropna().unique()
        if len(familia) > 0:
            st.info(f"ℹ️ {label} pertenece a la familia: **{familia[0]}**")

def mostrar_metricas_resumen(df_cambios):
    """Muestra métricas de resumen de cambios."""
    if not df_cambios.empty:
        total_cambios = len(df_cambios[df_cambios["¿Cambia?"] == "✅ Sí"])
        total_componentes = len(df_cambios)
        porcentaje = (total_cambios / total_componentes * 100) if total_componentes > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Cambios", total_cambios)
        with col2:
            st.metric("Total Componentes", total_componentes)
        with col3:
            st.metric("% Cambios", f"{porcentaje:.1f}%")

# =====================================
# INTERFAZ PRINCIPAL
# =====================================

def main():
    """Función principal de la aplicación."""
    
    # Header con información
    st.markdown("""
    # 🔧 Plataforma de Cambio de Producto – Laminador
    *Sistema de análisis y comparación de productos para optimización de cambios*
    """)
    
    # Cargar datos base con indicador de progreso
    with st.spinner("Cargando datos base..."):
        df_ddp, df_tiempo, df_desbaste = cargar_datos()
    
    if df_ddp is None:
        st.error("No se pudieron cargar los datos base. Verifica que los archivos existan.")
        st.stop()
    
    # Mostrar información de los datos cargados
    with st.expander("ℹ️ Información de datos cargados"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Productos DDP", len(df_ddp))
        with col2:
            st.metric("Tiempos de Cambio", len(df_tiempo))
        with col3:
            st.metric("Registros Desbaste", len(df_desbaste))
    
    # Carga global del programa
    cargar_programa_usuario()
    
    # Crear pestañas con iconos más descriptivos
    tabs = st.tabs([
        "🔍 Comparador Manual", 
        "📋 Análisis de Secuencia", 
        "🏭 Resumen Maestranza"
    ])
    
    # =====================================
    # PESTAÑA 1: COMPARADOR MANUAL
    # =====================================
    
    with tabs[0]:
        st.subheader("🔄 Comparación Manual de Productos")
        
        # Interfaz mejorada para selección
        with st.container():
            # Selección de familias con filtros
            familias = ["(Todos)"] + sorted(df_ddp["Familia"].dropna().unique())
            
            col_f1, col_f2, col_config = st.columns([1, 1, 1])
            
            with col_f1:
                familia_a = st.selectbox("🏷️ Familia A", familias, key="famA")
            with col_f2:
                familia_b = st.selectbox("🏷️ Familia B", familias, key="famB")
            with col_config:
                st.markdown("**Opciones de visualización:**")
                solo_cambios_global = st.checkbox("Solo mostrar cambios", value=True)
        
        # Filtrar productos por familia
        df_fam_a = df_ddp if familia_a == "(Todos)" else df_ddp[df_ddp["Familia"] == familia_a]
        df_fam_b = df_ddp if familia_b == "(Todos)" else df_ddp[df_ddp["Familia"] == familia_b]
        
        productos_a = sorted(df_fam_a["Producto"].dropna().unique())
        productos_b = sorted(df_fam_b["Producto"].dropna().unique())
        
        # Selección de productos con búsqueda
        col_a, col_b = st.columns(2)
        
        with col_a:
            producto_a = st.selectbox("🔧 Producto A", productos_a, key="A")
            if familia_a == "(Todos)":
                mostrar_info_familia(producto_a, df_ddp, "Producto A")
        
        with col_b:
            producto_b = st.selectbox("🔧 Producto B", productos_b, key="B")
            if familia_b == "(Todos)":
                mostrar_info_familia(producto_b, df_ddp, "Producto B")
        
        # Análisis de productos seleccionados
        if producto_a and producto_b:
            if producto_a == producto_b:
                st.warning("⚠️ Has seleccionado el mismo producto en ambos lados.")
            else:
                mostrar_comparacion_productos(
                    df_ddp, df_tiempo, df_desbaste, 
                    producto_a, producto_b, familia_a, familia_b,
                    solo_cambios_global
                )
    
    # =====================================
    # PESTAÑA 2: SECUENCIA DE PROGRAMA
    # =====================================
    
    with tabs[1]:
        st.subheader("📊 Análisis de Secuencia de Programa")
        
        if "df_prog" in st.session_state:
            mostrar_secuencia_programa(df_ddp, df_tiempo)
        else:
            st.info("📤 Por favor carga primero el archivo de programa.")
    
    # =====================================
    # PESTAÑA 3: MAESTRANZA
    # =====================================
    
    with tabs[2]:
        st.subheader("📈 Resumen Técnico para Maestranza")
        
        if "df_prog" in st.session_state:
            mostrar_resumen_maestranza(df_ddp)
        else:
            st.info("📤 Por favor carga primero el archivo de programa.")

def mostrar_comparacion_productos(df_ddp, df_tiempo, df_desbaste, producto_a, producto_b, familia_a, familia_b, solo_cambios=True):
    """Muestra la comparación detallada entre dos productos - MEJORADA."""
    
    df_a = df_ddp[df_ddp["Producto"] == producto_a]
    df_b = df_ddp[df_ddp["Producto"] == producto_b]
    
    if df_a.empty or df_b.empty:
        st.warning("⚠️ No se encontraron datos para uno o ambos productos.")
        return
    
    # Contenedor para métricas principales
    with st.container():
        # Mostrar tiempo de cambio con más detalle
        tiempo = obtener_tiempo_cambio(df_tiempo, producto_a, producto_b)
        tiempo_inverso = obtener_tiempo_cambio(df_tiempo, producto_b, producto_a)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if tiempo:
                st.success(f"⏱️ **Tiempo A→B:** {tiempo} min")
            else:
                st.warning("⏱️ **Tiempo A→B:** No registrado")
        
        with col2:
            if tiempo_inverso:
                st.success(f"⏱️ **Tiempo B→A:** {tiempo_inverso} min")
            else:
                st.warning("⏱️ **Tiempo B→A:** No registrado")
        
        with col3:
            if tiempo and tiempo_inverso:
                promedio = (tiempo + tiempo_inverso) / 2
                st.info(f"⏱️ **Promedio:** {promedio:.1f} min")
    
    # Comparación técnica (DDP)
    st.markdown("---")
    st.markdown("### 🔢 Análisis Técnico Detallado")
    
    columnas_ddp = [col for col in df_a.columns if col not in ["STD", "Producto", "Familia"]]
    
    with st.spinner("Analizando diferencias técnicas..."):
        resumen_ddp = comparar_productos(df_a, df_b, columnas_ddp)
    
    if not resumen_ddp.empty:
        # Mostrar métricas antes de la tabla
        mostrar_metricas_resumen(resumen_ddp)
        
        # Filtrar si se solicita
        if solo_cambios:
            resumen_ddp_filtrado = resumen_ddp[resumen_ddp["¿Cambia?"] == "✅ Sí"]
            if resumen_ddp_filtrado.empty:
                st.success("✅ **¡No hay cambios técnicos entre estos productos!**")
            else:
                st.dataframe(
                    resumen_ddp_filtrado.style.apply(resaltar_cambios, axis=1),
                    use_container_width=True,
                    height=400
                )
        else:
            st.dataframe(
                resumen_ddp.style.apply(resaltar_cambios, axis=1),
                use_container_width=True,
                height=400
            )
    
    # Comparación desbaste
    st.markdown("---")
    st.markdown("### 🧠 Análisis de Diagrama Desbaste")
    
    with st.spinner("Analizando diagrama de desbaste..."):
        df_desbaste_cmp = comparar_desbaste(df_desbaste, familia_a, familia_b)
    
    if not df_desbaste_cmp.empty:
        mostrar_metricas_resumen(df_desbaste_cmp)
        
        if solo_cambios:
            df_desbaste_filtrado = df_desbaste_cmp[df_desbaste_cmp["¿Cambia?"] == "✅ Sí"]
            if df_desbaste_filtrado.empty:
                st.success("✅ **¡No hay cambios en el diagrama de desbaste!**")
            else:
                st.dataframe(
                    df_desbaste_filtrado.style.apply(resaltar_cambios, axis=1),
                    use_container_width=True
                )
        else:
            st.dataframe(
                df_desbaste_cmp.style.apply(resaltar_cambios, axis=1),
                use_container_width=True
            )
    else:
        st.info("ℹ️ No se encontraron datos de desbaste para comparar.")
    
    # Análisis de cambios por componente
    if not resumen_ddp.empty:
        st.markdown("---")
        st.markdown("### 📊 Análisis de Impacto por Componente")
        
        resumen_contador = resumen_ddp[resumen_ddp["¿Cambia?"] == "✅ Sí"]
        if not resumen_contador.empty:
            conteo_por_componente = resumen_contador["Componente"].value_counts().reset_index()
            conteo_por_componente.columns = ["Componente", "Cantidad de Cambios"]
            
            # Mostrar top 10 componentes con más cambios
            st.dataframe(
                conteo_por_componente.head(10),
                use_container_width=True
            )

def mostrar_secuencia_programa(df_ddp, df_tiempo):
    """Muestra el análisis de la secuencia del programa - MEJORADA."""
    
    df_prog = st.session_state.df_prog
    
    # Mostrar información del programa
    st.markdown(f"**Programa cargado:** {len(df_prog)} registros")
    
    with st.spinner("Analizando secuencia de cambios..."):
        resumen = []
        
        # Optimizar el análisis usando vectorización cuando sea posible
        for i in range(len(df_prog) - 1):
            origen = df_prog.loc[i, "Nombre STD"]
            destino = df_prog.loc[i + 1, "Nombre STD"]
            
            # Skip si es el mismo producto
            if origen == destino:
                continue
            
            # Obtener tiempo de cambio
            tiempo = obtener_tiempo_cambio(df_tiempo, origen, destino)
            
            # Calcular cambios en código canal de forma más eficiente
            df_a = df_ddp[df_ddp["Producto"] == origen]
            df_b = df_ddp[df_ddp["Producto"] == destino]
            
            cambios_codigo_canal = 0
            if not df_a.empty and not df_b.empty and "Código Canal" in df_a.columns:
                # Merge para comparación eficiente
                merged = df_a[["STD", "Código Canal"]].merge(
                    df_b[["STD", "Código Canal"]], 
                    on="STD", 
                    suffixes=("_A", "_B")
                )
                if not merged.empty:
                    cambios_codigo_canal = (merged["Código Canal_A"] != merged["Código Canal_B"]).sum()
            
            # Obtener familias
            familia_origen = df_a['Familia'].iloc[0] if not df_a.empty else "N/A"
            familia_destino = df_b['Familia'].iloc[0] if not df_b.empty else "N/A"
            
            resumen.append({
                "Secuencia": i + 1,
                "Familia": f"{familia_origen} → {familia_destino}",
                "Producto Origen": origen,
                "Producto Destino": destino,
                "Tiempo estimado": tiempo,
                "Cambios Código Canal": cambios_codigo_canal
            })
    
    if not resumen:
        st.info("ℹ️ No se encontraron cambios de producto en la secuencia.")
        return
    
    # Agrupar cambios consecutivos
    df_resumen = agrupar_cambios_consecutivos(pd.DataFrame(resumen))
    
    # Mostrar resumen general
    tiempo_total = df_resumen["Tiempo estimado"].dropna().sum()
    cambios_totales = len(df_resumen)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Cambios", cambios_totales)
    with col2:
        st.metric("Tiempo Total Estimado", f"{tiempo_total:.0f} min" if tiempo_total > 0 else "N/A")
    with col3:
        st.metric("Tiempo Promedio/Cambio", f"{tiempo_total/cambios_totales:.1f} min" if tiempo_total > 0 and cambios_totales > 0 else "N/A")
    
    # Mostrar cambios detallados
    st.markdown("---")
    st.markdown("### 🔄 Detalle de Cambios en Secuencia")
    
    for idx, fila in df_resumen.iterrows():
        tiempo_mostrar = f"{int(fila['Tiempo estimado'])} min" if pd.notna(fila['Tiempo estimado']) else "⚠️ No registrado"
        
        # Color coding para el tiempo
        if pd.notna(fila['Tiempo estimado']):
            if fila['Tiempo estimado'] > 60:
                tiempo_color = "🔴"
            elif fila['Tiempo estimado'] > 30:
                tiempo_color = "🟡"
            else:
                tiempo_color = "🟢"
        else:
            tiempo_color = "⚪"
        
        titulo = f"{tiempo_color} **Cambio #{fila['Secuencia']}** | {fila['Producto Origen']} → {fila['Producto Destino']} | ⏱️ {tiempo_mostrar} | 🔧 {fila['Cambios Código Canal']} cambios canal"
        
        with st.expander(titulo):
            df_a_cmp = df_ddp[df_ddp["Producto"] == fila['Producto Origen']]
            df_b_cmp = df_ddp[df_ddp["Producto"] == fila['Producto Destino']]
            
            if not df_a_cmp.empty and not df_b_cmp.empty:
                columnas_cmp = [col for col in df_a_cmp.columns if col not in ["STD", "Producto", "Familia"]]
                resumen_cmp = comparar_productos(df_a_cmp, df_b_cmp, columnas_cmp)
                resumen_cmp_cambios = resumen_cmp[resumen_cmp["¿Cambia?"] == "✅ Sí"]
                
                if not resumen_cmp_cambios.empty:
                    st.dataframe(resumen_cmp_cambios, use_container_width=True)
                else:
                    st.success("✅ No hay cambios técnicos para este cambio de producto")

def mostrar_resumen_maestranza(df_ddp):
    """Muestra el resumen técnico para maestranza - MEJORADA."""
    
    df_prog = st.session_state.df_prog.copy()
    
    with st.spinner("Generando resumen para maestranza..."):
        # Detectar bloques consecutivos del mismo producto
        df_prog["Grupo"] = (df_prog["Nombre STD"] != df_prog["Nombre STD"].shift()).cumsum()
        
        # Sumar toneladas programadas por bloque consecutivo
        df_programa = (
            df_prog
            .groupby(["Grupo", "Nombre STD"], as_index=False)
            .agg({
                "PROGR": "sum",
                "Nombre STD": "first"  # Para mantener el nombre
            })
            .rename(columns={"PROGR": "Toneladas Programadas"})
        )
        
        # Obtener información técnica adicional
        info_tecnica = (
            df_ddp.groupby("Producto")
            .agg({
                "Código Canal": lambda x: ", ".join(sorted([str(c) for c in x.dropna().unique()])),
                "Familia": "first"
            })
            .reset_index()
            .rename(columns={"Producto": "Nombre STD"})
        )
        
        # Unir programa con información técnica
        df_resumen = df_programa.merge(info_tecnica, on="Nombre STD", how="left")
        df_resumen = df_resumen[["Nombre STD", "Toneladas Programadas", "Familia", "Código Canal"]]
        
        # Ordenar por secuencia original
        df_resumen = df_resumen.sort_values("Grupo").reset_index(drop=True)
    
    # Mostrar métricas generales
    total_toneladas = df_resumen["Toneladas Programadas"].sum()
    productos_unicos = df_resumen["Nombre STD"].nunique()
    familias_unicas = df_resumen["Familia"].nunique()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Toneladas", f"{total_toneladas:,.0f}")
    with col2:
        st.metric("Productos Únicos", productos_unicos)
    with col3:
        st.metric("Familias", familias_unicas)
    
    # Análisis por familia
    st.markdown("---")
    st.markdown("### 📊 Distribución por Familia")
    
    resumen_familias = (
        df_resumen.groupby("Familia", as_index=False)
        .agg({
            "Toneladas Programadas": "sum",
            "Nombre STD": "count"
        })
        .rename(columns={"Nombre STD": "Cantidad Productos"})
        .sort_values("Toneladas Programadas", ascending=False)
    )
    
    st.dataframe(resumen_familias, use_container_width=True)
    
    # Tabla principal
    st.markdown("---")
    st.markdown("### 📋 Resumen Detallado por Producto")
    
    # Formatear la tabla para mejor visualización
    df_display = df_resumen.copy()
    df_display["Toneladas Programadas"] = df_display["Toneladas Programadas"].apply(lambda x: f"{x:,.1f}")
    
    st.dataframe(df_display, use_container_width=True)
    
    # Exportación mejorada
    st.markdown("---")
    st.markdown("### 📥 Exportar Datos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Excel con múltiples hojas
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            # Hoja principal
            df_resumen.to_excel(writer, index=False, sheet_name="Resumen_Maestranza")
            
            # Hoja de resumen por familias
            resumen_familias.to_excel(writer, index=False, sheet_name="Resumen_Familias")
            
            # Hoja con programa completo
            st.session_state.df_prog.to_excel(writer, index=False, sheet_name="Programa_Completo")
            
            # Formatear hojas
            workbook = writer.book
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4CAF50',
                'font_color': 'white',
                'border': 1
            })
            
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                worksheet.set_row(0, 20, header_format)
                worksheet.autofit()
        
        buffer.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Resumen_Maestranza_{timestamp}.xlsx"
        
        st.download_button(
            label="📊 Descargar Excel Completo",
            data=buffer,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Incluye resumen principal, análisis por familias y programa completo"
        )
    
    with col2:
        # CSV simple
        csv_buffer = io.StringIO()
        df_resumen.to_csv(csv_buffer, index=False, encoding='utf-8')
        csv_data = csv_buffer.getvalue().encode('utf-8')
        
        st.download_button(
            label="📄 Descargar CSV",
            data=csv_data,
            file_name=f"resumen_maestranza_{timestamp}.csv",
            mime="text/csv",
            help="Archivo CSV simple para análisis adicional"
        )

# =====================================
# FUNCIONES ADICIONALES DE UTILIDAD
# =====================================

@st.cache_data
def generar_estadisticas_globales(df_ddp, df_tiempo):
    """Genera estadísticas globales del sistema."""
    stats = {
        "total_productos": df_ddp["Producto"].nunique(),
        "total_familias": df_ddp["Familia"].nunique(),
        "total_tiempos_registrados": len(df_tiempo),
        "tiempo_promedio": df_tiempo["Minutos Cambio"].mean(),
        "tiempo_maximo": df_tiempo["Minutos Cambio"].max(),
        "tiempo_minimo": df_tiempo["Minutos Cambio"].min()
    }
    return stats

def mostrar_sidebar_info():
    """Muestra información útil en la sidebar."""
    with st.sidebar:
        st.markdown("### ℹ️ Información del Sistema")
        
        if st.button("🔄 Limpiar Cache"):
            st.cache_data.clear()
            st.success("Cache limpiado")
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 📊 Estadísticas Rápidas")
        
        # Solo mostrar si los datos están cargados
        if 'datos_cargados' in st.session_state:
            stats = st.session_state.get('estadisticas_globales', {})
            if stats:
                st.metric("Productos", stats.get("total_productos", "N/A"))
                st.metric("Familias", stats.get("total_familias", "N/A"))
                st.metric("Tiempo Prom.", f"{stats.get('tiempo_promedio', 0):.1f} min")
        
        st.markdown("---")
        st.markdown("### 🔧 Configuración")
        
        # Configuraciones de usuario
        if st.checkbox("Modo Avanzado", help="Muestra opciones adicionales"):
            st.session_state.modo_avanzado = True
        else:
            st.session_state.modo_avanzado = False
        
        if st.checkbox("Auto-actualizar", help="Actualiza automáticamente al cambiar selecciones"):
            st.session_state.auto_actualizar = True
        else:
            st.session_state.auto_actualizar = False

def validar_integridad_datos(df_ddp, df_tiempo, df_desbaste):
    """Valida la integridad de los datos cargados."""
    problemas = []
    
    # Validaciones DDP
    if df_ddp["Producto"].isna().any():
        problemas.append("❌ Hay productos sin nombre en DDP")
    
    if df_ddp["Familia"].isna().sum() > len(df_ddp) * 0.1:
        problemas.append("⚠️ Más del 10% de productos sin familia asignada")
    
    # Validaciones Tiempo
    productos_ddp = set(df_ddp["Producto"].dropna())
    productos_tiempo_origen = set(df_tiempo["Nombre STD Origen"].dropna())
    productos_tiempo_destino = set(df_tiempo["Nombre STD Destino"].dropna())
    
    productos_sin_tiempo = productos_ddp - productos_tiempo_origen - productos_tiempo_destino
    if len(productos_sin_tiempo) > 0:
        problemas.append(f"⚠️ {len(productos_sin_tiempo)} productos sin tiempos de cambio registrados")
    
    # Validaciones Desbaste
    familias_ddp = set(df_ddp["Familia"].dropna())
    familias_desbaste = set(df_desbaste["Familia"].dropna())
    
    familias_sin_desbaste = familias_ddp - familias_desbaste
    if len(familias_sin_desbaste) > 0:
        problemas.append(f"⚠️ {len(familias_sin_desbaste)} familias sin diagrama de desbaste")
    
    return problemas

def mostrar_validacion_datos(df_ddp, df_tiempo, df_desbaste):
    """Muestra el resultado de la validación de datos."""
    problemas = validar_integridad_datos(df_ddp, df_tiempo, df_desbaste)
    
    if problemas:
        with st.expander("⚠️ Advertencias de Integridad de Datos"):
            for problema in problemas:
                st.write(problema)
    else:
        st.success("✅ Integridad de datos verificada correctamente")

# =====================================
# MAIN ACTUALIZADO
# =====================================

def main():
    """Función principal de la aplicación - VERSIÓN MEJORADA."""
    
    # Mostrar sidebar info
    mostrar_sidebar_info()
    
    # Header con información
    st.markdown("""
    # 🔧 Plataforma de Cambio de Producto – Laminador
    *Sistema de análisis y comparación de productos para optimización de cambios*
    """)
    
    # Cargar datos base con indicador de progreso
    with st.spinner("Cargando datos base..."):
        df_ddp, df_tiempo, df_desbaste = cargar_datos()
    
    if df_ddp is None:
        st.error("No se pudieron cargar los datos base. Verifica que los archivos existan.")
        st.stop()
    
    # Marcar datos como cargados y generar estadísticas
    st.session_state.datos_cargados = True
    st.session_state.estadisticas_globales = generar_estadisticas_globales(df_ddp, df_tiempo)
    
    # Validar integridad de datos
    mostrar_validacion_datos(df_ddp, df_tiempo, df_desbaste)
    
    # Mostrar información de los datos cargados
    with st.expander("ℹ️ Información de datos cargados", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Productos DDP", len(df_ddp))
        with col2:
            st.metric("Tiempos de Cambio", len(df_tiempo))
        with col3:
            st.metric("Registros Desbaste", len(df_desbaste))
        with col4:
            st.metric("Familias", df_ddp["Familia"].nunique())
    
    # Carga global del programa
    cargar_programa_usuario()
    
    # Crear pestañas con iconos más descriptivos
    tabs = st.tabs([
        "🔍 Comparador Manual", 
        "📋 Análisis de Secuencia", 
        "🏭 Resumen Maestranza",
        "📊 Dashboard General"
    ])
    
    # =====================================
    # PESTAÑA 1: COMPARADOR MANUAL
    # =====================================
    
    with tabs[0]:
        st.subheader("🔄 Comparación Manual de Productos")
        
        # Interfaz mejorada para selección
        with st.container():
            # Selección de familias con filtros
            familias = ["(Todos)"] + sorted(df_ddp["Familia"].dropna().unique())
            
            col_f1, col_f2, col_config = st.columns([1, 1, 1])
            
            with col_f1:
                familia_a = st.selectbox("🏷️ Familia A", familias, key="famA")
            with col_f2:
                familia_b = st.selectbox("🏷️ Familia B", familias, key="famB")
            with col_config:
                st.markdown("**Opciones de visualización:**")
                solo_cambios_global = st.checkbox("Solo mostrar cambios", value=True)
                if st.session_state.get('modo_avanzado', False):
                    mostrar_metricas = st.checkbox("Mostrar métricas detalladas", value=True)
                else:
                    mostrar_metricas = True
        
        # Filtrar productos por familia
        df_fam_a = df_ddp if familia_a == "(Todos)" else df_ddp[df_ddp["Familia"] == familia_a]
        df_fam_b = df_ddp if familia_b == "(Todos)" else df_ddp[df_ddp["Familia"] == familia_b]
        
        productos_a = sorted(df_fam_a["Producto"].dropna().unique())
        productos_b = sorted(df_fam_b["Producto"].dropna().unique())
        
        # Selección de productos con búsqueda
        col_a, col_b = st.columns(2)
        
        with col_a:
            producto_a = st.selectbox("🔧 Producto A", productos_a, key="A")
            if familia_a == "(Todos)":
                mostrar_info_familia(producto_a, df_ddp, "Producto A")
        
        with col_b:
            producto_b = st.selectbox("🔧 Producto B", productos_b, key="B")
            if familia_b == "(Todos)":
                mostrar_info_familia(producto_b, df_ddp, "Producto B")
        
        # Análisis de productos seleccionados
        if producto_a and producto_b:
            if producto_a == producto_b:
                st.warning("⚠️ Has seleccionado el mismo producto en ambos lados.")
            else:
                mostrar_comparacion_productos(
                    df_ddp, df_tiempo, df_desbaste, 
                    producto_a, producto_b, familia_a, familia_b,
                    solo_cambios_global
                )
    
    # =====================================
    # PESTAÑA 2: SECUENCIA DE PROGRAMA
    # =====================================
    
    with tabs[1]:
        st.subheader("📊 Análisis de Secuencia de Programa")
        
        if "df_prog" in st.session_state:
            mostrar_secuencia_programa(df_ddp, df_tiempo)
        else:
            st.info("📤 Por favor carga primero el archivo de programa.")
    
    # =====================================
    # PESTAÑA 3: MAESTRANZA
    # =====================================
    
    with tabs[2]:
        st.subheader("📈 Resumen Técnico para Maestranza")
        
        if "df_prog" in st.session_state:
            mostrar_resumen_maestranza(df_ddp)
        else:
            st.info("📤 Por favor carga primero el archivo de programa.")
    
    # =====================================
    # PESTAÑA 4: DASHBOARD GENERAL
    # =====================================
    
    with tabs[3]:
        st.subheader("📊 Dashboard General del Sistema")
        mostrar_dashboard_general(df_ddp, df_tiempo, df_desbaste)

def mostrar_dashboard_general(df_ddp, df_tiempo, df_desbaste):
    """Nueva pestaña con dashboard general del sistema."""
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Productos", df_ddp["Producto"].nunique())
    with col2:
        st.metric("Total Familias", df_ddp["Familia"].nunique()) 
    with col3:
        tiempo_prom = df_tiempo["Minutos Cambio"].mean()
        st.metric("Tiempo Cambio Prom.", f"{tiempo_prom:.1f} min")
    with col4:
        cobertura = (df_tiempo["Nombre STD Origen"].nunique() / df_ddp["Producto"].nunique()) * 100
        st.metric("Cobertura Tiempos", f"{cobertura:.1f}%")
    
    # Distribución por familias
    st.markdown("---")
    st.markdown("### 📊 Distribución de Productos por Familia")
    
    dist_familias = df_ddp["Familia"].value_counts().reset_index()
    dist_familias.columns = ["Familia", "Cantidad"]
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.bar_chart(dist_familias.set_index("Familia"))
    
    with col2:
        st.dataframe(dist_familias, use_container_width=True)
    
    # Análisis de tiempos de cambio
    st.markdown("---") 
    st.markdown("### ⏱️ Análisis de Tiempos de Cambio")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Distribución de Tiempos:**")
        bins = [0, 15, 30, 60, 120, float('inf')]
        labels = ['≤15 min', '15-30 min', '30-60 min', '60-120 min', '>120 min']
        df_tiempo['Categoria'] = pd.cut(df_tiempo["Minutos Cambio"], bins=bins, labels=labels)
        dist_tiempos = df_tiempo['Categoria'].value_counts()
        st.bar_chart(dist_tiempos)
    
    with col2:
        st.markdown("**Estadísticas:**")
        st.write(f"**Mínimo:** {df_tiempo['Minutos Cambio'].min():.1f} min")
        st.write(f"**Máximo:** {df_tiempo['Minutos Cambio'].max():.1f} min")
        st.write(f"**Mediana:** {df_tiempo['Minutos Cambio'].median():.1f} min")
        st.write(f"**Desv. Estándar:** {df_tiempo['Minutos Cambio'].std():.1f} min")
    
    # Top productos con más cambios registrados
    st.markdown("---")
    st.markdown("### 🔄 Productos con Más Cambios Registrados")
    
    cambios_origen = df_tiempo["Nombre STD Origen"].value_counts()
    cambios_destino = df_tiempo["Nombre STD Destino"].value_counts()
    total_cambios = (cambios_origen.add(cambios_destino, fill_value=0)).sort_values(ascending=False)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Top 10 Productos:**")
        st.dataframe(total_cambios.head(10).reset_index(), use_container_width=True)
    
    with col2:
        st.markdown("**Productos sin tiempos registrados:**")
        productos_sin_tiempo = set(df_ddp["Producto"]) - set(df_tiempo["Nombre STD Origen"]) - set(df_tiempo["Nombre STD Destino"])
        st.write(f"**Total:** {len(productos_sin_tiempo)} productos")
        if len(productos_sin_tiempo) > 0:
            st.write("Algunos ejemplos:")
            for prod in list(productos_sin_tiempo)[:5]:
                st.write(f"• {prod}")

# =====================================
# EJECUCIÓN PRINCIPAL
# =====================================

if __name__ == "__main__":
    main()