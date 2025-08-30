import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Análisis de Precios Multi-Hojas",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Ocultar la barra lateral
st.markdown("""
    <style>
        .css-1d391kg {display: none;}
    </style>
""", unsafe_allow_html=True)

# Título de la aplicación
st.title("💰 Sistema de Análisis de Precios Multi-Hojas")

# URLs de todas las hojas de cálculo disponibles
SHEET_URLS = {
    "Mérida - Hoja 1": "https://docs.google.com/spreadsheets/d/13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU/edit?gid=1252923180#gid=1252923180",
    "Mérida - Hoja 2": "https://docs.google.com/spreadsheets/d/13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU/edit?gid=0",  # Ejemplo con diferente gid
    "Tuxtla - Hoja Principal": "https://docs.google.com/spreadsheets/d/1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho/edit?gid=1168578915#gid=1168578915",
    "Tuxtla - Datos Adicionales": "https://docs.google.com/spreadsheets/d/1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho/edit?gid=1",  # Ejemplo con diferente gid
}

# Función para convertir URL de Google Sheets a formato CSV de exportación
def convert_google_sheet_url(url):
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')
    d_index = path_parts.index('d') if 'd' in path_parts else -1
    
    if d_index != -1 and len(path_parts) > d_index + 1:
        sheet_id = path_parts[d_index + 1]
        
        # Obtener el gid de los parámetros de consulta
        query_params = parse_qs(parsed_url.query)
        gid = query_params.get('gid', ['0'])[0]
        
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return None

# Función para cargar datos desde Google Sheets
@st.cache_data(ttl=3600)  # Cachear datos por 1 hora
def load_data(url):
    csv_url = convert_google_sheet_url(url)
    if csv_url:
        try:
            return pd.read_csv(csv_url)
        except Exception as e:
            st.error(f"Error al cargar los datos: {e}")
            return None
    return None

# Selector de hoja en la página principal
st.subheader("Selecciona la hoja para analizar:")
hoja_seleccionada = st.selectbox(
    "Hoja:",
    list(SHEET_URLS.keys()),
    index=0
)

# Obtener ubicación basada en el nombre de la hoja seleccionada
if "Mérida" in hoja_seleccionada:
    ubicacion = "Mérida"
elif "Tuxtla" in hoja_seleccionada:
    ubicacion = "Tuxtla"
else:
    ubicacion = hoja_seleccionada

# Cargar datos según la hoja seleccionada
with st.spinner(f"Cargando datos de {hoja_seleccionada}..."):
    df = load_data(SHEET_URLS[hoja_seleccionada])

if df is not None:
    # Limpiar nombres de columnas (eliminar espacios extra)
    df.columns = df.columns.str.strip()
    
    # Identificar columnas de precio automáticamente
    price_columns = []
    
    for col in df.columns:
        # Verificar si la columna contiene precios (números)
        if np.issubdtype(df[col].dtype, np.number):
            # Verificar si el nombre de la columna sugiere que es un precio
            if any(word in col.lower() for word in ['precio', 'price', 'costo', 'cost', 'valor', 'value']):
                price_columns.append(col)
    
    # Si no se detectan columnas de precio, usar todas las columnas numéricas
    if not price_columns:
        price_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Mostrar información de la hoja seleccionada
    st.success(f"📋 Hoja seleccionada: **{hoja_seleccionada}**")
    st.info(f"📊 Total de registros: **{len(df):,}** | 📈 Total de columnas: **{len(df.columns)}**")
    
    # Mostrar selector de columna de precio
    if price_columns:
        precio_col = st.selectbox(
            "Selecciona la columna de precio para analizar:",
            price_columns,
            index=0
        )
        
        # Mostrar estadísticas de precios
        st.divider()
        st.subheader(f"📊 Análisis de Precios - {hoja_seleccionada}")
        
        # Calcular métricas
        precio_minimo = df[precio_col].min()
        precio_maximo = df[precio_col].max()
        suma_precios = df[precio_col].sum()
        cantidad_registros = df[precio_col].count()
        promedio = suma_precios / cantidad_registros if cantidad_registros > 0 else 0
        
        # Mostrar métricas en columnas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Precio Mínimo", f"${precio_minimo:,.2f}")
        
        with col2:
            st.metric("Precio Máximo", f"${precio_maximo:,.2f}")
        
        with col3:
            st.metric("Suma de Todos los Precios", f"${suma_precios:,.2f}")
        
        with col4:
            st.metric("Promedio General", f"${promedio:,.2f}")
        
        # Mostrar detalles del cálculo
        with st.expander("📝 Detalles del cálculo del promedio"):
            st.write(f"**Fórmula del promedio:** Suma de precios / Cantidad de registros")
            st.write(f"**Suma de precios:** ${suma_precios:,.2f}")
            st.write(f"**Cantidad de registros:** {cantidad_registros:,}")
            st.write(f"**Cálculo:** ${suma_precios:,.2f} / {cantidad_registros:,} = ${promedio:,.2f}")
        
        # Mostrar distribución de precios
        st.subheader("Distribución de Precios")
        col1, col2 = st.columns(2)
        
        with col1:
            st.bar_chart(df[precio_col].value_counts().head(15))
        
        with col2:
            # Mostrar estadísticas adicionales
            st.write("**Estadísticas adicionales:**")
            st.write(f"**Mediana:** ${df[precio_col].median():,.2f}")
            st.write(f"**Desviación estándar:** ${df[precio_col].std():,.2f}")
            st.write(f"**Rango intercuartílico:** ${df[precio_col].quantile(0.75) - df[precio_col].quantile(0.25):,.2f}")
            st.write(f"**Valores únicos:** {df[precio_col].nunique()}")
        
        # Mostrar los 10 precios más altos y más bajos
        st.subheader("Precios Extremos")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**10 Precios Más Bajos:**")
            st.dataframe(df.nsmallest(10, precio_col)[[precio_col]].reset_index(drop=True), height=300)
        
        with col2:
            st.write("**10 Precios Más Altos:**")
            st.dataframe(df.nlargest(10, precio_col)[[precio_col]].reset_index(drop=True), height=300)
    
    else:
        st.error("No se detectaron columnas numéricas en esta hoja.")
    
    # Mostrar todos los datos
    st.divider()
    st.subheader(f"Todos los datos de {hoja_seleccionada}")
    st.dataframe(df, use_container_width=True)
    
    # Mostrar información del dataset
    with st.expander("ℹ️ Información del dataset"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Tipos de datos")
            st.write(df.dtypes)
        
        with col2:
            st.subheader("Estadísticas descriptivas")
            st.write(df.describe())
    
    # Opciones de descarga
    st.download_button(
        label="📥 Descargar Datos como CSV",
        data=df.to_csv(index=False).encode('utf-8'),
        file_name=f"datos_{hoja_seleccionada.lower().replace(' ', '_')}.csv",
        mime="text/csv",
    )
else:
    st.error("No se pudieron cargar los datos. Verifica que la hoja de cálculo sea pública.")

# Información de todas las hojas disponibles
st.divider()
st.subheader("📋 Hojas Disponibles")
col1, col2 = st.columns(2)

with col1:
    st.write("**Hojas de Mérida:**")
    for hoja in [h for h in SHEET_URLS.keys() if "Mérida" in h]:
        st.write(f"- {hoja}")

with col2:
    st.write("**Hojas de Tuxtla:**")
    for hoja in [h for h in SHEET_URLS.keys() if "Tuxtla" in h]:
        st.write(f"- {hoja}")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios multi-hojas • "
    f"{hoja_seleccionada} • {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
