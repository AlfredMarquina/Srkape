import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime, timedelta
import numpy as np
import re
import json

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
        # Verificar si existen secrets
        if not st.secrets:
            st.error("❌ No se encontraron secrets configurados")
            return None
            
        # Diferentes formas de acceder a las credenciales
        creds_dict = None
        
        # Método 1: Credenciales directas en secrets
        if 'gcp_service_account' in st.secrets:
            try:
                creds_dict = dict(st.secrets["gcp_service_account"])
                # Asegurar que la private key tenga el formato correcto
                if 'private_key' in creds_dict:
                    creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
            except Exception as e:
                st.error(f"❌ Error procesando credenciales: {e}")
                return None
        
        # Método 2: JSON string en secrets
        elif 'google_credentials' in st.secrets:
            try:
                creds_dict = json.loads(st.secrets["google_credentials"])
            except json.JSONDecodeError:
                st.error("❌ Error: google_credentials no es un JSON válido")
                return None
        
        # Método 3: Variables individuales en secrets
        elif all(key in st.secrets for key in ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']):
            try:
                creds_dict = {
                    "type": st.secrets["type"],
                    "project_id": st.secrets["project_id"],
                    "private_key_id": st.secrets["private_key_id"],
                    "private_key": st.secrets["private_key"].replace('\\n', '\n'),
                    "client_email": st.secrets["client_email"],
                    "client_id": st.secrets.get("client_id", ""),
                    "auth_uri": st.secrets.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
                    "token_uri": st.secrets.get("token_uri", "https://oauth2.googleapis.com/token"),
                }
            except Exception as e:
                st.error(f"❌ Error creando credenciales: {e}")
                return None
        
        else:
            st.error("""
            ❌ No se encontraron credenciales válidas en secrets.
            
            **Formas de configurar:**
            
            1. **gcp_service_account** (recomendado):
            ```toml
            [gcp_service_account]
            type = "service_account"
            project_id = "tu-project-id"
            private_key_id = "tu-private-key-id"
            private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
            client_email = "tu-email@project.iam.gserviceaccount.com"
            ```
            
            2. **google_credentials** (JSON string)
            3. **Variables individuales**
            """)
            return None

        # Crear credenciales
        try:
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
            )
            client = gspread.authorize(credentials)
            
            # Verificar que funciona
            try:
                client.list_spreadsheet_files()
                st.sidebar.success("✅ Autenticación exitosa con Google Sheets")
                return client
            except Exception as auth_error:
                st.error(f"❌ Error de autenticación: {auth_error}")
                return None
                
        except Exception as e:
            st.error(f"❌ Error creando credenciales: {e}")
            return None

    except Exception as e:
        st.error(f"❌ Error configurando Google Sheets: {e}")
        return None

# Función para verificar acceso al spreadsheet
def verify_spreadsheet_access(client, spreadsheet_id):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        spreadsheet.title  # Intentar acceder al título
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
        
    except Exception as e:
        st.error(f"❌ Error al acceder al spreadsheet: {e}")
        return None

# Función para obtener datos de una hoja específica
def get_sheet_data(worksheet):
    try:
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"❌ Error al obtener datos: {e}")
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
                numeric_test = pd.to_numeric(
                    df[col].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''), 
                    errors='coerce'
                )
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
        else:
            hotel_col = df.columns[0] if len(df.columns) > 0 else None
    
    if not price_col:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            price_col = numeric_cols[0]
        else:
            # Buscar cualquier columna que pueda contener números
            for col in df.columns:
                try:
                    numeric_test = pd.to_numeric(df[col].astype(str), errors='coerce')
                    if numeric_test.notna().sum() > 0:
                        price_col = col
                        break
                except:
                    continue
    
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
        st.error(f"❌ Error en la búsqueda: {e}")
        return [], 0, 0

# Función para calcular métricas
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

# Selector de ubicación
st.sidebar.header("📍 Selecciona Ubicación")
ubicacion = st.sidebar.radio("Ubicación:", ["Mérida", "Tuxtla"], index=0)
spreadsheet_id = SHEET_IDS[ubicacion]

# Obtener cliente
client = setup_gspread()

# Mostrar información de configuración
st.sidebar.header("⚙️ Configuración")
if client:
    st.sidebar.success("✅ Google Sheets conectado")
else:
    st.sidebar.error("❌ Google Sheets no configurado")

# Modo demo cuando no hay conexión
DEMO_MODE = client is None

if DEMO_MODE:
    st.warning("""
    🚧 **Modo Demo Activado**
    
    **Para usar todas las funciones:**
    1. Configura las credenciales de Google Sheets en Secrets
    2. Comparte los spreadsheets con el service account
    3. Recarga la aplicación
    
    **Formato de secrets recomendado:**
    ```toml
    [gcp_service_account]
    type = "service_account"
    project_id = "tu-project-id"
    private_key_id = "tu-private-key-id"
    private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
    client_email = "tu-email@project.iam.gserviceaccount.com"
    ```
    """)

# Barra de búsqueda de hoteles
st.header("🔍 Búsqueda de Hotel")

if DEMO_MODE:
    hotel_busqueda = st.text_input(
        "Ingresa el nombre del hotel a buscar:",
        placeholder="Ej: Hilton, Marriott, Holiday Inn...",
        disabled=True
    )
    st.info("⏳ Función disponible después de configurar Google Sheets")
else:
    hotel_busqueda = st.text_input(
        "Ingresa el nombre del hotel a buscar:",
        placeholder="Ej: Hilton, Marriott, Holiday Inn...",
        help="Buscará el hotel hasta encontrar 30 precios válidos"
    )

    if hotel_busqueda:
        # Verificar acceso primero
        access_status, message = verify_spreadsheet_access(client, spreadsheet_id)
        if not access_status:
            st.error(message)
        else:
            with st.spinner(f"Buscando '{hotel_busqueda}' hasta encontrar 30 precios..."):
                resultados, precios_encontrados, hojas_revisadas = search_hotel_until_30_prices(
                    client, spreadsheet_id, hotel_busqueda, 100
                )
            
            if resultados:
                # ... (el resto del código de búsqueda permanece igual)
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

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios de hoteles • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)

# Mostrar información de debug en el sidebar
if st.sidebar.checkbox("🔧 Mostrar información de debug"):
    st.sidebar.write("**Secrets disponibles:**", list(st.secrets.keys()) if st.secrets else "Ninguno")
    st.sidebar.write("**Ubicación seleccionada:**", ubicacion)
    st.sidebar.write("**Spreadsheet ID:**", spreadsheet_id)
    st.sidebar.write("**Modo Demo:**", DEMO_MODE)
