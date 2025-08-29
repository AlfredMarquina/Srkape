import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Análisis de Precios por Fecha",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Ocultar la barra lateral
st.markdown("""
    <style>
        .css-1d391kg {display: none;}
        div[data-testid="stDateInput"] {margin-bottom: 20px;}
    </style>
""", unsafe_allow_html=True)

# Título de la aplicación
st.title("💰 Sistema de Análisis de Precios por Fecha")

# URLs de las hojas de cálculo
SHEET_URLS = {
    "Mérida": "https://docs.google.com/spreadsheets/d/13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU/edit?gid=1252923180#gid=1252923180",
    "Tuxtla": "https://docs.google.com/spreadsheets/d/1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho/edit?gid=1168578915#gid=1168578915"
}

# Mapeo de fechas a GIDs (debes completar con tus GIDs reales)
FECHAS_GIDS = {
    "2024-01-01": "1252923180",
    "2024-01-02": "1168578915",
    "2024-01-03": "1234567890",
    "2024-01-04": "0987654321",
    "2024-01-05": "1122334455",
    # Agrega aquí todas tus fechas y GIDs correspondientes
}

# Función para convertir URL de Google Sheets a formato CSV de exportación
def convert_google_sheet_url(url, gid):
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')
    d_index = path_parts.index('d') if 'd' in path_parts else -1
    
    if d_index != -1 and len(path_parts) > d_index + 1:
        sheet_id = path_parts[d_index + 1]
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return None

# Función para cargar datos desde Google Sheets
@st.cache_data(ttl=3600)  # Cachear datos por 1 hora
def load_data(url, gid):
    csv_url = convert_google_sheet_url(url, gid)
    if csv_url:
        try:
            return pd.read_csv(csv_url)
        except Exception as e:
            st.error(f"Error al cargar los datos: {e}")
            return None
    return None

# Función para obtener las fechas disponibles
def obtener_fechas_disponibles():
    # Ordenar las fechas de más reciente a más antigua
    fechas = sorted([datetime.strptime(f, "%Y-%m-%d") for f in FECHAS_GIDS.keys()], reverse=True)
    return [f.strftime("%Y-%m-%d") for f in fechas]

# Selector de ubicación en la página principal
st.subheader("📍 Selecciona la ubicación:")
ubicacion = st.radio(
    "Ubicación:",
    ["Mérida", "Tuxtla"],
    index=0,
    horizontal=True,
    key="ubicacion_selector"
)

# Obtener fechas disponibles
fechas_disponibles = obtener_fechas_disponibles()

if not fechas_disponibles:
    st.error("No hay fechas disponibles. Configura el mapeo de FECHAS_GIDS.")
    st.stop()

# Seleccionar fecha
st.subheader("📅 Selecciona la fecha:")
fecha_seleccionada = st.selectbox(
    "Fecha:",
    options=fechas_disponibles,
    index=0,  # Mostrar la fecha más reciente por defecto
    key="fecha_selector",
    format_func=lambda x: datetime.strptime(x, "%Y-%m-%d").strftime("%d/%m/%Y")
)

# Obtener el GID correspondiente a la fecha seleccionada
gid_seleccionado = FECHAS_GIDS.get(fecha_seleccionada)

if not gid_seleccionado:
    st.error(f"No se encontró GID para la fecha {fecha_seleccionada}")
    st.stop()

# Cargar datos según la ubicación y fecha seleccionada
with st.spinner(f"Cargando datos de {ubicacion} - {fecha_seleccionada}..."):
    df = load_data(SHEET_URLS[ubicacion], gid_seleccionado)

if df is not None and not df.empty:
    # Limpiar nombres de columnas (eliminar espacios extra)
    df.columns = df.columns.str.strip()
    
    # Mostrar información de la fecha seleccionada
    fecha_formateada = datetime.strptime(fecha_seleccionada, "%Y-%m-%d").strftime("%d/%m/%Y")
    st.success(f"📊 Visualizando datos del {fecha_formateada} - {ubicacion}")
    
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
    
    # Selector de columna de precio si hay múltiples opciones
    if price_columns:
        if len(price_columns) > 1:
            precio_col = st.selectbox(
                "💰 Selecciona la columna de precio:",
                price_columns,
                index=0,
                key="precio_selector"
            )
        else:
            precio_col = price_columns[0]
        
        # Mostrar estadísticas de precios
        st.divider()
        st.subheader(f"📈 Métricas de Precios - {fecha_formateada}")
        
        # Calcular métricas
        precio_minimo = df[precio_col].min()
        precio_maximo = df[precio_col].max()
        suma_precios = df[precio_col].sum()
        cantidad_registros = df[precio_col].count()
        promedio_diario = suma_precios / cantidad_registros if cantidad_registros > 0 else 0
        
        # Mostrar métricas en columnas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Precio Mínimo", f"${precio_minimo:,.2f}", 
                     help="El precio más bajo registrado en esta fecha")
        
        with col2:
            st.metric("Precio Máximo", f"${precio_maximo:,.2f}", 
                     help="El precio más alto registrado en esta fecha")
        
        with col3:
            st.metric("Suma Total", f"${suma_precios:,.2f}", 
                     help="Suma de todos los precios registrados")
        
        with col4:
            st.metric("Promedio Diario", f"${promedio_diario:,.2f}", 
                     help="Promedio de precios (suma total / cantidad de registros)")
        
        # Mostrar detalles del cálculo
        with st.expander("📝 Detalles del cálculo del promedio"):
            st.write(f"**Fórmula:** Suma de precios ÷ Cantidad de registros = Promedio")
            st.write(f"**Cálculo:** ${suma_precios:,.2f} ÷ {cantidad_registros:,} = ${promedio_diario:,.2f}")
            
            # Mostrar distribución de precios
            st.subheader("Distribución de Precios")
            if len(df[precio_col].unique()) > 1:
                st.bar_chart(df[precio_col].value_counts())
            else:
                st.info("Solo hay un valor único de precio en esta fecha")
    
    # Mostrar todos los datos de la fecha seleccionada
    st.divider()
    st.subheader(f"📋 Datos Completos - {fecha_formateada}")
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
        file_name=f"datos_{ubicacion.lower()}_{fecha_seleccionada}.csv",
        mime="text/csv",
        help="Descargar todos los datos de esta fecha en formato CSV"
    )
    
    # Navegación entre fechas
    st.divider()
    st.subheader("🔄 Navegación entre Fechas")
    
    current_index = fechas_disponibles.index(fecha_seleccionada)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if current_index < len(fechas_disponibles) - 1:
            fecha_anterior = fechas_disponibles[current_index + 1]
            if st.button(f"⏮️ {datetime.strptime(fecha_anterior, '%Y-%m-%d').strftime('%d/%m')}", 
                        use_container_width=True, help="Ir a la fecha anterior"):
                st.session_state.fecha_selector = fecha_anterior
                st.rerun()
    
    with col2:
        st.info(f"Fecha actual: {fecha_formateada}")
    
    with col3:
        if current_index > 0:
            fecha_siguiente = fechas_disponibles[current_index - 1]
            if st.button(f"⏭️ {datetime.strptime(fecha_siguiente, '%Y-%m-%d').strftime('%d/%m')}", 
                        use_container_width=True, help="Ir a la fecha siguiente"):
                st.session_state.fecha_selector = fecha_siguiente
                st.rerun()

else:
    if df is None:
        st.error("No se pudieron cargar los datos. Verifica que la hoja de cálculo sea pública.")
    else:
        st.warning("No hay datos disponibles para la fecha seleccionada.")

# Información de todas las fechas disponibles
with st.expander("📋 Ver todas las fechas disponibles"):
    st.write("Lista completa de fechas con datos:")
    for i, fecha in enumerate(fechas_disponibles):
        fecha_bonita = datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y")
        st.write(f"{i+1}. {fecha_bonita}")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios por fecha • "
    f"{ubicacion} • Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M')}</div>",
    unsafe_allow_html=True
)
