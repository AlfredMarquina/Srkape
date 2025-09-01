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
    hotel_keywords = ['hotel', 'nombre', 'name', 'establecimiento', 'property', 'alojamiento']
    price_keywords = ['precio', 'price', 'costo', 'cost', 'valor', 'value', 'monto', 'amount', 'importe', 'tarifa']
    
    hotel_col = None
    price_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        
        # Detectar columna de hotel
        if not hotel_col and any(keyword in col_lower for keyword in hotel_keywords):
            hotel_col = col
        
        # Detectar columna de precio
        if not price_col and any(keyword in col_lower for keyword in price_keywords):
            try:
                numeric_test = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''), errors='coerce')
                if numeric_test.notna().sum() > 0:
                    price_col = col
            except:
                continue
    
    # Búsqueda alternativa si no se detecta por nombre
    if not hotel_col:
        for col in df.columns:
            if df[col].dtype == 'object' and df[col].astype(str).str.len().max() > 3:
                hotel_col = col
                break
    
    if not price_col:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            price_col = numeric_cols[0]
        else:
            # Intentar convertir todas las columnas
            for col in df.columns:
                try:
                    numeric_vals = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''), errors='coerce')
                    if numeric_vals.notna().sum() > len(df) * 0.3:  # Al menos 30% de valores numéricos
                        price_col = col
                        break
                except:
                    continue
    
    return hotel_col, price_col

# Función para buscar hotel hasta completar 30 precios
def search_hotel_until_30_prices(client, spreadsheet_id, hotel_name, max_precios=30):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        
        # Ordenar hojas intentando detectar fechas
        dated_sheets = []
        for ws in worksheets:
            sheet_name = ws.title.lower()
            date_patterns = [
                r'\d{2}[-/]\d{2}[-/]\d{4}', r'\d{4}[-/]\d{2}[-/]\d{2}', r'\d{2}[-/]\d{2}[-/]\d{2}',
                r'\d{2}[a-z]{3}\d{4}', r'\d{4}[a-z]{3}\d{2}', r'[a-z]{3}\d{2}\d{4}'
            ]
            
            date_found = None
            for pattern in date_patterns:
                match = re.search(pattern, sheet_name)
                if match:
                    date_found = match.group()
                    break
            
            dated_sheets.append((ws, date_found or sheet_name))
        
        # Ordenar por fecha (más recientes primero)
        dated_sheets.sort(key=lambda x: x[1], reverse=True)
        
        resultados = []
        precios_encontrados = 0
        hojas_revisadas = 0
        hojas_con_datos = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Buscar en hojas hasta completar 30 precios o revisar todas
        for i, (ws, date_str) in enumerate(dated_sheets):
            if precios_encontrados >= max_precios:
                break
                
            hojas_revisadas += 1
            status_text.text(f"Revisando hoja {i+1}/{len(dated_sheets)} - {hojas_revisadas} hojas revisadas, {precios_encontrados}/30 precios encontrados")
            progress_bar.progress(min(i / len(dated_sheets), 1.0))
            
            try:
                df = get_sheet_data(ws)
                if df is not None and not df.empty:
                    hojas_con_datos += 1
                    hotel_col, price_col = detect_columns(df)
                    
                    if hotel_col and price_col:
                        # Búsqueda flexible del hotel
                        mask = (
                            df[hotel_col].astype(str).str.lower().str.contains(hotel_name.lower(), na=False) |
                            df[hotel_col].astype(str).str.lower().str.startswith(hotel_name.lower(), na=False) |
                            df[hotel_col].astype(str).str.lower().str.endswith(hotel_name.lower(), na=False)
                        )
                        
                        hotel_data = df[mask]
                        
                        if not hotel_data.empty:
                            for _, row in hotel_data.iterrows():
                                if precios_encontrados >= max_precios:
                                    break
                                    
                                try:
                                    precio_str = str(row[price_col])
                                    precio_limpio = pd.to_numeric(
                                        precio_str.replace(',', '.').replace('$', '').replace(' ', '').replace('USD', ''),
                                        errors='coerce'
                                    )
                                    
                                    if not pd.isna(precio_limpio) and precio_limpio > 0:
                                        resultados.append({
                                            'hoja': ws.title,
                                            'hotel': row[hotel_col],
                                            'precio_original': precio_str,
                                            'precio': precio_limpio,
                                            'fecha_hoja': date_str,
                                            'columna_hotel': hotel_col,
                                            'columna_precio': price_col
                                        })
                                        precios_encontrados += 1
                                except:
                                    continue
            except:
                continue
        
        progress_bar.empty()
        status_text.empty()
        
        return resultados, precios_encontrados, hojas_revisadas, hojas_con_datos
        
    except Exception as e:
        st.error(f"Error en la búsqueda: {e}")
        return [], 0, 0, 0

# Función para calcular métricas de los resultados
def calculate_hotel_metrics(resultados):
    if not resultados:
        return None
    
    precios = [r['precio'] for r in resultados if r['precio'] > 0]
    
    if not precios:
        return None
    
    precios_ordenados = sorted(precios)
    
    return {
        'total_hojas_revisadas': len(set(r['hoja'] for r in resultados)),
        'total_precios_encontrados': len(precios),
        'precio_minimo': min(precios),
        'precio_maximo': max(precios),
        'suma_total': sum(precios),
        'promedio': sum(precios) / len(precios),
        'mediana': precios_ordenados[len(precios_ordenados)//2] if precios_ordenados else 0,
        'primer_hoja': resultados[0]['hoja'] if resultados else '',
        'ultima_hoja': resultados[-1]['hoja'] if resultados else '',
        'rango_hojas': f"{resultados[0]['hoja']} - {resultados[-1]['hoja']}" if len(resultados) > 1 else resultados[0]['hoja'] if resultados else ''
    }

# Selector de ubicación en el sidebar
st.sidebar.header("📍 Selecciona Ubicación")
ubicacion = st.sidebar.radio("Ubicación:", ["Mérida", "Tuxtla"], index=0)

spreadsheet_id = SHEET_IDS[ubicacion]

# Obtener cliente de Google Sheets
client = setup_gspread()

# Barra de búsqueda de hoteles
st.header("🔍 Búsqueda Avanzada de Hotel")
hotel_busqueda = st.text_input(
    "Ingresa el nombre del hotel a buscar:",
    placeholder="Ej: Hilton, Marriott, Holiday Inn, Fiesta Americana...",
    help="Buscará en todas las hojas necesarias hasta encontrar 30 precios válidos"
)

if hotel_busqueda and client:
    with st.spinner(f"Iniciando búsqueda de '{hotel_busqueda}'..."):
        resultados, precios_encontrados, hojas_revisadas, hojas_con_datos = search_hotel_until_30_prices(
            client, spreadsheet_id, hotel_busqueda, 30
        )
    
    if resultados:
        metrics = calculate_hotel_metrics(resultados)
        
        if metrics:
            st.success(f"✅ Encontrados {metrics['total_precios_encontrados']} precios en {metrics['total_hojas_revisadas']} hojas")
            st.info(f"📊 Se revisaron {hojas_revisadas} hojas totales, {hojas_con_datos} con datos válidos")
            
            # Mostrar métricas principales
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Precio Mínimo", f"${metrics['precio_minimo']:,.2f}")
            
            with col2:
                st.metric("Precio Máximo", f"${metrics['precio_maximo']:,.2f}")
            
            with col3:
                st.metric("Suma Total", f"${metrics['suma_total']:,.2f}")
            
            with col4:
                st.metric("Promedio 30", f"${metrics['promedio']:,.2f}")
            
            # Métricas adicionales
            col5, col6, col7, col8 = st.columns(4)
            
            with col5:
                st.metric("Precios Encontrados", metrics['total_precios_encontrados'])
            
            with col6:
                st.metric("Hojas con Datos", metrics['total_hojas_revisadas'])
            
            with col7:
                st.metric("Mediana", f"${metrics['mediana']:,.2f}")
            
            with col8:
                st.metric("Rango", f"${metrics['precio_maximo'] - metrics['precio_minimo']:,.2f}")
            
            # Detalles del cálculo
            with st.expander("📝 Detalles Complejos del Análisis", expanded=True):
                st.write(f"**Hotel buscado:** `{hotel_busqueda}`")
                st.write(f"**Total de hojas revisadas:** {hojas_revisadas}")
                st.write(f"**Hojas con datos válidos:** {hojas_con_datos}")
                st.write(f"**Hojas con precios del hotel:** {metrics['total_hojas_revisadas']}")
                st.write(f"**Total de precios encontrados:** {metrics['total_precios_encontrados']}")
                st.write(f"**Rango de hojas:** {metrics['rango_hojas']}")
                
                st.write("---")
                st.write("**Fórmula del promedio:**")
                st.latex(rf"\text{{Promedio}} = \frac{{\sum \text{{precios}}}}{{\text{{cantidad}}}} = \frac{{{metrics['suma_total']:,.2f}}}{{{metrics['total_precios_encontrados']}}} = {metrics['promedio']:,.2f}")
                
                st.write("**Distribución de precios:**")
                precios_df = pd.DataFrame([r['precio'] for r in resultados], columns=['Precio'])
                st.write(precios_df['Precio'].describe())
            
            # Mostrar resultados detallados
            st.subheader("📋 Detalle de Precios Encontrados")
            resultados_df = pd.DataFrame(resultados)
            
            # Formatear para mejor visualización
            display_df = resultados_df[['hoja', 'hotel', 'precio_original', 'precio', 'fecha_hoja']].copy()
            display_df['precio'] = display_df['precio'].apply(lambda x: f"${x:,.2f}")
            
            st.dataframe(
                display_df,
                use_container_width=True,
                height=400,
                column_config={
                    "hoja": "Hoja",
                    "hotel": "Hotel",
                    "precio_original": "Precio Original",
                    "precio": "Precio Convertido",
                    "fecha_hoja": "Fecha Detectada"
                }
            )
            
            # Gráfico de evolución
            st.subheader("📈 Evolución Temporal de Precios")
            try:
                chart_df = resultados_df.copy()
                chart_df['numero_hoja'] = range(1, len(chart_df) + 1)
                
                tab1, tab2 = st.tabs(["Línea Temporal", "Distribución"])
                
                with tab1:
                    st.line_chart(chart_df.set_index('numero_hoja')['precio'])
                
                with tab2:
                    st.bar_chart(chart_df['precio'])
                    
            except Exception as e:
                st.warning("No se pudo generar el gráfico de evolución")
            
            # Opción para descargar resultados
            csv = resultados_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Resultados Completos",
                data=csv,
                file_name=f"busqueda_{hotel_busqueda.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        else:
            st.warning("Se encontraron resultados pero no precios válidos para calcular métricas.")
    else:
        st.warning(f"No se encontró el hotel '{hotel_busqueda}' o no hay precios válidos en las hojas revisadas.")
        st.info("💡 Sugerencia: Intenta con un nombre más general o verifica la ortografía")

# Información adicional
st.sidebar.header("ℹ️ Acerca de la Búsqueda")
st.sidebar.info("""
**Características de la búsqueda:**
- Busca en TODAS las hojas necesarias
- Para cuando encuentra 30 precios válidos
- Detecta automáticamente columnas
- Conversión inteligente de formatos
- Búsqueda flexible por nombre
""")

st.sidebar.header("🔍 Tips de Búsqueda")
st.sidebar.info("""
**Para mejores resultados:**
- Usa nombres parciales: "Hilton" en lugar de "Hilton Garden Inn"
- Prueba variaciones: "Fiesta", "Fiesta Americana"
- Mayúsculas no importan
- La búsqueda es flexible
""")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
