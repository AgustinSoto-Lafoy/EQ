import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import time
from datetime import datetime, timedelta
import numpy as np

# =====================================
# CONFIGURACIÓN INICIAL MEJORADA
# =====================================

st.set_page_config(
    page_title="🏭 Laminador - Control de Cambios",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado para mejorar la apariencia
def load_custom_css():
    st.markdown("""
    <style>
    /* Tema industrial */
    .main-header {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .metric-card {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #3b82f6;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
    }
    
    .warning-card {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border-left: 4px solid #f59e0b;
    }
    
    .success-card {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        border-left: 4px solid #10b981;
    }
    
    .danger-card {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        border-left: 4px solid #ef4444;
    }
    
    .comparison-section {
        background: #f8fafc;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border: 1px solid #e2e8f0;
    }
    
    .timeline-item {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border-left: 3px solid #3b82f6;
        margin-bottom: 0.5rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #f1f5f9;
        border-radius: 8px 8px 0 0;
        padding: 0.5rem 1rem;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6;
        color: white;
    }
    
    /* Animaciones */
    .fade-in {
        animation: fadeIn 0.5s ease-in;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .pulse {
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    </style>
    """, unsafe_allow_html=True)

# =====================================
# FUNCIONES DE CARGA CON PROGRESO
# =====================================

@st.cache_data
def cargar_datos():
    """Carga los archivos base de datos con indicador de progreso."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("🔄 Cargando datos del laminador...")
        progress_bar.progress(25)
        ddp = pd.read_excel("data/Consolidado_Laminador.xlsx")
        
        status_text.text("🔄 Cargando base de datos de tiempos...")
        progress_bar.progress(50)
        tiempo = pd.read_excel("data/BBDD_Tiempo.xlsx")
        
        status_text.text("🔄 Cargando diagrama de desbaste...")
        progress_bar.progress(75)
        desbaste = pd.read_excel("data/Diagrama_Desbaste.xlsx")
        
        status_text.text("✅ Datos cargados exitosamente")
        progress_bar.progress(100)
        
        time.sleep(0.5)  # Pausa para mostrar completado
        progress_bar.empty()
        status_text.empty()
        
        return ddp, tiempo, desbaste
        
    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"❌ Error al cargar archivos base: {e}")
        return None, None, None

def cargar_programa_usuario():
    """Maneja la carga del archivo de programa con feedback mejorado."""
    if "df_prog" not in st.session_state:
        st.markdown("### 📤 Cargar Programa de Producción")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            archivo_programa = st.file_uploader(
                "Selecciona el archivo de programa (formato .xlsx)", 
                type=["xlsx"], 
                key="carga_global",
                help="El archivo debe contener la hoja 'TablaCombinada' con los datos del programa"
            )
        
        with col2:
            if archivo_programa is not None:
                st.markdown("**📋 Información del archivo:**")
                st.write(f"📄 Nombre: {archivo_programa.name}")
                st.write(f"📏 Tamaño: {archivo_programa.size} bytes")
        
        if archivo_programa is not None:
            try:
                with st.spinner("🔄 Procesando archivo..."):
                    df_prog = pd.read_excel(archivo_programa, sheet_name="TablaCombinada")
                    st.session_state.df_prog = df_prog.dropna(subset=["Nombre STD"]).reset_index(drop=True)
                
                st.success("✅ Archivo cargado exitosamente")
                st.balloons()  # Animación de celebración
                
                # Mostrar preview de los datos
                with st.expander("👀 Preview de los datos cargados"):
                    st.dataframe(st.session_state.df_prog.head(), use_container_width=True)
                    
            except Exception as e:
                st.error(f"❌ Error al cargar archivo: {e}")
                st.info("💡 Asegúrate de que el archivo tenga la hoja 'TablaCombinada' y la columna 'Nombre STD'")

# =====================================
# FUNCIONES DE ANÁLISIS MEJORADAS
# =====================================

def crear_grafico_tiempo_cambios(df_resumen):
    """Crea un gráfico de barras para tiempos de cambio."""
    fig = go.Figure()
    
    # Filtrar datos válidos
    datos_validos = df_resumen.dropna(subset=['Tiempo estimado'])
    
    if not datos_validos.empty:
        fig.add_trace(go.Bar(
            x=[f"{row['Producto Origen'][:10]}→{row['Producto Destino'][:10]}" for _, row in datos_validos.iterrows()],
            y=datos_validos['Tiempo estimado'],
            marker_color='rgba(59, 130, 246, 0.8)',
            text=datos_validos['Tiempo estimado'],
            textposition='auto',
            name='Tiempo (min)'
        ))
    
    fig.update_layout(
        title="⏱️ Tiempos de Cambio por Secuencia",
        xaxis_title="Cambios de Producto",
        yaxis_title="Tiempo (minutos)",
        template="plotly_white",
        height=400,
        showlegend=False
    )
    
    fig.update_xaxis(tickangle=45)
    return fig

def crear_heatmap_cambios(df_ddp, productos_seleccionados):
    """Crea un heatmap de intensidad de cambios entre productos."""
    if len(productos_seleccionados) < 2:
        return None
    
    # Crear matriz de cambios
    matriz_cambios = []
    productos = productos_seleccionados[:10]  # Limitar para visualización
    
    for prod_a in productos:
        fila_cambios = []
        for prod_b in productos:
            if prod_a == prod_b:
                fila_cambios.append(0)
            else:
                df_a = df_ddp[df_ddp["Producto"] == prod_a]
                df_b = df_ddp[df_ddp["Producto"] == prod_b]
                
                # Calcular número de cambios
                cambios = calcular_cambios_entre_productos(df_a, df_b)
                fila_cambios.append(cambios)
        
        matriz_cambios.append(fila_cambios)
    
    fig = go.Figure(data=go.Heatmap(
        z=matriz_cambios,
        x=[p[:15] for p in productos],
        y=[p[:15] for p in productos],
        colorscale='RdYlBu_r',
        text=matriz_cambios,
        texttemplate="%{text}",
        textfont={"size": 10},
        hoverongaps=False
    ))
    
    fig.update_layout(
        title="🌡️ Matriz de Intensidad de Cambios",
        xaxis_title="Producto Destino",
        yaxis_title="Producto Origen",
        template="plotly_white",
        height=500
    )
    
    return fig

def calcular_cambios_entre_productos(df_a, df_b):
    """Calcula el número de cambios entre dos productos."""
    if df_a.empty or df_b.empty:
        return 0
    
    cambios = 0
    columnas_comparar = [col for col in df_a.columns if col not in ["STD", "Producto", "Familia"]]
    
    posiciones = sorted(set(df_a["STD"]).union(df_b["STD"]))
    
    for pos in posiciones:
        fila_a = df_a[df_a["STD"] == pos]
        fila_b = df_b[df_b["STD"] == pos]
        
        for col in columnas_comparar:
            val_a = fila_a[col].values[0] if not fila_a.empty else None
            val_b = fila_b[col].values[0] if not fila_b.empty else None
            
            if val_a != val_b and not (pd.isna(val_a) and pd.isna(val_b)):
                cambios += 1
    
    return cambios

def crear_timeline_programa(df_programa):
    """Crea una timeline visual del programa."""
    if df_programa.empty:
        return None
    
    fig = go.Figure()
    
    # Crear datos para el timeline
    y_pos = 0
    colores = px.colors.qualitative.Set3
    
    for i, (_, row) in enumerate(df_programa.iterrows()):
        color = colores[i % len(colores)]
        
        # Determinar ancho basado en toneladas (normalizado)
        ancho = max(0.3, min(1.0, row.get('Toneladas Programadas', 1) / 100))
        
        fig.add_trace(go.Scatter(
            x=[i, i + ancho],
            y=[y_pos, y_pos],
            mode='lines+markers',
            line=dict(color=color, width=20),
            marker=dict(size=15, color=color),
            name=row['Nombre STD'][:20],
            text=f"{row['Nombre STD']}<br>Ton: {row.get('Toneladas Programadas', 'N/A')}",
            hovertemplate="%{text}<extra></extra>"
        ))
    
    fig.update_layout(
        title="📈 Timeline de Programa de Producción",
        xaxis_title="Secuencia",
        yaxis=dict(showticklabels=False, showgrid=False),
        template="plotly_white",
        height=300,
        showlegend=False
    )
    
    return fig

def crear_grafico_kpis(tiempo_total, num_cambios, productos_unicos):
    """Crea un dashboard de KPIs."""
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=("⏱️ Tiempo Total", "🔄 Cambios", "📦 Productos"),
        specs=[[{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}]]
    )
    
    # KPI Tiempo Total
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=tiempo_total,
        title={'text': "Minutos"},
        gauge={
            'axis': {'range': [None, tiempo_total * 1.5]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, tiempo_total * 0.5], 'color': "lightgray"},
                {'range': [tiempo_total * 0.5, tiempo_total], 'color': "gray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': tiempo_total * 1.2
            }
        }
    ), row=1, col=1)
    
    # KPI Número de Cambios
    fig.add_trace(go.Indicator(
        mode="number+delta",
        value=num_cambios,
        title={'text': "Cambios"},
        number={'font': {'size': 40}},
        delta={'reference': num_cambios * 0.8, 'relative': True}
    ), row=1, col=2)
    
    # KPI Productos Únicos
    fig.add_trace(go.Indicator(
        mode="number",
        value=productos_unicos,
        title={'text': "Productos"},
        number={'font': {'size': 40, 'color': 'green'}}
    ), row=1, col=3)
    
    fig.update_layout(height=300, template="plotly_white")
    return fig

# =====================================
# FUNCIONES DE COMPARACIÓN MEJORADAS
# =====================================

def comparar_productos_avanzado(df_a, df_b, columnas):
    """Comparación avanzada con categorización de cambios."""
    resumen = []
    posiciones = sorted(set(df_a["STD"]).union(df_b["STD"]))
    
    for pos in posiciones:
        fila_a = df_a[df_a["STD"] == pos]
        fila_b = df_b[df_b["STD"] == pos]
        
        for col in columnas:
            val_a = fila_a[col].values[0] if not fila_a.empty else None
            val_b = fila_b[col].values[0] if not fila_b.empty else None
            
            # Saltar valores vacíos
            if (val_a is None or pd.isna(val_a)) and (val_b is None or pd.isna(val_b)):
                continue
            
            cambia = val_a != val_b
            
            # Categorizar tipo de cambio
            if cambia:
                if col in ['Código Canal', 'Diámetro', 'Longitud']:
                    categoria = "🔴 Crítico"
                    prioridad = 1
                elif col in ['Velocidad', 'Temperatura']:
                    categoria = "🟡 Moderado"
                    prioridad = 2
                else:
                    categoria = "🟢 Menor"
                    prioridad = 3
            else:
                categoria = "✅ Sin cambio"
                prioridad = 4
            
            resumen.append({
                "Posición": pos,
                "Componente": col,
                "Valor A": val_a,
                "Valor B": val_b,
                "¿Cambia?": "✅ Sí" if cambia else "❌ No",
                "Categoría": categoria,
                "Prioridad": prioridad
            })
    
    df_resumen = pd.DataFrame(resumen)
    return df_resumen.sort_values(['Prioridad', 'Posición'])

def mostrar_comparacion_mejorada(df_resumen):
    """Muestra la comparación con visualización mejorada."""
    
    # Contar cambios por categoría
    cambios_por_categoria = df_resumen[df_resumen["¿Cambia?"] == "✅ Sí"]["Categoría"].value_counts()
    
    # Crear métricas visuales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        criticos = cambios_por_categoria.get("🔴 Crítico", 0)
        st.markdown(f"""
        <div class="metric-card danger-card">
            <h3>🔴 Críticos</h3>
            <h2>{criticos}</h2>
            <p>Requieren atención inmediata</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        moderados = cambios_por_categoria.get("🟡 Moderado", 0)
        st.markdown(f"""
        <div class="metric-card warning-card">
            <h3>🟡 Moderados</h3>
            <h2>{moderados}</h2>
            <p>Supervisión requerida</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        menores = cambios_por_categoria.get("🟢 Menor", 0)
        st.markdown(f"""
        <div class="metric-card success-card">
            <h3>🟢 Menores</h3>
            <h2>{menores}</h2>
            <p>Cambios rutinarios</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        sin_cambio = len(df_resumen[df_resumen["¿Cambia?"] == "❌ No"])
        st.markdown(f"""
        <div class="metric-card">
            <h3>✅ Sin Cambio</h3>
            <h2>{sin_cambio}</h2>
            <p>Componentes estables</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Gráfico de distribución de cambios
    if not df_resumen.empty:
        fig_pie = px.pie(
            values=cambios_por_categoria.values,
            names=cambios_por_categoria.index,
            title="📊 Distribución de Cambios por Criticidad",
            color_discrete_map={
                "🔴 Crítico": "#ef4444",
                "🟡 Moderado": "#f59e0b",
                "🟢 Menor": "#10b981"
            }
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

# =====================================
# INTERFAZ PRINCIPAL MEJORADA
# =====================================

def main():
    """Función principal con interfaz mejorada."""
    
    # Cargar CSS personalizado
    load_custom_css()
    
    # Header principal
    st.markdown("""
    <div class="main-header fade-in">
        <h1>🏭 Sistema de Control de Cambios - Laminador</h1>
        <p>Plataforma avanzada para análisis y optimización de cambios de producto</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar con navegación
    with st.sidebar:
        st.markdown("### 🧭 Navegación")
        st.markdown("---")
        
        # Estado del sistema
        st.markdown("### 📊 Estado del Sistema")
        if "df_prog" in st.session_state:
            st.success("✅ Programa cargado")
            productos_en_programa = len(st.session_state.df_prog["Nombre STD"].unique())
            st.metric("Productos únicos", productos_en_programa)
        else:
            st.warning("⚠️ Sin programa")
        
        st.markdown("---")
        
        # Configuración de visualización
        st.markdown("### ⚙️ Configuración")
        mostrar_solo_cambios = st.checkbox("Solo cambios", value=True)
        tema_oscuro = st.checkbox("Tema oscuro", value=False)
        animaciones = st.checkbox("Animaciones", value=True)
    
    # Cargar datos base
    df_ddp, df_tiempo, df_desbaste = cargar_datos()
    if df_ddp is None:
        st.stop()
    
    # Carga del programa
    cargar_programa_usuario()
    
    # Crear pestañas con iconos mejorados
    tabs = st.tabs([
        "🔍 Comparador Avanzado", 
        "📈 Análisis de Secuencia", 
        "🏭 Dashboard Maestranza",
        "📊 Reportes y Analítica"
    ])
    
    # =====================================
    # PESTAÑA 1: COMPARADOR AVANZADO
    # =====================================
    
    with tabs[0]:
        st.markdown("## 🔄 Comparador Avanzado de Productos")
        
        # Modo de comparación
        modo_comparacion = st.radio(
            "Selecciona el modo de comparación:",
            ["🎯 Comparación Específica", "🔍 Búsqueda Inteligente", "📊 Análisis Masivo"],
            horizontal=True
        )
        
        if modo_comparacion == "🎯 Comparación Específica":
            mostrar_comparacion_especifica(df_ddp, df_tiempo, df_desbaste, mostrar_solo_cambios)
        elif modo_comparacion == "🔍 Búsqueda Inteligente":
            mostrar_busqueda_inteligente(df_ddp, df_tiempo)
        else:
            mostrar_analisis_masivo(df_ddp, df_tiempo)
    
    # =====================================
    # PESTAÑA 2: ANÁLISIS DE SECUENCIA
    # =====================================
    
    with tabs[1]:
        st.markdown("## 📈 Análisis Avanzado de Secuencia")
        
        if "df_prog" in st.session_state:
            mostrar_analisis_secuencia_avanzado(df_ddp, df_tiempo)
        else:
            st.info("📤 Carga un archivo de programa para ver el análisis de secuencia")
    
    # =====================================
    # PESTAÑA 3: DASHBOARD MAESTRANZA
    # =====================================
    
    with tabs[2]:
        st.markdown("## 🏭 Dashboard Ejecutivo para Maestranza")
        
        if "df_prog" in st.session_state:
            mostrar_dashboard_maestranza(df_ddp)
        else:
            st.info("📤 Carga un archivo de programa para ver el dashboard")
    
    # =====================================
    # PESTAÑA 4: REPORTES Y ANALÍTICA
    # =====================================
    
    with tabs[3]:
        st.markdown("## 📊 Centro de Reportes y Analítica")
        mostrar_centro_reportes(df_ddp, df_tiempo, df_desbaste)

def mostrar_comparacion_especifica(df_ddp, df_tiempo, df_desbaste, mostrar_solo_cambios):
    """Muestra la comparación específica mejorada."""
    
    # Selector de familias con búsqueda
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🏷️ Producto A")
        familias = ["(Todos)"] + sorted(df_ddp["Familia"].dropna().unique())
        familia_a = st.selectbox("Familia A", familias, key="famA")
        
        df_fam_a = df_ddp if familia_a == "(Todos)" else df_ddp[df_ddp["Familia"] == familia_a]
        productos_a = sorted(df_fam_a["Producto"].dropna().unique())
        
        # Búsqueda de producto
        busqueda_a = st.text_input("🔍 Buscar producto A", key="search_a")
        if busqueda_a:
            productos_a = [p for p in productos_a if busqueda_a.lower() in p.lower()]
        
        producto_a = st.selectbox("Producto A", productos_a, key="prodA")
    
    with col2:
        st.markdown("### 🏷️ Producto B")
        familia_b = st.selectbox("Familia B", familias, key="famB")
        
        df_fam_b = df_ddp if familia_b == "(Todos)" else df_ddp[df_ddp["Familia"] == familia_b]
        productos_b = sorted(df_fam_b["Producto"].dropna().unique())
        
        # Búsqueda de producto
        busqueda_b = st.text_input("🔍 Buscar producto B", key="search_b")
        if busqueda_b:
            productos_b = [p for p in productos_b if busqueda_b.lower() in p.lower()]
        
        producto_b = st.selectbox("Producto B", productos_b, key="prodB")
    
    if producto_a and producto_b:
        # Información de los productos seleccionados
        col1, col2, col3 = st.columns(3)
        
        with col1:
            tiempo = obtener_tiempo_cambio(df_tiempo, producto_a, producto_b)
            if tiempo:
                st.metric("⏱️ Tiempo de Cambio", f"{tiempo} min", delta=f"{tiempo-30} min")
            else:
                st.metric("⏱️ Tiempo de Cambio", "No disponible")
        
        with col2:
            df_a = df_ddp[df_ddp["Producto"] == producto_a]
            df_b = df_ddp[df_ddp["Producto"] == producto_b]
            total_cambios = calcular_cambios_entre_productos(df_a, df_b)
            st.metric("🔄 Total de Cambios", total_cambios)
        
        with col3:
            # Calcular complejidad
            complejidad = "Alta" if total_cambios > 10 else "Media" if total_cambios > 5 else "Baja"
            color = "🔴" if complejidad == "Alta" else "🟡" if complejidad == "Media" else "🟢"
            st.metric("📊 Complejidad", f"{color} {complejidad}")
        
        # Comparación detallada
        st.markdown("### 🔍 Análisis Detallado")
        
        columnas_ddp = [col for col in df_a.columns if col not in ["STD", "Producto", "Familia"]]
        resumen_ddp = comparar_productos_avanzado(df_a, df_b, columnas_ddp)
        
        # Mostrar métricas de cambio
        mostrar_comparacion_mejorada(resumen_ddp)
        
        # Tabla de cambios con filtros
        if mostrar_solo_cambios:
            resumen_ddp = resumen_ddp[resumen_ddp["¿Cambia?"] == "✅ Sí"]
        
        # Filtros adicionales
        col1, col2 = st.columns(2)
        with col1:
            categorias_filtro = st.multiselect(
                "Filtrar por categoría:",
                resumen_ddp["Categoría"].unique(),
                default=resumen_ddp["Categoría"].unique()
            )
        
        with col2:
            posiciones_filtro = st.multiselect(
                "Filtrar por posición:",
                sorted(resumen_ddp["Posición"].unique()),
                default=sorted(resumen_ddp["Posición"].unique())
            )
        
        # Aplicar filtros
        resumen_filtrado = resumen_ddp[
            (resumen_ddp["Categoría"].isin(categorias_filtro)) &
            (resumen_ddp["Posición"].isin(posiciones_filtro))
        ]
        
        # Mostrar tabla con estilo
        st.dataframe(
            resumen_filtrado.drop(columns=["Prioridad"]),
            use_container_width=True,
            hide_index=True
        )

def mostrar_busqueda_inteligente(df_ddp, df_tiempo):
    """Función para búsqueda inteligente de productos similares."""
    st.info("🚧 Función en desarrollo - Próximamente búsqueda por características técnicas")

def mostrar_analisis_masivo(df_ddp, df_tiempo):
    """Análisis masivo de productos."""
    st.markdown("### 📊 Análisis Masivo de Compatibilidad")
    
    # Selección de productos para análisis masivo
    productos_disponibles = sorted(df_ddp["Producto"].dropna().unique())
    productos_seleccionados = st.multiselect(
        "Selecciona productos para análisis masivo (máximo 10):",
        productos_disponibles,
        default=productos_disponibles[:5] if len(productos_disponibles) >= 5 else productos_disponibles
    )
    
    if len(productos_seleccionados) >= 2:
        # Crear heatmap de cambios
        fig_heatmap = crear_heatmap_cambios(df_ddp, productos_seleccionados)
        if fig_heatmap:
            st.plotly_chart(fig_heatmap, use_container_width=True)
        
        # Análisis de clustering
        st.markdown("### 🎯 Grupos de Productos Similares")
        
        # Calcular matriz de distancias
        matriz_distancias = calcular_matriz_distancias(df_ddp, productos_seleccionados)
        
        # Mostrar recomendaciones
        st.markdown("### 💡 Recomendaciones de Secuenciación")
        mostrar_recomendaciones_secuencia(matriz_distancias, productos_seleccionados)
    else:
        st.warning("Selecciona al menos 2 productos para el análisis masivo")

def calcular_matriz_distancias(df_ddp, productos):
    """Calcula matriz de distancias entre productos."""
    matriz = {}
    for i, prod_a in enumerate(productos):
        matriz[prod_a] = {}
        for j, prod_b in enumerate(productos):
            if i != j:
                df_a = df_ddp[df_ddp["Producto"] == prod_a]
                df_b = df_ddp[df_ddp["Producto"] == prod_b]
                distancia = calcular_cambios_entre_productos(df_a, df_b)
                matriz[prod_a][prod_b] = distancia
            else:
                matriz[prod_a][prod_b] = 0
    return matriz

def mostrar_recomendaciones_secuencia(matriz_distancias, productos):
    """Muestra recomendaciones de secuenciación óptima."""
    recomendaciones = []
    
    for producto in productos:
        if producto in matriz_distancias:
            # Encontrar el producto más similar (menor distancia)
            distancias = matriz_distancias[producto]
            producto_similar = min(distancias.keys(), key=lambda x: distancias[x] if distancias[x] > 0 else float('inf'))
            
            if distancias[producto_similar] > 0:
                recomendaciones.append({
                    "Producto": producto,
                    "Siguiente Recomendado": producto_similar,
                    "Cambios Necesarios": distancias[producto_similar],
                    "Eficiencia": "🟢 Alta" if distancias[producto_similar] <= 3 else "🟡 Media" if distancias[producto_similar] <= 7 else "🔴 Baja"
                })
    
    if recomendaciones:
        df_recomendaciones = pd.DataFrame(recomendaciones)
        st.dataframe(df_recomendaciones, use_container_width=True, hide_index=True)

def mostrar_analisis_secuencia_avanzado(df_ddp, df_tiempo):
    """Muestra análisis avanzado de secuencia con visualizaciones."""
    df_prog = st.session_state.df_prog
    
    # KPIs principales
    st.markdown("### 📊 Indicadores Clave de Rendimiento")
    
    # Calcular métricas
    productos_unicos = len(df_prog["Nombre STD"].unique())
    toneladas_totales = df_prog["PROGR"].sum() if "PROGR" in df_prog.columns else 0
    
    # Análisis de cambios en secuencia
    resumen_cambios = []
    tiempos_cambio = []
    
    for i in range(len(df_prog) - 1):
        origen = df_prog.loc[i, "Nombre STD"]
        destino = df_prog.loc[i + 1, "Nombre STD"]
        
        if origen != destino:  # Solo contar cambios reales
            tiempo = obtener_tiempo_cambio(df_tiempo, origen, destino)
            if tiempo:
                tiempos_cambio.append(tiempo)
            
            # Calcular cambios técnicos
            df_a = df_ddp[df_ddp["Producto"] == origen]
            df_b = df_ddp[df_ddp["Producto"] == destino]
            cambios_tecnicos = calcular_cambios_entre_productos(df_a, df_b)
            
            familia_origen = df_a['Familia'].values[0] if not df_a.empty else "N/A"
            familia_destino = df_b['Familia'].values[0] if not df_b.empty else "N/A"
            
            resumen_cambios.append({
                "Secuencia": i + 1,
                "Origen": origen,
                "Destino": destino,
                "Familia_Origen": familia_origen,
                "Familia_Destino": familia_destino,
                "Tiempo": tiempo,
                "Cambios_Tecnicos": cambios_tecnicos,
                "Cambio_Familia": familia_origen != familia_destino
            })
    
    # Métricas calculadas
    tiempo_total = sum(tiempos_cambio) if tiempos_cambio else 0
    num_cambios = len(resumen_cambios)
    cambios_familia = sum(1 for c in resumen_cambios if c["Cambio_Familia"])
    
    # Mostrar KPIs con gráficos
    if tiempos_cambio:
        fig_kpis = crear_grafico_kpis(tiempo_total, num_cambios, productos_unicos)
        st.plotly_chart(fig_kpis, use_container_width=True)
    
    # Métricas adicionales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🏭 Toneladas Totales", f"{toneladas_totales:,.0f}")
    
    with col2:
        eficiencia = round((tiempo_total / num_cambios) if num_cambios > 0 else 0, 1)
        st.metric("⚡ Tiempo Promedio/Cambio", f"{eficiencia} min")
    
    with col3:
        st.metric("🔄 Cambios de Familia", cambios_familia, delta=f"{cambios_familia-num_cambios}")
    
    with col4:
        complejidad_promedio = sum(c["Cambios_Tecnicos"] for c in resumen_cambios) / len(resumen_cambios) if resumen_cambios else 0
        st.metric("🎯 Complejidad Promedio", f"{complejidad_promedio:.1f}")
    
    # Timeline visual
    if resumen_cambios:
        st.markdown("### 📈 Timeline de Producción")
        
        # Preparar datos para timeline
        df_timeline = pd.DataFrame(resumen_cambios)
        fig_timeline = crear_timeline_programa(df_timeline)
        if fig_timeline:
            st.plotly_chart(fig_timeline, use_container_width=True)
        
        # Gráfico de tiempos de cambio
        if tiempos_cambio:
            fig_tiempos = crear_grafico_tiempo_cambios(pd.DataFrame(resumen_cambios))
            st.plotly_chart(fig_tiempos, use_container_width=True)
    
    # Análisis detallado por cambio
    st.markdown("### 🔍 Análisis Detallado por Cambio")
    
    # Filtros para análisis detallado
    col1, col2 = st.columns(2)
    with col1:
        mostrar_solo_criticos = st.checkbox("Solo cambios críticos (>5 modificaciones)")
    with col2:
        mostrar_cambios_familia = st.checkbox("Solo cambios entre familias")
    
    # Aplicar filtros
    cambios_filtrados = resumen_cambios.copy()
    if mostrar_solo_criticos:
        cambios_filtrados = [c for c in cambios_filtrados if c["Cambios_Tecnicos"] > 5]
    if mostrar_cambios_familia:
        cambios_filtrados = [c for c in cambios_filtrados if c["Cambio_Familia"]]
    
    # Mostrar cambios en acordeones
    for cambio in cambios_filtrados[:10]:  # Limitar a 10 para rendimiento
        tiempo_str = f"{cambio['Tiempo']} min" if cambio['Tiempo'] else "No disponible"
        criticidad = "🔴" if cambio['Cambios_Tecnicos'] > 8 else "🟡" if cambio['Cambios_Tecnicos'] > 4 else "🟢"
        
        titulo = f"{criticidad} Cambio #{cambio['Secuencia']} | {cambio['Origen'][:20]} → {cambio['Destino'][:20]} | ⏱️ {tiempo_str}"
        
        with st.expander(titulo):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**📦 Producto Origen:** {cambio['Origen']}")
                st.markdown(f"**🏷️ Familia:** {cambio['Familia_Origen']}")
            
            with col2:
                st.markdown(f"**📦 Producto Destino:** {cambio['Destino']}")
                st.markdown(f"**🏷️ Familia:** {cambio['Familia_Destino']}")
            
            # Mostrar comparación detallada
            df_a = df_ddp[df_ddp["Producto"] == cambio['Origen']]
            df_b = df_ddp[df_ddp["Producto"] == cambio['Destino']]
            
            if not df_a.empty and not df_b.empty:
                columnas_cmp = [col for col in df_a.columns if col not in ["STD", "Producto", "Familia"]]
                resumen_cmp = comparar_productos_avanzado(df_a, df_b, columnas_cmp)
                resumen_cmp_filtrado = resumen_cmp[resumen_cmp["¿Cambia?"] == "✅ Sí"]
                
                if not resumen_cmp_filtrado.empty:
                    st.dataframe(
                        resumen_cmp_filtrado.drop(columns=["Prioridad"]),
                        use_container_width=True,
                        hide_index=True
                    )

def mostrar_dashboard_maestranza(df_ddp):
    """Dashboard ejecutivo mejorado para maestranza."""
    df_prog = st.session_state.df_prog.copy()
    
    # Header del dashboard
    st.markdown("### 🎛️ Panel de Control Ejecutivo")
    
    # Detectar bloques consecutivos
    df_prog["Grupo"] = (df_prog["Nombre STD"] != df_prog["Nombre STD"].shift()).cumsum()
    
    # Preparar resumen de programa
    df_programa = (
        df_prog
        .groupby(["Grupo", "Nombre STD"], as_index=False)
        .agg({"PROGR": "sum"})
        .rename(columns={"PROGR": "Toneladas Programadas"})
    )
    df_programa["Toneladas Programadas"] = df_programa["Toneladas Programadas"].astype(int)
    
    # KPIs ejecutivos
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_productos = len(df_programa)
        st.metric("📦 Productos en Programa", total_productos)
    
    with col2:
        total_toneladas = df_programa["Toneladas Programadas"].sum()
        st.metric("🏭 Toneladas Totales", f"{total_toneladas:,}")
    
    with col3:
        promedio_lote = df_programa["Toneladas Programadas"].mean()
        st.metric("📊 Lote Promedio", f"{promedio_lote:.0f} ton")
    
    with col4:
        productos_unicos = len(df_programa["Nombre STD"].unique())
        st.metric("🎯 Productos Únicos", productos_unicos)
    
    # Gráfico de distribución de toneladas
    st.markdown("### 📊 Distribución de Producción")
    
    fig_barras = px.bar(
        df_programa.head(15),  # Top 15 para mejor visualización
        x="Nombre STD",
        y="Toneladas Programadas",
        title="Toneladas por Producto",
        color="Toneladas Programadas",
        color_continuous_scale="Blues"
    )
    fig_barras.update_xaxis(tickangle=45)
    fig_barras.update_layout(height=400)
    st.plotly_chart(fig_barras, use_container_width=True)
    
    # Tabla de códigos de canal
    st.markdown("### 🔧 Configuración de Cilindros")
    
    posiciones_deseadas = ["M1", "M2", "M3", "M4", "A1", "A2", "A3", "A4", "A5", "A6"]
    df_canal_unico = (
        df_ddp[df_ddp["STD"].isin(posiciones_deseadas)]
        .dropna(subset=["Código Canal"])
        .sort_values(["Producto", "STD"])
        .drop_duplicates(subset=["Producto", "STD"], keep="first")
    )
    
    # Pivotear para obtener una columna por posición
    df_canal_pivot = df_canal_unico.pivot(index="Producto", columns="STD", values="Código Canal").reset_index()
    df_canal_pivot.columns.name = None
    
    # Unir con programa
    df_resumen = df_programa.merge(df_canal_pivot, left_on="Nombre STD", right_on="Producto", how="left").drop(columns=["Producto"], errors='ignore')
    
    columnas_orden = ["Nombre STD", "Toneladas Programadas"] + posiciones_deseadas
    df_resumen = df_resumen[[col for col in columnas_orden if col in df_resumen.columns]]
    
    # Filtros para la tabla
    col1, col2 = st.columns(2)
    with col1:
        min_toneladas = st.slider("Filtrar por toneladas mínimas:", 0, int(df_resumen["Toneladas Programadas"].max()), 0)
    with col2:
        buscar_producto = st.text_input("🔍 Buscar producto:", "")
    
    # Aplicar filtros
    df_filtrado = df_resumen[df_resumen["Toneladas Programadas"] >= min_toneladas]
    if buscar_producto:
        df_filtrado = df_filtrado[df_filtrado["Nombre STD"].str.contains(buscar_producto, case=False, na=False)]
    
    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
    
    # Análisis de frecuencia de cilindros mejorado
    st.markdown("### 🔄 Análisis de Frecuencia de Cilindros")
    
    codigos_programa = []
    for _, row in df_programa.iterrows():
        producto = row["Nombre STD"]
        toneladas = row["Toneladas Programadas"]
        
        codigos_producto = df_ddp[df_ddp["Producto"] == producto]["Código Canal"].dropna().unique()
        
        for codigo in codigos_producto:
            codigos_programa.append({
                "Nombre STD": producto,
                "Código Canal": codigo,
                "Toneladas Programadas": toneladas
            })
    
    df_codigos_programa = pd.DataFrame(codigos_programa)
    
    if not df_codigos_programa.empty:
        frecuencia_en_programa = (
            df_codigos_programa
            .groupby("Código Canal", dropna=True)
            .agg(
                Frecuencia=("Nombre STD", "count"),
                Toneladas_Programadas=("Toneladas Programadas", "sum")
            )
            .reset_index()
            .sort_values("Toneladas_Programadas", ascending=False)
        )
        
        # Gráfico de frecuencia
        fig_freq = px.bar(
            frecuencia_en_programa.head(20),
            x="Código Canal",
            y="Frecuencia",
            title="Frecuencia de Uso de Cilindros",
            color="Toneladas_Programadas",
            color_continuous_scale="Reds"
        )
        fig_freq.update_xaxis(tickangle=45)
        st.plotly_chart(fig_freq, use_container_width=True)
        
        # Tabla de frecuencia
        st.dataframe(frecuencia_en_programa, use_container_width=True, hide_index=True)
        
        # Botón de descarga mejorado
        col1, col2 = st.columns(2)
        with col1:
            buffer_completo = io.BytesIO()
            with pd.ExcelWriter(buffer_completo, engine="xlsxwriter") as writer:
                df_resumen.to_excel(writer, index=False, sheet_name="Resumen Maestranza")
                frecuencia_en_programa.to_excel(writer, index=False, sheet_name="Frecuencia Cilindros")
                
                # Agregar hoja de análisis
                analisis_data = {
                    "Métrica": ["Total Productos", "Toneladas Totales", "Lote Promedio", "Productos Únicos"],
                    "Valor": [total_productos, total_toneladas, f"{promedio_lote:.0f}", productos_unicos]
                }
                pd.DataFrame(analisis_data).to_excel(writer, index=False, sheet_name="Análisis")
            
            buffer_completo.seek(0)
            
            st.download_button(
                label="📥 Descargar Reporte Completo",
                data=buffer_completo,
                file_name=f"Reporte_Maestranza_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        with col2:
            # Generar reporte PDF (simulado con texto)
            reporte_texto = generar_reporte_texto(df_resumen, frecuencia_en_programa, total_productos, total_toneladas)
            st.download_button(
                label="📄 Descargar Reporte PDF",
                data=reporte_texto,
                file_name=f"Reporte_Ejecutivo_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain"
            )

def generar_reporte_texto(df_resumen, frecuencia, total_productos, total_toneladas):
    """Genera un reporte de texto estructurado."""
    reporte = f"""
REPORTE EJECUTIVO - LAMINADOR
========================================
Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}

RESUMEN EJECUTIVO
-----------------
• Total de productos en programa: {total_productos}
• Toneladas totales programadas: {total_toneladas:,}
• Lote promedio: {total_toneladas/total_productos:.0f} toneladas

TOP 10 PRODUCTOS POR TONELAJE
-----------------------------
"""
    
    top_productos = df_resumen.nlargest(10, "Toneladas Programadas")
    for i, (_, row) in enumerate(top_productos.iterrows(), 1):
        reporte += f"{i:2d}. {row['Nombre STD'][:30]:<30} {row['Toneladas Programadas']:>6,} ton\n"
    
    reporte += f"""

TOP 10 CILINDROS MÁS UTILIZADOS
-------------------------------
"""
    
    top_cilindros = frecuencia.head(10)
    for i, (_, row) in enumerate(top_cilindros.iterrows(), 1):
        reporte += f"{i:2d}. {row['Código Canal']:<15} Freq: {row['Frecuencia']:>3} | Ton: {row['Toneladas_Programadas']:>6,}\n"
    
    return reporte

def mostrar_centro_reportes(df_ddp, df_tiempo, df_desbaste):
    """Centro de reportes y analítica avanzada."""
    st.markdown("### 📊 Centro de Analítica Avanzada")
    
    # Pestañas de reportes
    tab_reportes = st.tabs(["📈 Análisis de Tendencias", "🔍 Auditoría de Datos", "⚡ Optimización", "📋 Reportes Personalizados"])
    
    with tab_reportes[0]:
        mostrar_analisis_tendencias(df_ddp, df_tiempo)
    
    with tab_reportes[1]:
        mostrar_auditoria_datos(df_ddp, df_tiempo, df_desbaste)
    
    with tab_reportes[2]:
        mostrar_sugerencias_optimizacion(df_ddp, df_tiempo)
    
    with tab_reportes[3]:
        mostrar_reportes_personalizados(df_ddp)

def mostrar_analisis_tendencias(df_ddp, df_tiempo):
    """Análisis de tendencias en los datos."""
    st.markdown("#### 📈 Análisis de Tendencias")
    
    # Análisis de distribución de familias
    if not df_ddp.empty:
        distribucion_familias = df_ddp["Familia"].value_counts()
        
        fig_familias = px.pie(
            values=distribucion_familias.values,
            names=distribucion_familias.index,
            title="Distribución de Productos por Familia"
        )
        st.plotly_chart(fig_familias, use_container_width=True)
        
        # Análisis de tiempos de cambio
        if not df_tiempo.empty:
            st.markdown("#### ⏱️ Estadísticas de Tiempos de Cambio")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                tiempo_promedio = df_tiempo["Minutos Cambio"].mean()
                st.metric("Tiempo Promedio", f"{tiempo_promedio:.1f} min")
            
            with col2:
                tiempo_min = df_tiempo["Minutos Cambio"].min()
                st.metric("Tiempo Mínimo", f"{tiempo_min} min")
            
            with col3:
                tiempo_max = df_tiempo["Minutos Cambio"].max()
                st.metric("Tiempo Máximo", f"{tiempo_max} min")
            
            # Histograma de tiempos
            fig_hist = px.histogram(
                df_tiempo,
                x="Minutos Cambio",
                nbins=20,
                title="Distribución de Tiempos de Cambio"
            )
            st.plotly_chart(fig_hist, use_container_width=True)

def mostrar_auditoria_datos(df_ddp, df_tiempo, df_desbaste):
    """Auditoría de calidad de datos."""
    st.markdown("#### 🔍 Auditoría de Calidad de Datos")
    
    auditoria_resultados = []
    
    # Auditoría DDP
    if not df_ddp.empty:
        productos_sin_familia = df_ddp["Familia"].isna().sum()
        duplicados_ddp = df_ddp.duplicated().sum()
        
        auditoria_resultados.extend([
            {"Tabla": "DDP", "Métrica": "Productos sin familia", "Valor": productos_sin_familia, "Estado": "🔴" if productos_sin_familia > 0 else "✅"},
            {"Tabla": "DDP", "Métrica": "Registros duplicados", "Valor": duplicados_ddp, "Estado": "🔴" if duplicados_ddp > 0 else "✅"},
            {"Tabla": "DDP", "Métrica": "Total productos", "Valor": len(df_ddp["Producto"].unique()), "Estado": "ℹ️"}
        ])
    
    # Auditoría Tiempos
    if not df_tiempo.empty:
        tiempos_nulos = df_tiempo["Minutos Cambio"].isna().sum()
        tiempos_cero = (df_tiempo["Minutos Cambio"] == 0).sum()
        
        auditoria_resultados.extend([
            {"Tabla": "Tiempos", "Métrica": "Tiempos nulos", "Valor": tiempos_nulos, "Estado": "🟡" if tiempos_nulos > 0 else "✅"},
            {"Tabla": "Tiempos", "Métrica": "Tiempos = 0", "Valor": tiempos_cero, "Estado": "🟡" if tiempos_cero > 0 else "✅"},
            {"Tabla": "Tiempos", "Métrica": "Combinaciones registradas", "Valor": len(df_tiempo), "Estado": "ℹ️"}
        ])
    
    # Mostrar resultados de auditoría
    if auditoria_resultados:
        df_auditoria = pd.DataFrame(auditoria_resultados)
        st.dataframe(df_auditoria, use_container_width=True, hide_index=True)

def mostrar_sugerencias_optimizacion(df_ddp, df_tiempo):
    """Sugerencias de optimización basadas en datos."""
    st.markdown("#### ⚡ Sugerencias de Optimización")
    
    sugerencias = []
    
    # Análisis de tiempos extremos
    if not df_tiempo.empty:
        percentil_95 = df_tiempo["Minutos Cambio"].quantile(0.95)
        cambios_lentos = df_tiempo[df_tiempo["Minutos Cambio"] > percentil_95]
        
        if not cambios_lentos.empty:
            sugerencias.append({
                "Categoría": "🐌 Tiempos Lentos",
                "Descripción": f"Se detectaron {len(cambios_lentos)} cambios que toman más de {percentil_95:.0f} minutos",
                "Acción": "Revisar procedimientos para estos cambios específicos",
                "Prioridad": "Alta"
            })
    
    # Análisis de productos problemáticos
    if "df_prog" in st.session_state and not df_ddp.empty:
        productos_programa = st.session_state.df_prog["Nombre STD"].unique()
        productos_sin_datos = [p for p in productos_programa if p not in df_ddp["Producto"].values]
        
        if productos_sin_datos:
            sugerencias.append({
                "Categoría": "❓ Datos Faltantes",
                "Descripción": f"{len(productos_sin_datos)} productos del programa no tienen datos técnicos",
                "Acción": "Completar base de datos técnica",
                "Prioridad": "Media"
            })
    
    # Sugerencias de eficiencia
    sugerencias.append({
        "Categoría": "📊 Analítica",
        "Descripción": "Implementar monitoreo en tiempo real de cambios",
        "Acción": "Instalar sensores IoT en posiciones críticas",
        "Prioridad": "Baja"
    })
    
    if sugerencias:
        for sugerencia in sugerencias:
            color = "🔴" if sugerencia["Prioridad"] == "Alta" else "🟡" if sugerencia["Prioridad"] == "Media" else "🟢"
            
            with st.expander(f"{color} {sugerencia['Categoría']} - Prioridad {sugerencia['Prioridad']}"):
                st.write(f"**Descripción:** {sugerencia['Descripción']}")
                st.write(f"**Acción Recomendada:** {sugerencia['Acción']}")

def mostrar_reportes_personalizados(df_ddp):
    """Generador de reportes personalizados."""
    st.markdown("#### 📋 Generador de Reportes Personalizados")
    
    # Configuración de reporte
    col1, col2 = st.columns(2)
    
    with col1:
        tipo_reporte = st.selectbox(
            "Tipo de reporte:",
            ["Resumen Ejecutivo", "Análisis Técnico", "Reporte de Cambios", "Auditoría de Calidad"]
        )
    
    with col2:
        formato_salida = st.selectbox(
            "Formato de salida:",
            ["Excel (.xlsx)", "CSV (.csv)", "Texto (.txt)"]
        )
    
    # Filtros para el reporte
    st.markdown("**Filtros del reporte:**")
    col1, col2 = st.columns(2)
    
    with col1:
        familias_seleccionadas = st.multiselect(
            "Familias a incluir:",
            df_ddp["Familia"].dropna().unique(),
            default=df_ddp["Familia"].dropna().unique()
        )
    
    with col2:
        incluir_graficos = st.checkbox("Incluir gráficos", value=True)
    
    # Botón de generación
    if st.button("🚀 Generar Reporte Personal"):
        df_filtrado = df_ddp[df_ddp["Familia"].isin(familias_seleccionadas)]

        if tipo_reporte == "Resumen Ejecutivo":
            df_resultado = df_filtrado.groupby("Familia").agg(
                Total_Productos=("Producto", "nunique"),
                Registros=("Producto", "count")
            ).reset_index()
        elif tipo_reporte == "Análisis Técnico":
            df_resultado = df_filtrado.pivot_table(
                index="Producto", columns="STD", values="Código Canal", aggfunc="first"
            ).reset_index()
        elif tipo_reporte == "Reporte de Cambios":
            df_resultado = df_filtrado[["Producto", "STD", "Código Canal", "Velocidad", "Longitud"]]
        elif tipo_reporte == "Auditoría de Calidad":
            df_resultado = df_filtrado[df_filtrado.isna().any(axis=1)]

        # Exportar en formato elegido
        if formato_salida == "Excel (.xlsx)":
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                df_resultado.to_excel(writer, index=False, sheet_name="Reporte")
                if incluir_graficos:
                    # Agregar resumen de familias
                    resumen_familias = df_ddp["Familia"].value_counts().reset_index()
                    resumen_familias.columns = ["Familia", "Frecuencia"]
                    resumen_familias.to_excel(writer, index=False, sheet_name="Resumen Familias")
            buffer.seek(0)
            st.download_button(
                label="📥 Descargar Excel",
                data=buffer,
                file_name="reporte_personalizado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        elif formato_salida == "CSV (.csv)":
            csv = df_resultado.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name="reporte_personalizado.csv",
                mime="text/csv"
            )
        elif formato_salida == "Texto (.txt)":
            texto = df_resultado.to_string(index=False)
            st.download_button(
                label="📥 Descargar TXT",
                data=texto,
                file_name="reporte_personalizado.txt",
                mime="text/plain"
            )



# =====================================
# FUNCIÓN FALTANTE: obtener_tiempo_cambio
# =====================================

def obtener_tiempo_cambio(df_tiempo, producto_origen, producto_destino):
    """Obtiene el tiempo de cambio entre dos productos."""
    tiempo_exacto = df_tiempo[
        (df_tiempo["Nombre STD Origen"] == producto_origen) & 
        (df_tiempo["Nombre STD Destino"] == producto_destino)
    ]["Minutos Cambio"].values

    return tiempo_exacto[0] if len(tiempo_exacto) > 0 else None


# =====================================
# LLAMADA PRINCIPAL SEGURA
# =====================================
if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        st.error(f'❌ Error crítico al ejecutar la app: {e}')
