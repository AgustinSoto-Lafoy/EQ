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
            df = pd.read_excel(archivo)
            # Optimizar tipos de datos básico
            for col in df.select_dtypes(include=['object']).columns:
                if df[col].nunique() / len(df) < 0.5:  # Solo si tiene sentido
                    try:
                        df[col] = df[col].astype('category')
                    except:
                        pass  # Si falla, mantener como object
            
            datos[key] = df
            logger.info(f"Archivo {archivo} cargado exitosamente")
        except Exception as e:
            errores.append(f"Error cargando {archivo}: {str(e)}")
            logger.error(f"Error cargando {archivo}: {str(e)}")
    
    if errores:
        st.error("❌ Errores al cargar archivos base:\n" + "\n".join(errores))
        return None, None, None
    
    return datos.get("ddp"), datos.get("tiempo"), datos.get("desbaste")

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
                        
                        # Validaciones básicas
                        if "Nombre STD" not in df_prog.columns:
                            st.error("❌ El archivo debe contener la columna 'Nombre STD'")
                            return
                        
                        df_prog_clean = df_prog.dropna(subset=["Nombre STD"]).reset_index(drop=True)
                        
                        if df_prog_clean.empty:
                            st.error("❌ No se encontraron datos válidos en el archivo")
                            return
                        
                        st.session_state.df_prog = df_prog_clean
                        st.success(f"✅ Archivo cargado exitosamente ({len(df_prog_clean)} registros)")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error al cargar archivo: {e}")
                        logger.error(f"Error cargando programa: {str(e)}")

# =====================================
# FUNCIONES DE COMPARACIÓN MEJORADAS
# =====================================

@st.cache_data
def comparar_productos(df_a, df_b, columnas):
    """Compara dos productos y retorna las diferencias - VERSIÓN SEGURA."""
    if df_a.empty or df_b.empty:
        return pd.DataFrame()
    
    resumen = []
    posiciones = sorted(set(df_a["STD"]).union(df_b["STD"]))
    
    for pos in posiciones:
        fila_a = df_a[df_a["STD"] == pos]
        fila_b = df_b[df_b["STD"] == pos]
        
        for col in columnas:
            # Verificar que la columna existe
            if col not in df_a.columns and col not in df_b.columns:
                continue
                
            val_a = fila_a[col].values[0] if not fila_a.empty and col in fila_a.columns else None
            val_b = fila_b[col].values[0] if not fila_b.empty and col in fila_b.columns else None
            
            # Saltar valores vacíos o nulos
            if (val_a is None or pd.isna(val_a)) and (val_b is None or pd.isna(val_b)):
                continue
            
            # Comparación segura
            try:
                cambia = val_a != val_b
            except:
                cambia = str(val_a) != str(val_b)
            
            resumen.append({
                "Posicion": pos,
                "Componente": col,
                "Valor A": val_a if not pd.isna(val_a) else "-",
                "Valor B": val_b if not pd.isna(val_b) else "-",
                "¿Cambia?": "✅ Sí" if cambia else "❌ No"
            })
    
    return pd.DataFrame(resumen)

@st.cache_data
def comparar_desbaste(df_desbaste, familia_a, familia_b):
    """Compara diagrama de desbaste entre dos familias - VERSIÓN SEGURA."""
    try:
        # Filtrar por familias de forma segura
        if familia_a != "(Todos)":
            desb_a = df_desbaste[df_desbaste["Familia"] == familia_a]
        else:
            desb_a = df_desbaste.copy()
            
        if familia_b != "(Todos)":
            desb_b = df_desbaste[df_desbaste["Familia"] == familia_b]
        else:
            desb_b = df_desbaste.copy()
        
        # Verificar columnas necesarias
        columnas_requeridas = ["SubSTD", "Componente limpio", "Valor"]
        if not all(col in df_desbaste.columns for col in columnas_requeridas):
            return pd.DataFrame()
        
        # Obtener todos los pares únicos
        pares_a = set(zip(desb_a["SubSTD"], desb_a["Componente limpio"]))
        pares_b = set(zip(desb_b["SubSTD"], desb_b["Componente limpio"]))
        todos_pares = sorted(pares_a.union(pares_b))
        
        resumen_desbaste = []
        for substd, comp in todos_pares:
            # Buscar valores de forma segura
            val_a_df = desb_a[(desb_a["SubSTD"] == substd) & (desb_a["Componente limpio"] == comp)]
            val_b_df = desb_b[(desb_b["SubSTD"] == substd) & (desb_b["Componente limpio"] == comp)]
            
            val_a = val_a_df["Valor"].values[0] if not val_a_df.empty else None
            val_b = val_b_df["Valor"].values[0] if not val_b_df.empty else None
            
            # Saltar valores vacíos
            if (val_a is None or pd.isna(val_a)) and (val_b is None or pd.isna(val_b)):
                continue
            
            # Comparación segura
            try:
                cambia = val_a != val_b
            except:
                cambia = str(val_a) != str(val_b)
                
            resumen_desbaste.append({
                "Posición": substd,
                "Componente": comp,
                "Valor A": val_a if not pd.isna(val_a) else "-",
                "Valor B": val_b if not pd.isna(val_b) else "-",
                "¿Cambia?": "✅ Sí" if cambia else "❌ No"
            })
        
        return pd.DataFrame(resumen_desbaste)
        
    except Exception as e:
        logger.error(f"Error en comparar_desbaste: {str(e)}")
        return pd.DataFrame()

@st.cache_data
def obtener_tiempo_cambio(df_tiempo, producto_origen, producto_destino):
    """Obtiene el tiempo de cambio entre dos productos - VERSIÓN SEGURA."""
    try:
        columnas_requeridas = ["Nombre STD Origen", "Nombre STD Destino", "Minutos Cambio"]
        if not all(col in df_tiempo.columns for col in columnas_requeridas):
            return None
            
        mask = (df_tiempo["Nombre STD Origen"] == producto_origen) & \
               (df_tiempo["Nombre STD Destino"] == producto_destino)
        
        resultado = df_tiempo.loc[mask, "Minutos Cambio"]
        return resultado.iloc[0] if not resultado.empty else None
    except Exception as e:
        logger.error(f"Error obteniendo tiempo: {str(e)}")
        return None

def agrupar_cambios_consecutivos(df):
    """Agrupa cambios consecutivos del mismo tipo - VERSIÓN SEGURA."""
    if df.empty:
        return df
    
    try:
        # Verificar columnas necesarias
        columnas_requeridas = ["Producto Origen", "Producto Destino"]
        if not all(col in df.columns for col in columnas_requeridas):
            return df
        
        # Crear grupos de forma segura
        df = df.copy()
        df["Grupo"] = (df[columnas_requeridas] != df[columnas_requeridas].shift()).any(axis=1).cumsum()

        # Definir agregaciones solo para columnas que existen
        agg_dict = {}
        columnas_posibles = {
            "Secuencia": "first",
            "Familia": "first", 
            "Producto Origen": "first",
            "Producto Destino": "first",
            "Tiempo estimado": "first",
            "Cambios Código Canal": "first"
        }
        
        for col, func in columnas_posibles.items():
            if col in df.columns:
                agg_dict[col] = func
        
        df_agrupado = df.groupby("Grupo", as_index=False).agg(agg_dict)
        return df_agrupado
        
    except Exception as e:
        logger.error(f"Error agrupando cambios: {str(e)}")
        return df

# =====================================
# FUNCIONES DE ESTILO Y UI
# =====================================

def resaltar_cambios(row):
    """Aplica estilo a las filas que tienen cambios."""
    try:
        color_cambio = "#ffebee"
        color_sin_cambio = "#f1f8e9"
        
        if "¿Cambia?" in row and row["¿Cambia?"] == "✅ Sí":
            return [f'background-color: {color_cambio}; font-weight: bold'] * len(row)
        else:
            return [f'background-color: {color_sin_cambio}'] * len(row)
    except:
        return [''] * len(row)

def mostrar_info_familia(producto, df_ddp, label):
    """Muestra información de la familia del producto."""
    try:
        if producto and "Familia" in df_ddp.columns:
            familia = df_ddp[df_ddp["Producto"] == producto]["Familia"].dropna().unique()
            if len(familia) > 0:
                st.info(f"ℹ️ {label} pertenece a la familia: **{familia[0]}**")
    except Exception as e:
        logger.error(f"Error mostrando familia: {str(e)}")

def mostrar_metricas_resumen(df_cambios):
    """Muestra métricas de resumen de cambios."""
    try:
        if not df_cambios.empty and "¿Cambia?" in df_cambios.columns:
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
    except Exception as e:
        logger.error(f"Error mostrando métricas: {str(e)}")

# =====================================
# INTERFAZ PRINCIPAL
# =====================================

def main():
    """Función principal de la aplicación."""
    
    # Header
    st.markdown("""
    # 🔧 Plataforma de Cambio de Producto – Laminador
    *Sistema de análisis y comparación de productos para optimización de cambios*
    """)
    
    # Cargar datos base
    with st.spinner("Cargando datos base..."):
        df_ddp, df_tiempo, df_desbaste = cargar_datos()
    
    if df_ddp is None:
        st.error("No se pudieron cargar los datos base. Verifica que los archivos existan.")
        st.stop()
    
    # Mostrar información básica
    with st.expander("ℹ️ Información de datos cargados", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Productos DDP", len(df_ddp))
        with col2:
            st.metric("Tiempos de Cambio", len(df_tiempo))
        with col3:
            st.metric("Registros Desbaste", len(df_desbaste))
    
    # Carga del programa
    cargar_programa_usuario()
    
    # Pestañas principales
    tabs = st.tabs([
        "🔍 Comparador Manual", 
        "📋 Análisis de Secuencia", 
        "🏭 Resumen Maestranza"
    ])
    
    # PESTAÑA 1: COMPARADOR MANUAL
    with tabs[0]:
        st.subheader("🔄 Comparación Manual de Productos")
        mostrar_comparador_manual(df_ddp, df_tiempo, df_desbaste)
    
    # PESTAÑA 2: SECUENCIA DE PROGRAMA
    with tabs[1]:
        st.subheader("📊 Análisis de Secuencia de Programa")
        if "df_prog" in st.session_state:
            mostrar_secuencia_programa(df_ddp, df_tiempo)
        else:
            st.info("📤 Por favor carga primero el archivo de programa.")
    
    # PESTAÑA 3: MAESTRANZA
    with tabs[2]:
        st.subheader("📈 Resumen Técnico para Maestranza")
        if "df_prog" in st.session_state:
            mostrar_resumen_maestranza(df_ddp)
        else:
            st.info("📤 Por favor carga primero el archivo de programa.")

def mostrar_comparador_manual(df_ddp, df_tiempo, df_desbaste):
    """Muestra el comparador manual de productos."""
    
    # Verificar columnas necesarias
    if "Familia" not in df_ddp.columns or "Producto" not in df_ddp.columns:
        st.error("❌ El archivo DDP debe contener las columnas 'Familia' y 'Producto'")
        return
    
    # Selección de familias
    familias = ["(Todos)"] + sorted(df_ddp["Familia"].dropna().unique())
    
    col_f1, col_f2, col_config = st.columns([1, 1, 1])
    
    with col_f1:
        familia_a = st.selectbox("🏷️ Familia A", familias, key="famA")
    with col_f2:
        familia_b = st.selectbox("🏷️ Familia B", familias, key="famB")
    with col_config:
        st.markdown("**Opciones:**")
        solo_cambios = st.checkbox("Solo mostrar cambios", value=True)
    
    # Filtrar productos por familia
    try:
        if familia_a == "(Todos)":
            df_fam_a = df_ddp
        else:
            df_fam_a = df_ddp[df_ddp["Familia"] == familia_a]
            
        if familia_b == "(Todos)":
            df_fam_b = df_ddp
        else:
            df_fam_b = df_ddp[df_ddp["Familia"] == familia_b]
        
        productos_a = sorted(df_fam_a["Producto"].dropna().unique())
        productos_b = sorted(df_fam_b["Producto"].dropna().unique())
        
    except Exception as e:
        st.error(f"Error filtrando productos: {str(e)}")
        return
    
    # Selección de productos
    col_a, col_b = st.columns(2)
    
    with col_a:
        if productos_a:
            producto_a = st.selectbox("🔧 Producto A", productos_a, key="A")
            if familia_a == "(Todos)":
                mostrar_info_familia(producto_a, df_ddp, "Producto A")
        else:
            st.warning("No hay productos disponibles para la Familia A")
            return
    
    with col_b:
        if productos_b:
            producto_b = st.selectbox("🔧 Producto B", productos_b, key="B")
            if familia_b == "(Todos)":
                mostrar_info_familia(producto_b, df_ddp, "Producto B")
        else:
            st.warning("No hay productos disponibles para la Familia B")
            return
    
    # Mostrar comparación
    if producto_a and producto_b:
        if producto_a == producto_b:
            st.warning("⚠️ Has seleccionado el mismo producto en ambos lados.")
        else:
            mostrar_comparacion_productos(
                df_ddp, df_tiempo, df_desbaste, 
                producto_a, producto_b, familia_a, familia_b, solo_cambios
            )

def mostrar_comparacion_productos(df_ddp, df_tiempo, df_desbaste, producto_a, producto_b, familia_a, familia_b, solo_cambios=True):
    """Muestra la comparación detallada entre dos productos."""
    
    try:
        df_a = df_ddp[df_ddp["Producto"] == producto_a]
        df_b = df_ddp[df_ddp["Producto"] == producto_b]
        
        if df_a.empty or df_b.empty:
            st.warning("⚠️ No se encontraron datos para uno o ambos productos.")
            return
        
        # Mostrar tiempos de cambio
        st.markdown("### ⏱️ Tiempos de Cambio")
        col1, col2 = st.columns(2)
        
        with col1:
            tiempo_ab = obtener_tiempo_cambio(df_tiempo, producto_a, producto_b)
            if tiempo_ab:
                st.success(f"**A → B:** {tiempo_ab} min")
            else:
                st.warning("**A → B:** No registrado")
        
        with col2:
            tiempo_ba = obtener_tiempo_cambio(df_tiempo, producto_b, producto_a)
            if tiempo_ba:
                st.success(f"**B → A:** {tiempo_ba} min")
            else:
                st.warning("**B → A:** No registrado")
        
        # Comparación técnica (DDP)
        st.markdown("---")
        st.markdown("### 🔢 Análisis Técnico")
        
        columnas_ddp = [col for col in df_a.columns if col not in ["STD", "Producto", "Familia"]]
        
        if columnas_ddp:
            with st.spinner("Analizando diferencias técnicas..."):
                resumen_ddp = comparar_productos(df_a, df_b, columnas_ddp)
            
            if not resumen_ddp.empty:
                mostrar_metricas_resumen(resumen_ddp)
                
                if solo_cambios:
                    resumen_filtrado = resumen_ddp[resumen_ddp["¿Cambia?"] == "✅ Sí"]
                    if resumen_filtrado.empty:
                        st.success("✅ **¡No hay cambios técnicos entre estos productos!**")
                    else:
                        st.dataframe(
                            resumen_filtrado.style.apply(resaltar_cambios, axis=1),
                            use_container_width=True
                        )
                else:
                    st.dataframe(
                        resumen_ddp.style.apply(resaltar_cambios, axis=1),
                        use_container_width=True
                    )
        
        # Comparación desbaste
        st.markdown("---")
        st.markdown("### 🧠 Análisis de Diagrama Desbaste")
        
        with st.spinner("Analizando diagrama de desbaste..."):
            df_desbaste_cmp = comparar_desbaste(df_desbaste, familia_a, familia_b)
        
        if not df_desbaste_cmp.empty:
            mostrar_metricas_resumen(df_desbaste_cmp)
            
            if solo_cambios:
                desbaste_filtrado = df_desbaste_cmp[df_desbaste_cmp["¿Cambia?"] == "✅ Sí"]
                if desbaste_filtrado.empty:
                    st.success("✅ **¡No hay cambios en el diagrama de desbaste!**")
                else:
                    st.dataframe(
                        desbaste_filtrado.style.apply(resaltar_cambios, axis=1),
                        use_container_width=True
                    )
            else:
                st.dataframe(
                    df_desbaste_cmp.style.apply(resaltar_cambios, axis=1),
                    use_container_width=True
                )
        else:
            st.info("ℹ️ No se encontraron datos de desbaste para comparar.")
            
    except Exception as e:
        st.error(f"Error en la comparación: {str(e)}")
        logger.error(f"Error en mostrar_comparacion_productos: {str(e)}")

def mostrar_secuencia_programa(df_ddp, df_tiempo):
    """Muestra el análisis de la secuencia del programa."""
    
    try:
        df_prog = st.session_state.df_prog
        st.markdown(f"**Programa cargado:** {len(df_prog)} registros")
        
        with st.spinner("Analizando secuencia de cambios..."):
            resumen = []
            
            for i in range(len(df_prog) - 1):
                origen = df_prog.loc[i, "Nombre STD"]
                destino = df_prog.loc[i + 1, "Nombre STD"]
                
                # Skip si es el mismo producto
                if origen == destino:
                    continue
                
                # Obtener tiempo de cambio
                tiempo = obtener_tiempo_cambio(df_tiempo, origen, destino)
                
                # Calcular cambios en código canal
                cambios_codigo_canal = 0
                try:
                    df_a = df_ddp[df_ddp["Producto"] == origen]
                    df_b = df_ddp[df_ddp["Producto"] == destino]
                    
                    if not df_a.empty and not df_b.empty and "Código Canal" in df_a.columns:
                        # Comparar códigos de canal de forma segura
                        for _, row_a in df_a.iterrows():
                            matching_b = df_b[df_b["STD"] == row_a["STD"]]
                            if not matching_b.empty:
                                if row_a["Código Canal"] != matching_b.iloc[0]["Código Canal"]:
                                    cambios_codigo_canal += 1
                except Exception as e:
                    logger.error(f"Error calculando cambios código canal: {str(e)}")
                
                # Obtener familias
                try:
                    familia_origen = df_ddp[df_ddp["Producto"] == origen]['Familia'].iloc[0] if not df_ddp[df_ddp["Producto"] == origen].empty else "N/A"
                    familia_destino = df_ddp[df_ddp["Producto"] == destino]['Familia'].iloc[0] if not df_ddp[df_ddp["Producto"] == destino].empty else "N/A"
                except:
                    familia_origen = "N/A"
                    familia_destino = "N/A"
                
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
        try:
            tiempo_total = df_resumen["Tiempo estimado"].dropna().sum() if "Tiempo estimado" in df_resumen.columns else 0
            cambios_totales = len(df_resumen)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Cambios", cambios_totales)
            with col2:
                st.metric("Tiempo Total Estimado", f"{tiempo_total:.0f} min" if tiempo_total > 0 else "N/A")
            with col3:
                st.metric("Tiempo Promedio/Cambio", f"{tiempo_total/cambios_totales:.1f} min" if tiempo_total > 0 and cambios_totales > 0 else "N/A")
        except Exception as e:
            logger.error(f"Error mostrando métricas secuencia: {str(e)}")
        
        # Mostrar cambios detallados
        st.markdown("---")
        st.markdown("### 🔄 Detalle de Cambios en Secuencia")
        
        for idx, fila in df_resumen.iterrows():
            try:
                tiempo_mostrar = f"{int(fila['Tiempo estimado'])} min" if pd.notna(fila.get('Tiempo estimado')) else "⚠️ No registrado"
                
                # Color coding para el tiempo
                if pd.notna(fila.get('Tiempo estimado')):
                    if fila['Tiempo estimado'] > 60:
                        tiempo_color = "🔴"
                    elif fila['Tiempo estimado'] > 30:
                        tiempo_color = "🟡"
                    else:
                        tiempo_color = "🟢"
                else:
                    tiempo_color = "⚪"
                
                cambios_canal = fila.get('Cambios Código Canal', 0)
                secuencia = fila.get('Secuencia', idx + 1)
                origen = fila.get('Producto Origen', 'N/A')
                destino = fila.get('Producto Destino', 'N/A')
                
                titulo = f"{tiempo_color} **Cambio #{secuencia}** | {origen} → {destino} | ⏱️ {tiempo_mostrar} | 🔧 {cambios_canal} cambios canal"
                
                with st.expander(titulo):
                    df_a_cmp = df_ddp[df_ddp["Producto"] == origen]
                    df_b_cmp = df_ddp[df_ddp["Producto"] == destino]
                    
                    if not df_a_cmp.empty and not df_b_cmp.empty:
                        columnas_cmp = [col for col in df_a_cmp.columns if col not in ["STD", "Producto", "Familia"]]
                        resumen_cmp = comparar_productos(df_a_cmp, df_b_cmp, columnas_cmp)
                        
                        if not resumen_cmp.empty:
                            resumen_cmp_cambios = resumen_cmp[resumen_cmp["¿Cambia?"] == "✅ Sí"]
                            
                            if not resumen_cmp_cambios.empty:
                                st.dataframe(resumen_cmp_cambios, use_container_width=True)
                            else:
                                st.success("✅ No hay cambios técnicos para este cambio de producto")
                        else:
                            st.info("No se pudieron analizar las diferencias técnicas")
                    else:
                        st.warning("No se encontraron datos para uno o ambos productos")
                        
            except Exception as e:
                logger.error(f"Error mostrando cambio {idx}: {str(e)}")
                st.error(f"Error mostrando cambio {idx + 1}")
        
    except Exception as e:
        st.error(f"Error analizando secuencia: {str(e)}")
        logger.error(f"Error en mostrar_secuencia_programa: {str(e)}")

def mostrar_resumen_maestranza(df_ddp):
    """Muestra el resumen técnico para maestranza."""
    
    try:
        df_prog = st.session_state.df_prog.copy()
        
        with st.spinner("Generando resumen para maestranza..."):
            # Detectar bloques consecutivos del mismo producto
            df_prog["Grupo"] = (df_prog["Nombre STD"] != df_prog["Nombre STD"].shift()).cumsum()
            
            # Verificar que existe la columna PROGR
            if "PROGR" not in df_prog.columns:
                st.error("❌ El archivo de programa debe contener la columna 'PROGR' para calcular toneladas")
                return
            
            # Agrupar y sumar toneladas
            df_programa = (
                df_prog
                .groupby(["Grupo", "Nombre STD"], as_index=False)
                .agg({"PROGR": "sum"})
                .rename(columns={"PROGR": "Toneladas Programadas"})
            )
            
            # Obtener información técnica adicional
            info_tecnica_dict = {}
            for producto in df_programa["Nombre STD"].unique():
                try:
                    producto_data = df_ddp[df_ddp["Producto"] == producto]
                    if not producto_data.empty:
                        # Códigos de canal
                        if "Código Canal" in producto_data.columns:
                            codigos = producto_data["Código Canal"].dropna().unique()
                            codigos_str = ", ".join(sorted([str(c) for c in codigos]))
                        else:
                            codigos_str = "N/A"
                        
                        # Familia
                        if "Familia" in producto_data.columns:
                            familia = producto_data["Familia"].iloc[0] if not producto_data.empty else "N/A"
                        else:
                            familia = "N/A"
                        
                        info_tecnica_dict[producto] = {
                            "Familia": familia,
                            "Código Canal": codigos_str
                        }
                    else:
                        info_tecnica_dict[producto] = {
                            "Familia": "N/A",
                            "Código Canal": "N/A"
                        }
                except Exception as e:
                    logger.error(f"Error procesando producto {producto}: {str(e)}")
                    info_tecnica_dict[producto] = {
                        "Familia": "N/A",
                        "Código Canal": "N/A"
                    }
            
            # Crear DataFrame de información técnica
            info_tecnica = pd.DataFrame.from_dict(info_tecnica_dict, orient='index').reset_index()
            info_tecnica.columns = ["Nombre STD", "Familia", "Código Canal"]
            
            # Unir programa con información técnica
            df_resumen = df_programa.merge(info_tecnica, on="Nombre STD", how="left")
            
            # Reordenar columnas y mantener orden por grupo
            df_resumen = df_resumen.sort_values("Grupo").reset_index(drop=True)
            df_resumen = df_resumen[["Nombre STD", "Toneladas Programadas", "Familia", "Código Canal"]]
        
        # Mostrar métricas generales
        try:
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
        except Exception as e:
            logger.error(f"Error calculando métricas maestranza: {str(e)}")
        
        # Análisis por familia
        st.markdown("---")
        st.markdown("### 📊 Distribución por Familia")
        
        try:
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
        except Exception as e:
            logger.error(f"Error creando resumen por familias: {str(e)}")
            st.error("Error creando resumen por familias")
        
        # Tabla principal
        st.markdown("---")
        st.markdown("### 📋 Resumen Detallado por Producto")
        
        # Formatear la tabla para mejor visualización
        df_display = df_resumen.copy()
        df_display["Toneladas Programadas"] = df_display["Toneladas Programadas"].apply(lambda x: f"{x:,.1f}")
        
        st.dataframe(df_display, use_container_width=True)
        
        # Exportación
        st.markdown("---")
        st.markdown("### 📥 Exportar Datos")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Excel con múltiples hojas
            try:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    # Hoja principal
                    df_resumen.to_excel(writer, index=False, sheet_name="Resumen_Maestranza")
                    
                    # Hoja de resumen por familias
                    if 'resumen_familias' in locals():
                        resumen_familias.to_excel(writer, index=False, sheet_name="Resumen_Familias")
                    
                    # Hoja con programa completo
                    st.session_state.df_prog.to_excel(writer, index=False, sheet_name="Programa_Completo")
                
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
            except Exception as e:
                logger.error(f"Error creando Excel: {str(e)}")
                st.error("Error generando archivo Excel")
        
        with col2:
            # CSV simple
            try:
                csv_buffer = io.StringIO()
                df_resumen.to_csv(csv_buffer, index=False, encoding='utf-8')
                csv_data = csv_buffer.getvalue().encode('utf-8')
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                
                st.download_button(
                    label="📄 Descargar CSV",
                    data=csv_data,
                    file_name=f"resumen_maestranza_{timestamp}.csv",
                    mime="text/csv",
                    help="Archivo CSV simple para análisis adicional"
                )
            except Exception as e:
                logger.error(f"Error creando CSV: {str(e)}")
                st.error("Error generando archivo CSV")
        
    except Exception as e:
        st.error(f"Error generando resumen maestranza: {str(e)}")
        logger.error(f"Error en mostrar_resumen_maestranza: {str(e)}")

# =====================================
# EJECUCIÓN PRINCIPAL
# =====================================

if __name__ == "__main__":
    main()