import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlparse, parse_qs

# Configuración de la página
st.set_page_config(
    page_title="Visualizador de Hojas de Cálculo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título de la aplicación
st.title("📊 Visualizador de Hojas de Cálculo de Google")

# URLs de las hojas de cálculo
SHEET_URLS = {
    "Sheet 1 - Datos de Ejemplo": "https://docs.google.com/spreadsheets/d/13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU/edit?gid=1252923180#gid=1252923180",
    "Sheet 2 - Información Adicional": "https://docs.google.com/spreadsheets/d/1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho/edit?gid=1168578915#gid=1168578915"
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

# Barra lateral con información
with st.sidebar:
    st.header("ℹ️ Información")
    st.markdown("""
    Esta aplicación muestra datos de diferentes hojas de cálculo de Google.
    Selecciona una pestaña para ver los datos específicos.
    """)
    
    st.divider()
    
    st.subheader("Enlaces a las hojas")
    for name, url in SHEET_URLS.items():
        st.markdown(f"- [{name}]({url})")

# Crear pestañas para cada hoja
tab_titles = list(SHEET_URLS.keys())
tabs = st.tabs(tab_titles)

for i, (name, url) in enumerate(SHEET_URLS.items()):
    with tabs[i]:
        st.header(name)
        st.caption(f"Fuente: [Enlace a la hoja original]({url})")
        
        # Cargar y mostrar datos
        with st.spinner("Cargando datos..."):
            df = load_data(url)
            
        if df is not None:
            st.subheader("Vista previa de los datos")
            st.dataframe(df.head(10), use_container_width=True)
            
            # Mostrar estadísticas básicas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de filas", df.shape[0])
            with col2:
                st.metric("Total de columnas", df.shape[1])
            with col3:
                st.metric("Valores nulos", df.isnull().sum().sum())
            
            # Selector de columnas para gráficos
            st.subheader("Análisis de datos")
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            
            if numeric_cols:
                selected_col = st.selectbox(
                    "Selecciona una columna para visualizar:",
                    numeric_cols,
                    key=f"col_selector_{i}"
                )
                
                # Mostrar histograma
                if selected_col:
                    st.bar_chart(df[selected_col].value_counts())
            else:
                st.info("No hay columnas numéricas para visualizar en este conjunto de datos.")
        else:
            st.error("No se pudieron cargar los datos. Verifica que la hoja de cálculo sea pública.")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Aplicación creada con Streamlit • "
    "Datos cargados desde Google Sheets</div>",
    unsafe_allow_html=True
)
