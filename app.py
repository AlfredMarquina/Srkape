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

# IDs de las hojas de cálculo - VERIFICAR ESTOS IDs
SHEET_IDS = {
    "Mérida": "13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU",
    "Tuxtla": "1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho"
}

# Configuración para acceso a Google Sheets usando Secrets
def setup_gspread():
    try:
        if 'gcp_service_account' not in st.secrets:
            st.error("❌ No se encontraron credenciales en st.secrets")
            st.info("""
            **Para configurar las credenciales:**
            1. Ve a la configuración de tu app en Streamlit Cloud
            2. Agrega las credenciales de servicio en 'Secrets'
            3. Asegúrate de que el service account tenga acceso a las hojas
            """)
            return None
            
        # Método más simple y robusto
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        client = gspread.authorize(credentials)
        
        # Verificar que la autenticación funciona
        try:
            client.list_spreadsheet_files()
            st.sidebar.success("✅ Autenticación exitosa")
            return client
        except Exception as auth_error:
            st.error(f"❌ Error de autenticación: {auth_error}")
            return None
            
    except Exception as e:
        st.error(f"❌ Error configurando Google Sheets: {e}")
        return None

# Función para verificar acceso al spreadsheet
def verify_spreadsheet_access(client, spreadsheet_id):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        # Intentar acceder a la información básica
        spreadsheet.title
        return True, f"✅ Acceso confirmado a: {spreadsheet.title}"
    except gspread.SpreadsheetNotFound:
        return False, "❌ Spreadsheet no encontrado. Verifica el ID."
    except gspread.exceptions.APIError as api_error:
        return False, f"❌ Error de API: {api_error}"
    except Exception as e:
        return False, f"❌ Error de acceso: {e}"

# Función para obtener todas las hojas de un spreadsheet
def get_all_sheets(spreadsheet_id, client):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        
        if not worksheets:
            st.warning("⚠️ El spreadsheet no contiene hojas")
            return None
            
        return {f"{ws.title}": ws for ws in worksheets}
        
    except gspread.SpreadsheetNotFound:
        st.error("❌ Spreadsheet no encontrado. Verifica:")
        st.error("1. El ID del spreadsheet")
        st.error("2. Que el service account tenga acceso")
        st.error("3. Que el spreadsheet exista")
        return None
    except gspread.exceptions.APIError as api_error:
        st.error(f"❌ Error de API de Google: {api_error}")
        return None
    except Exception as e:
        st.error(f"❌ Error al acceder al spreadsheet: {e}")
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
    hotel_keywords = ['hotel', 'nombre', 'name', 'establecimiento', 'property']
    price_keywords = ['precio', 'price', 'costo', 'cost', 'valor', 'value', 'monto', 'amount', 'importe']
    
    hotel_col = None
    price_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        
        if not hotel_col and any(keyword in col_lower for keyword in hotel_keywords):
            hotel_col = col
        
        if not price_col and any(keyword in col_lower for keyword in price_keywords):
            try:
                numeric_test = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''), errors='coerce')
                if numeric_test.notna().sum() > 0:
                    price_col = col
            except:
                continue
    
    # Fallbacks
    if not hotel_col:
        for col in df.columns:
            if df[col].dtype == 'object' and len(df[col].astype(str).str.strip().unique()) > 1:
                hotel_col = col
                break
    
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
        
        dated_sheets = []
        for ws in worksheets:
            sheet_name = ws.title.lower()
            date_patterns = [
                r'\d{2}[-/]\d{2}[-/]\d{4}',
                r'\d{4}[-/]\d{2}[-/]\d{2}',
                r'\d{2}[-/]\d{2}[-/]\d{2}',
            ]
            
            date_found = None
            for pattern in date_patterns:
                match = re.search(pattern, sheet_name)
                if match:
                    date_found = match.group()
                    break
            
            dated_sheets.append((ws, date_found or sheet_name))
        
        dated_sheets.sort(key=lambda x: x[1], reverse=True)
        
        resultados = []
        precios_encontrados = 0
        hojas_revisadas = 0
        
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
    
    ultimos_30 = resultados[:30]
    precios = [r['precio'] for r in ultimos_30]
    
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

# Función original para calcular métricas
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

# Verificar acceso si el cliente está disponible
if client:
    st.sidebar.header("🔍 Verificación de Acceso")
    access_status, message = verify_spreadsheet_access(client, spreadsheet_id)
    st.sidebar.info(message)
    
    if "no encontrado" in message.lower() or "error" in message.lower():
        st.sidebar.error("""
        **Solución:**
        1. Verifica el ID del spreadsheet
        2. Comparte el spreadsheet con el service account
        3. Email del service account: revisa en st.secrets
        """)

# Barra de búsqueda de hoteles
st.header("🔍 Búsqueda de Hotel")

if not client:
    st.warning("""
    ⚠️ **Configuración requerida:**
    
    1. **Agrega credenciales** en Streamlit Secrets
    2. **Comparte los spreadsheets** con el service account
    3. **Verifica los IDs** de los spreadsheets
    
    **Email del service account:** Revisa en tus credenciales de Google Cloud
    """)
else:
    hotel_busqueda = st.text_input(
        "Ingresa el nombre del hotel a buscar:",
        placeholder="Ej: Hilton, Marriott, Holiday Inn...",
        help="Buscará el hotel hasta encontrar 30 precios válidos"
    )

    if hotel_busqueda:
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
                        st.write(f"**Rango de fechas:** {metrics.get('primer_hoja', '')} - {metrics.get('ultima_hoja', '')}")
                        st.write(f"**Fórmula del promedio:** Suma total / {precios_encontrados}")
                        st.write(f"**Cálculo:** ${metrics['suma_total']:,.2f} / {precios_encontrados} = ${metrics['promedio']:,.2f}")
                
                st.subheader("📋 Precios Encontrados")
                resultados_df = pd.DataFrame(resultados)
                st.dataframe(
                    resultados_df[['hoja', 'hotel', 'precio', 'fecha_hoja']],
                    use_container_width=True,
                    height=400
                )
                
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
            
            st.dataframe(df, use_container_width=True, height=300)
            
        else:
            st.warning("La hoja seleccionada está vacía.")
    else:
        st.error("No se pudieron cargar las hojas.")

# Información adicional
st.sidebar.header("ℹ️ Configuración Requerida")
st.sidebar.info("""
**Para que funcione correctamente:**

1. **Credenciales** en Streamlit Secrets
2. **Compartir spreadsheets** con el service account
3. **IDs correctos** de los spreadsheets
4. **Permisos** de lectura en Google Sheets
""")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios de hoteles • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
