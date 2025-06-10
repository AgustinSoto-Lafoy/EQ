# app.py
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Cambio de Producto", layout="wide")
st.title("🔧 Plataforma de Cambio de Producto – Laminador")

st.sidebar.header("📁 Subida de Archivos")
file_ddp = st.sidebar.file_uploader("Cargar Consolidado Laminador (DDP)", type=["xlsx"])
file_tiempo = st.sidebar.file_uploader("Cargar Base Tiempo de Cambio", type=["xlsx"])
file_homologacion = st.sidebar.file_uploader("Cargar Mapa Homologación", type=["xlsx"])
file_programa = st.sidebar.file_uploader("Cargar Programa Producción", type=["xlsx"])

if file_ddp:
    df_ddp = pd.read_excel(file_ddp)
    st.subheader("🧾 Vista previa DDP")
    st.dataframe(df_ddp.head())

if file_homologacion:
    df_homolog = pd.read_excel(file_homologacion)
    st.subheader("📘 Vista previa Mapa Homologación")
    st.dataframe(df_homolog.head())
