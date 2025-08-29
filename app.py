import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
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
    </style>
""", unsafe_allow_html=True)

# Título de la aplicación
st.title("💰 Sistema de Análisis de Precios por Fecha Específica")

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

# Selector de ubicación en la página principal
st.subheader("Selecciona la ubicación:")
ubicacion = st.radio(
    "Ubicación:",
    ["Mérida", "Tuxtla"],
    index=0,
    horizontal=True
)

# Cargar datos según la ubicación seleccionada
with st.spinner(f"Cargando datos de {ubicacion}..."):
    df = load_data(SHEET_URLS[ubicacion])

if df is not None:
    # Limpiar nombres de columnas (eliminar espacios extra)
    df.columns = df.columns.str.strip()
    
    # Identificar columnas de fecha y precio automáticamente
    date_columns = []
    price_columns = []
    
    for col in df.columns:
        # Verificar si la columna contiene fechas
        if df[col].dtype == 'object':
            try:
                # Intentar convertir a fecha
                pd.to_datetime(df[col].dropna(), errors='raise')
                date_columns.append(col)
            except:
                pass
        
        # Verificar si la columna contiene precios (números)
        if np.issubdtype(df[col].dtype, np.number):
            # Verificar si el nombre de la columna sugiere que es un precio
            if any(word in col.lower() for word in ['precio', 'price', 'costo', 'cost', 'valor', 'value']):
                price_columns.append(col)
    
    # Si no se detectan columnas de precio, usar todas las columnas numéricas
    if not price_columns:
        price_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Si no se detectan columnas de fecha, buscar manualmente
    if not date_columns:
        date_columns = [col for col in df.columns if any(word in col.lower() for word in ['fecha', 'date', 'day', 'time'])]
    
    # Mostrar selectores de columna
    col1, col2 = st.columns(2)
    
    with col1:
        if date_columns:
            fecha_col = st.selectbox(
                "Selecciona la columna de fecha:",
                date_columns,
                index=0
            )
        else:
            st.warning("No se detectaron columnas de fecha en el dataset.")
            fecha_col = None
    
    with col2:
        if price_columns:
            precio_col = st.selectbox(
                "Selecciona la columna de precio:",
                price_columns,
                index=0
            )
        else:
            st.error("No se detectaron columnas de precio en el dataset.")
            precio_col = None
    
    # Si tenemos columna de fecha, procesar
    if fecha_col:
        try:
            # Convertir a formato de fecha
            df[fecha_col] = pd.to_datetime(df[fecha_col], errors='coerce')
            
            # Obtener fechas disponibles
            fechas_disponibles = df[fecha_col].dropna().dt.date.unique()
            fechas_disponibles = sorted(fechas_disponibles)
            
            if len(fechas_disponibles) > 0:
                # Selector de fecha única
                fecha_seleccionada = st.selectbox(
                    "Selecciona una fecha específica:",
                    options=fechas_disponibles,
                    index=len(fechas_disponibles)-1,  # Última fecha por defecto
                    format_func=lambda x: x.strftime("%Y-%m-%d")
                )
                
                # Filtrar por fecha seleccionada
                if fecha_seleccionada:
                    mask = df[fecha_col].dt.date == fecha_seleccionada
                    df_filtrado = df.loc[mask]
                    
                    # Mostrar información de la fecha seleccionada
                    st.success(f"Mostrando datos para la fecha: {fecha_seleccionada.strftime('%Y-%m-%d')}")
                    st.write(f"Registros encontrados: {len(df_filtrado)}")
                    
                    # Mostrar estadísticas de precios si tenemos columna de precio
                    if precio_col and len(df_filtrado) > 0:
                        st.divider()
                        st.subheader(f"📊 Información de Data Reset - {fecha_seleccionada.strftime('%Y-%m-%d')}")
                        
                        # Calcular métricas
                        precio_minimo = df_filtrado[precio_col].min()
                        precio_maximo = df_filtrado[precio_col].max()
                        suma_precios = df_filtrado[precio_col].sum()
                        cantidad_registros = df_filtrado[precio_col].count()
                        promedio_diario = suma_precios / cantidad_registros if cantidad_registros > 0 else 0
                        
                        # Mostrar métricas en columnas
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Precio Mínimo del Día", f"${precio_minimo:,.2f}")
                        
                        with col2:
                            st.metric("Precio Máximo del Día", f"${precio_maximo:,.2f}")
                        
                        with col3:
                            st.metric("Suma de Todos los Precios", f"${suma_precios:,.2f}")
                        
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
                            st.bar_chart(df_filtrado[precio_col].value_counts())
                        
                        # Mostrar datos filtrados
                        st.divider()
                        st.subheader(f"Datos de {fecha_seleccionada.strftime('%Y-%m-%d')}")
                        st.dataframe(df_filtrado, use_container_width=True)
                        
                        # Opciones de descarga para datos filtrados
                        st.download_button(
                            label="📥 Descargar Datos Filtrados como CSV",
                            data=df_filtrado.to_csv(index=False).encode('utf-8'),
                            file_name=f"datos_{ubicacion.lower()}_{fecha_seleccionada.strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                        )
                    elif precio_col:
                        st.warning("No hay datos de precios para la fecha seleccionada.")
            else:
                st.warning("No se encontraron fechas válidas en el dataset.")
                
        except Exception as e:
            st.error(f"No se pudieron procesar las fechas: {e}")
    
    # Mostrar todos los datos (sin filtrar)
    st.divider()
    st.subheader(f"Todos los datos de {ubicacion}")
    st.dataframe(df, use_container_width=True)
    
    # Mostrar información del dataset completo
    with st.expander("ℹ️ Información del dataset completo"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Tipos de datos")
            st.write(df.dtypes)
        
        with col2:
            st.subheader("Estadísticas descriptivas")
            st.write(df.describe())
    
    # Opciones de descarga para todos los datos
    st.download_button(
        label="📥 Descargar Todos los Datos como CSV",
        data=df.to_csv(index=False).encode('utf-8'),
        file_name=f"todos_datos_{ubicacion.lower()}.csv",
        mime="text/csv",
    )
else:
    st.error("No se pudieron cargar los datos. Verifica que la hoja de cálculo sea pública.")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios por fecha • "
    f"Datos de {ubicacion} • {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
