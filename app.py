import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Visualización de Datos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título de la aplicación
st.title("📊 Sistema de Visualización de Datos por Ubicación y Fecha")

# URLs de las hojas de cálculo
SHEET_URLS = {
    "Mérida": "https://docs.google.com/spreadsheets/d/13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU/edit?gid=1252923180#gid=1252923180",
    "Tuxtla": "https://docs.google.com/spreadsheets/d/1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho/edit?gid=1168578915#gid=1168578915"
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

# Barra lateral con controles
with st.sidebar:
    st.header("🔧 Controles")
    
    # Selector de ubicación
    ubicacion = st.radio(
        "Selecciona la ubicación:",
        ["Mérida", "Tuxtla"],
        index=0
    )
    
    st.divider()
    
    # Información sobre los datos
    st.subheader("ℹ️ Información")
    st.markdown(f"Estás viendo datos de: **{ubicacion}**")
    st.markdown(f"[Enlace a la hoja original]({SHEET_URLS[ubicacion]})")

# Cargar datos según la ubicación seleccionada
with st.spinner(f"Cargando datos de {ubicacion}..."):
    df = load_data(SHEET_URLS[ubicacion])

if df is not None:
    # Limpiar nombres de columnas (eliminar espacios extra)
    df.columns = df.columns.str.strip()
    
    # Identificar columnas de fecha
    date_columns = []
    for col in df.columns:
        # Verificar si la columna contiene fechas
        if df[col].dtype == 'object':
            try:
                # Intentar convertir a fecha
                pd.to_datetime(df[col].dropna(), errors='raise')
                date_columns.append(col)
            except:
                pass
    
    # Si no se detectan columnas de fecha, buscar manualmente
    if not date_columns:
        # Buscar columnas con nombres que sugieran fechas
        date_like_columns = [col for col in df.columns if any(word in col.lower() for word in ['fecha', 'date', 'day', 'time'])]
        if date_like_columns:
            date_columns = date_like_columns
    
    # Mostrar controles de fecha si hay columnas de fecha
    if date_columns:
        st.sidebar.divider()
        st.sidebar.subheader("📅 Filtros de Fecha")
        
        # Seleccionar columna de fecha
        fecha_col = st.sidebar.selectbox(
            "Selecciona la columna de fecha:",
            date_columns,
            index=0
        )
        
        # Convertir a formato de fecha
        try:
            df[fecha_col] = pd.to_datetime(df[fecha_col], errors='coerce')
            
            # Obtener rango de fechas disponible
            min_date = df[fecha_col].min()
            max_date = df[fecha_col].max()
            
            # Si hay valores de fecha válidos
            if not pd.isna(min_date) and not pd.isna(max_date):
                # Convertir a date (sin hora)
                min_date = min_date.date()
                max_date = max_date.date()
                
                # Selector de rango de fechas
                selected_dates = st.sidebar.date_input(
                    "Selecciona el rango de fechas:",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date
                )
                
                # Filtrar por fecha si se seleccionaron dos fechas
                if len(selected_dates) == 2:
                    start_date, end_date = selected_dates
                    # Convertir a datetime para comparación
                    start_datetime = pd.to_datetime(start_date)
                    end_datetime = pd.to_datetime(end_date)
                    
                    # Filtrar dataframe
                    mask = (df[fecha_col] >= start_datetime) & (df[fecha_col] <= end_datetime)
                    df = df.loc[mask]
        except Exception as e:
            st.sidebar.error(f"No se pudieron procesar las fechas: {e}")
    
    # Mostrar estadísticas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de registros", df.shape[0])
    with col2:
        st.metric("Total de columnas", df.shape[1])
    with col3:
        st.metric("Valores nulos", df.isnull().sum().sum())
    with col4:
        st.metric("Memoria utilizada", f"{df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")
    
    # Mostrar todos los datos
    st.subheader(f"Todos los datos de {ubicacion}")
    st.dataframe(df, use_container_width=True)
    
    # Mostrar información del dataset
    with st.expander("ℹ️ Información del dataset"):
        st.subheader("Tipos de datos")
        st.write(df.dtypes)
        
        st.subheader("Estadísticas descriptivas")
        st.write(df.describe())
    
    # Opciones de descarga
    st.sidebar.divider()
    st.sidebar.subheader("💾 Exportar Datos")
    
    # Convertir dataframe a CSV
    csv = df.to_csv(index=False).encode('utf-8')
    
    st.sidebar.download_button(
        label="Descargar como CSV",
        data=csv,
        file_name=f"datos_{ubicacion.lower()}.csv",
        mime="text/csv",
    )
else:
    st.error("No se pudieron cargar los datos. Verifica que la hoja de cálculo sea pública.")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de visualización de datos • "
    f"Datos de {ubicacion} • {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
