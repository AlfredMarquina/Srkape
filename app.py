import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime
import numpy as np
import re

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Análisis de Precios de Hoteles",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título de la aplicación
st.title("🏨 Sistema de Análisis de Precios de Hoteles")

# IDs de las hojas de cálculo
SHEET_IDS = {
    "Mérida": "13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU",
    "Tuxtla": "1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho"
}

# Configuración para acceso a Google Sheets usando Secrets
def setup_gspread():
    try:
        # Verificar que los secrets existen
        if 'gcp_service_account' not in st.secrets:
            st.error("No se encontraron las credenciales en los Secrets.")
            st.info("Por favor configura las credenciales en Streamlit Secrets")
            return None
            
        # Cargar credenciales desde Streamlit Secrets
        creds_info = {
            "type": st.secrets["gcp_service_account"]["type"],
            "project_id": st.secrets["gcp_service_account"]["project_id"],
            "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
            "private_key": st.secrets["gcp_service_account"]["private_key"].replace('\\n', '\n'),
            "client_email": st.secrets["gcp_service_account"]["client_email"],
            "client_id": st.secrets["gcp_service_account"]["client_id"],
            "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
            "token_uri": st.secrets["gcp_service_account"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"],
            "universe_domain": st.secrets["gcp_service_account"]["universe_domain"]
        }
        
        creds = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error de autenticación: {e}")
        return None

# Función para obtener todas las hojas de un spreadsheet
def get_all_sheets(spreadsheet_id, client):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        # Ordenar hojas por índice (más recientes primero)
        worksheets.sort(key=lambda x: x.index, reverse=True)
        return {f"{ws.title}": ws for ws in worksheets}
    except Exception as e:
        st.error(f"Error al acceder al spreadsheet: {e}")
        return None

# Función para obtener datos de una hoja específica
def get_sheet_data(worksheet):
    try:
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Error al obtener datos de {worksheet.title}: {e}")
        return pd.DataFrame()

# Función para detectar automáticamente la columna de precios
def detect_price_column(df):
    if df.empty:
        return None
    
    # Buscar columnas que probablemente contengan precios
    price_keywords = ['precio', 'price', 'costo', 'cost', 'valor', 'value', 'monto', 'amount', 'importe', 'tarifa']
    
    for col in df.columns:
        col_lower = str(col).lower()
        # Verificar si el nombre de la columna contiene palabras clave de precio
        if any(keyword in col_lower for keyword in price_keywords):
            return col
    
    # Si no se encuentra por nombre, buscar columnas numéricas
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        return numeric_cols[0]
    
    # Intentar convertir columnas a numéricas
    for col in df.columns:
        try:
            # Intentar convertir a numérico
            numeric_series = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''), errors='coerce')
            if numeric_series.notna().sum() > 0:  # Si hay valores numéricos
                return col
        except:
            continue
    
    return None

# Función para detectar automáticamente la columna de nombres de hoteles
def detect_hotel_column(df):
    if df.empty:
        return None
    
    # Buscar columnas que probablemente contengan nombres de hoteles
    hotel_keywords = ['hotel', 'nombre', 'name', 'propiedad', 'establecimiento', 'alojamiento']
    
    for col in df.columns:
        col_lower = str(col).lower()
        # Verificar si el nombre de la columna contiene palabras clave de hotel
        if any(keyword in col_lower for keyword in hotel_keywords):
            return col
    
    # Si no se encuentra, usar la primera columna de texto
    text_cols = df.select_dtypes(include=['object']).columns
    if len(text_cols) > 0:
        return text_cols[0]
    
    return None

# Función para buscar hoteles en múltiples hojas
def search_hotel_prices(client, spreadsheet_id, hotel_name, max_sheets=30):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        # Ordenar hojas por índice (más recientes primero)
        worksheets.sort(key=lambda x: x.index, reverse=True)
        
        resultados = []
        hojas_procesadas = 0
        precios_encontrados = 0
        
        for worksheet in worksheets:
            if hojas_procesadas >= max_sheets or precios_encontrados >= 30:
                break
                
            df = get_sheet_data(worksheet)
            if df.empty:
                continue
                
            # Detectar columnas
            hotel_col = detect_hotel_column(df)
            price_col = detect_price_column(df)
            
            if hotel_col and price_col:
                # Buscar el hotel (búsqueda insensible a mayúsculas y con coincidencias parciales)
                mask = df[hotel_col].astype(str).str.lower().str.contains(hotel_name.lower(), na=False)
                hotel_data = df[mask]
                
                if not hotel_data.empty:
                    # Procesar precios
                    for _, row in hotel_data.iterrows():
                        try:
                            precio = pd.to_numeric(
                                str(row[price_col]).replace(',', '.').replace('$', '').replace(' ', ''), 
                                errors='coerce'
                            )
                            if not pd.isna(precio) and precio > 0:
                                resultados.append({
                                    'hoja': worksheet.title,
                                    'hotel': row[hotel_col],
                                    'precio': precio,
                                    'fecha_hoja': worksheet.title  # Usamos el título como referencia de fecha
                                })
                                precios_encontrados += 1
                                
                                if precios_encontrados >= 30:
                                    break
                        except:
                            continue
            
            hojas_procesadas += 1
            
        return pd.DataFrame(resultados)
        
    except Exception as e:
        st.error(f"Error en la búsqueda: {e}")
        return pd.DataFrame()

# Función para calcular métricas de precios
def calculate_hotel_metrics(resultados_df):
    if resultados_df.empty:
        return None
    
    precios = resultados_df['precio']
    
    return {
        'total_hojas_revisadas': resultados_df['hoja'].nunique(),
        'total_precios_encontrados': len(precios),
        'precio_minimo': precios.min(),
        'precio_maximo': precios.max(),
        'suma_total': precios.sum(),
        'promedio': precios.mean(),
        'desviacion_estandar': precios.std()
    }

# Selector de ubicación en el sidebar
st.sidebar.header("📍 Selecciona Ubicación")
ubicacion = st.sidebar.radio("Ubicación:", ["Mérida", "Tuxtla"], index=0)

spreadsheet_id = SHEET_IDS[ubicacion]

# Obtener cliente de Google Sheets
client = setup_gspread()

# Barra de búsqueda de hoteles
st.header("🔍 Búsqueda de Precios de Hoteles")
hotel_busqueda = st.text_input(
    "Ingresa el nombre del hotel a buscar:",
    placeholder="Ej: Hilton, Marriott, Holiday Inn...",
    help="Busca coincidencias parciales en el nombre del hotel"
)

if hotel_busqueda and client:
    with st.spinner(f"Buscando '{hotel_busqueda}' en las últimas 30 hojas..."):
        resultados = search_hotel_prices(client, spreadsheet_id, hotel_busqueda, max_sheets=30)
    
    if not resultados.empty:
        st.success(f"✅ Se encontraron {len(resultados)} precios para hoteles que coinciden con '{hotel_busqueda}'")
        
        # Calcular métricas
        metrics = calculate_hotel_metrics(resultados)
        
        # Mostrar métricas
        st.subheader("📊 Métricas de Precios")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Precios Encontrados", metrics['total_precios_encontrados'])
            st.metric("Precio Mínimo", f"${metrics['precio_minimo']:,.2f}")
        
        with col2:
            st.metric("Hojas Revisadas", metrics['total_hojas_revisadas'])
            st.metric("Precio Máximo", f"${metrics['precio_maximo']:,.2f}")
        
        with col3:
            st.metric("Suma Total", f"${metrics['suma_total']:,.2f}")
            st.metric("Desviación Estándar", f"${metrics['desviacion_estandar']:,.2f}")
        
        with col4:
            st.metric("Promedio", f"${metrics['promedio']:,.2f}")
            st.metric("Rango", f"${metrics['precio_maximo'] - metrics['precio_minimo']:,.2f}")
        
        # Mostrar detalles del cálculo
        with st.expander("📝 Detalles del cálculo del promedio"):
            st.write(f"**Fórmula:** Suma total / Cantidad de precios")
            st.write(f"**Suma total:** ${metrics['suma_total']:,.2f}")
            st.write(f"**Cantidad de precios:** {metrics['total_precios_encontrados']}")
            st.write(f"**Cálculo:** ${metrics['suma_total']:,.2f} / {metrics['total_precios_encontrados']} = ${metrics['promedio']:,.2f}")
        
        # Mostrar resultados detallados
        st.subheader("📋 Precios Encontrados")
        st.dataframe(
            resultados.sort_values('precio', ascending=False),
            use_container_width=True,
            height=300
        )
        
        # Gráfico de precios
        st.subheader("📈 Distribución de Precios")
        col1, col2 = st.columns(2)
        
        with col1:
            st.bar_chart(resultados.set_index('hotel')['precio'].head(15))
        
        with col2:
            st.write("**Resumen estadístico:**")
            st.write(resultados['precio'].describe())
        
        # Opción de descarga
        csv = resultados.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Resultados de Búsqueda",
            data=csv,
            file_name=f"busqueda_{hotel_busqueda}_{ubicacion}.csv".replace(" ", "_"),
            mime="text/csv",
            use_container_width=True
        )
        
    else:
        st.warning(f"❌ No se encontraron precios para hoteles que coincidan con '{hotel_busqueda}'")
        st.info("Sugerencias:")
        st.write("- Verifica la ortografía del nombre del hotel")
        st.write("- Intenta con una búsqueda más general")
        st.write("- Asegúrate de que el hotel exista en la ubicación seleccionada")

# Sección de análisis de hojas individuales (mantener funcionalidad anterior)
st.header("📊 Análisis de Hojas Individuales")

if client:
    # Modo autenticado - acceso completo a todas las hojas
    with st.spinner("Cargando hojas disponibles..."):
        sheets_dict = get_all_sheets(spreadsheet_id, client)
    
    if sheets_dict:
        # Obtener nombres de hojas
        sheet_names = list(sheets_dict.keys())
        
        # Mostrar selector de hojas en sidebar
        st.sidebar.header("📋 Selecciona Hoja para Análisis")
        selected_sheet_name = st.sidebar.selectbox(
            "Hoja:",
            sheet_names,
            index=0
        )
        
        # Obtener datos de la hoja seleccionada
        with st.spinner(f"Cargando {selected_sheet_name}..."):
            selected_sheet = sheets_dict[selected_sheet_name]
            df = get_sheet_data(selected_sheet)
        
        if df is not None and not df.empty:
            # Detectar automáticamente la columna de precios
            price_column = detect_price_column(df)
            
            if price_column:
                # Calcular métricas de precios para la hoja actual
                precios = pd.to_numeric(
                    df[price_column].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''), 
                    errors='coerce'
                ).dropna()
                
                if len(precios) > 0:
                    st.metric("Precio Promedio (esta hoja)", f"${precios.mean():,.2f}")
                    st.metric("Total de Registros", len(df))
                
                # Mostrar datos
                st.dataframe(df, use_container_width=True, height=300)

# Información adicional en el sidebar
st.sidebar.header("ℹ️ Información")
st.sidebar.info("""
**Búsqueda de Hoteles:**
- Busca por nombre en las últimas 30 hojas
- Encuentra hasta 30 precios
- Calcula promedio automáticamente
- Muestra análisis completo
""")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios de hoteles • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
