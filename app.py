import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime
import numpy as np

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Análisis de Precios",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título de la aplicación
st.title("💰 Sistema de Análisis de Precios")

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

# Función para detectar automáticamente la columna de precios
def detect_price_column(df):
    # Buscar columnas que probablemente contengan precios
    price_keywords = ['precio', 'price', 'costo', 'cost', 'valor', 'value', 'monto', 'amount', 'importe']
    
    for col in df.columns:
        col_lower = str(col).lower()
        # Verificar si el nombre de la columna contiene palabras clave de precio
        if any(keyword in col_lower for keyword in price_keywords):
            # Verificar si la columna contiene valores numéricos
            if pd.api.types.is_numeric_dtype(df[col]) or df[col].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', '').str.isnumeric().any():
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

# Función para calcular métricas de precios
def calculate_price_metrics(df, price_column):
    if df.empty or price_column not in df.columns:
        return None
    
    try:
        # Limpiar y convertir a numérico
        price_series = pd.to_numeric(
            df[price_column].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''), 
            errors='coerce'
        ).dropna()
        
        if len(price_series) == 0:
            return None
            
        precio_min = price_series.min()
        precio_max = price_series.max()
        suma_total = price_series.sum()
        cantidad = len(price_series)
        promedio = suma_total / cantidad if cantidad > 0 else 0
        
        return {
            'precio_min': precio_min,
            'precio_max': precio_max,
            'suma_total': suma_total,
            'cantidad': cantidad,
            'promedio': promedio,
            'valores_validos': len(price_series),
            'valores_totales': len(df[price_column])
        }
    except Exception as e:
        st.error(f"Error al calcular métricas: {e}")
        return None

# Selector de ubicación en el sidebar
st.sidebar.header("📍 Selecciona Ubicación")
ubicacion = st.sidebar.radio("Ubicación:", ["Mérida", "Tuxtla"], index=0)

spreadsheet_id = SHEET_IDS[ubicacion]

# Obtener cliente de Google Sheets
client = setup_gspread()

if client:
    # Modo autenticado - acceso completo a todas las hojas
    with st.spinner("Cargando hojas disponibles..."):
        sheets_dict = get_all_sheets(spreadsheet_id, client)
    
    if sheets_dict:
        # Obtener nombres de hojas
        sheet_names = list(sheets_dict.keys())
        
        # Mostrar selector de hojas en sidebar
        st.sidebar.header("📋 Selecciona Hoja")
        selected_sheet_name = st.sidebar.selectbox(
            "Hoja:",
            sheet_names,
            index=len(sheet_names)-1 if sheet_names else 0
        )
        
        # Obtener datos de la hoja seleccionada
        with st.spinner(f"Cargando {selected_sheet_name}..."):
            selected_sheet = sheets_dict[selected_sheet_name]
            df = get_sheet_data(selected_sheet)
        
        if df is not None and not df.empty:
            # Mostrar información de la hoja
            st.header(f"📊 {ubicacion} - {selected_sheet_name}")
            
            # Detectar automáticamente la columna de precios
            price_column = detect_price_column(df)
            
            if price_column:
                st.success(f"✅ Columna de precios detectada: **{price_column}**")
                
                # Calcular métricas de precios
                metrics = calculate_price_metrics(df, price_column)
                
                if metrics:
                    # Mostrar métricas de precios
                    st.subheader("💰 Análisis de Precios")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Precio Mínimo", f"${metrics['precio_min']:,.2f}")
                    
                    with col2:
                        st.metric("Precio Máximo", f"${metrics['precio_max']:,.2f}")
                    
                    with col3:
                        st.metric("Suma Total", f"${metrics['suma_total']:,.2f}")
                    
                    with col4:
                        st.metric("Promedio Diario", f"${metrics['promedio']:,.2f}")
                    
                    # Mostrar detalles del cálculo
                    with st.expander("📝 Detalles del cálculo"):
                        st.write(f"**Fórmula del promedio:** Suma total / Cantidad de registros")
                        st.write(f"**Suma total:** ${metrics['suma_total']:,.2f}")
                        st.write(f"**Cantidad de registros:** {metrics['cantidad']:,}")
                        st.write(f"**Cálculo:** ${metrics['suma_total']:,.2f} / {metrics['cantidad']:,} = ${metrics['promedio']:,.2f}")
                        st.write(f"**Valores válidos:** {metrics['valores_validos']:,} de {metrics['valores_totales']:,}")
                
                else:
                    st.warning("No se pudieron calcular las métricas de precios.")
            else:
                st.warning("⚠️ No se pudo detectar automáticamente una columna de precios.")
                st.info("Las columnas disponibles son:")
                for col in df.columns:
                    st.write(f"- {col}")
            
            # Mostrar datos
            st.subheader("📋 Datos Completos")
            st.dataframe(df, use_container_width=True, height=300)
            
            # Estadísticas básicas
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if not numeric_cols.empty:
                with st.expander("📈 Estadísticas de columnas numéricas"):
                    st.dataframe(df[numeric_cols].describe())
            
            # Opciones de descarga
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"{ubicacion}_{selected_sheet_name}.csv".replace(" ", "_"),
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("La hoja seleccionada está vacía o no se pudieron cargar los datos.")
    else:
        st.error("No se pudieron cargar las hojas. Verifica los permisos.")
else:
    # Modo público - intentar cargar la hoja principal
    st.warning("🔐 Usando acceso público. Algunas funciones pueden estar limitadas.")
    
    # Para el modo público, necesitaríamos una función alternativa
    st.info("El modo autenticado no está disponible. Configura los secrets para acceso completo.")

# Información adicional en el sidebar
st.sidebar.header("ℹ️ Información")
st.sidebar.info("""
**Análisis de Precios:**
- Precio Mínimo: Valor más bajo
- Precio Máximo: Valor más alto  
- Suma Total: Suma de todos los precios
- Promedio Diario: Suma total / Cantidad
""")

st.sidebar.header("🔗 Enlaces Directos")
for name, sheet_id in SHEET_IDS.items():
    st.sidebar.markdown(f"- [{name}](https://docs.google.com/spreadsheets/d/{sheet_id}/)")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
