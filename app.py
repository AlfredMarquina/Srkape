import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import time

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Análisis de Precios por Hoja",
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
st.title("💰 Sistema de Análisis de Precios por Hoja Diaria")

# URLs de las hojas de cálculo
SHEET_URLS = {
    "Mérida": "https://docs.google.com/spreadsheets/d/13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU/edit?gid=1252923180#gid=1252923180",
    "Tuxtla": "https://docs.google.com/spreadsheets/d/1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho/edit?gid=1168578915#gid=1168578915"
}

# Función para convertir URL de Google Sheets a formato CSV de exportación
def convert_google_sheet_url(url, gid=None):
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')
    d_index = path_parts.index('d') if 'd' in path_parts else -1
    
    if d_index != -1 and len(path_parts) > d_index + 1:
        sheet_id = path_parts[d_index + 1]
        
        # Obtener el gid de los parámetros de consulta si no se proporciona
        if gid is None:
            query_params = parse_qs(parsed_url.query)
            gid = query_params.get('gid', ['0'])[0]
        
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return None

# Función para cargar datos desde Google Sheets
@st.cache_data(ttl=3600)  # Cachear datos por 1 hora
def load_data(url, gid=None):
    csv_url = convert_google_sheet_url(url, gid)
    if csv_url:
        try:
            return pd.read_csv(csv_url)
        except Exception as e:
            st.error(f"Error al cargar los datos: {e}")
            return None
    return None

# Función para simular la detección de hojas disponibles (esto deberías adaptarlo a tu estructura real)
def obtener_hojas_disponibles():
    # Simulamos hojas para los últimos 7 días
    hoy = datetime.now()
    hojas = []
    
    for i in range(7):
        fecha = hoy - timedelta(days=i)
        hojas.append({
            "nombre": f"Hoja {fecha.strftime('%Y-%m-%d')}",
            "fecha": fecha.date(),
            "gid": str(1000 + i)  # Esto es un ejemplo, debes usar los gid reales
        })
    
    return hojas

# Selector de ubicación en la página principal
st.subheader("Selecciona la ubicación:")
ubicacion = st.radio(
    "Ubicación:",
    ["Mérida", "Tuxtla"],
    index=0,
    horizontal=True,
    key="ubicacion_selector"
)

# Obtener hojas disponibles
hojas_disponibles = obtener_hojas_disponibles()
hojas_nombres = [hoja["nombre"] for hoja in hojas_disponibles]

# Selector de hoja
st.subheader("Selecciona la hoja:")
hoja_seleccionada_nombre = st.selectbox(
    "Hoja:",
    options=hojas_nombres,
    index=0,  # Mostrar la primera hoja (más reciente) por defecto
    key="hoja_selector"
)

# Obtener los detalles de la hoja seleccionada
hoja_seleccionada = next((hoja for hoja in hojas_disponibles if hoja["nombre"] == hoja_seleccionada_nombre), None)

if hoja_seleccionada:
    st.info(f"📅 Visualizando datos de: {hoja_seleccionada['nombre']}")

# Cargar datos según la ubicación y hoja seleccionada
with st.spinner(f"Cargando datos de {ubicacion} - {hoja_seleccionada_nombre}..."):
    # Nota: Aquí debes usar el gid correcto para cada hoja
    df = load_data(SHEET_URLS[ubicacion], hoja_seleccionada["gid"] if hoja_seleccionada else None)

if df is not None and not df.empty:
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
    
    # Selector de columna de precio
    if price_columns:
        precio_col = st.selectbox(
            "Selecciona la columna de precio:",
            price_columns,
            index=0,
            key="precio_selector"
        )
        
        # Mostrar estadísticas de precios
        st.divider()
        st.subheader(f"📊 Información de Data Reset - {hoja_seleccionada_nombre}")
        
        # Calcular métricas
        precio_minimo = df[precio_col].min()
        precio_maximo = df[precio_col].max()
        suma_precios = df[precio_col].sum()
        cantidad_registros = df[precio_col].count()
        promedio_diario = suma_precios / cantidad_registros if cantidad_registros > 0 else 0
        
        # Mostrar métricas en columnas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Precio Mínimo", f"${precio_minimo:,.2f}")
        
        with col2:
            st.metric("Precio Máximo", f"${precio_maximo:,.2f}")
        
        with col3:
            st.metric("Suma de Precios", f"${suma_precios:,.2f}")
        
        with col4:
            st.metric("Promedio Diario", f"${promedio_diario:,.2f}")
        
        # Mostrar detalles del cálculo
        with st.expander("📝 Detalles del cálculo"):
            st.write(f"**Fórmula del promedio:** Suma de precios / Cantidad de registros")
            st.write(f"**Suma de precios:** ${suma_precios:,.2f}")
            st.write(f"**Cantidad de registros:** {cantidad_registros:,}")
            st.write(f"**Cálculo:** ${suma_precios:,.2f} / {cantidad_registros:,} = ${promedio_diario:,.2f}")
            
            # Mostrar distribución de precios
            st.subheader("Distribución de Precios")
            st.bar_chart(df[precio_col].value_counts().head(10))
    
    # Mostrar todos los datos de la hoja seleccionada
    st.divider()
    st.subheader(f"Datos de {hoja_seleccionada_nombre}")
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
        file_name=f"datos_{ubicacion.lower()}_{hoja_seleccionada_nombre.replace(' ', '_')}.csv",
        mime="text/csv",
    )
    
    # Navegación entre hojas
    st.divider()
    st.subheader("🚀 Navegación Rápida entre Hojas")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("⏮️ Hoja Anterior", use_container_width=True):
            # Lógica para ir a la hoja anterior
            current_index = hojas_nombres.index(hoja_seleccionada_nombre)
            if current_index < len(hojas_nombres) - 1:
                st.session_state.hoja_selector = hojas_nombres[current_index + 1]
                st.rerun()
    
    with col2:
        st.info(f"Hoja actual: {hoja_seleccionada_nombre}")
    
    with col3:
        if st.button("⏭️ Hoja Siguiente", use_container_width=True):
            # Lógica para ir a la hoja siguiente
            current_index = hojas_nombres.index(hoja_seleccionada_nombre)
            if current_index > 0:
                st.session_state.hoja_selector = hojas_nombres[current_index - 1]
                st.rerun()

else:
    if df is None:
        st.error("No se pudieron cargar los datos. Verifica que la hoja de cálculo sea pública.")
    else:
        st.warning("La hoja seleccionada no contiene datos.")

# Información de todas las hojas disponibles
with st.expander("📋 Ver todas las hojas disponibles"):
    st.write("Lista completa de hojas:")
    for i, hoja in enumerate(hojas_disponibles):
        st.write(f"{i+1}. {hoja['nombre']}")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios por hoja • "
    f"Datos de {ubicacion} • {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
