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

# Cache para mejorar rendimiento
@st.cache_resource(ttl=3600)
def get_cached_client():
    return setup_gspread()

@st.cache_data(ttl=600)
def get_cached_sheets(_client, spreadsheet_id):
    return get_all_sheets(spreadsheet_id, _client)

@st.cache_data(ttl=300)
def get_cached_sheet_data(_worksheet):
    return get_sheet_data(_worksheet)

# Configuración para acceso a Google Sheets usando Secrets
def setup_gspread():
    try:
        if 'gcp_service_account' not in st.secrets:
            st.error("No se encontraron las credenciales en los Secrets.")
            return None
            
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

# Función mejorada para detectar automáticamente columnas relevantes
def detect_columns(df):
    if df.empty:
        return None, None
        
    # Palabras clave para buscar columnas
    hotel_keywords = ['hotel', 'nombre', 'name', 'establecimiento', 'property', 'hotel_name']
    price_keywords = ['precio', 'price', 'costo', 'cost', 'valor', 'value', 'monto', 'amount', 'importe', 'rate', 'tarifa']
    
    hotel_col = None
    price_col = None
    
    # Primera pasada: búsqueda exacta por palabras clave
    for col in df.columns:
        col_lower = str(col).lower()
        
        # Detectar columna de hotel
        if not hotel_col and any(keyword == col_lower for keyword in hotel_keywords):
            hotel_col = col
        
        # Detectar columna de precio
        if not price_col and any(keyword == col_lower for keyword in price_keywords):
            price_col = col
    
    # Segunda pasada: búsqueda parcial si no se encontró exacto
    if not hotel_col:
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in hotel_keywords):
                hotel_col = col
                break
    
    if not price_col:
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in price_keywords):
                # Verificar si contiene valores numéricos
                try:
                    numeric_test = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''), errors='coerce')
                    if numeric_test.notna().sum() > 0:
                        price_col = col
                        break
                except:
                    continue
    
    # Tercera pasada: si no se detecta por nombre, usar heurísticas
    if not hotel_col:
        for col in df.columns:
            # Buscar columnas con texto que podrían ser nombres de hoteles
            if (df[col].dtype == 'object' and 
                df[col].astype(str).str.len().mean() > 3 and 
                df[col].astype(str).str.isnumeric().mean() < 0.3):
                hotel_col = col
                break
    
    if not price_col:
        # Buscar columnas numéricas
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            price_col = numeric_cols[0]
        else:
            # Intentar convertir columnas a numéricas
            for col in df.columns:
                try:
                    numeric_series = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''), errors='coerce')
                    if numeric_series.notna().sum() > len(df) * 0.1:  # Al menos 10% de valores numéricos
                        price_col = col
                        break
                except:
                    continue
    
    return hotel_col, price_col

# Función optimizada para buscar hotel en múltiples hojas
def search_hotel_in_sheets(client, spreadsheet_id, hotel_name, max_sheets=30):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        
        # Limitar el número de hojas a procesar
        worksheets = worksheets[:max_sheets]
        
        resultados = []
        precios_encontrados = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, worksheet in enumerate(worksheets):
            if precios_encontrados >= 30:
                break
                
            status_text.text(f"Procesando hoja {i+1}/{len(worksheets)}: {worksheet.title}")
            progress_bar.progress((i + 1) / len(worksheets))
            
            try:
                df = get_cached_sheet_data(worksheet)
                if df is None or df.empty:
                    continue
                
                hotel_col, price_col = detect_columns(df)
                
                if hotel_col and price_col:
                    # Buscar el hotel (búsqueda insensible a mayúsculas)
                    mask = df[hotel_col].astype(str).str.lower().str.contains(hotel_name.lower(), na=False)
                    hotel_data = df[mask]
                    
                    if not hotel_data.empty:
                        for _, row in hotel_data.iterrows():
                            try:
                                precio_val = str(row[price_col])
                                # Limpiar y convertir el precio
                                precio_limpio = pd.to_numeric(
                                    re.sub(r'[^\d.,]', '', precio_val).replace(',', '.'),
                                    errors='coerce'
                                )
                                
                                if not pd.isna(precio_limpio) and precio_limpio > 0:
                                    resultados.append({
                                        'hoja': worksheet.title,
                                        'hotel': row[hotel_col],
                                        'precio': precio_limpio,
                                        'fecha_hoja': worksheet.title
                                    })
                                    precios_encontrados += 1
                                    
                                    if precios_encontrados >= 30:
                                        break
                            except Exception as e:
                                continue
            except Exception as e:
                continue
        
        progress_bar.empty()
        status_text.empty()
        
        return resultados
        
    except Exception as e:
        st.error(f"Error en la búsqueda: {e}")
        return []

# Función para calcular métricas de los resultados
def calculate_hotel_metrics(resultados):
    if not resultados:
        return None
    
    precios = [r['precio'] for r in resultados]
    
    return {
        'total_hojas_revisadas': len(set(r['hoja'] for r in resultados)),
        'total_precios_encontrados': len(precios),
        'precio_minimo': min(precios),
        'precio_maximo': max(precios),
        'suma_total': sum(precios),
        'promedio': sum(precios) / len(precios) if precios else 0,
        'hotel_nombre': resultados[0]['hotel'] if resultados else 'N/A'
    }

# Interfaz principal de la aplicación
def main():
    # Selector de ubicación en el sidebar
    st.sidebar.header("📍 Selecciona Ubicación")
    ubicacion = st.sidebar.radio("Ubicación:", ["Mérida", "Tuxtla"], index=0)
    
    spreadsheet_id = SHEET_IDS[ubicacion]
    
    # Obtener cliente de Google Sheets
    client = get_cached_client()
    
    if not client:
        st.error("No se pudo conectar a Google Sheets. Verifica la configuración.")
        return
    
    # Barra de búsqueda de hoteles
    st.header("🔍 Búsqueda de Hotel")
    hotel_busqueda = st.text_input(
        "Ingresa el nombre del hotel a buscar:",
        placeholder="Ej: Hilton, Marriott, Holiday Inn...",
        help="Buscará el hotel en las últimas 30 hojas disponibles"
    )
    
    if hotel_busqueda.strip():
        with st.spinner(f"Buscando '{hotel_busqueda}' en las últimas 30 hojas..."):
            resultados = search_hotel_in_sheets(client, spreadsheet_id, hotel_busqueda, 30)
        
        if resultados:
            metrics = calculate_hotel_metrics(resultados)
            
            if metrics:
                st.success(f"✅ Encontrados {metrics['total_precios_encontrados']} precios para '{metrics['hotel_nombre']}' en {metrics['total_hojas_revisadas']} hojas")
                
                # Mostrar métricas
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Precio Mínimo", f"${metrics['precio_minimo']:,.2f}")
                
                with col2:
                    st.metric("Precio Máximo", f"${metrics['precio_maximo']:,.2f}")
                
                with col3:
                    st.metric("Suma Total", f"${metrics['suma_total']:,.2f}")
                
                with col4:
                    st.metric("Promedio", f"${metrics['promedio']:,.2f}")
                
                # Detalles del cálculo
                with st.expander("📊 Detalles del análisis"):
                    st.write(f"**Hotel encontrado:** {metrics['hotel_nombre']}")
                    st.write(f"**Total de hojas revisadas:** {metrics['total_hojas_revisadas']}")
                    st.write(f"**Total de precios encontrados:** {metrics['total_precios_encontrados']}")
                    st.write(f"**Fórmula del promedio:** Suma total / Cantidad de precios")
                    st.write(f"**Cálculo:** ${metrics['suma_total']:,.2f} / {metrics['total_precios_encontrados']} = ${metrics['promedio']:,.2f}")
                
                # Mostrar resultados detallados
                st.subheader("📋 Precios Encontrados")
                resultados_df = pd.DataFrame(resultados)
                st.dataframe(
                    resultados_df[['hoja', 'hotel', 'precio']],
                    use_container_width=True,
                    height=300
                )
                
                # Gráfico de precios
                st.subheader("📈 Distribución de Precios")
                if len(resultados) > 1:
                    try:
                        # Crear un gráfico de dispersión para ver la distribución
                        chart_data = resultados_df[['hoja', 'precio']].copy()
                        chart_data['hoja_num'] = range(len(chart_data))
                        st.line_chart(chart_data.set_index('hoja_num')['precio'])
                    except:
                        st.info("No se pudo generar el gráfico de distribución")
            else:
                st.warning("Se encontraron resultados pero no se pudieron calcular las métricas.")
        else:
            st.warning(f"No se encontró el hotel '{hotel_busqueda}' en las últimas 30 hojas.")
            st.info("💡 Sugerencia: Intenta con un nombre más general o verifica la ortografía.")
    
    # Sección de análisis de hojas individuales
    st.header("📊 Análisis de Hoja Individual")
    
    with st.spinner("Cargando hojas disponibles..."):
        sheets_dict = get_cached_sheets(client, spreadsheet_id)
    
    if sheets_dict:
        sheet_names = list(sheets_dict.keys())
        
        st.sidebar.header("📋 Selecciona Hoja")
        selected_sheet_name = st.sidebar.selectbox(
            "Hoja:",
            sheet_names,
            index=len(sheet_names)-1 if sheet_names else 0
        )
        
        with st.spinner(f"Cargando {selected_sheet_name}..."):
            selected_sheet = sheets_dict[selected_sheet_name]
            df = get_cached_sheet_data(selected_sheet)
        
        if df is not None and not df.empty:
            st.subheader(f"Análisis de: {selected_sheet_name}")
            
            hotel_col, price_col = detect_columns(df)
            
            if hotel_col and price_col:
                st.success(f"✅ Columnas detectadas: Hotel → {hotel_col}, Precio → {price_col}")
                
                # Análisis de precios de la hoja actual
                try:
                    df['precio_limpio'] = pd.to_numeric(
                        df[price_col].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''),
                        errors='coerce'
                    )
                    
                    precios_validos = df['precio_limpio'].dropna()
                    
                    if len(precios_validos) > 0:
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Precio Mínimo", f"${precios_validos.min():,.2f}")
                        
                        with col2:
                            st.metric("Precio Máximo", f"${precios_validos.max():,.2f}")
                        
                        with col3:
                            st.metric("Suma Total", f"${precios_validos.sum():,.2f}")
                        
                        with col4:
                            st.metric("Promedio", f"${precios_validos.mean():,.2f}")
                    
                    # Mostrar top 10 hoteles más caros y más baratos
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("🏨 Top 10 Hoteles Más Caros")
                        top_caros = df.nlargest(10, 'precio_limpio')[['precio_limpio', hotel_col]].copy()
                        top_caros['precio_limpio'] = top_caros['precio_limpio'].apply(lambda x: f"${x:,.2f}")
                        st.dataframe(top_caros.rename(columns={'precio_limpio': 'Precio', hotel_col: 'Hotel'}), height=300)
                    
                    with col2:
                        st.subheader("🏨 Top 10 Hoteles Más Baratos")
                        top_baratos = df.nsmallest(10, 'precio_limpio')[['precio_limpio', hotel_col]].copy()
                        top_baratos['precio_limpio'] = top_baratos['precio_limpio'].apply(lambda x: f"${x:,.2f}")
                        st.dataframe(top_baratos.rename(columns={'precio_limpio': 'Precio', hotel_col: 'Hotel'}), height=300)
                
                except Exception as e:
                    st.error(f"Error en análisis de precios: {e}")
            
            # Mostrar datos completos
            st.subheader("📋 Datos Completos de la Hoja")
            st.dataframe(df, use_container_width=True, height=400)
            
        else:
            st.warning("La hoja seleccionada está vacía o no se pudieron cargar los datos.")
    else:
        st.error("No se pudieron cargar las hojas. Verifica los permisos.")

# Información adicional
st.sidebar.header("ℹ️ Información")
st.sidebar.info("""
**Búsqueda de Hoteles:**
- Busca en las últimas 30 hojas
- Calcula precios mínimo, máximo y promedio
- Muestra la distribución de precios
""")

# Ejecutar la aplicación
if __name__ == "__main__":
    main()

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios de hoteles • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
