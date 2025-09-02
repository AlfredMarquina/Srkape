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
    "Mérida": "13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU",
    "Madrid": "16DyY1PtkBTWMVd3Yj4cxA77X9En5GM5HGNZlF95wJBI",
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

# Función para buscar hotel en múltiples hojas
def search_hotel_in_sheets(client, spreadsheet_id, hotel_name, max_sheets=60):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        
        # Ordenar hojas por fecha (asumiendo que los nombres contienen fechas)
        dated_sheets = []
        for ws in worksheets:
            sheet_name = ws.title.lower()
            # Buscar patrones de fecha en el nombre de la hoja
            date_patterns = [
                r'\d{2}[-/]\d{2}[-/]\d{4}',  # DD-MM-YYYY
                r'\d{4}[-/]\d{2}[-/]\d{2}',  # YYYY-MM-DD
                r'\d{2}[-/]\d{2}[-/]\d{2}',  # DD-MM-YY
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, sheet_name)
                if match:
                    dated_sheets.append((ws, match.group()))
                    break
            else:
                # Si no encuentra fecha, usar el nombre como está
                dated_sheets.append((ws, sheet_name))
        
        # Ordenar por fecha (las más recientes primero)
        dated_sheets.sort(key=lambda x: x[1], reverse=True)
        
        # Tomar las últimas max_sheets hojas
        recent_sheets = dated_sheets[:max_sheets]
        
        resultados = []
        precios_encontrados = 0
        
        for ws, date_str in recent_sheets:
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
        
        return resultados, precios_encontrados
        
    except Exception as e:
        st.error(f"Error en la búsqueda: {e}")
        return [], 0

# Función para calcular métricas de los resultados
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

# Función para obtener el top 10 de hoteles por precio
def get_top_hotels(client, spreadsheet_id, num_sheets=10, top_type="min"):
    """
    Obtiene el top 10 de hoteles con menor o mayor precio
    top_type: "min" para menor precio, "max" para mayor precio
    """
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        
        # Ordenar hojas por fecha (más recientes primero)
        dated_sheets = []
        for ws in worksheets:
            sheet_name = ws.title.lower()
            date_patterns = [
                r'\d{2}[-/]\d{2}[-/]\d{4}', r'\d{4}[-/]\d{2}[-/]\d{2}', r'\d{2}[-/]\d{2}[-/]\d{2}'
            ]
            
            date_found = None
            for pattern in date_patterns:
                match = re.search(pattern, sheet_name)
                if match:
                    date_found = match.group()
                    break
            
            dated_sheets.append((ws, date_found or sheet_name))
        
        dated_sheets.sort(key=lambda x: x[1], reverse=True)
        recent_sheets = dated_sheets[:num_sheets]
        
        all_hotels = []
        
        for ws, date_str in recent_sheets:
            try:
                df = get_sheet_data(ws)
                if df is not None and not df.empty:
                    hotel_col, price_col = detect_columns(df)
                    
                    if hotel_col and price_col:
                        # Procesar cada fila
                        for _, row in df.iterrows():
                            try:
                                hotel_name = str(row[hotel_col]).strip()
                                if not hotel_name or hotel_name.lower() in ['nan', 'none', '']:
                                    continue
                                
                                # Limpiar y convertir precio
                                price_str = str(row[price_col])
                                price_clean = re.sub(r'[^\d.]', '', price_str)
                                precio = float(price_clean) if price_clean else None
                                
                                if precio and precio > 0 and hotel_name:
                                    all_hotels.append({
                                        'hotel': hotel_name,
                                        'precio': precio,
                                        'hoja': ws.title,
                                        'fecha': date_str
                                    })
                            except:
                                continue
            except:
                continue
        
        # Agrupar por hotel y calcular precio promedio
        hotel_stats = {}
        for hotel_data in all_hotels:
            hotel_name = hotel_data['hotel']
            if hotel_name not in hotel_stats:
                hotel_stats[hotel_name] = {
                    'precios': [],
                    'hojas': set(),
                    'ultima_hoja': hotel_data['hoja']
                }
            hotel_stats[hotel_name]['precios'].append(hotel_data['precio'])
            hotel_stats[hotel_name]['hojas'].add(hotel_data['hoja'])
        
        # Calcular promedio por hotel
        hotel_ranking = []
        for hotel_name, stats in hotel_stats.items():
            if stats['precios']:
                avg_price = sum(stats['precios']) / len(stats['precios'])
                hotel_ranking.append({
                    'hotel': hotel_name,
                    'precio_promedio': avg_price,
                    'precio_min': min(stats['precios']),
                    'precio_max': max(stats['precios']),
                    'muestras': len(stats['precios']),
                    'hojas': len(stats['hojas']),
                    'ultima_hoja': stats['ultima_hoja']
                })
        
        # Ordenar según el tipo de top
        if top_type == "min":
            hotel_ranking.sort(key=lambda x: x['precio_promedio'])
        else:  # max
            hotel_ranking.sort(key=lambda x: x['precio_promedio'], reverse=True)
        
        return hotel_ranking[:10]  # Top 10
        
    except Exception as e:
        st.error(f"Error obteniendo top hoteles: {e}")
        return []

# Función para mostrar los tops en la interfaz
def display_top_hotels(client, spreadsheet_id, ubicacion):
    st.header("🏆 Top 10 Hoteles")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 Top 10 Menor Precio")
        with st.spinner("Buscando hoteles más económicos..."):
            top_min = get_top_hotels(client, spreadsheet_id, 10, "min")
        
        if top_min:
            min_df = pd.DataFrame(top_min)
            min_df['ranking'] = range(1, len(min_df) + 1)
            min_df = min_df[['ranking', 'hotel', 'precio_promedio', 'muestras', 'hojas', 'ultima_hoja']]
            min_df.columns = ['#', 'Hotel', 'Precio Promedio', 'Muestras', 'Hojas', 'Última Hoja']
            
            # Formatear precios
            min_df['Precio Promedio'] = min_df['Precio Promedio'].apply(lambda x: f"${x:,.2f}")
            
            st.dataframe(
                min_df,
                use_container_width=True,
                height=400,
                hide_index=True
            )
            
            # Gráfico de barras
            try:
                chart_data = min_df.copy()
                chart_data['Precio Numérico'] = [x['precio_promedio'] for x in top_min]
                st.bar_chart(chart_data.set_index('Hotel')['Precio Numérico'])
            except:
                pass
        else:
            st.info("No se encontraron datos para el top de menores precios")
    
    with col2:
        st.subheader("💎 Top 10 Mayor Precio")
        with st.spinner("Buscando hoteles más caros..."):
            top_max = get_top_hotels(client, spreadsheet_id, 10, "max")
        
        if top_max:
            max_df = pd.DataFrame(top_max)
            max_df['ranking'] = range(1, len(max_df) + 1)
            max_df = max_df[['ranking', 'hotel', 'precio_promedio', 'muestras', 'hojas', 'ultima_hoja']]
            max_df.columns = ['#', 'Hotel', 'Precio Promedio', 'Muestras', 'Hojas', 'Última Hoja']
            
            # Formatear precios
            max_df['Precio Promedio'] = max_df['Precio Promedio'].apply(lambda x: f"${x:,.2f}")
            
            st.dataframe(
                max_df,
                use_container_width=True,
                height=400,
                hide_index=True
            )
            
            # Gráfico de barras
            try:
                chart_data = max_df.copy()
                chart_data['Precio Numérico'] = [x['precio_promedio'] for x in top_max]
                st.bar_chart(chart_data.set_index('Hotel')['Precio Numérico'])
            except:
                pass
        else:
            st.info("No se encontraron datos para el top de mayores precios")

# Función para mostrar estadísticas generales
def display_hotel_statistics(client, spreadsheet_id):
    st.header("📈 Estadísticas Generales de Hoteles")
    
    with st.spinner("Calculando estadísticas..."):
        top_min = get_top_hotels(client, spreadsheet_id, 20, "min")
        top_max = get_top_hotels(client, spreadsheet_id, 20, "max")
    
    if top_min and top_max:
        # Calcular estadísticas generales
        all_prices = []
        for hotel in top_min + top_max:
            all_prices.append(hotel['precio_promedio'])
        
        if all_prices:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Precio Promedio General", f"${sum(all_prices)/len(all_prices):,.2f}")
            
            with col2:
                st.metric("Precio Más Bajo", f"${min(all_prices):,.2f}")
            
            with col3:
                st.metric("Precio Más Alto", f"${max(all_prices):,.2f}")
            
            with col4:
                st.metric("Rango de Precios", f"${max(all_prices)-min(all_prices):,.2f}")
            
            # Distribución de precios
            st.subheader("📊 Distribución de Precios")
            price_df = pd.DataFrame({'Precio': all_prices})
            st.bar_chart(price_df, x='Precio')

# Selector de ubicación en el sidebar
st.sidebar.header("📍 Selecciona Ubicación")
ubicacion = st.sidebar.radio("Ubicación:", ["Mérida", "Madrid", "Tuxtla"], index=0)

spreadsheet_id = SHEET_IDS[ubicacion]

# Obtener cliente de Google Sheets
client = setup_gspread()

# Barra de búsqueda de hoteles
st.header("🔍 Búsqueda de Hotel")
hotel_busqueda = st.text_input(
    "Ingresa el nombre del hotel a buscar:",
    placeholder="Ej: Hilton, Marriott, Holiday Inn...",
    help="Buscará el hotel en las últimas 30 Dias disponibles"
)

if hotel_busqueda and client:
    with st.spinner(f"Buscando '{hotel_busqueda}' en los últimos 30 Dias..."):
        resultados, precios_encontrados = search_hotel_in_sheets(client, spreadsheet_id, hotel_busqueda, 60)
    
    if resultados:
        metrics = calculate_hotel_metrics(resultados)
        
        if metrics:
            st.success(f"✅ Encontrados {metrics['total_precios_encontrados']} precios en {metrics['total_hojas_revisadas']} hojas")
            
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
                st.write(f"**Hotel buscado:** {hotel_busqueda}")
                st.write(f"**Total de hojas revisadas:** {metrics['total_hojas_revisadas']}")
                st.write(f"**Total de precios encontrados:** {metrics['total_precios_encontrados']}")
                st.write(f"**Rango de fechas:** {metrics['primer_hoja']} - {metrics['ultima_hoja']}")
                st.write(f"**Fórmula del promedio:** Suma total / Cantidad de precios")
                st.write(f"**Cálculo:** ${metrics['suma_total']:,.2f} / {metrics['total_precios_encontrados']} = ${metrics['promedio']:,.2f}")
            
            # Mostrar resultados detallados
            st.subheader("📋 Precios Encontrados")
            resultados_df = pd.DataFrame(resultados)
            st.dataframe(
                resultados_df[['hoja', 'hotel', 'precio', 'fecha_hoja']],
                use_container_width=True,
                height=300
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
        st.warning(f"No se encontró el hotel '{hotel_busqueda}' en las últimas 30 hojas.")

# Sección de análisis de hojas individuales (código anterior)
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

# Sección de Top 10 Hoteles
st.markdown("---")
if client:
    display_top_hotels(client, spreadsheet_id, ubicacion)
    
    # Opcional: Estadísticas generales
    with st.expander("📈 Ver Estadísticas Generales Detalladas"):
        display_hotel_statistics(client, spreadsheet_id)

# Información adicional
st.sidebar.header("ℹ️ Información")
st.sidebar.info("""
**Búsqueda de Hoteles:**
- Busca en las últimas 30 hojas
- Calcula precios mínimo, máximo y promedio
- Muestra la evolución temporal

**Top 10 Hoteles:**
- Muestra los 10 hoteles más económicos
- Muestra los 10 hoteles más caros
- Basado en las últimas 10 hojas
""")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios de hoteles • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)

