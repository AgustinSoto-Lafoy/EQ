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

def _cruzar_programa_con_mapa(archivo_bytes):
    """
    Lee el programa (.xlsm o .xlsx) y genera el DataFrame equivalente a TablaCombinada
    haciendo el cruce interno con la hoja 'Mapa'.

    Returns (df_resultado, warnings_list) o lanza Exception si falla algo crítico.
    """
    import openpyxl

    wb = openpyxl.load_workbook(archivo_bytes, read_only=True, keep_vba=True, data_only=True)

    # --- Validar hojas requeridas ---
    hojas_requeridas = ["Prog LAM REN", "Mapa"]
    for hoja in hojas_requeridas:
        if hoja not in wb.sheetnames:
            raise ValueError(
                f"El archivo no contiene la hoja requerida '{hoja}'. "
                f"Hojas disponibles: {wb.sheetnames}"
            )

    # --- Leer Mapa ---
    ws_mapa = wb["Mapa"]
    mapa_rows = list(ws_mapa.iter_rows(min_row=2, values_only=True))
    df_mapa = pd.DataFrame(
        mapa_rows,
        columns=["Producto Limpio", "Nombre STD", "Producto STD", "Es Prueba"]
    ).dropna(subset=["Producto Limpio"])
    df_mapa["_key"] = df_mapa["Producto Limpio"].astype(str).str.strip()

    # --- Leer Prog LAM REN (encabezado en fila 8, datos desde fila 9) ---
    ws_prog = wb["Prog LAM REN"]
    all_rows = list(ws_prog.iter_rows(min_row=8, values_only=True))
    if not all_rows:
        raise ValueError("La hoja 'Prog LAM REN' no tiene datos.")

    headers = list(all_rows[0])
    # Renombrar PROGR. → PROGR para consistencia con el resto de la app
    headers = ["PROGR" if str(h) == "PROGR." else h for h in headers]

    data_rows = all_rows[1:]
    df_prog = pd.DataFrame(data_rows, columns=headers)

    # Filtrar solo filas con CLASIFICADA numérico (filas reales de producción)
    df_prog = df_prog[pd.to_numeric(df_prog["CLASIFICADA"], errors="coerce").notna()].copy()
    df_prog.reset_index(drop=True, inplace=True)

    if df_prog.empty:
        raise ValueError("No se encontraron filas de producción en 'Prog LAM REN'.")

    # --- Cruce ---
    df_prog["_key"] = df_prog["DESCRIPCIÓN"].astype(str).str.strip()
    df_merged = df_prog.merge(
        df_mapa[["_key", "Nombre STD", "Producto STD", "Es Prueba"]].rename(
            columns={"Es Prueba": "Tabla13.Es Prueba"}
        ),
        on="_key",
        how="left"
    ).drop(columns=["_key"])

    # Calcular filas sin match para advertencia
    sin_match = df_merged[df_merged["Nombre STD"].isna()]["DESCRIPCIÓN"].dropna().unique().tolist()
    warnings = []
    if sin_match:
        warnings.append(
            f"{len(sin_match)} producto(s) sin homologación en el Mapa: {', '.join(str(x) for x in sin_match[:5])}"
            + (" ..." if len(sin_match) > 5 else "")
        )

    return df_merged, warnings


def cargar_programa_usuario():
    """Maneja la carga del archivo de programa del usuario."""
    if "df_prog" not in st.session_state:
        with st.container():
            st.markdown("### 📤 Cargar Programa")
            archivo_programa = st.file_uploader(
                "Sube el archivo de programa (.xlsm o .xlsx)",
                type=None,  # Sin filtro MIME: Streamlit rechaza xlsm por su MIME type
                key="carga_global",
                help="Archivo debe contener las hojas 'Prog LAM REN' y 'Mapa'"
            )

            if archivo_programa is not None:
                ext = archivo_programa.name.rsplit(".", 1)[-1].lower()
                if ext not in ("xlsx", "xlsm"):
                    st.error(f"❌ Formato no soportado (.{ext}). Sube un archivo .xlsx o .xlsm.")
                    archivo_programa = None

            if archivo_programa is not None:
                with st.spinner("Cargando y cruzando programa con Mapa..."):
                    try:
                        archivo_bytes = io.BytesIO(archivo_programa.read())
                        df_merged, warnings = _cruzar_programa_con_mapa(archivo_bytes)

                        df_prog_clean = df_merged.dropna(subset=["Nombre STD"]).reset_index(drop=True)

                        if df_prog_clean.empty:
                            st.error("❌ No se encontraron filas con 'Nombre STD' tras el cruce. Verifica que la hoja 'Mapa' esté actualizada.")
                            return

                        st.session_state.df_prog = df_prog_clean

                        for w in warnings:
                            st.warning(f"⚠️ {w}")

                        st.success(f"✅ Programa cargado y cruzado exitosamente ({len(df_prog_clean)} registros)")
                        st.rerun()

                    except ValueError as e:
                        st.error(f"❌ {e}")
                    except Exception as e:
                        st.error(f"❌ Error al procesar archivo: {e}")
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
            if col not in df_a.columns or col not in df_b.columns:
                continue
                
            val_a = fila_a[col].values[0] if not fila_a.empty and col in fila_a.columns else None
            val_b = fila_b[col].values[0] if not fila_b.empty and col in fila_b.columns else None
            
            # Saltar valores vacíos o nulos
            if (val_a is None or pd.isna(val_a)) and (val_b is None or pd.isna(val_b)):
                continue
            
            # Comparación segura
            try:
                cambia = val_a != val_b
            except (TypeError, ValueError):
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
    """Compara diagrama de desbaste entre dos familias"""
    try:
        # Si son la misma familia, no hay cambios
        if familia_a == familia_b:
            return pd.DataFrame()
        
        # Filtrar por familias de forma segura
        if familia_a != "(Todos)":
            desb_a = df_desbaste[df_desbaste["Familia"] == familia_a].copy()
        else:
            desb_a = df_desbaste.copy()
            
        if familia_b != "(Todos)":
            desb_b = df_desbaste[df_desbaste["Familia"] == familia_b].copy()
        else:
            desb_b = df_desbaste.copy()
        
        # Verificar columnas necesarias
        columnas_requeridas = ["SubSTD", "Componente limpio", "Valor"]
        if not all(col in df_desbaste.columns for col in columnas_requeridas):
            logger.error(f"Columnas faltantes en desbaste. Requeridas: {columnas_requeridas}")
            return pd.DataFrame()
        
        # Limpiar valores para comparación consistente
        def limpiar_valor(val):
            if pd.isna(val) or val is None:
                return None
            # Convertir a string y limpiar espacios
            val_str = str(val).strip()
            # Intentar convertir a número si es posible
            try:
                return float(val_str)
            except:
                return val_str
        
        # Aplicar limpieza a los valores
        desb_a["Valor_limpio"] = desb_a["Valor"].apply(limpiar_valor)
        desb_b["Valor_limpio"] = desb_b["Valor"].apply(limpiar_valor)
        
        # Obtener todos los pares únicos (SubSTD, Componente)
        pares_a = set(zip(desb_a["SubSTD"], desb_a["Componente limpio"]))
        pares_b = set(zip(desb_b["SubSTD"], desb_b["Componente limpio"]))
        todos_pares = sorted(pares_a.union(pares_b))
        
        resumen_desbaste = []
        for substd, comp in todos_pares:
            # Buscar valores de forma segura
            val_a_df = desb_a[(desb_a["SubSTD"] == substd) & (desb_a["Componente limpio"] == comp)]
            val_b_df = desb_b[(desb_b["SubSTD"] == substd) & (desb_b["Componente limpio"] == comp)]
            
            # Obtener valores limpios
            val_a_limpio = val_a_df["Valor_limpio"].iloc[0] if not val_a_df.empty else None
            val_b_limpio = val_b_df["Valor_limpio"].iloc[0] if not val_b_df.empty else None
            
            # Obtener valores originales para mostrar
            val_a_original = val_a_df["Valor"].iloc[0] if not val_a_df.empty else None
            val_b_original = val_b_df["Valor"].iloc[0] if not val_b_df.empty else None
            
            # Si ambos son None, continuar
            if val_a_limpio is None and val_b_limpio is None:
                continue
            
            # Determinar si hay cambio
            if val_a_limpio is None or val_b_limpio is None:
                # Si uno tiene valor y el otro no, es un cambio
                cambia = True
            else:
                # Comparar valores limpios
                cambia = val_a_limpio != val_b_limpio
                
            resumen_desbaste.append({
                "Posición": substd,
                "Componente": comp,
                "Valor A": str(val_a_original) if val_a_original is not None else "-",
                "Valor B": str(val_b_original) if val_b_original is not None else "-",
                "¿Cambia?": "✅ Sí" if cambia else "❌ No"
            })
        
        df_resultado = pd.DataFrame(resumen_desbaste)
        
        # Log para debugging
        if not df_resultado.empty:
            cambios = len(df_resultado[df_resultado["¿Cambia?"] == "✅ Sí"])
            logger.info(f"Comparación desbaste {familia_a} vs {familia_b}: {cambios} cambios de {len(df_resultado)} componentes")
        
        return df_resultado
        
    except Exception as e:
        logger.error(f"Error en comparar_desbaste: {str(e)}")
        return pd.DataFrame()

@st.cache_data
def obtener_tiempo_cambio(df_tiempo, producto_origen, producto_destino):
    """
    Retorna el tiempo exacto para la dirección Origen → Destino.
    No hace fallback inverso: la dirección del cambio es relevante
    (124 pares asimétricos en BBDD_Tiempo).
    """
    try:
        columnas_requeridas = ["Nombre STD Origen", "Nombre STD Destino", "Minutos Cambio"]
        if not all(col in df_tiempo.columns for col in columnas_requeridas):
            return None
        mask = (
            (df_tiempo["Nombre STD Origen"] == producto_origen) &
            (df_tiempo["Nombre STD Destino"] == producto_destino)
        )
        resultado = df_tiempo.loc[mask, "Minutos Cambio"]
        return int(resultado.iloc[0]) if not resultado.empty else None
    except Exception as e:
        logger.error(f"Error obteniendo tiempo: {str(e)}")
        return None

def agrupar_cambios_consecutivos(df):
    """Agrupa cambios consecutivos del mismo tipo"""
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
    # Plataforma de Cambio de Producto – Laminador Renca
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
        "Comparador Manual", 
        "Análisis de Secuencia", 
        "Resumen Maestranza",
        "Utilaje"
    ])
    
    # PESTAÑA 1: COMPARADOR MANUAL
    with tabs[0]:
        st.subheader("Comparación Manual de Productos")
        mostrar_comparador_manual(df_ddp, df_tiempo, df_desbaste)
    
    # PESTAÑA 2: SECUENCIA DE PROGRAMA
    with tabs[1]:
        st.subheader("Análisis de Secuencia de Programa")
        if "df_prog" in st.session_state:
            mostrar_secuencia_programa(df_ddp, df_tiempo)
        else:
            st.info("📤 Por favor carga primero el archivo de programa.")
    
    # PESTAÑA 3: MAESTRANZA
    with tabs[2]:
        st.subheader("Resumen Técnico para Maestranza")
        if "df_prog" in st.session_state:
            mostrar_resumen_maestranza(df_ddp)
        else:
            st.info("📤 Por favor carga primero el archivo de programa.")

    # PESTAÑA 4: UTILAJE
    with tabs[3]:
        st.subheader("Análisis de Utilaje")
        mostrar_analisis_utilaje(df_ddp)

def mostrar_comparador_manual(df_ddp, df_tiempo, df_desbaste):
    """Muestra el comparador manual de productos."""
    
    # Verificar columnas necesarias
    if "Familia" not in df_ddp.columns or "Producto" not in df_ddp.columns:
        st.error("❌ El archivo DDP debe contener las columnas 'Familia' y 'Producto'")
        return
    
    # Selección de familias con ancho uniforme
    familias = ["(Todos)"] + sorted(df_ddp["Familia"].dropna().unique())
    
    col_f1, col_f2 = st.columns([2, 2])
    
    with col_f1:
        familia_a = st.selectbox("Familia A", familias, key="famA")
    with col_f2:
        familia_b = st.selectbox("Familia B", familias, key="famB")
    
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
    
    # Selección de productos con ancho uniforme
    col_a, col_b = st.columns([2, 2])
    
    with col_a:
        if productos_a:
            producto_a = st.selectbox("Producto A", productos_a, key="A")
            if familia_a == "(Todos)":
                mostrar_info_familia(producto_a, df_ddp, "Producto A")
        else:
            st.warning("No hay productos disponibles para la Familia A")
            return
    
    with col_b:
        if productos_b:
            producto_b = st.selectbox("Producto B", productos_b, key="B")
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
                producto_a, producto_b, familia_a, familia_b
            )

def mostrar_comparacion_productos(df_ddp, df_tiempo, df_desbaste, producto_a, producto_b, familia_a, familia_b):
    try:
        df_a = df_ddp[df_ddp["Producto"] == producto_a]
        df_b = df_ddp[df_ddp["Producto"] == producto_b]
        
        if df_a.empty or df_b.empty:
            st.warning("⚠️ No se encontraron datos para uno o ambos productos.")
            return
        
        # Tiempo de cambio — respetar direccionalidad (A→B puede ≠ B→A)
        tiempo_ab = obtener_tiempo_cambio(df_tiempo, producto_a, producto_b)
        tiempo_ba = obtener_tiempo_cambio(df_tiempo, producto_b, producto_a)

        if tiempo_ab is None and tiempo_ba is None:
            st.warning("⚠️ **Tiempo de cambio:** No registrado para estos productos")
        elif tiempo_ab == tiempo_ba or tiempo_ba is None:
            st.success(f"⏱️ **Tiempo de cambio:** {tiempo_ab} min")
        elif tiempo_ab is None:
            st.success(f"⏱️ **Tiempo de cambio:** {tiempo_ba} min (solo dirección inversa registrada)")
        else:
            # Asimétrico: mostrar ambas direcciones
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.success(f"⏱️ **{producto_a} → {producto_b}:** {tiempo_ab} min")
            with col_t2:
                st.info(f"⏱️ **{producto_b} → {producto_a}:** {tiempo_ba} min")
        
        # Opción de filtro encima de las tablas
        st.markdown("---")
        col_filtro, col_space = st.columns([1, 3])
        with col_filtro:
            mostrar_solo_cambios = st.checkbox("Solo mostrar cambios", value=True, key="filtro_tablas")
        
        # Comparación técnica (DDP)
        st.markdown("### Análisis Técnico")
        
        columnas_ddp = [col for col in df_a.columns if col not in ["STD", "Producto", "Familia"]]
        
        if columnas_ddp:
            with st.spinner("Analizando diferencias técnicas..."):
                resumen_ddp = comparar_productos(df_a, df_b, columnas_ddp)
            
            if not resumen_ddp.empty:
                mostrar_metricas_resumen(resumen_ddp)
                
                if mostrar_solo_cambios:
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
        st.markdown("### Análisis de Diagrama Desbaste")
        
        # Obtener las familias de los productos seleccionados
        familia_real_a = df_a["Familia"].iloc[0] if not df_a.empty and "Familia" in df_a.columns else familia_a
        familia_real_b = df_b["Familia"].iloc[0] if not df_b.empty and "Familia" in df_b.columns else familia_b
        
        # Log para debugging
        logger.info(f"Comparando desbaste: Producto A '{producto_a}' (Familia {familia_real_a}) vs Producto B '{producto_b}' (Familia {familia_real_b})")
        
        with st.spinner("Analizando diagrama de desbaste..."):
            df_desbaste_cmp = comparar_desbaste(df_desbaste, familia_real_a, familia_real_b)
        
        if not df_desbaste_cmp.empty:
            mostrar_metricas_resumen(df_desbaste_cmp)
            
            if mostrar_solo_cambios:
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
        
        # ===============================
        # NUEVO RESUMEN: Cambios por Componente
        # ===============================
        st.markdown("---")
        st.markdown("### Resumen")

        resumen_total = pd.DataFrame()

        if not resumen_ddp.empty:
            resumen_total = pd.concat([resumen_total, resumen_ddp], ignore_index=True)
        if not df_desbaste_cmp.empty:
            resumen_total = pd.concat([resumen_total, df_desbaste_cmp], ignore_index=True)

        if not resumen_total.empty and "¿Cambia?" in resumen_total.columns:
            resumen_componentes = (
                resumen_total[resumen_total["¿Cambia?"] == "✅ Sí"]
                .groupby("Componente")
                .size()
                .reset_index(name="Cantidad de Cambios")
                .sort_values("Cantidad de Cambios", ascending=False)
            )

            if not resumen_componentes.empty:
                st.dataframe(resumen_componentes, use_container_width=True, hide_index=True)
            else:
                st.success("✅ No se registraron cambios en ningún componente.")
        else:
            st.info("ℹ️ No se encontraron diferencias para construir el resumen de componentes.")

            
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
        st.markdown("### Detalle de Cambios en Secuencia")
        
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
                
                titulo = f"{tiempo_color} **Cambio #{secuencia}** | {origen} → {destino} | ⏱️ {tiempo_mostrar} | {cambios_canal} cambios canal"
                
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

def _exportar_maestranza_xlsx(df_resumen, df_frecuencia, df_prog_completo):
    """
    Genera el Excel de Maestranza con Table style (TableStyleLight15),
    columna Nota en Frecuencia_Cilindros, y nombre de columna Toneladas.
    Retorna un BytesIO listo para st.download_button.
    """
    import openpyxl
    from openpyxl import Workbook
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.utils.dataframe import dataframe_to_rows
    from openpyxl.utils import get_column_letter

    def _escribir_tabla(ws, df, table_name, table_style="TableStyleLight15"):
        """Escribe df en ws como Excel Table con estilo."""
        for r in dataframe_to_rows(df, index=False, header=True):
            ws.append(r)
        n_rows = len(df) + 1  # +1 header
        n_cols = len(df.columns)
        ref = f"A1:{get_column_letter(n_cols)}{n_rows}"
        tab = Table(displayName=table_name, ref=ref)
        style = TableStyleInfo(
            name=table_style,
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False
        )
        tab.tableStyleInfo = style
        ws.add_table(tab)
        # Autofit columnas (estimado por contenido)
        for col_cells in ws.columns:
            max_len = max(
                (len(str(c.value)) if c.value is not None else 0) for c in col_cells
            )
            ws.column_dimensions[get_column_letter(col_cells[0].column)].width = min(max_len + 4, 40)

    wb = Workbook()

    # --- Hoja 1: Resumen_Maestranza ---
    ws1 = wb.active
    ws1.title = "Resumen_Maestranza"
    _escribir_tabla(ws1, df_resumen, "Tabla1")

    # --- Hoja 2: Frecuencia_Cilindros ---
    if not df_frecuencia.empty:
        ws2 = wb.create_sheet("Frecuencia_Cilindros")
        # Insertar columna Nota vacía en posición 2 (después de Código Canal)
        df_frec_export = df_frecuencia.copy().rename(columns={"Toneladas": "Toneladas"})
        df_frec_export.insert(1, "Nota", None)
        _escribir_tabla(ws2, df_frec_export, "Tabla2")

    # --- Hoja 3: Programa_Completo ---
    ws3 = wb.create_sheet("Programa_Completo")
    for r in dataframe_to_rows(df_prog_completo, index=False, header=True):
        ws3.append(r)
    # Sin Table style en programa (igual al archivo deseado)
    for col_cells in ws3.columns:
        max_len = max(
            (len(str(c.value)) if c.value is not None else 0) for c in col_cells
        )
        ws3.column_dimensions[get_column_letter(col_cells[0].column)].width = min(max_len + 4, 50)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def mostrar_resumen_maestranza(df_ddp):
    """Muestra el resumen técnico para maestranza con análisis de cilindros."""
    
    try:
        df_prog = st.session_state.df_prog.copy()
        
        with st.spinner("Generando resumen para maestranza..."):
            # Detectar bloques consecutivos del mismo producto
            df_prog["Grupo"] = (df_prog["Nombre STD"] != df_prog["Nombre STD"].shift()).cumsum()

            # Verificar que existe la columna PROGR
            if "PROGR" not in df_prog.columns:
                st.error("❌ El archivo de programa debe contener la columna 'PROGR' para calcular toneladas")
                return

            # --- AUDITORÍA 1: filas con PROGR nulo ---
            filas_sin_progr = df_prog[df_prog["PROGR"].isna()]
            productos_sin_progr = filas_sin_progr["Nombre STD"].dropna().unique().tolist()

            # Agrupar y sumar toneladas (excluir PROGR nulo para evitar sum→0)
            df_programa = (
                df_prog.dropna(subset=["PROGR"])
                .groupby(["Grupo", "Nombre STD"], as_index=False)
                .agg({"PROGR": "sum"})
                .rename(columns={"PROGR": "Toneladas"})
            )
            df_programa = df_programa[df_programa["Toneladas"] > 0].reset_index(drop=True)
            df_programa["Toneladas"] = df_programa["Toneladas"].astype(int)

            # Productos con PROGR nulo que NO aparecen con tonelaje real en ningún otro bloque
            productos_en_programa = set(df_programa["Nombre STD"].unique())
            productos_solo_nulos = [p for p in productos_sin_progr if p not in productos_en_programa]

            # Seleccionar primeras ocurrencias por Producto y STD para posiciones específicas
            posiciones_deseadas = ["M1", "M2", "M3", "M4", "A1", "A2", "A3", "A4", "A5", "A6"]

            # Verificar que tenemos las columnas necesarias
            if "STD" in df_ddp.columns and "Código Canal" in df_ddp.columns:
                df_canal_unico = (
                    df_ddp[df_ddp["STD"].isin(posiciones_deseadas)]
                    .dropna(subset=["Código Canal"])
                    .sort_values(["Producto", "STD"])
                    .drop_duplicates(subset=["Producto", "STD"], keep="first")
                )

                if not df_canal_unico.empty:
                    df_canal_pivot = df_canal_unico.pivot(
                        index="Producto",
                        columns="STD",
                        values="Código Canal"
                    ).reset_index()
                    df_canal_pivot.columns.name = None

                    # --- AUDITORÍA 2: productos del programa sin match en DDP ---
                    productos_en_ddp = set(df_canal_pivot["Producto"].unique())
                    productos_sin_ddp = [
                        p for p in df_programa["Nombre STD"].unique()
                        if p not in productos_en_ddp
                    ]

                    df_resumen = df_programa.merge(
                        df_canal_pivot,
                        left_on="Nombre STD",
                        right_on="Producto",
                        how="left"
                    ).drop(columns=["Producto"], errors='ignore')

                    # --- AUDITORÍA 3: posiciones faltantes por producto ---
                    posiciones_presentes = [p for p in posiciones_deseadas if p in df_resumen.columns]
                    audit_posiciones = []
                    for _, row in df_resumen.iterrows():
                        faltantes = [
                            pos for pos in posiciones_presentes
                            if pd.isna(row.get(pos))
                        ]
                        if faltantes:
                            audit_posiciones.append({
                                "Producto": row["Nombre STD"],
                                "Posiciones sin datos": ", ".join(faltantes)
                            })

                    columnas_orden = ["Nombre STD", "Toneladas"] + posiciones_deseadas
                    df_resumen = df_resumen[[col for col in columnas_orden if col in df_resumen.columns]]
                else:
                    df_resumen = df_programa[["Nombre STD", "Toneladas"]]
                    productos_sin_ddp = list(df_programa["Nombre STD"].unique())
                    audit_posiciones = []
            else:
                df_resumen = df_programa[["Nombre STD", "Toneladas"]]
                productos_sin_ddp = list(df_programa["Nombre STD"].unique())
                audit_posiciones = []
                st.warning("⚠️ No se encontraron columnas 'STD' o 'Código Canal' para análisis detallado")
        
        # Mostrar métricas generales
        try:
            total_toneladas = df_resumen["Toneladas"].sum()
            productos_unicos = df_resumen["Nombre STD"].nunique()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Toneladas", f"{total_toneladas:,.0f}")
            with col2:
                st.metric("Productos Únicos", productos_unicos)
            with col3:
                bloques_consecutivos = len(df_resumen)
                st.metric("Bloques Consecutivos", bloques_consecutivos)
        except Exception as e:
            logger.error(f"Error calculando métricas maestranza: {str(e)}")
        
        # -----------------------------------------------
        # AUDITORÍAS — visibles antes de la tabla
        # -----------------------------------------------
        hay_alertas = False

        if productos_solo_nulos:
            hay_alertas = True
            with st.expander(f"⚠️ {len(productos_solo_nulos)} producto(s) excluidos por PROGR vacío", expanded=True):
                st.warning(
                    "Estos productos aparecen en el programa solo con PROGR=vacío "
                    "y fueron excluidos del resumen. Si deben tener tonelaje, corrige el programa."
                )
                st.dataframe(
                    pd.DataFrame({"Producto excluido (PROGR vacío)": productos_solo_nulos}),
                    use_container_width=True, hide_index=True
                )

        if productos_sin_ddp:
            hay_alertas = True
            with st.expander(f"🔴 {len(productos_sin_ddp)} producto(s) sin datos de cilindros en DDP", expanded=True):
                st.error(
                    "Estos productos están en el programa pero no se encontraron en el "
                    "Consolidado_Laminador. Las columnas M1–A6 quedarán vacías. "
                    "Verifica que el nombre STD coincida exactamente con el DDP."
                )
                st.dataframe(
                    pd.DataFrame({"Producto sin datos en DDP": productos_sin_ddp}),
                    use_container_width=True, hide_index=True
                )

        if audit_posiciones:
            hay_alertas = True
            with st.expander(f"🟡 {len(audit_posiciones)} producto(s) con posiciones sin código de canal", expanded=False):
                st.warning(
                    "Estos productos existen en el DDP pero no tienen Código Canal "
                    "registrado para algunas posiciones. Puede ser intencional (posición no usada) "
                    "o un dato faltante."
                )
                st.dataframe(
                    pd.DataFrame(audit_posiciones),
                    use_container_width=True, hide_index=True
                )

        if not hay_alertas:
            st.success("✅ Sin inconsistencias detectadas — todos los productos tienen datos completos.")

        # Tabla principal
        st.markdown("### Resumen Detallado por Producto")
        st.dataframe(df_resumen, use_container_width=True)
        
        # ===============================================
        # SECCIÓN DE FRECUENCIA DE CILINDROS
        # ===============================================
        
        st.markdown("### Frecuencia de Cilindros en Programa")
        
        try:
            # Crear una lista con todos los códigos de canal para cada producto en el programa
            codigos_programa = []
            productos_sin_canal = []  # AUDITORÍA 4: productos sin ningún Código Canal

            for _, row in df_programa.iterrows():
                producto = row["Nombre STD"]
                toneladas = row["Toneladas"]

                if "Código Canal" in df_ddp.columns:
                    codigos_producto = df_ddp[df_ddp["Producto"] == producto]["Código Canal"].dropna().unique()

                    if len(codigos_producto) == 0:
                        productos_sin_canal.append(producto)
                    else:
                        for codigo in codigos_producto:
                            codigos_programa.append({
                                "Nombre STD": producto,
                                "Código Canal": codigo,
                                "Toneladas": toneladas
                            })
            
            # Convertir a DataFrame
            df_codigos_programa = pd.DataFrame(codigos_programa)
            
            # Calcular frecuencia si hay datos
            if not df_codigos_programa.empty:
                frecuencia_en_programa = (
                    df_codigos_programa
                    .groupby("Código Canal", dropna=True)
                    .agg(
                        Frecuencia=("Nombre STD", "count"),
                        Toneladas=("Toneladas", "sum")
                    )
                    .reset_index()
                    .sort_values("Toneladas", ascending=False)
                )
                
                # Mostrar tabla de frecuencias
                st.dataframe(frecuencia_en_programa.set_index("Código Canal"), use_container_width=True)
                
                # Mostrar métricas de cilindros
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Cilindros Únicos", len(frecuencia_en_programa))
                with col2:
                    cilindro_mas_usado = frecuencia_en_programa.iloc[0]["Código Canal"] if not frecuencia_en_programa.empty else "N/A"
                    st.metric("Cilindro Más Usado", cilindro_mas_usado)
                with col3:
                    max_frecuencia = frecuencia_en_programa.iloc[0]["Frecuencia"] if not frecuencia_en_programa.empty else 0
                    st.metric("Frecuencia Máxima", max_frecuencia)

            else:
                st.warning("No se encontraron códigos de canal para los productos en el programa.")
                frecuencia_en_programa = pd.DataFrame()

            # AUDITORÍA 4: productos sin ningún Código Canal registrado
            if productos_sin_canal:
                with st.expander(f"🔴 {len(set(productos_sin_canal))} producto(s) sin Código Canal en DDP", expanded=True):
                    st.error(
                        "Estos productos no tienen ningún Código Canal registrado en el "
                        "Consolidado_Laminador. No aparecerán en la frecuencia de cilindros. "
                        "Verifica el DDP o el nombre STD."
                    )
                    st.dataframe(
                        pd.DataFrame({"Producto sin Código Canal": sorted(set(productos_sin_canal))}),
                        use_container_width=True, hide_index=True
                    )
                
        except Exception as e:
            logger.error(f"Error calculando frecuencia de cilindros: {str(e)}")
            st.error("Error calculando frecuencia de cilindros")
            frecuencia_en_programa = pd.DataFrame()
        
        # ===============================================
        # EXPORTACIÓN
        # ===============================================

        st.markdown("---")
        st.markdown("### 📥 Exportar Datos")

        col1, col2 = st.columns(2)

        with col1:
            try:
                buffer_completo = _exportar_maestranza_xlsx(
                    df_resumen, frecuencia_en_programa, st.session_state.df_prog
                )
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                st.download_button(
                    label="Descargar Resumen Técnico Completo",
                    data=buffer_completo,
                    file_name=f"Resumen_Maestranza_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Incluye resumen maestranza, frecuencia de cilindros y programa completo"
                )
            except Exception as e:
                logger.error(f"Error creando Excel: {str(e)}")
                st.error("Error generando archivo Excel")
        
    except Exception as e:
        st.error(f"Error generando resumen maestranza: {str(e)}")
        logger.error(f"Error en mostrar_resumen_maestranza: {str(e)}")

def mostrar_analisis_utilaje(df_ddp):
    """Muestra el análisis detallado de utilaje."""
    
    try:
        # Verificar que tenemos los datos necesarios
        if df_ddp.empty:
            st.warning("⚠️ No hay datos de productos disponibles para análisis de utilaje.")
            return
        
        # Definir componentes de utilaje
        componentes_utilaje = [
            "Caja Guía Entrada",
            "Caja Guía Salida", 
            "Embudo Entrada",
            "Embudo Salida",
            "Código Polín Entrada",
            "Código Polín Salida",
            "Estabilización Entrada", 
            "Estabilización Salida",
            "Rodamiento Entrada",
            "Rodamiento Salida",
            "Semiguía Entrada",
            "Semiguía Salida",
            "Raspador Entrada",
            "Raspador Salida"
        ]
        
        # Verificar qué componentes existen en los datos
        componentes_disponibles = [comp for comp in componentes_utilaje if comp in df_ddp.columns]
        componentes_faltantes = [comp for comp in componentes_utilaje if comp not in df_ddp.columns]
        
        # Mostrar información de disponibilidad
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Productos", len(df_ddp["Producto"].unique()) if "Producto" in df_ddp.columns else 0)
        with col2:
            st.metric("Componentes Disponibles", len(componentes_disponibles))
        with col3:
            st.metric("Componentes Faltantes", len(componentes_faltantes))
        
        if componentes_faltantes:
            with st.expander("⚠️ Componentes no encontrados en los datos"):
                for comp in componentes_faltantes:
                    st.write(f"• {comp}")
        
        if not componentes_disponibles:
            st.error("❌ No se encontraron componentes de utilaje en los datos.")
            return
        
        # Crear pestañas para diferentes análisis
        sub_tabs = st.tabs([
            "Análisis según Programa",
            "Análisis Individual", 
            "Comparación Manual",
            "Estadísticas Generales"
        ])
        
        # PESTAÑA 1: ANÁLISIS SEGÚN PROGRAMA
        with sub_tabs[0]:
            if "df_prog" in st.session_state:
                mostrar_utilaje_programa(df_ddp, componentes_disponibles)
            else:
                st.info("📤 Por favor carga primero el archivo de programa para ver el análisis de utilaje según la secuencia de producción.")
        
        # PESTAÑA 2: ANÁLISIS INDIVIDUAL
        with sub_tabs[1]:
            st.markdown("### 🔍 Análisis Individual de Producto")
            
            productos_disponibles = sorted(df_ddp["Producto"].dropna().unique()) if "Producto" in df_ddp.columns else []
            
            if productos_disponibles:
                col_prod, col_filtro = st.columns([2, 1])
                
                with col_prod:
                    producto_seleccionado = st.selectbox(
                        "Selecciona un producto para ver su utilaje:",
                        productos_disponibles,
                        key="producto_utilaje_individual"
                    )
                
                with col_filtro:
                    st.markdown("**Opciones:**")
                    mostrar_solo_definidos = st.checkbox("Solo mostrar componentes definidos", value=True, key="filtro_individual")
                
                if producto_seleccionado:
                    mostrar_utilaje_producto(df_ddp, producto_seleccionado, componentes_disponibles, mostrar_solo_definidos)
        
        # PESTAÑA 3: COMPARACIÓN MANUAL
        with sub_tabs[2]:
            st.markdown("### Comparación de Utilaje entre Productos")
            
            productos_disponibles = sorted(df_ddp["Producto"].dropna().unique()) if "Producto" in df_ddp.columns else []
            
            if len(productos_disponibles) >= 2:
                col_a, col_b, col_opciones = st.columns([2, 2, 1])
                
                with col_a:
                    producto_a_util = st.selectbox(
                        "Producto A:",
                        productos_disponibles,
                        key="producto_a_utilaje_comp"
                    )
                
                with col_b:
                    producto_b_util = st.selectbox(
                        "Producto B:",
                        productos_disponibles,
                        index=1 if len(productos_disponibles) > 1 else 0,
                        key="producto_b_utilaje_comp"
                    )
                
                with col_opciones:
                    st.markdown("**Opciones:**")
                    solo_diferencias = st.checkbox("Solo diferencias", value=True, key="solo_dif_utilaje_comp")
                
                if producto_a_util != producto_b_util:
                    comparar_utilaje_productos(df_ddp, producto_a_util, producto_b_util, componentes_disponibles, solo_diferencias)
                else:
                    st.warning("⚠️ Selecciona productos diferentes para compararlos.")
            else:
                st.warning("⚠️ Se necesitan al menos 2 productos para comparar.")
        
        # PESTAÑA 4: ESTADÍSTICAS GENERALES
        with sub_tabs[3]:
            st.markdown("### Análisis General de Utilaje")
            mostrar_estadisticas_utilaje(df_ddp, componentes_disponibles)
        
    except Exception as e:
        st.error(f"Error en análisis de utilaje: {str(e)}")
        logger.error(f"Error en mostrar_analisis_utilaje: {str(e)}")

def mostrar_utilaje_programa(df_ddp, componentes_disponibles):
    """Muestra el análisis de utilaje basado en el programa de producción."""
    
    try:
        df_prog = st.session_state.df_prog.copy()
        
        st.markdown("### Análisis de Utilaje según Secuencia de Producción")
        
        with st.spinner("Analizando necesidades de utilaje según programa..."):
            # Detectar bloques consecutivos del mismo producto
            df_prog["Grupo"] = (df_prog["Nombre STD"] != df_prog["Nombre STD"].shift()).cumsum()
            
            # Verificar que existe la columna PROGR para toneladas
            if "PROGR" not in df_prog.columns:
                st.error("❌ El archivo de programa debe contener la columna 'PROGR' para calcular toneladas")
                return
            
            # Agrupar y sumar toneladas
            df_programa = (
                df_prog.dropna(subset=["PROGR"])
                .groupby(["Grupo", "Nombre STD"], as_index=False)
                .agg({"PROGR": "sum"})
                .rename(columns={"PROGR": "Toneladas"})
            )
            df_programa = df_programa[df_programa["Toneladas"] > 0].reset_index(drop=True)
            df_programa["Toneladas"] = df_programa["Toneladas"].astype(int)
            
            # Análisis de cambios de utilaje en la secuencia
            cambios_utilaje = []
            
            for i in range(len(df_programa) - 1):
                producto_actual = df_programa.loc[i, "Nombre STD"]
                producto_siguiente = df_programa.loc[i + 1, "Nombre STD"]
                
                # Skip si es el mismo producto
                if producto_actual == producto_siguiente:
                    continue
                
                # Obtener datos de utilaje para ambos productos
                datos_actual = df_ddp[df_ddp["Producto"] == producto_actual]
                datos_siguiente = df_ddp[df_ddp["Producto"] == producto_siguiente]
                
                if datos_actual.empty or datos_siguiente.empty:
                    continue
                
                # Analizar cambios en cada componente
                componentes_cambian = []
                for comp in componentes_disponibles:
                    val_actual = datos_actual[comp].dropna().unique()
                    val_siguiente = datos_siguiente[comp].dropna().unique()
                    
                    # Determinar si hay cambio
                    if len(val_actual) > 0 and len(val_siguiente) > 0:
                        if set(val_actual) != set(val_siguiente):
                            componentes_cambian.append(comp)
                
                if componentes_cambian:
                    cambios_utilaje.append({
                        "Secuencia": i + 1,
                        "Producto Origen": producto_actual,
                        "Producto Destino": producto_siguiente,
                        "Componentes que Cambian": len(componentes_cambian),
                        "Detalle Componentes": ", ".join(componentes_cambian[:3]) + ("..." if len(componentes_cambian) > 3 else "")
                    })
        
        # Mostrar métricas generales
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Productos", len(df_programa))
        with col2:
            st.metric("Cambios de Producto", len(cambios_utilaje))
        with col3:
            cambios_con_utilaje = len([c for c in cambios_utilaje if c["Componentes que Cambian"] > 0])
            st.metric("Cambios con Utilaje", cambios_con_utilaje)
        with col4:
            total_toneladas = df_programa["Toneladas"].sum()
            st.metric("Total Toneladas", f"{total_toneladas:,.0f}")
        
        # Mostrar tabla de cambios de utilaje
        if cambios_utilaje:
            st.markdown("---")
            st.markdown("#### Cambios de Utilaje en la Secuencia")
            
            df_cambios = pd.DataFrame(cambios_utilaje)
            
            # Aplicar color según cantidad de cambios
            def colorear_cambios(row):
                cambios = row["Componentes que Cambian"]
                if cambios >= 10:
                    return ['background-color: #ffcdd2'] * len(row)  # Rojo claro
                elif cambios >= 5:
                    return ['background-color: #fff9c4'] * len(row)  # Amarillo claro
                else:
                    return ['background-color: #c8e6c9'] * len(row)  # Verde claro
            
            st.dataframe(
                df_cambios.style.apply(colorear_cambios, axis=1),
                use_container_width=True,
                hide_index=True
            )
            
            # Leyenda de colores
            with st.expander("📋 Leyenda de colores"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown("🟢 **Verde:** 1-4 componentes cambian")
                with col2:
                    st.markdown("🟡 **Amarillo:** 5-9 componentes cambian")
                with col3:
                    st.markdown("🔴 **Rojo:** 10+ componentes cambian")
        
        # Análisis de frecuencia de utilajes en el programa
        st.markdown("---")
        st.markdown("#### Frecuencia de Utilajes en Programa")
        
        # Recopilar todos los utilajes usados en el programa
        utilajes_programa = {}
        
        for componente in componentes_disponibles:
            utilajes_programa[componente] = []
            
            for _, row in df_programa.iterrows():
                producto = row["Nombre STD"]
                toneladas = row["Toneladas"]
                
                # Obtener valores de utilaje para este producto
                datos_producto = df_ddp[df_ddp["Producto"] == producto]
                if not datos_producto.empty:
                    valores = datos_producto[componente].dropna().unique()
                    for valor in valores:
                        utilajes_programa[componente].append({
                            "Valor": valor,
                            "Producto": producto,
                            "Toneladas": toneladas
                        })
        
        # Selector de componente para análisis detallado
        componente_analizar = st.selectbox(
            "Selecciona componente para ver frecuencia:",
            componentes_disponibles,
            key="comp_frecuencia_programa"
        )
        
        if componente_analizar and utilajes_programa[componente_analizar]:
            df_comp = pd.DataFrame(utilajes_programa[componente_analizar])
            
            # Agrupar por valor y sumar toneladas
            frecuencia_comp = (
                df_comp
                .groupby("Valor")
                .agg(
                    Frecuencia=("Producto", "count"),
                    Toneladas_Total=("Toneladas", "sum"),
                    Productos=("Producto", lambda x: ", ".join(x.unique()[:3]) + ("..." if len(x.unique()) > 3 else ""))
                )
                .reset_index()
                .sort_values("Toneladas_Total", ascending=False)
            )
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.dataframe(frecuencia_comp, use_container_width=True, hide_index=True)
            
            with col2:
                # Métricas del componente
                st.metric("Valores Únicos", len(frecuencia_comp))
                if not frecuencia_comp.empty:
                    valor_mas_usado = frecuencia_comp.iloc[0]["Valor"]
                    st.metric("Más Usado", valor_mas_usado)
        
        # Resumen de necesidades de utilaje
        st.markdown("---")
        st.markdown("#### Resumen de Necesidades de Utilaje")
        
        # Crear tabla resumen con todos los productos y sus utilajes
        resumen_utilaje = []
        
        for _, row in df_programa.iterrows():
            producto = row["Nombre STD"]
            toneladas = row["Toneladas"]
            
            datos_producto = df_ddp[df_ddp["Producto"] == producto]
            if not datos_producto.empty:
                fila_resumen = {
                    "Producto": producto,
                    "Toneladas": toneladas
                }
                
                # Agregar valores de cada componente
                for comp in componentes_disponibles[:6]:  # Mostrar solo los primeros 6 para no hacer la tabla muy ancha
                    valores = datos_producto[comp].dropna().unique()
                    fila_resumen[comp] = ", ".join([str(v) for v in valores]) if len(valores) > 0 else "-"
                
                resumen_utilaje.append(fila_resumen)
        
        if resumen_utilaje:
            df_resumen_utilaje = pd.DataFrame(resumen_utilaje)
            st.dataframe(df_resumen_utilaje, use_container_width=True, hide_index=True)
        
        # Botón de exportación
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("📥 Exportar Análisis de Utilaje", key="export_utilaje_programa"):
                exportar_utilaje_programa(df_programa, df_ddp, componentes_disponibles, cambios_utilaje)
        
    except Exception as e:
        st.error(f"Error en análisis de utilaje según programa: {str(e)}")
        logger.error(f"Error en mostrar_utilaje_programa: {str(e)}")

def exportar_utilaje_programa(df_programa, df_ddp, componentes_disponibles, cambios_utilaje):
    """Exporta el análisis de utilaje según programa."""
    
    try:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            # Hoja 1: Resumen del programa con utilajes principales
            resumen_export = []
            for _, row in df_programa.iterrows():
                producto = row["Nombre STD"]
                toneladas = row["Toneladas"]
                
                datos_producto = df_ddp[df_ddp["Producto"] == producto]
                if not datos_producto.empty:
                    fila = {"Producto": producto, "Toneladas": toneladas}
                    
                    for comp in componentes_disponibles:
                        valores = datos_producto[comp].dropna().unique()
                        fila[comp] = ", ".join([str(v) for v in valores]) if len(valores) > 0 else ""
                    
                    resumen_export.append(fila)
            
            if resumen_export:
                df_resumen = pd.DataFrame(resumen_export)
                df_resumen.to_excel(writer, sheet_name="Resumen_Utilaje_Programa", index=False)
            
            # Hoja 2: Cambios de utilaje
            if cambios_utilaje:
                df_cambios = pd.DataFrame(cambios_utilaje)
                df_cambios.to_excel(writer, sheet_name="Cambios_Utilaje", index=False)
            
            # Hoja 3: Frecuencia de cada componente
            for i, comp in enumerate(componentes_disponibles[:10]):  # Limitar a 10 componentes
                frecuencias = {}
                
                for _, row in df_programa.iterrows():
                    producto = row["Nombre STD"]
                    toneladas = row["Toneladas"]
                    
                    datos_producto = df_ddp[df_ddp["Producto"] == producto]
                    if not datos_producto.empty:
                        valores = datos_producto[comp].dropna().unique()
                        for valor in valores:
                            if valor not in frecuencias:
                                frecuencias[valor] = {"Frecuencia": 0, "Toneladas": 0, "Productos": []}
                            frecuencias[valor]["Frecuencia"] += 1
                            frecuencias[valor]["Toneladas"] += toneladas
                            frecuencias[valor]["Productos"].append(producto)
                
                if frecuencias:
                    df_freq = pd.DataFrame([
                        {
                            "Valor": k,
                            "Frecuencia": v["Frecuencia"],
                            "Toneladas": v["Toneladas"],
                            "Productos": ", ".join(v["Productos"][:5]) + ("..." if len(v["Productos"]) > 5 else "")
                        }
                        for k, v in frecuencias.items()
                    ]).sort_values("Toneladas", ascending=False)
                    
                    sheet_name = f"Frec_{comp[:20]}" if i < 9 else "Frec_Otros"  # Limitar nombre de hoja
                    df_freq.to_excel(writer, sheet_name=sheet_name, index=False)
            
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
        filename = f"Analisis_Utilaje_Programa_{timestamp}.xlsx"
        
        st.download_button(
            label="Descargar Análisis Completo",
            data=buffer,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Incluye resumen de utilaje por programa, cambios y frecuencias"
        )
        
        st.success("✅ Análisis exportado exitosamente")
        
    except Exception as e:
        st.error(f"Error exportando análisis: {str(e)}")
        logger.error(f"Error en exportar_utilaje_programa: {str(e)}")

def mostrar_utilaje_producto(df_ddp, producto, componentes_disponibles, mostrar_solo_definidos=True):
    """Muestra el detalle de utilaje para un producto específico."""
    
    try:
        # Filtrar datos del producto
        datos_producto = df_ddp[df_ddp["Producto"] == producto]
        
        if datos_producto.empty:
            st.warning(f"⚠️ No se encontraron datos para el producto {producto}")
            return
        
        # Crear tabla de utilaje
        utilaje_data = []
        
        for componente in componentes_disponibles:
            valores_componente = datos_producto[componente].dropna().unique()
            
            # Si solo mostrar definidos y no hay valores, saltar
            if mostrar_solo_definidos and (len(valores_componente) == 0 or (len(valores_componente) == 1 and pd.isna(valores_componente[0]))):
                continue
            
            # Procesar valores
            if len(valores_componente) == 0:
                valor_mostrar = "No definido"
            elif len(valores_componente) == 1:
                valor_mostrar = str(valores_componente[0]) if not pd.isna(valores_componente[0]) else "No definido"
            else:
                valor_mostrar = ", ".join([str(v) for v in valores_componente if not pd.isna(v)])
            
            utilaje_data.append({
                "Componente": componente,
                "Valor": valor_mostrar,
                "Múltiples Valores": "Sí" if len(valores_componente) > 1 else "No"
            })
        
        if utilaje_data:
            df_utilaje = pd.DataFrame(utilaje_data)
            
            # Aplicar estilo condicional
            def resaltar_multiples(row):
                if row["Múltiples Valores"] == "Sí":
                    return ['background-color: #fff3cd'] * len(row)
                elif row["Valor"] == "No definido":
                    return ['background-color: #f8d7da'] * len(row)
                else:
                    return ['background-color: #d1edff'] * len(row)
            
            st.dataframe(
                df_utilaje.style.apply(resaltar_multiples, axis=1),
                use_container_width=True,
                hide_index=True
            )
            
            # Mostrar leyenda de colores
            with st.expander("📋 Leyenda de colores"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown("🔵 **Azul:** Valor único definido")
                with col2:
                    st.markdown("🟡 **Amarillo:** Múltiples valores")
                with col3:
                    st.markdown("🔴 **Rojo:** No definido")
        else:
            st.info("ℹ️ No hay componentes de utilaje definidos para este producto (o todos están ocultos por el filtro).")
            
    except Exception as e:
        st.error(f"Error mostrando utilaje del producto: {str(e)}")
        logger.error(f"Error en mostrar_utilaje_producto: {str(e)}")

def comparar_utilaje_productos(df_ddp, producto_a, producto_b, componentes_disponibles, solo_diferencias=True):
    """Compara el utilaje entre dos productos."""
    
    try:
        # Obtener datos de ambos productos
        datos_a = df_ddp[df_ddp["Producto"] == producto_a]
        datos_b = df_ddp[df_ddp["Producto"] == producto_b]
        
        if datos_a.empty or datos_b.empty:
            st.warning("⚠️ No se encontraron datos para uno o ambos productos.")
            return
        
        # Crear comparación
        comparacion_data = []
        
        for componente in componentes_disponibles:
            # Obtener valores únicos de cada producto
            valores_a = datos_a[componente].dropna().unique()
            valores_b = datos_b[componente].dropna().unique()
            
            # Procesar valores para mostrar
            valor_a = ", ".join([str(v) for v in valores_a]) if len(valores_a) > 0 else "No definido"
            valor_b = ", ".join([str(v) for v in valores_b]) if len(valores_b) > 0 else "No definido"
            
            # Determinar si hay diferencia
            diferentes = set(valores_a) != set(valores_b)
            
            # Si solo mostrar diferencias y son iguales, saltar
            if solo_diferencias and not diferentes:
                continue
            
            comparacion_data.append({
                "Componente": componente,
                f"Producto A ({producto_a})": valor_a,
                f"Producto B ({producto_b})": valor_b,
                "¿Diferente?": "✅ Sí" if diferentes else "❌ No"
            })
        
        if comparacion_data:
            df_comparacion = pd.DataFrame(comparacion_data)
            
            # Mostrar métricas de comparación
            total_componentes = len(df_comparacion)
            componentes_diferentes = len(df_comparacion[df_comparacion["¿Diferente?"] == "✅ Sí"])
            porcentaje_diferencias = (componentes_diferentes / total_componentes * 100) if total_componentes > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Componentes Analizados", total_componentes)
            with col2:
                st.metric("Componentes Diferentes", componentes_diferentes)
            with col3:
                st.metric("% Diferencias", f"{porcentaje_diferencias:.1f}%")
            
            # Aplicar estilo a la tabla
            def resaltar_diferencias(row):
                if row["¿Diferente?"] == "✅ Sí":
                    return ['background-color: #ffebee'] * len(row)
                else:
                    return ['background-color: #f1f8e9'] * len(row)
            
            st.dataframe(
                df_comparacion.style.apply(resaltar_diferencias, axis=1),
                use_container_width=True,
                hide_index=True
            )
            
        else:
            if solo_diferencias:
                st.success("✅ **¡No hay diferencias en el utilaje entre estos productos!**")
            else:
                st.info("ℹ️ No se encontraron componentes de utilaje para comparar.")
                
    except Exception as e:
        st.error(f"Error comparando utilaje: {str(e)}")
        logger.error(f"Error en comparar_utilaje_productos: {str(e)}")

def mostrar_estadisticas_utilaje(df_ddp, componentes_disponibles):
    """Muestra estadísticas generales del utilaje."""
    
    try:
        # Análisis de frecuencias por componente
        st.markdown("####Frecuencia de Valores por Componente")
        
        # Selector de componente para análisis detallado
        componente_analisis = st.selectbox(
            "Selecciona componente para análisis detallado:",
            componentes_disponibles,
            key="componente_analisis"
        )
        
        if componente_analisis:
            col_analisis, col_exportar = st.columns([3, 1])
            
            with col_analisis:
                # Obtener frecuencias del componente seleccionado
                valores_componente = df_ddp[componente_analisis].dropna()
                
                if not valores_componente.empty:
                    frecuencias = valores_componente.value_counts().reset_index()
                    frecuencias.columns = ["Valor", "Frecuencia"]
                    frecuencias["Porcentaje"] = (frecuencias["Frecuencia"] / frecuencias["Frecuencia"].sum() * 100).round(1)
                    
                    st.dataframe(frecuencias, use_container_width=True, hide_index=True)
                    
                    # Mostrar métricas del componente
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Valores Únicos", len(frecuencias))
                    with col2:
                        st.metric("Productos con Valor", len(valores_componente))
                    with col3:
                        valor_mas_comun = frecuencias.iloc[0]["Valor"] if not frecuencias.empty else "N/A"
                        st.metric("Valor Más Común", valor_mas_comun)
                else:
                    st.info(f"ℹ️ No hay valores definidos para {componente_analisis}")
            
            with col_exportar:
                # Botón para exportar análisis completo
                if st.button("📥 Exportar Análisis"):
                    exportar_analisis_utilaje(df_ddp, componentes_disponibles)
        
        # Resumen general de todos los componentes
        st.markdown("---")
        st.markdown("#### 📋 Resumen General de Componentes")
        
        resumen_general = []
        for componente in componentes_disponibles:
            valores = df_ddp[componente].dropna()
            valores_unicos = len(valores.unique()) if not valores.empty else 0
            productos_con_valor = len(valores) if not valores.empty else 0
            total_productos = len(df_ddp)
            cobertura = (productos_con_valor / total_productos * 100) if total_productos > 0 else 0
            
            resumen_general.append({
                "Componente": componente,
                "Valores Únicos": valores_unicos,
                "Productos con Valor": productos_con_valor,
                "Cobertura (%)": f"{cobertura:.1f}%"
            })
        
        df_resumen = pd.DataFrame(resumen_general)
        
        # Colorear por cobertura
        def colorear_cobertura(row):
            cobertura = float(row["Cobertura (%)"].replace("%", ""))
            if cobertura >= 80:
                return ['background-color: #d1edff'] * len(row)
            elif cobertura >= 50:
                return ['background-color: #fff3cd'] * len(row)
            else:
                return ['background-color: #f8d7da'] * len(row)
        
        st.dataframe(
            df_resumen.style.apply(colorear_cobertura, axis=1),
            use_container_width=True,
            hide_index=True
        )
        
    except Exception as e:
        st.error(f"Error en estadísticas de utilaje: {str(e)}")
        logger.error(f"Error en mostrar_estadisticas_utilaje: {str(e)}")

def exportar_analisis_utilaje(df_ddp, componentes_disponibles):
    """Exporta el análisis completo de utilaje."""
    
    try:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            # Hoja 1: Resumen por componente
            resumen_componentes = []
            for componente in componentes_disponibles:
                valores = df_ddp[componente].dropna()
                frecuencias = valores.value_counts()
                
                for valor, freq in frecuencias.items():
                    resumen_componentes.append({
                        "Componente": componente,
                        "Valor": valor,
                        "Frecuencia": freq
                    })
            
            if resumen_componentes:
                df_resumen_comp = pd.DataFrame(resumen_componentes)
                df_resumen_comp.to_excel(writer, sheet_name="Resumen_Componentes", index=False)
            
            # Hoja 2: Matriz completa de utilaje
            columnas_utilaje = ["Producto"] + componentes_disponibles
            df_utilaje_completo = df_ddp[columnas_utilaje]
            df_utilaje_completo.to_excel(writer, sheet_name="Utilaje_Completo", index=False)
            
            # Hoja 3: Estadísticas generales
            estadisticas = []
            for componente in componentes_disponibles:
                valores = df_ddp[componente].dropna()
                estadisticas.append({
                    "Componente": componente,
                    "Valores_Unicos": len(valores.unique()) if not valores.empty else 0,
                    "Productos_con_Valor": len(valores),
                    "Cobertura_Porcentaje": len(valores) / len(df_ddp) * 100 if len(df_ddp) > 0 else 0
                })
            
            df_estadisticas = pd.DataFrame(estadisticas)
            df_estadisticas.to_excel(writer, sheet_name="Estadisticas", index=False)
        
        buffer.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Analisis_Utilaje_{timestamp}.xlsx"
        
        st.download_button(
            label="Descargar Análisis Completo",
            data=buffer,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Incluye resumen por componentes, matriz completa y estadísticas"
        )
        
        st.success("✅ Análisis exportado exitosamente")
        
    except Exception as e:
        st.error(f"Error exportando análisis: {str(e)}")
        logger.error(f"Error en exportar_analisis_utilaje: {str(e)}")

if __name__ == "__main__":
    main()