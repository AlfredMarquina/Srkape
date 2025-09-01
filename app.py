import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime, timedelta
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
    "Mérida": "13tPaaJCX4o4HkxrRdPiuc5dq83Eh7-KU",
    "Tuxtla": "1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho"
}

# Configuración para acceso a Google Sheets usando Secrets
def setup_gspread():
    try:
        if 'gcp_service_account' not in st.secrets:
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
        st.error(f"Error al obtener datos: {e}")
        return None

# Función para detectar automáticamente columnas relevantes
def detect_columns(df):
    # Buscar columna de hotel
    hotel_keywords = ['hotel', 'nombre', 'name', 'establecimiento', 'property']
    price_keywords = ['precio', 'price', 'costo', 'cost', 'valor', 'value', 'monto', 'amount', 'importe']
    
    hotel_col = None
    price_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        
        # Detectar columna de hotel
        if not hotel_col and any(keyword in col_lower for keyword in hotel_keywords):
            hotel_col = col
        
        # Detectar columna de precio
        if not price_col and any(keyword in col_lower for keyword in price_keywords):
            # Verificar si contiene valores numéricos
            try:
                numeric_test = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''), errors='coerce')
                if numeric_test.notna().sum() > 0:
                    price_col = col
            except:
                continue
    
    # Si no se detecta por nombre, buscar la primera columna de texto para hotel
    if not hotel_col:
        for col in df.columns:
            if df[col].dtype == 'object' and len(df[col].astype(str).str.strip().unique()) > 1:
                hotel_col = col
                break
    
    # Si no se detecta por nombre, buscar la primera columna numérica para precio
    if not price_col:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            price_col = numeric_cols[0]
    
    return hotel_col, price_col

# Función para buscar hotel hasta obtener 30 precios válidos
def search_hotel_until_30_prices(client, spreadsheet_id, hotel_name, max_sheets_to_check=100):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        
        # Ordenar hojas por fecha (las más recientes primero)
        dated_sheets = []
        for ws in worksheets:
            sheet_name = ws.title.lower()
            # Buscar patrones de fecha en el nombre de la hoja
            date_patterns = [
                r'\d{2}[-/]\d{2}[-/]\d{4}',  # DD-MM-YYYY
                r'\d{4}[-/]\d{2}[-/]\d{2}',  # YYYY-MM-DD
                r'\d{2}[-/]\d{2}[-/]\d{2}',  # DD-MM-YY
            ]
            
            date_found = None
            for pattern in date_patterns:
                match = re.search(pattern, sheet_name)
                if match:
                    date_found = match.group()
                    break
            
            dated_sheets.append((ws, date_found or sheet_name))
        
        # Ordenar por fecha (las más recientes primero)
        dated_sheets.sort(key=lambda x: x[1], reverse=True)
        
        resultados = []
        precios_encontrados = 0
        hojas_revisadas = 0
        
        # Recorrer hojas hasta encontrar 30 precios o revisar todas
        for ws, date_str in dated_sheets:
            if precios_encontrados >= 30:
                break
                
            if hojas_revisadas >= max_sheets_to_check:
                break
                
            try:
                df = get_sheet_data(ws)
                if df is not None and not df.empty:
                    hotel_col, price_col = detect_columns(df)
                    
                    if hotel_col and price_col:
                        # Buscar el hotel (búsqueda insensible a mayúsculas)
                        mask = df[hotel_col].astype(str).str.lower().str.contains(hotel_name.lower(), na=False)
                        hotel_data = df[mask]
                        
                        if not hotel_data.empty:
                            for _, row in hotel_data.iterrows():
                                if precios_encontrados >= 30:
                                    break
                                    
                                try:
                                    precio = pd.to_numeric(
                                        str(row[price_col]).replace(',', '.').replace('$', '').replace(' ', ''),
                                        errors='coerce'
                                    )
                                    
                                    if not pd.isna(precio) and precio > 0:
                                        resultados.append({
                                            'hoja': ws.title,
                                            'hotel': row[hotel_col],
                                            'precio': precio,
                                            'fecha_hoja': date_str
                                        })
                                        precios_encontrados += 1
                                except:
                                    continue
            except:
                continue
            
            hojas_revisadas += 1
        
        return resultados, precios_encontrados, hojas_revisadas
        
    except Exception as e:
        st.error(f"Error en la búsqueda: {e}")
        return [], 0, 0

# Función para calcular métricas con exactamente 30 precios
def calculate_hotel_metrics_30(resultados):
    if not resultados or len(resultados) < 30:
        return None
    
    # Tomar exactamente los últimos 30 precios encontrados
    ultimos_30 = resultados[:30]  # Ya están ordenados de más reciente a más antiguo
    precios = [r['precio'] for r in ultimos_30]
    
    # Contar precios por hoja
    precios_por_hoja = {}
    for r in ultimos_30:
        if r['hoja'] in precios_por_hoja:
            precios_por_hoja[r['hoja']] += 1
        else:
            precios_por_hoja[r['hoja']] = 1
    
    return {
        'total_hojas_revisadas': len(set(r['hoja'] for r in ultimos_30)),
        'total_precios': len(precios),
        'precio_minimo': min(precios),
        'precio_maximo': max(precios),
        'suma_total': sum(precios),
        'promedio': sum(precios) / len(precios),
        'rango_fechas': f"{ultimos_30[-1]['fecha_hoja']} - {ultimos_30[0]['fecha_hoja']}",
        'precios_por_hoja': precios_por_hoja
    }

# Función original para calcular métricas (para cuando no hay 30 precios)
def calculate_hotel_metrics(resultados):
    if not resultados:
        return None
    
    precios = [r['precio'] for r in resultados if r['precio'] > 0]
    
    if not precios:
        return None
    
    return {
        'total_hojas_revisadas': len(set(r['hoja'] for r in resultados)),
        'total_precios_encontrados': len(precios),
        'precio_minimo': min(precios),
        'precio_maximo': max(precios),
        'suma_total': sum(precios),
        'promedio': sum(precios) / len(precios),
        'primer_hoja': resultados[0]['hoja'] if resultados else '',
        'ultima_hoja': resultados[-1]['hoja'] if resultados else ''
    }

# Selector de ubicación en el sidebar
st.sidebar.header("📍 Selecciona Ubicación")
ubicacion = st.sidebar.radio("Ubicación:", ["Mérida", "Tuxtla"], index=0)

spreadsheet_id = SHEET_IDS[ubicacion]

# Obtener cliente de Google Sheets
client = setup_gspread()

# Barra de búsqueda de hoteles
st.header("🔍 Búsqueda de Hotel")
hotel_busqueda = st.text_input(
    "Ingresa el nombre del hotel a buscar:",
    placeholder="Ej: Hilton, Marriott, Holiday Inn...",
    help="Buscará el hotel hasta encontrar 30 precios válidos"
)

if hotel_busqueda and client:
    with st.spinner(f"Buscando '{hotel_busqueda}' hasta encontrar 30 precios..."):
        resultados, precios_encontrados, hojas_revisadas = search_hotel_until_30_prices(client, spreadsheet_id, hotel_busqueda, 100)
    
    if resultados:
        if precios_encontrados >= 30:
            st.success(f"✅ Encontrados 30 precios en {hojas_revisadas} hojas revisadas")
            metrics = calculate_hotel_metrics_30(resultados)
        else:
            st.warning(f"⚠️ Solo se encontraron {precios_encontrados} precios (se necesitan 30)")
            metrics = calculate_hotel_metrics(resultados)
        
        if metrics:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Precio Mínimo", f"${metrics['precio_minimo']:,.2f}")
            
            with col2:
                st.metric("Precio Máximo", f"${metrics['precio_maximo']:,.2f}")
            
            with col3:
                st.metric("Suma Total", f"${metrics['suma_total']:,.2f}")
            
            with col4:
                if precios_encontrados >= 30:
                    st.metric("Promedio (30)", f"${metrics['promedio']:,.2f}")
                else:
                    st.metric("Promedio", f"${metrics['promedio']:,.2f}")
            
            # Detalles del cálculo
            with st.expander("📊 Detalles del análisis"):
                st.write(f"**Hotel buscado:** {hotel_busqueda}")
                st.write(f"**Total de hojas revisadas:** {hojas_revisadas}")
                st.write(f"**Total de precios encontrados:** {precios_encontrados}")
                
                if precios_encontrados >= 30:
                    st.write(f"**Precios usados para el promedio:** 30")
                    st.write(f"**Rango de fechas:** {metrics['rango_fechas']}")
                    st.write(f"**Fórmula del promedio:** Suma total / 30")
                    st.write(f"**Cálculo:** ${metrics['suma_total']:,.2f} / 30 = ${metrics['promedio']:,.2f}")
                    
                    st.write("**Distribución de precios por hoja:**")
                    for hoja, cantidad in metrics['precios_por_hoja'].items():
                        st.write(f"  - {hoja}: {cantidad} precios")
                else:
                    st.write(f"**Precios usados para el promedio:** {precios_encontrados}")
                    st.write(f"**Rango de fechas:** {metrics['primer_hoja']} - {metrics['ultima_hoja']}")
                    st.write(f"**Fórmula del promedio:** Suma total / {precios_encontrados}")
                    st.write(f"**Cálculo:** ${metrics['suma_total']:,.2f} / {precios_encontrados} = ${metrics['promedio']:,.2f}")
            
            # Mostrar resultados detallados
            st.subheader("📋 Precios Encontrados")
            resultados_df = pd.DataFrame(resultados)
            st.dataframe(
                resultados_df[['hoja', 'hotel', 'precio', 'fecha_hoja']],
                use_container_width=True,
                height=400
            )
            
            # Gráfico de precios por hoja
            st.subheader("📈 Evolución de Precios")
            try:
                chart_data = resultados_df[['hoja', 'precio']].copy()
                chart_data['hoja'] = chart_data['hoja'].astype(str)
                st.line_chart(chart_data.set_index('hoja')['precio'])
            except:
                st.info("No se pudo generar el gráfico de evolución")
        
        else:
            st.warning("Se encontraron resultados pero no precios válidos.")
    else:
        st.warning(f"No se encontró el hotel '{hotel_busqueda}' en las hojas revisadas.")

# Sección de análisis de hojas individuales
st.header("📊 Análisis de Hoja Individual")

if client:
    with st.spinner("Cargando hojas disponibles..."):
        sheets_dict = get_all_sheets(spreadsheet_id, client)
    
    if sheets_dict:
        sheet_names = list(sheets_dict.keys())
        
        st.sidebar.header("📋 Selecciona Dia")
        selected_sheet_name = st.sidebar.selectbox(
            "Hoja:",
            sheet_names,
            index=len(sheet_names)-1 if sheet_names else 0
        )
        
        with st.spinner(f"Cargando {selected_sheet_name}..."):
            selected_sheet = sheets_dict[selected_sheet_name]
            df = get_sheet_data(selected_sheet)
        
        if df is not None and not df.empty:
            st.subheader(f"{selected_sheet_name}")
            
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
                
                except Exception as e:
                    st.error(f"Error en análisis de precios: {e}")
            
            # Mostrar datos
            st.dataframe(df, use_container_width=True, height=300)
            
        else:
            st.warning("La hoja seleccionada está vacía.")
    else:
        st.error("No se pudieron cargar las hojas.")

# Información adicional
st.sidebar.header("ℹ️ Información")
st.sidebar.info("""
**Búsqueda de Hoteles:**
- Busca hasta encontrar 30 precios válidos
- Calcula promedio de los últimos 30 precios
- Muestra distribución por hojas
- Ordena por fecha (más reciente primero)
""")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios de hoteles • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
