import streamlit as st
import pandas as pd

st.set_page_config(page_title="Cambio de Producto", layout="wide")

@st.cache_data
def cargar_datos():
    ddp = pd.read_excel("data/Consolidado_Laminador.xlsx")
    tiempo = pd.read_excel("data/BBDD_Tiempo.xlsx")
    desbaste = pd.read_excel("data/Diagrama_Desbaste.xlsx")
    return ddp, tiempo, desbaste

df_ddp, df_tiempo, df_desbaste = cargar_datos()

tabs = st.tabs(["🆚 Comparador de Productos", "📋 Secuencia de Programa"])

# --- PESTAÑA COMPARADOR MANUAL ---
with tabs[0]:
    st.title("🔧 Plataforma de Cambio de Producto – Laminador")
    st.subheader("🔄 Comparador Manual de Productos")

    familias = ["(Todos)"] + sorted(df_ddp["Familia"].dropna().unique())
    colf1, colf2 = st.columns(2)
    with colf1:
        familiaA = st.selectbox("Selecciona Familia A", familias, key="famA")
    with colf2:
        familiaB = st.selectbox("Selecciona Familia B", familias, key="famB")

    df_famA = df_ddp if familiaA == "(Todos)" else df_ddp[df_ddp["Familia"] == familiaA]
    df_famB = df_ddp if familiaB == "(Todos)" else df_ddp[df_ddp["Familia"] == familiaB]

    productosA = sorted(df_famA["Producto"].dropna().unique())
    productosB = sorted(df_famB["Producto"].dropna().unique())

    colA, colB = st.columns(2)
    with colA:
        productoA = st.selectbox("Selecciona Producto A", productosA, key="A", index=0)
        if familiaA == "(Todos)" and productoA:
            familia_real_A = df_ddp[df_ddp["Producto"] == productoA]["Familia"].dropna().unique()
            if len(familia_real_A) > 0:
                st.markdown(f"<span style='font-size: 14px;'>Producto A pertenece a la familia: <b>{familia_real_A[0]}</b></span>", unsafe_allow_html=True)

    with colB:
        productoB = st.selectbox("Selecciona Producto B", productosB, key="B", index=0)
        if familiaB == "(Todos)" and productoB:
            familia_real_B = df_ddp[df_ddp["Producto"] == productoB]["Familia"].dropna().unique()
            if len(familia_real_B) > 0:
                st.markdown(f"<span style='font-size: 14px;'>Producto B pertenece a la familia: <b>{familia_real_B[0]}</b></span>", unsafe_allow_html=True)

    def comparar_productos(dfA, dfB, columnas):
        resumen = []
        posiciones = sorted(set(dfA["STD"]).union(dfB["STD"]))
        for pos in posiciones:
            filaA = dfA[dfA["STD"] == pos]
            filaB = dfB[dfB["STD"] == pos]
            for col in columnas:
                valA = filaA[col].values[0] if not filaA.empty else None
                valB = filaB[col].values[0] if not filaB.empty else None
                if (valA is None or pd.isna(valA)) and (valB is None or pd.isna(valB)):
                    continue
                cambia = valA != valB
                resumen.append({"Posicion": pos, "Componente": col, "Valor A": valA, "Valor B": valB, "¿Cambia?": "✅ Sí" if cambia else "❌ No"})
        return pd.DataFrame(resumen)

    def resaltar(row):
        base_color = "#ffacac" if st.get_option("theme.base") == "Light" else "#FF6E6E"
        return [f'background-color: {base_color}' if row["¿Cambia?"] == "✅ Sí" else '' for _ in row]

    df_A = df_famA[df_famA["Producto"] == productoA]
    df_B = df_famB[df_famB["Producto"] == productoB]

    if not df_A.empty and not df_B.empty:
        tiempo_exacto = df_tiempo[(df_tiempo["Nombre STD Origen"] == productoA) & (df_tiempo["Nombre STD Destino"] == productoB)]["Minutos Cambio"].values
        if len(tiempo_exacto) > 0:
            st.success(f"⏱️ Tiempo estimado de cambio: {tiempo_exacto[0]} minutos")
        else:
            st.warning("No se encontró tiempo de cambio registrado entre estos productos.")

        columnas_ddp = [col for col in df_A.columns if col not in ["STD", "Producto", "Familia"]]
        resumen_ddp = comparar_productos(df_A, df_B, columnas_ddp)

        st.markdown("### 🔢 Diferencias Técnicas por cambio producto")
        if st.checkbox("Mostrar solo componentes que cambian (DDP)", value=False):
            resumen_ddp = resumen_ddp[resumen_ddp["¿Cambia?"] == "✅ Sí"]
        st.dataframe(resumen_ddp.style.apply(resaltar, axis=1))

        resumen_desbaste = []
        desbA = df_desbaste[df_desbaste["Familia"] == familiaA] if familiaA != "(Todos)" else df_desbaste
        desbB = df_desbaste[df_desbaste["Familia"] == familiaB] if familiaB != "(Todos)" else df_desbaste

        pares = sorted(set(zip(desbA["SubSTD"], desbA["Componente limpio"])) | set(zip(desbB["SubSTD"], desbB["Componente limpio"])), key=lambda x: int(x[0][1]) if x[0].startswith("D") and x[0][1:].isdigit() else 99)
        for substd, comp in pares:
            val1 = desbA[(desbA["SubSTD"] == substd) & (desbA["Componente limpio"] == comp)]["Valor"].values
            val2 = desbB[(desbB["SubSTD"] == substd) & (desbB["Componente limpio"] == comp)]["Valor"].values
            val1 = val1[0] if len(val1) > 0 else None
            val2 = val2[0] if len(val2) > 0 else None
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
        df_desbaste_cmp = pd.DataFrame(resumen_desbaste)
        st.markdown("### 🧠 Diagrama Desbaste")
        if st.checkbox("Mostrar solo componentes que cambian (Desbaste)", value=False):
            df_desbaste_cmp = df_desbaste_cmp[df_desbaste_cmp["¿Cambia?"] == "✅ Sí"]
        st.dataframe(df_desbaste_cmp.astype(str).style.apply(resaltar, axis=1))

        st.markdown("### 📊 Resumen de cambios")
        resumen_contador = resumen_ddp[resumen_ddp["¿Cambia?"] == "✅ Sí"]
        conteo_por_componente = resumen_contador["Componente"].value_counts().reset_index()
        conteo_por_componente.columns = ["Componente", "Cantidad de Cambios"]
        st.dataframe(conteo_por_componente)

# --- PESTAÑA SECUENCIA DE PROGRAMA ---

def agrupar_cambios_consecutivos(df):
    df["Grupo"] = (df[["Producto Origen", "Producto Destino", "Tiempo estimado", "Cambios Código Canal"]]
                   .ne(df[["Producto Origen", "Producto Destino", "Tiempo estimado", "Cambios Código Canal"]].shift())
                   .any(axis=1)
                   .cumsum())
    df_agrupado = df.groupby("Grupo").agg({
        "Secuencia": "first",
        "Familia": "first",
        "Producto Origen": "first",
        "Producto Destino": "last",
        "Tiempo estimado": "first",
        "Cambios Código Canal": "first"
    }).reset_index(drop=True)
    return df_agrupado

with tabs[1]:
    st.title("📋 Secuencia de Programa")

    archivo = st.file_uploader("📤 Sube el archivo de programa (xlsx)", type=["xlsx"])

    if archivo is not None:
        try:
            df_prog = pd.read_excel(archivo, sheet_name="TablaCombinada")
            df_prog = df_prog[["Nombre STD"]].dropna().reset_index(drop=True)

            resumen = []
            for i in range(len(df_prog) - 1):
                origen = df_prog.loc[i, "Nombre STD"]
                destino = df_prog.loc[i + 1, "Nombre STD"]

                t = df_tiempo[(df_tiempo["Nombre STD Origen"] == origen) & (df_tiempo["Nombre STD Destino"] == destino)]["Minutos Cambio"].values
                tiempo = t[0] if len(t) > 0 else None

                df_A = df_ddp[df_ddp["Producto"] == origen]
                df_B = df_ddp[df_ddp["Producto"] == destino]

                if not df_A.empty and not df_B.empty:
                    merged = df_A.merge(df_B, on="STD", suffixes=("_A", "_B"))
                    cambios_codigo_canal = merged.apply(
                        lambda row: row["Código Canal_A"] != row["Código Canal_B"]
                        if "Código Canal_A" in row and "Código Canal_B" in row else False, axis=1
                    ).sum()

                    resumen.append({
                        "Secuencia": i + 1,
                        "Familia": f"{df_A['Familia'].values[0]}" + "-" + f"{df_B['Familia'].values[0]}",
                        "Producto Origen": origen,
                        "Producto Destino": destino,
                        "Tiempo estimado": tiempo,
                        "Cambios Código Canal": cambios_codigo_canal
                    })

            df_resumen = agrupar_cambios_consecutivos(pd.DataFrame(resumen))

            st.markdown("### 🧩 Cambios en secuencia (con comparador técnico)")
            for idx, fila in df_resumen.iterrows():
                titulo = f"🔹 #{fila['Secuencia']} | {fila['Producto Origen']} → {fila['Producto Destino']} | ⏱️ {fila['Tiempo estimado']} min | 🔧 {fila['Cambios Código Canal']} cambios canal"
                with st.expander(titulo):
                    df_A_cmp = df_ddp[df_ddp["Producto"] == fila['Producto Origen']]
                    df_B_cmp = df_ddp[df_ddp["Producto"] == fila['Producto Destino']]
                    columnas_cmp = [col for col in df_A_cmp.columns if col not in ["STD", "Producto", "Familia"]]
                    resumen_cmp = comparar_productos(df_A_cmp, df_B_cmp, columnas_cmp)
                    resumen_cmp = resumen_cmp[resumen_cmp["¿Cambia?"] == "✅ Sí"]
                    st.dataframe(resumen_cmp)

        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {e}")
